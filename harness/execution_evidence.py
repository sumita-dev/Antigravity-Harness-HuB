"""Local, tamper-evident execution receipts; not an OS security boundary."""
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import signal
import sys
import subprocess
import time
import uuid
from datetime import datetime, timezone
import xml.etree.ElementTree as ET


class EvidenceError(ValueError):
    """Missing, failed, stale or tampered execution evidence."""


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _safe(path):
    path = Path(path).absolute()
    for part in [path, *path.parents]:
        if part.is_symlink() or (part.exists() and getattr(os.lstat(part), 'st_file_attributes', 0) & 1024):
            raise EvidenceError('Links/junctions are not permitted')
    return path


def _relative(root, name):
    if not isinstance(name, str) or not name or Path(name).is_absolute() or '..' in Path(name).parts or ':' in name:
        raise EvidenceError('Invalid artifact path')
    result = _safe(root / name)
    if not result.is_relative_to(root):
        raise EvidenceError('Artifact escapes root')
    return result


def normalize_command(command):
    if not isinstance(command, dict):
        raise EvidenceError('Command must be an object')
    argv = command.get('argv', command.get('command'))
    if not isinstance(argv, list) or not argv or any(not isinstance(s, str) or not s or '\x00' in s for s in argv):
        raise EvidenceError('Command requires explicit argv list')
    cwd = command.get('cwd')
    if not isinstance(cwd, str) or not Path(cwd).is_absolute():
        raise EvidenceError('cwd must be absolute')
    cwd = _safe(cwd)
    if not cwd.is_dir():
        raise EvidenceError('cwd is not a directory')
    ac_ids = command.get('ac_ids')
    if not isinstance(ac_ids, list) or not ac_ids or any(not isinstance(s, str) or not s for s in ac_ids) or len(set(ac_ids)) != len(ac_ids):
        raise EvidenceError('Nonempty unique ac_ids required')
    timeout = command.get('timeout', 60)
    if isinstance(timeout, bool) or not isinstance(timeout, (int,float)) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
        raise EvidenceError('Invalid timeout')
    report = command.get('report')
    if report is not None:
        if not isinstance(report, dict) or report.get('kind') not in {'junit','ruff'}:
            raise EvidenceError('Invalid report contract')
        if report.get('path') != 'stdout':
            _relative(cwd, report.get('path'))
        elif report['kind'] != 'ruff':
            raise EvidenceError('Only Ruff supports stdout reports')
    browser = command.get('browser')
    if browser is not None:
        if not isinstance(browser, dict) or not isinstance(browser.get('url'), str) or not browser['url'].startswith(('http://','https://')) or not isinstance(browser.get('assertions'), list) or not browser['assertions']:
            raise EvidenceError('Browser requires URL and assertions')
        for assertion in browser['assertions']:
            if not isinstance(assertion, dict) or not isinstance(assertion.get('selector'), str) or not assertion['selector'] or ('text' in assertion and not isinstance(assertion['text'], str)):
                raise EvidenceError('Invalid browser assertion')
        viewport = browser.get('viewport', {'width':1280,'height':720})
        if not isinstance(viewport,dict) or set(viewport) != {'width','height'} or any(type(v) is not int or not 1 <= v <= 8192 for v in viewport.values()):
            raise EvidenceError('Invalid browser viewport')
        interactions = browser.get('interactions', [])
        if not isinstance(interactions,list):
            raise EvidenceError('Invalid browser interactions')
        for item in interactions:
            if not isinstance(item,dict) or item.get('action') not in {'click','fill'} or not isinstance(item.get('selector'),str) or not item['selector'] or (item['action']=='fill' and not isinstance(item.get('value'),str)):
                raise EvidenceError('Invalid browser interaction')
        for key in ('allow_console_errors','allow_network_errors'):
            values = browser.get(key,[])
            if not isinstance(values,list) or any(not isinstance(v,str) or not v for v in values):
                raise EvidenceError('Invalid browser error allowlist')
    return {'id':command.get('id', command.get('command_id')), 'argv':argv, 'cwd':str(cwd), 'ac_ids':ac_ids, 'timeout':timeout, 'report':report, 'browser':browser}


def _validate_report(kind, data):
    if kind == 'ruff':
        parsed = json.loads(data)
        if not isinstance(parsed, list) or parsed:
            raise EvidenceError('Ruff report must contain zero findings')
        return {'findings':0}
    root = ET.fromstring(data)
    cases = list(root.iter('testcase'))
    if root.tag not in {'testsuites','testsuite'} or not cases:
        raise EvidenceError('JUnit report contains zero tests')
    if any(list(root.iter(tag)) for tag in ('failure','error')):
        raise EvidenceError('JUnit failures/errors')
    if any(int(node.get(key, '0')) > 0 for node in root.iter() for key in ('failures','errors')):
        raise EvidenceError('JUnit failures/errors')
    passed = [case for case in cases if case.find('skipped') is None]
    if not passed:
        raise EvidenceError('JUnit has no executed tests')
    return {'tests':len(cases), 'passed':len(passed)}


def _browser_run(contract, directory, timeout):
    from playwright.sync_api import sync_playwright, expect
    deadline = time.monotonic() + timeout
    errors, network = [], []
    def remaining():
        value = (deadline-time.monotonic())*1000
        if value <= 0:
            raise EvidenceError('Browser total deadline exceeded')
        return value
    with sync_playwright() as engine:
        browser = engine.chromium.launch(headless=True, timeout=remaining())
        try:
            context = browser.new_context(viewport=contract.get('viewport', {'width':1280,'height':720}))
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
            page = context.new_page()
            page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('response', lambda response: network.append(str(response.status)+' '+response.url) if response.status >= 400 else None)
            page.on('requestfailed', lambda request: network.append(request.url+' '+str(request.failure)))
            response = page.goto(contract['url'], wait_until='domcontentloaded', timeout=remaining())
            if response is None or response.status >= 400:
                raise EvidenceError('Browser navigation failed')
            for item in contract.get('interactions',[]):
                locator = page.locator(item['selector'])
                if item['action'] == 'click':
                    locator.click(timeout=remaining())
                else:
                    locator.fill(item['value'], timeout=remaining())
            for item in contract['assertions']:
                locator = page.locator(item['selector'])
                expect(locator).to_be_visible(timeout=remaining())
                if 'text' in item:
                    expect(locator).to_contain_text(item['text'], timeout=remaining())
            page.screenshot(path=str(directory/'browser.png'), full_page=True, timeout=remaining())
            context.tracing.stop(path=str(directory/'trace.zip'))
            unexpected_console = [e for e in errors if not any(allowed in e for allowed in contract.get('allow_console_errors',[]))]
            unexpected_network = [e for e in network if not any(allowed in e for allowed in contract.get('allow_network_errors',[]))]
            if unexpected_console or unexpected_network:
                raise EvidenceError('Browser console/network errors: '+repr(unexpected_console+unexpected_network))
            return {'status':'PASS', 'url':page.url, 'assertions':contract['assertions'], 'console_errors':errors, 'network_errors':network}
        finally:
            browser.close()


class ExecutionEvidenceStore:
    def __init__(self, root):
        self.root = _safe(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.key_path = _safe(self.root/'key.bin')
        try:
            with self.key_path.open('xb') as stream:
                stream.write(os.urandom(32))
        except FileExistsError:
            pass
        if len(self.key_path.read_bytes()) != 32:
            raise EvidenceError('Invalid evidence key')

    def run(self, task_id, actor, spec_sha256, manifest_sha256, argv, cwd, ac_ids, timeout=60, command_id=None, report=None, browser=None):
        for value in (spec_sha256, manifest_sha256):
            if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
                raise EvidenceError('Invalid digest')
        if not all(isinstance(v, str) and v.strip() for v in (task_id, actor)):
            raise EvidenceError('Task and actor required')
        command = normalize_command(dict(id=command_id, argv=argv,cwd=cwd,ac_ids=ac_ids,timeout=timeout,report=report,browser=browser))
        receipt_id = uuid.uuid4().hex
        directory = _safe(self.root/receipt_id)
        directory.mkdir()
        artifacts = {}
        def artifact(name, data):
            path = _relative(directory, name)
            path.write_bytes(data)
            artifacts[name] = _sha(data)
        report_path = None
        stale_report = False
        if report and report['path'] != 'stdout':
            report_path = _relative(Path(command['cwd']), report['path'])
            stale_report = report_path.exists()
        started = datetime.now(timezone.utc).isoformat()
        start = time.monotonic()
        timed_out = False
        error = None
        stdout = stderr = b''
        exit_code = None
        status = 'FAIL'
        execution_context = {'collector':'harness.execution_evidence/v1', 'python_version':sys.version,
            'collector_pid':os.getpid(), 'resolved_executable':None, 'tool_version_status':'NOT_VERIFIED',
            'actor_identity_status':'DECLARED', 'native_isolation_status':'NOT_VERIFIED'}
        try:
            executable = Path(argv[0])
            if executable.is_absolute() or any(separator in argv[0] for separator in ('/', '\\')):
                executable = executable if executable.is_absolute() else Path(command['cwd'])/executable
                resolved = str(_safe(executable).resolve()) if executable.is_file() else None
            else:
                # Never let shutil.which inject the collector's current directory.
                search_dirs = os.environ.get('PATH','').split(os.pathsep)
                if os.name == 'nt':
                    search_dirs.insert(0, command['cwd'])
                extensions = ['']
                if os.name == 'nt' and not executable.suffix:
                    extensions += os.environ.get('PATHEXT','.COM;.EXE;.BAT;.CMD').split(';')
                resolved = None
                for directory in search_dirs:
                    directory = Path(directory)
                    if not directory.is_absolute():
                        directory = Path(command['cwd'])/directory
                    for extension in extensions:
                        candidate = directory/(argv[0]+extension)
                        if candidate.is_file() and os.access(candidate,os.X_OK):
                            resolved = str(candidate)
                            break
                    if resolved:
                        break
            if not resolved:
                raise EvidenceError('Executable not found')
            resolved = str(_safe(resolved).resolve())
            if os.name == 'nt' and Path(resolved).suffix.lower() in {'.bat','.cmd'}:
                raise EvidenceError('Batch commands require a shell; use a direct executable')
            execution_context['resolved_executable'] = resolved
            process = subprocess.Popen([resolved,*argv[1:]], cwd=command['cwd'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
                start_new_session=os.name != 'nt', creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0)
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                if os.name == 'nt':
                    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'], capture_output=True, timeout=10, shell=False)
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                process.kill()
                stdout, stderr = process.communicate(timeout=10)
            exit_code = process.returncode
            status = 'PASS' if exit_code == 0 and not timed_out else 'FAIL'
        except (OSError, subprocess.SubprocessError, EvidenceError) as exc:
            error = str(exc)
        artifact('stdout.bin', stdout)
        artifact('stderr.bin', stderr)
        report_result = None
        browser_result = None
        if report:
            try:
                if stale_report:
                    raise EvidenceError('Declared report existed before execution; use a fresh path')
                data = stdout if report_path is None else _safe(report_path).read_bytes()
                artifact('report.bin',data)
                report_result = _validate_report(report['kind'],data)
            except (ValueError,OSError,ET.ParseError) as exc:
                error, status = str(exc), 'FAIL'
        if browser and status == 'PASS':
            try:
                browser_result = _browser_run(browser,directory,timeout)
                for name in ('browser.png','trace.zip'):
                    data = _safe(directory/name).read_bytes()
                    artifacts[name] = _sha(data)
            except ImportError as exc:
                error, status = str(exc), 'NOT_VERIFIED'
                browser_result = {'status':'NOT_VERIFIED','reason':str(exc)}
            except Exception as exc:
                error, status = str(exc), 'NOT_VERIFIED' if 'Executable doesn' in str(exc) else 'FAIL'
                browser_result = {'status':status,'reason':str(exc)}
        receipt = dict(schema_version=1,receipt_id=receipt_id,task_id=task_id,actor=actor,spec_sha256=spec_sha256,manifest_sha256=manifest_sha256,command=command,
            started_at=started,finished_at=datetime.now(timezone.utc).isoformat(),duration_seconds=time.monotonic()-start,exit_code=exit_code,timed_out=timed_out,status=status,
            execution_context=execution_context,artifacts=artifacts,report_result=report_result,browser_result=browser_result,error=error)
        receipt['receipt_sha256'] = _sha(_canonical(receipt))
        receipt['signature'] = hmac.new(_safe(self.key_path).read_bytes(),_canonical(receipt),hashlib.sha256).hexdigest()
        _safe(directory/'receipt.json').write_bytes(_canonical(receipt))
        return receipt

    def verify(self, receipt_id, *, task_id, actor, spec_sha256, manifest_sha256, command=None):
        if not isinstance(receipt_id,str) or not re.fullmatch('[0-9a-f]{32}',receipt_id):
            raise EvidenceError('Invalid receipt ID')
        try:
            directory = _safe(self.root/receipt_id)
            receipt = json.loads(_safe(directory/'receipt.json').read_bytes())
            unsigned = dict(receipt)
            signature = unsigned.pop('signature')
            expected = hmac.new(_safe(self.key_path).read_bytes(),_canonical(unsigned),hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature,expected):
                raise EvidenceError('Receipt signature mismatch')
            digest = unsigned.pop('receipt_sha256')
            if _sha(_canonical(unsigned)) != digest:
                raise EvidenceError('Receipt digest mismatch')
            bindings = dict(receipt_id=receipt_id,task_id=task_id,actor=actor,spec_sha256=spec_sha256,manifest_sha256=manifest_sha256)
            if any(receipt.get(k) != v for k,v in bindings.items()):
                raise EvidenceError('Receipt binding mismatch')
            if command is not None and normalize_command(command) != receipt['command']:
                raise EvidenceError('Receipt command contract mismatch')
            if receipt.get('schema_version') != 1 or not {'stdout.bin','stderr.bin'} <= set(receipt.get('artifacts',{})):
                raise EvidenceError('Incomplete receipt schema/artifacts')
            contract = normalize_command(receipt['command'])
            if contract['report']:
                if 'report.bin' not in receipt['artifacts'] or not isinstance(receipt.get('report_result'),dict):
                    raise EvidenceError('Missing report evidence')
                _validate_report(contract['report']['kind'], _relative(directory,'report.bin').read_bytes())
            if contract['browser']:
                if receipt.get('browser_result',{}).get('status') != 'PASS' or not {'browser.png','trace.zip'} <= set(receipt['artifacts']):
                    raise EvidenceError('Missing browser evidence')
                if any(not _relative(directory,name).stat().st_size for name in ('browser.png','trace.zip')):
                    raise EvidenceError('Empty browser artifacts')
            if receipt['status'] != 'PASS' or receipt['exit_code'] != 0 or receipt['timed_out']:
                raise EvidenceError('Execution not verified PASS')
            for name,digest in receipt['artifacts'].items():
                if _sha(_relative(directory,name).read_bytes()) != digest:
                    raise EvidenceError('Artifact digest mismatch')
            return receipt
        except (OSError,ValueError,KeyError,TypeError) as exc:
            if isinstance(exc,EvidenceError):
                raise
            raise EvidenceError('Missing or corrupt receipt') from exc

import importlib
import json
import sys
from pathlib import Path
import pytest


def api():
    try:
        return importlib.import_module('harness.execution_evidence')
    except ModuleNotFoundError:
        pytest.fail('Execution evidence adapter missing')


def run(tmp_path, code="print('real output')", **kw):
    store = api().ExecutionEvidenceStore(tmp_path / 'evidence')
    receipt = store.run('task', 'qa', 'a'*64, 'b'*64, [sys.executable, '-c', code], str(tmp_path), ['AC1'], command_id='unit', **kw)
    return store, receipt


def verify(store, receipt, **kw):
    return store.verify(receipt['receipt_id'], task_id='task', actor='qa', spec_sha256='a'*64, manifest_sha256='b'*64, **kw)


def test_real_process_and_tamper(tmp_path):
    store, receipt = run(tmp_path)
    assert receipt['exit_code'] == 0
    assert verify(store, receipt)['status'] == 'PASS'
    artifact = store.root / receipt['receipt_id'] / 'stdout.bin'
    assert artifact.read_bytes().strip() == b'real output'
    artifact.write_bytes(b'fake')
    with pytest.raises(api().EvidenceError):
        verify(store, receipt)


def test_failed_timeout_and_binding_rejected(tmp_path):
    for code, options in [('raise SystemExit(3)', {}), ('import time; time.sleep(5)', {'timeout': .1})]:
        store, receipt = run(tmp_path, code, **options)
        assert receipt['status'] != 'PASS'
        with pytest.raises(api().EvidenceError):
            verify(store, receipt)
    store, receipt = run(tmp_path)
    with pytest.raises(api().EvidenceError):
        store.verify(receipt['receipt_id'], task_id='other', actor='qa', spec_sha256='a'*64, manifest_sha256='b'*64)
    with pytest.raises(api().EvidenceError):
        verify(store, receipt, command={'id':'other','argv':[sys.executable], 'cwd':str(tmp_path),'ac_ids':['AC1']})


@pytest.mark.parametrize('xml', ['<testsuite tests="0"/>', '<testsuite tests="1" failures="1"><testcase><failure/></testcase></testsuite>', '<testsuite tests="1" errors="1"><testcase><error/></testcase></testsuite>'])
def test_invalid_junit_never_passes(tmp_path, xml):
    code = "from pathlib import Path; Path('result.xml').write_text(" + repr(xml) + ")"
    store, receipt = run(tmp_path, code, report={'kind':'junit','path':'result.xml'})
    assert receipt['status'] == 'FAIL'
    with pytest.raises(api().EvidenceError):
        verify(store, receipt)


def test_report_must_be_fresh_and_ruff_json(tmp_path):
    (tmp_path/'old.xml').write_text('<testsuite tests="1"><testcase/></testsuite>')
    _, receipt = run(tmp_path, report={'kind':'junit','path':'old.xml'})
    assert receipt['status'] == 'FAIL'
    _, receipt = run(tmp_path, "print('[]')", report={'kind':'ruff','path':'stdout'})
    assert receipt['status'] == 'PASS'
    _, receipt = run(tmp_path, "print('[{\"code\":\"F401\"}]')", report={'kind':'ruff','path':'stdout'})
    assert receipt['status'] == 'FAIL'


def test_receipt_fabrication_and_traversal(tmp_path):
    store, receipt = run(tmp_path)
    path = store.root/receipt['receipt_id']/'receipt.json'
    data = json.loads(path.read_text()); data['actor'] = 'forged'; path.write_text(json.dumps(data))
    with pytest.raises(api().EvidenceError):
        verify(store, receipt)
    with pytest.raises(api().EvidenceError):
        store.verify('../outside', task_id='task', actor='qa', spec_sha256='a'*64, manifest_sha256='b'*64)
    with pytest.raises(api().EvidenceError):
        run(tmp_path, report={'kind':'junit','path':'../escape'})


def test_browser_unavailable_never_passes(tmp_path, monkeypatch):
    module = api()
    def unavailable(*args):
        raise ImportError('browser unavailable')
    monkeypatch.setattr(module, '_browser_run', unavailable)
    _, receipt = run(tmp_path, browser={'url':'http://localhost:8000','assertions':[{'selector':'h1','text':'Hello'}]})
    assert receipt['status'] == 'NOT_VERIFIED'



def test_valid_junit_and_exact_contract(tmp_path):
    xml = '<testsuite tests="1"><testcase name="real"/></testsuite>'
    code = "from pathlib import Path; Path('fresh.xml').write_text(" + repr(xml) + ")"
    store, receipt = run(tmp_path, code, report={'kind':'junit','path':'fresh.xml'})
    result = verify(store, receipt, command=receipt['command'])
    assert result['report_result']['passed'] == 1
    assert result['artifacts']['report.bin']


def test_browser_artifacts_required_even_when_runner_claims_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(api(), '_browser_run', lambda *args: {'status':'PASS'})
    _, receipt = run(tmp_path, browser={'url':'http://localhost:8000','assertions':[{'selector':'h1'}]})
    assert receipt['status'] == 'FAIL'


def test_cli_emits_real_receipt(tmp_path):
    import subprocess
    contract = tmp_path/'contract.json'
    contract.write_text(json.dumps({'id':'unit','argv':[sys.executable,'-c','print(42)'],'cwd':str(tmp_path),'ac_ids':['AC1']}))
    result = subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'scripts/run_verification.py'),'--store',str(tmp_path/'store'),'--contract',str(contract),'--task-id','task','--actor','qa','--spec-sha256','a'*64,'--manifest-sha256','b'*64],capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['status'] == 'PASS'

@pytest.mark.parametrize('extra',[{'viewport':{'width':0,'height':10}},{'interactions':[{'action':'execute','selector':'h1'}]},{'allow_console_errors':'anything'}])
def test_browser_contract_rejects_unsafe_shapes(tmp_path, extra):
    contract = {'url':'http://localhost:8000','assertions':[{'selector':'h1'}], **extra}
    with pytest.raises(api().EvidenceError):
        run(tmp_path, browser=contract)

@pytest.fixture
def fake_playwright_boundary(monkeypatch):
    """Unit boundary only: runs the real collector without a native browser."""
    from types import ModuleType, SimpleNamespace
    state = SimpleNamespace(events={}, calls=[], inject=None, failure=None, closed=False)
    class Locator:
        def click(self, **kw): state.calls.append(('click', kw))
        def fill(self, value, **kw): state.calls.append(('fill', value, kw))
    class Expect:
        def to_be_visible(self, **kw):
            state.calls.append(('visible', kw))
            if state.failure == 'visible': raise AssertionError('not visible')
        def to_contain_text(self, value, **kw):
            state.calls.append(('text',value,kw))
            if state.failure == 'text': raise AssertionError('text mismatch')
    class Page:
        url = 'http://localhost:8000'
        def on(self, event, callback): state.events[event] = callback
        def goto(self, url, **kw):
            state.calls.append(('goto',url,kw))
            if state.inject:
                event, payload = state.inject
                state.events[event](payload)
            return SimpleNamespace(status=200)
        def locator(self, selector):
            state.calls.append(('locator',selector))
            return Locator()
        def screenshot(self, path, **kw):
            state.calls.append(('screenshot',kw)); Path(path).write_bytes(b'unit png')
    class Tracing:
        def start(self, **kw): state.calls.append(('trace_start',kw))
        def stop(self, path): Path(path).write_bytes(b'unit trace')
    class Browser:
        def new_context(self, **kw):
            state.calls.append(('context',kw))
            return SimpleNamespace(tracing=Tracing(),new_page=lambda:Page())
        def close(self): state.closed=True
    class Engine:
        def __enter__(self): return self
        def __exit__(self, *args): state.calls.append(('engine_exit',))
        @property
        def chromium(self): return self
        def launch(self, **kw):
            state.calls.append(('launch',kw)); return Browser()
    module = ModuleType('playwright.sync_api')
    module.sync_playwright = Engine
    module.expect = lambda locator: Expect()
    monkeypatch.setitem(sys.modules,'playwright.sync_api',module)
    return state


@pytest.mark.parametrize('event,payload', [
    ('console', {'type':'error','text':'console boom'}),
    ('pageerror', 'page boom'),
    ('response', {'status':404,'url':'http://localhost:8000/missing'}),
    ('requestfailed', {'url':'http://localhost:8000/network','failure':'closed'}),
])
def test_real_browser_collector_rejects_error_events(tmp_path, fake_playwright_boundary, event, payload):
    from types import SimpleNamespace
    state = fake_playwright_boundary
    state.inject = (event, SimpleNamespace(**payload) if isinstance(payload,dict) else payload)
    with pytest.raises(api().EvidenceError, match='console/network'):
        api()._browser_run({'url':'http://localhost:8000','assertions':[{'selector':'h1'}]},tmp_path,5)
    assert state.closed
    assert ('engine_exit',) in state.calls


@pytest.mark.parametrize('failure',['visible','text'])
def test_real_browser_collector_rejects_assertion_failures(tmp_path,fake_playwright_boundary,failure):
    state = fake_playwright_boundary
    state.failure = failure
    with pytest.raises(AssertionError):
        api()._browser_run({'url':'http://localhost:8000','assertions':[{'selector':'h1','text':'Hello'}]},tmp_path,5)
    assert state.closed


def test_real_browser_collector_forwards_contract_and_remaining_deadline(tmp_path,fake_playwright_boundary,monkeypatch):
    state = fake_playwright_boundary
    clock = iter([10,10.1,10.2,10.3,10.4,10.5,10.6,10.7])
    monkeypatch.setattr(api().time,'monotonic',lambda:next(clock))
    result = api()._browser_run({'url':'http://localhost:8000','viewport':{'width':900,'height':600},'interactions':[{'action':'click','selector':'button'},{'action':'fill','selector':'input','value':'abc'}],'assertions':[{'selector':'h1','text':'Hello'}]},tmp_path,5)
    assert result['status']=='PASS'
    assert ('context',{'viewport':{'width':900,'height':600}}) in state.calls
    assert any(call[0]=='fill' and call[1]=='abc' for call in state.calls)
    timeouts = [call[-1]['timeout'] for call in state.calls if call[0] in {'launch','goto','click','fill','visible','text','screenshot'}]
    assert len(timeouts)==7 and timeouts == sorted(timeouts,reverse=True)
    assert 0 < timeouts[-1] < timeouts[0] < 5000
    assert next(call for call in state.calls if call[0]=='goto')[2]['wait_until']=='domcontentloaded'
    assert (tmp_path/'browser.png').read_bytes()==b'unit png'
    assert (tmp_path/'trace.zip').read_bytes()==b'unit trace'
    assert state.closed


def test_real_browser_collector_total_deadline_stops_and_cleans_up(tmp_path,fake_playwright_boundary,monkeypatch):
    clock = iter([0,0.1,6])
    monkeypatch.setattr(api().time,'monotonic',lambda:next(clock))
    with pytest.raises(api().EvidenceError,match='deadline'):
        api()._browser_run({'url':'http://localhost:8000','assertions':[{'selector':'h1'}]},tmp_path,5)
    assert fake_playwright_boundary.closed
    assert not any(call[0]=='goto' for call in fake_playwright_boundary.calls)

def test_receipt_has_observed_collector_and_executable_metadata(tmp_path):
    store, receipt = run(tmp_path)
    metadata = verify(store,receipt)['execution_context']
    assert metadata['collector'] == 'harness.execution_evidence/v1'
    assert metadata['python_version'] == sys.version
    assert metadata['collector_pid'] > 0
    assert Path(metadata['resolved_executable']).resolve() == Path(sys.executable).resolve()
    assert metadata['tool_version_status'] == 'NOT_VERIFIED'
    assert metadata['actor_identity_status'] == 'DECLARED'

@pytest.mark.parametrize('prefix',['./', '.\\'])
def test_dot_relative_executable_resolves_from_signed_cwd(tmp_path, monkeypatch, prefix):
    import subprocess
    helper = tmp_path/'verify.exe'
    helper.write_bytes(b'unit executable boundary')
    captured = []
    class Process:
        returncode = 0
        def communicate(self, timeout): return b'observed', b''
    def launch(argv, **kwargs):
        captured.append((argv,kwargs))
        return Process()
    monkeypatch.setattr(subprocess,'Popen',launch)
    store = api().ExecutionEvidenceStore(tmp_path/'evidence')
    receipt = store.run('task','qa','a'*64,'b'*64,[prefix+'verify.exe'],str(tmp_path),['AC1'])
    assert receipt['status'] == 'PASS'
    assert Path(captured[0][0][0]) == helper.resolve()
    assert receipt['execution_context']['resolved_executable'] == str(helper.resolve())

@pytest.mark.skipif(sys.platform != 'win32', reason='Windows current-directory executable search')
def test_windows_bare_executable_uses_signed_cwd_not_collector(tmp_path, monkeypatch):
    import subprocess
    signed = tmp_path/'signed'; signed.mkdir()
    collector = tmp_path/'collector'; collector.mkdir()
    (signed/'verify.exe').write_bytes(b'signed helper')
    (collector/'verify.exe').write_bytes(b'wrong helper')
    monkeypatch.chdir(collector)
    observed = []
    class Process:
        returncode=0
        def communicate(self,timeout): return b'', b''
    monkeypatch.setattr(subprocess,'Popen',lambda argv,**kwargs: (observed.append(argv) or Process()))
    receipt=api().ExecutionEvidenceStore(tmp_path/'store').run('task','qa','a'*64,'b'*64,['verify.exe'],str(signed),['AC1'])
    assert receipt['status']=='PASS'
    assert Path(observed[0][0]) == (signed/'verify.exe').resolve()

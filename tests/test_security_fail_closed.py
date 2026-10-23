import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts import run_security_audit as audit

@pytest.mark.parametrize('manifest,scanner', [('package.json','npm'),('requirements.txt','python')])
def test_required_missing_scanner_is_not_verified(tmp_path, monkeypatch, manifest, scanner):
    (tmp_path / manifest).write_text('{}')
    monkeypatch.setattr(audit.shutil, 'which', lambda _: None)
    report = audit.run_security_audit(tmp_path)
    assert report['passed'] is False
    assert report['status'] == 'NOT_VERIFIED'
    assert report['dependencies'][scanner]['required'] is True

@pytest.mark.parametrize('manifest,scanner', [('package.json','npm'),('requirements.txt','python')])
@pytest.mark.parametrize('output,code', [('',0),('{}',0),('not json',0),('{"error":{"code":"bad"}}',1),('{"metadata":{"vulnerabilities":{"critical":0}}}',2)])
def test_invalid_or_failed_scanner_cannot_pass(tmp_path, monkeypatch, manifest, scanner, output, code):
    (tmp_path / manifest).write_text('{}')
    monkeypatch.setattr(audit.shutil, 'which', lambda name: name)
    monkeypatch.setattr(audit.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=output, returncode=code))
    report = audit.run_security_audit(tmp_path)
    assert report['passed'] is False
    assert report['status'] == 'ERROR'

@pytest.mark.parametrize('manifest', ['package.json','requirements.txt'])
def test_timeout_is_error(tmp_path, monkeypatch, manifest):
    (tmp_path / manifest).write_text('{}')
    monkeypatch.setattr(audit.shutil, 'which', lambda name: name)
    def timeout(*a, **k): raise subprocess.TimeoutExpired('audit', 20)
    monkeypatch.setattr(audit.subprocess, 'run', timeout)
    assert audit.run_security_audit(tmp_path)['status'] == 'ERROR'

@pytest.mark.parametrize('shape', ['list','object'])
def test_pip_counts_vulnerabilities_not_dependencies(tmp_path, monkeypatch, shape):
    (tmp_path / 'requirements.txt').write_text('safe==1\nrisky==1')
    deps = [{'name':'safe','vulns':[]}, {'name':'risky','vulns':[{'id':'a'}, {'id':'b','severity':'HIGH'}]}]
    data = deps if shape == 'list' else {'dependencies':deps}
    monkeypatch.setattr(audit.shutil, 'which', lambda name: name)
    monkeypatch.setattr(audit.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=json.dumps(data), returncode=1))
    report = audit.run_security_audit(tmp_path)
    assert report['summary']['unknown'] == 1
    assert report['summary']['high'] == 1
    assert report['dependencies']['python']['vulnerabilities']['found'] == 2
    assert report['status'] == 'FAIL'
    assert report['passed'] is False

@pytest.mark.parametrize('code', [0,1])
def test_npm_high_blocks_report_and_valid_nonzero_means_findings(tmp_path, monkeypatch, code):
    (tmp_path / 'package.json').write_text('{}')
    monkeypatch.setattr(audit.shutil, 'which', lambda name: name)
    data = {'metadata':{'vulnerabilities':{'critical':0,'high':2,'moderate':0,'low':0}}}
    monkeypatch.setattr(audit.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=json.dumps(data), returncode=code))
    report = audit.run_security_audit(tmp_path)
    assert report['status'] == 'FAIL'
    assert report['summary']['high'] == 2
    assert report['passed'] is False

@pytest.mark.parametrize('folder', ['tests','fixtures','mocks'])
def test_real_secrets_in_test_paths_and_long_lines_are_detected(tmp_path, folder):
    path = tmp_path / folder
    path.mkdir()
    (path / 'test_key.py').write_text('x' * 1100 + ' key="AKIA1234567890ABCDEF" # example')
    assert len(audit.scan_directory_for_secrets(tmp_path)) == 1

def test_comment_or_embedded_dummy_does_not_hide_real_token():
    assert audit.is_safe_dummy_value('sk-abcdefdummy12345678901234567890', '# example') is False

def test_cli_missing_required_scanner_fails_without_flag(tmp_path, monkeypatch, capsys):
    (tmp_path / 'package.json').write_text('{}')
    monkeypatch.setattr(audit.shutil, 'which', lambda _: None)
    monkeypatch.setattr(sys, 'argv', ['audit', '--app-dir', str(tmp_path), '--json'])
    assert audit.main() == 1
    assert json.loads(capsys.readouterr().out)['status'] == 'NOT_VERIFIED'

@pytest.mark.parametrize('data', [{'dependencies':[{'name':'safe','vulns':[]}]}, []])
def test_clean_python_dependencies_pass(tmp_path, monkeypatch, data):
    (tmp_path / 'requirements.txt').write_text('safe==1' if data else '# empty dependencies')
    monkeypatch.setattr(audit.shutil, 'which', lambda name: name)
    monkeypatch.setattr(audit.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=json.dumps(data), returncode=0))
    report = audit.run_security_audit(tmp_path)
    assert report['status'] == 'PASS'
    assert report['summary']['unknown'] == 0

@pytest.mark.parametrize('data', [
    {'dependencies':[{'name':'skipped','skip_reason':'unsupported'}]},
    {'dependencies':[{'name':'broken','vulns':[{}]}]},
    {'metadata':{'vulnerabilities':{'critical':-1,'high':0,'moderate':0,'low':0}}},
    {'metadata':{'vulnerabilities':{'critical':False,'high':0,'moderate':0,'low':0}}},
])
def test_incomplete_dependency_records_fail_closed(tmp_path, monkeypatch, data):
    manifest = 'package.json' if 'metadata' in data else 'requirements.txt'
    (tmp_path / manifest).write_text('{}')
    monkeypatch.setattr(audit.shutil, 'which', lambda name: name)
    monkeypatch.setattr(audit.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=json.dumps(data), returncode=0))
    assert audit.run_security_audit(tmp_path)['status'] == 'ERROR'

def test_critical_only_cli_flag_preserves_high_reporting(tmp_path, monkeypatch, capsys):
    (tmp_path / 'package.json').write_text('{}')
    monkeypatch.setattr(audit.shutil, 'which', lambda name: name)
    data = {'metadata':{'vulnerabilities':{'critical':0,'high':1,'moderate':0,'low':0}}}
    monkeypatch.setattr(audit.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=json.dumps(data), returncode=1))
    monkeypatch.setattr(sys, 'argv', ['audit','--app-dir',str(tmp_path),'--json','--fail-on-critical'])
    assert audit.main() == 0
    assert json.loads(capsys.readouterr().out)['passed'] is True

def test_markdown_explains_unknown_blocking_policy(tmp_path):
    report = audit.run_security_audit(tmp_path)
    text = audit.format_markdown_report(report)
    assert 'UNKNOWN' in text
    assert 'CRITICAL, HIGH, UNKNOWN' in text

@pytest.mark.parametrize('manifest', ['pyproject.toml','Pipfile','poetry.lock','services/api/package.json','services/api/requirements.txt'])
def test_unsupported_or_nested_manifest_is_not_verified(tmp_path, manifest):
    path=tmp_path / manifest
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('{}')
    report=audit.run_security_audit(tmp_path)
    assert report['status'] == 'NOT_VERIFIED'
    assert report['passed'] is False

def test_unreadable_source_is_error(tmp_path, monkeypatch):
    path=tmp_path / 'app.py';path.write_text('safe')
    original=Path.read_text
    def read(self,*args,**kwargs):
        if self == path: raise PermissionError('denied')
        return original(self,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',read)
    assert audit.run_security_audit(tmp_path)['status'] == 'ERROR'

def test_default_cli_fails_on_secret(tmp_path, monkeypatch, capsys):
    (tmp_path / 'key.py').write_text('key="AKIA1234567890ABCDEF"')
    monkeypatch.setattr(sys,'argv',['audit','--app-dir',str(tmp_path),'--json'])
    assert audit.main() == 1

def test_critical_only_policy_matches_report(tmp_path, monkeypatch):
    (tmp_path / 'package.json').write_text('{}')
    monkeypatch.setattr(audit.shutil,'which',lambda name:name)
    data={'metadata':{'vulnerabilities':{'critical':0,'high':1,'moderate':0,'low':0}}}
    monkeypatch.setattr(audit.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout=json.dumps(data),returncode=1))
    report=audit.run_security_audit(tmp_path,fail_on_critical=True)
    assert report['passed'] is True
    assert report['policy']['blocking_severities'] == ['CRITICAL','UNKNOWN']

def test_large_source_is_skipped(tmp_path):
    (tmp_path/'large.py').write_text('x'*(1024*1024+1))
    assert audit.run_security_audit(tmp_path)['status'] == 'PASS'

@pytest.mark.parametrize('data',[[],{'dependencies':[{'vulns':[]}]}])
def test_empty_or_anonymous_pip_result_for_nonempty_target_is_error(tmp_path,monkeypatch,data):
    (tmp_path/'requirements.txt').write_text('safe==1')
    monkeypatch.setattr(audit.shutil,'which',lambda name:name)
    monkeypatch.setattr(audit.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout=json.dumps(data),returncode=0))
    assert audit.run_security_audit(tmp_path)['status'] == 'ERROR'

def test_alternate_requirements_is_not_verified(tmp_path):
    (tmp_path/'requirements-dev.txt').write_text('safe==1')
    assert audit.run_security_audit(tmp_path)['status'] == 'NOT_VERIFIED'

def test_pip_results_must_cover_named_requirement_targets(tmp_path,monkeypatch):
    (tmp_path/'requirements.txt').write_text('safe==1\nmissing-package>=2')
    monkeypatch.setattr(audit.shutil,'which',lambda name:name)
    data={'dependencies':[{'name':'safe','vulns':[]}]}
    monkeypatch.setattr(audit.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout=json.dumps(data),returncode=0))
    assert audit.run_security_audit(tmp_path)['status'] == 'ERROR'

@pytest.mark.parametrize('target', ['missing-package>=2; python_version >= "3"','-r extra.txt','-e git+https://example.invalid/repo.git#egg=missing','https://example.invalid/missing.whl','git+https://example.invalid/repo.git'])
def test_unsupported_requirement_targets_cannot_claim_coverage(tmp_path,monkeypatch,target):
    (tmp_path/'requirements.txt').write_text('safe==1\n'+target)
    monkeypatch.setattr(audit.shutil,'which',lambda name:name)
    data={'dependencies':[{'name':'safe','vulns':[]}]}
    monkeypatch.setattr(audit.subprocess,'run',lambda *a,**k:SimpleNamespace(stdout=json.dumps(data),returncode=0))
    report=audit.run_security_audit(tmp_path)
    assert report['status'] == 'NOT_VERIFIED'
    assert report['passed'] is False

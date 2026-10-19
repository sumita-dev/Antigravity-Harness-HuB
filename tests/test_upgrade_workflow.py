import json
import sys
import pytest
from harness.app_workflow import AppWorkflowStore, WorkflowError

def prepared(tmp_path, **extra):
    project = tmp_path / 'app'; project.mkdir(); (project/'main.py').write_text('x=1')
    store=AppWorkflowStore(tmp_path/'brain'); state=store.create('task','build',project)
    spec=dict(scope='scope',design='design',contracts='contracts',risks='risk',acceptance_criteria=[dict(id='AC1',description='works',ui=False)],verification_commands=[dict(id='test',argv=[sys.executable,'-c','print("ok")'],cwd='.',ac_ids=['AC1'])], **extra)
    state=store.submit_spec('task',spec,'architect'); store.review_design('task','APPROVE','designer',state['spec_sha256'],'reviewed'); store.sign_off('task',state['spec_sha256'],'SIGN_OFF: approved')
    return store,project

def test_default_is_schema3(tmp_path):
    project=tmp_path/'app'; project.mkdir()
    assert AppWorkflowStore(tmp_path/'brain').create('t','build',project)['schema_version']==3

def test_critique_is_independent_current_and_persisted(tmp_path):
    store,project=prepared(tmp_path)
    state=store.submit_implementation('task','maker','implemented')
    assert state['stage']=='CRITIQUE'
    with pytest.raises(WorkflowError): store.review_code('task','APPROVE','maker',state['spec_sha256'],state['manifest_sha256'],'ok')
    state=store.review_code('task','APPROVE','critic',state['spec_sha256'],state['manifest_sha256'],'logic checked')
    assert state['stage']=='AUDIT'
    (project/'main.py').write_text('x=2')
    with pytest.raises(WorkflowError,match='changed'): store.status('task')

def test_critic_budget_persists(tmp_path):
    store,_=prepared(tmp_path)
    for i in range(2):
        state=store.submit_implementation('task','maker','fix')
        state=store.review_code('task','REJECT','critic',state['spec_sha256'],state['manifest_sha256'],'gap')
    assert state['stage']=='ESCALATED'
    assert state['critic_rounds']==2

def test_unexecuted_qa_cannot_approve(tmp_path):
    store,_=prepared(tmp_path); state=store.submit_implementation('task','maker','done')
    store.review_code('task','APPROVE','critic',state['spec_sha256'],state['manifest_sha256'],'ok')
    with pytest.raises(WorkflowError,match='receipt'):
        store.audit('task','APPROVE','qa',dict(report='ok',spec_sha256=state['spec_sha256'],manifest_sha256=state['manifest_sha256'],commands=[dict(id='test',command='echo ok',cwd=state['project_root'],exit_code=0)]))

def test_real_execution_still_requires_allowed_evidence_path(tmp_path):
    store,_=prepared(tmp_path)
    state=store.submit_implementation('task','maker','done')
    store.review_code('task','APPROVE','critic',state['spec_sha256'],state['manifest_sha256'],'ok')
    state=store.execute('task','qa','test')
    receipt=state['execution_receipt']
    evidence=tmp_path/'app'/'proof.txt'
    # Keep evidence outside the source snapshot using a signed external evidence root.
    evidence=tmp_path/'proof.txt'; evidence.write_text('checked')
    payload=dict(report='checked',spec_sha256=state['spec_sha256'],manifest_sha256=state['manifest_sha256'],commands=[dict(id='test',receipt_id=receipt['receipt_id'])],preview=dict(checks=[dict(id='AC1',status='PASS',evidence=str(evidence))]))
    # Explicit allowed evidence root is signed into spec; default project-only evidence must fail closed.
    with pytest.raises(WorkflowError): store.audit('task','APPROVE','qa',payload)


def test_real_receipt_approval_and_tamper_revalidation(tmp_path):
    store,_=prepared(tmp_path,evidence_root=str(tmp_path))
    state=store.submit_implementation('task','maker','done')
    store.review_code('task','APPROVE','critic',state['spec_sha256'],state['manifest_sha256'],'ok')
    state=store.execute('task','qa','test'); receipt=state['execution_receipt']
    proof=tmp_path/'proof.txt'; proof.write_text('checked')
    payload=dict(report='checked',spec_sha256=state['spec_sha256'],manifest_sha256=state['manifest_sha256'],commands=[dict(id='test',receipt_id=receipt['receipt_id'])],preview=dict(checks=[dict(id='AC1',status='PASS',evidence=str(proof))]))
    assert store.audit('task','APPROVE','qa',payload)['stage']=='APPROVED'
    assert store.status('task')['stage']=='APPROVED'
    receipt_path=store.root.parent/'execution_evidence'/receipt['receipt_id']/'receipt.json'
    record=json.loads(receipt_path.read_text()); record['actor']='forged'; receipt_path.write_text(json.dumps(record))
    with pytest.raises(WorkflowError): store.status('task')


def test_source_mutated_by_command_cannot_produce_approval(tmp_path):
    store,project=prepared(tmp_path)
    # Re-sign an explicit command that changes a source file.
    store.revise('task','change verification')
    command=dict(id='mutate',argv=[sys.executable,'-c',"from pathlib import Path; Path('main.py').write_text('changed')"],cwd='.',ac_ids=['AC1'])
    spec=dict(scope='s',design='d',contracts='c',risks='r',acceptance_criteria=[dict(id='AC1',description='works',ui=False)],verification_commands=[command])
    state=store.submit_spec('task',spec,'architect'); store.review_design('task','APPROVE','designer',state['spec_sha256'],'ok');store.sign_off('task',state['spec_sha256'],'SIGN_OFF: approved')
    state=store.submit_implementation('task','maker','done');store.review_code('task','APPROVE','critic',state['spec_sha256'],state['manifest_sha256'],'ok')
    with pytest.raises(WorkflowError,match='changed'):store.execute('task','qa','mutate')

def test_standalone_receipt_not_admitted_without_workflow_snapshot(tmp_path):
    from harness.execution_evidence import ExecutionEvidenceStore
    store,_=prepared(tmp_path,evidence_root=str(tmp_path))
    state=store.submit_implementation('task','maker','done');store.review_code('task','APPROVE','critic',state['spec_sha256'],state['manifest_sha256'],'ok')
    c=state['spec']['verification_commands'][0]
    receipt=ExecutionEvidenceStore(store.root.parent/'execution_evidence').run('task','qa',state['spec_sha256'],state['manifest_sha256'],c['argv'],state['project_root'],c['ac_ids'],command_id='test')
    proof=tmp_path/'proof.txt';proof.write_text('checked')
    with pytest.raises(WorkflowError,match='workflow execute'):
        store.audit('task','APPROVE','qa',dict(report='ok',spec_sha256=state['spec_sha256'],manifest_sha256=state['manifest_sha256'],commands=[dict(id='test',receipt_id=receipt['receipt_id'])],preview=dict(checks=[dict(id='AC1',status='PASS',evidence=str(proof))])))


@pytest.mark.parametrize('module_name',['harness.app_workflow','harness.marketing_workflow'])
def test_checkpoint_permission_retry_imports_time(tmp_path,monkeypatch,module_name):
    import importlib
    module=importlib.import_module(module_name); original=module.os.replace; calls=[]
    def once(source,target):
        calls.append(1)
        if len(calls)==1:raise PermissionError('transient')
        return original(source,target)
    monkeypatch.setattr(module.os,'replace',once)
    if module_name.endswith('app_workflow'):
        project=tmp_path/'project';project.mkdir(); state=module.AppWorkflowStore(tmp_path/'brain').create('retry','retry',project)
    else:
        state=module.MarketingWorkflowStore(tmp_path/'brain').create('retry','retry','content')
    assert state['revision']==1
    assert len(calls)==2


def test_non_ui_manual_browser_cannot_skip_signed_execution_coverage(tmp_path):
    project=tmp_path/'app';project.mkdir();store=AppWorkflowStore(tmp_path/'brain');store.create('task','build',project)
    spec=dict(scope='s',design='d',contracts='c',risks='r',acceptance_criteria=[dict(id='AC1',description='required',ui=False,verification='manual_browser'),dict(id='AC2',description='other',ui=False)],verification_commands=[dict(id='test',argv=[sys.executable,'-c','print(1)'],cwd='.',ac_ids=['AC2'])])
    with pytest.raises(WorkflowError,match='only applies to UI'):store.submit_spec('task',spec,'architect')


def test_maker_execution_receipt_rejected_even_when_claimed_in_audit(tmp_path):
    from harness.execution_evidence import ExecutionEvidenceStore
    store,_=prepared(tmp_path,evidence_root=str(tmp_path));state=store.submit_implementation('task','maker','done');store.review_code('task','APPROVE','critic',state['spec_sha256'],state['manifest_sha256'],'ok')
    c=state['spec']['verification_commands'][0];receipt=ExecutionEvidenceStore(store.root.parent/'execution_evidence').run('task','maker',state['spec_sha256'],state['manifest_sha256'],c['argv'],state['project_root'],c['ac_ids'],command_id='test')
    proof=tmp_path/'proof.txt';proof.write_text('checked')
    with pytest.raises(WorkflowError,match='Independent execution actor'):
        store.audit('task','APPROVE','qa',dict(report='ok',spec_sha256=state['spec_sha256'],manifest_sha256=state['manifest_sha256'],commands=[dict(id='test',receipt_id=receipt['receipt_id'],actor='maker')],preview=dict(checks=[dict(id='AC1',status='PASS',evidence=str(proof))])))


def test_legacy_exhausted_migration_preserves_escalation(tmp_path):
    project=tmp_path/'app';project.mkdir();store=AppWorkflowStore(tmp_path/'brain');store.create('task','build',project)
    path=store._path('task');state=json.loads(path.read_text());state.update(schema_version=2,stage='ESCALATED',next_agent=None);state['reject_counts']['code']=2;path.write_text(json.dumps(state))
    migrated=store.migrate_legacy('task','revalidate')
    assert migrated['schema_version']==3
    assert migrated['stage']=='ESCALATED'
    assert store.status('task')['reject_counts']['code']==2


def test_pending_browser_stage_executes_only_pending_signed_browser_plan(tmp_path,monkeypatch):
    from harness import execution_evidence
    def unavailable(*args):
        raise ImportError("Browser deliberately unavailable at collector boundary")
    monkeypatch.setattr(execution_evidence, "_browser_run", unavailable)
    project=tmp_path/'app';project.mkdir();(project/'main.py').write_text('pass')
    store=AppWorkflowStore(tmp_path/'brain');store.create('task','build',project)
    commands=[dict(id='test',argv=[sys.executable,'-c','print(1)'],cwd='.',ac_ids=['AC1']),dict(id='browser',argv=[sys.executable,'-c','print(1)'],cwd='.',ac_ids=['UI'],timeout=1,browser=dict(url='http://localhost:49999',assertions=[dict(selector='body')]))]
    spec=dict(scope='s',design='d',contracts='c',risks='r',evidence_root=str(tmp_path),acceptance_criteria=[dict(id='AC1',description='works',ui=False),dict(id='UI',description='visible',ui=True)],verification_commands=commands)
    state=store.submit_spec('task',spec,'architect');store.review_design('task','APPROVE','designer',state['spec_sha256'],'ok');store.sign_off('task',state['spec_sha256'],'SIGN_OFF: approved')
    state=store.submit_implementation('task','maker','done');store.review_code('task','APPROVE','critic',state['spec_sha256'],state['manifest_sha256'],'ok');state=store.execute('task','qa','test')
    proof=tmp_path/'proof.txt';proof.write_text('checked')
    store.audit('task','PARTIAL_APPROVE','qa',dict(report='UI pending',spec_sha256=state['spec_sha256'],manifest_sha256=state['manifest_sha256'],commands=[dict(id='test',receipt_id=state['execution_receipt']['receipt_id'])],preview=dict(url='http://localhost:49999',checks=[dict(id='AC1',status='PASS',evidence=str(proof)),dict(id='UI',status='NOT_VERIFIED',reason='browser unavailable')])))
    with pytest.raises(WorkflowError,match='only permits signed browser'):store.execute('task','browser-reviewer','test')
    result=store.execute('task','browser-reviewer','browser')
    assert result['stage']=='AUDIT_PENDING_BROWSER'
    assert result['execution_receipt']['receipt_id'] in result['execution_runs']
    assert result['browser_status']=='NOT_VERIFIED'

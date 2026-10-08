import importlib
import json
from pathlib import Path

import pytest


def store(tmp_path):
    module = importlib.import_module('harness.marketing_workflow')
    return module.MarketingWorkflowStore(tmp_path), module.WorkflowError


def fixture(tmp_path, mode='content', status='verified'):
    workflow, error = store(tmp_path)
    workflow.create('task', 'Marketing brief', mode)
    evidence = tmp_path / 'source.txt'
    evidence.write_text('Source reports 12 customers.', encoding='utf-8')
    dossier = {'schema_version': 1, 'brief': 'Marketing brief',
               'sources': [{'id': 's1', 'reference': 'https://example.org/report',
                            'retrieved_at': '2026-10-08', 'evidence': str(evidence)}],
               'claims': [{'id': 'c1', 'statement': '12 customers', 'source_ids': ['s1'],
                           'status': status, 'units': 'customers', 'timeframe': '2026'}],
               'limitations': ['Small sample']}
    state = workflow.submit_dossier('task', 'researcher', dossier)
    if mode == 'content':
        draft = tmp_path / 'draft.txt'
        draft.write_text('12 customers', encoding='utf-8')
        state = workflow.submit_content('task', 'creator', {
            'dossier_sha256': state['dossier_sha256'], 'artifacts': [{'path': str(draft)}],
            'claim_checks': [{'claim_id': 'c1', 'artifact': str(draft),
                              'location': '12 customers', 'label': 'factual'}]})
    return workflow, error, state, dossier


def approval(tmp_path, state):
    report = tmp_path / 'audit.txt'
    report.write_text('Sources, claims, policy, integrity and task quality checked.', encoding='utf-8')
    return {'verdict': 'APPROVE', 'report': str(report),
            'dossier_sha256': state['dossier_sha256'],
            'artifacts_sha256': state.get('artifacts_sha256'),
            'baseline_sha256': state['baseline_sha256'],
            'claim_checks': [{'claim_id': 'c1', 'status': 'PASS', 'evidence': str(report)}],
            'checklist': [{'id': check, 'status': 'PASS', 'evidence': str(report)}
                          for check in state['required_checks']]}


def test_module_is_available():
    assert importlib.util.find_spec('harness.marketing_workflow') is not None


@pytest.mark.parametrize('mode', ['content', 'research-only'])
def test_real_workflows_require_independent_audit(tmp_path, mode):
    workflow, error, state, _ = fixture(tmp_path, mode)
    assert state['stage'] == 'AUDIT'
    payload = approval(tmp_path, state)
    with pytest.raises(error):
        workflow.audit('task', 'researcher', payload)
    if mode == 'content':
        with pytest.raises(error):
            workflow.audit('task', 'creator', payload)
    assert workflow.audit('task', 'checker', payload)['stage'] == 'APPROVED'
    assert workflow.status('task')['next_agent'] is None


@pytest.mark.parametrize('mutation', ['claims', 'checklist', 'binding'])
def test_missing_or_stale_coverage_cannot_approve(tmp_path, mutation):
    workflow, error, state, _ = fixture(tmp_path)
    payload = approval(tmp_path, state)
    if mutation == 'claims':
        payload['claim_checks'] = []
    elif mutation == 'checklist':
        payload['checklist'] = []
    else:
        payload['dossier_sha256'] = '0' * 64
    with pytest.raises(error):
        workflow.audit('task', 'checker', payload)


@pytest.mark.parametrize('file', ['source.txt', 'draft.txt', 'audit.txt'])
def test_changed_bytes_invalidate_approval(tmp_path, file):
    workflow, error, state, _ = fixture(tmp_path)
    workflow.audit('task', 'checker', approval(tmp_path, state))
    (tmp_path / file).write_text('Changed bytes', encoding='utf-8')
    with pytest.raises(error):
        workflow.status('task')


def test_unverified_assertion_and_unlabelled_assumption_fail(tmp_path):
    workflow, error, state, _ = fixture(tmp_path, status='unverified')
    with pytest.raises(error):
        workflow.audit('task', 'checker', approval(tmp_path, state))
    workflow, error, state, dossier = fixture(tmp_path / 'assumption', mode='research-only', status='assumption')
    # Research-only claims already carry an explicit assumption label in the dossier.
    assert workflow.audit('task', 'checker', approval(tmp_path / 'assumption', state))['stage'] == 'APPROVED'


def test_reject_counts_survive_revision_restart_and_replacement(tmp_path):
    workflow, error, state, dossier = fixture(tmp_path)
    payload = approval(tmp_path, state)
    payload['verdict'] = 'REJECT'
    assert workflow.audit('task', 'checker', payload)['reject_counts']['audit'] == 1
    workflow.revise('task', 'Fix research')
    workflow, error = store(tmp_path)
    state = workflow.submit_dossier('task', 'researcher', dossier)
    draft = tmp_path / 'draft.txt'
    state = workflow.submit_content('task', 'creator', {'dossier_sha256': state['dossier_sha256'],
        'artifacts': [{'path': str(draft)}], 'claim_checks': [{'claim_id': 'c1', 'artifact': str(draft),
        'location': '12 customers', 'label': 'factual'}]})
    payload = approval(tmp_path, state)
    payload['verdict'] = 'REJECT'
    assert workflow.audit('task', 'checker', payload)['stage'] == 'ESCALATED'
    with pytest.raises(error):
        workflow.revise('task', 'Try again')


def test_replacement_clears_audit_and_publishing(tmp_path):
    workflow, error, state, dossier = fixture(tmp_path)
    workflow.audit('task', 'checker', approval(tmp_path, state))
    request = {'action': 'post', 'destination': 'page', 'content': '12 customers', 'media': [], 'schedule': None}
    record = workflow.prepare_publish('task', 'operator', request)
    workflow.authorize_publish('task', record['publish_id'], 'PUBLISH: approved')
    state = workflow.submit_dossier('task', 'researcher', dossier)
    assert state['stage'] == 'CREATION'
    assert state['publishing'] == {}
    assert state['audit'] is None


def test_publish_timeout_requires_explicit_reconciliation(tmp_path):
    workflow, error, state, _ = fixture(tmp_path)
    workflow.audit('task', 'checker', approval(tmp_path, state))
    request = {'action': 'post', 'destination': 'page', 'content': '12 customers', 'media': [], 'schedule': None}
    record = workflow.prepare_publish('task', 'operator', request)
    with pytest.raises(error):
        workflow.validate_publish('task', record['publish_id'], request)
    workflow.authorize_publish('task', record['publish_id'], 'PUBLISH: approved')
    assert workflow.validate_publish('task', record['publish_id'], request)['status'] == 'UNKNOWN'
    with pytest.raises(error):
        workflow.validate_publish('task', record['publish_id'], request)
    evidence = tmp_path / 'reconcile.txt'
    evidence.write_text('External API confirms no post was created.', encoding='utf-8')
    workflow.reconcile_publish('task', record['publish_id'], 'operator', {'status': 'FAILED', 'evidence': str(evidence)})
    assert workflow.status('task')['publishing'][record['publish_id']]['status'] == 'FAILED'


def test_invalid_identifiers_corruption_and_concurrent_lock_fail_closed(tmp_path):
    workflow, error = store(tmp_path)
    for identity in ['../escape', 'CON', '', 'nested/id']:
        with pytest.raises(error):
            workflow.create(identity, 'brief', 'content')
    workflow.create('task', 'brief', 'content')
    path = tmp_path / 'marketing_workflows' / 'task.json'
    lock = path.with_suffix('.lock')
    lock.write_text('locked')
    with pytest.raises(error):
        workflow.revise('task', 'reason')
    lock.unlink()
    path.write_text('{corrupt')
    with pytest.raises(error):
        workflow.status('task')


def test_creator_cannot_reduce_baseline(tmp_path):
    workflow, error, state, _ = fixture(tmp_path)
    with pytest.raises(error):
        workflow.submit_content('task', 'creator', {'dossier_sha256': state['dossier_sha256'],
            'required_checks': [], 'artifacts': [{'path': str(tmp_path / 'draft.txt')}], 'claim_checks': []})


def test_cli_has_distinct_marketing_checkpoint_mode(tmp_path, monkeypatch, capsys):
    import run_harness
    monkeypatch.setenv('HARNESS_BRAIN_DIR', str(tmp_path))
    assert run_harness.main(['--marketing-workflow', 'init', '--task-id', 'cli', '--task', 'Research brief',
                             '--marketing-mode', 'research-only', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['stage'] == 'RESEARCH'
    assert run_harness.main(['--marketing-workflow', 'status', '--task-id', 'cli', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['next_agent'] == 'web_researcher'


def test_cli_legacy_recovery_calls_explicit_migration(tmp_path, monkeypatch, capsys):
    import run_harness
    calls = []
    class RecoveryStore:
        def migrate_legacy(self, task_id, reason):
            calls.append((task_id, reason))
            return {'task_id': task_id, 'stage': 'DESIGN', 'next_agent': 'architect', 'revision': 4}
    monkeypatch.setattr(run_harness, 'AppWorkflowStore', RecoveryStore)
    payload = tmp_path / 'recovery.json'
    payload.write_text(json.dumps({'reason': 'Explicit legacy evidence revalidation'}), encoding='utf-8')
    assert run_harness.main(['--workflow', 'migrate-legacy', '--task-id', 'legacy',
                             '--payload', str(payload), '--json']) == 0
    assert calls == [('legacy', 'Explicit legacy evidence revalidation')]
    assert json.loads(capsys.readouterr().out)['stage'] == 'DESIGN'


def test_cli_mutually_exclusive_workflow_modes_and_unknown_task_fail(tmp_path, monkeypatch, capsys):
    import run_harness
    monkeypatch.setenv('HARNESS_BRAIN_DIR', str(tmp_path))
    with pytest.raises(SystemExit) as failure:
        run_harness.main(['--workflow', 'status', '--marketing-workflow', 'status', '--task-id', 'missing'])
    assert failure.value.code == 2
    capsys.readouterr()
    assert run_harness.main(['--marketing-workflow', 'status', '--task-id', 'missing', '--json']) == 1
    assert 'error' in json.loads(capsys.readouterr().out)


def test_content_assumption_requires_visible_label(tmp_path):
    workflow, error, state, _ = fixture(tmp_path, status='assumption')
    with pytest.raises(error):
        workflow.audit('task', 'checker', approval(tmp_path, state))
    draft = tmp_path / 'draft.txt'
    draft.write_text('Assumption: 12 customers', encoding='utf-8')
    state = workflow.submit_content('task', 'creator', {'dossier_sha256': state['dossier_sha256'],
        'artifacts': [{'path': str(draft)}], 'claim_checks': [{'claim_id': 'c1', 'artifact': str(draft),
        'location': 'Assumption: 12 customers', 'label': 'assumption'}]})
    assert workflow.audit('task', 'checker', approval(tmp_path, state))['stage'] == 'APPROVED'


def test_excluded_claim_cannot_still_be_asserted_in_draft(tmp_path):
    workflow, error, state, _ = fixture(tmp_path, status='unverified')
    draft = tmp_path / 'draft.txt'
    state = workflow.submit_content('task', 'creator', {'dossier_sha256': state['dossier_sha256'],
        'artifacts': [{'path': str(draft)}], 'claim_checks': [{'claim_id': 'c1', 'artifact': str(draft),
        'location': 'Intentionally excluded', 'label': 'excluded'}]})
    with pytest.raises(error):
        workflow.audit('task', 'checker', approval(tmp_path, state))


def test_unknown_attempt_cannot_be_erased_by_dossier_replacement(tmp_path):
    workflow, error, state, dossier = fixture(tmp_path)
    workflow.audit('task', 'checker', approval(tmp_path, state))
    request = {'action': 'post', 'destination': 'page', 'content': '12 customers', 'media': [], 'schedule': None}
    record = workflow.prepare_publish('task', 'operator', request)
    workflow.authorize_publish('task', record['publish_id'], 'PUBLISH: approved')
    workflow.validate_publish('task', record['publish_id'], request)
    state = workflow.submit_dossier('task', 'researcher', dossier)
    draft = tmp_path / 'draft.txt'
    state = workflow.submit_content('task', 'creator', {'dossier_sha256': state['dossier_sha256'],
        'artifacts': [{'path': str(draft)}], 'claim_checks': [{'claim_id': 'c1', 'artifact': str(draft),
        'location': '12 customers', 'label': 'factual'}]})
    workflow.audit('task', 'checker', approval(tmp_path, state))
    with pytest.raises(error):
        workflow.prepare_publish('task', 'operator', request)
    evidence = tmp_path / 'reconcile.txt'
    evidence.write_text('The external system confirms no write.', encoding='utf-8')
    assert workflow.reconcile_publish('task', record['publish_id'], 'operator',
        {'status': 'FAILED', 'evidence': str(evidence)})['status'] == 'FAILED'
    assert workflow.prepare_publish('task', 'operator', request)['status'] == 'PREPARED'


@pytest.mark.parametrize('field', ['dossier', 'content', 'audit'])
def test_internally_hashed_but_malformed_checkpoint_fails_closed(tmp_path, field):
    from hashlib import sha256
    workflow, error, state, _ = fixture(tmp_path)
    workflow.audit('task', 'checker', approval(tmp_path, state))
    path = tmp_path / 'marketing_workflows' / 'task.json'
    state = json.loads(path.read_text(encoding='utf-8'))
    state[field] = {}
    state[field + '_sha256'] = sha256(b'{}').hexdigest()
    path.write_text(json.dumps(state), encoding='utf-8')
    with pytest.raises(error):
        workflow.status('task')


def test_publish_binds_media_bytes_and_exact_request(tmp_path):
    workflow, error, state, _ = fixture(tmp_path)
    workflow.audit('task', 'checker', approval(tmp_path, state))
    media = tmp_path / 'image.png'
    media.write_bytes(b'original image')
    request = {'action': 'post-photo', 'destination': 'page', 'content': '12 customers',
               'media': [str(media)], 'schedule': None}
    record = workflow.prepare_publish('task', 'operator', request)
    workflow.authorize_publish('task', record['publish_id'], 'PUBLISH: approved')
    with pytest.raises(error):
        workflow.validate_publish('task', record['publish_id'], {**request, 'destination': 'different-page'})
    media.write_bytes(b'replaced image')
    with pytest.raises(error):
        workflow.validate_publish('task', record['publish_id'], request)


def test_publish_preserves_exact_content_and_raw_authorization(tmp_path):
    workflow, error, state, _ = fixture(tmp_path)
    workflow.audit('task', 'checker', approval(tmp_path, state))
    request = {'action': 'post', 'destination': 'page', 'content': '12 customers', 'media': [], 'schedule': None}
    record = workflow.prepare_publish('task', 'operator', request)
    raw = '  PUBLISH: approved\n'
    assert workflow.authorize_publish('task', record['publish_id'], raw)['raw_authorization'] == raw
    with pytest.raises(error):
        workflow.validate_publish('task', record['publish_id'], {**request, 'content': ' 12 customers'})


def test_unsent_preparation_can_be_replaced_after_revision(tmp_path):
    workflow, error, state, dossier = fixture(tmp_path)
    workflow.audit('task', 'checker', approval(tmp_path, state))
    request = {'action': 'post', 'destination': 'page', 'content': '12 customers', 'media': [], 'schedule': None}
    workflow.prepare_publish('task', 'operator', request)
    state = workflow.submit_dossier('task', 'researcher', dossier)
    draft = tmp_path / 'draft.txt'
    state = workflow.submit_content('task', 'creator', {'dossier_sha256': state['dossier_sha256'],
        'artifacts': [{'path': str(draft)}], 'claim_checks': [{'claim_id': 'c1', 'artifact': str(draft),
        'location': '12 customers', 'label': 'factual'}]})
    workflow.audit('task', 'checker', approval(tmp_path, state))
    assert workflow.prepare_publish('task', 'operator', request)['status'] == 'PREPARED'


def test_unknown_blocks_new_request_until_reconciled(tmp_path):
    workflow, error, state, _ = fixture(tmp_path)
    workflow.audit('task', 'checker', approval(tmp_path, state))
    request = {'action': 'post', 'destination': 'page', 'content': '12 customers', 'media': [], 'schedule': None}
    record = workflow.prepare_publish('task', 'operator', request)
    workflow.authorize_publish('task', record['publish_id'], 'PUBLISH: approved')
    workflow.validate_publish('task', record['publish_id'], request)
    with pytest.raises(error):
        workflow.prepare_publish('task', 'operator', {**request, 'destination': 'different-page'})


def test_already_prepared_second_request_cannot_bypass_unknown(tmp_path):
    workflow, error, state, _ = fixture(tmp_path)
    workflow.audit('task', 'checker', approval(tmp_path, state))
    request = {'action': 'post', 'destination': 'page', 'content': '12 customers', 'media': [], 'schedule': None}
    first = workflow.prepare_publish('task', 'operator', request)
    second_request = {**request, 'destination': 'second-page'}
    second = workflow.prepare_publish('task', 'operator', second_request)
    for record in (first, second):
        workflow.authorize_publish('task', record['publish_id'], 'PUBLISH: approved')
    workflow.validate_publish('task', first['publish_id'], request)
    with pytest.raises(error):
        workflow.validate_publish('task', second['publish_id'], second_request)


@pytest.mark.parametrize('invalid', ['sources', 'source_reference', 'claim_reference', 'claim_status', 'empty_evidence'])
def test_invalid_dossier_fails_closed(tmp_path, invalid):
    workflow, error, _, dossier = fixture(tmp_path)
    if invalid == 'sources':
        dossier['sources'] = []
    elif invalid == 'source_reference':
        dossier['sources'][0]['reference'] = ''
    elif invalid == 'claim_reference':
        dossier['claims'][0]['source_ids'] = ['missing-source']
    elif invalid == 'claim_status':
        dossier['claims'][0]['status'] = 'trusted'
    else:
        (tmp_path / 'source.txt').write_text('')
    with pytest.raises(error):
        workflow.submit_dossier('task', 'researcher', dossier)


def test_evidence_outside_brain_and_symlink_rejected(tmp_path):
    workflow, error, state, dossier = fixture(tmp_path)
    outside = tmp_path.parent / 'outside.txt'
    outside.write_text('source', encoding='utf-8')
    dossier['sources'][0]['evidence'] = str(outside)
    with pytest.raises(error):
        workflow.submit_dossier('task', 'researcher', dossier)
    link = tmp_path / 'linked.txt'
    try:
        link.symlink_to(tmp_path / 'source.txt')
    except OSError:
        pytest.skip('Symlink privilege unavailable')
    dossier['sources'][0]['evidence'] = str(link)
    with pytest.raises(error):
        workflow.submit_dossier('task', 'researcher', dossier)


@pytest.mark.parametrize('raw', [
    'Do not publish this post', 'No', 'yes', 'APPROVE', 'Publish exact request',
    'If the checker approves, PUBLISH: approved', 'PUBLISH: approved only after review',
    'Do not PUBLISH: approved', 'PUBLISH: approved\nDo not send', '', None,
    'S\u1ebfp: Duy\u1ec7t \u0111\u0103ng b\u00e0i n\u00e0y n\u1ebfu \u0111\u1ee7 \u0111i\u1ec1u ki\u1ec7n',
])
def test_publish_consent_denial_ambiguity_and_conditions_are_rejected(tmp_path, raw):
    workflow, error, state, _ = fixture(tmp_path)
    workflow.audit('task', 'checker', approval(tmp_path, state))
    request = {'action': 'post', 'destination': 'page', 'content': '12 customers', 'media': [], 'schedule': None}
    record = workflow.prepare_publish('task', 'operator', request)
    revision = workflow.status('task')['revision']
    with pytest.raises(error):
        workflow.authorize_publish('task', record['publish_id'], raw)
    current = workflow.status('task')
    assert current['revision'] == revision
    assert current['publishing'][record['publish_id']]['status'] == 'PREPARED'
    assert current['publishing'][record['publish_id']]['raw_authorization'] is None


@pytest.mark.parametrize('raw', [
    'PUBLISH: approved', '  publish: APPROVED\n',
    'Duy\u1ec7t \u0111\u0103ng b\u00e0i n\u00e0y',
    'S\u1ebfp: Duy\u1ec7t \u0111\u0103ng b\u00e0i n\u00e0y',
    'S\u1ebfp: PUBLISH: approved',
])
def test_exact_affirmative_consent_preserves_raw_and_allows_bound_attempt(tmp_path, raw):
    workflow, error, state, _ = fixture(tmp_path)
    workflow.audit('task', 'checker', approval(tmp_path, state))
    request = {'action': 'post', 'destination': 'page', 'content': '12 customers', 'media': [], 'schedule': None}
    record = workflow.prepare_publish('task', 'operator', request)
    consent = workflow.authorize_publish('task', record['publish_id'], raw)
    assert consent['raw_authorization'] == raw
    assert consent['authorization_binding_sha256'] == record['binding_sha256']
    assert workflow.validate_publish('task', record['publish_id'], request)['status'] == 'UNKNOWN'


@pytest.mark.parametrize('raw', ['Do not publish this post', 'PUBLISH: approved if reviewed',
                               'Authorize this exact request.', None])
def test_legacy_or_tampered_prepared_authorization_is_revalidated(tmp_path, raw):
    workflow, error, state, _ = fixture(tmp_path)
    workflow.audit('task', 'checker', approval(tmp_path, state))
    request = {'action': 'post', 'destination': 'page', 'content': '12 customers', 'media': [], 'schedule': None}
    record = workflow.prepare_publish('task', 'operator', request)
    workflow.authorize_publish('task', record['publish_id'], 'PUBLISH: approved')
    checkpoint = tmp_path / 'marketing_workflows' / 'task.json'
    state = json.loads(checkpoint.read_text(encoding='utf-8'))
    state['publishing'][record['publish_id']]['raw_authorization'] = raw
    checkpoint.write_text(json.dumps(state), encoding='utf-8')
    with pytest.raises(error):
        workflow.validate_publish('task', record['publish_id'], request)
    assert workflow.status('task')['publishing'][record['publish_id']]['status'] == 'PREPARED'

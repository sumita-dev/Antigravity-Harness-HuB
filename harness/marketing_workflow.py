"""Local evidence checkpoints for native marketing agents; no agent/network execution.

Actor IDs and authorization text are submitted provenance, not authenticated identity.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from uuid import uuid4

from harness.app_workflow import WorkflowError
from harness.skills.router import DEFAULT_CONFIG, SkillLoader, SkillRouter


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise WorkflowError(f'{name} must be a nonempty string')
    return value.strip()


def _publish_consent(raw_authorization):
    message = _text(raw_authorization, 'raw authorization record')
    grammar = r'(?:S\u1ebfp:\s*)?(?:Duy\u1ec7t \u0111\u0103ng b\u00e0i n\u00e0y|PUBLISH: approved)'
    if not re.fullmatch(grammar, message, re.I):
        raise WorkflowError('Explicit whole publish approval required: Duy\u1ec7t \u0111\u0103ng b\u00e0i n\u00e0y / PUBLISH: approved')


def _safe_path(value):
    path = Path(value).absolute()
    if '..' in path.parts or any(part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction())
                               for part in (path, *path.parents)):
        raise WorkflowError('Traversal, symlink or junction path is forbidden')
    return path.resolve()


class MarketingWorkflowStore:
    NEXT_AGENT = {'RESEARCH': 'web_researcher', 'CREATION': 'creator',
                  'AUDIT': 'compliance_critic', 'APPROVED': None, 'ESCALATED': None}
    REQUIRED_CHECKS = ['source_accuracy', 'policy', 'integrity', 'task_quality']

    def __init__(self, root=None):
        self.brain = _safe_path(root or os.environ.get('HARNESS_BRAIN_DIR',
                                Path(__file__).resolve().parents[1] / '.brain'))
        self.root = _safe_path(self.brain / 'marketing_workflows')
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, task_id):
        if not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', task_id):
            raise WorkflowError('Invalid task ID')
        if task_id.upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)),
                              *(f'LPT{i}' for i in range(1, 10))}:
            raise WorkflowError('Reserved task ID')
        return _safe_path(self.root / f'{task_id}.json')

    @contextmanager
    def _locked(self, task_id):
        path = self._path(task_id)
        lock = _safe_path(path.with_suffix('.lock'))
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise WorkflowError('Task is locked; verify abandoned writer before removing lock') from exc
        try:
            os.close(fd)
            yield path
        finally:
            lock.unlink()

    def _save(self, path, state, action, actor):
        state['revision'] += 1
        state['next_agent'] = self.NEXT_AGENT[state['stage']]
        state['events'].append({'revision': state['revision'], 'action': action, 'actor': actor,
                                'stage': state['stage'], 'timestamp': datetime.now(timezone.utc).isoformat()})
        temporary = _safe_path(path.with_suffix('.tmp'))
        try:
            with temporary.open('w', encoding='utf-8') as stream:
                json.dump(state, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.replace(temporary, path)
            except PermissionError:
                time.sleep(0.02)
                os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return state

    def _load(self, path):
        try:
            state = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise WorkflowError('Cannot read marketing checkpoint') from exc
        if not isinstance(state, dict) or state.get('schema_version') != 1 or state.get('task_id') != path.stem:
            raise WorkflowError('Corrupt checkpoint identity/schema')
        if state.get('stage') not in self.NEXT_AGENT or state.get('next_agent') != self.NEXT_AGENT[state['stage']]:
            raise WorkflowError('Corrupt stage routing')
        if type(state.get('revision')) is not int or state['revision'] < 1 or not isinstance(state.get('events'), list):
            raise WorkflowError('Corrupt revision/history')
        if not isinstance(state.get('actors'), dict) or not isinstance(state.get('publishing'), dict) or not isinstance(state.get('publish_history'), list):
            raise WorkflowError('Corrupt actors/publishing')
        if not isinstance(state.get('reject_counts'), dict) or type(state['reject_counts'].get('audit')) is not int or state['reject_counts']['audit'] < 0:
            raise WorkflowError('Corrupt reject counter')
        if state['reject_counts']['audit'] >= 2 and state['stage'] != 'ESCALATED':
            raise WorkflowError('Corrupt circuit breaker')
        baseline = state.get('baseline')
        if not isinstance(baseline, dict) or _hash(_canonical(baseline)) != state.get('baseline_sha256'):
            raise WorkflowError('Corrupt baseline binding')
        if baseline.get('required_checks') != self.REQUIRED_CHECKS or state.get('required_checks') != self.REQUIRED_CHECKS:
            raise WorkflowError('Corrupt required checklist')
        if baseline.get('brief') != state.get('task') or baseline.get('mode') != state.get('mode') or state.get('mode') not in {'content', 'research-only'}:
            raise WorkflowError('Corrupt immutable brief/mode')
        for key in ('dossier', 'content', 'audit'):
            value = state.get(key)
            if value is not None and (not isinstance(value, dict) or _hash(_canonical(value)) != state.get(f'{key}_sha256')):
                raise WorkflowError(f'Corrupt {key} binding')
        if state.get('dossier') and (not isinstance(state['dossier'].get('sources'), list)
                or not state['dossier']['sources'] or not isinstance(state['dossier'].get('claims'), list)
                or not state['dossier']['claims'] or state['dossier'].get('baseline_sha256') != state['baseline_sha256']):
            raise WorkflowError('Malformed dossier')
        if state.get('content') and (not isinstance(state['content'].get('artifacts'), list)
                or not state['content']['artifacts'] or not isinstance(state['content'].get('claim_checks'), list)):
            raise WorkflowError('Malformed content')
        if state.get('audit') and (not isinstance(state['audit'].get('claim_checks'), list)
                or not isinstance(state['audit'].get('checklist'), list)
                or not isinstance(state['audit'].get('report'), dict)):
            raise WorkflowError('Malformed audit')
        if state.get('content') and _hash(_canonical(state['content']['artifacts'])) != state.get('artifacts_sha256'):
            raise WorkflowError('Corrupt artifact binding')
        if state['stage'] in {'CREATION', 'AUDIT', 'APPROVED'} and not state.get('dossier'):
            raise WorkflowError('Missing dossier')
        if state['stage'] in {'AUDIT', 'APPROVED'} and state['mode'] == 'content' and not state.get('content'):
            raise WorkflowError('Missing draft')
        if state['stage'] == 'APPROVED' and (not state.get('audit') or state['audit'].get('verdict') != 'APPROVE'):
            raise WorkflowError('Missing approval')
        return state

    def _open(self, state):
        if state['stage'] == 'ESCALATED':
            raise WorkflowError('ESCALATED task cannot reopen; explicit human direction requires a new linked task')

    def _evidence(self, value):
        path = _safe_path(_text(value, 'evidence path'))
        if not path.is_relative_to(self.brain) or not path.is_file():
            raise WorkflowError('Evidence must be a file under the configured brain directory')
        data = path.read_bytes()
        if not data:
            raise WorkflowError('Empty evidence')
        return {'path': str(path), 'sha256': _hash(data)}

    def _fresh(self, record):
        if not isinstance(record, dict) or self._evidence(record.get('path')) != record:
            raise WorkflowError('Stale evidence bytes')

    def _binding(self, state, payload):
        for key in ('dossier_sha256', 'artifacts_sha256', 'baseline_sha256'):
            if payload.get(key) != state.get(key):
                raise WorkflowError(f'Stale or missing {key}')

    def _coverage(self, items, ids, name, id_key):
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise WorkflowError(f'Invalid {name}')
        actual = [item.get(id_key) for item in items]
        if len(actual) != len(set(str(item) for item in actual)) or set(str(item) for item in actual) != set(ids):
            raise WorkflowError(f'{name} must cover every ID exactly once')

    def _current(self, state, approved=False):
        if approved and state['stage'] != 'APPROVED':
            raise WorkflowError('Current APPROVED audit required')
        dossier = state.get('dossier')
        if dossier:
            for source in dossier['sources']:
                self._fresh(source['evidence'])
        content = state.get('content')
        if content:
            if content['dossier_sha256'] != state['dossier_sha256'] or content['baseline_sha256'] != state['baseline_sha256']:
                raise WorkflowError('Stale draft binding')
            for record in content['artifacts']:
                self._fresh(record)
        audit = state.get('audit')
        if approved:
            self._binding(state, audit)
            checker = state['actors'].get('checker')
            if not checker or checker in {state['actors'].get('researcher'), state['actors'].get('creator')}:
                raise WorkflowError('Independent checker required')
            self._fresh(audit['report'])
            for row in audit['claim_checks'] + audit['checklist']:
                self._fresh(row['evidence'])
            self._validate_approval(state, audit, normalized=True)

    def create(self, task_id, task, mode):
        task = _text(task, 'task')
        if mode not in {'content', 'research-only'}:
            raise WorkflowError('mode must be content or research-only')
        config = DEFAULT_CONFIG.read_bytes()
        skill_name, _ = SkillRouter().route(task)
        skill_path = SkillLoader().find_skill_path(skill_name)
        baseline = {'brief': task, 'mode': mode, 'required_checks': list(self.REQUIRED_CHECKS),
                    'config_sha256': _hash(config), 'skill': {'name': skill_name,
                    'sha256': _hash(Path(skill_path).read_bytes()) if skill_path else None}}
        with self._locked(task_id) as path:
            if path.exists():
                raise WorkflowError('Task already exists')
            state = {'schema_version': 1, 'task_id': task_id, 'task': task, 'mode': mode,
                     'stage': 'RESEARCH', 'revision': 0, 'events': [], 'actors': {},
                     'reject_counts': {'audit': 0}, 'baseline': baseline,
                     'baseline_sha256': _hash(_canonical(baseline)), 'required_checks': list(self.REQUIRED_CHECKS),
                     'dossier': None, 'content': None, 'audit': None, 'publishing': {}, 'publish_history': []}
            return self._save(path, state, 'init', 'orchestrator')

    def _clear(self, state, dossier=False):
        keys = ['content', 'audit', 'content_sha256', 'artifacts_sha256', 'audit_sha256']
        if dossier:
            keys += ['dossier', 'dossier_sha256']
        for key in keys:
            state[key] = None
        # Invalidating approval must not erase an uncertain external side effect.
        state['publish_history'].extend({**row, 'invalidated': True} for row in state['publishing'].values())
        state['publishing'] = {}
        state['actors'].pop('checker', None)
        state['actors'].pop('creator', None)
        if dossier:
            state['actors'].pop('researcher', None)

    def submit_dossier(self, task_id, actor, payload):
        actor = _text(actor, 'actor')
        with self._locked(task_id) as path:
            state = self._load(path)
            self._open(state)
            if not isinstance(payload, dict) or payload.get('schema_version') != 1 or payload.get('brief') != state['task']:
                raise WorkflowError('Dossier schema/brief mismatch')
            sources, claims = payload.get('sources'), payload.get('claims')
            if not isinstance(sources, list) or not sources or not isinstance(claims, list) or not claims:
                raise WorkflowError('Sources and claims must be nonempty lists')
            normalized_sources, source_ids = [], set()
            for row in sources:
                if not isinstance(row, dict):
                    raise WorkflowError('Invalid source')
                identity = _text(row.get('id'), 'source id')
                if identity in source_ids:
                    raise WorkflowError('Duplicate source ID')
                source_ids.add(identity)
                normalized_sources.append({'id': identity, 'reference': _text(row.get('reference'), 'reference'),
                    'retrieved_at': _text(row.get('retrieved_at'), 'retrieved_at'),
                    'evidence': self._evidence(row.get('evidence'))})
            normalized_claims, claim_ids = [], set()
            for row in claims:
                if not isinstance(row, dict):
                    raise WorkflowError('Invalid claim')
                identity = _text(row.get('id'), 'claim id')
                refs = row.get('source_ids')
                if identity in claim_ids or not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or ref not in source_ids for ref in refs) or len(set(refs)) != len(refs):
                    raise WorkflowError('Invalid claim IDs/source references')
                claim_ids.add(identity)
                if row.get('status') not in {'verified', 'assumption', 'unverified'}:
                    raise WorkflowError('Invalid claim status')
                normalized_claims.append({'id': identity, 'statement': _text(row.get('statement'), 'statement'),
                    'source_ids': refs, 'status': row['status'], 'units': _text(row.get('units'), 'units'),
                    'timeframe': _text(row.get('timeframe'), 'timeframe')})
            limitations = payload.get('limitations')
            if not isinstance(limitations, list) or any(not isinstance(item, str) or not item.strip() for item in limitations):
                raise WorkflowError('limitations must be a string list')
            dossier = {'schema_version': 1, 'brief': state['task'], 'sources': normalized_sources,
                       'claims': normalized_claims, 'limitations': limitations, 'baseline_sha256': state['baseline_sha256']}
            self._clear(state)
            state.update(dossier=dossier, dossier_sha256=_hash(_canonical(dossier)),
                         stage='AUDIT' if state['mode'] == 'research-only' else 'CREATION')
            state['actors']['researcher'] = actor
            return self._save(path, state, 'research', actor)

    def submit_content(self, task_id, actor, payload):
        actor = _text(actor, 'actor')
        with self._locked(task_id) as path:
            state = self._load(path)
            self._open(state)
            if state['mode'] != 'content' or state['stage'] not in {'CREATION', 'AUDIT', 'APPROVED'}:
                raise WorkflowError('Content requires a dossier in content mode')
            if not isinstance(payload, dict) or payload.get('dossier_sha256') != state['dossier_sha256']:
                raise WorkflowError('Stale dossier binding')
            if 'required_checks' in payload and payload['required_checks'] != state['required_checks']:
                raise WorkflowError('Creator cannot reduce the required checklist')
            # A replacement can repair stale draft bytes, but cannot use stale sources.
            for source in state['dossier']['sources']:
                self._fresh(source['evidence'])
            artifacts = payload.get('artifacts')
            if not isinstance(artifacts, list) or not artifacts or any(not isinstance(row, dict) for row in artifacts):
                raise WorkflowError('Missing content artifacts')
            artifacts = [self._evidence(row.get('path')) for row in artifacts]
            if len({row['path'] for row in artifacts}) != len(artifacts):
                raise WorkflowError('Duplicate artifacts')
            checks = payload.get('claim_checks')
            self._coverage(checks, [row['id'] for row in state['dossier']['claims']], 'claim_checks', 'claim_id')
            paths = {row['path'] for row in artifacts}
            normalized = []
            for row in checks:
                label = row.get('label')
                if label not in {'factual', 'assumption', 'excluded'}:
                    raise WorkflowError('Invalid claim label')
                artifact = str(_safe_path(_text(row.get('artifact'), 'claim artifact')))
                location = _text(row.get('location'), 'claim location/excerpt')
                if artifact not in paths:
                    raise WorkflowError('Claim artifact not submitted')
                if label != 'excluded' and location not in Path(artifact).read_text(encoding='utf-8'):
                    raise WorkflowError('Claim excerpt must occur in the artifact')
                normalized.append({'claim_id': row['claim_id'], 'artifact': artifact, 'location': location, 'label': label})
            self._clear(state)
            content = {'dossier_sha256': state['dossier_sha256'], 'baseline_sha256': state['baseline_sha256'],
                       'artifacts': artifacts, 'claim_checks': normalized}
            state.update(content=content, content_sha256=_hash(_canonical(content)),
                         artifacts_sha256=_hash(_canonical(artifacts)), stage='AUDIT')
            state['actors']['creator'] = actor
            return self._save(path, state, 'content', actor)

    def _validate_approval(self, state, payload, normalized=False):
        claims = state['dossier']['claims']
        self._coverage(payload.get('claim_checks'), [row['id'] for row in claims], 'audit claim checks', 'claim_id')
        self._coverage(payload.get('checklist'), state['required_checks'], 'audit checklist', 'id')
        for row in payload['claim_checks'] + payload['checklist']:
            if row.get('status') != 'PASS':
                raise WorkflowError('Every required audit check must PASS')
            if normalized:
                self._fresh(row.get('evidence'))
            else:
                self._evidence(row.get('evidence'))
        by_id = {row['claim_id']: row for row in state['content']['claim_checks']} if state.get('content') else {}
        for claim in claims:
            check = by_id.get(claim['id'])
            if check and check['label'] == 'excluded':
                if any(claim['statement'] in Path(row['path']).read_text(encoding='utf-8')
                       for row in state['content']['artifacts']):
                    raise WorkflowError('Excluded claim statement is still present in a draft')
                continue
            if claim['status'] == 'unverified':
                raise WorkflowError('Unverified factual claim cannot APPROVE')
            if claim['status'] == 'assumption' and check:
                if check['label'] != 'assumption' or not re.search(r'(?i)(assumption|gi\u1ea3 \u0111\u1ecbnh)\s*:', check['location']):
                    raise WorkflowError('Assumptions must be visibly labelled in the exact artifact excerpt')
            if claim['status'] == 'verified' and check and check['label'] not in {'factual', 'assumption'}:
                raise WorkflowError('Invalid factual coverage')

    def audit(self, task_id, actor, payload):
        actor = _text(actor, 'actor')
        with self._locked(task_id) as path:
            state = self._load(path)
            self._open(state)
            if state['stage'] != 'AUDIT' or not isinstance(payload, dict):
                raise WorkflowError('Audit requires AUDIT stage')
            if actor in {state['actors'].get('researcher'), state['actors'].get('creator')}:
                raise WorkflowError('Checker must differ from researcher and creator')
            self._binding(state, payload)
            self._current(state)
            verdict = payload.get('verdict')
            if verdict not in {'APPROVE', 'REJECT', 'ESCALATE'}:
                raise WorkflowError('Invalid verdict')
            report = self._evidence(payload.get('report'))
            if verdict == 'APPROVE':
                self._validate_approval(state, payload)
            audit = {'verdict': verdict, 'report': report, 'dossier_sha256': state['dossier_sha256'],
                     'artifacts_sha256': state.get('artifacts_sha256'), 'baseline_sha256': state['baseline_sha256'],
                     'claim_checks': [], 'checklist': []}
            if verdict == 'APPROVE':
                for key in ('claim_checks', 'checklist'):
                    audit[key] = [{**row, 'evidence': self._evidence(row['evidence'])} for row in payload[key]]
            state['actors']['checker'] = actor
            state['audit'], state['audit_sha256'] = audit, _hash(_canonical(audit))
            state['publishing'] = {}
            if verdict == 'REJECT':
                state['reject_counts']['audit'] += 1
            state['stage'] = ('ESCALATED' if verdict == 'ESCALATE' or state['reject_counts']['audit'] >= 2
                              else 'APPROVED' if verdict == 'APPROVE' else
                              'RESEARCH' if state['mode'] == 'research-only' else 'CREATION')
            return self._save(path, state, 'audit', actor)

    def revise(self, task_id, reason):
        reason = _text(reason, 'revision reason')
        with self._locked(task_id) as path:
            state = self._load(path)
            self._open(state)
            self._clear(state, dossier=True)
            state['stage'] = 'RESEARCH'
            state['revision_reason'] = reason
            return self._save(path, state, 'revise', 'orchestrator')

    def status(self, task_id):
        with self._locked(task_id) as path:
            state = self._load(path)
            self._current(state, approved=state['stage'] == 'APPROVED')
            return state

    def _publish_payload(self, state, payload):
        if not isinstance(payload, dict):
            raise WorkflowError('Publish payload must be an object')
        _text(payload.get('content'), 'publish content')
        content = payload['content']
        if not state.get('content') or content not in [Path(row['path']).read_bytes().decode('utf-8')
                                                      for row in state['content']['artifacts']]:
            raise WorkflowError('Publish content must match an approved artifact exactly')
        media = payload.get('media', [])
        if not isinstance(media, list):
            raise WorkflowError('media must be a path list')
        records = [self._evidence(item) for item in media]
        schedule = payload.get('schedule')
        if schedule is not None:
            schedule = _text(schedule, 'schedule')
        return {'action': _text(payload.get('action'), 'action'),
                'destination': _text(payload.get('destination'), 'destination'),
                'content': content, 'media': records, 'schedule': schedule,
                'dossier_sha256': state['dossier_sha256'], 'artifacts_sha256': state['artifacts_sha256'],
                'audit_sha256': state['audit_sha256'], 'baseline_sha256': state['baseline_sha256']}

    def prepare_publish(self, task_id, actor, payload):
        actor = _text(actor, 'actor')
        with self._locked(task_id) as path:
            state = self._load(path)
            self._current(state, approved=True)
            binding = self._publish_payload(state, payload)
            digest = _hash(_canonical(binding))
            request_digest = _hash(_canonical({key: binding[key] for key in ('action', 'destination', 'content', 'media', 'schedule')}))
            all_records = [*state['publishing'].values(), *state['publish_history']]
            if any(row.get('status') == 'UNKNOWN' for row in all_records):
                raise WorkflowError('Unresolved UNKNOWN attempt blocks writes until reconciliation')
            if any(row.get('request_sha256') == request_digest and row.get('status') == 'SUCCEEDED'
                   for row in all_records) or any(row.get('request_sha256') == request_digest and row.get('status') == 'PREPARED'
                                                 for row in state['publishing'].values()):
                raise WorkflowError('An unresolved/prepared/succeeded matching publish already exists')
            identity = uuid4().hex
            record = {'publish_id': identity, 'binding': binding, 'binding_sha256': digest, 'request_sha256': request_digest,
                      'status': 'PREPARED', 'raw_authorization': None, 'actor': actor}
            state['publishing'][identity] = record
            self._save(path, state, 'publish-prepare', actor)
            return record

    def _publish_record(self, state, publish_id, historical=False):
        record = state['publishing'].get(publish_id)
        if record is None and historical:
            record = next((row for row in state['publish_history'] if row.get('publish_id') == publish_id), None)
        if not isinstance(record, dict) or _hash(_canonical(record.get('binding'))) != record.get('binding_sha256'):
            raise WorkflowError('Missing/corrupt publish record')
        binding = record['binding']
        if not historical:
            for key in ('dossier_sha256', 'artifacts_sha256', 'audit_sha256', 'baseline_sha256'):
                if binding.get(key) != state.get(key):
                    raise WorkflowError('Stale publish approval')
            for media in binding['media']:
                self._fresh(media)
        return record

    def authorize_publish(self, task_id, publish_id, raw_authorization):
        _publish_consent(raw_authorization)
        with self._locked(task_id) as path:
            state = self._load(path)
            self._current(state, approved=True)
            record = self._publish_record(state, publish_id)
            if record['status'] != 'PREPARED':
                raise WorkflowError('Only a prepared request may be authorized')
            record['raw_authorization'] = raw_authorization
            record['authorization_binding_sha256'] = record['binding_sha256']
            self._save(path, state, 'publish-authorize', 'submitted_authorization')
            return record

    def validate_publish(self, task_id, publish_id, payload):
        with self._locked(task_id) as path:
            state = self._load(path)
            self._current(state, approved=True)
            record = self._publish_record(state, publish_id)
            if record['status'] != 'PREPARED' or not record.get('raw_authorization') or record.get('authorization_binding_sha256') != record['binding_sha256']:
                raise WorkflowError('Missing authorization or unresolved/finished attempt; reconcile UNKNOWN before retry')
            _publish_consent(record['raw_authorization'])
            if any(row.get('status') == 'UNKNOWN' for row in [*state['publishing'].values(), *state['publish_history']]):
                raise WorkflowError('Unresolved UNKNOWN attempt blocks writes until reconciliation')
            if _hash(_canonical(self._publish_payload(state, payload))) != record['binding_sha256']:
                raise WorkflowError('Publish request differs from authorized binding')
            # Persist UNKNOWN before the caller crosses the network boundary.
            record['status'] = 'UNKNOWN'
            self._save(path, state, 'publish-attempt', record['actor'])
            return record

    def record_publish(self, task_id, publish_id, status, external_id=None, error=None):
        if status not in {'SUCCEEDED', 'FAILED', 'UNKNOWN'}:
            raise WorkflowError('Invalid publish outcome')
        with self._locked(task_id) as path:
            state = self._load(path)
            record = self._publish_record(state, publish_id)
            if record['status'] != 'UNKNOWN':
                raise WorkflowError('Only an in-flight UNKNOWN attempt can record an outcome')
            if status == 'SUCCEEDED':
                record['external_id'] = _text(external_id, 'external_id')
            elif external_id is not None:
                raise WorkflowError('External ID requires API success')
            record['status'], record['error'] = status, str(error) if error is not None else None
            self._save(path, state, 'publish-outcome', record['actor'])
            return record

    def reconcile_publish(self, task_id, publish_id, actor, payload):
        actor = _text(actor, 'actor')
        if not isinstance(payload, dict) or payload.get('status') not in {'SUCCEEDED', 'FAILED'}:
            raise WorkflowError('Reconciliation requires confirmed SUCCEEDED or FAILED status')
        with self._locked(task_id) as path:
            state = self._load(path)
            record = self._publish_record(state, publish_id, historical=True)
            if record['status'] != 'UNKNOWN':
                raise WorkflowError('Only UNKNOWN attempts need reconciliation')
            evidence = self._evidence(payload.get('evidence'))
            if payload['status'] == 'SUCCEEDED':
                record['external_id'] = _text(payload.get('external_id'), 'external_id')
            record['status'] = payload['status']
            record['reconciliation'] = {'actor': actor, 'evidence': evidence}
            self._save(path, state, 'publish-reconcile', actor)
            return record

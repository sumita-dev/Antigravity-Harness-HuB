import copy
import pytest
from harness.traceability import validate_traceability, ready_tasks


def spec():
    return {'requirements': [{'id': 'R1'}], 'acceptance_criteria': [{'id': 'A1'}],
            'verification_commands': [{'id': 'V1', 'ac_ids': ['A1']}],
            'tasks': [{'id': 'T1', 'requirement_ids': ['R1'], 'ac_ids': ['A1'], 'depends_on': [], 'owned_paths': ['src/']},
                      {'id': 'T2', 'requirement_ids': ['R1'], 'ac_ids': ['A1'], 'depends_on': ['T1'], 'owned_paths': ['tests/']}]}


def test_valid_map_and_only_approved_dependencies_are_ready():
    s = spec()
    validate_traceability(s)
    assert ready_tasks(s, {}) == ['T1']
    assert ready_tasks(s, {'T1': 'PASS'}) == []
    assert ready_tasks(s, {'T1': 'APPROVED'}) == ['T2']


@pytest.mark.parametrize('change,match', [
    (lambda s: s['tasks'][0].update(depends_on=['T2']), 'cycle'),
    (lambda s: s['tasks'][1].update(depends_on=['missing']), 'reference'),
    (lambda s: s['tasks'][1].update(owned_paths=['src/file.py'], depends_on=[]), 'ownership'),
    (lambda s: s['tasks'][0].update(owned_paths=['../secret']), 'path'),
    (lambda s: s['requirements'].append({'id': 'R2'}), 'coverage'),
    (lambda s: s['verification_commands'][0].update(ac_ids=[]), 'coverage'),
    (lambda s: s['tasks'][0].update(ac_ids=['missing']), 'reference'),
    (lambda s: s['tasks'].append(copy.deepcopy(s['tasks'][0])), 'Duplicate'),
])
def test_invalid_maps_rejected(change, match):
    s = spec()
    change(s)
    with pytest.raises(ValueError, match=match):
        validate_traceability(s)


def test_parallel_disjoint_tasks_ready_and_legacy_spec_optional():
    s = spec()
    s['tasks'][1]['depends_on'] = []
    assert ready_tasks(s, {}) == ['T1', 'T2']
    validate_traceability({'acceptance_criteria': [{'id': 'legacy'}]})

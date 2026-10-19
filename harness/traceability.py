"""Small signed-spec traceability validator; no execution or approval authority."""
from pathlib import PurePosixPath


def _index(items, label):
    if not isinstance(items, list) or not items:
        raise ValueError(f'{label} must be a nonempty list')
    result = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id'].strip() or item['id'] != item['id'].strip():
            raise ValueError(f'Invalid {label} id')
        if item['id'] in result:
            raise ValueError(f'Duplicate {label} id')
        result[item['id']] = item
    return result


def _refs(item, field, allowed, required=False):
    refs = item.get(field, [])
    if not isinstance(refs, list) or any(not isinstance(x, str) for x in refs) or len(set(refs)) != len(refs):
        raise ValueError(f'Invalid {field} references')
    if not set(refs) <= set(allowed):
        raise ValueError(f'Unknown {field} reference')
    if required and not refs:
        raise ValueError(f'Missing {field} coverage')
    return refs


def validate_traceability(spec):
    """Validate optional requirements/tasks against existing AC/command fields.

    Absent requirements and tasks retain compatibility with earlier signed specs.
    Once either is supplied both are mandatory; every requirement and applicable
    AC needs task coverage, and applicable ACs need declared verification coverage.
    Shared owned paths are allowed only between transitively ordered tasks.
    """
    if not isinstance(spec, dict):
        raise ValueError('spec must be an object')
    if 'tasks' not in spec and 'requirements' not in spec:
        return
    requirements = _index(spec.get('requirements'), 'requirements')
    tasks = _index(spec.get('tasks'), 'tasks')
    criteria = _index(spec.get('acceptance_criteria'), 'acceptance_criteria')
    commands = _index(spec.get('verification_commands'), 'verification_commands')
    required_ac = {key for key, ac in criteria.items() if ac.get('applicable', True)}
    covered_r, covered_a, verified = set(), set(), set()
    dependencies, paths = {}, {}
    for key, task in tasks.items():
        covered_r.update(_refs(task, 'requirement_ids', requirements, True))
        covered_a.update(_refs(task, 'ac_ids', criteria, True))
        dependencies[key] = _refs(task, 'depends_on', tasks)
        owned = task.get('owned_paths', [])
        if not isinstance(owned, list):
            raise ValueError('owned_paths must be a list')
        paths[key] = []
        for raw in owned:
            if not isinstance(raw, str) or not raw.strip():
                raise ValueError('Invalid owned path')
            normalized = raw.replace('\\', '/')
            path = PurePosixPath(normalized)
            if path.is_absolute() or ':' in normalized or '..' in path.parts or '*' in normalized or '?' in normalized:
                raise ValueError('Unsafe owned path')
            paths[key].append(path.as_posix().casefold().rstrip('/'))
    ancestors = {}
    def visit(key, active):
        if key in active:
            raise ValueError('Task dependency cycle')
        if key not in ancestors:
            chain = set(dependencies[key])
            for parent in dependencies[key]:
                chain.update(visit(parent, active | {key}))
            ancestors[key] = chain
        return ancestors[key]
    for key in tasks:
        visit(key, set())
    for left in tasks:
        for right in tasks:
            if left >= right or left in ancestors[right] or right in ancestors[left]:
                continue
            for a in paths[left]:
                for b in paths[right]:
                    if a == '.' or b == '.' or a == b or a.startswith(b + '/') or b.startswith(a + '/'):
                        raise ValueError(f'Parallel ownership conflict: {left}, {right}')
    for command in commands.values():
        verified.update(_refs(command, 'ac_ids', criteria, True))
    for ac in criteria.values():
        _refs(ac, 'requirement_ids', requirements)
        declared = _refs(ac, 'verification_ids', commands)
        if any(ac['id'] not in commands[c].get('ac_ids', []) for c in declared):
            raise ValueError('AC verification reference lacks reciprocal coverage')
    if covered_r != set(requirements) or not required_ac <= covered_a or not required_ac <= verified:
        raise ValueError('Incomplete requirement/AC/verification coverage')


def ready_tasks(spec, statuses):
    """Return unstarted tasks whose prerequisites have independent APPROVED status."""
    validate_traceability(spec)
    return [task['id'] for task in spec.get('tasks', [])
            if task['id'] not in statuses and all(statuses.get(dep) == 'APPROVED' for dep in task.get('depends_on', []))]

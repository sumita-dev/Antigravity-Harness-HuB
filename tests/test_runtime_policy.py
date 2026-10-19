import pytest
from harness.policy import resolve_runtime_policy


def test_explicit_tier_resolves_config_model_without_claiming_native_enforcement():
    policy = resolve_runtime_policy('qa_auditor', metadata={'model': 'flash', 'enable_subagent_tools': False})
    assert policy['model_tier'] == 'flash'
    assert policy['model_preference'] == 'Gemini 3.8 Flash'
    assert policy['enforcement'] == 'DECLARED'
    assert policy['allow_nested_subagents'] is False


def test_metadata_mismatch_and_unknown_role_fail_explicitly():
    with pytest.raises(ValueError, match='model'):
        resolve_runtime_policy('qa_auditor', metadata={'model': 'inherit'})
    with pytest.raises(ValueError, match='role'):
        resolve_runtime_policy('invented')


def test_dispatch_export_uses_resolved_app_model_policy():
    from scripts.dispatch_subagents import parse_agent_file
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'agents/app/qa_auditor.md'
    data = parse_agent_file(path)
    assert data['model'] == 'flash'
    assert data['model_preference'] == 'Gemini 3.8 Flash'
    assert data['runtime_policy']['enforcement'] == 'DECLARED'


def test_dispatch_cli_composes_real_stage_stack_risk_and_dependency_closure():
    import json
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    run = subprocess.run([sys.executable, str(root / 'scripts/dispatch_subagents.py'),
        '--export-schema', 'builder', '--stage', 'IMPLEMENTATION', '--stack', 'database',
        '--risk', 'high'], cwd=root, capture_output=True, text=True, encoding='utf-8')
    assert run.returncode == 0, run.stderr
    data = json.loads(run.stdout)
    selection = data['skill_selection']
    assert {'database-migrations', 'security-review', 'test-driven-development'} <= set(selection['skills'])
    assert selection['stage'] == 'IMPLEMENTATION'
    assert selection['chars'] <= 64000
    assert selection['instructions']
    design = subprocess.run([sys.executable, str(root / 'scripts/dispatch_subagents.py'),
        '--export-schema', 'architect', '--stage', 'DESIGN', '--stack', 'ui'],
        cwd=root, capture_output=True, text=True, encoding='utf-8')
    assert design.returncode == 0, design.stderr
    selected = json.loads(design.stdout)['skill_selection']['skills']
    assert {'app', 'karpathy-coder', 'test-driven-development', 'accessibility'} <= set(selected)


def test_dispatch_defaults_use_audit_stage_and_e2e_role_profile():
    from pathlib import Path
    from scripts.dispatch_subagents import parse_agent_file
    root = Path(__file__).resolve().parents[1]
    qa = parse_agent_file(root / 'agents/app/qa_auditor.md')
    assert qa['skill_selection']['stage'] == 'AUDIT'
    assert 'verification-before-completion' in qa['skill_selection']['skills']
    e2e = parse_agent_file(root / 'agents/app/e2e_engineer.md')
    assert {'verify-ui', 'accessibility'} <= set(e2e['skill_selection']['skills'])

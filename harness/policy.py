"""Declared dispatch preferences; this module does not invoke native models."""
import json
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / 'configs' / 'harness_config.json'


def resolve_runtime_policy(role, config=None, metadata=None):
    if config is None:
        config = json.loads(DEFAULT_CONFIG.read_text(encoding='utf-8'))
    elif isinstance(config, (str, Path)):
        config = json.loads(Path(config).read_text(encoding='utf-8'))
    tier = config.get('roles', {}).get(role)
    if tier is None:
        raise ValueError(f'Unknown role: {role}')
    model = config.get('models', {}).get(tier)
    if not model:
        raise ValueError(f'Unknown model tier: {tier}')
    metadata = metadata or {}
    declared = metadata.get('model', tier)
    if declared != tier:
        raise ValueError(f'Declared model {declared} disagrees with configured {tier}')
    if metadata.get('enable_subagent_tools', False):
        raise ValueError('Nested subagents prohibited; Chief dispatches decomposition')
    return {'role': role, 'model_tier': tier, 'model_preference': model,
            'allow_nested_subagents': False, 'dispatch_owner': 'chief', 'enforcement': 'DECLARED'}

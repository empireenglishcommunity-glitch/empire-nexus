"""Regression: config must be importable at module scope in api_server.

The submit-recording + pronunciation-check paths reference `config.*` directly
(scoring budget, audio cap, teacher-feed channel). A missing module-level import
caused a live 'name config is not defined' NameError that silently failed every
shadow scoring. This locks it.
"""
from src import api_server, config


def test_api_server_config_in_scope():
    assert api_server.config is config
    assert isinstance(api_server.config.NUTQ_SCORE_BUDGET_SECONDS, (int, float))
    assert isinstance(api_server.config.NUTQ_AZURE_MAX_AUDIO_SECONDS, int)

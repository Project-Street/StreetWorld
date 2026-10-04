"""
Lazy exports for env classes.

This keeps `GrpcClientEnv` usable in lightweight client-only setups without
pulling simulator-side dependencies at import time.
"""

from importlib import import_module
from typing import Any, List

__all__ = [
    "ScenarioEnv",
    "BaseEnv",
    "OnSiteScenarioEnv",
    "StreetStudioScenarioEnv",
    "GrpcClientEnv",
    "make_interactive_env",
]

_MODULE_BY_NAME = {
    "ScenarioEnv": "streetworld.envs.scenario_env",
    "BaseEnv": "streetworld.envs.base_env",
    "OnSiteScenarioEnv": "streetworld.envs.onsite_scenario_env",
    "StreetStudioScenarioEnv": "streetworld.envs.streetstudio_scenario_env",
    "GrpcClientEnv": "streetworld.envs.grpc_client_env",
    "make_interactive_env": "streetworld.envs.interactive_env",
}


def __getattr__(name: str) -> Any:
    module_path = _MODULE_BY_NAME.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_path)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> List[str]:
    return sorted(list(globals().keys()) + __all__)

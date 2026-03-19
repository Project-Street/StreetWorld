import os

MetaDrive_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

__all__ = ["BaseEnv", "ScenarioEnv", "get_metadrive_class", "MetaDrive_PACKAGE_DIR"]


def __getattr__(name):
    if name in {"ScenarioEnv", "BaseEnv"}:
        from metadrive.envs import BaseEnv, ScenarioEnv

        exports = {
            "ScenarioEnv": ScenarioEnv,
            "BaseEnv": BaseEnv,
        }
        return exports[name]

    if name == "get_metadrive_class":
        from metadrive.utils.registry import get_metadrive_class

        return get_metadrive_class

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

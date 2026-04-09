import os

try:
    from metadrive.envs import (
        ScenarioEnv, BaseEnv
    )
    from metadrive.utils.registry import get_metadrive_class
except ImportError:
    # Print a warning message if the import fails
    print("Warning: Failed to import MetaDrive. Please ensure that the MetaDrive package is properly installed and that all dependencies are satisfied.")
MetaDrive_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

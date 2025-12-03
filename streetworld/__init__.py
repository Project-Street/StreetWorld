import os

from streetworld.envs import BaseEnv, ScenarioEnv
from streetworld.utils.registry import get_metadrive_class

MetaDrive_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

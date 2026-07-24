from copy import deepcopy

from metadrive.configs.diffusiondrive_config import DIFFUSIONDRIVE_CONFIG


MOMAD_CONFIG = deepcopy(DIFFUSIONDRIVE_CONFIG)
MOMAD_CONFIG["decision_repeat"] = 5
MOMAD_CONFIG["actor_config"]["policy_config"]["control_dt"] = 0.1

import copy

from metadrive.default_config import BASE_DEFAULT_CONFIG
from metadrive.obs.global_rlsl_obs import GlobalRLSLObserver


ONSITE_DEFAULT_CONFIG = copy.deepcopy(BASE_DEFAULT_CONFIG)
ONSITE_DEFAULT_CONFIG["actor_config"]["check_crash"] = False
ONSITE_DEFAULT_CONFIG["participant_config"]["check_crash"] = False


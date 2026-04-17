import copy

from streetworld.default_config import BASE_DEFAULT_CONFIG
from streetworld.obs.global_rlsl_obs import GlobalRLSLObserver


ONSITE_DEFAULT_CONFIG = copy.deepcopy(BASE_DEFAULT_CONFIG)
ONSITE_DEFAULT_CONFIG["gui_image_key"] = "front_cam"
ONSITE_DEFAULT_CONFIG["actor_config"]["check_crash"] = False
ONSITE_DEFAULT_CONFIG["participant_config"]["check_crash"] = False
ONSITE_DEFAULT_CONFIG["actor_config"]["observer_config"]["navigation"]["looking_ahead_step"] = 150

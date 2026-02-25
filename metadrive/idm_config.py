import copy

from metadrive.default_config import BASE_DEFAULT_CONFIG
from metadrive.obs.assembly_obs import AssemblyObservation
from metadrive.obs.navigation_obs import NavigationObservation
from metadrive.obs.surrounding_obs import SurroundingObservation
from metadrive.policy.idm_policy import IDMPolicy


IDM_CONFIG = copy.deepcopy(BASE_DEFAULT_CONFIG)
IDM_CONFIG["participant_config"]["observer"] = AssemblyObservation
IDM_CONFIG["participant_config"]["observer_config"] = dict(
    navigation=dict(
        observer_class=NavigationObservation,
        navigating_type="expert_following",
    ),
    surrounding=dict(
        observer_class=SurroundingObservation,
    ),
)
IDM_CONFIG["participant_config"]["policy"] = IDMPolicy
IDM_CONFIG["participant_config"]["policy_config"] = dict(
    front_distance=5.0,
    react_time=1.0,
)

idm_config = IDM_CONFIG

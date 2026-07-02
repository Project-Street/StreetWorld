import copy

from metadrive.default_config import BASE_DEFAULT_CONFIG
from metadrive.obs.assembly_obs import AssemblyObservation
from metadrive.obs.state_obs import StateObservation
from metadrive.obs.surrounding_obs import SurroundingObservation
from metadrive.policy.idm_policy import IDMPolicy


IDM_CONFIG = copy.deepcopy(BASE_DEFAULT_CONFIG)
IDM_CONFIG["actor_config"]["controller_config"]["enable_reverse"] = False
IDM_CONFIG["participant_config"]["observer"] = AssemblyObservation
IDM_CONFIG["participant_config"]["observer_config"] = dict(
    states=dict(
        observer_class=StateObservation,
    ),
    surrounding=dict(
        observer_class=SurroundingObservation,
        coordinate_mode="world",
        ignore_dist=None,
    ),
)
IDM_CONFIG["participant_config"]["policy"] = IDMPolicy
IDM_CONFIG["participant_config"]["policy_config"] = dict(
    enable_lane_change=True,
    arrive_speed_threshold=10.0,
    current_lane_max_dist=2.25,
)
IDM_CONFIG["participant_config"]["controller_config"]["enable_reverse"] = False

idm_config = IDM_CONFIG

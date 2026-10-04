from streetworld.component.traffic_participants.base_traffic_participant import BaseTrafficParticipant
from streetworld.constants import CollisionGroup
from streetworld.constants import MetaDriveType, Semantics, get_color_palette


class Cyclist(BaseTrafficParticipant):
    MASS = 80  # kg
    TYPE_NAME = MetaDriveType.CYCLIST
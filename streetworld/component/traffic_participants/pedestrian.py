

from streetworld.component.traffic_participants.base_traffic_participant import BaseTrafficParticipant
from streetworld.constants import MetaDriveType
from streetworld.utils.math import norm


class Pedestrian(BaseTrafficParticipant):
    MASS = 70  # kg
    TYPE_NAME = MetaDriveType.PEDESTRIAN

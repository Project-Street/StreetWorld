from streetworld.component.traffic_participants.base_traffic_participant import BaseTrafficParticipant
from streetworld.constants import MetaDriveType


class Pedestrian(BaseTrafficParticipant):
    MASS = 70  # kg
    TYPE_NAME = MetaDriveType.PEDESTRIAN

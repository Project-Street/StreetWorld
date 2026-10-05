from streetworld.objects.traffic_participants.base_traffic_participant import BaseTrafficParticipant
from streetworld.constants import MetaDriveType


class Cyclist(BaseTrafficParticipant):
    MASS = 80  # kg
    TYPE_NAME = MetaDriveType.CYCLIST

from streetworld.objects.pg_space import VehicleParameterSpace, ParameterSpace
from streetworld.objects.vehicle.base_vehicle import BaseVehicle


def get_vehicle_type(length):
    if length <= 4:
        return SVehicle
    elif length <= 5.2:
        return MVehicle
    elif length <= 6.2:
        return LVehicle
    else:
        return XLVehicle

class DefaultVehicle(BaseVehicle):
    PARAMETER_SPACE = ParameterSpace(VehicleParameterSpace.DEFAULT_VEHICLE)
    TIRE_RADIUS = 0.313
    LATERAL_TIRE_TO_CENTER = 0.815
    FRONT_WHEELBASE = 1.05234
    REAR_WHEELBASE = 1.4166
    MASS = 1000

    DEFAULT_LENGTH = 4.515  # meters
    DEFAULT_HEIGHT = 1.19  # meters
    DEFAULT_WIDTH = 1.852  # meters


class XLVehicle(BaseVehicle):
    PARAMETER_SPACE = ParameterSpace(VehicleParameterSpace.XL_VEHICLE)
    TIRE_RADIUS = 0.37
    LATERAL_TIRE_TO_CENTER = 0.931
    REAR_WHEELBASE = 1.075
    FRONT_WHEELBASE = 1.726
    CHASSIS_TO_WHEEL_AXIS = 0.3
    MASS = 1600

    DEFAULT_LENGTH = 5.74  # meters
    DEFAULT_HEIGHT = 2.8  # meters
    DEFAULT_WIDTH = 2.3  # meters

class LVehicle(BaseVehicle):
    PARAMETER_SPACE = ParameterSpace(VehicleParameterSpace.L_VEHICLE)
    TIRE_RADIUS = 0.429
    LATERAL_TIRE_TO_CENTER = 0.75
    REAR_WHEELBASE = 1.218261
    FRONT_WHEELBASE = 1.5301
    MASS = 1300

    DEFAULT_LENGTH = 4.87  # meters
    DEFAULT_HEIGHT = 1.85  # meters
    DEFAULT_WIDTH = 2.046  # meters


class MVehicle(BaseVehicle):
    PARAMETER_SPACE = ParameterSpace(VehicleParameterSpace.M_VEHICLE)
    TIRE_RADIUS = 0.39
    LATERAL_TIRE_TO_CENTER = 0.803
    REAR_WHEELBASE = 1.203
    FRONT_WHEELBASE = 1.285
    MASS = 1200

    DEFAULT_LENGTH = 4.6  # meters
    DEFAULT_HEIGHT = 1.37  # meters
    DEFAULT_WIDTH = 1.85  # meters

class SVehicle(BaseVehicle):
    PARAMETER_SPACE = ParameterSpace(VehicleParameterSpace.S_VEHICLE)
    TIRE_RADIUS = 0.376
    LATERAL_TIRE_TO_CENTER = 0.7

    FRONT_WHEELBASE = 1.385
    REAR_WHEELBASE = 1.11

    MASS = 800

    DEFAULT_LENGTH = 4.3  # meters
    DEFAULT_HEIGHT = 1.7  # meters
    DEFAULT_WIDTH = 1.7  # meters


def random_vehicle_type(np_random, p=None):
    v_type = {
        "s": SVehicle,
        "m": MVehicle,
        "l": LVehicle,
        "xl": XLVehicle,
        "default": DefaultVehicle,
    }
    if p:
        assert len(p) == len(v_type), \
            "This function only allows to choose a vehicle from 6 types: {}".format(v_type.keys())
    prob = [1 / len(v_type) for _ in range(len(v_type))] if p is None else p
    return v_type[np_random.choice(list(v_type.keys()), p=prob)]

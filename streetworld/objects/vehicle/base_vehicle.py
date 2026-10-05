from collections import deque
from typing import Union

import numpy as np
from panda3d.bullet import BulletVehicle, BulletBoxShape, ZUp
from panda3d.core import Vec3, TransformState, LVector3

from streetworld.objects.base_object import BaseObject
from streetworld.objects.pg_space import VehicleParameterSpace, ParameterSpace
from streetworld.constants import MetaDriveType
from streetworld.engine.physics_node import BaseRigidBodyNode
from streetworld.utils.config import Config
from streetworld.utils.math import safe_clip_for_small_array
from streetworld.utils.math import norm
import torch


class BaseVehicleState:
    def __init__(self):
        self.init_state_info()

    def init_state_info(self):
        """
        Call this before reset()/step()
        """
        self.crash_vehicle = False
        self.crash_human = False
        self.crash_object = False
        self.crash_world = False


class BaseVehicle(BaseObject, BaseVehicleState):
    """
    Vehicle chassis and its wheels index
                    0       1
                    II-----II
                        |
                        |  <---chassis/wheelbase
                        |
                    II-----II
                    2       3
    """
    PARAMETER_SPACE = ParameterSpace(VehicleParameterSpace.BASE_VEHICLE)

    TIRE_RADIUS = None
    LATERAL_TIRE_TO_CENTER = None
    FRONT_WHEELBASE = None
    REAR_WHEELBASE = None

    CHASSIS_TO_WHEEL_AXIS = 0.2
    SUSPENSION_LENGTH = 15

    def __init__(
        self,
        config: Union[dict, Config],
        physics_world,
        size=None,
        name: str = None,
        random_seed=None,
        position=None,
        heading_theta=None,
        _calling_reset=True,
        **kwargs
    ):
        """
        This Vehicle Config is different from self.get_config(), and it is used to define which modules to use, and
        module parameters. And self.physics_config defines the physics feature of vehicles, such as length/width
        :param vehicle_config: mostly, vehicle module config
        :param random_seed: int
        """
        # check
        assert config is not None, "Please specify the vehicle config."


        if size is None:
            size = (self.DEFAULT_LENGTH, self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)
        BaseObject.__init__(self, physics_world, size, name, random_seed, config)
        BaseVehicleState.__init__(self)
        self.set_metadrive_type(MetaDriveType.VEHICLE)

        # build vehicle physics model
        self.vehicle, self.body = self._create_vehicle_chassis()
        self.wheels = self._create_wheel()

        # powertrain config
        self.enable_reverse = self.config["enable_reverse"]
        self.max_steering = self.config["max_steering"]
        self.max_engine_force = self.config["max_engine_force"]
        self.max_brake_force = self.config["max_brake_force"]

        # state info
        self.throttle_brake = 0.0
        self.steering = 0
        self.last_current_action = deque([(0.0, 0.0), (0.0, 0.0)], maxlen=2)


        # step info
        self._init_step_info()

        if _calling_reset:
            self.reset(position=position, heading_theta=heading_theta, vehicle_config=config, **kwargs)

    def _init_step_info(self):
        # done info will be initialized every frame
        self.init_state_info()

    @staticmethod
    def _preprocess_action(action):
        action = safe_clip_for_small_array(action, -1, 1)
        return action, {'raw_action': (action[0], action[1])}

    def attachDyWld(self):
        self.physics_world.dynamic_world.attach(self.body)
        self.physics_world.dynamic_world.attach(self.vehicle)

    def detachDyWld(self):
        self.physics_world.dynamic_world.remove(self.vehicle)
        self.physics_world.dynamic_world.remove(self.body)

    def reset(
        self,
        name=None,
        random_seed=None,
        position: np.ndarray = None,
        heading_theta: float = 0.0,
        velocity: np.ndarray = None,
        angular_velocity: float = 0.0,
        *args,
        **kwargs
    ):
        """
        pos is a 2-d array, and heading is a float (unit degree)
        if pos is not None, vehicle will be reset to the position
        else, vehicle will be reset to spawn place
        """
        if name is not None:
            self.rename(name)

        # reset fully
        if random_seed is not None:
            assert isinstance(random_seed, int)
            self.seed(random_seed)
            self.sample_parameters()


        self.set_heading_theta(heading_theta)

        self.set_position(position)

        if self.config["spawn_velocity"]:
            self.set_velocity(velocity)
            self.set_angular_velocity(angular_velocity)
            self.last_velocity = self.velocity
            self.last_angular_velocity = self.angular_velocity

        # done info
        self._init_step_info()

    def move(self, action=None):
        """
        Save info and make decision before action
        """
        # init step info to store info before each step

        self._init_step_info()

        if 'transform' in action and 'velocity' in action and 'angular_velocity' in action:
            self.set_transform(action["transform"])

            self.set_velocity(action["velocity"])
            self.set_angular_velocity(action["angular_velocity"])
            step_info = None
        else:
            if "max_acceleration" in self.config:
                self.limit_acceleration()

            self.last_velocity = self.velocity
            self.last_angular_velocity = self.angular_velocity

            action, step_info = self._preprocess_action(action)
            self.last_current_action.append(action)  # the real step of physics world is implemented in taskMgr.step()
            self._set_action(action)
        return step_info

    def limit_acceleration(self):
        max_velocity_delta = float(self.config["max_acceleration"]) * self.physics_world.step_size_sec
        assert max_velocity_delta > 0.0

        current_velocity = self.velocity
        delta_velocity = current_velocity[:2] - self.last_velocity[:2]
        delta_speed = norm(delta_velocity[0], delta_velocity[1])
        if delta_speed <= max_velocity_delta:
            return

        limited_velocity = self.last_velocity[:2] + delta_velocity / delta_speed * max_velocity_delta
        self.body.setLinearVelocity(LVector3(limited_velocity[0], limited_velocity[1], current_velocity[2]))

    def check_crash_world(self):
        if not self.config["check_crash_world"]:
            return

        contacts = self.physics_world.dynamic_world.contactTest(self.body, False)
        ground_contact = list()
        for contact in contacts.getContacts():
            node1 = contact.getNode1()
            if node1.getName() == MetaDriveType.GROUND:
                maniP = contact.getManifoldPoint()
                pos = maniP.getPositionWorldOnB()
                ground_contact.append(torch.tensor([pos.x, pos.y, pos.z]))

        if not ground_contact:
            return

        contact_points = torch.stack(ground_contact).cuda().float()
        wheel_centers = []
        for i in range(self.vehicle.getNumWheels()):
            wheel = self.vehicle.getWheel(i)
            wheel_center = wheel.getWorldTransform().getRow3(3)
            wheel_center = torch.tensor([wheel_center.x, wheel_center.y, wheel_center.z])
            wheel_centers.append(wheel_center)
        wheel_centers = torch.stack(wheel_centers).cuda().float()

        diff = contact_points[:, :2].unsqueeze(1) - wheel_centers[:, :2].unsqueeze(0)  # [N,4,3]
        dist = diff.norm(dim=-1)                              # [N,4]
        nearest_idx = dist.argmin(dim=1)                                 # [N]
        nearest_z = wheel_centers[nearest_idx, 2]                        # [N]

        if (contact_points[:, 2] - nearest_z > 0).any().item():
            self.crash_world = True

    def _set_action(self, action):
        if action is None:
            return
        steering = action[0]
        self.throttle_brake = action[1]
        self.steering = steering
        self.vehicle.setSteeringValue(self.steering * self.max_steering, 0)
        self.vehicle.setSteeringValue(self.steering * self.max_steering, 1)
        self._apply_throttle_brake(action[1])

    def _apply_throttle_brake(self, throttle_brake):
        for wheel_index in range(4):
            if throttle_brake >= 0:
                self.vehicle.setBrake(2.0, wheel_index)
                if self.speed_km_h > self.max_speed_km_h:
                    self.vehicle.applyEngineForce(0.0, wheel_index)
                else:
                    self.vehicle.applyEngineForce(self.max_engine_force * throttle_brake, wheel_index)
            else:
                if self.enable_reverse:
                    self.vehicle.applyEngineForce(self.max_engine_force * throttle_brake, wheel_index)
                    self.vehicle.setBrake(0, wheel_index)
                else:
                    DEADZONE = 0.01

                    # Speed m/s in car's heading:
                    heading = self.heading
                    velocity = self.velocity
                    speed_in_heading = velocity[0] * heading[0] + velocity[1] * heading[1]

                    if speed_in_heading < DEADZONE:
                        self.vehicle.applyEngineForce(0.0, wheel_index)
                        self.vehicle.setBrake(2, wheel_index)
                    else:
                        self.vehicle.applyEngineForce(0.0, wheel_index)
                        self.vehicle.setBrake(abs(throttle_brake) * self.max_brake_force, wheel_index)

    def _create_vehicle_chassis(self):
        chassis = BaseRigidBodyNode(self.name, MetaDriveType.VEHICLE, self.MASS)
        chassis.base_object = self

        chassis_shape = BulletBoxShape(Vec3(self.WIDTH / 2, self.LENGTH / 2, self.HEIGHT / 2))
        chassis_shape.setMargin(0.03)
        ts = TransformState.makePos(Vec3(0, 0, self.TIRE_RADIUS))
        chassis.addShape(chassis_shape, ts)
        chassis.setDeactivationEnabled(False)
        chassis.notifyCollisions(True)  # advance collision check, do callback in pg_collision_callback

        vehicle_chassis = BulletVehicle(self.physics_world.dynamic_world, chassis)
        vehicle_chassis.setCoordinateSystem(ZUp)
        return vehicle_chassis, chassis

    def _create_wheel(self):
        f_l = self.FRONT_WHEELBASE
        r_l = -self.REAR_WHEELBASE
        lateral = self.LATERAL_TIRE_TO_CENTER
        axis_height = self.TIRE_RADIUS - self.CHASSIS_TO_WHEEL_AXIS
        radius = self.TIRE_RADIUS
        wheels = []
        for id, pos in enumerate(
            [Vec3(lateral, f_l, axis_height), Vec3(-lateral, f_l, axis_height),
            Vec3(lateral, r_l, axis_height), Vec3(-lateral, r_l, axis_height)]
        ):
            wheel = self.vehicle.createWheel()
            wheel.setChassisConnectionPointCs(pos)
            wheel.setFrontWheel(True if id < 2 else False)
            wheel.setWheelDirectionCs(Vec3(0, 0, -1))
            wheel.setWheelAxleCs(Vec3(1, 0, 0))

            wheel.setWheelRadius(radius)
            wheel.setMaxSuspensionTravelCm(self.SUSPENSION_LENGTH)
            wheel.setSuspensionStiffness(50)
            wheel.setWheelsDampingRelaxation(4.8)
            wheel.setWheelsDampingCompression(3.2)
            wheel.setFrictionSlip(0.5)
            wheel.setRollInfluence(0.5)
            wheels.append(wheel)
        return wheels

    def destroy(self):
        super(BaseVehicle, self).destroy()
        self.detachDyWld()
        self.body.base_object = None
        self.origin = None
        self.vehicle = None
        self.wheels = None

    def set_position(self, position):
        if len(position) == 2:
            position.append(self.position[-1])
        super(BaseVehicle, self).set_position(position)

    def __del__(self):
        super(BaseVehicle, self).__del__()
        self.wheels = None

    @property
    def current_action(self):
        return self.last_current_action[-1]

    @property
    def max_speed_km_h(self):
        return self.config["max_speed_km_h"]

    def get_steering_wheel_angle(self):
        return self.steering * self.max_steering * (np.pi / 180.0)

    def get_longitudinal_acceleration(self):
        return self.acceleration[:2] * self.heading

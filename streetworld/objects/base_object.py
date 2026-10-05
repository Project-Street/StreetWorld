import copy
import math
from abc import ABC

import numpy as np
from panda3d.core import LVector3, TransformState, LMatrix4

from streetworld.base_class.base_runnable import BaseRunnable
from streetworld.engine.physics_node import BaseRigidBodyNode
from streetworld.type import MetaDriveType
from streetworld.utils.coordinates_shift import panda_vector
from streetworld.utils.math import clip, norm, wrap_to_pi


class BaseObject(BaseRunnable, MetaDriveType, ABC):
    """
    BaseObject is something interacting with game engine. If something is expected to have an body in the world or have
    appearance in the world, it must be a subclass of BaseObject.

    It is created with name/config/randomEngine and can make decision in the world. Besides the random engine can help
    sample some special configs for it ,Properties and parameters in PARAMETER_SPACE of the object are fixed after
    calling __init__().
    """
    MASS = None  # if object has an body, the mass will be set automatically

    YFront2X = np.array([
        [ 0., 1.,  0.],
        [ -1.,  0.,  0.],
        [ 0. , 0.,  1.],
    ])
    XFront2Y = np.array([
        [ 0., -1.,  0.],
        [ 1.,  0.,  0.],
        [ 0. , 0.,  1.],
    ])

    def __init__(self, physics_world, size=None, name=None, random_seed=None, config=None, escape_random_seed_assertion=False):
        """
        Config is a static conception, which specified the parameters of one element.
        There parameters doesn't change, such as length of straight road, max speed of one vehicle, etc.
        """
        config = copy.deepcopy(config)
        BaseRunnable.__init__(self, name, random_seed, config)
        MetaDriveType.__init__(self)
        if not escape_random_seed_assertion:
            assert random_seed is not None, "Please assign a random seed for {} class.".format(self.class_name)

        self.physics_world = physics_world

        # Following properties are available when this object needs visualization and physics property
        self.body: BaseRigidBodyNode = None

        if size:
            self.LENGTH, self.WIDTH, self.HEIGHT = size

        self.last_velocity = np.zeros(2)
        self.last_angular_velocity = 0

    def destroy(self):
        """
        Fully delete this element and release the memory
        """
        super(BaseObject, self).destroy()

    def set_position(self, position):
        """
        Set this object to a place, the default value is the regular height for red car
        :param position: 2d array or list
        :param height: give a fixed height
        """
        assert len(position) == 3
        self.body.setTransform(self.body.getTransform().setPos(panda_vector(position)))

    @property
    def position(self):
        return self.body.getTransform().getPos()

    def set_heading_theta(self, heading_theta, to_deg=True) -> None:
        """
        Set heading theta for this object
        :param heading_theta: float
        :param in_rad: when set to True, heading theta should be in rad, otherwise, in degree
        """

        h = heading_theta
        if to_deg:
            h = heading_theta * 180 / np.pi
        # Apply panda2ego transform: -90 degrees to convert from ego (+X forward) to panda (+Y forward)
        h_panda = h - 90.0
        cur_hpr = self.body.getTransform().getHpr()
        new_hpr = LVector3(h_panda, cur_hpr[1], cur_hpr[2])
        self.body.setTransform(self.body.getTransform().setHpr(new_hpr))

    @property
    def heading_theta(self):
        """
        Get the heading theta of this object, unit [rad]
        :return:  heading in rad
        """
        h_panda = self.body.getTransform().getHpr()[0]
        # Apply inverse transform: +90 degrees to convert from panda (+Y forward) to ego (+X forward)
        h_ego = h_panda + 90.0
        return wrap_to_pi(h_ego / 180 * np.pi)

    def set_transform(self, m):
        M = m[:3, :3] @ BaseObject.YFront2X
        self.body.setTransform(TransformState.makeMat(LMatrix4(
            M[0, 0], M[1, 0], M[2, 0], m[3, 0],
            M[0, 1], M[1, 1], M[2, 1], m[3, 1],
            M[0, 2], M[1, 2], M[2, 2], m[3, 2],
            m[0, 3], m[1, 3], m[2, 3], m[3, 3]
        )))

    @property
    def transform(self):
        mat = self.body.getTransform().getMat()
        M = np.array([
            [mat[0][0], mat[1][0], mat[2][0], mat[3][0]],
            [mat[0][1], mat[1][1], mat[2][1], mat[3][1]],
            [mat[0][2], mat[1][2], mat[2][2], mat[3][2]],
            [mat[0][3], mat[1][3], mat[2][3], mat[3][3]]
        ], dtype=np.float32)
        M[:3, :3] = M[:3, :3]  @ BaseObject.XFront2Y
        return M

    def set_velocity(self, velocity):
        """
        Set velocity for object including the direction of velocity and the value (speed)
        The direction of velocity will be normalized automatically, value decided its scale
        :param direction: 2d array or list
        :param value: speed [m/s]
        :param in_local_frame: True, apply speed to local fram
        """
        self.last_velocity = self.velocity
        if len(velocity) == 2:
            self.body.setLinearVelocity(
                LVector3(velocity[0], velocity[1], self.body.getLinearVelocity()[-1])
            )
        else:
            self.body.setLinearVelocity(LVector3(velocity[0], velocity[1], velocity[2]))

    @property
    def velocity(self):
        """
        Velocity, unit: m/s
        """
        velocity = self.body.getLinearVelocity()
        return np.asarray([velocity[0], velocity[1], velocity[2]])

    def set_angular_velocity(self, angular_velocity, in_rad=True):
        self.last_angular_velocity = self.angular_velocity
        if not in_rad:
            angular_velocity = angular_velocity / 180 * np.pi
        self.body.setAngularVelocity(LVector3(0, 0, angular_velocity))

    @property
    def angular_velocity(self):
        return self.body.getAngularVelocity()[-1]

    @property
    def angular_acceleration(self):
        step_size = self.physics_world.step_size_sec
        step_size = max(step_size, 1e-6)
        return float(self.angular_velocity - self.last_angular_velocity) / step_size

    @property
    def acceleration(self):
        """
        Acceleration, unit: m/s^2
        """
        total_force = self.body.getTotalForce()
        mass = self.body.getMass()
        return np.asarray([total_force[0], total_force[1], total_force[2]]) / mass

    @property
    def speed(self):
        """
        return the speed in m/s
        """
        velocity = self.velocity
        speed = norm(velocity[0], velocity[1])
        return clip(speed, 0.0, 100000.0)

    @property
    def speed_km_h(self):
        """
        km/h
        """
        return self.speed * 3.6

    @property
    def heading(self):
        """
        Heading is a vector = [cos(heading_theta), sin(heading_theta)]
        """
        real_heading = self.heading_theta
        heading = (math.cos(real_heading), math.sin(real_heading))
        return heading

    def rename(self, new_name):
        super(BaseObject, self).rename(new_name)

        self.body.rename(new_name)

    def attachDyWld(self, obj=None):
        if not obj:
            self.physics_world.dynamic_world.attach(self.body)
        else:
            self.physics_world.dynamic_world.attach(obj)

    def detachDyWld(self, obj=None):
        if not obj:
            self.physics_world.dynamic_world.remove(self.body)
        else:
            self.physics_world.dynamic_world.remove(obj)

    def set_kinematic(self, is_kinematic):
        self.body.setKinematic(is_kinematic)
        if is_kinematic:
            self.body.setActive(not is_kinematic)
            self.body.setStatic(not is_kinematic)

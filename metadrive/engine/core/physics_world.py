import logging

from panda3d.bullet import BulletWorld
from panda3d.core import Vec3

from metadrive.constants import CollisionGroup


class PhysicsWorld:
    def __init__(self, disable_collision=False, physics_world_step_size=0.01, substep : int = 1): # physics_world_step_size in microsecond
        self.physics_world_step_size = physics_world_step_size
        self.substep = int(substep)

        # a dynamic world, moving objects or objects which react to other objects should be placed here
        self.dynamic_world = BulletWorld()
        # CollisionGroup.set_collision_rule(self.dynamic_world, disable_collision=disable_collision)
        self.dynamic_world.setGravity(Vec3(0, 0, -9.81))  # set gravity
        # a static world which used to query position/overlap .etc. Don't implement doPhysics() in this world
        self.static_world = BulletWorld()
        # CollisionGroup.set_collision_rule(self.static_world, disable_collision=disable_collision)

    def report_bodies(self):
        dynamic_bodies = \
            self.dynamic_world.getNumRigidBodies() + self.dynamic_world.getNumGhosts() + self.dynamic_world.getNumVehicles()
        static_bodies = \
            self.static_world.getNumRigidBodies() + self.static_world.getNumGhosts() + self.static_world.getNumVehicles()
        return "dynamic bodies:{}, static_bodies: {}".format(dynamic_bodies, static_bodies)

    def destroy(self):
        self.dynamic_world.clearDebugNode()
        self.dynamic_world.clearContactAddedCallback()
        self.dynamic_world.clearFilterCallback()

        self.static_world.clearDebugNode()
        self.static_world.clearContactAddedCallback()
        self.static_world.clearFilterCallback()

        self.dynamic_world = None
        self.static_world = None

    def step(self):
        self.dynamic_world.doPhysics(self.step_size_sec, self.substep, self.step_size_sec / self.substep)
    
    @property
    def step_size_sec(self):
        return self.physics_world_step_size * 1e-6
    
    def step_size_ms(self):
        return self.physics_world_step_size * 1e-3
    
    def step_size_us(self):
        return self.physics_world_step_size

    def __del__(self):
        logging.debug("Physics world is destroyed successfully!")

"""Rigid body nodes connect Bullet collision callbacks to simulation objects."""

from panda3d.bullet import BulletRigidBodyNode


class BaseRigidBodyNode(BulletRigidBodyNode):
    def __init__(self, base_object_name, type_name, mass=None):
        self.type_name = type_name
        assert type_name, "Type name can not be None"
        super(BaseRigidBodyNode, self).__init__(type_name)
        self.setPythonTag(type_name, self)
        self.base_object_name = base_object_name
        self._clear_python_tag = False

        if mass is not None:
            self.setMass(mass)

    def rename(self, new_name):
        self.base_object_name = new_name

    def destroy(self):
        # This sentence is extremely important!
        self.base_object_name = None
        self.clearPythonTag(self.getName())
        self._clear_python_tag = True

    def __del__(self):
        assert self._clear_python_tag, "You should call destroy() of BaseRigidBodyNode!"

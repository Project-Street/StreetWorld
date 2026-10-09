<a id="section-2-3"></a>

# 2.3 AgentManager components

[简体中文](../../../zh/guides/architecture/agent-manager.md)

[Contents](../../../DOCUMENTATION_EN.md) · [Previous: 2.2 SimulatorInterface: scene loading and rendering](simulator.md) · [Next: 2.4 reset: start a scene](reset.md)

Environment advances a scene through multiple AgentManagers: one for the ego vehicle and one for each surrounding participant. At each simulation step, it calls these Managers to update their objects in the same scene.

Each object can have its own observations, policy, and motion model:

- Observer produces camera images, vehicle state, and other observations.
- Policy computes control or motion commands from external actions, recorded trajectories, or traffic models. The ego vehicle can use iLQR to track a model's trajectory, while surrounding vehicles replay recordings or use IDM to respond to traffic.
- Controller executes those commands to move the simulated object.

Here, Controller refers to simulation objects such as `BaseVehicle`, `Pedestrian`, and Cyclist.

---

[Contents](../../../DOCUMENTATION_EN.md) · [Previous: 2.2 SimulatorInterface: scene loading and rendering](simulator.md) · [Next: 2.4 reset: start a scene](reset.md)

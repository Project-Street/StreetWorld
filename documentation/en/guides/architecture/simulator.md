<a id="section-2-2"></a>

# 2.2 SimulatorInterface: scene loading and rendering

[简体中文](../../../zh/guides/architecture/simulator.md)

[Contents](../../../DOCUMENTATION_EN.md) · [Previous: 2.1 Environment roles and types](environment.md) · [Next: 2.3 AgentManager components](agent-manager.md)

SimulatorInterface defines the scene data supplied to Environment and how a renderer generates camera images from simulation state. Datasets can use different file formats, and renderers can run in different ways, provided their implementations return data in this format.

Pass a SimulatorInterface instance when constructing an Environment. During `reset()`, the environment reads trajectories, camera parameters, and terrain, then loads 3D assets and road maps. During simulation, it passes the current timestamp and participant poses to the backend; the ego camera Observer requests images from it.

The ST Renderer implementation reads nuScenes or Waymo assets and renders on the local GPU. The NuRec implementation reads NuRec assets and requests images from a separate rendering service. See [Chapter 3](../simulator-interface.md#section-3-2) for data formats and backend configuration.

---

[Contents](../../../DOCUMENTATION_EN.md) · [Previous: 2.1 Environment roles and types](environment.md) · [Next: 2.3 AgentManager components](agent-manager.md)

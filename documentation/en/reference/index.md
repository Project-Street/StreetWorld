<a id="chapter-5"></a>

# 5. API reference

[简体中文](../../zh/reference/index.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous chapter: 4. Configuration system](../guides/configuration.md) · [Next: 5.1 Environment](environment.md)

Configuration fields use complete environment paths. Create cfg from an environment class's default_config() and modify it before construction; env denotes an environment that has completed reset. Each example is independent.

Look up methods by class in the [API index](../../API_CLASS_FUNCTIONS_EN.md).

- [5.1 Environment](environment.md)
    - [5.1.1 BaseEnv](environment.md#api-1-1)
    - [5.1.2 ScenarioEnv](environment.md#api-1-2)
    - [5.1.3 InteractiveScenarioEnv](environment.md#api-1-3)
    - [5.1.4 GrpcClientEnv](environment.md#api-2-1)
    - [5.1.5 EnvServicer](environment.md#api-2-2)
    - [5.1.6 Environment module functions](environment.md#section-5-1-6)
- [5.2 Manager](manager.md)
    - [5.2.1 BaseManager](manager.md#api-4-1)
    - [5.2.2 ScenarioDataManager](manager.md#api-4-2)
    - [5.2.3 AgentManager](manager.md#api-4-3)
- [5.3 Observation](observation.md)
    - [5.3.1 BaseObservation](observation.md#api-5-1)
    - [5.3.2 DummyObservation](observation.md#api-5-2)
    - [5.3.3 DefaultObservation](observation.md#api-5-3)
    - [5.3.4 AssemblyObservation](observation.md#api-5-4)
    - [5.3.5 GaussianObservation](observation.md#api-5-5)
    - [5.3.6 StateObservation](observation.md#api-5-6)
    - [5.3.7 NavigationObservation](observation.md#api-5-7)
    - [5.3.8 SurroundingObservation](observation.md#api-5-8)
    - [5.3.9 CollisionBodyObservation](observation.md#api-5-9)
- [5.4 Policy](policy.md)
    - [5.4.1 BasePolicy](policy.md#api-6-1)
    - [5.4.2 EnvInputPolicy](policy.md#api-6-2)
    - [5.4.3 EnvInputPIDPolicy](policy.md#api-6-3)
    - [5.4.4 EnvInputILQRPolicy](policy.md#api-6-4)
    - [5.4.5 ExpertILQRPolicy](policy.md#api-6-5)
    - [5.4.6 ReplayPolicy](policy.md#api-6-6)
    - [5.4.7 IDMPolicy](policy.md#api-6-7)
    - [5.4.8 TrajectoryIDMPolicy](policy.md#api-6-8)
    - [5.4.9 Policy module functions](policy.md#section-5-4-9)
- [5.5 Object / Controller](object.md)
    - [5.5.1 BaseObject](object.md#api-7-1)
    - [5.5.2 BaseVehicle](object.md#api-7-2)
    - [5.5.3 DefaultVehicle](object.md#api-7-3)
    - [5.5.4 XLVehicle](object.md#api-7-4)
    - [5.5.5 LVehicle](object.md#api-7-5)
    - [5.5.6 MVehicle](object.md#api-7-6)
    - [5.5.7 SVehicle](object.md#api-7-7)
    - [5.5.8 BaseTrafficParticipant](object.md#api-7-8)
    - [5.5.9 Pedestrian](object.md#api-7-9)
    - [5.5.10 Cyclist](object.md#api-7-10)
    - [5.5.11 GroundPlane](object.md#api-7-11)
    - [5.5.12 MeshTerrain](object.md#api-7-12)
    - [5.5.13 Object module functions](object.md#section-5-5-13)
- [5.6 Runtime utilities](runtime.md)
    - [5.6.1 StepCounter](runtime.md#api-8-1)
    - [5.6.2 PhysicsWorld](runtime.md#api-8-2)
- [5.7 Config](config.md#api-3-1)

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous chapter: 4. Configuration system](../guides/configuration.md) · [Next: 5.1 Environment](environment.md)

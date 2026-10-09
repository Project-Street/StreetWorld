<a id="section-2-2"></a>

# 2.2 SimulatorInterface：场景加载与渲染

[English](../../../en/guides/architecture/simulator.md)

[总目录](../../../DOCUMENTATION_ZH.md) · [上一页：2.1 Environment 的作用与类型](environment.md) · [下一页：2.3 AgentManager 的组成](agent-manager.md)

SimulatorInterface 约定场景数据怎样交给 Environment，以及渲染器怎样根据仿真状态生成相机图像。不同数据集可以有各自的文件格式，不同渲染器也可以有各自的运行方式；各实现按这套约定返回数据，Environment 就能使用它们。

创建 Environment 时，需要传入一个 SimulatorInterface 实例。`reset()` 通过它读取轨迹、相机参数和地形，加载 3D 资产与道路地图。运行场景时，Environment 把当前时间和周边对象的位姿交给它，主车的相机观测再调用它获取图像。

仓库中的 ST Renderer 实现读取 nuScenes 或 Waymo 资产，在本机 GPU 上渲染；NuRec 实现读取 NuRec 资产，向独立运行的渲染服务请求图像。接口的数据格式和两种实现的配置见[第三章](../simulator-interface.md#section-3-2)。

---

[总目录](../../../DOCUMENTATION_ZH.md) · [上一页：2.1 Environment 的作用与类型](environment.md) · [下一页：2.3 AgentManager 的组成](agent-manager.md)

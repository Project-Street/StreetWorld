# StreetWorld Documentation 主体框架

文档按照「安装与运行 → 宏观架构 → 接口约定 → 配置系统 → 组件详解 → 基类 → Policy Launcher 附录」组织。

本文中的 Environment Server 对应当前 `env_server_*` 提供的 Environment gRPC Server；模型推理端指连接它的 Policy Launcher。

## 1. Setup 与 Quick Start

目标：完成安装，按需要选择浏览器驾驶、外部模型接入或专家轨迹跟踪示例。

### 1.1 安装

- 运行环境与依赖。
- 仓库与子模块的安装。
- 渲染后端的准备。
- 场景数据的目录、格式和准备方式。TODO：会将数据放到云端，届时直接下载即可。

### 1.2 Web Controller

用途：在浏览器中查看仿真场景，使用键盘手动试控车辆。

入口：[env_easydrive_web_controller.py](../streetworld/examples/env_easydrive_web_controller.py)。

- 通过终端界面选择数据集和场景标签。
- 启动命令。
- 浏览器连接与操作方式。
- 油门、制动和转向控制量的含义。
- Web Controller 的相关配置。
- 场景切换与运行结束方式。

### 1.3 Environment Server

用途：将仿真作为 gRPC 服务运行，让外部驾驶模型接收观测并提交规划结果。

入口：[env_server_easydrive.py](../streetworld/examples/env_server_easydrive.py)。

- 场景选择与后端选择。
- gRPC 地址和 WebUI 地址。
- 服务端启动与客户端连接的最小流程。
- 通过 [env_server_scene_config.py](../streetworld/examples/env_server_scene_config.py) 指定场景列表。
- 分别列出两个服务端脚本的参数。

### 1.4 Drive Expert iLQR

用途：查看车辆沿专家轨迹行驶时的仿真效果，专家轨迹取自场景中记录的主车轨迹。

入口：[drive_expert_ilqr.py](../streetworld/examples/drive_expert_ilqr.py)。

- 场景列表文本文件与数据集选择。
- 启动命令与关键参数。
- Expert iLQR 的运行流程。
- 运行结果与结束条件。

## 2. Architecture：整体结构与运行流程

目标：说明 Environment、SimulatorInterface 和 AgentManager 各自用于什么，如何开始场景、执行动作，以及仿真时间怎样控制。

2.1 至 2.6 合并在 `guides/architecture.md` 中。

### 2.1 Environment 的作用与类型

- OpenAI Gym 的交互方式与 Gymnasium 基类。
- Environment 如何连接驾驶程序与仿真。
- BaseEnv、ScenarioEnv、交互环境和远程客户端各自提供的功能。

### 2.2 SimulatorInterface：场景加载与渲染

- 场景数据和图像渲染的接口约定。
- Environment 如何通过接口加载场景和获取画面。
- ST Renderer 与 NuRec 两种实现。

### 2.3 AgentManager 的组成

- Environment 如何管理主车和周边对象的多个 AgentManager。
- Observer。
- Policy。
- Controller。
- 三者的职责和配合方式。

这里的 Controller 是仿真对象，需要与 Web Controller 的概念区分。

### 2.4 reset：开始一个场景

说明 reset 初始化一轮驾驶测试、返回初始观测，以及什么时候调用它。

### 2.5 step：执行动作

- step 如何执行驾驶输入并返回运行结果。
- 物理步长与 decision_repeat 分别控制什么。
- 用具体数值说明一个环境步经过多少仿真时间。

### 2.6 同步与异步

- 同步模式等待驾驶程序，异步模式持续运行。
- 用模型推理耗时的例子区分实际时间和仿真时间。
- 两种模式适合的使用情况，以及异步返回观测的时机。

## 3. Interfaces：Environment 与 Simulator

目标：说明 Environment 与场景加载、渲染接口的用途，给出调用方式、数据格式和扩展方法。

### 3.1 Environment：本地与远程调用

#### 本地调用

- 构造参数。
- `reset()`。
- `step()`。
- `close()`。
- `observation`、`reward`、`terminated`、`truncated`、`info` 的返回值约定。
- 轨迹点的 x、y 含义、坐标原点与采样时间。
- 转向和油门/制动输入的取值含义。
- 观测的数据格式、运动量单位和场景信息字段。
- AgentState 的全部取值与结束条件。
- 默认奖励项、修改权重、覆写奖励函数和替换奖励计算器。
- InteractiveEnv 管理 WebUI、TUI 和 VideoExporter 的功能与配置。

#### 远程调用与 gRPC

- 模型推理端与仿真端的职责。
- GrpcClientEnv 的调用示例。
- 本地与远程调用的数据对应关系。
- 远程场景选择、动作格式和图像形状。
- 地图对象、未传输观测和消息大小的限制。

### 3.2 3D 资产与 SimulatorInterface

- 接口的用途，以及接入不同数据格式和渲染方式的原因。
- 四个方法各自的用途、调用顺序和前置条件。
- `load_metadata()` 的六项返回值、轨迹、对象尺寸、相机参数和地形。
- `load_model()` 加载模型并返回道路地图。
- `update_scene()` 的时间戳和对象位姿。
- `render()` 的批量相机参数、外参方向、图像格式和相机顺序。
- 坐标、时间、长度单位和资源释放要求。

### 3.3 渲染后端示例

#### ST Renderer

- nuScenes / Waymo 的本地渲染与接口创建。
- 数据目录、场景 ID 和自定义 root。

#### NuRec

- NuRec 的场景重建、USDZ 资产和渲染服务。
- StreetWorld 读取本地数据与请求远程渲染的分工。
- 渲染服务的安装、场景挂载和启动命令。
- 场景查询、Environment Server 启动与控制输入。
- 自行创建 NuRec SimulatorInterface 的参数。

## 4. Config System：配置如何组织和生效

目标：解释 Config 的使用、配置层级与优先级，再介绍环境和各组件的常用参数。4.1 至 4.5 各自分页，完整字段和 API 放到组件参考。

### 4.1 Config 的用途与使用

以当前主流程使用的 [streetworld.config.Config](../streetworld/config.py) 为准。

- Config 保存哪些设置，以及为什么在创建环境时传入。
- 从字典创建配置，环境合并默认值。
- 字典访问与属性访问。
- 从文件加载。
- 复制与导出。

- `merge_from()`。
- 嵌套合并。
- 点分隔键。
- 列表修改。
- 整项替换。

### 4.2 配置层级与优先级

- 用 iLQR 配置示例解释顶层环境字段与 Agent 配置。
- `actor_config`、`participant_config` 及各组件的配置层级。
- 基础、场景和交互环境的默认配置。
- 模型配置、命令行设置和环境构造时的合并顺序。
- nuScenes / Waymo 与 NuRec 启动分支的配置来源。

### 4.3 Environment 与 Agent 的常用参数

- 场景选择、物理步长、环境步时长和异步模式。
- 环境与主车各自的步数限制。
- 碰撞检测和专家轨迹预热。

### 4.4 Observer 配置

- AssemblyObservation 的用途、子观测创建与组合方式。
- 展开默认主车的完整观测配置，并说明对应的返回字段。
- 默认轨迹配置对导航和相机的设置。
- GaussianObservation 的自定义相机示例与参数含义。
- 图像类型、导航路径、周边对象过滤和交互界面布局。

### 4.5 Policy 与 Controller 配置

- 默认主车使用 EnvInputPolicy，周边对象使用 ReplayPolicy。
- 以 EnvInputILQRPolicy 说明模型轨迹与车辆控制。
- `trajectory_dt`、`control_dt` 与物理步长、`decision_repeat` 的关系。
- Controller 的车辆尺寸、初始速度、倒车、动力和碰撞配置。
- Controller 与 Policy 中同名加速度限制的区别。

## 5. Component Reference：各组件的配置与全部公开 API

目标：按模块提供配置说明与 API 查询，每个组件可以拆成独立页面。

### 5.1 Environments

按当前环境实现逐个介绍配置与全部公开 API。

#### BaseEnv

实现：[base_env.py](../streetworld/envs/base_env.py)。

- 基础仿真环境的职责与生命周期。
- SimulatorInterface 的传入方式，以及 Manager、物理世界的组织。
- 基础环境的全部配置项。
- 全部公开方法与属性。

#### ScenarioEnv

实现：[scenario_env.py](../streetworld/envs/scenario_env.py)。

- 与 `BaseEnv` 的继承关系。
- 场景环境的配置项及其生效位置。
- 奖励、终止条件和评测指标。
- 本类新增与覆写的公开 API。

#### 交互环境

实现：[interactive_env.py](../streetworld/envs/interactive_env.py)。

- `make_interactive_env(env_class)` 如何包装已有环境。
- 工厂内部的 `InteractiveEnv` 及其继承关系；当前示例以 `ScenarioEnv` 为基类，生成 `InteractiveScenarioEnv`。
- WebUI、TUI、视频输出与评测相关配置。
- 包装工厂、生成环境的公开 API，以及继承方法的行为变化。

#### GrpcClientEnv

实现：[grpc_client_env.py](../streetworld/envs/grpc_client_env.py)。

- 远程环境客户端的职责，以及与服务端仿真环境的关系。
- 连接地址、端口、超时和连接等待等构造参数。
- `reset()`、`step()`、`close()` 的完整 API。
- 与第 3.1 节远程接口约定的对应关系。

### 5.2 Managers

- `BaseManager`。
- `ScenarioDataManager`。
- `AgentManager`。

### 5.3 Observations

- `AssemblyObservation`。
- `GaussianObservation`。
- `StateObservation`。
- `NavigationObservation`。
- `SurroundingObservation`。
- `CollisionBodyObservation`。
- `DefaultObservation` 与 `DummyObservation`。

每种 Observation 都需给出实际输出字段、形状和类型。

### 5.4 Policies

- `EnvInputPolicy`。
- `EnvInputPIDPolicy`。
- `EnvInputILQRPolicy`。
- `ExpertILQRPolicy`。
- `ReplayPolicy`。
- `IDMPolicy`。
- `TrajectoryIDMPolicy`。

每种 Policy 都需明确输入动作与输出控制的格式。

### 5.5 Controller

- `BaseObject`。
- `BaseVehicle` 与各个车型。
- `BaseTrafficParticipant`、`Pedestrian`、`Cyclist`。
- `GroundPlane` 与 `MeshTerrain`。

### 5.6 运行辅助组件

- `StepCounter`：时间与步数。
- `PhysicsWorld`：物理世界。

### 5.7 Config

- Config 的职责、构造参数与全部公开 API。
- 配置合并、复制和文件读取的行为与限制。
- Config 的使用示例。

### 每个组件的统一说明模板

#### 职责与创建方式

- 职责和使用场景。
- 在整体架构中的位置。
- 构造方式与依赖。
- 生命周期。

#### 配置字段表

每个字段说明：

- 完整键路径。
- 类型。
- 默认值或必填状态。
- 用途。
- 单位。
- 生效条件。
- 关联字段与约束。

#### 全部公开 API

覆盖构造函数、公开方法、属性、类方法和模块级函数。

每个 API 说明：

- 函数签名。
- 参数。
- 返回值。
- 副作用。
- 调用条件。
- 异常。
- 当前实现状态。

#### 最小使用示例

展示组件的创建、配置与主要调用方式。

## 6. Base Classes：公共基础能力与继承约定

### 6.1 基础能力

- `Configurable`：配置持有与更新。
- `Nameable`：名称与对象标识。
- `Randomizable`：随机种子与随机状态。
- `BaseRunnable`：运行生命周期与状态接口。

## 7. 附录：Policy Launchers

### 7.1 统一启动流程

入口：[policy_launcher.launch](../policy_launcher/launch.py)。

- 仿真服务与模型推理环境分别如何准备。
- 统一 Launcher 的参数。
- gRPC 连接与评测循环。
- 模型、源码路径、checkpoint、设备与服务端 Policy preset 的对应关系。

### 7.2 UniAD

Launcher 标识：`uniad`。

### 7.3 VAD

Launcher 标识：`vad`。

### 7.4 GenAD

Launcher 标识：`genad`。

### 7.5 MomAD

Launcher 标识：`momad`。

### 7.6 ST-P3

Launcher 标识：`stp3`。

### 7.7 OpenDriveVLA

Launcher 标识：`opendrivevla`。

### 7.8 Latent TransFuser

Launcher 标识：`latent_transfuser`。

### 7.9 DiffusionDrive

Launcher 标识：`diffusiondrive`。

### 7.10 SparseDrive

Launcher 标识：`sparsedrive`。

### 7.11 Alpamayo 1

Launcher 标识：`alpamayo1`。

### 7.12 Alpamayo 1.5

Launcher 标识：`alpamayo1.5`。

### 7.13 AutoVLA

Launcher 标识：`autovla`。

### 7.14 Epona

Launcher 标识：`epona`。

### 7.15 OpenEMMA GPT

Launcher 标识：`openemma_gpt`。

### 7.16 OpenEMMA Qwen

Launcher 标识：`openemma_qwen`。

### 7.17 OpenEMMA LLaVA

Launcher 标识：`openemma_llava`。

### 7.18 OpenEMMA Llama

Launcher 标识：`openemma_llama`。

### 每个模型的统一说明模板

- 依赖环境。
- 上游源码准备。
- 权重与模型配置准备。
- 路径配置。
- 服务端启动命令。
- Launcher 启动命令。
- 输入输出要求。

## 编写原则

- Config 字段需要核对实际读取位置和生效条件，不能只复制默认配置中的注释。
- API 需要说明当前实现状态；未实现或未接入运行流程的内容应按代码现状标明。
- 概念说明与字段、API 查询分别承担不同职责，通过链接关联。
- 以 StreetWorld 当前代码为依据组织内容，重新核对现有文档中的 MetaDrive 遗留说明。

# E2 本地 fork 迁移

## GitHub 发布分支

`codex/rh56e2-public` 以原上游基线为父提交，重新收录集成代码、配置和文档；
不继承含模型的本地 `codex/rh56e2-sdk-integration` 提交历史。
后者与模型文件保留在本机，不推送到公开仓库。公开分支排除 E2 MJCF、URDF、网格和
G1+E2 组合 XML，依赖准备见 [外部模型说明](docs/zh/assets.md)。
SDK 发布目标为私有仓库 `wz-automind/rh56e2-sdk`；不把源码或 wheel 复制到公开 fork。
本次发布准备只修改文档/忽略规则和 Git 收录范围，不修改已验证的控制或打包脚本。
独立手部 MJCF 因此需要在 SCP 部署时额外携带本地模型包，详见部署说明。

下文是初次本地迁移的历史验证记录，其中 wheel 哈希对应当时的产物，
不代表增加发布说明后重新构建的 wheel。发布代码不等于完成 ARM64/G1 真机验收。

## 初次本地迁移记录

上游 Teleopit 基线 `f9263865c581802ad531854b8e547e2403a945f3`，保留完整 Git 历史。
E2 overlay 来源 `wz-automind/teleopit-rh56e2-repro@0f12802bfa72d7282d0b7649522aa343b11be797`。
somehand 配置基线 `f0a6b42e151ca10a6eec3e24c24c10cd13c40314` (0.3.0)。
独立 SDK 固定 0.1.0，以本地产出的 wheel 安装，不依赖浮动分支，也不复制 SDK 源码。

原 `/home/jiachengli/Teleopit` 的未提交内容未迁移/修改；本目录由其 Git 对象克隆。
本地验证复用已下载 G1 模型资源（仍 ignored），不是把旧工作树当作新代码基线。
基线补全模型后 436 passed / 1 skipped，未更改上游测试。

E2 手部配置/MJCF/mesh 迁入本 fork，传递引用的 `inspire_dfq.yaml` 和
`_universal_common.yaml` 同步收录；实际 somehand loader + MuJoCo 从临时 cwd 验证路径。
默认写入禁用、故障/温度门控、跟踪超时与 -1 保持语义不变。

没有 GitHub fork/推送、G1 部署或真机动作。原部署可以继续使用，回退无需删除本目录。

SDK wheel SHA256：`3838c1027b6a9794c1e88cdd29a1be4cb6f3e0ec307af3a331e2e170ffc2d552`。
SDK 初次交付提交 `f4d308a`；后续审查修复以最终交接提交和重建 wheel 为准。

真实无窗口仿真：G1+E2 模型 + `track_g1.onnx` + 已有 BVH，
`viewers=none +num_steps=20 +sim_hands.enabled=true` 实际返回 steps=20，root_height=0.7873732。
这是离线策略/物理/手部模块加载验证，不是实时 PICO 手势或真机控制验证。
G1 C++ SDK 打包源提交 `c753829882fba461ed07ba25aaabee0a25d83663`，本地复制 Git 历史，无原目录改动。

审查前离线回归：466 passed / 1 skipped；compileall 和 E2 适用 Ruff 检查通过。
跳过的是上游 `test_bvh_to_mujoco_pipeline_stands`，未提供其专用 policy 环境变量与 XSens 测试输入；
本轮另外执行了上述真实 E2 仿真。两项 warning 来自上游 Torch JIT 弃用和有意保留的旧协议兼容导入。
干净临时环境从本地 wheelhouse 安装 SDK 成功；缺 somehand 时离线安装器报出包名，未联网回退。
绘图 SDK 与 fork 的测试均未向真实 G1/E2 发包。

## 独立审查

一次独立只读审查发现两类沿用的配置校验缺陷：字符串 false 被转成真；
NaN/Infinity 及整数强制转换可能绕过运行时保护。已补先失败后通过的回归测试，
严格拒绝非布尔开关、非有限时序参数、整数设置中的浮点/字符串/布尔输入。
没有更改 G1 控制算法。审查未列出 Minor 遗留项。
修复后全套：469 passed、1 skipped、77 subtests passed；compileall 与适用 Ruff 通过。
上游 `cfg_get` 对 OmegaConf 的 null 取默认值语义保留：默认开关关闭、默认时序有限。

审查暂不判断 T1 物理方向/覆盖/固件、ARM64 与原生桥、实时 PICO/G1 运动/停机安全，
因为缺少目标设备测试且真机操作未获授权；不将软件测试解释为这些能力的验收。
公开分发与资产许可核查同样延后，尚未发布。

额外验证：从固定 somehand Git 提交生成干净 wheel，替换新隔离环境中的旧可编辑依赖；
解压部署包到临时目录后单独安装 SDK / somehand / fork，22 项集成与资源测试通过。
导入路径均指向解压目录和新 venv，不指向旧 repro 或原来改过的 somehand 目录。

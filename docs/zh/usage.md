# G1 + RH56E2 使用

设备 SDK 单独安装。
先在本地主机仿真，再按 [部署说明](deployment.md) 准备 G1，最后进行操作员在场的真机验证。

## 1. 本地环境与安装

在主机用 SSH 克隆已合并的主分支和私有 SDK（后者要求账号获授权）：

```bash
git clone --branch master git@github.com:wz-automind/Teleopit.git Teleopit-rh56e2-fork
git clone --branch main git@github.com:wz-automind/rh56e2-sdk.git rh56e2-sdk
```

先在 SDK 目录按其[安装文档](https://github.com/wz-automind/rh56e2-sdk/blob/main/docs/installation.md)
构建 `dist/rh56e2_sdk-0.1.0-py3-none-any.whl`。
另按 [外部模型准备](assets.md) 补齐 E2 模型；它们不随 GitHub 克隆或通用资产下载提供。

默认 Miniforge 已安装。**首次使用且还没有 `teleopit` 环境时**先执行：

```bash
source "$HOME/miniforge3/bin/activate"
conda create -n teleopit python=3.10
```

已有环境直接激活，在自己的项目目录安装：

```bash
source "$HOME/miniforge3/bin/activate" teleopit
cd "$HOME/Teleopit-rh56e2-fork"
python -m pip install ../rh56e2-sdk/dist/rh56e2_sdk-0.1.0-py3-none-any.whl
python -m pip install -e '.[rh56e2]'
python scripts/setup/download_assets.py --only robots gmr ckpt bvh
python scripts/dev/check_rh56e2.py --profile sim
```

SDK 安装使用获授权私有源码构建的本地 wheel；尚未在 PyPI 发布。
若更新后的 SDK wheel 仍为 `0.1.0`，普通安装可能跳过它。
停止占用 SDK 的程序后，在需要更新的环境执行（不重装其他依赖）：

```bash
python -m pip install --force-reinstall --no-deps --no-index \
  ../rh56e2-sdk/dist/rh56e2_sdk-0.1.0-py3-none-any.whl
```

已经激活其他可用环境时不必重复激活；脚本也接受 `TELEOPIT_PYTHON=/absolute/path/to/python`。
全新克隆不包含 Conda/venv 环境、SDK wheel 或 E2 模型。

只有修改代码或开发验证时才需要下面的命令，日常运行不用重复执行：

```bash
python -m pip install -e '.[dev]'
mkdir -p dist/wheelhouse
cp -i ../rh56e2-sdk/dist/rh56e2_sdk-0.1.0-py3-none-any.whl dist/wheelhouse/
bash scripts/dev/validate.sh
```

`[dev]` 包含 pytest 和 Ruff；验证脚本依次做语法检查、全套测试和 E2 相关静态检查，
不需要再重复运行 unittest。复制 SDK wheel 时已有同名文件会询问，确认是刚构建的版本再覆盖。
`dist/wheelhouse/` **只放 SDK wheel**，分发测试会验证缺少构建工具时的报错；
它不是部署 G1 使用的完整 ARM64 wheelhouse。全套测试还需要前面准备的运行模型和资源。

## 2. 先跑仿真

PICO 联机仿真（需要 PICO 输入与图形桌面，不连接 G1 电机）：

```bash
bash scripts/run/run_sim_rh56e2.sh controller.policy_path=ckpt/track_g1.onnx
```

没有 PICO 时，用已有 BVH 做离线无窗口冒烟检查：

```bash
python scripts/run/run_sim_rh56e2.py --config-name default \
  robot=g1_rh56e2 input.bvh_file=data/sample_bvh/aiming1_subject1.bvh \
  controller.policy_path=ckpt/track_g1.onnx viewers=none \
  +num_steps=20 +sim_hands.enabled=true
```

本地已实际执行上述 20 步，返回 `steps: 20`。这验证模型、控制策略和仿真集成，
不代表验证了实时 PICO 手势输入，更不代表 G1 真机安全。
交互图形可把 `viewers=none` 改为 `viewers=sim2sim`；无需虚构 `--headless` 参数。

## 3. 真机网络与端口确认

主机跑 Teleopit 时，填写**主机**连接机器人控制网的网卡。例如此前有线验证：
主机 `enp5s0=192.168.123.100/24`，G1 `192.168.123.164` 能 ping 通。
G1 自己跑 Teleopit 时，控制网卡示例是 **G1 的 `eth1`**，不是主机 `enp5s0`。
SSH 可走 Wi-Fi 或网线，它只说明登录连通，不证明 DDS 或 E2 端点可达。

```bash
ip -4 address
ip route get 192.168.123.164
ping -c 3 192.168.123.164
ip neigh
nc -vz -w 2 192.168.123.210 6000
nc -vz -w 2 192.168.123.211 6000
```

当时端口定位过程是：根据 RH56E2 Modbus TCP 协议配置取 `6000`，检查路由/邻居，
验证 TCP 可连接，再用只读 FC03 读出合理的六路遥测确认设备；并非看到开放端口就认定设备正确。
示例地址 `.210/.211`、unit ID 255 不是所有出厂设备的通用保证。
没有 `nc` 可直接用下面的检查工具。无需向随机寄存器写值“探测”。

```bash
python scripts/dev/check_rh56e2.py --profile real --hardware \
  --left-host 192.168.123.210 --right-host 192.168.123.211 --port 6000
```

检查工具支持单手/双手，增加 `--tactile` 可只读检查 T1 全阵列。默认不联网，只查本地依赖。
E2 手部默认 dry-run 禁写；单手/双手二维热力图的安装与命令见
[SDK 触觉文档](https://github.com/wz-automind/rh56e2-sdk/blob/main/docs/tactile.md)，
绘图环境另需 SDK 的 `[viz]` 可选依赖。Teleopit 不复制这些脚本，也不会自动启动热力图窗口。
不要让多个调试程序同时争用手的 TCP 会话。

## 4. G1 与 E2 启动

**这不是只读调试：即使 E2 禁写，G1 身体运行仍有运动风险。**
先确认支持/悬吊条件、急停、遥控器接管、关节活动空间和低层控制模式，操作员准备好后才执行。
停止其他占用 G1/E2 控制的进程。`ENABLE_G1_REAL=YES` 明确允许启动身体控制；
再加 `ENABLE_RH56E2_WRITES=YES` 才允许 E2 动作。

主机有线运行（PICO 广播地址按 PICO 实际可访问的主机 IP 填写）：

```bash
ENABLE_G1_REAL=YES ENABLE_RH56E2_WRITES=YES \
NETWORK_INTERFACE=enp5s0 \
LEFT_HAND_IP=192.168.123.210 RIGHT_HAND_IP=192.168.123.211 \
bash scripts/run/run_sim2real_rh56e2.sh
```

需要指定 PICO 发现地址时，在上面的环境变量中增加
`PICO_ADVERTISE_IP=主机上PICO可访问的IP`（替换为实际地址，不要原样粘贴占位文字）。
这是运行 Teleopit 的主机地址，不是 E2 地址；不设置时保留自动选择。
主机与 G1 两种入口都接受此变量；显式传入的 `input.bridge_advertise_ip=...` 优先于环境变量。

G1 内部运行时：

```bash
source "$HOME/miniforge3/bin/activate" teleopit
cd "$HOME/Teleopit-rh56e2"
ENABLE_G1_REAL=YES ENABLE_RH56E2_WRITES=YES \
NETWORK_INTERFACE=eth1 PICO_ADVERTISE_IP=192.168.50.62 \
bash scripts/run/run_unitree_g1_rh56e2.sh
```

`192.168.50.62` 只是此前 G1 Wi-Fi 示例，换网络须改成当前值。
手的故障/温度检查、限频、最小变化量、跟踪失效保持继续有效。
缺少/过期手势输出 -1 保持，不自动张开；双手写入非原子操作。
终端 Ctrl+C 用于请求程序退出，不能代替遥控器阻尼/硬件急停。

手部写开关只能通过环境变量设置，脚本拒绝同名 Hydra 覆盖项。直接调用 Python 入口则由配置的
`hands.rh56e2.write_enabled` 控制，默认 false；不要把配置检查命令误作运动验收。
YAML 开关必须是实际布尔值 `false/true`，不能加引号变成字符串；所有时间/频率须为有限正数，
端口、设备 ID、温度限值和六通道命令必须是整数，不接受浮点截断或布尔值冒充整数。

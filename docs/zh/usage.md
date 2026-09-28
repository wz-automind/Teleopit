# G1 + RH56E2 使用


## 1. 安装

默认主机已经安装 Miniconda，G1安装Miniforge：

```bash
git clone git@github.com:wz-automind/Teleopit.git
git clone git@github.com:wz-automind/rh56e2-sdk.git

source "$HOME/miniconda3/bin/activate"
conda create -n teleopit python=3.10
source "$HOME/miniconda3/bin/activate" teleopit

python -m pip install -e "$HOME/rh56e2-sdk"
cd "$HOME/Teleopit"
python -m pip install -e '.[rh56e2]'
python scripts/setup/download_assets.py --only robots gmr ckpt bvh
```

E2 三维模型不随仓库发布。仿真前从有权使用的来源补齐：

```text
assets/rh56e2/somehand/assets/mjcf/
  inspire_rh56e2_left/model.xml
  inspire_rh56e2_right/model.xml
assets/robots/unitree_g1/g1_29dof_rh56e2.xml
assets/robots/unitree_g1/meshes/rh56e2/
```

## 2. 先跑仿真

PICO 联机仿真：

```bash
cd "$HOME/Teleopit"
source "$HOME/miniconda3/bin/activate" teleopit
python scripts/run/run_sim.py --config-name pico4_sim_rh56e2
```

没有 PICO 时可以用 BVH 做 20 步无窗口检查：

```bash
python scripts/run/run_sim.py \
  --config-name pico4_sim_rh56e2 \
  input=bvh \
  input.bvh_file=data/sample_bvh/aiming1_subject1.bvh \
  controller.policy_path=ckpt/track_g1.onnx \
  viewers=none \
  num_steps=20 \
  sim_hands.enabled=true
```
想打开MuJoCo窗口查看BVH动作，可以运行：

```bash
python scripts/run/run_sim.py \
  --config-name pico4_sim_rh56e2 \
  input=bvh \
  input.bvh_file=data/sample_bvh/aiming1_subject1.bvh \
  controller.policy_path=ckpt/track_g1.onnx \
  viewers=sim2sim \
  num_steps=0 \
  sim_hands.enabled=true
```

## 3. 确认 G1、网卡和 E2 端口

运行 Teleopit 的机器必须能访问 G1 控制网及两只手。主机运行时填写主机网卡
（例如 `enp5s0`）；G1 内运行时通常填写 G1 的 `eth1`。

```bash
ip -4 address
ip route get 192.168.123.164
ping -c 3 192.168.123.164
nc -vz -w 2 192.168.123.210 6000
nc -vz -w 2 192.168.123.211 6000
```

当时根据 RH56E2 Modbus TCP 配置找到端口 `6000`，再通过 TCP 连通和只读
FC03 遥测确认设备。不要通过写随机寄存器探测。示例 IP、端口及 unit ID
必须以自己的设备配置为准。

只读检查：

```bash
python scripts/dev/check_rh56e2.py --profile real --hardware \
  --left-host 192.168.123.210 \
  --right-host 192.168.123.211 \
  --port 6000
```

该工具也支持单手和 `--tactile`。单手/双手触觉热力图见
[`rh56e2-sdk` 触觉文档](https://github.com/wz-automind/rh56e2-sdk/blob/main/docs/tactile.md)。

## 4. 真机启动

下面的命令会控制 G1 和双手。必须先准备支撑、急停、遥控器接管和安全空间。
`ENABLE_G1_REAL=YES` 允许身体控制；`ENABLE_RH56E2_WRITES=YES` 允许手部写入。
真机环境首次使用时先执行 `bash scripts/setup/setup_g1_bridge.sh`。

主机通过有线网卡运行：

```bash
cd "$HOME/Teleopit"
source "$HOME/miniconda3/bin/activate" teleopit

ENABLE_G1_REAL=YES ENABLE_RH56E2_WRITES=YES \
NETWORK_INTERFACE=enp5s0 \
LEFT_HAND_IP=192.168.123.210 RIGHT_HAND_IP=192.168.123.211 \
bash scripts/run/run_sim2real_rh56e2.sh
```

如果 PICO 需要指定发现地址，在同一命令增加
`PICO_ADVERTISE_IP=<运行Teleopit的机器上PICO可访问的IP>`。

G1 内运行使用同一个脚本，只需把网卡改为 `eth1`：

```bash
ENABLE_G1_REAL=YES ENABLE_RH56E2_WRITES=YES \
NETWORK_INTERFACE=eth1 PICO_ADVERTISE_IP=192.168.50.62 \
LEFT_HAND_IP=192.168.123.210 RIGHT_HAND_IP=192.168.123.211 \
bash scripts/run/run_sim2real_rh56e2.sh
```

不设置 `ENABLE_RH56E2_WRITES=YES` 时，手部保持只读。Ctrl+C 只请求程序退出，
不能代替遥控器阻尼或硬件急停。

## 5. 通过 SSH 传到 G1

先在主机完成安装、模型准备和仿真，并按 SDK 自己的安装文档生成 wheel。
然后打包完整 Teleopit 工作目录；这样 E2 本地模型也会一起传输，但不会携带
Git 历史和录制数据：

```bash
cd "$HOME"
tar --exclude-vcs \
    --exclude='Teleopit/data/recordings' \
    --exclude='*/__pycache__' \
    --exclude='*.pyc' \
    -czf Teleopit.tar.gz Teleopit

scp Teleopit.tar.gz \
  rh56e2-sdk/dist/rh56e2_sdk-0.1.0-py3-none-any.whl \
  unitree@192.168.123.164:/home/unitree/
```

登录 G1 后解压并安装：

```bash
ssh unitree@192.168.123.164
cd "$HOME"
tar -xzf Teleopit.tar.gz

source "$HOME/miniforge3/bin/activate"
conda create -n teleopit python=3.10
source "$HOME/miniforge3/bin/activate" teleopit
python -m pip install --no-index \
  "$HOME/rh56e2_sdk-0.1.0-py3-none-any.whl"
python -m pip install -e "$HOME/Teleopit[rh56e2]"
cd "$HOME/Teleopit"
bash scripts/setup/setup_g1_bridge.sh
```

已有 `teleopit` 环境时跳过 `conda create`。Teleopit 其余依赖仍须能通过
pip 安装，离线 G1 应提前准备匹配 ARM64/Python 3.10 的 wheelhouse。
完成后先执行第 3 节只读检查，
确认 G1 网卡、两只手和 PICO 地址，再执行第 4 节真机命令。

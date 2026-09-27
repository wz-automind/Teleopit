# 用 SSH/SCP 传到 G1

G1 不假定已有 Teleopit 或 `teleopit` 环境。默认已有 `$HOME/miniforge3`。
流程是主机准备并打包源码/资源 → SCP（基于 SSH）传输 → G1 解压 → 建环境与安装。
不用让 G1 再克隆 Teleopit，也不再解压旧 repro 覆盖 Teleopit。
本次只验证本地主机；ARM64、SCP、G1 安装及动作尚未执行。

## 1. 主机准备

完成 [本地仿真](usage.md) 后，确认 G1 C++ SDK 源码已准备在
`third_party/g1_bridge_sdk/thirdparty/unitree_sdk2`。本次本地目录已准备，来源提交
`c753829882fba461ed07ba25aaabee0a25d83663`。全新克隆时在能联网的主机执行：

```bash
mkdir -p third_party/g1_bridge_sdk/thirdparty
git clone https://github.com/unitreerobotics/unitree_sdk2.git \
  third_party/g1_bridge_sdk/thirdparty/unitree_sdk2
git -C third_party/g1_bridge_sdk/thirdparty/unitree_sdk2 checkout c753829882fba461ed07ba25aaabee0a25d83663
```

已存在目录时不要重复 clone 或覆盖；先检查现有提交。
离线安装还需要匹配 G1 **ARM64 + Python 3.10** 的 wheelhouse。
SDK 本体是纯 Python wheel，但 NumPy、MuJoCo、Torch、ONNX Runtime 等不等于跨架构通用。
不要拷贝主机 Conda 环境。没有 ARM64 依赖包时，应先在同架构联网机器准备，不能视为已经部署完成。
可在该准备机器上，用相同 fork 源码运行：

```bash
python -m pip wheel --wheel-dir wheelhouse . setuptools wheel 'pybind11>=2.10' \
  'somehand @ git+https://github.com/BotRunner64/somehand.git@f0a6b42e151ca10a6eec3e24c24c10cd13c40314' \
  'pico-bridge @ https://github.com/BotRunner64/pico-bridge/releases/download/v0.2.1/pico_bridge-0.2.1-py3-none-any.whl'
cp /path/to/rh56e2_sdk-0.1.0-py3-none-any.whl wheelhouse/
```

上述依赖准备命令可能因某版本无 ARM64 wheel 而失败，须解决报出的具体包后再传输；本次未在 ARM64 执行。
代码打包以 **Git HEAD 的已提交内容** 为准；不会包含未提交修改。
先按 [外部模型准备](assets.md) 补齐本机模型。公开分支不跟踪 E2 模型，
其中独立手部 MJCF 要额外打一个本地包，和源码包一起通过 SCP 传输。
下面两个目标压缩包均应使用尚不存在的新文件名，避免覆盖之前的备份。

```bash
python scripts/setup/package_rh56e2.py --output ../Teleopit-rh56e2.tar.gz
test ! -e ../rh56e2-local-models.tar.gz && tar -czf ../rh56e2-local-models.tar.gz \
  assets/rh56e2/somehand/assets/mjcf/inspire_rh56e2_left \
  assets/rh56e2/somehand/assets/mjcf/inspire_rh56e2_right
scp ../Teleopit-rh56e2.tar.gz unitree@192.168.123.164:/home/unitree/
scp ../rh56e2-local-models.tar.gz unitree@192.168.123.164:/home/unitree/
scp -r /path/to/arm64-wheelhouse unitree@192.168.123.164:/home/unitree/rh56e2-wheelhouse
```

打包脚本白名单收录提交源码、G1/GMR 运行模型、`track_g1.onnx` 和独立 C++ SDK 的 Git HEAD；
其中 G1 目录白名单包含本地 `g1_29dof_rh56e2.xml` 和 E2 网格；独立手部 MJCF 则在额外模型包中。
不包含环境、密钥、录制数据或白名单以外的未跟踪文件。源码目标压缩包已存在会拒绝覆盖，换文件名即可。
这些是给自己获授权设备使用的私下部署包，**不得上传到公开 GitHub Release 或其他公共下载地址**。
预览 BVH 不属于真机部署必需资源，因此不打包。

## 2. G1 解压并配置环境

```bash
ssh unitree@192.168.123.164
test ! -e "$HOME/Teleopit-rh56e2" && tar -xzf "$HOME/Teleopit-rh56e2.tar.gz" -C "$HOME"
source "$HOME/miniforge3/bin/activate"
conda create -n teleopit python=3.10
source "$HOME/miniforge3/bin/activate" teleopit
cd "$HOME/Teleopit-rh56e2"
tar --keep-old-files -xzf "$HOME/rh56e2-local-models.tar.gz"
bash scripts/setup/install_rh56e2.sh --wheelhouse "$HOME/rh56e2-wheelhouse"
```

解压前存在同名目录则上面的命令不会覆盖，请另选目录或先人工备份。
已有 `teleopit` 环境就跳过创建，直接 source 激活。
模型包解压也拒绝覆盖已有文件；仅解压自己刚生成并确认内容的包。
创建 Conda 环境本身也需要包缓存/联网源；wheelhouse 只覆盖 pip 包，不包含 Miniforge 环境包。
SDK 安装器只使用指定 wheelhouse，缺包会报名字，不回退到 GitHub 克隆。

编译身体 DDS 桥需要系统 CMake、C++ 编译器与匹配的 Unitree SDK 库。在 G1 环境中执行：

```bash
python -m pip install --no-index --find-links "$HOME/rh56e2-wheelhouse" setuptools wheel pybind11
CMAKE_BUILD_PARALLEL_LEVEL=2 python -m pip install --no-index --no-build-isolation ./third_party/g1_bridge_sdk
python scripts/dev/check_rh56e2.py --profile real
```

缺编译器或原生库时先补齐，不以“启动机器人试试”替代编译/导入检查。
安装成功后按使用说明核对网卡、PICO 广播地址、E2 IP/端口，再做只读检查；动作必须另行授权。
原 `$HOME/Teleopit` 和旧 repro 不覆盖、不删除，验证失败可继续使用原部署。

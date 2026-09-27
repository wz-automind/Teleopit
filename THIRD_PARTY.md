# 第三方来源与发布边界

上游 Teleopit 的 Apache-2.0 LICENSE 保留。fork 基线与集成来源见 MIGRATION.md。
`rh56e2-sdk` 是独立包，不将其源码或许可假设并入 Teleopit。

`assets/rh56e2/somehand/configs/retargeting/base/inspire_dfq.yaml` 与
`_universal_common.yaml` 来源 somehand `f0a6b42e151ca10a6eec3e24c24c10cd13c40314`。
E2 专用 MJCF/mesh/vendor 文件及 G1+E2 XML 不包含在本公开分支及其新增提交历史中。
本地迁移版本中的这些文件来自旧 repro 的相应 overlay，仅在本地保留；
不据本仓库的 Apache LICENSE 推定厂商素材也自动获得该授权。
公开发布这些模型前必须核查再分发权；获取和存放要求见 docs/zh/assets.md。

下载的 G1/GMR 资源和 ONNX 策略仍为外部运行资产，不新增提交到 Git；
C++ Unitree SDK 作为单独固定提交的本地外部源码，用于离线部署打包。
SDK 源码位于私有仓库，访问/分发需要相应授权。本公开仓库不包含 SDK 源码或 wheel。
部署包可能包含本地模型和私有 SDK；不得作为公开 Release 附件上传。
发布代码不代表已部署机器人，不复制录制数据与个人配置。

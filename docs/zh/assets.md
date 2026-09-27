# E2 外部模型准备

## 需要哪些文件

在 fork 根目录准备以下结构，路径和模型内部的关节命名必须与本集成匹配：

```text
assets/
  rh56e2/somehand/assets/mjcf/
    inspire_rh56e2_left/model.xml
    inspire_rh56e2_left/meshes/...
    inspire_rh56e2_right/model.xml
    inspire_rh56e2_right/meshes/...
  robots/unitree_g1/
    g1_29dof_rh56e2.xml
    meshes/rh56e2/left/...
    meshes/rh56e2/right/...
```

通用 G1/GMR 模型和策略仍按 `download_assets.py` 下载，**该下载器不会提供上面的 E2 专用文件**。
`assets/rh56e2/somehand/vendor/` 是原始导入素材，不是运行必需目录，不需传到 G1。
公开保留 somehand 的许可证与重定向 YAML；它们不替代模型。

## 如何补齐

已有获授权、验证过的本地集成资源时，按上述相对路径复制到新克隆目录，避免覆盖其他资源。
如果没有，请向设备供应商或项目维护者确认使用授权和匹配本项目的模型包。
本仓库目前没有可公开下载的 E2 模型包，也没有从任意厂商 URDF 自动生成组合模型的脚本；
不要把原始 URDF 改扩展名冒充这里的 XML。缺模型时不能声称 E2 仿真或手势重定向已可运行。

这些目录受 `.gitignore` 保护；不要 `git add -f`，也不要把本地全量部署压缩包上传公开仓库。
补齐依赖和模型后，执行：

```bash
python scripts/dev/check_rh56e2.py --profile sim
python -m pytest tests/test_rh56e2_resources.py -q
```

全套测试中的资源测试需要这些文件，缺失时会明确失败，而不是跳过后宣称仿真通过。
给自己获授权使用的 G1 转移本地模型，见 [SSH/SCP 部署](deployment.md)。

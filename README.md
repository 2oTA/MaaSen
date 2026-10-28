<!-- markdownlint-disable MD033 MD041 -->
<div align="center">

# MaaSen

**织梦森林 自动化挂机工具**

</div>

基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 开发的《织梦森林》日常自动化工具，源自 [MaaPracticeBoilerplate](https://github.com/MaaXYZ/MaaPracticeBoilerplate) 项目模板。

## 功能

- ✅ **进入游戏**：模拟器桌面点击游戏图标 → 等待加载 → 点击「进入森林」→ 自动关闭开屏广告 → 点击主界面的森林入口
- ✅ **复位视野**：双指捏合缩放到最小，再把镜头拖回中央，每次进入森林后视角一致

（更多功能开发中……）

## 使用方法

1. 前往 [Releases](../../releases) 下载最新版本 zip
2. 解压后双击运行，界面由通用 UI（MFAAvalonia）提供
3. 连接安卓模拟器（需开启 ADB；当前在 MuMu 模拟器 720×1280 竖屏下调试）
4. 把模拟器停在游戏所在桌面，确认游戏图标可见，勾选「进入游戏」「复位视野」后点击开始

> 「复位视野」依赖「进入游戏」结束时的森林场景；单独运行时请确保游戏已经进入森林。

## 更新

发布包是「UI + 资源」整包，更新有三种方式：

| 方式 | 操作 | 说明 |
| --- | --- | --- |
| 界面内更新 | 设置 → 更新设置 → 下载源选「GitHub」→ 检查资源 → 资源更新 | 下载整个平台包（约 130MB），连 UI 和 MaaFW 框架一起换成包内版本，完成后自动重启 |
| 重新下载全量包 | 同一页面 → 重新下载资源全量包 | 忽略版本号强制重下，资源损坏时使用 |
| 手动覆盖 | 下载新 zip，用其中的 `resource/` 和 `interface.json` 覆盖安装目录 | 只换资源，不动 UI 和框架 |

> 界面内更新依赖 GitHub Release 的 tag：只有推送了新 tag 才会检测到新版本。本项目未配置 Mirror酱，下载源请选「GitHub」。

详见 [更新与发版说明](./docs/zh_cn/update.md)。

## 开发

- 开发文档见 [docs/zh_cn/develop/](./docs/zh_cn/develop/how_to_develop.md)
- 任务链：`assets/resource/pipeline/launch_game.json`（进入游戏）、`assets/resource/pipeline/reset_view.json`（复位视野）
- 默认参数：`assets/resource/default_pipeline.json`
- 农田地块坐标：[docs/zh_cn/farm/plots.md](./docs/zh_cn/farm/plots.md)
- 本地校验：`npm ci && npx @nekosu/maa-tools check`
- 本地打包前先初始化模型子模块：`git submodule update --init --recursive`
- 发版：推送 tag（如 `v0.1.0`）后 CI 自动打包发布

## 免责声明

本项目仅供学习交流使用，使用本工具产生的一切后果（含账号风险）请自行承担。

## 鸣谢

本项目由 **[MaaFramework](https://github.com/MaaXYZ/MaaFramework)** 强力驱动，UI 由 [MFAAvalonia](https://github.com/SweetSmellFox/MFAAvalonia) 提供。

感谢 [MaaPracticeBoilerplate](https://github.com/MaaXYZ/MaaPracticeBoilerplate) 模板。

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

## 开发

- 开发文档见 [docs/zh_cn/develop/](./docs/zh_cn/develop/how_to_develop.md)
- 任务链：`assets/resource/pipeline/launch_game.json`（进入游戏）、`assets/resource/pipeline/reset_view.json`（复位视野）
- 默认参数：`assets/resource/default_pipeline.json`
- 本地校验：`npm ci && npx @nekosu/maa-tools check`
- 本地打包前先初始化模型子模块：`git submodule update --init --recursive`
- 发版：推送 tag（如 `v0.1.0`）后 CI 自动打包发布

## 免责声明

本项目仅供学习交流使用，使用本工具产生的一切后果（含账号风险）请自行承担。

## 鸣谢

本项目由 **[MaaFramework](https://github.com/MaaXYZ/MaaFramework)** 强力驱动，UI 由 [MFAAvalonia](https://github.com/SweetSmellFox/MFAAvalonia) 提供。

感谢 [MaaPracticeBoilerplate](https://github.com/MaaXYZ/MaaPracticeBoilerplate) 模板。

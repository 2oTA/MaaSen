<!-- markdownlint-disable MD033 MD041 -->
<div align="center">

# MaaSen

**织梦森林 自动化挂机工具**

</div>

基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 开发的《织梦森林》日常自动化工具，源自 [MaaPracticeBoilerplate](https://github.com/MaaXYZ/MaaPracticeBoilerplate) 项目模板。

## 功能

- ✅ 进入游戏：桌面找图标 → 等待加载 → 识别点击「进入森林」→ 自动关闭弹窗广告 → 点击主界面入口
- ✅ 居中视野：捏合缩放到最小 + 两段拖动自动居中，每次进入后视角一致

（更多功能开发中……）

## 使用方法

1. 前往 [Releases](../../releases) 下载最新版本 zip
2. 解压后双击运行，界面由通用 UI（MFAAvalonia）提供
3. 连接安卓设备 / 模拟器（需开启 ADB），选择「安卓端」控制器
4. 勾选「进入游戏」任务，点击开始

## 开发

- 开发文档见 [docs/zh_cn/develop/](./docs/zh_cn/develop/how_to_develop.md)
- 本地校验：`npm ci && npx @nekosu/maa-tools check`
- 任务链代码：`assets/resource/pipeline/launch_game.json`
- 发版：推送 tag（如 `v0.1.0`）后 CI 自动打包发布

## 免责声明

本项目仅供学习交流使用，使用本工具产生的一切后果（含账号风险）请自行承担。

## 鸣谢

本项目由 **[MaaFramework](https://github.com/MaaXYZ/MaaFramework)** 强力驱动，UI 由 [MFAAvalonia](https://github.com/SweetSmellFox/MFAAvalonia) 提供。

感谢 [MaaPracticeBoilerplate](https://github.com/MaaXYZ/MaaPracticeBoilerplate) 模板。

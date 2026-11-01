<!-- markdownlint-disable MD033 MD041 -->
<div align="center">

# MaaSen

**织梦森林 自动化挂机工具**

</div>

基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 开发的《织梦森林》日常自动化工具，源自 [MaaPracticeBoilerplate](https://github.com/MaaXYZ/MaaPracticeBoilerplate) 项目模板。

## 功能

- ✅ **进入游戏**：模拟器桌面点击游戏图标 → 等待加载 → 点击「进入森林」→ 自动关闭开屏广告 → 点击主界面的森林入口
- ✅ **复位视野**：双指捏合缩放到最小，再把镜头拖回中央，每次进入森林后视角一致
- 🔄 **更新数据**：进入花房读取已拥有的花，结果写入 `config/flowers.json`，并刷新「种植」里可选的「种植花朵」候选（只保留已获得的花）
- 🌱 **种植**：选择地块与花朵，点空地弹出种植列表 → 在花名上方的花朵图片上按下手指 → **全程不松手**地拖过该地块剩余的空地

（更多功能开发中……）

## 使用方法

1. 前往 [Releases](../../releases) 下载最新版本 zip
2. 解压后双击运行，界面由通用 UI（MFAAvalonia）提供
3. 连接安卓模拟器（需开启 ADB；当前在 MuMu 模拟器 720×1280 竖屏下调试）
4. 把模拟器停在游戏所在桌面，确认游戏图标可见，勾选「进入游戏」「复位视野」后点击开始

> 「复位视野」依赖「进入游戏」结束时的森林场景；单独运行时请确保游戏已经进入森林。

> 首次使用「种植」前先跑一次「更新数据」，它会按你实际拥有的花刷新「种植花朵」下拉框。MFAAvalonia 只在启动时读一次 `interface.json`（源码里是静态缓存，没有文件监听），所以**列表要等下次启动才变短**；不重启也能正常种——选一朵已获得的花即可，选到未获得的会立刻停下并列出你已拥有的花。

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
- 任务链：`assets/resource/pipeline/launch_game.json`（进入游戏）、`reset_view.json`（复位视野）、`greenhouse.json`（更新数据）、`plant.json`（种植）
- 默认参数：`assets/resource/default_pipeline.json`
- 农田地块坐标：[docs/zh_cn/farm/plots.md](./docs/zh_cn/farm/plots.md)
- 「更新数据」「种植」依赖 Python Agent：需要本机 Python 并 `pip install MaaFw`（发版前需改为内置解释器）
- 「更新数据」的滚动用 `touch_down / move / up` 手动实现，抬手前在终点停 `end_hold` 毫秒：游戏列表会按抬手速度做惯性滑，直接 `swipe` 会冲过头
- 「种植」的地块与花朵是两个 `select` 选项，分别覆盖 `PlantPlot` 与 `Plant` 两个节点的 `custom_action_param`——MaaFramework 的 `pipeline_override` 是整对象替换而不是深合并，两个参数必须落在不同节点上
- 「种植花朵」的候选列表是 `interface.json` 里 `option` 的最后一项，两头有 `// >>> 种植花朵候选` / `// <<< 种植花朵候选` 标记；「更新数据」按 `config/flowers.json` 的 `owned` 直接重写这两行之间的内容，所以界面只显示已获得的花。MFAAvalonia 只在启动时读一次 `interface.json`（`MaaProcessor.Interface` 是静态缓存，没有 FileSystemWatcher），改动在下次启动时生效；仓库里提交的默认值是完整 12 种花，没跑过「更新数据」时不会缺项
- 「种植」在开始时校验所选的花：不在 `owned` 里就直接报错并列出已获得的花，不会白跑一趟列表 OCR
- 本地校验：`npm ci && npx @nekosu/maa-tools check`
- 本地打包前先初始化模型子模块：`git submodule update --init --recursive`
- 发版：推送 tag（如 `v0.1.0`）后 CI 自动打包发布

## 免责声明

本项目仅供学习交流使用，使用本工具产生的一切后果（含账号风险）请自行承担。

## 鸣谢

本项目由 **[MaaFramework](https://github.com/MaaXYZ/MaaFramework)** 强力驱动，UI 由 [MFAAvalonia](https://github.com/SweetSmellFox/MFAAvalonia) 提供。

感谢 [MaaPracticeBoilerplate](https://github.com/MaaXYZ/MaaPracticeBoilerplate) 模板。

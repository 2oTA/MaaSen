<!-- markdownlint-disable MD033 MD041 -->
<div align="center">

# MaaSen

**织梦森林 自动化挂机工具**

</div>

基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 开发的《织梦森林》日常自动化工具，源自 [MaaPracticeBoilerplate](https://github.com/MaaXYZ/MaaPracticeBoilerplate) 项目模板。

## 功能

- ✅ **进入游戏**：模拟器桌面点击游戏图标 → 等待加载 → 点击「进入森林」→ 自动关闭开屏广告 → 点击主界面的森林入口
- ✅ **复位视野**：双指捏合缩放到最小，再把镜头拖回中央，每次进入森林后视角一致
- 🔄 **更新数据**：进入花房读取已拥有的花，结果写入 `config/flowers.json`，并把「种植」里的「种植花朵」候选刷新为已获得的花（候选有变化时自动重启 MFAAvalonia 立刻生效）
- 🌱 **种植**：勾选地块（可多选）与花朵，点空地弹出种植列表 → 在花名上方的花朵图片上按下手指 → **全程不松手**地拖过该地块剩余的空地
- 💧 **浇水**：识别农田里缺水的地 → 点一下让游戏弹出洒水壶 → 在洒水壶上按下手指，**全程不松手**地拖过所有缺水的地，全部浇完才抬手

（更多功能开发中……）

## 使用方法

1. 前往 [Releases](../../releases) 下载最新版本 zip
2. 解压后双击运行，界面由通用 UI（MFAAvalonia）提供
3. 连接安卓模拟器（需开启 ADB；当前在 MuMu 模拟器 720×1280 竖屏下调试）
4. 把模拟器停在游戏所在桌面，确认游戏图标可见，勾选「进入游戏」「复位视野」后点击开始

> 「复位视野」依赖「进入游戏」结束时的森林场景；单独运行时请确保游戏已经进入森林。

> 首次使用「种植」前先跑一次「更新数据」：没更新过时，「种植花朵」下拉框里只有一条「⚠ 首次使用请先运行「更新数据」并等待自动重启」的提示项。「更新数据」发现候选有变化时会让 MFAAvalonia 自己重启一次（约 8 秒）让新候选立刻生效——但重启会打断排在它后面的任务，所以请把「更新数据」放在任务列表最后。

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
- 任务链：`assets/resource/pipeline/launch_game.json`（进入游戏）、`reset_view.json`（复位视野）、`greenhouse.json`（更新数据）、`plant.json`（种植）、`water.json`（浇水）
- 默认参数：`assets/resource/default_pipeline.json`
- 农田地块坐标：[docs/zh_cn/farm/plots.md](./docs/zh_cn/farm/plots.md)
- 「更新数据」「种植」「浇水」依赖 Python Agent：需要本机 Python 并 `pip install MaaFw`（发版前需改为内置解释器）
- 「更新数据」的滚动用 `touch_down / move / up` 手动实现，抬手前在终点停 `end_hold` 毫秒：游戏列表会按抬手速度做惯性滑，直接 `swipe` 会冲过头
- 「种植」的地块与花朵是两个选项：「种植地块」是 `checkbox`（可多选，每块地对应一个独立节点 `PlantSelect1`~`PlantSelect6` 的 `custom_action_param`），「种植花朵」是 `select`（覆盖 `Plant` 节点）。之所以每块地单独一个节点，是因为 MaaFramework 的 `pipeline_override` 对 `custom_action_param` 是整对象替换而不是深合并，多个 case 覆盖同一节点会互相顶掉
- 「种植花朵」的候选列表是 `interface.json` 里 `option` 的最后一项，两头有 `// >>> 种植花朵候选` / `// <<< 种植花朵候选` 标记；「更新数据」按 `config/flowers.json` 的 `owned` 直接重写这两行之间的内容，所以界面只显示已获得的花。仓库里提交的默认值是一条「⚠ 首次使用请先运行「更新数据」并等待自动重启」提示项 + 完整 12 种花，第一次跑完更新数据后提示项就会被真实候选替换
- MFAAvalonia 只在启动时读一次 `interface.json`（`MaaProcessor.Interface` 是静态缓存，没有 FileSystemWatcher），而且任务运行中关窗会弹确认框，所以「更新数据」在候选变化后是用 detached 的 `cmd` 延迟 `taskkill /F` 掉父进程再 `start` 起来，实现自动重启
- 「种植」在开始时校验所选的花：候选还是提示项、没跑过「更新数据」、或选中的花不在 `owned` 里，都会直接报错并说明下一步，不会白跑一趟列表 OCR；一块地都没勾选也会直接提示
- 「浇水」不按地块四边形过滤（`only_in_plots: false`）：游戏镜头可以拖动/缩放，地块坐标只在「复位视野」后的固定视角成立，而缺水格子本身辨识度高，宁可宽松一点也不漏浇；识别区域 `farm_roi` 是比 6 块地并集更宽松的一块矩形
- 本地校验：`npm ci && npx @nekosu/maa-tools check`
- 本地打包前先初始化模型子模块：`git submodule update --init --recursive`
- 发版：推送 tag（如 `v0.1.0`）后 CI 自动打包发布

## 免责声明

本项目仅供学习交流使用，使用本工具产生的一切后果（含账号风险）请自行承担。

## 鸣谢

本项目由 **[MaaFramework](https://github.com/MaaXYZ/MaaFramework)** 强力驱动，UI 由 [MFAAvalonia](https://github.com/SweetSmellFox/MFAAvalonia) 提供。

感谢 [MaaPracticeBoilerplate](https://github.com/MaaXYZ/MaaPracticeBoilerplate) 模板。

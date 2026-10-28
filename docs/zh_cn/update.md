# 更新与发版说明

本文说明 MaaSen 的版本号构成、三种更新方式，以及发布新版本的流程。

## 三个版本号

界面「更新设置」里会同时显示三个版本号，它们是相互独立的：

| 版本 | 含义 | 由谁决定 |
| --- | --- | --- |
| 软件版本 | MFAAvalonia 自身版本 | UI 自己的更新通道 |
| 资源版本 | 本项目 `interface.json` 的 `version` | 发布时的 git tag（CI 打包时用 tag 覆盖） |
| 框架版本 | MaaFramework 运行时版本 | 随发布包一起携带 |

## 更新方式

### 通过界面更新

操作路径：设置 → 更新设置，把下载源切到「GitHub」，然后：

- **检查资源**：读取 `interface.json` 中的 `github`，调用 GitHub API 取最新 Release 的 tag，与本地资源版本做 semver 比较（`v` 前缀会被忽略）
- **资源更新**：仅在远端 tag 更新时可用
- **重新下载资源全量包**：忽略版本号强制重下，用于资源损坏或更新中断

实际行为如下（依据 MFAAvalonia 的 `VersionChecker` 实现）：

1. 按当前系统与架构，从 Release 资产中挑优先级最高的包（Windows x64 对应 `MaaSen-win-x86_64-vX.zip`）
2. 下载并解压整包（约 130MB）
3. 覆盖 `resource/`、`agent/`、`interface.json`
4. 因为包内含程序文件，还会覆盖 `MFAAvalonia.dll`、`runtimes/`、`libs/`、`plugins/` 等，但会跳过正在运行的 exe
5. 写入新的资源版本号，然后自动重启

因此**界面内的「资源更新」等价于整包更新**：资源、UI、框架会一起变成发布包自带的版本。如果希望固定某个 UI 或框架版本，请使用下面的手动更新。

> 本项目没有配置 `mirrorchyan_rid`，下载源请选择「GitHub」；选择 Mirror酱会提示当前资源不支持。

### 手动更新（只换资源）

1. 下载新 Release 的 zip
2. 解压，关闭正在运行的 MFAAvalonia
3. 用新包中的 `resource/` 覆盖安装目录的 `resource/`，并用新的 `interface.json` 覆盖旧文件
4. 重新启动

`config/`（设备与界面配置）和 `debug/`（日志）不在更新范围内，会保留。

### 重新下载全量包

资源文件损坏、更新卡住或版本号异常时，使用「重新下载资源全量包」；它会忽略版本比较，直接拉取最新包覆盖。

## 发版流程

```bash
# 1. 修改版本号
#    assets/interface.json -> "version": "0.1.2"

# 2. 提交并推送主干
git add .
git commit -m "chore: 版本号提升至 0.1.2"
git push origin main

# 3. 打 tag 并推送（触发 CI 打包与发布）
git tag v0.1.2
git push origin v0.1.2
```

推送 tag 后，`install` 工作流会自动构建 win / linux / macos / android 各架构的包并发布 Release，随后用户端「检查资源」即可看到新版本。

注意事项：

- 只推 main 不推 tag 不会产生新版本，界面内也检测不到
- tag 必须匹配 `v*`；带 `alpha`、`beta` 等字样的 tag 属于预发布，稳定渠道不会收到
- 已发布的 tag 不要移动或删除，修复问题请发新版本
- 发布包内 `interface.json` 的版本号会由 CI 用 tag 覆盖，本地文件里的版本号只用于开发

## 常见问题

**检查资源一直提示已是最新？**

确认三件事：远端是否推送了新 tag、下载源是否为 GitHub、`interface.json` 的 `github` 是否指向本项目。

**资源更新后软件版本变了？**

正常。整包更新会用发布包自带的 MFAAvalonia 覆盖安装目录中的程序文件。

**手动更新后版本号没变？**

手动更新需要一并替换 `interface.json`，资源版本号来自该文件。

**更新后配置丢失？**

`config/` 不在更新覆盖范围内；若确实丢失，请检查是否误删了安装目录下的 `config/`。

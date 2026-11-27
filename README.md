# Kimi Code ARM64（Frame）

面向 ARM64 Debian / Ubuntu 的非官方 Kimi Code 桌面集成应用。Frame 在后台管理官方 Kimi Code CLI 和本机 Kimi Web 服务，并通过独立 Chrome 应用窗口提供与官方浏览器一致的界面体验。

> 本项目不是 Kimi 官方 Desktop，也不修改或替代 Kimi Code 模型服务。核心能力由官方 Kimi Code CLI 提供。

**当前发行版本：2.0.14**（安装包：`dist/kimi-code-arm64_2.0.14_arm64.deb`）

## 2.0.14 发行说明

- 新增控制窗口“安装 Google Chrome”按钮：未安装浏览器时，一键从 Google 官方下载并安装 Chrome stable ARM64，全程显示进度，完成后自动打开 Kimi Web。
- 新增 Snap Chromium 检测（`/snap/bin/chromium`），浏览器探测覆盖 PATH、常见安装路径和 Snap。
- Chrome 异常退出时显示错误对话框和日志位置，不再静默退出应用；Chrome 输出统一记录到 `~/.cache/kimi-code-arm64/chrome.log`。
- 更新检查和信号处理等后台任务不再依赖浏览器是否就绪。
- 新增 `dist/clear-all.sh` 洁净清除脚本：先备份会话、凭据和配置，再卸载 Frame、CLI 和各浏览器，用于干净的重新安装。
- 2.x 已完全移除 WebKitGTK，截屏和文件对话框由 Chrome DevTools 原生桥接提供。

## 为什么做这个项目

Kimi Code 官方 Desktop 的 Linux 版本面向 x86_64，很多 ARM64 设备可以运行官方 CLI，却无法安装官方 Linux Desktop。Frame 不模拟 x86_64，也不重新实现 Kimi Code，而是组合官方 CLI、本机 Web 服务和 Chrome 应用窗口，提供统一的安装、升级、使用和安全退出入口。

```text
GTK 状态/控制窗口（按需显示）
    └── 后台启动官方 Kimi Code CLI
            └── CLI 启动本机 Kimi Web 服务
                    └── 独立 Chrome 应用窗口显示 Web 界面
```

## 主要功能

### 单窗口桌面体验

- 使用本机 Chrome / Chromium 显示 Kimi Web，滚动和渲染行为与直接打开 `kimi web` 一致。
- 正常运行只显示一个无地址栏、无标签栏的 Chrome 应用窗口，GTK 控制窗口自动隐藏。
- 重复点击应用图标时，只将现有对话窗口激活并置顶，不重复创建实例或控制窗口。
- 标题同时显示 CLI 和 Frame 版本，例如 `Kimi Code 2.8.1 · Frame 2.0.14`；未安装 CLI 时只显示 Frame 版本。
- 使用与 Kimi Web 官方 favicon 一致的应用图标。
- 默认关闭 Chrome 翻译功能和翻译弹窗，始终停留在原始页面。
- 使用独立配置目录 `~/.cache/kimi-code-arm64/chrome-profile`，不影响日常 Chrome 配置。

### 浏览器与 CLI 安装升级

- 未安装浏览器时，可一键从 Google 官方安装 Chrome stable ARM64，也可使用已安装的 Chromium（含 Snap 版）。
- 自动检测 `~/.kimi-code/bin/kimi` 和 `PATH` 中的 CLI。
- 未安装 CLI 时可通过控制窗口后台下载、校验并安装官方 ARM64 CLI，不需要单独安装 Node.js。
- 启动时检查官方更新，运行期间每 6 小时再次检查，仅在新版可用时显示升级按钮。
- 升级前安全停止 Web 服务，完成后自动恢复界面；失败时尝试恢复原有 CLI 和服务。
- 安装、升级日志保存在 `~/.cache/kimi-code-arm64/`。

### 会话与桌面桥接

- 共用 CLI 的账号、模型配置和 `~/.kimi-code/sessions/` 中的会话记录。
- 输入框“添加”菜单提供“截屏”，通过系统截图工具框选区域并添加 PNG 附件；取消框选不会添加附件。
- 支持网页文件选择对话框和外部链接打开。
- 截屏和对话框通过本机回环地址上的 Chrome DevTools Protocol 实现，不依赖 WebKit 或 Chrome 扩展。
- 为避免会话占用冲突，不建议 CLI 和 Web 同时向同一会话发送任务。

### 安全退出与默认值

- 关闭 Chrome 窗口或控制窗口都会触发安全退出。
- 优先调用经过认证的本地关闭接口，再使用 SIGTERM，最后才强制结束由本应用启动的进程。
- Web 服务仅监听 `127.0.0.1`，使用临时访问令牌认证 REST 和 WebSocket 连接。
- 不主动开放局域网访问，不启用绕过认证选项，CLI 和浏览器下载均使用官方来源。

## 支持环境

- ARM64（`aarch64` 或 `arm64`）
- Debian / Ubuntu
- Google Chrome stable ARM64 或 Chromium（含 Snap 版）；缺失时可由控制窗口一键安装
- 安装、升级 CLI 和使用模型服务时需要联网
- 使用官方模型需要相应的 Kimi 账号权限或会员权益，也可按 Web 界面提示配置模型服务

不提供 RPM、Alpine、Windows、macOS、x86_64 或离线安装包。

## 安装

独立安装说明见 [dist/install.txt](dist/install.txt)。

### 1. 获取文件

```bash
git clone https://github.com/mustaches/kimi-code-arm64.git
cd kimi-code-arm64/dist
```

也可以只复制以下文件到目标机器的同一目录：

```text
kimi-code-arm64_2.0.14_arm64.deb
kimi-code-arm64_2.0.14_arm64.deb.sha256
install-2.0.14.sh
install.txt
```

### 2. 校验并安装

```bash
uname -m
sha256sum -c kimi-code-arm64_2.0.14_arm64.deb.sha256
```

架构应为 `aarch64` 或 `arm64`，校验应显示 `OK` 或“确定/成功”。然后执行：

```bash
sudo apt update
install -m 0644 kimi-code-arm64_2.0.14_arm64.deb /tmp/
sudo apt install /tmp/kimi-code-arm64_2.0.14_arm64.deb
rm -f /tmp/kimi-code-arm64_2.0.14_arm64.deb
```

APT 会安装 Python、PyGObject、GTK、GNOME 截图工具和证书等依赖。Chrome / Chromium 需要自行安装（或由控制窗口一键安装），不包含在 DEB 强制依赖中。安装后会自动刷新图标缓存。

也可以使用一键脚本：

```bash
chmod +x install-2.0.14.sh
./install-2.0.14.sh
```

请以普通用户运行，脚本仅在需要时调用 sudo。

## 首次启动

从应用菜单启动 **Kimi Code ARM64**，或执行：

```bash
kimi-code-arm64
```

- 已安装 CLI：自动启动本机服务并打开 Chrome 应用窗口。
- 未安装 CLI：在控制窗口点击“安装 Kimi Code CLI”，等待下载和校验完成后按页面提示登录或配置模型服务。
- 未安装 Chrome / Chromium：点击控制窗口的“安装 Google Chrome”按钮，从 Google 官方下载并安装 Chrome stable ARM64，不使用 Snap 或 x86_64 安装包。

CLI 默认安装到 `~/.kimi-code/bin/kimi`。首次打开独立 Chrome 配置时，需要完成一次欢迎向导。

## 升级 CLI

当检测到更高版本时，控制窗口会显示升级按钮。升级流程为：安全停止当前服务 → 安装官方更新 → 重启服务和界面。安装或升级期间请勿强制结束应用。

## 安全退出

关闭 Chrome 窗口或控制窗口即可。应用会优先调用认证的本地关闭接口，必要时再结束后台进程，避免遗留本应用启动的 Web 服务。

## 卸载

仅卸载 Frame：

```bash
sudo apt remove kimi-code-arm64
```

不会删除 CLI、账号凭据、模型配置或会话记录，这些数据仍保存在 `~/.kimi-code`。如需清理 Frame 自己的缓存，可另行删除：

```bash
rm -rf ~/.cache/kimi-code-arm64 ~/.local/share/kimi-code-arm64
```

删除任何 CLI 数据前请先备份，不要手工编辑 `sessions` 中的会话文件。

如需为洁净安装清除 Frame、CLI、Google Chrome、Chromium 和 Snap Chromium，可使用：

```bash
./dist/clear-all.sh --dry-run  # 只预览，不做任何修改
./dist/clear-all.sh            # 输入 YES 后执行清理
./dist/clear-all.sh --yes      # 跳过确认，直接执行清理
```

脚本会先把 `~/.kimi-code` 和 Frame 缓存移动到 `~/kimi-code-arm64-backup-<时间戳>`，再卸载软件，因此会话、凭据和模型配置仍可恢复。

## 从源码构建

构建工具需要 `dpkg-deb`，不需要 root 权限：

```bash
git clone https://github.com/mustaches/kimi-code-arm64.git
cd kimi-code-arm64
./build-deb.sh
```

输出为 `dist/kimi-code-arm64_2.0.14_arm64.deb`。DEB 不包含 CLI，首次启动后由应用在线安装官方 CLI。

## 项目结构

```text
kimi-code-arm64/
├── kimi_code_arm64.py          # GTK 应用、CLI/浏览器安装升级和 Web 生命周期管理
├── cdp_bridge.py               # Chrome DevTools 客户端、截屏与外链处理
├── cdp_bridge.js               # 注入 Kimi Web 的桌面桥接
├── kimi-code-arm64.desktop     # Linux 应用菜单入口
├── kimi-code-arm64.png         # 应用图标（与 Kimi Web favicon 一致）
├── build-deb.sh                # DEB 构建脚本
├── packaging/
│   ├── control                 # DEB 元数据和运行依赖
│   └── kimi-code-arm64         # 系统启动命令
└── dist/
    ├── kimi-code-arm64_2.0.14_arm64.deb
    ├── kimi-code-arm64_2.0.14_arm64.deb.sha256
    ├── install-2.0.14.sh        # 一键安装脚本
    ├── clear-all.sh             # 备份后清除 CLI、浏览器和 Frame，供洁净安装
    └── install.txt              # 独立安装说明
```

## 故障排查

### 提示未找到 Chrome / Chromium

点击控制窗口的“安装 Google Chrome”按钮即可从 Google 官方安装 stable ARM64。也可以手动执行：

```bash
curl -fLO https://dl.google.com/linux/direct/google-chrome-stable_current_arm64.deb
sudo apt install ./google-chrome-stable_current_arm64.deb
```

安装完成后应用会自动启动 Kimi Web。下载和安装日志位于 `~/.cache/kimi-code-arm64/chrome-install.log`。

### 已安装 CLI，但应用提示未安装

```bash
kimi --version
~/.kimi-code/bin/kimi --version
```

确认 CLI 文件存在且具有执行权限。

### CLI 安装或 Web 启动失败

检查网络、DNS 和代理，并保留以下日志：

```text
~/.cache/kimi-code-arm64/cli-install.log
~/.cache/kimi-code-arm64/server.log
~/.cache/kimi-code-arm64/chrome.log
~/.cache/kimi-code-arm64/cdp.log
```

### APT 安装提示 `_apt` 无权读取本地 DEB

先将 DEB 以 `0644` 权限复制到 `/tmp`，再执行 `sudo apt install /tmp/<文件名>.deb`。检查安装状态：

```bash
dpkg-query -W -f='${Status}\n' kimi-code-arm64
```

应输出 `install ok installed`。

## 相关链接

- 项目仓库：<https://github.com/mustaches/kimi-code-arm64>
- Kimi Code 官方文档：<https://www.kimi.com/code/docs/en/>
- Kimi Code CLI 安装说明：<https://www.kimi.com/code/docs/en/kimi-code-cli/guides/getting-started.html>
- 独立安装文档：[dist/install.txt](dist/install.txt)

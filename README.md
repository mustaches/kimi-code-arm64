# Kimi Code ARM64

一个面向 ARM64 Debian / Ubuntu 的非官方 Kimi Code 桌面集成应用。

它通过本机 Chrome 应用窗口展示 Kimi Web 界面，GTK 窗口负责状态显示与控制，将 Kimi Code CLI 和 Kimi Web 集成在一起，提供桌面应用的使用体验，同时保留 CLI 的会话、账号和模型配置。

> 本项目不是 Kimi 官方 Desktop，也不修改或替代 Kimi Code 模型服务。核心能力由官方 Kimi Code CLI 提供。
> 2.0.3 起已完全移除 WebKitGTK 后端，界面统一由 Chrome 应用窗口提供；区域截屏和文件对话框通过 Chrome DevTools 原生桥接保留。

## 为什么做这个项目

Kimi Code 官方 Desktop 的 Linux 版本目前面向 x86_64，而很多 ARM64 开发设备可以正常运行 Kimi Code CLI，却无法安装官方 Linux Desktop。

ARM64 用户通常只能使用终端界面，存在以下不便：

- 关闭终端后，前台 CLI 进程会结束。
- 在 CLI、浏览器和多个终端之间切换不够方便。
- 没有统一的图形化安装、升级和安全退出入口。
- 官方 x86_64 Desktop 不能直接作为原生 ARM64 应用使用。

本项目的解决思路不是模拟 x86_64，也不是重新实现 Kimi Code，而是组合已经支持 ARM64 的官方组件：

```text
原生 GTK 状态/控制窗口
    └── 后台启动官方 Kimi Code CLI
            └── CLI 启动本机 Kimi Web 服务
                    └── Chrome 应用窗口显示 Web 界面
```

这样既保留官方 CLI 的能力和更新机制，也提供与官方浏览器一致的界面体验。项目已在多台 ARM64 实体机器上完成安装和运行验证。

## 主要功能

### Chrome 应用窗口界面

- 使用本机已安装的 Chrome / Chromium 显示 Web 界面，滚动、渲染行为与直接用浏览器打开 `kimi web` 完全一致。
- 使用独立配置目录 `~/.cache/kimi-code-arm64/chrome-profile`，不影响日常 Chrome 配置；首次打开需完成一次欢迎向导。
- 在应用菜单中提供“Kimi Code ARM64”启动入口。正常使用只显示一个无地址栏的 Chrome 应用窗口；GTK 控制窗口自动隐藏，安装、升级或出错时显示，也可通过应用图标重新唤出。
- 标题栏直接显示当前 Kimi Code CLI 的实际版本号（例如 `Kimi Code 2.8.1`），CLI 安装或升级后自动更新。
- 默认禁用 Chrome 翻译功能和翻译弹窗，启动始终停留在原始页面。
- 关闭 Chrome 窗口或 GTK 状态窗口都会触发同样的安全退出流程，本地服务随窗口关闭。
- 未安装 Chrome / Chromium 时，状态窗口会提示先安装浏览器，不会回退到 WebKit。
- 区域截屏和文件选择对话框通过 Chrome DevTools 原生桥接实现，不依赖 WebKit 或 Chrome 扩展。

### 自动安装 Kimi Code CLI

- 启动时自动检测 `~/.kimi-code/bin/kimi` 和 `PATH` 中的 CLI。
- 已有 CLI 时直接启动，不重复安装。
- 未安装 CLI 时，右上角显示“安装 Kimi Code CLI”。
- 点击按钮后，后台调用官方安装脚本，下载适用于 `linux-arm64` 的最新版本。
- 官方脚本会验证 CLI 文件的 SHA-256。
- 安装期间终端窗口保持隐藏，应用内显示当前进度。
- 不需要另外安装 Node.js。

### 自动检测和一键升级

- 应用启动时自动检查官方 CLI 最新版本。
- 应用运行期间每 6 小时再次检查。
- 仅在官方版本高于当前版本时显示升级按钮，避免误降级。
- 升级前安全停止 Web 服务，升级完成后自动恢复界面。
- 升级失败时尝试恢复原有 CLI 和 Web 服务。
- 安装和升级日志保存在本机，便于排查网络或下载问题。

### CLI 与 Web 会话集成

- 使用现有 Kimi CLI 账号、模型配置和会话数据。
- 已保存的 CLI 会话可以在 Web 界面中查看和继续。
- CLI 和 Web 打开同一会话时，可以查看相同的消息和工具执行记录。
- 会话默认保存在 `~/.kimi-code/sessions/`，关闭窗口不会删除历史记录。

为避免会话占用冲突，不建议 CLI 和 Web 同时向同一会话发送任务。

### 区域截屏与桌面桥接

- 输入框的“添加”菜单提供“截屏”入口，点击后使用系统截图工具框选区域，截图自动作为 PNG 附件添加到当前输入框。
- 按 Esc 或取消系统截图选择时不会添加附件，临时截图在读取后立即删除。
- 通过 Chrome DevTools Protocol 在本机回环地址与专用 Chrome 实例通信，不加载 Chrome 扩展，不需要 x86_64 模拟或 QEMU。
- 支持网页“打开文件”对话框和外部链接打开，行为与 1.x 一致。

### 安全退出

- 点击窗口右上角的原生关闭按钮即可执行安全退出流程。
- 优先调用经过认证的本地关闭接口，再使用 SIGTERM，最后才强制结束应用自己启动的进程。
- 支持 SIGTERM 和 SIGINT，降低注销或外部结束应用时遗留 Web 子进程的风险。
- 不会关闭不属于当前应用的其他 Kimi Web 实例。

### 本机安全默认值

- Web 服务仅监听 `127.0.0.1`。
- 使用临时访问令牌认证 REST 和 WebSocket 连接。
- 不主动开放局域网访问，不启用绕过认证选项。
- CLI 下载和升级使用 Kimi Code 官方来源。

## 支持环境

- 架构：ARM64，`uname -m` 输出 `aarch64` 或 `arm64`
- 系统：Debian / Ubuntu
- 浏览器：本机已安装 Google Chrome 或 Chromium（2.0.3 起必需）
- 安装包：DEB
- 网络：安装 APT 依赖、安装或升级 CLI、使用模型服务时均需要联网
- 账号：使用官方模型需要相应的 Kimi 账号权限或会员权益，也可以按 Web 界面提示配置可用模型服务

当前不提供 Fedora / RHEL 的 RPM 包，不支持 Alpine、Windows、macOS 或 x86_64 安装包，也不支持离线安装。

## 安装

独立的纯文本安装说明见 [dist/install.txt](dist/install.txt)。以下步骤与其内容一致。

### 1. 获取安装文件

可以直接克隆仓库：

```bash
git clone https://github.com/mustaches/kimi-code-arm64.git
cd kimi-code-arm64/dist
```

也可以只将以下三个文件下载或复制到目标机器的同一目录：

```text
kimi-code-arm64_2.0.3_arm64.deb
kimi-code-arm64_2.0.3_arm64.deb.sha256
install.txt
```

### 2. 确认系统架构

```bash
uname -m
```

输出应为：

```text
aarch64
```

或：

```text
arm64
```

### 3. 校验安装包

在 DEB 和 SHA-256 文件所在目录执行：

```bash
sha256sum -c kimi-code-arm64_2.0.3_arm64.deb.sha256
```

应显示 `OK` 或“确定/成功”。如果校验失败，请重新获取安装包，不要继续安装。

### 4. 安装应用及依赖

为避免 APT 的沙箱用户 `_apt` 无权读取用户主目录而出现权限提示，先以 `0644` 权限将 DEB 复制到 `/tmp`，再从该路径安装：

```bash
sudo apt update
install -m 0644 kimi-code-arm64_2.0.3_arm64.deb /tmp/
sudo apt install /tmp/kimi-code-arm64_2.0.3_arm64.deb
rm -f /tmp/kimi-code-arm64_2.0.3_arm64.deb
```

不需要关闭 APT 沙箱。APT 会安装 Python、PyGObject、GTK、curl 和证书等依赖。界面显示需要本机已安装 Chrome 或 Chromium（不在 DEB 依赖中强制安装）。

## 首次启动

在应用列表中启动 **Kimi Code ARM64**，或者执行：

```bash
kimi-code-arm64
```

如果已经安装 CLI，应用会直接打开 Web 界面。

如果尚未安装 CLI：

1. 点击右上角“安装 Kimi Code CLI”。
2. 等待后台下载、校验和安装完成。
3. 应用会自动启动 Web 服务并打开界面。
4. 按页面提示登录 Kimi 账号或配置模型服务。

CLI 默认安装位置：

```text
~/.kimi-code/bin/kimi
```

## CLI 升级

当检测到更高版本时，窗口上方会出现“升级 Kimi Code CLI”或“升级到某版本”按钮。

点击后应用会：

1. 安全停止当前 Web 服务。
2. 从官方来源下载并安装更新。
3. 自动重新启动 Web 服务。
4. 恢复 Kimi Code 界面。

安装或升级期间请耐心等待，不要强制杀进程。暂时无法检查更新不会影响当前版本继续使用。

## 安全退出

点击窗口右上角的原生关闭按钮，等待应用保存会话并关闭本地 Web 服务。

安全退出会优先调用经过认证的本地关闭接口，必要时再结束后台进程。

## 卸载

仅卸载图形应用：

```bash
sudo apt remove kimi-code-arm64
```

该命令不会自动删除 CLI、账号配置或会话记录。相关数据仍保存在：

```text
~/.kimi-code
```

如需删除，请先备份，不要手工编辑 `sessions` 中的会话文件。

## 从源码构建

构建工具需要 `dpkg-deb`，构建过程不需要 root 权限：

```bash
git clone https://github.com/mustaches/kimi-code-arm64.git
cd kimi-code-arm64
./build-deb.sh
```

构建结果：

```text
dist/kimi-code-arm64_2.0.3_arm64.deb
```

DEB 不包含 CLI。首次启动后由应用在线安装官方 CLI，因此分发包体积较小。

## 项目结构

```text
kimi-code-arm64/
├── kimi_code_arm64.py          # GTK 应用、CLI 安装升级和 Web 生命周期管理
├── cdp_bridge.py               # Chrome DevTools 客户端、截屏与外链处理
├── cdp_bridge.js               # 注入 Kimi Web 的桌面桥接
├── kimi-code-arm64.desktop     # Linux 应用菜单入口
├── kimi-code-arm64.svg         # 应用图标
├── build-deb.sh                # DEB 构建脚本
├── packaging/
│   ├── control                 # DEB 元数据和运行依赖
│   └── kimi-code-arm64         # 系统启动命令
└── dist/
    ├── kimi-code-arm64_2.0.3_arm64.deb
    ├── kimi-code-arm64_2.0.3_arm64.deb.sha256
    └── install.txt             # 独立安装说明
```

## 故障排查

### 界面滚动、渲染异常

2.0.3 起界面统一由 Chrome 应用窗口提供，行为与直接用浏览器打开 `kimi web` 一致，不再受 WebKitGTK 与 Kimi Web 虚拟滚动列表兼容性问题（滚动跳变、回滚）影响。如果菜单启动后仍出现旧式内嵌窗口，请确认已安装 2.0.3 并完全退出旧实例后再启动。

### 提示未找到 Chrome / Chromium

2.0.3 需要本机 Chrome 或 Chromium 显示界面。安装后重新启动应用即可：

```bash
google-chrome --version
```

### APT 依赖问题

```bash
sudo apt update
sudo apt --fix-broken install
install -m 0644 kimi-code-arm64_2.0.3_arm64.deb /tmp/
sudo apt install /tmp/kimi-code-arm64_2.0.3_arm64.deb
rm -f /tmp/kimi-code-arm64_2.0.3_arm64.deb
```

### `_apt` 无权读取本地 DEB

如果出现以下提示，但前面已经显示“正在设置 kimi-code-arm64”，通常不是安装失败：

```text
N: 由于文件 ... 无法被用户 '_apt' 访问，已脱离沙盒并提权为根用户
```

检查安装状态：

```bash
dpkg-query -W -f='${Status}\n' kimi-code-arm64
```

应输出：

```text
install ok installed
```

如果希望避免该提示，可以先把 DEB 复制到 `/tmp`，再在该目录执行安装命令。

### 已安装 CLI，但应用提示未安装

```bash
kimi --version
~/.kimi-code/bin/kimi --version
```

确认 CLI 文件存在且具有执行权限。

### CLI 安装失败

检查网络、DNS 和代理，确认能够访问：

```text
https://code.kimi.com/kimi-code/latest
```

安装日志：

```text
~/.cache/kimi-code-arm64/cli-install.log
```

### Web 启动失败

查看：

```text
~/.cache/kimi-code-arm64/server.log
```

升级失败时请保留安装日志和 Web 日志，以便进一步定位问题。

## 相关链接

- 项目仓库：<https://github.com/mustaches/kimi-code-arm64>
- Kimi Code 官方文档：<https://www.kimi.com/code/docs/en/>
- Kimi Code CLI 安装说明：<https://www.kimi.com/code/docs/en/kimi-code-cli/guides/getting-started.html>
- 独立安装文档：[dist/install.txt](dist/install.txt)

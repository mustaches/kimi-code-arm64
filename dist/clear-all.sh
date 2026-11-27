#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
ASSUME_YES=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --yes|-y) ASSUME_YES=1 ;;
        *)
            printf '未知参数：%s\n用法：%s [--dry-run] [--yes]\n' "$arg" "$0" >&2
            exit 2
            ;;
    esac
done

if [ "$EUID" -eq 0 ]; then
    printf '请勿使用 root 或 sudo 运行本脚本。需要管理员权限时会自动调用 sudo。\n' >&2
    exit 1
fi

printf '%s\n' '将执行以下操作：'
printf '%s\n' '  1. 停止 Frame、Kimi Web 和专用 Chrome 实例'
printf '%s\n' '  2. 备份 ~/.kimi-code 和 Frame 缓存到带时间戳的目录'
printf '%s\n' '  3. 卸载 kimi-code-arm64、Google Chrome、Chromium 和 Snap Chromium'
printf '%s\n' '  4. 删除 CLI 启动链接，保留备份供恢复或以后清理'

if [ "$ASSUME_YES" -ne 1 ]; then
    read -r -p '输入 YES 继续：' answer
    if [ "$answer" != "YES" ]; then
        printf '已取消，未做任何修改。\n'
        exit 0
    fi
fi

run() {
    printf '+'
    printf ' %q' "$@"
    printf '\n'
    if [ "$DRY_RUN" -eq 0 ]; then
        "$@"
    fi
}

stop_processes() {
    if [ "$DRY_RUN" -eq 1 ]; then
        printf '+ 停止 Frame、Kimi Web 和专用 Chrome 实例（模拟）\n'
        return
    fi
    pkill -TERM -f '/usr/lib/kimi-code-arm64/kimi_code_arm64.py' 2>/dev/null || true
    pkill -TERM -f 'kimi web --json' 2>/dev/null || true
    pkill -TERM -f 'chrome.*chrome-profile' 2>/dev/null || true
    sleep 3
}

remove_package() {
    local package=$1
    if dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed'; then
        run sudo apt remove -y "$package"
    else
        printf '未安装，跳过：%s\n' "$package"
    fi
}

stop_processes

remove_package kimi-code-arm64
remove_package google-chrome
remove_package google-chrome-stable
remove_package chromium
remove_package chromium-browser

if command -v snap >/dev/null 2>&1 && snap list chromium >/dev/null 2>&1; then
    run sudo snap remove chromium
else
    printf 'Snap Chromium 未安装，跳过。\n'
fi

if [ -L /usr/local/bin/kimi ]; then
    run sudo rm -f /usr/local/bin/kimi
fi
if [ -f "$HOME/.local/bin/kimi" ]; then
    run rm -f "$HOME/.local/bin/kimi"
fi

BACKUP="$HOME/kimi-code-arm64-backup-$(date +%Y%m%d-%H%M%S)"
run mkdir -p "$BACKUP"

for path in "$HOME/.kimi-code" "$HOME/.cache/kimi-code-arm64" "$HOME/.local/share/kimi-code-arm64"; do
    if [ -e "$path" ]; then
        run mv "$path" "$BACKUP/"
    fi
done

printf '\n清理完成。会话、凭据和模型配置已保留在：\n%s\n' "$BACKUP"
printf '%s\n' '现在可以进行洁净安装。确认不再需要备份后，可手动删除该目录。'

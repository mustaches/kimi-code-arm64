#!/usr/bin/env bash
set -euo pipefail

TARGET_VERSION="2.0.1"
PACKAGE="kimi-code-arm64"
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
DEB_NAME="${PACKAGE}_${TARGET_VERSION}_arm64.deb"
DEB_PATH="$SCRIPT_DIR/$DEB_NAME"
CHECKSUM_PATH="$DEB_PATH.sha256"
TMP_DEB=""

fail() {
    printf '错误：%s\n' "$1" >&2
    exit 1
}

cleanup() {
    if [[ -n "$TMP_DEB" ]]; then
        rm -f -- "$TMP_DEB"
    fi
}
trap cleanup EXIT

script_version() {
    local path=$1
    sed -n \
        -e 's/^APP_VERSION = "\([^"]*\)"$/\1/p' \
        -e "s/^APP_VERSION = '\([^']*\)'$/\1/p" \
        "$path" | head -n 1
}

check_higher_version() {
    local version=$1
    local source=$2

    if [[ ! $version =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$ ]]; then
        fail "无法识别 $source 中的版本号 $version，为避免误删已停止。"
    fi
    if dpkg --compare-versions "$version" gt "$TARGET_VERSION"; then
        printf '发现更高版本 %s（%s）。\n' "$version" "$source"
        printf '当前脚本仅安装 %s，未做任何更改，现已退出。\n' "$TARGET_VERSION"
        exit 0
    fi
}

remove_user_residual() {
    local path=$1
    if [[ -f $path || -L $path ]]; then
        printf '清除残留：%s\n' "$path"
        rm -f -- "$path"
        RESIDUAL_FOUND=1
    fi
}

remove_system_residual() {
    local path=$1
    if [[ -f $path || -L $path ]]; then
        printf '清除系统残留：%s\n' "$path"
        sudo rm -f -- "$path"
        RESIDUAL_FOUND=1
    fi
}

if (( EUID == 0 )); then
    fail "请使用普通用户运行本脚本，不要对整个脚本使用 sudo。"
fi

command -v dpkg >/dev/null 2>&1 || fail "未找到 dpkg。"
command -v apt >/dev/null 2>&1 || fail "未找到 apt。"
command -v sudo >/dev/null 2>&1 || fail "未找到 sudo。"
command -v sha256sum >/dev/null 2>&1 || fail "未找到 sha256sum。"
[[ $(dpkg --print-architecture) == "arm64" ]] || fail "此安装包仅支持 ARM64 系统。"

printf '正在扫描已安装版本……\n'
INSTALLED_VERSION=""
if [[ $(dpkg-query -W -f='${Status}' "$PACKAGE" 2>/dev/null || true) == "install ok installed" ]]; then
    INSTALLED_VERSION=$(dpkg-query -W -f='${Version}' "$PACKAGE")
    printf '检测到 DPKG 安装版本：%s\n' "$INSTALLED_VERSION"
    check_higher_version "$INSTALLED_VERSION" "DPKG 软件包"
else
    printf '未发现已安装的 DPKG 软件包。\n'
fi

MANUAL_SCRIPTS=(
    "$HOME/.local/share/kimi-code-arm64/kimi_code_arm64.py"
    "/usr/local/lib/kimi-code-arm64/kimi_code_arm64.py"
    "/usr/local/share/kimi-code-arm64/kimi_code_arm64.py"
    "/usr/lib/kimi-code-arm64/kimi_code_arm64.py"
)

for path in "${MANUAL_SCRIPTS[@]}"; do
    [[ -f $path ]] || continue
    VERSION=$(script_version "$path")
    [[ -n $VERSION ]] || fail "无法读取 $path 中的版本号，为避免误删已停止。"
    printf '检测到程序文件：%s（版本 %s）\n' "$path" "$VERSION"
    check_higher_version "$VERSION" "$path"
done

if [[ $INSTALLED_VERSION == "1.1.0" ]]; then
    printf '正在卸载 DPKG 管理的 1.1.0 版本……\n'
    sudo apt remove -y "$PACKAGE"
elif [[ -n $INSTALLED_VERSION ]]; then
    printf '当前 DPKG 版本不是 1.1.0，无需先行卸载。\n'
else
    printf '无需卸载 DPKG 软件包。\n'
fi

printf '正在检查旧版残留文件……\n'
RESIDUAL_FOUND=0
USER_RESIDUALS=(
    "$HOME/.local/bin/kimi-code-arm64"
    "$HOME/.local/share/kimi-code-arm64/kimi_code_arm64.py"
    "$HOME/.local/share/applications/kimi-code-arm64.desktop"
    "$HOME/.local/share/icons/hicolor/scalable/apps/kimi-code-arm64.svg"
)
SYSTEM_RESIDUALS=(
    "/usr/local/bin/kimi-code-arm64"
    "/usr/local/lib/kimi-code-arm64/kimi_code_arm64.py"
    "/usr/local/share/kimi-code-arm64/kimi_code_arm64.py"
    "/usr/local/share/applications/kimi-code-arm64.desktop"
    "/usr/local/share/icons/hicolor/scalable/apps/kimi-code-arm64.svg"
)

for path in "${USER_RESIDUALS[@]}"; do
    remove_user_residual "$path"
done
for path in "${SYSTEM_RESIDUALS[@]}"; do
    remove_system_residual "$path"
done

if (( ! RESIDUAL_FOUND )); then
    printf '未发现需要清除的残留文件。\n'
fi

[[ -f $DEB_PATH ]] || fail "未找到安装包：$DEB_PATH"
[[ -f $CHECKSUM_PATH ]] || fail "未找到校验文件：$CHECKSUM_PATH"

printf '正在校验 %s……\n' "$DEB_NAME"
(
    cd "$SCRIPT_DIR"
    sha256sum -c "$DEB_NAME.sha256"
)

TMP_DEB=$(mktemp "/tmp/${PACKAGE}_${TARGET_VERSION}.XXXXXX.deb")
install -m 0644 "$DEB_PATH" "$TMP_DEB"

printf '正在更新 APT 软件索引……\n'
sudo apt update
printf '正在安装 %s……\n' "$TARGET_VERSION"
sudo apt install -y "$TMP_DEB"

FINAL_VERSION=$(dpkg-query -W -f='${Version}' "$PACKAGE" 2>/dev/null || true)
[[ $FINAL_VERSION == "$TARGET_VERSION" ]] || fail "安装后版本验证失败，当前版本为 ${FINAL_VERSION:-未知}。"

hash -r
printf '安装完成：%s %s\n' "$PACKAGE" "$FINAL_VERSION"
printf '顶部标题：Kimi Code Frame(%s)\n' "$FINAL_VERSION"
printf '现在可以运行：kimi-code-arm64\n'

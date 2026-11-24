#!/usr/bin/env python3
import html
import json
import os
import re
import select
import signal
import shutil
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

os.environ.setdefault("WEBKIT_DISABLE_COMPOSITING_MODE", "1")
os.environ.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gio, GLib, Gtk, WebKit2

APP_ID = "com.kimi.CodeARM64"
APP_VERSION = "1.1.0"
INSTALL_URL = "https://code.kimi.com/kimi-code/install.sh"
LATEST_URL = "https://code.kimi.com/kimi-code/latest"
APP_DATA = Path.home() / ".local/share/kimi-code-arm64"
APP_CACHE = Path.home() / ".cache/kimi-code-arm64"


def discover_kimi():
    candidates = []
    override = os.environ.get("KIMI_CODE_ARM64_CLI")
    if override:
        candidates.append(Path(override).expanduser())
    candidates.append(Path.home() / ".kimi-code/bin/kimi")
    path_kimi = shutil.which("kimi")
    if path_kimi:
        candidates.append(Path(path_kimi))
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    return None


def version_key(version):
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?", version)
    if not match:
        return (0, 0, 0, 0)
    major, minor, patch = (int(match.group(index)) for index in range(1, 4))
    return (major, minor, patch, 0 if match.group(4) else 1)


def current_version(cli_path):
    output = subprocess.check_output(
        [str(cli_path), "--version"],
        stderr=subprocess.STDOUT,
        text=True,
        timeout=15,
    ).strip()
    version = output.split()[0] if output else ""
    if not re.match(r"^\d+\.\d+\.\d+", version):
        raise RuntimeError("无法识别 CLI 版本")
    return version


def latest_version():
    request = urllib.request.Request(
        LATEST_URL,
        headers={"User-Agent": f"Kimi-Code-ARM64/{APP_VERSION}"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        version = response.read(128).decode("utf-8").strip()
    if not re.match(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$", version):
        raise RuntimeError("官方更新接口返回了无效版本")
    return version


def run_stream(command, log_name, on_progress, env=None):
    APP_CACHE.mkdir(parents=True, exist_ok=True)
    lines = []
    with (APP_CACHE / log_name).open("w") as log:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            start_new_session=True,
        )
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            lines.append(line)
            lines = lines[-8:]
            log.write(line + "\n")
            log.flush()
            GLib.idle_add(on_progress, line)
        return_code = process.wait()
    return return_code, "\n".join(lines)


def install_native_cli(on_progress):
    environment = os.environ.copy()
    environment["KIMI_INSTALL_DIR"] = str(Path.home() / ".kimi-code")
    return run_stream(
        ["bash", "-c", f"set -o pipefail; curl -fsSL {INSTALL_URL} | bash"],
        "cli-install.log",
        on_progress,
        environment,
    )


def page_html(title, message, busy=True):
    spinner = '<div class="spinner"></div>' if busy else ""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
html,body{{height:100%;margin:0;background:#101114;color:#eee;font-family:sans-serif}}
body{{display:flex;align-items:center;justify-content:center}}
main{{text-align:center;max-width:640px;padding:40px}}
.mark{{width:58px;height:58px;margin:0 auto 24px;border-radius:16px;background:#1565d8;color:white;font-size:34px;font-weight:700;line-height:58px}}
h1{{font-size:22px;font-weight:600;margin:0 0 14px}}
p{{color:#a8abb3;font-size:14px;line-height:1.7;margin:0;white-space:pre-wrap;overflow-wrap:anywhere}}
.spinner{{width:24px;height:24px;border:3px solid #333;border-top-color:#5b9cf6;border-radius:50%;margin:24px auto 0;animation:spin .8s linear infinite}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
</style>
</head>
<body><main><div class="mark">K</div><h1>{html.escape(title)}</h1><p>{html.escape(message)}</p>{spinner}</main></body>
</html>"""


class KimiServer:
    def __init__(self, cli_path, on_ready, on_failure):
        self.cli_path = cli_path
        self.on_ready = on_ready
        self.on_failure = on_failure
        self.process = None
        self.origin = None
        self.token = None
        self.stopping = False
        self.starting = False
        self.log = None

    def start(self):
        self.starting = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            APP_CACHE.mkdir(parents=True, exist_ok=True)
            self.log = (APP_CACHE / "server.log").open("a")
            self.process = subprocess.Popen(
                [str(self.cli_path), "web", "--json", "--port", "58639"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=self.log,
                text=True,
                start_new_session=True,
            )
            if self.stopping:
                return
            readable, _, _ = select.select([self.process.stdout], [], [], 30)
            if not readable:
                raise RuntimeError("Kimi Web 启动超时，请查看 ~/.cache/kimi-code-arm64/server.log")
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError("Kimi Web 未能启动，请查看 ~/.cache/kimi-code-arm64/server.log")
            payload = json.loads(line)
            origin = payload["origin"]
            token = payload["token"]
            parsed = urllib.parse.urlsplit(origin)
            if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not token:
                raise RuntimeError("Kimi Web 返回了不安全的本地地址")
            self.origin = origin.rstrip("/")
            self.token = token
            self.starting = False
            url = f"{self.origin}/#token={urllib.parse.quote(token, safe='')}"
            GLib.idle_add(self.on_ready, url)
            return_code = self.process.wait()
            if not self.stopping:
                GLib.idle_add(self.on_failure, f"Kimi Web 意外退出，退出码：{return_code}")
        except Exception as error:
            self.starting = False
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            if not self.stopping:
                GLib.idle_add(self.on_failure, str(error))

    def stop(self, callback):
        if self.stopping:
            GLib.idle_add(callback)
            return
        self.stopping = True
        threading.Thread(target=self._stop, args=(callback,), daemon=True).start()

    def _stop(self, callback):
        deadline = time.monotonic() + 30
        while self.process is None and self.starting and time.monotonic() < deadline:
            time.sleep(0.05)
        process = self.process
        if process is not None and process.poll() is None:
            self._request_shutdown()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        if process is not None and process.stdout is not None:
            process.stdout.close()
        if self.log is not None:
            self.log.close()
        GLib.idle_add(callback)

    def _request_shutdown(self):
        if not self.origin or not self.token:
            return
        request = urllib.request.Request(
            f"{self.origin}/api/v1/shutdown",
            data=b"",
            method="POST",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=3):
                pass
        except Exception:
            pass


class KimiWindow(Gtk.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application)
        self.application = application
        self.set_title("Kimi Code ARM64")
        self.set_default_size(1280, 800)

        self.header = Gtk.HeaderBar(title="Kimi Code", subtitle="ARM64 桌面集成")
        self.header.set_show_close_button(True)
        self.update_button = Gtk.Button(label="升级 Kimi Code CLI")
        self.update_button.get_style_context().add_class("suggested-action")
        self.update_button.connect("clicked", lambda *_args: application.upgrade_cli())
        self.update_button.set_no_show_all(True)
        self.header.pack_end(self.update_button)
        self.action_button = Gtk.Button(label="退出kimi code")
        self.action_button.get_style_context().add_class("destructive-action")
        self.action_button.connect("clicked", lambda *_args: application.primary_action())
        self.header.pack_end(self.action_button)
        self.set_titlebar(self.header)

        data_dir = APP_DATA / "webkit"
        cache_dir = APP_CACHE / "webkit"
        data_dir.mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)
        data_manager = WebKit2.WebsiteDataManager(
            base_data_directory=str(data_dir),
            base_cache_directory=str(cache_dir),
        )
        context = WebKit2.WebContext(website_data_manager=data_manager)
        self.webview = WebKit2.WebView(web_context=context)
        self.add(self.webview)
        self.connect("delete-event", self._on_delete)

    def show_missing(self, message=""):
        self.update_button.hide()
        self.action_button.set_sensitive(True)
        self.action_button.set_label("安装 Kimi Code CLI")
        self.action_button.get_style_context().remove_class("destructive-action")
        self.action_button.get_style_context().add_class("suggested-action")
        self.header.set_subtitle("需要安装 Kimi Code CLI")
        detail = message or "应用需要联网下载官方最新版 CLI。安装完成后会自动启动，终端窗口保持隐藏。"
        self.webview.load_html(page_html("尚未安装 Kimi Code CLI", detail, False), None)

    def show_starting(self):
        self.action_button.set_sensitive(True)
        self.action_button.set_label("退出kimi code")
        self.action_button.get_style_context().add_class("destructive-action")
        self.action_button.get_style_context().remove_class("suggested-action")
        self.header.set_subtitle("CLI 已在后台启动，终端不可见")
        self.webview.load_html(page_html("正在启动 Kimi Code", "正在准备 Web 界面…"), None)

    def show_operation(self, title, message, button_label):
        self.action_button.set_sensitive(False)
        self.action_button.set_label(button_label)
        self.update_button.set_sensitive(False)
        self.webview.load_html(page_html(title, message), None)

    def show_progress(self, message):
        if self.application.operation in {"install", "upgrade"}:
            self.header.set_subtitle(message[-160:])
        return False

    def server_ready(self, url):
        if self.application.operation != "exit":
            self.webview.load_uri(url)
            self.action_button.set_sensitive(True)
            self.action_button.set_label("退出kimi code")
        return False

    def server_failed(self, message):
        if self.application.operation != "exit":
            self.webview.load_html(page_html("Kimi Code 启动失败", message, False), None)
            self.action_button.set_sensitive(True)
        return False

    def set_status(self, message):
        self.header.set_subtitle(message)
        return False

    def show_update(self, version):
        self.update_button.set_label(f"升级到 {version}")
        self.update_button.set_sensitive(True)
        self.update_button.show()
        return False

    def hide_update(self):
        self.update_button.hide()
        return False

    def _on_delete(self, *_args):
        self.application.request_exit()
        return True


class KimiApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.window = None
        self.server = None
        self.cli_path = None
        self.latest = None
        self.operation = None
        self.checking_updates = False

    def do_activate(self):
        if self.window is not None:
            self.window.present()
            return
        self.window = KimiWindow(self)
        self.window.show_all()
        self.window.update_button.hide()
        self.cli_path = discover_kimi()
        if self.cli_path:
            self.start_server()
        else:
            self.window.show_missing()
        GLib.timeout_add_seconds(21600, self._periodic_update_check)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self._on_unix_signal)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self._on_unix_signal)

    def _on_unix_signal(self):
        self.request_exit()
        return False

    def primary_action(self):
        if self.cli_path:
            self.request_exit()
        else:
            self.install_cli()

    def start_server(self, check=True):
        self.window.show_starting()
        self.server = KimiServer(self.cli_path, self.window.server_ready, self.window.server_failed)
        self.server.start()
        if check:
            self.check_updates()

    def install_cli(self):
        if self.operation:
            return
        self.operation = "install"
        self.window.show_operation("正在安装 Kimi Code CLI", "正在从官方源下载最新版并校验安装文件…", "正在安装…")
        threading.Thread(target=self._install_worker, daemon=True).start()

    def _install_worker(self):
        try:
            code, output = install_native_cli(self.window.show_progress)
            path = discover_kimi() if code == 0 else None
            GLib.idle_add(self._install_done, code, output, path)
        except Exception as error:
            GLib.idle_add(self._install_done, 1, str(error), None)

    def _install_done(self, code, output, path):
        self.operation = None
        if code == 0 and path:
            self.cli_path = path
            self.window.set_status("CLI 安装完成，正在启动…")
            self.start_server()
        else:
            self.cli_path = None
            self.window.show_missing(f"安装失败，请检查网络后重试。\n\n{output}\n\n日志：{APP_CACHE / 'cli-install.log'}")
        return False

    def check_updates(self):
        if not self.cli_path or self.checking_updates or self.operation:
            return
        self.checking_updates = True
        self.window.set_status("正在检查 CLI 更新…")
        threading.Thread(target=self._update_check_worker, daemon=True).start()

    def _update_check_worker(self):
        try:
            installed = current_version(self.cli_path)
            latest = latest_version()
            GLib.idle_add(self._update_check_done, installed, latest, "")
        except Exception as error:
            GLib.idle_add(self._update_check_done, "", "", str(error))

    def _update_check_done(self, installed, latest, error):
        self.checking_updates = False
        if error:
            self.window.set_status(f"CLI 更新检查失败：{error}")
            return False
        if version_key(latest) > version_key(installed):
            self.latest = latest
            self.window.set_status(f"CLI {installed} → {latest} 可用")
            self.window.show_update(latest)
        else:
            self.latest = None
            self.window.hide_update()
            self.window.set_status(f"CLI {installed} · 当前版本无需升级")
        return False

    def _periodic_update_check(self):
        self.check_updates()
        return True

    def upgrade_cli(self):
        if self.operation or not self.latest or not self.cli_path:
            return
        self.operation = "upgrade"
        self.window.show_operation("正在升级 Kimi Code CLI", "先安全关闭 Web 服务，再安装更新并自动重启…", "正在升级…")
        if self.server:
            self.server.stop(self._upgrade_after_stop)
        else:
            self._upgrade_after_stop()

    def _upgrade_after_stop(self):
        threading.Thread(target=self._upgrade_worker, daemon=True).start()
        return False

    def _upgrade_worker(self):
        try:
            native_path = Path.home() / ".kimi-code/bin/kimi"
            if self.cli_path == native_path:
                code, output = install_native_cli(self.window.show_progress)
            else:
                code, output = run_stream(
                    [str(self.cli_path), "upgrade", "-y"],
                    "cli-upgrade.log",
                    self.window.show_progress,
                )
            path = discover_kimi() if code == 0 else self.cli_path
            GLib.idle_add(self._upgrade_done, code, output, path)
        except Exception as error:
            GLib.idle_add(self._upgrade_done, 1, str(error), self.cli_path)

    def _upgrade_done(self, code, output, path):
        self.operation = None
        self.cli_path = path
        if code == 0:
            self.window.hide_update()
            self.latest = None
            self.window.set_status("CLI 升级完成，正在重启…")
            self.start_server(check=False)
            self.check_updates()
        else:
            self.window.set_status(f"升级失败，已恢复 CLI：{output[-180:]}")
            self.window.show_update(self.latest)
            if self.cli_path:
                self.start_server(check=False)
            else:
                self.window.show_missing(output)
        return False

    def request_exit(self):
        if self.operation == "exit":
            return
        if self.operation in {"install", "upgrade"}:
            self.window.set_status("请等待安装或升级完成后再退出")
            return
        self.operation = "exit"
        self.window.show_operation("正在安全退出", "正在保存会话并关闭本地 Kimi Web 服务…", "正在安全退出…")
        if self.server:
            self.server.stop(self.finish_exit)
        else:
            self.finish_exit()

    def finish_exit(self):
        self.quit()
        return False


if __name__ == "__main__":
    GLib.set_prgname("kimi-code-arm64")
    raise SystemExit(KimiApplication().run(None))

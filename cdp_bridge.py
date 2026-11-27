import base64
import json
import os
import socket
import struct
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

APP_CACHE = Path.home() / ".cache/kimi-code-arm64"
BRIDGE_JS = (Path(__file__).resolve().parent / "cdp_bridge.js").read_text()


class WebSocket:
    def __init__(self, url):
        rest = url[5:]
        hostport, path = rest.split("/", 1)
        host, port = hostport.split(":")
        self.sock = socket.create_connection((host, int(port)), timeout=15)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode())
        buffer = b""
        while b"\r\n\r\n" not in buffer:
            buffer += self.sock.recv(4096)
        if b"101" not in buffer.split(b"\r\n")[0]:
            raise ConnectionError("websocket handshake failed")
        self.sock.settimeout(None)

    def send(self, text):
        data = text.encode()
        header = bytearray([0x81])
        mask = os.urandom(4)
        length = len(data)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", length)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", length)
        header += mask
        self.sock.sendall(bytes(header) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _read_exact(self, count):
        buffer = b""
        while len(buffer) < count:
            chunk = self.sock.recv(count - len(buffer))
            if not chunk:
                raise ConnectionError("websocket closed")
            buffer += chunk
        return buffer

    def recv(self):
        payload = b""
        while True:
            first, second = self._read_exact(2)
            fin = first & 0x80
            opcode = first & 0x0F
            length = second & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._read_exact(8))[0]
            mask = self._read_exact(4) if second & 0x80 else None
            data = self._read_exact(length)
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if opcode == 9:
                continue
            payload += data
            if fin:
                return payload.decode()


class CdpBridge:
    def __init__(self, on_open_dialog):
        self.on_open_dialog = on_open_dialog
        self.next_id = 0
        self.pending = {}
        self.condition = threading.Condition()
        self.ws = None
        self.stopped = False
        self.title = None

    def _log(self, message):
        if os.environ.get("KIMI_CODE_ARM64_CDP_DEBUG") != "1":
            return
        try:
            APP_CACHE.mkdir(parents=True, exist_ok=True)
            with (APP_CACHE / "cdp.log").open("a") as log:
                log.write(f"{time.strftime('%H:%M:%S')} {message}\n")
        except OSError:
            pass

    def start(self, port, url=None, title=None):
        self.title = title
        deadline = time.monotonic() + 90
        while True:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=3) as response:
                    targets = json.load(response)
                page = next(target for target in targets if target.get("type") == "page")
                self.ws = WebSocket(page["webSocketDebuggerUrl"])
                break
            except Exception:
                if self.stopped or time.monotonic() > deadline:
                    return
                time.sleep(0.5)
        self._log("bridge connected")
        threading.Thread(target=self._reader, daemon=True).start()
        self.call("Runtime.enable")
        self.call("Page.enable")
        self.call("Runtime.addBinding", {"name": "__kimiNativeBridge"})
        try:
            self.call("Page.addScriptToEvaluateOnLoad", {"scriptSource": BRIDGE_JS})
        except RuntimeError:
            self.call("Page.addScriptToEvaluateOnLoad", {"source": BRIDGE_JS})
        if url:
            self.call("Page.navigate", {"url": url})
        else:
            self._inject()

    def stop(self):
        self.stopped = True
        if self.ws:
            try:
                self.ws.sock.close()
            except OSError:
                pass

    def call(self, method, params=None):
        with self.condition:
            self.next_id += 1
            message_id = self.next_id
            event = threading.Event()
            self.pending[message_id] = (event, {})
            self.ws.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        if not event.wait(timeout=30):
            raise TimeoutError(method)
        message = self.pending.pop(message_id)[1]
        if "error" in message:
            raise RuntimeError(message["error"])
        return message.get("result", {})

    def _reader(self):
        while not self.stopped:
            try:
                raw = self.ws.recv()
            except (OSError, ConnectionError) as error:
                self._log(f"reader stopped: {error}")
                break
            except Exception as error:
                self._log(f"reader error: {error}")
                break
            try:
                message = json.loads(raw)
            except ValueError:
                continue
            self._dispatch(message)

    def _dispatch(self, message):
        if "id" in message:
            entry = self.pending.get(message["id"])
            if entry:
                event, result = entry
                result.update(message)
                event.set()
            return
        method = message.get("method")
        params = message.get("params") or {}
        if method == "Page.loadEventFired":
            threading.Thread(target=self._inject, daemon=True).start()
        elif method == "Runtime.bindingCalled":
            self._log(f"binding called: {str(params)[:160]}")
            threading.Thread(target=self._on_binding, args=(params,), daemon=True).start()

    def _inject(self):
        try:
            self.call("Runtime.addBinding", {"name": "__kimiNativeBridge"})
            self.call("Runtime.evaluate", {"expression": BRIDGE_JS})
            self._apply_title()
        except (OSError, TimeoutError):
            pass

    def _apply_title(self):
        if not self.title:
            return
        title = json.dumps(self.title, ensure_ascii=False)
        script = f"window.__kimiSetTitle ? window.__kimiSetTitle({title}) : (document.title = {title});"
        try:
            self.call("Runtime.evaluate", {"expression": script})
        except (OSError, TimeoutError):
            pass

    def set_title(self, title):
        self.title = title
        self._apply_title()

    def _on_binding(self, params):
        request = {}
        try:
            request = json.loads(params.get("payload") or "{}")
            message_id = request.get("id")
            action = (request.get("payload") or {}).get("action")
            if action == "captureScreenshot":
                result = self._capture_screenshot()
            elif action == "openExternal":
                result = self._open_external((request.get("payload") or {}).get("url") or "")
            elif action == "showOpenDialog":
                result = self.on_open_dialog((request.get("payload") or {}).get("options") or {})
            elif action == "ping":
                result = {"ok": True}
            else:
                result = {"status": "error"}
            self._resolve(message_id, result)
        except Exception as error:
            self._log(f"binding error: {error}")
            self._resolve(request.get("id") if isinstance(request, dict) else None,
                          {"status": "error", "message": str(error)})

    def _resolve(self, message_id, result):
        if message_id is None:
            return
        script = f"window.__kimiResolve({json.dumps(message_id)}, {json.dumps(result, ensure_ascii=False)});"
        try:
            self._log(f"resolve {message_id}: {str(result)[:100]}")
            self.call("Runtime.evaluate", {"expression": script})
        except (OSError, TimeoutError) as error:
            self._log(f"resolve error: {error}")

    def _capture_screenshot(self):
        path = APP_CACHE / f"screenshot-{time.time_ns()}.png"
        APP_CACHE.mkdir(parents=True, exist_ok=True)
        try:
            completed = subprocess.run(
                ["gnome-screenshot", "--area", "--file", str(path)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300,
            )
            if completed.returncode != 0:
                return {"status": "error"}
            if not path.is_file():
                return {"status": "cancel"}
            return {"status": "ok", "captureId": str(time.time_ns()),
                    "png": base64.b64encode(path.read_bytes()).decode("ascii")}
        except (OSError, subprocess.SubprocessError):
            return {"status": "error"}
        finally:
            try:
                path.unlink()
            except OSError:
                pass

    def _open_external(self, url):
        try:
            uri = urllib.parse.urlsplit(url)
            if uri.scheme not in {"http", "https"} or not uri.hostname:
                return False
            subprocess.Popen(["xdg-open", url], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
            return True
        except (AttributeError, TypeError, OSError):
            return False

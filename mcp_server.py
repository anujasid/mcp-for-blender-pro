import json
import threading
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .core import util
from .core.context import ToolContext

_server = None
_thread = None
_token = None


def _registry():
    from . import get_registry
    return get_registry()


def _reply(request_id, result=None, error=None):
    body = {"jsonrpc": "2.0", "id": request_id}
    body["error" if error else "result"] = error if error else result
    return body


class Handler(BaseHTTPRequestHandler):
    server_version = "MCPForBlenderPro/1.0"

    def log_message(self, *_args):
        return

    def do_GET(self):
        if self.path in ("/", "/health", "/mcp"):
            self._send(200, {"status": "ok", "service": "mcp-for-blender-pro"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != '/mcp':
            self._send(404, {'error': 'not found'})
            return
        if _token:
            expected = "Bearer " + _token
            if not secrets.compare_digest(self.headers.get("Authorization", ''), expected):
                self._send(401, {"error": "Unauthorized"})
                return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 4 * 1024 * 1024:
                self._send(413, {'error': 'Invalid request size'})
                return
            request = json.loads(self.rfile.read(length).decode("utf-8"))
            result = self.dispatch(request)
            if result is None:
                self.send_response(202)
                self.end_headers()
                return
            self._send(200, result)
        except Exception as exc:
            self._send(500, _reply(None, error={"code": -32603, "message": str(exc)}))

    def dispatch(self, request):
        method = request.get("method")
        rid = request.get("id")
        if method == "initialize":
            return _reply(rid, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "mcp-for-blender-pro", "version": "1.0.0"}})
        if method in ("notifications/initialized", "notifications/cancelled"):
            return None
        if method == "ping":
            return _reply(rid, {})
        if method == "tools/list":
            return _reply(rid, {"tools": [t.mcp_spec() for t in _registry().tools()]})
        if method == "tools/call":
            params = request.get("params", {})
            result = _registry().call(params.get("name", ""), params.get("arguments", {}), ToolContext(source="mcp"))
            return _reply(rid, result.to_mcp())
        return _reply(rid, error={"code": -32601, "message": f"Method not found: {method}"})

    def _send(self, status, body):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def start():
    global _server, _thread, _token
    if _server:
        return
    prefs = util.settings()
    port = prefs.mcp_port if prefs else 9876
    _token = prefs.mcp_token if prefs.mcp_require_token else None
    _server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    _thread = threading.Thread(target=_server.serve_forever, daemon=True, name="mcp-pro-http")
    _thread.start()
    print(f"MCP for Blender Pro server listening on http://127.0.0.1:{port}/mcp")


def stop():
    global _server, _thread
    if _server:
        _server.shutdown()
        _server.server_close()
    _server = None
    _thread = None


def restart():
    stop()
    start()

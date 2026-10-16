import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request

import bpy

USER_AGENT = "mcp-for-blender-pro/1.0"
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
_ssl_context = None


class NetError(Exception):
    def __init__(self, message, status=None, body=None):
        super().__init__(message)
        self.status = status
        self.body = body


def _context():
    global _ssl_context
    if _ssl_context is None:
        try:
            import certifi
            _ssl_context = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            _ssl_context = ssl.create_default_context()
    return _ssl_context


def is_local(url):
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return host in _LOCAL_HOSTS or host.endswith(".local") or host.startswith("192.168.") or host.startswith("10.")


def ensure_online(url):
    if is_local(url):
        return
    if not getattr(bpy.app, "online_access", True):
        raise NetError(
            "Online access is disabled in Blender. Enable it in Edit > Preferences > System > Network > Allow Online Access."
        )


def request(method, url, headers=None, body=None, timeout=120):
    ensure_online(url)
    data = None
    final_headers = {"User-Agent": USER_AGENT}
    if headers:
        final_headers.update(headers)
    if body is not None:
        if isinstance(body, (bytes, bytearray)):
            data = bytes(body)
        else:
            data = json.dumps(body).encode("utf-8")
            final_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=final_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_context()) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        text = payload.decode("utf-8", "replace")
        message = text
        try:
            parsed = json.loads(text)
            err = parsed.get("error", parsed)
            message = err.get("message") if isinstance(err, dict) else str(err)
        except Exception:
            pass
        raise NetError(f"HTTP {exc.code}: {message[:800]}", status=exc.code, body=text)
    except urllib.error.URLError as exc:
        raise NetError(f"Cannot reach {urllib.parse.urlparse(url).netloc}: {exc.reason}")
    except TimeoutError:
        raise NetError(f"Request to {urllib.parse.urlparse(url).netloc} timed out after {timeout}s")


def get_json(url, headers=None, timeout=60):
    _status, raw = request("GET", url, headers=headers, timeout=timeout)
    return json.loads(raw.decode("utf-8"))


def post_json(url, body, headers=None, timeout=300):
    _status, raw = request("POST", url, headers=headers, body=body, timeout=timeout)
    return json.loads(raw.decode("utf-8"))


def download(url, path, timeout=300, chunk=1 << 16):
    ensure_online(url)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    tmp = path + ".part"
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_context()) as resp, open(tmp, "wb") as out:
            while True:
                block = resp.read(chunk)
                if not block:
                    break
                out.write(block)
    except urllib.error.HTTPError as exc:
        raise NetError(f"Download failed: HTTP {exc.code} for {url}", status=exc.code)
    except urllib.error.URLError as exc:
        raise NetError(f"Download failed: {exc.reason}")
    os.replace(tmp, path)
    return path

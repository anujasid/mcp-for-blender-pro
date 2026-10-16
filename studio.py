import base64
import json
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .core import mainthread, util, approval

_server = None
_token = secrets.token_urlsafe(32)


def state():
    from . import profiles
    from . import agents
    from dataclasses import asdict
    from . import get_registry
    from .chat import session
    import bpy
    chat = session(get_registry())
    prefs = util.settings()
    with approval.lock:
        pending = [{'id': key, 'name': item['name'], 'arguments': item['arguments']} for key, item in approval.pending.items()]
    return {'messages': list(chat.transcript), 'busy': chat.busy, 'status': chat.status,
            'language': getattr(prefs, 'language', 'en'),
            'agents': [asdict(agent) for agent in agents.all_agents()],
            'tasks': list(chat.tasks),
            'profiles': profiles.public_records(),
            'url': getattr(prefs, prefs.provider + '_url', ''),
            'protocol': getattr(prefs, 'custom_protocol', 'openai'),
            'provider': prefs.provider, 'model': prefs.model, 'scene': bpy.context.scene.name,
            'objects': [{'name': obj.name, 'type': obj.type} for obj in bpy.context.scene.objects][:200],
            'pending': pending, 'blender': bpy.app.version_string, 'tools': len(get_registry().tools())}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, payload, content_type='application/json'):
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        return secrets.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + _token)

    def do_GET(self):
        if self.path == '/':
            self.send(200, (Path(__file__).parent / 'web/index.html').read_bytes(), 'text/html; charset=utf-8')
            return
        if not self.authorized():
            self.send(401, {'error': 'Unauthorized'})
            return
        try:
            if self.path == '/api/state':
                self.send(200, mainthread.run(state))
            elif self.path == '/api/viewport':
                from . import get_registry, ToolContext
                result = get_registry().call('viewport_screenshot', {'width': 1024}, ToolContext())
                if result.is_error:
                    raise RuntimeError(result.text)
                self.send(200, base64.b64decode(result.images[0]['data']), 'image/png')
            else:
                self.send(404, {'error': 'Not found'})
        except Exception as exc:
            self.send(500, {'error': str(exc)})

    def do_POST(self):
        if not self.authorized():
            self.send(401, {'error': 'Unauthorized'})
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length < 1000000:
                raise ValueError('Invalid body size')
            body = json.loads(self.rfile.read(length))
            if self.path == '/api/models':
                def model_config():
                    prefs = util.settings()
                    kind = body.get('provider', prefs.provider)
                    return kind, body.get('key') or prefs.key_for(kind), body.get('url') or getattr(prefs, kind + '_url', ''), body.get('protocol') or getattr(prefs, 'custom_protocol', 'openai')
                from .providers import list_models
                config = mainthread.run(model_config)
                try:
                    models = list_models(*config)
                except Exception as exc:
                    if getattr(exc, 'status', None) in (401, 403):
                        self.send(400, {'error': 'Model provider rejected the API key. Check the key, provider and API URL in Settings.'})
                        return
                    raise
                self.send(200, {'models': models})
                return
            def action():
                from . import get_registry
                from .chat import session
                chat = session(get_registry())
                if self.path == '/api/send':
                    if not chat.send(body.get('text', ''), team=bool(body.get('team', False))):
                        raise ValueError('Chat is busy or message is empty')
                elif self.path == '/api/cancel':
                    chat.cancelled.set()
                    approval.reject_all()
                elif self.path == '/api/clear':
                    chat.clear()
                elif self.path in {'/api/profile-save', '/api/profile-use', '/api/profile-delete'}:
                    if chat.busy:
                        raise ValueError('Wait for the current task to finish')
                    from . import profiles
                    if self.path == '/api/profile-save':
                        profiles.save(body.get('name', ''))
                    elif self.path == '/api/profile-use':
                        profiles.activate(body['id'])
                    else:
                        profiles.remove(body['id'])
                    import bpy
                    bpy.ops.wm.save_userpref()
                elif self.path == '/api/language':
                    if body.get('language') not in {'en', 'ru', 'de', 'fr', 'es', 'zh'}:
                        raise ValueError('Unknown language')
                    util.prefs().language = body['language']
                    import bpy
                    bpy.ops.wm.save_userpref()
                elif self.path == '/api/approve':
                    approval.decide(body['id'], bool(body['allowed']))
                elif self.path in {'/api/agent-save', '/api/agent-delete', '/api/agent-move'}:
                    if chat.busy:
                        raise ValueError('Stop the current task before editing the team')
                    from . import agents
                    if self.path == '/api/agent-save':
                        agents.update(body)
                    elif self.path == '/api/agent-delete':
                        agents.remove(body['id'])
                    else:
                        values = agents.all_agents()
                        index = next(i for i, agent in enumerate(values) if agent.id == body['id'])
                        target = max(0, min(len(values) - 1, index + int(body['direction'])))
                        values[index], values[target] = values[target], values[index]
                        agents.save({agent.id: agent for agent in values})
                    import bpy
                    bpy.ops.wm.save_userpref()
                elif self.path == '/api/settings':
                    prefs = util.prefs()
                    if chat.busy:
                        raise ValueError('Wait for the current request to finish')
                    if body.get('provider') not in {'anthropic', 'openai', 'gemini', 'openrouter', 'opencode', 'ollama', 'custom'}:
                        raise ValueError('Unknown provider')
                    prefs.provider = body['provider']
                    prefs.model = body['model']
                    if prefs.provider == 'custom':
                        protocol = body.get('protocol', 'openai')
                        if protocol not in {'openai', 'anthropic', 'ollama'}:
                            raise ValueError('Unknown API protocol')
                        prefs.custom_protocol = protocol
                    if body.get('key'):
                        setattr(prefs, prefs.provider + '_key', body['key'])
                    if body.get('url') and prefs.provider in {'custom', 'ollama'}:
                        setattr(prefs, prefs.provider + '_url', body['url'])
                    import bpy
                    bpy.ops.wm.save_userpref()
                else:
                    raise ValueError('Unknown action')
                return {'ok': True}
            self.send(200, mainthread.run(action))
        except Exception as exc:
            self.send(400, {'error': str(exc)})


def start():
    global _server
    if _server is None:
        _server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        _server.daemon_threads = True
        threading.Thread(target=_server.serve_forever, daemon=True).start()
    return f'http://127.0.0.1:{_server.server_port}/#' + _token


def open_window():
    import os
    import subprocess
    url = start()
    candidates = [Path(os.environ.get('PROGRAMFILES(X86)', '')) / 'Microsoft/Edge/Application/msedge.exe',
                  Path(os.environ.get('PROGRAMFILES', '')) / 'Google/Chrome/Application/chrome.exe']
    for executable in candidates:
        if executable.is_file():
            subprocess.Popen([str(executable), '--app=' + url, '--window-size=1440,960'])
            return
    webbrowser.open(url, new=1)


def stop():
    global _server
    if _server:
        _server.shutdown()
        _server.server_close()
        _server = None

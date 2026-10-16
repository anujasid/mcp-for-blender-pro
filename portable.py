import json
import os
import subprocess
import threading
from pathlib import Path

from .core import util

models = []
connections = []
status = 'Load models to select an OpenCode model'
loading = False


def binary_path():
    folder = Path(__file__).parent / 'tools/windows-x64'
    binary = folder / 'opencode.exe'
    if not binary.is_file():
        parts = sorted(folder.glob('parts/opencode.part-*'))
        if parts:
            with open(binary, 'wb') as target:
                for part in parts:
                    target.write(part.read_bytes())
        if not binary.is_file():
            raise RuntimeError('OpenCode is missing. Reinstall mcp-for-blender-pro.zip')
    return binary


def refresh():
    global loading, status
    if loading:
        return
    binary = binary_path()
    loading, status = True, 'Loading OpenCode connections and models...'

    def worker():
        rows, saved = [], []
        problem = ''
        options = dict(capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=90,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        for standalone in (False, True):
            suffix = ['--standalone'] if standalone else []
            try:
                catalog = subprocess.run([str(binary), 'models', *suffix], **options)
                catalog.check_returncode()
                auth = subprocess.run([str(binary), 'auth', 'list', *suffix, '--format', 'json'], **options)
                auth.check_returncode()
                rows = sorted(set(line.strip() for line in catalog.stdout.splitlines()
                                  if '/' in line and not any(c.isspace() for c in line.strip())))
                saved = [item.get('name', item['id']) for item in json.loads(auth.stdout)
                         if item.get('connections')]
                message = f'{len(rows)} models available'
                break
            except Exception as exc:
                rows, saved = [], []
                problem = str(exc) or exc.__class__.__name__
        else:
            message = 'Could not load OpenCode: ' + problem

        def apply():
            global models, connections, status, loading
            models = [(name, name, name) for name in rows]
            connections, status, loading = saved, message, False
            util.redraw_all()

        from .core import mainthread
        mainthread.post(apply)

    threading.Thread(target=worker, daemon=True).start()


def connect():
    subprocess.Popen([str(binary_path()), 'auth', 'login'],
                     creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))


def launch(model=''):
    from . import mcp_server
    binary = binary_path()
    prefs = util.prefs()
    if not prefs.mcp_enabled:
        prefs.mcp_enabled = True
    mcp_server.restart()
    workspace = Path(util.user_dir('opencode-workspace'))
    config = {'$schema': 'https://opencode.ai/config.json', 'mcp': {'servers': {'blender': {
        'type': 'remote', 'url': f'http://127.0.0.1:{prefs.mcp_port}/mcp', 'oauth': False,
        'headers': {'Authorization': 'Bearer {env:BLENDER_MCP_TOKEN}'}}}}}
    if model.strip():
        if '/' not in model:
            raise ValueError('Use provider/model, for example opencode/big-pickle')
        config['model'] = model.strip()
    (workspace / 'opencode.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
    env = os.environ.copy()
    env['BLENDER_MCP_TOKEN'] = prefs.mcp_token
    subprocess.Popen([str(binary), '--standalone', str(workspace)], cwd=str(workspace), env=env,
                     creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))

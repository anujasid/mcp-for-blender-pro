import json
import threading
from types import SimpleNamespace

from .core import mainthread, util
from .core.context import ToolContext
from .core.results import ToolResult
from .providers import get_provider
from .core import approval
from . import agents

SYSTEM = """You are an expert Blender artist and Python developer. Work through the provided Blender tools. Inspect the scene before changing it when useful. Prefer small verifiable steps. Never use file, network, process, handler, or add-on operations. Explain what you changed briefly."""


class ChatSession:
    def __init__(self, registry):
        self.registry = registry
        self.messages = []
        self.transcript = []
        self.busy = False
        self.error = ""
        self.status = "Ready"
        self._lock = threading.Lock()
        self.cancelled = threading.Event()
        self.tasks = []

    def clear(self):
        if self.busy:
            return
        with self._lock:
            self.messages.clear()
            self.transcript.clear()
            self.error = ""
            self.status = "Ready"

    def send(self, text, team=False):
        text = (text or "").strip()
        if not text or self.busy:
            return False
        chain = agents.chain() if team else []
        self.busy = True
        self.cancelled.clear()
        self.error = ""
        prefs = util.settings()
        self.config = SimpleNamespace(**{name: getattr(prefs, name) for name in (
            'provider', 'model', 'max_tokens', 'temperature', 'max_steps', 'request_timeout',
            'anthropic_key', 'openai_key', 'gemini_key', 'openrouter_key', 'opencode_key',
            'custom_key', 'custom_url', 'custom_protocol', 'ollama_url', 'approval', 'auto_look')})
        self.config.key_for = lambda kind: getattr(self.config, kind + '_key', '')
        self.transcript.append(("user", text))
        if team:
            threading.Thread(target=self._run_team, args=(text, chain), daemon=True, name="mcp-pro-team").start()
        else:
            threading.Thread(target=self._run, args=(text,), daemon=True, name="mcp-pro-chat").start()
        return True

    def _run_team(self, text, chain):
        try:
            if any(a.kind == 'manager' for a in chain):
                from .orchestration import run
                self.tasks = []
                run(self, text, chain)
                return
            brief = text
            outputs = []
            for number, agent in enumerate(chain, 1):
                if self.cancelled.is_set():
                    break
                self.status = f'{number}/{len(chain)} · {agent.name} · {agent.role}'
                self.transcript.append(('agent', f'{agent.name} · {agent.role}'))
                output = self._run_agent(agent, brief)
                if self.error:
                    break
                outputs.append(f'{agent.name} ({agent.role}): {output}')
                brief = f'Original request: {text}\nPrevious stage results:\n' + '\n\n'.join(outputs) + '\nContinue your role.'
        except Exception as exc:
            self.error = str(exc)
            self.transcript.append(('error', self.error))
        finally:
            self.busy = False
            self.status = 'Ready'
            mainthread.post(util.redraw_all)

    def _run_agent(self, agent, text, read_only=False):
        prefs = self.config
        local = SimpleNamespace(**vars(prefs))
        local.provider = agent.provider or prefs.provider
        local.model = agent.model or prefs.model
        local.key_for = lambda kind: getattr(local, kind + '_key', '')
        provider = get_provider(local)
        messages = [{'role': 'system', 'content': SYSTEM + f'\nYour name is {agent.name}. Your position is {agent.role}.\nYour instructions: {agent.instructions}'}, {'role': 'user', 'content': text}]
        allowed = {t.name for t in self.registry.tools() if not read_only or not t.mutating}
        specs = [t.mcp_spec() for t in self.registry.tools() if t.name in allowed]
        for _ in range(local.max_steps):
            if self.cancelled.is_set(): return
            response = provider.complete(messages, local.model, local.max_tokens, local.temperature, specs)
            if self.cancelled.is_set():
                return ''
            if response.get('content'):
                self.transcript.append(('assistant', f'{agent.name}: {response["content"]}'))
            calls = response.get('tool_calls') or []
            if not calls: return response.get('content') or ''
            assistant = {'role': 'assistant', 'content': response.get('content') or '', 'tool_calls': [{'id': c['id'], 'type': 'function', 'function': {'name': c['name'], 'arguments': json.dumps(c['input'])}} for c in calls]}
            messages.append(assistant)
            images = []
            for call in calls:
                if self.cancelled.is_set():
                    return ''
                tool = self.registry.get(call['name'])
                if tool is None:
                    raise ValueError('Unknown tool: ' + call['name'])
                if call['name'] not in allowed:
                    raise ValueError('This agent cannot change the scene: ' + call['name'])
                if not self._allowed(tool, call['input']):
                    raise RuntimeError('Agent operation declined or cancelled')
                result = self.registry.call(call['name'], call['input'], ToolContext(source=f'agent:{agent.id}'))
                self.transcript.append(('tool', f'{agent.name} → {call["name"]}: {result.summary()}'))
                messages.append({'role': 'tool', 'tool_call_id': call['id'], 'content': result.text})
                images.extend(result.images)
                if result.is_error:
                    raise RuntimeError(f'{agent.name}: {result.text}')
            if images:
                messages.append({'role': 'user', 'content': [{'type': 'image_url', 'image_url': {
                    'url': 'data:' + image.get('mime', 'image/png') + ';base64,' + image['data']}} for image in images]})
        raise RuntimeError(f'{agent.name}: maximum tool steps reached')

    def _run(self, text):
        try:
            prefs = self.config
            provider = get_provider(prefs)
            self.messages.append({"role": "user", "content": text})
            if prefs.auto_look:
                image = self.registry.call('viewport_screenshot', {}, ToolContext())
                if image.images:
                    self.messages[-1]['content'] = [{'type': 'text', 'text': text}] + [
                        {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + entry['data']}}
                        for entry in image.images]
            messages = [{"role": "system", "content": SYSTEM}] + list(self.messages)
            specs = [t.mcp_spec() for t in self.registry.tools()]
            for _ in range(prefs.max_steps if prefs else 40):
                if self.cancelled.is_set():
                    break
                self.status = "Thinking…"
                response = provider.complete(messages, prefs.model, prefs.max_tokens, prefs.temperature, specs)
                if self.cancelled.is_set():
                    break
                if response.get("content"):
                    self.transcript.append(("assistant", response["content"]))
                calls = response.get("tool_calls") or []
                assistant = {"role": "assistant", "content": response.get("content") or ""}
                if calls:
                    assistant['tool_calls'] = [{'id': c['id'], 'type': 'function', 'function': {
                        'name': c['name'], 'arguments': json.dumps(c['input'])}} for c in calls]
                messages.append(assistant)
                self.messages = messages[1:]
                if not calls:
                    break
                for call in calls:
                    name = call.get("name")
                    args = call.get("input", {})
                    tool = self.registry.get(name)
                    if not tool:
                        result = ToolResult.error(f"Unknown tool: {name}")
                    elif not self._allowed(tool, args):
                        result = ToolResult.error(f"Tool {name} was declined by the user")
                    else:
                        self.status = f"Running {name}…"
                        result = self.registry.call(name, args, ToolContext(source="chat"))
                    self.transcript.append(("tool", f"{name}: {result.summary()}"))
                    messages.append({"role": "tool", "tool_call_id": call['id'], "content": result.text})
                    if result.images:
                        messages[-1]['images'] = result.images
                images = [image for message in messages if message.get('role') == 'tool' for image in message.pop('images', [])]
                if images:
                    messages.append({'role': 'user', 'content': [{'type': 'image_url', 'image_url': {
                        'url': 'data:' + image.get('mime', 'image/png') + ';base64,' + image['data']}}
                        for image in images]})
                self.messages = messages[1:]
            else:
                self.transcript.append(("error", "Maximum tool steps reached"))
        except Exception as exc:
            self.error = str(exc)
            self.transcript.append(("error", self.error))
        finally:
            self.busy = False
            self.status = "Ready"
            mainthread.post(util.redraw_all)

    def _allowed(self, tool, args):
        prefs = self.config
        if self.cancelled.is_set():
            return False
        if prefs.approval == "never" or not tool.mutating or (prefs.approval == "code" and tool.name != "execute_code"):
            return True
        self.status = 'Waiting for approval in Blender'
        return approval.request(tool.name, args, self.cancelled)


_session = None


def session(registry):
    global _session
    if _session is None or _session.registry is not registry:
        _session = ChatSession(registry)
    return _session

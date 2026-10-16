import json
from urllib.parse import urlencode

from .core import net
from .core.results import ToolError


def list_models(kind, key='', base_url='', protocol='openai'):
    custom = kind == 'custom'
    if custom and protocol in {'anthropic', 'ollama'}:
        kind = protocol
    bases = {'anthropic': 'https://api.anthropic.com/v1', 'openai': 'https://api.openai.com/v1',
             'gemini': 'https://generativelanguage.googleapis.com/v1beta',
             'openrouter': 'https://openrouter.ai/api/v1', 'opencode': 'https://opencode.ai/zen/v1',
             'ollama': base_url or 'http://localhost:11434', 'custom': base_url or 'http://localhost:1234/v1'}
    if kind not in bases:
        raise ToolError('Unknown provider')
    if custom and base_url:
        bases[kind] = base_url
    if kind in {'anthropic', 'openai', 'gemini'} and not key:
        raise ToolError('Enter an API key to load models')
    headers = {}
    if kind == 'anthropic':
        headers = {'x-api-key': key, 'anthropic-version': '2023-06-01'}
    elif kind == 'gemini':
        headers = {'x-goog-api-key': key}
    elif key:
        headers = {'Authorization': 'Bearer ' + key}
    endpoint = bases[kind].rstrip('/') + ('/api/tags' if kind == 'ollama' else '/models')
    models = {}
    cursor = None
    seen = set()
    for _ in range(100):
        params = {}
        if kind == 'anthropic':
            params['limit'] = 100
            if cursor:
                params['after_id'] = cursor
        if kind == 'gemini':
            params['pageSize'] = 100
            if cursor:
                params['pageToken'] = cursor
        data = net.get_json(endpoint + ('?' + urlencode(params) if params else ''), headers=headers, timeout=30)
        entries = data.get('models', []) if kind in {'gemini', 'ollama'} else data.get('data', [])
        if not isinstance(entries, list):
            raise ToolError('API returned an invalid model list')
        for item in entries:
            if kind == 'gemini' and 'generateContent' not in item.get('supportedGenerationMethods', []):
                continue
            identifier = item.get('id') or item.get('name') or item.get('model')
            if not isinstance(identifier, str) or not identifier:
                continue
            if kind == 'opencode' and (identifier == 'big-pickle' or identifier.endswith('-free')):
                continue
            if kind == 'gemini':
                identifier = identifier.removeprefix('models/')
            label = item.get('display_name') or item.get('displayName') or item.get('name') or identifier
            models[identifier] = {'id': identifier, 'name': label}
        cursor = data.get('last_id') if kind == 'anthropic' and data.get('has_more') else data.get('nextPageToken') if kind == 'gemini' else None
        if not cursor:
            break
        if cursor in seen:
            raise ToolError('API repeated its model pagination cursor')
        seen.add(cursor)
    else:
        raise ToolError('API model list exceeded pagination limit')
    return sorted(models.values(), key=lambda item: item['id'].casefold())


class Provider:
    def __init__(self, name, key, base_url):
        self.name, self.key, self.base_url = name, key, base_url.rstrip("/")

    def complete(self, messages, model, max_tokens, temperature, tools=None):
        raise NotImplementedError


class OpenAICompatible(Provider):
    def complete(self, messages, model, max_tokens, temperature, tools=None):
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        if tools:
            payload["tools"] = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["inputSchema"]}} for t in tools]
        data = net.post_json(self.base_url + "/chat/completions", payload, headers=headers, timeout=300)
        msg = data["choices"][0]["message"]
        calls = []
        for call in msg.get("tool_calls") or []:
            try: args = json.loads(call["function"]["arguments"])
            except Exception: args = {}
            calls.append({"type": "tool_use", "id": call.get("id", "call"), "name": call["function"]["name"], "input": args})
        return {"content": msg.get("content"), "tool_calls": calls, "usage": data.get("usage", {})}


class Anthropic(Provider):
    def complete(self, messages, model, max_tokens, temperature, tools=None):
        system = ""
        clean = []
        for msg in messages:
            if msg["role"] == "system": system = msg["content"]
            elif msg['role'] == 'tool':
                block = {'type': 'tool_result', 'tool_use_id': msg['tool_call_id'], 'content': msg['content']}
                if clean and clean[-1]['role'] == 'user':
                    clean[-1]['content'].append(block)
                else:
                    clean.append({'role': 'user', 'content': [block]})
            else:
                content = msg.get('content') or ''
                blocks = [{'type': 'text', 'text': content}] if isinstance(content, str) and content else []
                if isinstance(content, list):
                    for item in content:
                        if item['type'] == 'image_url':
                            prefix, data = item['image_url']['url'].split(',', 1)
                            blocks.append({'type': 'image', 'source': {'type': 'base64', 'media_type': prefix[5:].split(';')[0], 'data': data}})
                        else:
                            blocks.append(item)
                for call in msg.get('tool_calls', []):
                    blocks.append({'type': 'tool_use', 'id': call['id'], 'name': call['function']['name'], 'input': json.loads(call['function']['arguments'])})
                if clean and clean[-1]['role'] == msg['role']:
                    clean[-1]['content'].extend(blocks)
                else:
                    clean.append({'role': msg['role'], 'content': blocks or [{'type': 'text', 'text': 'Continue'}]})
        payload = {"model": model, "max_tokens": max_tokens, "temperature": temperature, "messages": clean, "system": system}
        if tools: payload["tools"] = [{"name": t["name"], "description": t["description"], "input_schema": t["inputSchema"]} for t in tools]
        data = net.post_json(self.base_url + "/messages", payload, headers={"x-api-key": self.key, "anthropic-version": "2023-06-01"}, timeout=300)
        return {"content": "\n".join(x.get("text", "") for x in data.get("content", []) if x.get("type") == "text"), "tool_calls": [x for x in data.get("content", []) if x.get("type") == "tool_use"], "usage": data.get("usage", {})}


class Ollama(OpenAICompatible):
    def complete(self, messages, model, max_tokens, temperature, tools=None):
        import copy
        converted = copy.deepcopy(messages)
        for message in converted:
            for call in message.get('tool_calls', []):
                call['function']['arguments'] = json.loads(call['function']['arguments'])
            if isinstance(message.get('content'), list):
                message['images'] = [x['image_url']['url'].split(',', 1)[1] for x in message['content'] if x['type'] == 'image_url']
                message['content'] = '\n'.join(x['text'] for x in message['content'] if x['type'] == 'text')
        payload = {"model": model, "messages": converted, "stream": False, "options": {"temperature": temperature, "num_predict": max_tokens}}
        if tools: payload["tools"] = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["inputSchema"]}} for t in tools]
        data = net.post_json(self.base_url + "/api/chat", payload, timeout=300)
        msg = data.get("message", {})
        calls = [{"type": "tool_use", "id": f"ollama_{i}", "name": c["function"]["name"], "input": c["function"].get("arguments", {})} for i, c in enumerate(msg.get("tool_calls", []))]
        return {"content": msg.get("content"), "tool_calls": calls, "usage": {}}


def get_provider(prefs):
    kind = prefs.provider
    key = prefs.key_for(kind)
    if kind == "anthropic":
        if not key: raise ToolError("Anthropic API key is not configured")
        return Anthropic(kind, key, "https://api.anthropic.com/v1")
    if kind == "openai":
        if not key: raise ToolError("OpenAI API key is not configured")
        return OpenAICompatible(kind, key, "https://api.openai.com/v1")
    if kind == "gemini":
        if not key: raise ToolError("Gemini API key is not configured")
        return OpenAICompatible(kind, key, "https://generativelanguage.googleapis.com/v1beta/openai")
    if kind == "openrouter":
        if not key: raise ToolError("OpenRouter API key is not configured")
        return OpenAICompatible(kind, key, "https://openrouter.ai/api/v1")
    if kind == "opencode":
        if prefs.model == 'big-pickle' or prefs.model.endswith('-free'):
            raise ToolError('This free model works only inside OpenCode. Use OpenCode Portable, or select a paid API model with a Zen API key.')
        if not key:
            raise ToolError('Enter your OpenCode Zen API key for direct chat. For free models, use OpenCode Portable.')
        return OpenAICompatible(kind, key, "https://opencode.ai/zen/v1")
    if kind == "ollama":
        return Ollama(kind, "", prefs.ollama_url)
    if kind == "custom":
        protocol = getattr(prefs, 'custom_protocol', 'openai')
        if protocol == 'anthropic':
            return Anthropic(kind, key, prefs.custom_url)
        if protocol == 'ollama':
            return Ollama(kind, key, prefs.custom_url)
        return OpenAICompatible(kind, key, prefs.custom_url)
    raise ToolError(f"Unknown provider: {kind}")

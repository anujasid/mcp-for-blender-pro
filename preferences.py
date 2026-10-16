import secrets

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import AddonPreferences

from .core import util
from .i18n import LANGUAGES

PROVIDERS = [
    ("anthropic", "Anthropic Claude", "api.anthropic.com"),
    ("openai", "OpenAI", "api.openai.com"),
    ("gemini", "Google Gemini", "generativelanguage.googleapis.com"),
    ("openrouter", "OpenRouter", "openrouter.ai"),
    ("opencode", "OpenCode Zen", "opencode.ai/zen"),
    ("ollama", "Ollama (local)", "localhost:11434"),
    ("custom", "Custom API", ""),
]

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-5",
    "openai": "gpt-5.5",
    "gemini": "gemini-3.5-flash",
    "openrouter": "anthropic/claude-sonnet-5",
    "opencode": "claude-sonnet-5",
    "ollama": "qwen3",
    "custom": "",
}


def _provider_changed(self, context):
    self.model = DEFAULT_MODELS.get(self.provider, "")
    wm = context.window_manager
    if wm is not None and hasattr(wm, "mcp_pro_models"):
        wm.mcp_pro_models.clear()


def _mcp_changed(self, context):
    from . import mcp_server
    if self.mcp_enabled:
        mcp_server.restart()
    else:
        mcp_server.stop()


def new_token():
    return secrets.token_urlsafe(24)


class MCPProPreferences(AddonPreferences):
    bl_idname = util.ADDON_ID
    language: EnumProperty(name='Language', items=LANGUAGES, default='en')
    connection_profiles: StringProperty(default='[]', options={'HIDDEN'})

    provider: EnumProperty(name="Provider", items=PROVIDERS, default="anthropic", update=_provider_changed)
    model: StringProperty(name="Model", default="claude-sonnet-5")

    anthropic_key: StringProperty(name="Anthropic API Key", subtype="PASSWORD")
    openai_key: StringProperty(name="OpenAI API Key", subtype="PASSWORD")
    gemini_key: StringProperty(name="Gemini API Key", subtype="PASSWORD")
    openrouter_key: StringProperty(name="OpenRouter API Key", subtype="PASSWORD")
    opencode_key: StringProperty(name="OpenCode Zen API Key", subtype="PASSWORD")
    custom_key: StringProperty(name="API Key", subtype="PASSWORD")
    ollama_url: StringProperty(name="Ollama URL", default="http://localhost:11434")
    custom_url: StringProperty(name="Base URL", default="http://localhost:1234/v1")
    custom_protocol: EnumProperty(name='Protocol', items=[('openai', 'Chat Completions', ''), ('anthropic', 'Anthropic Messages', ''), ('ollama', 'Ollama', '')], default='openai')

    max_tokens: IntProperty(name="Max Output Tokens", default=8192, min=512, max=128000)
    temperature: FloatProperty(name="Temperature", default=0.3, min=0.0, max=2.0)
    max_steps: IntProperty(name="Max Tool Steps", default=40, min=1, max=200)
    request_timeout: IntProperty(name="Request Timeout (s)", default=300, min=10, max=3600)

    safe_mode: BoolProperty(name="Safe Mode", default=True,
                            description="Validate AI Python before it runs: blocks file access, processes, network and handlers")
    approval: EnumProperty(name="Ask Before", default="code", items=[
        ("never", "Never", "Run every tool immediately"),
        ("code", "Running Python", "Ask before execute_python only"),
        ("mutating", "Any Change", "Ask before every tool that changes the scene"),
    ])
    screenshot_size: IntProperty(name="Screenshot Size", default=800, min=256, max=2048)
    auto_look: BoolProperty(name="Send Viewport With Message", default=False,
                            description="Attach a viewport screenshot to each message you send")

    mcp_enabled: BoolProperty(name="MCP Server", default=False, update=_mcp_changed,
                              description="Serve the tools over MCP for OpenCode, Claude Desktop, Cursor, VS Code")
    mcp_port: IntProperty(name="Port", default=9876, min=1024, max=65535)
    mcp_require_token: BoolProperty(name="Require Token", default=True,
                                    description="Clients must send Authorization: Bearer <token>")
    mcp_token: StringProperty(name="Token", subtype="PASSWORD")

    polyhaven: BoolProperty(name="Poly Haven Assets", default=True)
    sketchfab_api_key: StringProperty(name='Sketchfab API Key', subtype='PASSWORD')
    polypizza_api_key: StringProperty(name='Poly Pizza API Key', subtype='PASSWORD')
    agent_team_json: StringProperty(name='Agent team data', default='', options={'HIDDEN'})

    def key_for(self, provider):
        return {
            "anthropic": self.anthropic_key, "openai": self.openai_key, "gemini": self.gemini_key,
            "openrouter": self.openrouter_key, "opencode": self.opencode_key, "custom": self.custom_key,
        }.get(provider, "")

    def draw(self, context):
        from .ui import draw_preferences
        draw_preferences(self, self.layout, context)


def register():
    bpy.utils.register_class(MCPProPreferences)
    p = util.prefs()
    if p is not None and not p.mcp_token:
        p.mcp_token = new_token()


def unregister():
    bpy.utils.unregister_class(MCPProPreferences)

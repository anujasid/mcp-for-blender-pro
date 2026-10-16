bl_info = {
    "name": "mcp-for-blender-pro",
    "author": "anujasid",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > MCP Pro",
    "description": "Built-in AI chat and MCP server for OpenCode, Claude and Cursor",
    "category": "Development",
}

import bpy

from . import preferences, ui, mcp_server
from .core import mainthread, results, util
from .core.context import ToolContext
from .tools import core as core_tools, objects as object_tools
from .tools import assets


_registry = None


def get_registry():
    global _registry
    if _registry is None:
        _registry = results.Registry()
        core_tools.register_tools(_registry)
        object_tools.register_tools(_registry)
        assets.register_tools(_registry)
    return _registry


class MCP_OT_TestTool(bpy.types.Operator):
    bl_idname = "mcp_pro.test_tool"
    bl_label = "Test Tool"
    bl_description = "Test a tool call (dev only)"

    def execute(self, context):
        registry = get_registry()
        ctx = ToolContext(source="manual")
        result = registry.call("get_scene_info", {}, ctx)
        self.report({"INFO"}, f"Result: {result.text[:200]}")
        return {"FINISHED"}


class MCP_PT_MainPanel(bpy.types.Panel):
    bl_label = "MCP Pro"
    bl_idname = "MCP_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MCP Pro"

    def draw(self, context):
        layout = self.layout
        prefs = util.prefs()

        box = layout.box()
        box.label(text="AI Provider", icon="NETWORK_DRIVE")
        if prefs:
            box.label(text=f"{prefs.provider.title()}: {prefs.model}")
        else:
            box.label(text="Configure in Preferences", icon="ERROR")
        
        box = layout.box()
        box.label(text="Tools", icon="TOOL_SETTINGS")
        registry = get_registry()
        tool_count = len(registry.tools())
        box.label(text=f"{tool_count} tools available")
        
        box = layout.box()
        box.label(text="Quick Test", icon="PLAY")
        box.operator("mcp_pro.test_tool", text="Test Scene Info")
        
        layout.separator()


classes = (
    MCP_OT_TestTool,
)


def register():
    preferences.register()
    ui.register()
    for cls in classes:
        bpy.utils.register_class(cls)
    mainthread.start()
    if util.settings().mcp_enabled:
        mcp_server.start()
    try:
        path = util.find_startup_file()
        if path:
            util.run_embedded(path)
        else:
            util.bootstrap_runtime()
    except Exception:
        pass


def unregister():
    mainthread.stop()
    mcp_server.stop()
    ui.unregister()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    preferences.unregister()


if __name__ == "__main__":
    register()

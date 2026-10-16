import json
import textwrap

import bpy
from bpy.props import StringProperty, BoolProperty, EnumProperty

from .core import util
from .core import approval
from .i18n import t


def draw_preferences(prefs, layout, context):
    from .model_menu import draw_connection

    draw_connection(layout, prefs)
    box = layout.box()
    box.label(text=t('Generation'), icon='PREFERENCES')
    box.prop(prefs, "max_tokens")
    box.prop(prefs, "temperature")
    box.prop(prefs, "max_steps")
    box.prop(prefs, "request_timeout")
    box = layout.box()
    box.label(text=t('Safety and preview'), icon="LOCKED")
    box.prop(prefs, "safe_mode")
    box.prop(prefs, "approval")
    box.prop(prefs, "screenshot_size")
    box.prop(prefs, "auto_look")
    box = layout.box()
    box.label(text=t('Asset services'), icon='ASSET_MANAGER')
    box.prop(prefs, 'polyhaven')
    box.prop(prefs, 'sketchfab_api_key')
    box.prop(prefs, 'polypizza_api_key')
    box = layout.box()
    box.label(text=t('External tools'), icon="PLUGIN")
    box.prop(prefs, "mcp_enabled")
    if prefs.mcp_enabled:
        box.prop(prefs, "mcp_port")
        box.prop(prefs, "mcp_require_token")
        if prefs.mcp_require_token:
            box.prop(prefs, "mcp_token")
            box.label(text=t('Keep the access token private'), icon="INFO")
    box = layout.box()
    box.label(text=t('Interface'), icon='WORLD')
    box.prop(prefs, 'language')


class MCP_OT_Send(bpy.types.Operator):
    bl_idname = "mcp_pro.send"
    bl_label = "Send"
    def execute(self, context):
        from . import get_registry
        from .chat import session as get_session
        session = get_session(get_registry())
        if session.send(context.scene.mcp_pro_input):
            context.scene.mcp_pro_input = ""
        return {"FINISHED"}


class MCP_OT_Clear(bpy.types.Operator):
    bl_idname = "mcp_pro.clear"
    bl_label = "Clear Chat"
    def execute(self, context):
        from . import get_registry
        from .chat import session
        session(get_registry()).clear()
        return {"FINISHED"}


class MCP_PT_Chat(bpy.types.Panel):
    bl_idname = "MCP_PRO_PT_CHAT"
    bl_label = "mcp-for-blender-pro"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MCP Pro"

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text=t('Workspace'), icon='VIEW3D')
        box.operator('mcp_pro.studio', text=t('Open Studio Window'), icon='WINDOW')
        box.operator('mcp_pro.portable', text=t('OpenCode Portable'), icon='CONSOLE')
        prefs = util.prefs()
        if prefs:
            box.label(text=textwrap.shorten(
                f'{prefs.provider} / {prefs.model or "—"}',
                width=max(24, context.region.width // 9), placeholder='…'
            ), icon='NETWORK_DRIVE')


class MCP_PT_Connection(bpy.types.Panel):
    bl_idname = 'MCP_PRO_PT_connection'
    bl_label = 'Connection'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MCP Pro'
    bl_parent_id = 'MCP_PRO_PT_CHAT'

    def draw(self, context):
        from .model_menu import draw_connection

        prefs = util.prefs()
        if prefs:
            draw_connection(self.layout, prefs)
        else:
            self.layout.label(text=t('Enable the extension in Preferences'), icon='ERROR')


class MCP_PT_Conversation(bpy.types.Panel):
    bl_idname = 'MCP_PRO_PT_conversation'
    bl_label = 'Chat'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MCP Pro'
    bl_parent_id = 'MCP_PRO_PT_CHAT'

    def draw(self, context):
        from . import get_registry
        from .chat import session as get_session

        session = get_session(get_registry())
        layout = self.layout
        layout.label(text=textwrap.shorten(session.status, width=30, placeholder='…'),
                     icon='TIME' if session.busy else 'CHECKMARK')
        with approval.lock:
            items = list(approval.pending.items())
        for key, item in items:
            prompt = layout.box()
            prompt.label(text=t('Permission requested') + ': ' + item['name'], icon='QUESTION')
            for line in textwrap.wrap(json.dumps(item['arguments'], ensure_ascii=False), 36)[:8]:
                prompt.label(text=line)
            row = prompt.row()
            for label, allowed in [('Allow', True), ('Reject', False)]:
                op = row.operator('mcp_pro.approve', text=t(label))
                op.key, op.allowed = key, allowed
        layout.prop(context.scene, 'mcp_pro_input', text=t('Message'))
        row = layout.row(align=True)
        row.enabled = not session.busy
        row.operator('mcp_pro.send', text=t('Send'), icon='PLAY')
        if session.busy:
            layout.operator('mcp_pro.cancel', text=t('Stop after current step'), icon='CANCEL')
        elif session.transcript:
            layout.operator('mcp_pro.clear', text=t('New conversation'), icon='TRASH')
        if session.transcript:
            box = layout.box()
            for role, message in session.transcript[-2:]:
                icon = {'user': 'USER', 'assistant': 'CONSOLE', 'tool': 'TOOL_SETTINGS',
                        'error': 'ERROR', 'review': 'CHECKMARK', 'agent': 'USER'}.get(role, 'INFO')
                box.label(text=role.title(), icon=icon)
                for line in textwrap.wrap(' '.join(message.split()),
                                          max(22, context.region.width // 8))[:3]:
                    box.label(text=line)


class MCP_PT_History(bpy.types.Panel):
    bl_idname = 'MCP_PRO_PT_history'
    bl_label = 'Recent activity'
    bl_options = {'DEFAULT_CLOSED'}
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MCP Pro'
    bl_parent_id = 'MCP_PRO_PT_CHAT'

    def draw(self, context):
        from . import get_registry
        from .chat import session as get_session

        messages = get_session(get_registry()).transcript[-12:]
        if not messages:
            self.layout.label(text=t('No messages yet'))
        for role, message in messages:
            box = self.layout.box()
            box.label(text=role.title())
            for line in textwrap.wrap(' '.join(message.split()),
                                      max(22, context.region.width // 8))[:8]:
                box.label(text=line)


class MCP_PT_Help(bpy.types.Panel):
    bl_idname = 'MCP_PRO_PT_help'
    bl_label = 'Quick guide'
    bl_options = {'DEFAULT_CLOSED'}
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MCP Pro'
    bl_parent_id = 'MCP_PRO_PT_CHAT'

    def draw(self, context):
        layout = self.layout
        for index, text in enumerate(('Choose a connection',
                                      'Load and select a model',
                                      'Send a message',
                                      'Set up agents in Studio'), 1):
            layout.label(text=f'{index}. {t(text)}')


class MCP_OT_Approve(bpy.types.Operator):
    bl_idname = 'mcp_pro.approve'
    bl_label = 'Approve Operation'
    key: StringProperty()
    allowed: BoolProperty()

    def execute(self, context):
        approval.decide(self.key, self.allowed)
        return {'FINISHED'}


class MCP_OT_Cancel(bpy.types.Operator):
    bl_idname = 'mcp_pro.cancel'
    bl_label = 'Cancel after current operation'

    def execute(self, context):
        from .chat import session
        from . import get_registry
        session(get_registry()).cancelled.set()
        approval.reject_all()
        return {'FINISHED'}


def refresh():
    util.redraw_all()
    return 0.5


class MCP_OT_Studio(bpy.types.Operator):
    bl_idname = 'mcp_pro.studio'
    bl_label = 'Open Studio Window'

    def execute(self, context):
        from .studio import open_window
        open_window()
        return {'FINISHED'}


def _opencode_models(self, context):
    from . import portable
    return portable.models


class MCP_OT_OpenCodeRefresh(bpy.types.Operator):
    bl_idname = 'mcp_pro.opencode_refresh'
    bl_label = 'Refresh models and connections'

    def execute(self, context):
        from . import portable
        portable.refresh()
        return {'FINISHED'}


class MCP_OT_OpenCodeConnect(bpy.types.Operator):
    bl_idname = 'mcp_pro.opencode_connect'
    bl_label = 'Add or change connection'

    def execute(self, context):
        from . import portable
        portable.connect()
        return {'FINISHED'}


class MCP_OT_Portable(bpy.types.Operator):
    bl_idname = 'mcp_pro.portable'
    bl_label = 'OpenCode Portable'
    model: EnumProperty(name='OpenCode model', items=_opencode_models)

    def invoke(self, context, event):
        from . import portable
        portable.refresh()
        return context.window_manager.invoke_props_dialog(self, width=560)

    def draw(self, context):
        from . import portable
        layout = self.layout
        layout.label(text='OpenCode connections', icon='NETWORK_DRIVE')
        if portable.connections:
            for name in portable.connections:
                layout.label(text=name + ': connection saved', icon='CHECKMARK')
        elif not portable.loading:
            layout.label(text='Connect a provider to use its models')
        layout.operator('mcp_pro.opencode_connect', icon='ADD')
        layout.label(text='Complete sign-in in the opened window, then refresh.')
        row = layout.row()
        row.enabled = not portable.loading
        row.operator('mcp_pro.opencode_refresh', icon='FILE_REFRESH')
        layout.label(text=portable.status)
        if portable.models:
            layout.prop(self, 'model')
        layout.label(text='Click OK to open OpenCode with the selected model.')

    def execute(self, context):
        from .portable import launch
        try:
            if not self.model:
                self.report({'WARNING'}, 'Load and select a model first')
                return {'CANCELLED'}
            launch(self.model)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return {'FINISHED'}


classes = (MCP_OT_Send, MCP_OT_Clear, MCP_OT_Approve, MCP_OT_Cancel,
           MCP_OT_Studio, MCP_OT_OpenCodeRefresh, MCP_OT_OpenCodeConnect,
           MCP_OT_Portable, MCP_PT_Chat, MCP_PT_Connection,
           MCP_PT_Conversation, MCP_PT_History, MCP_PT_Help)


def register():
    from . import model_menu
    model_menu.register()
    bpy.types.Scene.mcp_pro_input = StringProperty(name="Message", default="")
    for cls in classes: bpy.utils.register_class(cls)
    bpy.app.timers.register(refresh, persistent=True)


def unregister():
    from . import model_menu
    model_menu.unregister()
    from .studio import stop
    stop()
    approval.reject_all()
    if bpy.app.timers.is_registered(refresh):
        bpy.app.timers.unregister(refresh)
    for cls in reversed(classes): bpy.utils.unregister_class(cls)
    del bpy.types.Scene.mcp_pro_input

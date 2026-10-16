import threading
import bpy
from bpy.props import StringProperty
from .core import util, mainthread
from .providers import list_models
from .i18n import t

models = []
status = ''
loading = False
generation = 0


class MCP_OT_LoadModels(bpy.types.Operator):
    bl_idname = 'mcp_pro.load_models'
    bl_label = 'Load models'

    def execute(self, context):
        global loading, status, generation
        prefs = util.settings()
        config = (prefs.provider, prefs.key_for(prefs.provider), getattr(prefs, prefs.provider + '_url', ''), prefs.custom_protocol)
        generation += 1
        current = generation
        loading, status = True, 'Loading models…'
        def worker():
            try:
                result = list_models(*config)
                message = f'{len(result)} models available'
            except Exception as exc:
                result, message = [], str(exc)
            def apply():
                global loading, status, models
                if current != generation:
                    return
                if util.settings().provider != config[0]:
                    loading, status = False, 'Connection changed. Load models again.'
                    return
                models, status, loading = result, message, False
                util.redraw_all()
            mainthread.post(apply)
        threading.Thread(target=worker, daemon=True).start()
        return {'FINISHED'}


class MCP_OT_SelectModel(bpy.types.Operator):
    bl_idname = 'mcp_pro.select_model'
    bl_label = 'Select model'
    model: StringProperty()

    def execute(self, context):
        util.prefs().model = self.model
        return {'FINISHED'}


class MCP_MT_Models(bpy.types.Menu):
    bl_idname = 'MCP_MT_models'
    bl_label = 'Available models'

    def draw(self, context):
        if not models:
            self.layout.label(text='Load models from your API first')
        for model in models:
            self.layout.operator('mcp_pro.select_model', text=model['id']).model = model['id']


def draw_connection(layout, prefs):
    box = layout.box()
    box.prop(prefs, 'language')
    box.label(text=t('Connection'), icon='LINKED')
    row = box.row(align=True)
    row.menu('MCP_MT_profiles', text='Profiles', icon='PRESET')
    row.operator('mcp_pro.profile_save', text='', icon='ADD')
    box.prop(prefs, 'provider', text=t('Service'))
    if prefs.provider == 'opencode':
        box.label(text='Free models: OpenCode Portable', icon='INFO')
    if prefs.provider == 'custom':
        box.prop(prefs, 'custom_protocol')
        box.prop(prefs, 'custom_url', text='API address')
    elif prefs.provider == 'ollama':
        box.prop(prefs, 'ollama_url', text='Server')
    if prefs.provider != 'ollama':
        box.prop(prefs, prefs.provider + '_key', text=t('API key'))
    row = box.row(align=True)
    row.operator('mcp_pro.load_models', text=t('Load models'), icon='FILE_REFRESH')
    row.menu('MCP_MT_models', text=t('Choose model'), icon='DOWNARROW_HLT')
    box.prop(prefs, 'model', text=t('Model ID'))
    if status:
        import textwrap
        for line in textwrap.wrap(status, 42):
            box.label(text=line)


class MCP_OT_ProfileSave(bpy.types.Operator):
    bl_idname = 'mcp_pro.profile_save'
    bl_label = 'Save connection profile'
    name: StringProperty(name='Profile name')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        from . import profiles
        try:
            profiles.save(self.name)
            bpy.ops.wm.save_userpref()
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return {'FINISHED'}


class MCP_OT_ProfileSelect(bpy.types.Operator):
    bl_idname = 'mcp_pro.profile_select'
    bl_label = 'Use connection profile'
    identifier: StringProperty()

    def execute(self, context):
        from . import profiles
        profiles.activate(self.identifier)
        global models, status
        models, status = [], ''
        bpy.ops.wm.save_userpref()
        return {'FINISHED'}


class MCP_MT_Profiles(bpy.types.Menu):
    bl_idname = 'MCP_MT_profiles'
    bl_label = 'Connection profiles'

    def draw(self, context):
        from . import profiles
        for row in profiles.public_records():
            op = self.layout.operator('mcp_pro.profile_select', text=row['name'] + ' / ' + row['provider'])
            op.identifier = row['id']


classes = (MCP_OT_LoadModels, MCP_OT_SelectModel, MCP_MT_Models, MCP_OT_ProfileSave, MCP_OT_ProfileSelect, MCP_MT_Profiles)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    global generation
    generation += 1
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

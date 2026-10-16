import bpy

from ..core import util
from ..core.results import ToolError


def backend():
    from . import upstream_addon
    instance = upstream_addon.BlenderMCPServer()

    def config(scene_attr, pref_attr=None, env_var=None):
        import os
        prefs = util.settings()
        if pref_attr and hasattr(prefs, pref_attr):
            value = getattr(prefs, pref_attr)
            if value:
                return value
        return os.environ.get(env_var, '') if env_var else ''

    instance._get_config_value = config
    return instance


def invoke(ctx, method, **kwargs):
    result = getattr(backend(), method)(**kwargs)
    if isinstance(result, dict) and result.get('error'):
        raise ToolError(str(result['error']))
    return result


def register_tools(registry):
    def api(ctx, query):
        return invoke(ctx, 'bpy_api_lookup', query=query)

    def node(ctx, bl_idname):
        return invoke(ctx, 'describe_node_type', bl_idname=bl_idname)

    def export(ctx, filepath, format='glb', object_names=None):
        return invoke(ctx, 'export_scene', filepath=bpy.path.abspath(filepath), format=format, object_names=object_names)

    def search(ctx, query, source='polyhaven', asset_type='models', limit=12):
        if source == 'polyhaven':
            return invoke(ctx, 'search_polyhaven_assets', query=query, asset_type=asset_type)
        if source == 'sketchfab':
            return invoke(ctx, 'search_sketchfab_models', query=query, count=limit)
        if source == 'polypizza':
            return invoke(ctx, 'search_polypizza_models', query=query, limit=limit)
        raise ToolError('source must be polyhaven, sketchfab or polypizza')

    def download(ctx, id, source='polyhaven', asset_type='models', resolution='1k'):
        if source == 'polyhaven':
            return invoke(ctx, 'download_polyhaven_asset', asset_id=id, asset_type=asset_type, resolution=resolution)
        if source == 'sketchfab':
            return invoke(ctx, 'download_sketchfab_model', uid=id)
        if source == 'polypizza':
            return invoke(ctx, 'download_polypizza_model', model_id=id)
        raise ToolError('source must be polyhaven, sketchfab or polypizza')

    registry.tool('bpy_api_lookup', 'Look up the installed Blender Python API', properties={'query': {'type': 'string'}}, required=('query',))(api)
    registry.tool('describe_node_type', 'Inspect shader or geometry node inputs and properties', properties={'bl_idname': {'type': 'string'}}, required=('bl_idname',))(node)
    registry.tool('export_scene', 'Export the scene or named objects to GLB, glTF, FBX or OBJ', properties={
        'filepath': {'type': 'string'}, 'format': {'type': 'string', 'enum': ['glb', 'gltf', 'fbx', 'obj']},
        'object_names': {'type': 'array', 'items': {'type': 'string'}}}, required=('filepath',), mutating=True)(export)
    registry.tool('search_assets', 'Search Poly Haven HDRIs, textures and models; Sketchfab or Poly Pizza models', properties={
        'query': {'type': 'string'}, 'source': {'type': 'string', 'enum': ['polyhaven', 'sketchfab', 'polypizza']},
        'asset_type': {'type': 'string', 'enum': ['models', 'hdris', 'textures']}, 'limit': {'type': 'integer'}}, required=('query',), group='assets')(search)
    registry.tool('import_asset', 'Download and import an asset returned by search_assets', properties={
        'id': {'type': 'string'}, 'source': {'type': 'string', 'enum': ['polyhaven', 'sketchfab', 'polypizza']},
        'asset_type': {'type': 'string', 'enum': ['models', 'hdris', 'textures']}, 'resolution': {'type': 'string'}}, required=('id',), mutating=True, group='assets')(download)

import contextlib
import io
import math
import os
import base64

import bpy

from ..core import safety
from ..core.results import ToolResult
from ..core.util import find_object, round3, eevee_engine_id, scene_bounds


def get_scene_info(ctx):
    scene = bpy.context.scene
    return {
        "scene_name": scene.name,
        "frame_current": scene.frame_current,
        "frame_range": [scene.frame_start, scene.frame_end],
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        "engine": scene.render.engine,
        "object_count": len(bpy.data.objects),
        "mesh_count": len(bpy.data.meshes),
        "material_count": len(bpy.data.materials),
        "selected_objects": [o.name for o in bpy.context.selected_objects][:200],
        "active_object": bpy.context.active_object.name if bpy.context.active_object else None,
        "camera": scene.camera.name if scene.camera else None,
        "world": scene.world.name if scene.world else None,
        "collections": [c.name for c in scene.collection.children_recursive],
    }


def list_objects(ctx, filter=None, limit=100):
    items = list(bpy.data.objects)
    if filter:
        needle = filter.lower()
        items = [o for o in items if needle in o.name.lower() or needle in o.type.lower()]
    return [{"name": o.name, "type": o.type, "location": round3(o.location),
             "visible": not o.hide_viewport and not o.hide_get(), "selected": o.select_get()}
            for o in items[:max(1, min(limit, 1000))]]


def get_object_info(ctx, name):
    obj = find_object(name)
    result = {"name": obj.name, "type": obj.type, "location": round3(obj.location),
              "rotation_euler": round3([math.degrees(v) for v in obj.rotation_euler]),
              "scale": round3(obj.scale), "dimensions": round3(obj.dimensions),
              "selected": obj.select_get(), "visible": not obj.hide_get(),
              "parent": obj.parent.name if obj.parent else None,
              "children": [c.name for c in obj.children][:100]}
    if obj.type == "MESH":
        result.update(vertices=len(obj.data.vertices), edges=len(obj.data.edges), polygons=len(obj.data.polygons),
                      materials=[m.name for m in obj.data.materials])
    return result


def execute_code(ctx, code, safe_mode=None):
    from ..core import util
    prefs = util.settings()
    enabled = prefs.safe_mode or safe_mode is True
    if enabled:
        safety.check(code)
    output = io.StringIO()
    namespace = {"bpy": bpy, "math": math}
    with contextlib.redirect_stdout(output):
        exec(compile(code, "<mcp-pro>", "exec"), namespace, namespace)
    return {"executed": True, "output": output.getvalue() or "ok"}


def viewport_screenshot(ctx, width=None, height=None, camera=None):
    from ..core import util
    scene = bpy.context.scene
    prefs = util.prefs()
    maximum = prefs.screenshot_size if prefs else 800
    width = max(64, min(int(width or maximum), maximum))
    height = max(64, min(int(height or width), maximum))
    old = (scene.camera, scene.render.engine, scene.render.resolution_x,
           scene.render.resolution_y, scene.render.filepath)
    try:
        if camera:
            scene.camera = find_object(camera)
        if scene.camera is None:
            cam_data = bpy.data.cameras.new("MCP Pro Camera")
            cam = bpy.data.objects.new("MCP Pro Camera", cam_data)
            scene.collection.objects.link(cam)
            center, radius = scene_bounds()
            cam.location = center + (radius * 2.5, -radius * 2.5, radius * 1.8)
            direction = center - cam.location
            cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
            scene.camera = cam
        scene.render.engine = eevee_engine_id()
        scene.render.resolution_x, scene.render.resolution_y = width, height
        scene.render.resolution_percentage = 100
        path = os.path.join(util.temp_dir(), "mcp_pro_view.png")
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        with open(path, "rb") as handle:
            data = base64.b64encode(handle.read()).decode("ascii")
        return ToolResult.ok({"width": width, "height": height}, images=[{"data": data, "mime": "image/png"}])
    finally:
        scene.camera, scene.render.engine, scene.render.resolution_x, scene.render.resolution_y, scene.render.filepath = old


def register_tools(registry):
    from .viewport import viewport_screenshot
    registry.tool("get_scene_info", "Get a compact overview of the current Blender scene")(get_scene_info)
    registry.tool("list_objects", "List scene objects", properties={
        "filter": {"type": "string"}, "limit": {"type": "integer", "default": 100}})(list_objects)
    registry.tool("get_object_info", "Get detailed information about one object",
                  properties={"name": {"type": "string"}}, required=("name",))(get_object_info)
    registry.tool("execute_code", "Execute Blender Python with Safe Mode checks", properties={
        "code": {"type": "string"}, "safe_mode": {"type": "boolean"}},
        required=("code",), mutating=True)(execute_code)
    registry.tool("viewport_screenshot", "Render a screenshot for visual verification", properties={
        "width": {"type": "integer"}, "height": {"type": "integer"},
        "camera": {"type": "string"}})(viewport_screenshot)

import base64
import os
import tempfile

import bpy

from ..core.results import ToolError, ToolResult
from ..core import util


def viewport_screenshot(ctx, width=None, height=None, camera=None):
    if bpy.app.background:
        raise ToolError("Viewport capture requires Blender with a graphical window")
    maximum = max(64, min(int(width or height or util.settings().screenshot_size), 2048))
    window = area = region = space = None
    for candidate in bpy.context.window_manager.windows:
        for item in candidate.screen.areas:
            if item.type == 'VIEW_3D':
                window, area, space = candidate, item, item.spaces.active
                region = next((r for r in item.regions if r.type == 'WINDOW'), None)
                break
        if region:
            break
    if region is None:
        raise ToolError("No 3D viewport found")
    if camera:
        raise ToolError("This tool captures the current viewport. Switch the viewport to camera view first.")
    fd, path = tempfile.mkstemp(suffix='.png', dir=util.temp_dir())
    os.close(fd)
    image = None
    try:
        method = 'offscreen'
        try:
            import gpu
            import numpy as np
            factor = min(1.0, maximum / max(region.width, region.height))
            w, h = max(1, int(region.width * factor)), max(1, int(region.height * factor))
            with bpy.context.temp_override(window=window, area=area, region=region):
                offscreen = gpu.types.GPUOffScreen(w, h)
                try:
                    offscreen.draw_view3d(
                        window.scene, window.view_layer, space, region,
                        space.region_3d.view_matrix, space.region_3d.window_matrix,
                        do_color_management=True,
                    )
                    buffer = offscreen.texture_color.read()
                finally:
                    offscreen.free()
            buffer.dimensions = w * h * 4
            pixels = np.asarray(buffer, dtype=np.float32) / 255.0
            image = bpy.data.images.new('MCP Pro Viewport', w, h, alpha=True)
            image.pixels.foreach_set(pixels.ravel())
            image.filepath_raw = path
            image.file_format = 'PNG'
            image.save()
        except Exception:
            if image is not None:
                bpy.data.images.remove(image)
                image = None
            method = 'window_grab'
            with bpy.context.temp_override(window=window, area=area, region=region):
                bpy.ops.screen.screenshot_area(filepath=path)
            image = bpy.data.images.load(path)
            w, h = image.size
            if max(w, h) > maximum:
                factor = maximum / max(w, h)
                w, h = max(1, int(w * factor)), max(1, int(h * factor))
                image.scale(w, h)
                image.file_format = 'PNG'
                image.save()
        with open(path, 'rb') as handle:
            data = base64.b64encode(handle.read()).decode('ascii')
        return ToolResult.ok({'width': w, 'height': h, 'method': method}, images=[{'data': data, 'mime': 'image/png'}])
    finally:
        if image is not None:
            bpy.data.images.remove(image)
        if os.path.exists(path):
            os.remove(path)

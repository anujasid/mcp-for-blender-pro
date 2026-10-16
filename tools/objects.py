import math

import bpy

from ..core.results import ToolError
from ..core.util import find_object, vec3, radians3, color4, link_to_scene, round3


def add_cube(ctx, name="Cube", location=None, size=1.0):
    loc = vec3(location, "location", (0, 0, 0))
    bpy.ops.mesh.primitive_cube_add(size=size, location=loc)
    created = bpy.context.active_object
    created.name = name
    return {"name": created.name, "location": round3(created.location)}


def add_sphere(ctx, name="Sphere", location=None, radius=1.0, subdivisions=32):
    loc = vec3(location, "location", (0, 0, 0))
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=radius,
        segments=subdivisions,
        ring_count=subdivisions // 2,
        location=loc,
    )
    obj = bpy.context.active_object
    obj.name = name
    return {"name": obj.name, "location": round3(obj.location), "radius": radius}


def add_cylinder(ctx, name="Cylinder", location=None, radius=1.0, depth=2.0, vertices=32):
    loc = vec3(location, "location", (0, 0, 0))
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius,
        depth=depth,
        vertices=vertices,
        location=loc,
    )
    obj = bpy.context.active_object
    obj.name = name
    return {"name": obj.name, "location": round3(obj.location)}


def add_plane(ctx, name="Plane", location=None, size=2.0):
    loc = vec3(location, "location", (0, 0, 0))
    bpy.ops.mesh.primitive_plane_add(size=size, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    return {"name": obj.name, "location": round3(obj.location)}


def add_light(ctx, name="Light", light_type="POINT", location=None, energy=100.0, color=None):
    types = {"POINT", "SUN", "SPOT", "AREA"}
    if light_type.upper() not in types:
        raise ToolError(f"light_type must be one of {types}")
    loc = vec3(location, "location", (0, 0, 5))
    light_data = bpy.data.lights.new(name, light_type.upper())
    light_data.energy = energy
    if color:
        light_data.color = color4(color, "color")[:3]
    obj = bpy.data.objects.new(name, light_data)
    obj.location = loc
    link_to_scene(obj)
    return {"name": obj.name, "type": light_type.upper(), "location": round3(obj.location)}


def add_camera(ctx, name="Camera", location=None, rotation=None, lens=50.0):
    loc = vec3(location, "location", (0, -5, 5))
    rot = radians3(rotation, "rotation") or (math.radians(60), 0, 0)
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = lens
    obj = bpy.data.objects.new(name, cam_data)
    obj.location = loc
    obj.rotation_euler = rot
    link_to_scene(obj)
    return {"name": obj.name, "location": round3(obj.location)}


def delete_object(ctx, name):
    obj = find_object(name)
    bpy.data.objects.remove(obj, do_unlink=True)
    return {"deleted": name}


def move_object(ctx, name, location=None, rotation=None, scale=None):
    obj = find_object(name)
    if location is not None:
        obj.location = vec3(location, "location")
    if rotation is not None:
        obj.rotation_euler = radians3(rotation, "rotation")
    if scale is not None:
        obj.scale = vec3(scale, "scale")
    return {
        "name": obj.name,
        "location": round3(obj.location),
        "rotation_euler": round3([math.degrees(v) for v in obj.rotation_euler]),
        "scale": round3(obj.scale),
    }


def duplicate_object(ctx, name, new_name=None, location=None):
    obj = find_object(name)
    new_obj = obj.copy()
    if obj.data:
        new_obj.data = obj.data.copy()
    if new_name:
        new_obj.name = new_name
    link_to_scene(new_obj)
    if location is not None:
        new_obj.location = vec3(location, "location")
    return {"original": obj.name, "duplicate": new_obj.name, "location": round3(new_obj.location)}


def set_material(ctx, object_name, material_name=None, color=None, metallic=0.0, roughness=0.5):
    obj = find_object(object_name)
    if not hasattr(obj.data, "materials"):
        raise ToolError(f"Object {object_name} cannot have materials (type: {obj.type})")
    mat_name = material_name or f"{obj.name}_Material"
    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf:
        bsdf.inputs['Metallic'].default_value = metallic
        bsdf.inputs['Roughness'].default_value = roughness
    if color is not None:
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = color4(color, "color")
            bsdf.inputs["Metallic"].default_value = metallic
            bsdf.inputs["Roughness"].default_value = roughness
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    return {"object": obj.name, "material": mat.name}


def parent_objects(ctx, child_name, parent_name):
    child = find_object(child_name)
    parent = find_object(parent_name)
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()
    return {"child": child.name, "parent": parent.name}


def register_tools(registry):
    registry.tool(
        "add_cube",
        "Add a cube mesh to the scene",
        properties={
            "name": {"type": "string", "description": "Object name", "default": "Cube"},
            "location": {"type": "array", "description": "[x, y, z] position", "items": {"type": "number"}},
            "size": {"type": "number", "description": "Edge length", "default": 1.0},
        },
        mutating=True,
    )(add_cube)

    registry.tool(
        "add_sphere",
        "Add a UV sphere mesh to the scene",
        properties={
            "name": {"type": "string", "description": "Object name", "default": "Sphere"},
            "location": {"type": "array", "description": "[x, y, z] position", "items": {"type": "number"}},
            "radius": {"type": "number", "description": "Sphere radius", "default": 1.0},
            "subdivisions": {"type": "integer", "description": "Segments count", "default": 32},
        },
        mutating=True,
    )(add_sphere)

    registry.tool(
        "add_cylinder",
        "Add a cylinder mesh to the scene",
        properties={
            "name": {"type": "string", "description": "Object name", "default": "Cylinder"},
            "location": {"type": "array", "description": "[x, y, z] position", "items": {"type": "number"}},
            "radius": {"type": "number", "description": "Base radius", "default": 1.0},
            "depth": {"type": "number", "description": "Height along Z", "default": 2.0},
            "vertices": {"type": "integer", "description": "Side vertices", "default": 32},
        },
        mutating=True,
    )(add_cylinder)

    registry.tool(
        "add_plane",
        "Add a plane mesh to the scene",
        properties={
            "name": {"type": "string", "description": "Object name", "default": "Plane"},
            "location": {"type": "array", "description": "[x, y, z] position", "items": {"type": "number"}},
            "size": {"type": "number", "description": "Edge length", "default": 2.0},
        },
        mutating=True,
    )(add_plane)

    registry.tool(
        "add_light",
        "Add a light source to the scene",
        properties={
            "name": {"type": "string", "description": "Light name", "default": "Light"},
            "light_type": {"type": "string", "description": "POINT, SUN, SPOT or AREA", "default": "POINT"},
            "location": {"type": "array", "description": "[x, y, z] position", "items": {"type": "number"}},
            "energy": {"type": "number", "description": "Light strength in watts", "default": 100.0},
            "color": {"description": "[r,g,b] in 0..1 or hex #RRGGBB"},
        },
        mutating=True,
    )(add_light)

    registry.tool(
        "add_camera",
        "Add a camera to the scene",
        properties={
            "name": {"type": "string", "description": "Camera name", "default": "Camera"},
            "location": {"type": "array", "description": "[x, y, z] position", "items": {"type": "number"}},
            "rotation": {"type": "array", "description": "[rx, ry, rz] in degrees", "items": {"type": "number"}},
            "lens": {"type": "number", "description": "Focal length (mm)", "default": 50.0},
        },
        mutating=True,
    )(add_camera)

    registry.tool(
        "delete_object",
        "Delete an object from the scene",
        properties={
            "name": {"type": "string", "description": "Object name to delete"},
        },
        required=("name",),
        mutating=True,
    )(delete_object)

    registry.tool(
        "move_object",
        "Move, rotate or scale an object",
        properties={
            "name": {"type": "string", "description": "Object name"},
            "location": {"type": "array", "description": "[x, y, z] position", "items": {"type": "number"}},
            "rotation": {"type": "array", "description": "[rx, ry, rz] in degrees", "items": {"type": "number"}},
            "scale": {"type": "array", "description": "[sx, sy, sz] scale factors", "items": {"type": "number"}},
        },
        required=("name",),
        mutating=True,
    )(move_object)

    registry.tool(
        "duplicate_object",
        "Duplicate an object",
        properties={
            "name": {"type": "string", "description": "Source object name"},
            "new_name": {"type": "string", "description": "New object name (optional)"},
            "location": {"type": "array", "description": "Position for duplicate", "items": {"type": "number"}},
        },
        required=("name",),
        mutating=True,
    )(duplicate_object)

    registry.tool(
        "set_material",
        "Create or assign a material to an object",
        properties={
            "object_name": {"type": "string", "description": "Object name"},
            "material_name": {"type": "string", "description": "Material name (auto-generated if omitted)"},
            "color": {"description": "[r,g,b] in 0..1 or hex #RRGGBB"},
            "metallic": {"type": "number", "description": "Metallic value 0..1", "default": 0.0},
            "roughness": {"type": "number", "description": "Roughness value 0..1", "default": 0.5},
        },
        required=("object_name",),
        mutating=True,
    )(set_material)

    registry.tool(
        "parent_objects",
        "Make one object child of another",
        properties={
            "child_name": {"type": "string", "description": "Child object name"},
            "parent_name": {"type": "string", "description": "Parent object name"},
        },
        required=("child_name", "parent_name"),
        mutating=True,
    )(parent_objects)

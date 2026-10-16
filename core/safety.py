import ast

from .results import ToolError

BLOCKED_MODULES = {
    "os", "sys", "subprocess", "shutil", "socket", "ctypes", "importlib",
    "urllib", "http", "requests", "ftplib", "smtplib", "telnetlib", "ssl",
    "pathlib", "glob", "tempfile", "pickle", "marshal", "multiprocessing",
    "threading", "asyncio", "signal", "winreg", "_winapi", "pty", "builtins",
    "webbrowser", "zipfile", "tarfile", "io", "code", "runpy", "site",
    "addon_utils", "bl_ext", "gc", "inspect", "posix", "nt", "_thread",
}

BLOCKED_CALLS = {
    "eval", "exec", "compile", "open", "__import__", "globals", "locals",
    "vars", "breakpoint", "input", "memoryview", "delattr",
}

ATTR_CALLS = {"getattr", "setattr", "hasattr"}

BLOCKED_ATTRS = {
    "system", "popen", "spawn", "spawnv", "execv", "unlink", "rmdir", "rmtree",
    "as_module", "execfile", "driver_namespace", "script_paths",
    "load_post", "load_pre", "save_pre", "save_post", "depsgraph_update_post",
    "depsgraph_update_pre", "frame_change_post", "frame_change_pre",
    "persistent", "binary_path", "f_globals", "f_locals", "gi_frame", "tb_frame",
}

BLOCKED_OPS = {
    ("wm", "quit_blender"), ("wm", "read_homefile"), ("wm", "read_factory_settings"),
    ("wm", "url_open"), ("wm", "path_open"), ("wm", "save_userpref"),
    ("preferences", "addon_install"), ("preferences", "addon_remove"),
    ("preferences", "addon_enable"), ("preferences", "addon_disable"),
    ("extensions", "package_install"), ("extensions", "package_uninstall"),
    ("extensions", "package_install_files"),
    ("script", "python_file_run"), ("script", "reload"), ("text", "run_script"),
}


class SafetyViolation(ToolError):
    pass


def _root_name(node):
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _ops_target(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    parts.reverse()
    if len(parts) >= 4 and parts[0] == "bpy" and parts[1] == "ops":
        return parts[2], parts[3]
    return None


def _check_attr_call(node, problems):
    if len(node.args) < 2:
        return
    key = node.args[1]
    if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
        problems.append(f"line {node.lineno}: {node.func.id}() needs a literal attribute name")
    elif key.value.startswith("_") or key.value in BLOCKED_ATTRS:
        problems.append(f"line {node.lineno}: {node.func.id}(..., '{key.value}')")


def check(code):
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        raise SafetyViolation(f"SyntaxError: {exc.msg} (line {exc.lineno})")
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in BLOCKED_MODULES:
                    problems.append(f"line {node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level or (node.module or "").split(".")[0] in BLOCKED_MODULES:
                problems.append(f"line {node.lineno}: from {node.module or '.'} import ...")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                if func.id in BLOCKED_CALLS:
                    problems.append(f"line {node.lineno}: {func.id}()")
                elif func.id in ATTR_CALLS:
                    _check_attr_call(node, problems)
            target = _ops_target(func)
            if target in BLOCKED_OPS:
                problems.append(f"line {node.lineno}: bpy.ops.{target[0]}.{target[1]}()")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                problems.append(f"line {node.lineno}: dunder access .{node.attr}")
            elif node.attr in BLOCKED_ATTRS:
                problems.append(f"line {node.lineno}: .{node.attr}")
            elif node.attr == "handlers" and _root_name(node) == "bpy":
                problems.append(f"line {node.lineno}: bpy.app.handlers")
        elif isinstance(node, ast.Name) and node.id in {"__builtins__", "__loader__", "__spec__", "__file__"}:
            problems.append(f"line {node.lineno}: {node.id}")
    if problems:
        raise SafetyViolation(
            "Safe mode blocked this script:\n- " + "\n- ".join(sorted(set(problems))[:20])
            + "\nUse the bpy data API and the built-in tools instead. File access, processes, "
              "network, handlers and add-on management are blocked while Safe Mode is on."
        )
    return tree

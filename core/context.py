import bpy

from . import mainthread


class ToolContext:
    def __init__(self, source="chat", timeout=600.0):
        self.source = source
        self.timeout = timeout

    def main(self, func):
        return mainthread.run(func, timeout=self.timeout)

    def undo_push(self, name):
        if bpy.app.background:
            return
        try:
            bpy.ops.ed.undo_push(message=f"MCP Pro: {name}")
        except Exception:
            pass

import json
import traceback


class ToolError(Exception):
    pass


class ToolResult:
    def __init__(self, text="", images=None, is_error=False):
        self.text = text
        self.images = list(images or [])
        self.is_error = is_error

    @classmethod
    def ok(cls, data=None, images=None):
        if data is None:
            text = "ok"
        elif isinstance(data, str):
            text = data
        else:
            text = json.dumps(data, ensure_ascii=False, indent=1, default=str)
        return cls(text=text, images=images)

    @classmethod
    def error(cls, message):
        return cls(text=str(message), is_error=True)

    def summary(self, limit=160):
        text = " ".join(self.text.split())
        if len(text) > limit:
            text = text[:limit - 1] + "\u2026"
        if self.images:
            text += f" [+{len(self.images)} image(s)]"
        return text

    def to_mcp(self):
        content = []
        if self.text:
            content.append({"type": "text", "text": self.text})
        for image in self.images:
            content.append({
                "type": "image",
                "data": image["data"],
                "mimeType": image.get("mime", "image/png"),
            })
        if not content:
            content.append({"type": "text", "text": "ok"})
        return {"content": content, "isError": bool(self.is_error)}


class Tool:
    def __init__(self, name, description, schema, func, mutating=False,
                 main_thread=True, title=None, group="core"):
        self.name = name
        self.description = description
        self.schema = schema or {"type": "object", "properties": {}}
        self.func = func
        self.mutating = mutating
        self.main_thread = main_thread
        self.title = title or name.replace("_", " ").title()
        self.group = group

    def mcp_spec(self):
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "inputSchema": self.schema,
            "annotations": {
                "title": self.title,
                "readOnlyHint": not self.mutating,
                "destructiveHint": self.mutating,
                "openWorldHint": self.group == "assets",
            },
        }


class Registry:
    def __init__(self):
        self._tools = {}

    def add(self, tool):
        self._tools[tool.name] = tool
        return tool

    def tool(self, name, description, properties=None, required=(), **options):
        def decorator(func):
            schema = {
                "type": "object",
                "properties": properties or {},
                "required": list(required),
                "additionalProperties": False,
            }
            self.add(Tool(name, description, schema, func, **options))
            return func
        return decorator

    def get(self, name):
        return self._tools.get(name)

    def tools(self, predicate=None):
        items = list(self._tools.values())
        if predicate is not None:
            items = [t for t in items if predicate(t)]
        return items

    def _clean_args(self, tool, args):
        if not isinstance(args, dict):
            raise ToolError("Tool arguments must be a JSON object")
        props = tool.schema.get("properties", {})
        unknown = sorted(k for k in args if k not in props)
        if unknown:
            raise ToolError(
                f"Unknown argument(s) for {tool.name}: {', '.join(unknown)}. "
                f"Allowed: {', '.join(props) or 'none'}"
            )
        clean = {k: v for k, v in args.items() if v is not None}
        missing = [k for k in tool.schema.get("required", []) if k not in clean]
        if missing:
            raise ToolError("Missing required argument(s): " + ", ".join(missing))
        return clean

    def call(self, name, args, ctx):
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult.error(f"Unknown tool: {name}. Available: {', '.join(sorted(self._tools))}")
        try:
            clean = self._clean_args(tool, args or {})
            if tool.main_thread:
                value = ctx.main(lambda: self._run_main(tool, clean, ctx))
            else:
                try:
                    value = tool.func(ctx, **clean)
                finally:
                    if tool.mutating:
                        ctx.main(lambda: ctx.undo_push(tool.title))
            if isinstance(value, ToolResult):
                return value
            return ToolResult.ok(value)
        except ToolError as exc:
            return ToolResult.error(str(exc))
        except Exception as exc:
            detail = traceback.format_exc(limit=4)
            return ToolResult.error(f"{type(exc).__name__}: {exc}\n{detail[-2000:]}")

    @staticmethod
    def _run_main(tool, clean, ctx):
        try:
            return tool.func(ctx, **clean)
        finally:
            if tool.mutating:
                ctx.undo_push(tool.title)

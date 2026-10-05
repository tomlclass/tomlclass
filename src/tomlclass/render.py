"""
Renderer: splice the original source using per-part dirty overrides.

Unchanged parts return their source slice verbatim (byte-exact axiom);
edited parts re-render from the live value with canonical formatting.

New entries (``block.pending`` / ``pending_tables`` / AoT pending elements)
are emitted *after* the newline that follows the block's last content part,
so they never glue onto an existing line.
"""

from __future__ import annotations

from typing import Any

from .nodes import ArrayOfTables, Table, format_key, format_value

__all__: list[str] = []


def render_document(source: str, parts: list[tuple[int, int, str, Any]], root: Table) -> str:
    out: list[str] = []
    flushed: set[int] = set()
    last_kv: dict[int, int] = {}       # id(block) -> part index of its last kv part
    aot_last: dict[int, int] = {}      # id(aot) -> part index of its last element header
    part_tables: dict[int, Table] = {} # part index -> block table (kv) / table (header)

    for index, (_s, _e, kind, payload) in enumerate(parts):
        if kind == "kv":
            block = payload[0]
            last_kv[id(block)] = index
            part_tables[index] = block
        elif kind == "header":
            table, aot = payload
            part_tables[index] = table
            if table.kind == "aot" and aot is not None:
                aot_last[id(aot)] = index

    # flush anchors: part index -> blocks whose pending entries render right
    # after that part (it is the newline trivia following their last content)
    anchors: dict[int, list[Table]] = {}
    for index in last_kv.values():
        anchors.setdefault(index + 1, []).append(part_tables[index])
    # sealed (dotted) tables anchor their pending entries right after their
    # own last physical line, not at the host block's tail
    for table in _walk_tables(root):
        if table._anchor is not None:
            anchors.setdefault(table._anchor + 1, []).append(table)

    suppress_trivia = False
    for index, (s, e, kind, payload) in enumerate(parts):
        if kind == "trivia":
            if suppress_trivia:
                continue
            text = source[s:e]
            anchor_blocks = anchors.get(index)
            if anchor_blocks:
                nl = text.find("\n")
                if nl != -1:
                    out.append(text[: nl + 1])
                    for block in anchor_blocks:
                        _flush(out, block, flushed)
                    out.append(text[nl + 1 :])
                else:
                    out.append(text)
                    for block in anchor_blocks:
                        _flush(out, block, flushed)
            else:
                out.append(text)
        elif kind == "kv":
            block, path = payload
            if block.dead or path in block.deleted:
                suppress_trivia = True
                continue
            suppress_trivia = False
            appended_array = block.array_appends.get(path)
            if appended_array is not None and appended_array._appended:
                vs, ve, _cs = block.entry_spans[path]
                out.append(source[s:vs] + _splice_array_append(source[vs:ve], appended_array) + source[ve:e])
                continue
            override_comment = path in block.comments
            if override_comment or path in block.dirty:
                vs, ve, cs = block.entry_spans[path]
                value_text = format_value(block.dirty[path]) if path in block.dirty else source[vs:ve]
                if override_comment:
                    ctext = block.comments[path]
                    if ctext is None:
                        out.append(source[s:vs] + value_text)
                    else:
                        # reuse the original leading whitespace; new injections add their own separator
                        sep = source[ve:cs] if cs < e else "  "
                        out.append(source[s:vs] + value_text + sep + f"# {ctext}")
                else:
                    out.append(source[s:vs] + value_text + source[ve:e])
            else:
                out.append(source[s:e])
        elif kind == "header":
            table, aot = payload
            if table.dead:
                suppress_trivia = True
                # whole replacement: render all new elements at the last (dead) element position
                if aot is not None and aot_last.get(id(aot)) == index and aot.pending_elements:
                    header = "[[" + ".".join(format_key(k) for k in table._header_keys) + "]]\n"
                    for data in aot.pending_elements:
                        out.append(header)
                        for key, value in data.items():
                            out.append(f"{format_key(key)} = {format_value(value)}\n")
                    aot.pending_elements.clear()
                continue
            suppress_trivia = False
            out.append(source[s:e])
            # empty table with runtime-added entries and no kv anchor part:
            if id(table) not in last_kv and (table.pending or table.pending_tables) and index + 1 < len(parts):
                anchors.setdefault(index + 1, []).append(table)

    def _visit(table: Table) -> None:
        if id(table) not in flushed and not table.dead:
            _flush(out, table, flushed)
        for value in table.values():
            if isinstance(value, Table):
                _visit(value)
            elif isinstance(value, ArrayOfTables):
                for element in value:
                    if isinstance(element, Table):
                        _visit(element)

    _visit(root)
    return "".join(out)


def _walk_tables(table: Table):
    yield table
    for value in table.values():
        if isinstance(value, Table):
            yield from _walk_tables(value)
        elif isinstance(value, ArrayOfTables):
            for element in value:
                if isinstance(element, Table):
                    yield from _walk_tables(element)


def _flush(
    out: list[str],
    block: Table,
    flushed: set[int],
    parent_path: tuple[str, ...] = (),
    *,
    top: bool = True,
) -> None:
    """
    Render pending entries of *block*.

    ``top=True``: called from the render loop / sealed-table anchor — scalar
    keys are block-relative (``block._phys`` applies). ``top=False``: called
    from a pending-table recursion — ``parent_path`` already contains the full
    table path and scalar keys are plain names.
    """
    if id(block) in flushed or block.dead:
        return
    flushed.add(id(block))
    if block._aot is not None and block._aot.pending_elements:
        header = "[[" + ".".join(format_key(k) for k in parent_path + tuple(block._header_keys)) + "]]\n"
        for data in block._aot.pending_elements:
            out.append(header)
            for key, value in data.items():
                out.append(f"{format_key(key)} = {format_value(value)}\n")
        block._aot.pending_elements.clear()
    for path, value in block.pending:
        full = (block._phys if top else ()) + path
        key = ".".join(format_key(k) for k in full)
        out.append(f"{key} = {format_value(value)}\n")
    for path, subtable in block.pending_tables:
        # pending sub-tables carry the host path prefix ([tool.mytool], not [mytool])
        full = (parent_path if not top else ()) + tuple(block._header_keys) + path
        header = "[" + ".".join(format_key(k) for k in full) + "]\n"
        out.append("\n" + header)
        _flush(out, subtable, flushed, parent_path=full, top=False)


def _splice_array_append(value_text: str, arr: Any) -> str:
    """
    Insert appended elements into the original array text.

    Multiline arrays gain a new properly-indented line (trailing comments of
    the previous last element stay on that element); single-line arrays are
    extended in place.
    """
    close = value_text.rfind("]")
    body = value_text[:close]
    elems = ", ".join(format_value(v) for v in arr._appended)
    newline = chr(10)
    if newline in body:
        # match the last element line's indentation; the new element is appended as its own line
        content_end = len(body.rstrip())
        elem_line_start = body.rfind(newline, 0, content_end) + 1
        elem_line = body[elem_line_start:content_end]
        indent = elem_line[: len(elem_line) - len(elem_line.lstrip())]
        return body[:content_end] + newline + indent + elems + "," + body[content_end:] + "]"
    stripped = body.rstrip()
    trailing = body[len(stripped):]
    if stripped.endswith("["):
        return stripped + elems + trailing + "]"
    if stripped.endswith(","):
        return stripped + " " + elems + trailing + "]"
    return stripped + ", " + elems + trailing + "]"

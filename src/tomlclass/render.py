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

from .nodes import Array, ArrayOfTables, Table, format_key, format_value

__all__: list[str] = []


def render_document(source: str, parts: list[tuple[int, int, str, Any]], root: Table) -> str:
    # generated lines (pending entries, new tables) match the file's endings
    nl = "\r\n" if "\r\n" in source else chr(10)
    out: list[str] = []
    flushed: set[int] = set()
    scalar_flushed: set[int] = set()
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
    # flush anchors: part index -> flush requests rendered right after that
    # part (it is the newline trivia following their last content).
    # ("table", block) flushes the block's pending entries; ("aot", aot)
    # flushes an aot's pending_elements (rendered as fresh [[blocks]]).
    anchors: dict[int, list[tuple[str, Any]]] = {}
    for index in last_kv.values():
        block = part_tables[index]
        if block.kind == "root":
            # root's pending scalars flush right after the last root kv line
            # (before the first header); root's pending tables must NOT anchor
            # here — a new [cache] would land in the file's front. They render
            # at EOF instead (see the post-loop flush).
            anchors.setdefault(index + 1, []).append(("table_scalars", block))
        else:
            anchors.setdefault(index + 1, []).append(("table", block))
    # an aot with runtime-added elements anchors after its last element's
    # last kv line — NOT after the [[header]], where the new element would
    # land before the last element's own entries
    aot_tails: dict[int, tuple[int, Any]] = {}
    for index in last_kv.values():
        block = part_tables[index]
        if block._aot is not None:
            aot_tails[id(block._aot)] = (index + 1, block._aot)
    for idx, aot in aot_tails.values():
        anchors.setdefault(idx, []).append(("aot", aot))
    # aot elements inserted before a parsed element anchor to that element's
    # [[header]] part — the new block renders right before it (header parts
    # always follow a trivia part, so they never collide with the anchors above).
    # Bookkeeping lives in ArrayOfTables._inserted_elements — keep in sync.
    for index, (_s, _e, kind, payload) in enumerate(parts):
        if kind != "header":
            continue
        table, aot = payload
        if aot is None or not aot._inserted_elements:
            continue
        if any(anchor is table for anchor, _el in aot._inserted_elements):
            anchors.setdefault(index, []).append(("aot_ins", (aot, table)))
    # sealed (dotted) tables anchor their pending entries right after their
    # own last physical line, not at the host block's tail
    for table in _walk_tables(root):
        if table._anchor is not None:
            anchors.setdefault(table._anchor + 1, []).append(("table", table))

    suppress_trivia = False

    def _dispatch_flush(kind_: str, obj: Any) -> None:
        if kind_ == "aot":
            _flush_aot_appended(out, obj, nl, flushed)
        elif kind_ == "table_scalars":
            _flush(out, obj, flushed, scalar_flushed=scalar_flushed, scalars_only=True, nl=nl)
        else:
            _flush(out, obj, flushed, nl=nl)

    for index, (s, e, kind, payload) in enumerate(parts):
        if kind == "trivia":
            anchor_blocks = anchors.get(index)
            if suppress_trivia and not anchor_blocks:
                continue
            text = source[s:e]
            if anchor_blocks:
                if suppress_trivia:
                    # the preceding line is dead and stays suppressed, but the
                    # anchors at this position must still flush (a whole
                    # replacement renders its new elements right here)
                    for kind_, obj in anchor_blocks:
                        _dispatch_flush(kind_, obj)
                    continue
                pos = text.find("\n")
                if pos != -1:
                    out.append(text[: pos + 1])
                    for kind_, obj in anchor_blocks:
                        _dispatch_flush(kind_, obj)
                    out.append(text[pos + 1 :])
                else:
                    out.append(text)
                    for kind_, obj in anchor_blocks:
                        _dispatch_flush(kind_, obj)
            else:
                out.append(text)
        elif kind == "kv":
            block, path = payload
            if block.dead or path in block.deleted:
                suppress_trivia = True
                continue
            suppress_trivia = False
            # array value handling: element edits / appends anywhere in the
            # array tree rebuild the whole value region (layout and element
            # comments survive); anything unrebuildable falls back to a
            # canonical render of the OUTERMOST array — rendering an inner
            # array alone would drop its siblings
            array_top = None
            if path in block.array_appends:
                array_top = block.array_appends[path]
                while array_top._parent_array is not None:
                    array_top = array_top._parent_array
            dirty_value = block.dirty.get(path)
            if dirty_value is not None and not isinstance(dirty_value, Array):
                array_top = None  # the array was replaced by a scalar/inline value
            elif dirty_value is not None:
                top = dirty_value
                while top._parent_array is not None:
                    top = top._parent_array
                if array_top is None or not array_top.span or array_top.span != top.span:
                    array_top = top  # a descendant mutation registered the inner array
            override_comment = path in block._comments
            if override_comment or path in block.dirty or array_top is not None:
                vs, ve, cs = block.entry_spans[path]
                value_text = None
                if array_top is not None and (dirty_value is None or isinstance(dirty_value, Array)):
                    # region rebuild: covers element edits, structural child
                    # mutations (None → canonical fallback inside), and
                    # appended elements at every nesting level
                    value_text = _render_array_edits(source, vs, ve, array_top)
                if value_text is None:
                    if array_top is not None:
                        # unrebuildable tree: canonical render of the OUTERMOST
                        # array — the inner value alone would drop its siblings
                        value_text = format_value(array_top)
                    elif dirty_value is not None:
                        value_text = format_value(dirty_value)
                    else:
                        value_text = source[vs:ve]
                if override_comment:
                    ctext = block._comments[path]  # raw: starts with '#', or None = suppressed
                    if ctext is None:
                        out.append(source[s:vs] + value_text)
                    else:
                        # reuse the original leading whitespace; new injections add their own separator
                        sep = source[ve:cs] if cs < e else "  "
                        out.append(source[s:vs] + value_text + sep + ctext)
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
                    header = "[[" + ".".join(format_key(k) for k in table._header_keys) + "]]" + nl
                    for data in aot.pending_elements:
                        out.append(header)
                        for key, value in data.items():
                            out.append(f"{format_key(key)} = {format_value(value)}" + nl)
                    aot.pending_elements.clear()
                # inserts anchored to a removed element still render —
                # at the position that element occupied
                if aot is not None:
                    for kind_, obj in anchors.get(index, ()):
                        if kind_ == "aot_ins":
                            _flush_aot_inserted(out, obj[0], obj[1], nl)
                continue
            # root-level pending scalars with no root kv anchor must render
            # BEFORE the first header — appended after it they would silently
            # become entries of the enclosing table
            if id(root) not in last_kv and id(root) not in scalar_flushed and root.pending:
                _flush(out, root, flushed, scalar_flushed=scalar_flushed, scalars_only=True, nl=nl)
            suppress_trivia = False
            for kind_, obj in anchors.get(index, ()):
                if kind_ == "aot_ins":
                    _flush_aot_inserted(out, obj[0], obj[1], nl)
            # a set_comment override splices into the header line; the parsed
            # comment span marks where the original comment starts. A None
            # override suppresses the original comment entirely.
            if () in table._comments:
                ctext = table._comments[()]
                span = table._header_comment_span
                base = source[s : span[0]].rstrip() if span else source[s:e].rstrip()
                out.append(f"{base}  {ctext}" if ctext else base)
            else:
                out.append(source[s:e])
            # empty table with runtime-added entries and no kv anchor part:
            if id(table) not in last_kv and (table.pending or table.pending_tables) and index + 1 < len(parts):
                anchors.setdefault(index + 1, []).append(("table", table))

    # root-level pending tables render at EOF — after every parsed block —
    # no matter where the root's own kv lines sit (its scalars flushed earlier
    # via the table_scalars anchor, before the first header)
    if root.pending_tables and id(root) not in flushed:
        _flush(out, root, flushed, scalar_flushed=scalar_flushed, nl=nl)

    def _visit(table: Table) -> None:
        if id(table) not in flushed and not table.dead:
            _flush(out, table, flushed, scalar_flushed=scalar_flushed, nl=nl)
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
    scalar_flushed: set[int] | None = None,
    scalars_only: bool = False,
    nl: str = chr(10),
) -> None:
    """
    Render pending entries of *block*.

    ``top=True``: called from the render loop / sealed-table anchor — scalar
    keys are block-relative (``block._phys`` applies). ``top=False``: called
    from a pending-table recursion — ``parent_path`` already contains the full
    table path and scalar keys are plain names.

    ``scalars_only=True`` (with *scalar_flushed*): emit only ``block.pending``
    scalar entries and record the block, leaving ``pending_tables`` for a full
    flush later — used to place root-level keys before the first header.
    """
    if id(block) in flushed or block.dead:
        return
    if scalars_only:
        if scalar_flushed is None or id(block) in scalar_flushed:
            return
        scalar_flushed.add(id(block))
        for path, value in block.pending:
            full = (block._phys if top else ()) + path
            key = ".".join(format_key(k) for k in full)
            ctext = block._comments.get(full)
            suffix = f"  {ctext}" if ctext else ""
            out.append(f"{key} = {format_value(value)}{suffix}" + nl)
        out.extend(line + nl for line in block.pending_trivia)
        return
    flushed.add(id(block))
    # an implicit super-table ([db.pool] exists, [db] never declared) that
    # gained entries renders its own [header] block — dotted lines at the
    # parent level would land at EOF, physically inside the previously
    # defined block's scope, silently changing their meaning
    implicit_super = (
        top and not block.defined and block._block is None and bool(block._header_keys) and block.pending
    )
    if implicit_super:
        if out:
            out.append(nl)
        out.append("[" + ".".join(format_key(k) for k in block._header_keys) + "]" + nl)
    # NOTE: an aot's pending_elements are rendered exclusively by the aot
    # anchor (aot_tails) or the _visit fallback — never here, where the
    # position would be that of an arbitrary element table.
    if scalar_flushed is None or id(block) not in scalar_flushed:
        for path, value in block.pending:
            # implicit super-table entries render plain under their own
            # freshly emitted [header]
            prefix = block._phys or () if top else ()
            full = prefix + path
            key = ".".join(format_key(k) for k in full)
            ctext = block._comments.get(full)
            suffix = f"  {ctext}" if ctext else ""
            out.append(f"{key} = {format_value(value)}{suffix}" + nl)
        out.extend(line + nl for line in block.pending_trivia)
    for path, subtable in block.pending_tables:
        if subtable.dead:
            continue  # replaced/removed before render: no header, no body
        # pending sub-tables carry the host path prefix ([tool.mytool], not [mytool])
        full = (parent_path if not top else ()) + tuple(block._header_keys) + path
        header = "[" + ".".join(format_key(k) for k in full) + "]" + nl
        if "".join(out).strip():
            out.append(nl)
        out.append(header)
        _flush(out, subtable, flushed, parent_path=full, top=False, scalar_flushed=scalar_flushed, nl=nl)
    for path, aot in block.pending_aots:
        # a constructed aot assigned to a fresh key: its elements render as
        # [[blocks]] at the block tail; the registration is never cleared so
        # later appends re-render with it (dumps stays idempotent)
        full = (parent_path if not top else ()) + tuple(block._header_keys) + path
        base_header = "[[" + ".".join(format_key(k) for k in full) + "]]"
        for element in aot:
            if "".join(out).strip():
                out.append(nl)
            ctext = element._comments.get(())
            out.append(base_header + (f"  {ctext}" if ctext else "") + nl)
            for key, value in element.items():
                out.append(f"{format_key(key)} = {format_value(value)}" + nl)


def _flush_aot_appended(out: list[str], aot: Any, nl: str, flushed: set[int]) -> None:
    """Emit an aot's runtime-appended element tables as fresh ``[[block]]`` sections."""
    if id(aot) in flushed:
        return
    tail_ids = {id(element) for element in aot._appended_elements}
    tail_ids.update(id(el) for anchor, el in aot._inserted_elements if anchor is None)
    if not tail_ids:
        return
    flushed.add(id(aot))
    _emit_aot_blocks(out, aot, tail_ids, nl)


def _flush_aot_inserted(out: list[str], aot: Any, anchor: Any, nl: str) -> None:
    """
    Emit elements inserted before the parsed element *anchor* as fresh
    ``[[block]]`` sections, in current list order so memory and output agree.
    """
    ids = {id(el) for a, el in aot._inserted_elements if a is anchor}
    if not ids:
        return
    _emit_aot_blocks(out, aot, ids, nl)


def _emit_aot_blocks(out: list[str], aot: Any, ids: set[int], nl: str) -> None:
    header = "[[" + ".".join(format_key(k) for k in aot._header_keys) + "]]" + nl
    # walk the live list, not the bookkeeping: appended/inserted order must
    # match memory, and removed or dead elements render nothing
    for element in aot:
        if id(element) in ids and not element.dead:
            out.append(header)
            for key, value in element.items():
                out.append(f"{format_key(key)} = {format_value(value)}" + nl)


def _render_array_edits(source: str, vs: int, ve: int, dirty_value: Any) -> str | None:
    """
    Render the value text ``source[vs:ve]`` for an array whose *elements* were
    assigned through the mapping API, splicing new element texts into the
    original text — layout and element comments survive. Nested arrays are
    rebuilt recursively (inner edits first, then spliced into the parent), so
    ``arr[0][0] = 9`` touches exactly one position, and appended elements are
    re-attached by ``_splice_array_append``. Returns None when rebuilding is
    impossible and the caller should fall back to canonical rendering of the
    touched array.
    """
    top = dirty_value
    while top._parent_array is not None:
        top = top._parent_array
    region = _build_region(source, top)
    if region is None:
        return None
    s0, s1 = top.span
    return source[vs:s0] + region + source[s1:ve]


def _build_region(source: str, a: Any) -> str | None:
    if a._dirty_indices is None or len(a.spans) > len(a) or not a.span:
        return None
    ops: list[tuple[int, int, str]] = []
    for i in sorted(a._dirty_indices):
        if i < len(a.spans) and a.spans[i] is not None:
            sp = a.spans[i]
            ops.append((sp[0], sp[1], format_value(a[i])))
        # span-None entries are appended elements: re-attached below
    for v in a:
        if isinstance(v, Array):
            child = _build_region(source, v)
            if child is None:
                return None
            ops.append((v.span[0], v.span[1], child))
    ops.sort(key=lambda t: -t[0])
    region = source[a.span[0] : a.span[1]]
    for o0, o1, rep in ops:
        region = region[: o0 - a.span[0]] + rep + region[o1 - a.span[0] :]
    appended_indices = [i for i, sp in enumerate(a.spans) if sp is None]
    tail = [format_value(a[i]) for i in range(len(a.spans), len(a))]
    if appended_indices or tail:
        elems = [format_value(a[i]) for i in appended_indices] + tail
        region = _splice_array_append(region, elems)
    return region


def _splice_array_append(value_text: str, elems: list[str]) -> str:
    """
    Insert appended element texts into the original array text.

    Multiline arrays gain a new properly-indented line (trailing comments of
    the previous last element stay on that element); single-line arrays are
    extended in place.
    """
    close = value_text.rfind("]")
    body = value_text[:close]
    elems_text = ", ".join(elems)
    # match the file's line ending so an appended line does not create
    # mixed line endings inside one array
    crlf = chr(13) + chr(10)
    newline = crlf if crlf in body else chr(10)
    if newline in body:
        # match the last element line's indentation; the new element is appended as its own line
        content_end = len(body.rstrip())
        elem_line_start = body.rfind(newline, 0, content_end) + len(newline)
        elem_line = body[elem_line_start:content_end]
        indent = elem_line[: len(elem_line) - len(elem_line.lstrip())]
        return body[:content_end] + newline + indent + elems_text + "," + body[content_end:] + "]"
    stripped = body.rstrip()
    trailing = body[len(stripped):]
    if stripped.endswith("["):
        return stripped + elems_text + trailing + "]"
    if stripped.endswith(","):
        return stripped + " " + elems_text + trailing + "]"
    return stripped + ", " + elems_text + trailing + "]"

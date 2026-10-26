"""
Engine benchmark: tomlclass vs tomli vs tomlkit (all pure Python, same machine).

Usage:
    uv run --with tomli --with tomlkit python scripts/bench/bench.py --compare --iterations 500
"""

import argparse
import gc
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import tomlclass

DATA_FILES = [
    ("data0 (pytomlpp)", Path(__file__).parent / "data" / "data0.toml"),
    ("data2 (tomli)", Path(__file__).parent / "data" / "data2.toml"),
]


def bench_parse(label: str, text: str, iterations: int) -> float:
    for _ in range(5):
        tomlclass.parse(text)  # warmup
    gc.collect()
    start = time.perf_counter()
    for _ in range(iterations):
        tomlclass.parse(text)
    elapsed = time.perf_counter() - start
    print(f"  tomlclass parse {label:<18} {elapsed:8.2f}s / {iterations} iters")
    return elapsed


# -- deterministic edit-path fixtures -----------------------------------------


def gen_array_doc(elements: int = 500) -> str:
    """A table hosting one multiline array with a comment on every element."""
    lines = ["[weights]", "values = ["]
    for i in range(elements):
        comma = "," if i < elements - 1 else ""
        lines.append(f"    {i * 7 % 997}{comma}  # element {i}")
    lines.append("]")
    return "\n".join(lines) + "\n"


def gen_aot_doc(blocks: int = 100) -> str:
    """An array of tables with *blocks* ``[[item]]`` sections."""
    parts: list[str] = []
    for i in range(blocks):
        parts.append("[[item]]")
        parts.append(f"id = {i}")
        parts.append(f"name = 'item {i}'")
        parts.append(f"score = {i}.5")
        parts.append("")
    return "\n".join(parts)


def _timed(fn: Callable[[], Any], iterations: int) -> float:
    fn()  # warmup (also fails fast if a workload is miswired)
    gc.collect()
    start = time.perf_counter()
    for _ in range(iterations):
        fn()
    return time.perf_counter() - start


def _report(name: str, elapsed: float, iterations: int) -> None:
    per_ms = elapsed / iterations * 1000
    print(f"  {name:<36} {elapsed:8.3f}s / {iterations} iters  ({per_ms:7.2f} ms/iter)")


def run_edit_workloads(iterations: int, tomlkit: Any) -> None:
    """Parse+edit+dumps cycles: the cost above the parse-only baseline is the edit path."""
    data2 = (Path(__file__).parent / "data" / "data2.toml").read_text(encoding="utf-8")
    array_doc = gen_array_doc(500)
    aot_doc = gen_aot_doc(100)

    def set100() -> None:  # 100 new scalar keys on one existing table
        doc = tomlclass.parse(data2)
        table = doc["contain"]
        for i in range(100):
            table[f"new-key-{i}"] = i
        doc.dumps()

    def tables50() -> None:  # 50 new [sub]tables at document root
        doc = tomlclass.parse(data2)
        for i in range(50):
            doc[f"t{i:02d}"] = {"x": i, "y": "value"}
        doc.dumps()

    def array50() -> None:  # 50 element edits in a 500-element multiline array
        doc = tomlclass.parse(array_doc)
        values = doc["weights"]["values"]
        for i in range(0, 500, 10):
            values[i] = i * 13
        doc.dumps()

    def aot50() -> None:  # 50 dict appends onto a 100-block array of tables
        doc = tomlclass.parse(aot_doc)
        items = doc["item"]
        for i in range(50):
            items.append({"id": 100 + i, "name": f"item {100 + i}", "score": 100.5})
        doc.dumps()

    def aot_insert25() -> None:  # 25 inserts at the head (anchor scan path)
        doc = tomlclass.parse(aot_doc)
        items = doc["item"]
        for i in range(25):
            items.insert(0, {"id": -1 - i, "name": "inserted", "score": 0.5})
        doc.dumps()

    class _AppConfig(tomlclass.Config):
        ghost: float = 0.5
        port: int = 8080

    updates = {
        "contain.new-key-0": 1,
        "contain.ghost": 0.5,
        "crime.reject-naughty": 42,
        "server.host": "localhost",  # missing keys exercise the create path
        "server.port": 8080,
    }

    def update_e2e() -> None:  # update(): read + dotted sets + atomic write
        path.write_bytes(data2.encode("utf-8"))
        tomlclass.update(path, updates)

    print("== edit-path workloads (each iteration = parse + edit + dumps)")

    def parse_only(text: str) -> Callable[[], Any]:
        return lambda: tomlclass.parse(text)

    _report("tomlclass parse only (data2)", _timed(parse_only(data2), iterations), iterations)
    _report("tomlclass parse only (array500)", _timed(parse_only(array_doc), iterations), iterations)
    _report("tomlclass parse only (aot100)", _timed(parse_only(aot_doc), iterations), iterations)
    _report("tomlclass set100 + dumps", _timed(set100, iterations), iterations)
    _report("tomlclass tables50 + dumps", _timed(tables50, iterations), iterations)
    _report("tomlclass array50edit + dumps", _timed(array50, iterations), iterations)
    _report("tomlclass aot50append + dumps", _timed(aot50, iterations), iterations)
    _report("tomlclass aot25insert + dumps", _timed(aot_insert25, iterations), iterations)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.toml"
        _report("tomlclass update() end-to-end", _timed(update_e2e, iterations), iterations)

        def config_cycle() -> None:  # Config.load + mutate + save
            path.write_bytes(data2.encode("utf-8"))
            cfg = _AppConfig.load(path)
            cfg.port = 9090
            cfg.save(path)

        _report("tomlclass Config load+save", _timed(config_cycle, iterations), iterations)

    if tomlkit is not None:
        def kset100() -> None:
            doc = tomlkit.parse(data2)
            table = doc["contain"]
            for i in range(100):
                table[f"new-key-{i}"] = i
            tomlkit.dumps(doc)

        def ktables50() -> None:
            doc = tomlkit.parse(data2)
            for i in range(50):
                doc[f"t{i:02d}"] = tomlkit.table()
                doc[f"t{i:02d}"]["x"] = i
                doc[f"t{i:02d}"]["y"] = "value"
            tomlkit.dumps(doc)

        _report("tomlkit    set100 + dumps", _timed(kset100, iterations), iterations)
        _report("tomlkit    tables50 + dumps", _timed(ktables50, iterations), iterations)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=500)
    parser.add_argument("--compare", action="store_true", help="also benchmark tomli")
    args = parser.parse_args()

    tomli = None
    tomlkit = None
    if args.compare:
        try:
            import tomli as tomli_mod
            tomli = tomli_mod
        except ImportError:
            print("--compare requested but tomli is not installed; skipping tomli")
        try:
            import tomlkit as tomlkit_mod
            tomlkit = tomlkit_mod
        except ImportError:
            print("--compare requested but tomlkit is not installed; skipping tomlkit")

    ratios: list[tuple[str, float]] = []
    for label, path in DATA_FILES:
        text = path.read_text(encoding="utf-8")
        print(f"== {label} ({len(text)} bytes)")
        mine = bench_parse(label, text, args.iterations)
        if tomli is not None:
            start = time.perf_counter()
            for _ in range(args.iterations):
                tomli.loads(text)
            theirs = time.perf_counter() - start
            print(f"  tomli      parse {label:<18} {theirs:8.2f}s / {args.iterations} iters")
            ratios.append(("tomli", mine / theirs))
            print(f"  ratio tomlclass/tomli = {mine / theirs:.2f}x (budget: <= 2.00x)")
        if tomlkit is not None:
            start = time.perf_counter()
            for _ in range(args.iterations):
                tomlkit.parse(text)
            theirs = time.perf_counter() - start
            print(f"  tomlkit    parse {label:<18} {theirs:8.2f}s / {args.iterations} iters")
            ratios.append(("tomlkit", mine / theirs))
            print(f"  ratio tomlclass/tomlkit = {mine / theirs:.2f}x")

        # dumps cost for an unchanged document must be ~free
        doc = tomlclass.parse(text)
        start = time.perf_counter()
        for _ in range(args.iterations):
            doc.dumps()
        elapsed = time.perf_counter() - start
        print(f"  tomlclass dumps(unchanged) {label:<10} {elapsed:8.4f}s")

        # edited dumps: the real user path (edit one key, then render)
        first_key = next(iter(doc.root))
        start = time.perf_counter()
        for _ in range(args.iterations):
            doc[first_key] = 1
            doc.dumps()
            doc[first_key] = 2
        elapsed = time.perf_counter() - start
        print(f"  tomlclass dumps(1-key edit) {label:<10} {elapsed:8.4f}s")
        if tomlkit is not None:
            kdoc = tomlkit.parse(text)
            start = time.perf_counter()
            for _ in range(args.iterations):
                tomlkit.dumps(kdoc)
            elapsed = time.perf_counter() - start
            print(f"  tomlkit  dumps(unchanged) {label:<10} {elapsed:8.2f}s")

    run_edit_workloads(args.iterations, tomlkit)

    tomli_ratios = [r for name, r in ratios if name == "tomli"]
    if tomli_ratios:
        print(f"\nWORST parse ratio vs tomli: {max(tomli_ratios):.2f}x (budget: <= 2.00x)")
        return 0 if max(tomli_ratios) <= 2.0 else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

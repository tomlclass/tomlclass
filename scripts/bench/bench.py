"""
Engine benchmark: tomlclass vs tomli vs tomlkit (all pure Python, same machine).

Usage:
    uv run --with tomli --with tomlkit python scripts/bench/bench.py --compare --iterations 500
"""

import argparse
import gc
import sys
import time
from pathlib import Path

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

    tomli_ratios = [r for name, r in ratios if name == "tomli"]
    if tomli_ratios:
        print(f"\nWORST parse ratio vs tomli: {max(tomli_ratios):.2f}x (budget: <= 2.00x)")
        return 0 if max(tomli_ratios) <= 2.0 else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Run the API test suite in memory-bounded chunks.

The full suite OOMs as a single pytest process under the api container's memory
limit (memory accumulates across the ~300 tests — each test spins up a fresh
TestClient/app lifespan). This runs it as several sequential pytest invocations:
a fresh process per chunk releases memory between chunks, and serial execution
avoids races on the shared test database (tests truncate tables).

Exits non-zero if any chunk fails. Chunk size is configurable via
PYTEST_CHUNK_SIZE (default 8 files); extra args are forwarded to pytest, e.g.
`python scripts/run_tests.py -k auth`.
"""

from __future__ import annotations

import glob
import math
import os
import subprocess
import sys


def main() -> int:
    # Target files-per-chunk; the suite is split into ceil(num_files/size) chunks.
    # Fewer chunks = less repeated per-process setup (schema rebuild + seed), so
    # keep this as large as memory allows. ~13 (≈3 chunks today) stays well under
    # the container memory limit while only paying the setup cost a few times.
    chunk_size = int(os.getenv("PYTEST_CHUNK_SIZE", "13"))
    files = sorted(glob.glob("tests/test_*.py"))
    if not files:
        print("run_tests: no test files found under tests/", file=sys.stderr)
        return 1

    # Balanced round-robin split (no tiny trailing chunk).
    n_chunks = max(1, math.ceil(len(files) / chunk_size))
    chunks = [c for c in (files[i::n_chunks] for i in range(n_chunks)) if c]
    extra = sys.argv[1:]  # forwarded to pytest
    failed: list[int] = []

    for idx, chunk in enumerate(chunks, 1):
        print(
            f"\n===== test chunk {idx}/{len(chunks)} ({len(chunk)} files) =====",
            flush=True,
        )
        rc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                *extra,
                *chunk,
            ]
        ).returncode
        if rc != 0:
            failed.append(idx)

    print("\n" + "=" * 52)
    if failed:
        print(
            f"FAILED: {len(failed)}/{len(chunks)} chunk(s) -> {failed}",
            file=sys.stderr,
        )
        return 1
    print(f"OK: all {len(chunks)} chunk(s) passed ({len(files)} test files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

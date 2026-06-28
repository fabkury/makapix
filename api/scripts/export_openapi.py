"""Dump the FastAPI OpenAPI 3.1 schema as stable, sorted JSON to stdout.

Used by `make openapi` (regenerate the committed `api/openapi.json`) and
`make check` (fail the gate if the committed schema drifted from the code).
Keys are sorted so the committed file produces a deterministic, reviewable diff.
"""

from __future__ import annotations

import json
import sys

from app.main import app


def main() -> None:
    schema = app.openapi()
    json.dump(schema, sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()

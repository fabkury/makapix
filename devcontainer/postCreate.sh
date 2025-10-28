#!/usr/bin/env bash
set -euo pipefail

cd /workspace

python3 -m pip install --upgrade pip
python3 -m pip install -e ./api[dev]

npm --prefix web install

pre-commit install

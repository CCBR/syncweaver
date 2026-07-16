#!/usr/bin/env bash
set -euo pipefail

python ./check_cli_docs.py
python -m quartodoc build --verbose && \
  python -m quartodoc interlinks
quarto render

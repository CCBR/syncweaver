ccbr_tools quarto-add fnl
python ./check_cli_docs.py
python -m quartodoc build --verbose && \
  python -m quartodoc interlinks
quarto render

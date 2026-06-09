"""
Workflow template files for syncweaver.

Templates can be listed and copied into downstream host repository or package repos
using the helper functions below or via the CLI:

```sh
syncweaver templates list
syncweaver templates add update-sources --output .github/workflows/
```

Use `available_templates_markdown()` to render the current template inventory.
"""

import importlib.resources
import pathlib

_TEMPLATE_DESCRIPTIONS = {
    "update-sources.yml": "Run syncweaver update from a workflow dispatch or repository dispatch",
}


def list_templates() -> list[str]:
    """
    List available workflow templates.

    Returns:
        list[str]: Template file names.

    Examples:
        >>> list_templates()
    """
    pkg = importlib.resources.files(__package__)
    return sorted(p.name for p in pkg.iterdir() if p.name.endswith(".yml"))


def available_templates_markdown() -> str:
    """
    Build a markdown bullet list of currently available template files.

    Returns:
        str: Markdown-formatted bullet list.

    Examples:
        >>> available_templates_markdown()
    """
    lines = []
    for name in list_templates():
        description = _TEMPLATE_DESCRIPTIONS.get(name)
        if description:
            lines.append(f"- `{name}` - {description}")
        else:
            lines.append(f"- `{name}`")
    return "\n".join(lines)


def read_template(template_name: str) -> str:
    """
    Read a template file's contents.

    Args:
        template_name (str): Name of the template file (with or without .yml extension).

    Returns:
        str: Contents of the template file.

    Raises:
        FileNotFoundError: If the template file does not exist.

    Examples:
        >>> read_template("host-repo-pattern1-outbound.yml")
    """
    if not template_name.endswith(".yml"):
        template_name = f"{template_name}.yml"
    available = list_templates()
    if template_name not in available:
        raise FileNotFoundError(
            f"Template '{template_name}' not found. "
            f"Available templates: {', '.join(available)}"
        )
    template_content = ""
    template_path = importlib.resources.files(__package__) / template_name
    with importlib.resources.as_file(template_path) as p:
        template_content = p.read_text()
    return template_content


def use_template(
    template_name: str,
    output_dir: str | pathlib.Path = ".github/workflows",
    overwrite: bool = False,
) -> pathlib.Path:
    """
    Copy a workflow template into the specified output directory.

    Args:
        template_name (str): Name of the template file (with or without .yml extension).
        output_dir (str | pathlib.Path): Directory to write the template. Defaults to
            ``.github/workflows``.
        overwrite (bool): If ``True``, overwrite an existing file. Defaults to ``False``.

    Returns:
        pathlib.Path: Path to the written file.

    Raises:
        FileNotFoundError: If the template does not exist.
        FileExistsError: If the destination file already exists and ``overwrite`` is ``False``.

    Examples:
        >>> use_template("host-repo-pattern1-outbound.yml")
    """
    if not template_name.endswith(".yml"):
        template_name = f"{template_name}.yml"
    content = read_template(template_name)
    out_dir = pathlib.Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / template_name
    if dest.exists() and not overwrite:
        raise FileExistsError(
            f"{dest} already exists. Pass overwrite=True to replace it."
        )
    dest.write_text(content)
    return dest

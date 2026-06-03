"""
Workflow template files for syncweaver.

Templates can be listed and copied into downstream capsule or package repos
using the helper functions below or via the CLI:

```sh
syncweaver templates list
syncweaver templates add capsule-pattern1-outbound --output .github/workflows/
```

### Available templates

- `capsule-pattern1-outbound.yml` — Push vendored code changes as an upstream PR
- `capsule-dependencies-refresh.yml` — Regenerate DEPENDENCIES.yml on entrypoint changes
- `capsule-mark-rejected.yml` — Manually mark a patch as rejected (workflow_dispatch)
- `package-release-notify.yml` — Dispatch release notifications to relevant capsules
"""

import importlib.resources
import pathlib


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
        >>> read_template("capsule-pattern1-outbound.yml")
    """
    if not template_name.endswith(".yml"):
        template_name = f"{template_name}.yml"
    available = list_templates()
    if template_name not in available:
        raise FileNotFoundError(
            f"Template '{template_name}' not found. "
            f"Available templates: {', '.join(available)}"
        )
    template_path = importlib.resources.files(__package__) / template_name
    with importlib.resources.as_file(template_path) as p:
        return p.read_text()


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
        >>> use_template("capsule-pattern1-outbound.yml")
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

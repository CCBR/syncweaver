"""Tests for the syncweaver templates module."""

import pytest

from syncweaver.templates import (
    available_templates_markdown,
    list_templates,
    read_template,
    use_template,
)


def test_list_templates():
    names = list_templates()
    assert len(names) > 0
    assert all(n.endswith(".yml") for n in names)


def test_read_template():
    names = list_templates()
    content = read_template(names[0])
    assert isinstance(content, str)


def test_read_template_without_extension():
    names = list_templates()
    stem = names[0].removesuffix(".yml")
    content = read_template(stem)
    assert isinstance(content, str)


def test_read_template_not_found():
    with pytest.raises(FileNotFoundError):
        read_template("does-not-exist.yml")


def test_use_template(tmp_path):
    names = list_templates()
    dest = use_template(names[0], output_dir=tmp_path)
    assert dest.exists()
    assert dest.read_text() == read_template(names[0])


def test_use_template_no_overwrite(tmp_path):
    names = list_templates()
    use_template(names[0], output_dir=tmp_path)
    with pytest.raises(FileExistsError):
        use_template(names[0], output_dir=tmp_path, overwrite=False)


def test_use_template_overwrite(tmp_path):
    names = list_templates()
    use_template(names[0], output_dir=tmp_path)
    dest = use_template(names[0], output_dir=tmp_path, overwrite=True)
    assert dest.exists()


def test_available_templates_markdown_contains_discovered_names():
    names = list_templates()
    rendered = available_templates_markdown()
    for name in names:
        assert f"`{name}`" in rendered

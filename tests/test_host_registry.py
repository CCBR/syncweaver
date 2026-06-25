"""Tests for host registry helper functions."""

from __future__ import annotations

import json

import pytest
import yaml

from syncweaver.host_registry import build_host_matrix_from_registry


def test_build_host_matrix_fails_when_registry_missing(tmp_path):
    """Verify missing registry file raises a readable FileNotFoundError.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    registry_path = tmp_path / "host-repositories.yml"

    with pytest.raises(FileNotFoundError, match="host repository registry not found"):
        build_host_matrix_from_registry(registry_path, "CCBR/package1")


def test_build_host_matrix_fails_when_hosts_is_not_list(tmp_path):
    """Verify invalid registry shape raises a readable ValueError.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    registry_path = tmp_path / "host-repositories.yml"
    registry_path.write_text(yaml.safe_dump({"hosts": {"bad": "shape"}}))

    with pytest.raises(ValueError, match="must define a list under 'hosts'"):
        build_host_matrix_from_registry(registry_path, "CCBR/package1")


def test_build_host_matrix_selects_matching_hosts(tmp_path):
    """Verify registry filtering returns hosts relevant to source repository.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    registry_data = {
        "hosts": [
            {
                "repository": "NIDAP/MOSuite-create",
                "source_repository": "CCBR/package1",
                "lockfile": ".syncweaver-lock.json",
                "remote_subdir": "",
            },
            {
                "repository": "NIDAP/Other-host",
                "source_repository": "CCBR/package2",
            },
            {
                "repository": "NIDAP/No-filter",
                "source_repository": "CCBR/package1",
            },
            "bad-item",
        ]
    }
    registry_path = tmp_path / "host-repositories.yml"
    registry_path.write_text(yaml.safe_dump(registry_data))

    matrix_hosts = build_host_matrix_from_registry(
        registry_path=registry_path,
        source_repository="CCBR/package1",
    )

    assert len(matrix_hosts) == 2
    assert matrix_hosts[0]["repository"] == "NIDAP/MOSuite-create"
    assert matrix_hosts[0]["lockfile"] == ".syncweaver-lock.json"
    assert "source_path" not in matrix_hosts[0]
    assert matrix_hosts[1]["repository"] == "NIDAP/No-filter"


def test_build_host_matrix_serializable_for_strategy(tmp_path):
    """Verify matrix output is JSON serializable for workflow fan-out usage.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    registry_data = {
        "hosts": [
            {
                "repository": "NIDAP/MOSuite-create",
            }
        ]
    }
    registry_path = tmp_path / "host-repositories.yml"
    registry_path.write_text(yaml.safe_dump(registry_data))

    matrix_hosts = build_host_matrix_from_registry(
        registry_path=registry_path,
        source_repository="CCBR/package1",
    )

    serialized = json.dumps(matrix_hosts)
    assert "NIDAP/MOSuite-create" in serialized


def test_build_host_matrix_does_not_require_name(tmp_path):
    """Verify registry entries resolve without a legacy `name` field.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    registry_data = {
        "hosts": [
            {
                "repository": "NIDAP/MOSuite-create",
                "source_repository": "CCBR/package1",
            }
        ]
    }
    registry_path = tmp_path / "host-repositories.yml"
    registry_path.write_text(yaml.safe_dump(registry_data))

    matrix_hosts = build_host_matrix_from_registry(
        registry_path=registry_path,
        source_repository="CCBR/package1",
    )

    assert len(matrix_hosts) == 1
    assert matrix_hosts[0]["repository"] == "NIDAP/MOSuite-create"


def test_build_host_matrix_ignores_name_only_entries(tmp_path):
    """Verify entries without repository are skipped even if `name` is present.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    registry_data = {
        "hosts": [
            {
                "name": "legacy-host-name-only",
                "source_repository": "CCBR/package1",
            },
            {
                "name": "legacy-name",
                "repository": "NIDAP/MOSuite-create",
                "source_repository": "CCBR/package1",
            },
        ]
    }
    registry_path = tmp_path / "host-repositories.yml"
    registry_path.write_text(yaml.safe_dump(registry_data))

    matrix_hosts = build_host_matrix_from_registry(
        registry_path=registry_path,
        source_repository="CCBR/package1",
    )

    assert len(matrix_hosts) == 1
    assert matrix_hosts[0]["repository"] == "NIDAP/MOSuite-create"

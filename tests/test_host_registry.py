"""Tests for host registry helper functions."""

from __future__ import annotations

import json

import pytest
import yaml
from unittest.mock import patch, MagicMock

from syncweaver.host_registry import (
    build_host_matrix_from_registry,
    get_lockfile_sources_from_remote,
    source_repo_in_host_lockfile,
)


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


def test_get_lockfile_sources_from_remote_parses_json():
    """Verify lockfile JSON is fetched and source URLs are extracted.

    Returns:
        None: Assertions validate function behavior.
    """
    lockfile_data = {
        "name": "NIDAP/host-repo",
        "sources": {
            "code/pkg1": {
                "repo_url": "https://github.com/CCBR/package1",
                "ref": "main",
            },
            "code/pkg2": {
                "repo_url": "CCBR/package2",
                "ref": "v1.0",
            },
        },
    }

    with patch("syncweaver.host_registry.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = json.dumps(lockfile_data)
        mock_get.return_value = mock_response

        sources = get_lockfile_sources_from_remote(
            host_repository="NIDAP/host-repo",
            lockfile_path=".syncweaver-lock.json",
            ref="main",
        )

        assert len(sources) == 2
        assert "https://github.com/CCBR/package1" in sources
        assert "https://github.com/CCBR/package2" in sources


def test_get_lockfile_sources_from_remote_normalizes_urls():
    """Verify different URL formats are normalized consistently.

    Returns:
        None: Assertions validate function behavior.
    """
    lockfile_data = {
        "sources": {
            "code/pkg1": {
                "repo_url": "git@github.com:CCBR/package1.git",
                "ref": "main",
            },
        },
    }

    with patch("syncweaver.host_registry.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = json.dumps(lockfile_data)
        mock_get.return_value = mock_response

        sources = get_lockfile_sources_from_remote(
            host_repository="NIDAP/host-repo",
            lockfile_path=".syncweaver-lock.json",
        )

        assert "https://github.com/CCBR/package1" in sources


def test_get_lockfile_sources_from_remote_handles_empty_sources():
    """Verify empty or missing sources dict returns empty set.

    Returns:
        None: Assertions validate function behavior.
    """
    with patch("syncweaver.host_registry.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = json.dumps({"sources": {}})
        mock_get.return_value = mock_response

        sources = get_lockfile_sources_from_remote(
            host_repository="NIDAP/host-repo",
            lockfile_path=".syncweaver-lock.json",
        )

        assert len(sources) == 0


def test_get_lockfile_sources_from_remote_raises_on_invalid_json():
    """Verify invalid JSON raises ValueError with helpful message.

    Returns:
        None: Assertions validate function behavior.
    """
    with patch("syncweaver.host_registry.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = "{ invalid json"
        mock_get.return_value = mock_response

        with pytest.raises(ValueError, match="invalid JSON"):
            get_lockfile_sources_from_remote(
                host_repository="NIDAP/host-repo",
                lockfile_path=".syncweaver-lock.json",
            )


def test_source_repo_in_host_lockfile_returns_true_when_present():
    """Verify function returns True when source repo is in lockfile.

    Returns:
        None: Assertions validate function behavior.
    """
    lockfile_data = {
        "sources": {
            "code/pkg": {
                "repo_url": "https://github.com/CCBR/mypackage",
                "ref": "main",
            },
        },
    }

    with patch("syncweaver.host_registry.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = json.dumps(lockfile_data)
        mock_get.return_value = mock_response

        result = source_repo_in_host_lockfile(
            source_repository="CCBR/mypackage",
            host_repository="NIDAP/host-repo",
            lockfile_path=".syncweaver-lock.json",
        )

        assert result is True


def test_source_repo_in_host_lockfile_returns_false_when_absent():
    """Verify function returns False when source repo is not in lockfile.

    Returns:
        None: Assertions validate function behavior.
    """
    lockfile_data = {
        "sources": {
            "code/pkg": {
                "repo_url": "https://github.com/CCBR/other-package",
                "ref": "main",
            },
        },
    }

    with patch("syncweaver.host_registry.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = json.dumps(lockfile_data)
        mock_get.return_value = mock_response

        result = source_repo_in_host_lockfile(
            source_repository="CCBR/mypackage",
            host_repository="NIDAP/host-repo",
            lockfile_path=".syncweaver-lock.json",
        )

        assert result is False


def test_source_repo_in_host_lockfile_returns_false_on_fetch_error():
    """Verify function returns False when lockfile cannot be fetched.

    Returns:
        None: Assertions validate function behavior.
    """
    with patch("syncweaver.host_registry.requests.get") as mock_get:
        mock_get.side_effect = Exception("Network error")

        result = source_repo_in_host_lockfile(
            source_repository="CCBR/mypackage",
            host_repository="NIDAP/host-repo",
            lockfile_path=".syncweaver-lock.json",
        )

        assert result is False

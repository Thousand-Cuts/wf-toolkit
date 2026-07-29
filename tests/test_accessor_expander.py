"""Tests for skills/workfront-permissions/scripts/accessor_expander.py."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "skills" / "workfront-permissions" / "scripts"


@pytest.fixture(autouse=True)
def _expander_on_path():
    str_scripts = str(SCRIPTS_DIR)
    if str_scripts not in sys.path:
        sys.path.insert(0, str_scripts)
    yield


@pytest.fixture
def expander():
    sys.modules.pop("accessor_expander", None)
    return importlib.import_module("accessor_expander")


def test_user_accessor_returns_itself(expander):
    out = expander.expand_accessor_to_users({"objCode": "USER", "id": "u1"})
    assert out == ["u1"]


def test_group_accessor_returns_members(expander):
    out = expander.expand_accessor_to_users(
        {"objCode": "GROUP", "id": "g1"},
        group_member_index={"g1": ["u1", "u2", "u3"]},
    )
    assert out == ["u1", "u2", "u3"]


def test_team_accessor_returns_members(expander):
    out = expander.expand_accessor_to_users(
        {"objCode": "TEAMOB", "id": "t1"},
        team_member_index={"t1": ["u1", "u2"]},
    )
    assert out == ["u1", "u2"]


def test_role_accessor_returns_users(expander):
    out = expander.expand_accessor_to_users(
        {"objCode": "ROLE", "id": "r1"},
        role_member_index={"r1": ["u1"]},
    )
    assert out == ["u1"]


def test_unknown_objcode_returns_empty(expander):
    out = expander.expand_accessor_to_users(
        {"objCode": "WHAT", "id": "x"},
    )
    assert out == []


def test_missing_id_returns_empty(expander):
    out = expander.expand_accessor_to_users({"objCode": "GROUP"})
    assert out == []


def test_group_with_subgroup_cascade(expander):
    out = expander.expand_accessor_to_users(
        {"objCode": "GROUP", "id": "g1"},
        group_member_index={"g1": ["u1"], "g2": ["u2", "u3"]},
        group_child_index={"g1": ["g2"]},
        cascade_to_subgroups=True,
    )
    assert sorted(out) == ["u1", "u2", "u3"]


def test_group_without_subgroup_cascade_excludes_subgroup_members(expander):
    out = expander.expand_accessor_to_users(
        {"objCode": "GROUP", "id": "g1"},
        group_member_index={"g1": ["u1"], "g2": ["u2"]},
        group_child_index={"g1": ["g2"]},
        cascade_to_subgroups=False,
    )
    assert out == ["u1"]


def test_group_with_parent_cascade(expander):
    out = expander.expand_accessor_to_users(
        {"objCode": "GROUP", "id": "g1"},
        group_member_index={"g1": ["u1"], "parent": ["u2", "u3"]},
        group_parent_index={"g1": ["parent"]},
        cascade_to_parent_groups=True,
    )
    assert sorted(out) == ["u1", "u2", "u3"]


def test_cyclic_groups_do_not_loop_forever(expander):
    out = expander.expand_accessor_to_users(
        {"objCode": "GROUP", "id": "g1"},
        group_member_index={"g1": ["u1"], "g2": ["u2"]},
        group_child_index={"g1": ["g2"], "g2": ["g1"]},  # cycle
        cascade_to_subgroups=True,
    )
    assert sorted(out) == ["u1", "u2"]


def test_dedup_preserves_order(expander):
    out = expander.expand_accessor_to_users(
        {"objCode": "GROUP", "id": "g1"},
        group_member_index={"g1": ["u1", "u2"], "g2": ["u2", "u3"]},
        group_child_index={"g1": ["g2"]},
        cascade_to_subgroups=True,
    )
    assert out == ["u1", "u2", "u3"]


def test_empty_indices_return_empty(expander):
    out = expander.expand_accessor_to_users(
        {"objCode": "GROUP", "id": "g1"},
    )
    assert out == []

"""Tests for skills/workfront-permissions/scripts/inheritance_walker.py."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "skills" / "workfront-permissions" / "scripts"


@pytest.fixture(autouse=True)
def _walker_on_path():
    str_scripts = str(SCRIPTS_DIR)
    if str_scripts not in sys.path:
        sys.path.insert(0, str_scripts)
    yield


@pytest.fixture
def walker():
    sys.modules.pop("inheritance_walker", None)
    return importlib.import_module("inheritance_walker")


def test_parent_path_for_task(walker):
    assert walker.parent_path_for_objcode("TASK") == ["PROJ", "PORT", "PROG"]


def test_parent_path_for_optask(walker):
    assert walker.parent_path_for_objcode("OPTASK") == ["PROJ", "PORT", "PROG"]


def test_parent_path_for_proj(walker):
    assert walker.parent_path_for_objcode("PROJ") == ["PORT", "PROG"]


def test_parent_path_for_unknown(walker):
    assert walker.parent_path_for_objcode("UNKNOWN") == []


def test_parent_path_for_tmpl_is_empty(walker):
    assert walker.parent_path_for_objcode("TMPL") == []


def test_walk_for_rules_returns_parents_as_is_for_task(walker):
    target = {
        "objCode": "TASK",
        "parents": [
            {"objCode": "PROJ", "ID": "p1", "accessRules": []},
            {"objCode": "PORT", "ID": "port1", "accessRules": []},
        ],
    }
    out = walker.walk_for_rules(target)
    assert len(out) == 2
    assert out[0]["objCode"] == "PROJ"


def test_walk_for_rules_caps_docu_depth(walker):
    parents = [
        {"objCode": "FOLDER", "ID": f"f{i}", "accessRules": []}
        for i in range(15)
    ]
    target = {"objCode": "DOCU", "parents": parents}
    out = walker.walk_for_rules(target)
    assert len(out) == walker.FOLDER_DEPTH_CAP + 1  # cap + marker entry
    assert out[-1]["objCode"] == "DEPTH_CAP"


def test_walk_for_rules_docu_below_cap_passes_through(walker):
    parents = [
        {"objCode": "FOLDER", "ID": f"f{i}", "accessRules": []}
        for i in range(5)
    ]
    target = {"objCode": "DOCU", "parents": parents}
    out = walker.walk_for_rules(target)
    assert len(out) == 5
    assert all(p["objCode"] == "FOLDER" for p in out)


def test_needs_inheritance_walk_task_yes(walker):
    assert walker.needs_inheritance_walk("TASK") is True


def test_needs_inheritance_walk_tmpl_no(walker):
    assert walker.needs_inheritance_walk("TMPL") is False


def test_is_known_objcode(walker):
    assert walker.is_known_objcode("PROJ") is True
    assert walker.is_known_objcode("BOGUS") is False

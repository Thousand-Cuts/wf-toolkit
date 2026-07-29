"""Tests for skills/workfront-custom-forms/scripts/schema_cache.py.

Renamed from test_schema_cache.py to avoid collision with the
workfront-reports schema_cache tests (same module name, different skill).
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "skills" / "workfront-custom-forms" / "scripts"


@pytest.fixture
def schema_cache(monkeypatch, tmp_path):
    """Import the custom-forms schema_cache module fresh per test and
    redirect its CACHE_DIR to tmp_path.

    The fresh import dance is necessary because workfront-reports has
    a same-named module on sys.path — importlib.invalidate_caches() plus
    a sys.path-prepend ensures we load the right one.
    """
    str_scripts = str(SCRIPTS_DIR)
    if str_scripts in sys.path:
        sys.path.remove(str_scripts)
    sys.path.insert(0, str_scripts)
    sys.modules.pop("schema_cache", None)

    module = importlib.import_module("schema_cache")
    monkeypatch.setattr(module, "CACHE_DIR", tmp_path)
    return module


def test_read_returns_none_when_no_file(schema_cache):
    assert schema_cache.read("example.workfront.com") is None


def test_write_then_read_round_trips(schema_cache):
    objects = {
        "category": {"fields": [{"name": "name"}, {"name": "objCode"}]},
        "parameter": {"fields": [{"name": "parameterType"}]},
    }
    schema_cache.write("example.workfront.com", objects)
    data = schema_cache.read("example.workfront.com")
    assert data is not None
    assert data["objects"] == objects
    assert data["host"] == "example.workfront.com"


def test_write_sets_mode_600(schema_cache):
    schema_cache.write("example.workfront.com", {"category": {}})
    path = schema_cache.cache_path("example.workfront.com")
    mode = os.stat(path).st_mode & 0o777
    assert mode == 0o600


def test_read_returns_none_after_ttl_expiry(schema_cache):
    schema_cache.write("example.workfront.com", {"category": {}})
    path = schema_cache.cache_path("example.workfront.com")
    data = json.loads(path.read_text())
    data["captured_at_epoch"] = int(time.time()) - (25 * 60 * 60)
    path.write_text(json.dumps(data))
    assert schema_cache.read("example.workfront.com") is None


def test_read_returns_none_on_hash_mismatch(schema_cache):
    schema_cache.write("example.workfront.com", {"category": {"v": 1}})
    path = schema_cache.cache_path("example.workfront.com")
    data = json.loads(path.read_text())
    data["objects"] = {"category": {"v": 2}}
    path.write_text(json.dumps(data))
    assert schema_cache.read("example.workfront.com") is None


def test_invalidate_removes_file(schema_cache):
    schema_cache.write("example.workfront.com", {"category": {}})
    assert schema_cache.cache_path("example.workfront.com").exists()
    schema_cache.invalidate("example.workfront.com")
    assert not schema_cache.cache_path("example.workfront.com").exists()
    assert schema_cache.read("example.workfront.com") is None


def test_invalidate_is_safe_when_file_absent(schema_cache):
    schema_cache.invalidate("never-cached.workfront.com")  # no exception


def test_different_hosts_have_independent_caches(schema_cache):
    schema_cache.write("a.workfront.com", {"category": {"v": "a"}})
    schema_cache.write("b.workfront.com", {"category": {"v": "b"}})

    a = schema_cache.read("a.workfront.com")
    b = schema_cache.read("b.workfront.com")
    assert a["objects"]["category"]["v"] == "a"
    assert b["objects"]["category"]["v"] == "b"
    assert (
        schema_cache.cache_path("a.workfront.com")
        != schema_cache.cache_path("b.workfront.com")
    )


def test_hash_of_is_canonical(schema_cache):
    h1 = schema_cache.hash_of({"a": 1, "b": 2})
    h2 = schema_cache.hash_of({"b": 2, "a": 1})
    assert h1 == h2


def test_read_returns_none_on_corrupted_json(schema_cache):
    path = schema_cache.cache_path("example.workfront.com")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json")
    assert schema_cache.read("example.workfront.com") is None

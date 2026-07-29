"""Tests for skills/workfront-reports/scripts/schema_cache.py."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "workfront-reports" / "scripts"))

import schema_cache  # noqa: E402


class SchemaCacheTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.tmp.name)
        patcher = patch.object(schema_cache, "CACHE_DIR", self.cache_dir)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_host_hash_is_stable_and_collision_resistant(self):
        h1 = schema_cache.host_hash("acme.my.workfront.com")
        h2 = schema_cache.host_hash("acme.my.workfront.com")
        h3 = schema_cache.host_hash("contoso.my.workfront.com")
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)
        self.assertEqual(len(h1), 12)

    def test_put_then_get_roundtrips(self):
        metadata = {"name": "report", "fields": [{"name": "uiObjCode"}]}
        schema_cache.put("acme.my.workfront.com", "report", metadata)
        retrieved = schema_cache.get("acme.my.workfront.com", "report")
        self.assertEqual(retrieved["fields"], metadata["fields"])
        self.assertIn("schemaHash", retrieved)
        self.assertIn("fetchedAt", retrieved)

    def test_get_returns_none_when_absent(self):
        self.assertIsNone(schema_cache.get("acme.my.workfront.com", "report"))

    def test_schema_hash_changes_on_response_change(self):
        m1 = {"fields": [{"name": "uiObjCode"}]}
        m2 = {"fields": [{"name": "reportObjCode"}]}
        schema_cache.put("acme.my.workfront.com", "report", m1)
        hash1 = schema_cache.get("acme.my.workfront.com", "report")["schemaHash"]
        schema_cache.put("acme.my.workfront.com", "report", m2)
        hash2 = schema_cache.get("acme.my.workfront.com", "report")["schemaHash"]
        self.assertNotEqual(hash1, hash2)

    def test_cache_is_per_host(self):
        schema_cache.put("acme.my.workfront.com", "report", {"fields": [{"name": "A"}]})
        schema_cache.put("contoso.my.workfront.com", "report", {"fields": [{"name": "B"}]})
        a = schema_cache.get("acme.my.workfront.com", "report")
        c = schema_cache.get("contoso.my.workfront.com", "report")
        self.assertEqual(a["fields"][0]["name"], "A")
        self.assertEqual(c["fields"][0]["name"], "B")

    def test_inspect_returns_all_objects_for_host(self):
        schema_cache.put("acme.my.workfront.com", "report", {"fields": []})
        schema_cache.put("acme.my.workfront.com", "uivw", {"fields": []})
        bundle = schema_cache.inspect("acme.my.workfront.com")
        self.assertIn("report", bundle)
        self.assertIn("uivw", bundle)

    def test_ttl_expiry(self):
        schema_cache.put("acme.my.workfront.com", "report", {"fields": []})
        with patch.object(schema_cache, "now_epoch", return_value=schema_cache.now_epoch() + 25 * 3600):
            self.assertIsNone(schema_cache.get("acme.my.workfront.com", "report"))


if __name__ == "__main__":
    unittest.main()

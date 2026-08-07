"""Tests for skills/workfront-reports/scripts/pre_flight_validator.py."""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "workfront-reports" / "scripts"))

import pre_flight_validator  # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "metadata"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}-metadata.json").read_text())


class _StubCache:
    """Stand-in for schema_cache.get/put used by the validator."""
    def __init__(self, metadata_by_obj: dict):
        self._data = metadata_by_obj

    def get(self, host: str, obj_code: str):
        return self._data.get(obj_code.lower())


class PlainFieldValidationTest(unittest.TestCase):
    def setUp(self):
        self.cache = _StubCache({"proj": _load("proj")})

    def test_valid_field_passes(self):
        bundle = {"uift": {"definition": {"status": "CUR", "status_Mod": "in"},
                           "uiObjCode": "PROJ"},
                  "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertTrue(result["valid"])

    def test_isTemplate_on_PROJ_blocks_with_synonym_hint(self):
        bundle = {"uift": {"definition": {"isTemplate": "false",
                                          "isTemplate_Mod": "eq"},
                           "uiObjCode": "PROJ"},
                  "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertFalse(result["valid"])
        # error mentions the field AND the synonym hint
        msg = " ".join(e["reason"] + " " + " ".join(e.get("suggestions", []))
                       for e in result["errors"])
        self.assertIn("isTemplate", " ".join(e["path"] for e in result["errors"]))
        self.assertIn("TMPL", msg)

    def test_unknown_field_yields_levenshtein_suggestion(self):
        # Misspell "status" as "statu"
        bundle = {"uift": {"definition": {"statu": "CUR"},
                           "uiObjCode": "PROJ"},
                  "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertFalse(result["valid"])
        suggestions = " ".join(
            " ".join(e.get("suggestions", [])) for e in result["errors"]
        )
        self.assertIn("status", suggestions)


class SessionTokenPassThroughTest(unittest.TestCase):
    def setUp(self):
        self.cache = _StubCache({"proj": _load("proj")})

    def test_USER_ID_in_value_does_not_validate_as_field(self):
        bundle = {"uift": {"definition": {"ownerID": "$$USER.ID",
                                          "ownerID_Mod": "eq"},
                           "uiObjCode": "PROJ"},
                  "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertTrue(result["valid"])  # ownerID is real on PROJ; $$ value passes


class ORGroupTest(unittest.TestCase):
    def setUp(self):
        self.cache = _StubCache({"proj": _load("proj")})

    def test_OR_group_inherits_uiObjCode_context(self):
        bundle = {"uift": {"definition": {
            "OR:1:status": "CUR",
            "OR:1:status_Mod": "in",
            "OR:1:fakeFieldDoesNotExist": "x",
        }, "uiObjCode": "PROJ"},
            "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        # Real field passes; fake field fails
        self.assertFalse(result["valid"])
        bad_paths = [e["path"] for e in result["errors"]]
        self.assertTrue(any("fakeFieldDoesNotExist" in p for p in bad_paths))


class EXISTSBlockTest(unittest.TestCase):
    def setUp(self):
        self.cache = _StubCache({
            "proj": _load("proj"),
            "task": _load("task")
        })

    def test_EXISTS_block_resolves_against_block_objCode(self):
        bundle = {"uift": {"definition": {
            "EXISTS:a:$$EXISTSMOD": "EXISTS",
            "EXISTS:a:$$OBJCODE": "TASK",
            "EXISTS:a:ID": "FIELD:taskID",
            "EXISTS:a:status": "CPL",         # status IS on TASK
            "EXISTS:a:status_Mod": "in"
        }, "uiObjCode": "PROJ"},
            "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertTrue(result["valid"])

    def test_EXISTS_control_keys_skipped(self):
        bundle = {"uift": {"definition": {
            "EXISTS:a:$$EXISTSMOD": "EXISTS",
            "EXISTS:a:$$OBJCODE": "TASK",
            "EXISTS:a:$$ID": "anything",
            "EXISTS:a:ID": "FIELD:taskID"
        }, "uiObjCode": "PROJ"},
            "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        # control keys + ID-on-TASK both valid
        self.assertTrue(result["valid"])


class EXISTSCountCapTest(unittest.TestCase):
    """v0.16.2 — gotcha #17. Adobe documents 5 as the hard cap; pre-flight
    warns at 4 and errors at 5+."""

    def setUp(self):
        self.cache = _StubCache({
            "proj": _load("proj"),
            "task": _load("task"),
        })

    def _build_uift_with_n_exists(self, n):
        """Construct a UIFT.definition with n distinct EXISTS letter blocks."""
        defn = {}
        for letter in "abcdefghij"[:n]:
            defn[f"EXISTS:{letter}:$$EXISTSMOD"] = "EXISTS"
            defn[f"EXISTS:{letter}:$$OBJCODE"] = "TASK"
            defn[f"EXISTS:{letter}:ID"] = "FIELD:taskID"
        return {"uift": {"definition": defn, "uiObjCode": "PROJ"},
                "report": {"uiObjCode": "PROJ"}}

    def test_three_exists_blocks_pass_silently(self):
        bundle = self._build_uift_with_n_exists(3)
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertTrue(result["valid"], result)
        # No EXISTS-cap warning at n=3
        self.assertFalse(any(
            "EXISTS letter block" in w.get("reason", "")
            for w in result["warnings"]
        ))

    def test_four_exists_blocks_emit_warning(self):
        bundle = self._build_uift_with_n_exists(4)
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertTrue(result["valid"], result)
        warns = [w for w in result["warnings"]
                 if "EXISTS letter block" in w.get("reason", "")]
        self.assertEqual(len(warns), 1)
        self.assertIn("approaching", warns[0]["reason"].lower())

    def test_five_exists_blocks_emit_error(self):
        bundle = self._build_uift_with_n_exists(5)
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertFalse(result["valid"])
        errs = [e for e in result["errors"]
                if "EXISTS letter block" in e.get("reason", "")]
        self.assertEqual(len(errs), 1)
        self.assertIn("cap", errs[0]["reason"].lower())
        # Suggestions include the prompt-driven escape hatch
        all_suggestions = " ".join(errs[0].get("suggestions", []))
        self.assertIn("prompt", all_suggestions.lower())

    def test_six_exists_blocks_still_error_without_force(self):
        bundle = self._build_uift_with_n_exists(6)
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertFalse(result["valid"])
        errs = [e for e in result["errors"]
                if "EXISTS letter block" in e.get("reason", "")]
        self.assertEqual(len(errs), 1)

    def test_force_overrides_exists_cap_error(self):
        bundle = self._build_uift_with_n_exists(6)
        result = pre_flight_validator.validate(
            bundle, "host", cache=self.cache, force=True
        )
        # Error becomes warning; bundle is still considered valid as long as
        # no OTHER errors exist.
        errs = [e for e in result["errors"]
                if "EXISTS letter block" in e.get("reason", "")]
        self.assertEqual(len(errs), 0)
        warns = [w for w in result["warnings"]
                 if "EXISTS letter block" in w.get("reason", "")]
        self.assertEqual(len(warns), 1)
        self.assertIn("--force", warns[0]["reason"])


class JoinPathTest(unittest.TestCase):
    def setUp(self):
        self.cache = _StubCache({
            "proj": _load("proj"),
            "user": _load("user")
        })

    def test_one_hop_join_validates(self):
        bundle = {"uift": {"definition": {
            "owner:name": "Alice",
            "owner:name_Mod": "cicontains"
        }, "uiObjCode": "PROJ"},
            "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertTrue(result["valid"])


class UIVWColumnTest(unittest.TestCase):
    def setUp(self):
        self.cache = _StubCache({"proj": _load("proj")})

    def test_column_valuefield_validated(self):
        bundle = {"uivw": {"definition": {"column": [
            {"valuefield": "status", "valueformat": "val"},
            {"valuefield": "doesNotExist", "valueformat": "string"}
        ]}, "uiObjCode": "PROJ"},
            "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertFalse(result["valid"])
        self.assertTrue(any("doesNotExist" in e["path"] for e in result["errors"]))


class QuerysortGrammarTest(unittest.TestCase):
    def setUp(self):
        self.cache = _StubCache({
            "proj": _load("proj"),
            "user": _load("user"),
        })

    def test_querysort_with_join_path_passes(self):
        """`owner:name` querysort — `owner` is a relation on PROJ, `name` is a field on USER."""
        bundle = {"uivw": {"definition": {"column": [
            {"valuefield": "name", "querysort": "owner:name"}
        ]}, "uiObjCode": "PROJ"},
            "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertTrue(result["valid"], result)

    def test_querysort_with_misspelled_relation_fails_with_suggestions(self):
        """`ownr:name` — `ownr` is not a relation on PROJ; should error with `owner` suggested."""
        bundle = {"uivw": {"definition": {"column": [
            {"valuefield": "name", "querysort": "ownr:name"}
        ]}, "uiObjCode": "PROJ"},
            "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertFalse(result["valid"])
        suggestions = " ".join(
            " ".join(e.get("suggestions", [])) for e in result["errors"]
        )
        self.assertIn("owner", suggestions)
        self.assertTrue(any("querysort" in e["path"] for e in result["errors"]))


class CombinedPrefixDecompositionTest(unittest.TestCase):
    def setUp(self):
        self.cache = _StubCache({
            "proj": _load("proj"),
            "task": _load("task"),
        })

    def test_OR_plus_DE_records_parity_ref_with_outer_objcode(self):
        bundle = {"uift": {"definition": {
            "OR:1:DE:Project Tier": "Gold",
            "OR:1:DE:Project Tier_Mod": "eq",
        }, "uiObjCode": "PROJ"},
            "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        refs = result.get("de_refs", [])
        names = [r["name"] for r in refs]
        self.assertIn("Project Tier", names)
        # Resolution objCode for OR-prefixed DE: is the outer uiObjCode (OR inherits scope)
        proj_ref = next(r for r in refs if r["name"] == "Project Tier")
        self.assertEqual(proj_ref["uiObjCode"], "PROJ")

    def test_EXISTS_plus_DE_records_parity_ref_with_block_objcode(self):
        bundle = {"uift": {"definition": {
            "EXISTS:a:$$EXISTSMOD": "EXISTS",
            "EXISTS:a:$$OBJCODE": "TASK",
            "EXISTS:a:ID": "FIELD:taskID",
            "EXISTS:a:DE:Tier": "Gold",
            "EXISTS:a:DE:Tier_Mod": "eq",
        }, "uiObjCode": "PROJ"},
            "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        refs = result.get("de_refs", [])
        tier_refs = [r for r in refs if r["name"] == "Tier"]
        self.assertEqual(len(tier_refs), 1)
        # Resolution objCode for EXISTS-prefixed DE: is the block's $$OBJCODE
        self.assertEqual(tier_refs[0]["uiObjCode"], "TASK")


class ShapeContractTest(unittest.TestCase):
    def setUp(self):
        self.cache = _StubCache({"proj": _load("proj")})

    def test_empty_bundle_is_valid(self):
        result = pre_flight_validator.validate({"report": {"uiObjCode": "PROJ"}},
                                               "host", cache=self.cache)
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])

    def test_result_shape(self):
        result = pre_flight_validator.validate({"report": {"uiObjCode": "PROJ"}},
                                               "host", cache=self.cache)
        self.assertIn("valid", result)
        self.assertIn("errors", result)
        self.assertIn("warnings", result)


class NoMetadataCachedTest(unittest.TestCase):
    def test_missing_metadata_yields_warning_not_error(self):
        cache = _StubCache({})  # no metadata at all
        bundle = {"uift": {"definition": {"status": "CUR"},
                           "uiObjCode": "PROJ"},
                  "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=cache)
        # Should soft-fail: valid=True (or at least not raise), warning included
        self.assertTrue(len(result.get("warnings", [])) > 0)


class ForceFlagTest(unittest.TestCase):
    def setUp(self):
        self.cache = _StubCache({"proj": _load("proj")})

    def test_force_downgrades_errors_to_warnings(self):
        bundle = {"uift": {"definition": {"isTemplate": "false",
                                          "isTemplate_Mod": "eq"},
                           "uiObjCode": "PROJ"},
                  "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(
            bundle, "host", cache=self.cache, force=True
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])
        # All previous errors now appear as warnings with forced:true
        forced = [w for w in result["warnings"] if w.get("forced")]
        self.assertGreater(len(forced), 0)
        self.assertTrue(any("isTemplate" in w.get("path", "") for w in forced))

    def test_force_with_no_errors_is_noop_advisory(self):
        bundle = {"uift": {"definition": {"status": "CUR", "status_Mod": "in"},
                           "uiObjCode": "PROJ"},
                  "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(
            bundle, "host", cache=self.cache, force=True
        )
        self.assertTrue(result["valid"])
        self.assertTrue(any(
            "nothing to force" in (w.get("reason") or "").lower()
            for w in result["warnings"]
        ))


class PseudoFieldsAllowlistTest(unittest.TestCase):
    def setUp(self):
        self.cache = _StubCache({
            "optask": _load("optask") if (FIXTURES / "optask-metadata.json").exists() else {"fields": {"name": {}, "status": {}}, "references": {}, "collections": {}},
            "task": _load("task"),
            "proj": _load("proj"),
        })

    def test_OPTASK_statusEquatesWith_passes_in_uift(self):
        bundle = {"uift": {"definition": {
            "statusEquatesWith": "CPL",
            "statusEquatesWith_Mod": "eq",
        }, "uiObjCode": "OPTASK"},
            "report": {"uiObjCode": "OPTASK"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertTrue(result["valid"], result)

    def test_OPTASK_assignmentsListString_passes_in_uivw(self):
        bundle = {"uivw": {"definition": {"column": [
            {"valuefield": "assignmentsListString", "valueformat": "string"}
        ]}, "uiObjCode": "OPTASK"},
            "report": {"uiObjCode": "OPTASK"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertTrue(result["valid"], result)

    def test_TASK_assignmentsListString_passes_in_uivw(self):
        bundle = {"uivw": {"definition": {"column": [
            {"valuefield": "assignmentsListString", "valueformat": "string"}
        ]}, "uiObjCode": "TASK"},
            "report": {"uiObjCode": "TASK"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertTrue(result["valid"], result)

    def test_statusEquatesWith_in_uivw_slot_still_errors(self):
        """slot constraint: statusEquatesWith is allowlisted for uift, NOT for uivw."""
        bundle = {"uivw": {"definition": {"column": [
            {"valuefield": "statusEquatesWith", "valueformat": "val"}
        ]}, "uiObjCode": "OPTASK"},
            "report": {"uiObjCode": "OPTASK"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertFalse(result["valid"])


class DEParityCheckTest(unittest.TestCase):
    def setUp(self):
        self.cache = _StubCache({"proj": _load("proj")})

    def test_de_parity_with_api_key_all_present_passes(self):
        bundle = {"uift": {"definition": {
            "DE:Project Tier": "Gold",
            "DE:Project Tier_Mod": "eq",
        }, "uiObjCode": "PROJ"},
            "report": {"uiObjCode": "PROJ"}}
        # Stub: parameter search returns matching record
        def fake_fetch(host, names, api_key):
            return {"data": [{"name": "Project Tier", "ID": "abc", "parameterGroup": {"name": "Default"}}]}
        result = pre_flight_validator.validate(
            bundle, "host", cache=self.cache,
            api_key="fake-key", de_fetch=fake_fetch
        )
        self.assertTrue(result["valid"], result)

    def test_de_parity_with_api_key_missing_name_errors(self):
        bundle = {"uift": {"definition": {
            "DE:NotARealField": "x",
            "DE:NotARealField_Mod": "eq",
        }, "uiObjCode": "PROJ"},
            "report": {"uiObjCode": "PROJ"}}
        def fake_fetch(host, names, api_key):
            return {"data": []}
        result = pre_flight_validator.validate(
            bundle, "host", cache=self.cache,
            api_key="fake-key", de_fetch=fake_fetch
        )
        self.assertFalse(result["valid"])
        msgs = " ".join(e["reason"] for e in result["errors"])
        self.assertIn("NotARealField", msgs)

    def test_de_parity_without_api_key_soft_fails_to_warnings(self):
        bundle = {"uift": {"definition": {
            "DE:Project Tier": "Gold",
            "DE:Project Tier_Mod": "eq",
        }, "uiObjCode": "PROJ"},
            "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        # No api_key => soft-fail: a warning per DE: ref, no errors
        self.assertTrue(result["valid"])
        de_warnings = [
            w for w in result["warnings"]
            if "Project Tier" in (w.get("value") or "")
        ]
        self.assertEqual(len(de_warnings), 1)


class ValueExpressionBraceParseTest(unittest.TestCase):
    def setUp(self):
        self.cache = _StubCache({
            "proj": _load("proj"),
            "user": _load("user"),
        })

    def test_simple_brace_field_resolves(self):
        bundle = {"uivw": {"definition": {"column": [
            {"valueexpression": "CONCAT({name}, '-suffix')",
             "valueformat": "HTML", "textmode": "true"}
        ]}, "uiObjCode": "PROJ"},
            "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertTrue(result["valid"], result)

    def test_joined_brace_field_resolves(self):
        bundle = {"uivw": {"definition": {"column": [
            {"valueexpression": "CONCAT({owner}.{name}, '-x')",
             "valueformat": "HTML", "textmode": "true"}
        ]}, "uiObjCode": "PROJ"},
            "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertTrue(result["valid"], result)

    def test_unknown_brace_field_errors(self):
        bundle = {"uivw": {"definition": {"column": [
            {"valueexpression": "CONCAT({nonExistentField}, 'x')",
             "valueformat": "HTML", "textmode": "true"}
        ]}, "uiObjCode": "PROJ"},
            "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertFalse(result["valid"])
        self.assertTrue(any(
            "nonExistentField" in e.get("value", "") or
            "nonExistentField" in e.get("path", "")
            for e in result["errors"]
        ))


class CurlyQuoteLintTest(unittest.TestCase):
    """v0.16.1 — Detect Unicode curly quotes that silently break the
    text-mode parser. See knowledge/reports/05-gotchas.md #14."""

    def setUp(self):
        self.cache = _StubCache({
            "proj": _load("proj"),
            "user": _load("user"),
        })

    def _path_was_flagged(self, errors, path_substring):
        return any(
            path_substring in e.get("path", "")
            and "curly quote" in e.get("reason", "").lower()
            for e in errors
        )

    def test_straight_quotes_pass(self):
        bundle = {"uivw": {"definition": {"column": [
            {"valueexpression": "IF({percentComplete}=0,\"zero\",\"other\")",
             "valueformat": "HTML", "textmode": "true"}
        ]}, "uiObjCode": "PROJ"},
            "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertTrue(result["valid"], result)

    def test_curly_double_quotes_in_column_valueexpression_error(self):
        bundle = {"uivw": {"definition": {"column": [
            {"valueexpression": "IF({percentComplete}=0,“zero”,“other”)",
             "valueformat": "HTML", "textmode": "true"}
        ]}, "uiObjCode": "PROJ"},
            "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertFalse(result["valid"])
        self.assertTrue(self._path_was_flagged(
            result["errors"], "uivw.definition.column[0].valueexpression"
        ))

    def test_curly_single_quotes_in_column_valueexpression_error(self):
        bundle = {"uivw": {"definition": {"column": [
            {"valueexpression": "IF({owner}.{name}=‘Alex’,1,0)",
             "valueformat": "HTML", "textmode": "true"}
        ]}, "uiObjCode": "PROJ"},
            "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertFalse(result["valid"])
        self.assertTrue(self._path_was_flagged(
            result["errors"], "uivw.definition.column[0].valueexpression"
        ))

    def test_curly_quote_in_aggregator_valueexpression_error(self):
        """aggregator.valueexpression carries the same risk as the
        column-level valueexpression (mutually exclusive with
        aggregator.valuefield per 07-view-patterns.md)."""
        bundle = {"uivw": {"definition": {"column": [
            {"valuefield": "name",
             "aggregator": {
                 "valueexpression": "IF({status}=“CMP”,1,0)",
                 "valueformat": "doubleAsString",
             },
             "valueformat": "HTML", "textmode": "true"}
        ]}, "uiObjCode": "PROJ"},
            "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertFalse(result["valid"])
        self.assertTrue(self._path_was_flagged(
            result["errors"], "uivw.definition.column[0].aggregator.valueexpression"
        ))

    def test_curly_quote_in_group_valueexpression_error(self):
        bundle = {"uigb": {"definition": {"group": [
            {"valueexpression": "IF({owner}.{name}=‘Alex’,“mine”,“other”)",
             "textmode": "true"}
        ]}, "uiObjCode": "PROJ"},
            "uivw": {"definition": {"column": []}, "uiObjCode": "PROJ"},
            "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        self.assertFalse(result["valid"])
        self.assertTrue(self._path_was_flagged(
            result["errors"], "uigb.definition.group[0].valueexpression"
        ))

    def test_curly_quote_error_message_includes_sed_fix(self):
        bundle = {"uivw": {"definition": {"column": [
            {"valueexpression": "x “bad”",
             "valueformat": "HTML", "textmode": "true"}
        ]}, "uiObjCode": "PROJ"},
            "report": {"uiObjCode": "PROJ"}}
        result = pre_flight_validator.validate(bundle, "host", cache=self.cache)
        curly_errors = [
            e for e in result["errors"]
            if "curly quote" in e.get("reason", "").lower()
        ]
        self.assertEqual(len(curly_errors), 1)
        all_suggestions = " ".join(curly_errors[0].get("suggestions", []))
        self.assertIn("sed", all_suggestions.lower())
        self.assertIn("plain-text", all_suggestions.lower())


class PerTenantWhitelistTest(unittest.TestCase):
    def setUp(self):
        self.cache = _StubCache({"optask": {"fields": {"name": {}}, "references": {}, "collections": {}}})
        self.tmpdir = tempfile.mkdtemp(prefix="wf-whitelist-test-")

    def test_per_tenant_whitelist_unblocks_field(self):
        # Pre-load a whitelist file for 'host'
        from pre_flight_validator import _whitelist_path
        wl_path = _whitelist_path("host", cache_dir=self.tmpdir)
        wl = {
            "host": "host",
            "fields": [{
                "uiObjCode": "OPTASK",
                "fieldname": "customStateEquatesWith",
                "slots": ["uift.definition"],
                "learned_at": "2026-05-14T15:42:00Z",
                "learned_via": "manual",
            }]
        }
        Path(wl_path).write_text(json.dumps(wl))
        bundle = {"uift": {"definition": {
            "customStateEquatesWith": "X",
            "customStateEquatesWith_Mod": "eq",
        }, "uiObjCode": "OPTASK"},
            "report": {"uiObjCode": "OPTASK"}}
        result = pre_flight_validator.validate(
            bundle, "host", cache=self.cache,
            whitelist_dir=self.tmpdir
        )
        self.assertTrue(result["valid"], result)

    def test_per_tenant_beats_global(self):
        # `statusEquatesWith` is in global PSEUDO_FIELDS for OPTASK at slot
        # uift.definition. Add a per-tenant entry for a DIFFERENT slot to prove
        # we read per-tenant first (this exists for slot uivw.column.valuefield).
        from pre_flight_validator import _whitelist_path
        wl_path = _whitelist_path("host", cache_dir=self.tmpdir)
        wl = {
            "host": "host",
            "fields": [{
                "uiObjCode": "OPTASK",
                "fieldname": "statusEquatesWith",
                "slots": ["uivw.column.valuefield"],
                "learned_at": "2026-05-14T15:42:00Z",
                "learned_via": "manual",
            }]
        }
        Path(wl_path).write_text(json.dumps(wl))
        bundle = {"uivw": {"definition": {"column": [
            {"valuefield": "statusEquatesWith", "valueformat": "val"}
        ]}, "uiObjCode": "OPTASK"},
            "report": {"uiObjCode": "OPTASK"}}
        result = pre_flight_validator.validate(
            bundle, "host", cache=self.cache,
            whitelist_dir=self.tmpdir
        )
        self.assertTrue(result["valid"], result)

    def test_learn_from_blocked_writes_entries(self):
        from pre_flight_validator import learn_from_blocked
        # Synthesize a forced-output JSON
        forced_output = {
            "valid": True, "errors": [], "de_refs": [],
            "warnings": [{
                "forced": True,
                "path": "uift.definition.customField",
                "value": "customField",
                "reason": "OPTASK has no field 'customField'.",
            }]
        }
        out_path = Path(self.tmpdir) / "preflight-out.json"
        out_path.write_text(json.dumps(forced_output))
        added = learn_from_blocked(
            "host", "OPTASK", str(out_path), cache_dir=self.tmpdir
        )
        self.assertEqual(len(added), 1)
        from pre_flight_validator import _whitelist_path
        wl = json.loads(Path(_whitelist_path("host", cache_dir=self.tmpdir)).read_text())
        names = [f["fieldname"] for f in wl["fields"]]
        self.assertIn("customField", names)

    def test_forget_removes_entry(self):
        from pre_flight_validator import _whitelist_path, forget
        wl_path = _whitelist_path("host", cache_dir=self.tmpdir)
        Path(wl_path).write_text(json.dumps({
            "host": "host",
            "fields": [
                {"uiObjCode": "OPTASK", "fieldname": "a", "slots": ["uift.definition"]},
                {"uiObjCode": "OPTASK", "fieldname": "b", "slots": ["uift.definition"]},
            ]
        }))
        forget("host", "OPTASK", "a", cache_dir=self.tmpdir)
        wl = json.loads(Path(wl_path).read_text())
        names = [f["fieldname"] for f in wl["fields"]]
        self.assertNotIn("a", names)
        self.assertIn("b", names)

    def test_forget_all_wipes_tenant(self):
        from pre_flight_validator import _whitelist_path, forget_all
        wl_path = _whitelist_path("host", cache_dir=self.tmpdir)
        Path(wl_path).write_text(json.dumps({
            "host": "host",
            "fields": [{"uiObjCode": "OPTASK", "fieldname": "a", "slots": []}]
        }))
        forget_all("host", cache_dir=self.tmpdir)
        self.assertFalse(Path(wl_path).exists())


class CLIEnvCredentialsTest(unittest.TestCase):
    """--host / --api-key fall back to WF_HOST / WF_API_KEY env vars, so the
    key never has to appear in the process argv (toolkit credential rule)."""

    def _run_cli(self, argv, env):
        captured = {}

        def spy_validate(bundle, host, cache=None, force=False, api_key=None,
                         de_fetch=None, whitelist_dir=None):
            captured.update(host=host, api_key=api_key)
            return {"valid": True, "errors": [], "warnings": [], "de_refs": []}

        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ("WF_HOST", "WF_API_KEY")}
        clean_env.update(env)
        with patch.object(sys, "argv", ["pre_flight_validator.py"] + argv), \
             patch.dict(os.environ, clean_env, clear=True), \
             patch("sys.stdin", io.StringIO('{"report": {}}')), \
             patch.object(pre_flight_validator, "validate", spy_validate), \
             patch("sys.stdout", io.StringIO()):
            rc = pre_flight_validator._cli()
        return rc, captured

    def test_host_and_api_key_fall_back_to_env(self):
        rc, captured = self._run_cli(
            ["--from-stdin"],
            {"WF_HOST": "env.workfront.com", "WF_API_KEY": "env-key"})
        self.assertEqual(rc, 0)
        self.assertEqual(captured["host"], "env.workfront.com")
        self.assertEqual(captured["api_key"], "env-key")

    def test_flags_override_env(self):
        rc, captured = self._run_cli(
            ["--from-stdin", "--host", "flag.workfront.com",
             "--api-key", "flag-key"],
            {"WF_HOST": "env.workfront.com", "WF_API_KEY": "env-key"})
        self.assertEqual(rc, 0)
        self.assertEqual(captured["host"], "flag.workfront.com")
        self.assertEqual(captured["api_key"], "flag-key")

    def test_no_key_anywhere_passes_none(self):
        rc, captured = self._run_cli(
            ["--from-stdin"], {"WF_HOST": "env.workfront.com"})
        self.assertEqual(rc, 0)
        self.assertIsNone(captured["api_key"])

    def test_missing_host_everywhere_is_usage_error(self):
        with patch("sys.stderr", io.StringIO()):
            rc, _ = self._run_cli(["--from-stdin"], {})
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()

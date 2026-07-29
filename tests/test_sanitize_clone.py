"""Tests for skills/workfront-reports/scripts/sanitize_clone.py (v0.9.0).

The sanitizer walks JSON-object Workfront report payloads (NOT text-mode strings)
and produces 5 buckets: strip, prompt, parity_check, host_rewrite, cleaned.
"""

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "workfront-reports" / "scripts"))

import sanitize_clone  # noqa: E402


def _has(items, key_substr, value_substr=""):
    """True iff any item matches both substrings."""
    return any(
        key_substr in (i.get("key") or i.get("path") or i.get("field") or "")
        and value_substr in str(i.get("value") or i.get("url") or i.get("field") or "")
        for i in items
    )


class StripBucketTest(unittest.TestCase):
    def test_customerID_on_report_is_auto_stripped(self):
        payload = {"report": {"customerID": "src-xyz", "name": "X"}}
        result = sanitize_clone.sanitise(payload)
        self.assertTrue(_has(result["strip"], "report.customerID", "src-xyz"))
        self.assertNotIn("customerID", result["cleaned"]["report"])

    def test_preferenceID_is_auto_stripped(self):
        payload = {"report": {"preferenceID": "pref-xyz"}}
        result = sanitize_clone.sanitise(payload)
        self.assertTrue(_has(result["strip"], "report.preferenceID"))
        self.assertNotIn("preferenceID", result["cleaned"]["report"])

    def test_securityRootID_is_auto_stripped(self):
        payload = {"report": {"securityRootID": "sec-xyz"}}
        result = sanitize_clone.sanitise(payload)
        self.assertTrue(_has(result["strip"], "report.securityRootID"))


class PromptBucketTest(unittest.TestCase):
    def test_ownerID_is_prompted_not_stripped(self):
        payload = {"report": {"ownerID": "user-xyz"}}
        result = sanitize_clone.sanitise(payload)
        self.assertTrue(_has(result["prompt"], "report.ownerID"))
        self.assertEqual(result["cleaned"]["report"]["ownerID"], "user-xyz")

    def test_categoryID_is_prompted(self):
        payload = {"report": {"categoryID": "form-xyz"}}
        result = sanitize_clone.sanitise(payload)
        self.assertTrue(_has(result["prompt"], "report.categoryID"))

    def test_unknown_ID_field_is_prompted(self):
        payload = {"report": {"name": "X", "templateID": "tpl-xyz"}}
        result = sanitize_clone.sanitise(payload)
        self.assertTrue(_has(result["prompt"], "report.templateID"))


class FilterDefinitionWalkerTest(unittest.TestCase):
    def test_hardcoded_GUID_in_filter_value_is_prompted(self):
        payload = {"uift": {"definition": {
            "portfolioID": "4c78821c0000d6fa8d5e52f07a1d54d0",
            "portfolioID_Mod": "in"
        }}}
        result = sanitize_clone.sanitise(payload)
        self.assertTrue(any(
            "4c78821c0000d6fa8d5e52f07a1d54d0" in (i.get("value") or "")
            for i in result["prompt"]
        ))

    def test_hardcoded_date_is_prompted(self):
        payload = {"uift": {"definition": {
            "plannedCompletionDate": "2026-04-01",
            "plannedCompletionDate_Mod": "lt"
        }}}
        result = sanitize_clone.sanitise(payload)
        self.assertTrue(any(
            "2026-04-01" in (i.get("value") or "")
            for i in result["prompt"]
        ))

    def test_session_token_passes_through(self):
        payload = {"uift": {"definition": {
            "assignedToID": "$$USER.ID",
            "assignedToID_Mod": "eq",
            "lastUpdateDate": "$$TODAY-30d",
            "lastUpdateDate_Mod": "gte"
        }}}
        result = sanitize_clone.sanitise(payload)
        self.assertEqual(result["prompt"], [])
        # values pass through unchanged
        self.assertEqual(
            result["cleaned"]["uift"]["definition"]["assignedToID"],
            "$$USER.ID"
        )

    def test_DE_reference_in_filter_key_collected_for_parity_check(self):
        payload = {"uift": {"definition": {
            "DE:Project Tier": "Tier 1",
            "DE:Project Tier_Mod": "in"
        }, "uiObjCode": "PROJ"}}
        result = sanitize_clone.sanitise(payload)
        self.assertTrue(any(
            i.get("field") == "Project Tier" for i in result["parity_check"]
        ))

    def test_OR_group_key_unwraps_for_DE_parity(self):
        payload = {"uift": {"definition": {
            "OR:1:DE:Project Tier": "Tier 1",
            "OR:1:DE:Project Tier_Mod": "in"
        }, "uiObjCode": "PROJ"}}
        result = sanitize_clone.sanitise(payload)
        self.assertTrue(any(
            i.get("field") == "Project Tier" for i in result["parity_check"]
        ))

    def test_EXISTS_block_control_keys_pass_through(self):
        payload = {"uift": {"definition": {
            "EXISTS:a:$$EXISTSMOD": "EXISTS",
            "EXISTS:a:$$OBJCODE": "TASK",
            "EXISTS:a:ID": "FIELD:taskID",
            "EXISTS:a:assignedToID": "$$USER.ID"
        }, "uiObjCode": "DOCU"}}
        result = sanitize_clone.sanitise(payload)
        # control keys + session token: no prompts, no parity checks
        self.assertEqual(result["prompt"], [])
        self.assertEqual(result["parity_check"], [])


class ViewDefinitionWalkerTest(unittest.TestCase):
    def test_DE_reference_in_column_valuefield_collected(self):
        # NOTE: per the asymmetry, column.valuefield DROPS DE: prefix
        payload = {"uivw": {"definition": {"column": [
            {"valuefield": "Project Tier", "valueformat": "string"}
        ]}, "uiObjCode": "PROJ"}}
        result = sanitize_clone.sanitise(payload)
        # Bare custom-field name in valuefield is interpreted as DE: reference
        self.assertTrue(any(
            i.get("field") == "Project Tier" for i in result["parity_check"]
        ))

    def test_DE_reference_in_column_querysort_collected(self):
        payload = {"uivw": {"definition": {"column": [
            {"valuefield": "name", "querysort": "DE:Launch Date"}
        ]}, "uiObjCode": "PROJ"}}
        result = sanitize_clone.sanitise(payload)
        self.assertTrue(any(
            i.get("field") == "Launch Date" for i in result["parity_check"]
        ))

    def test_DE_reference_in_aggregator_valuefield_collected(self):
        payload = {"uivw": {"definition": {"column": [
            {"valuefield": "DE:Duration Delta 2",
             "aggregator": {"function": "AVG", "valuefield": "DE:Duration Delta 2",
                            "valueformat": "customNumberAsDouble"}}
        ]}, "uiObjCode": "PROJ"}}
        result = sanitize_clone.sanitise(payload)
        # DE: prefix kept here; one parity check for "Duration Delta 2"
        fields = [i.get("field") for i in result["parity_check"]]
        self.assertIn("Duration Delta 2", fields)

    def test_DE_parity_check_dedupes_across_locations(self):
        payload = {
            "uift": {"definition": {
                "DE:Tier": "X", "DE:Tier_Mod": "in"
            }},
            "uivw": {"definition": {"column": [
                {"valuefield": "Tier"},
                {"valuefield": "name", "querysort": "DE:Tier"}
            ]}, "uiObjCode": "PROJ"}
        }
        result = sanitize_clone.sanitise(payload)
        # All three locations reference "Tier" — should dedupe to one parity_check entry
        tier_entries = [i for i in result["parity_check"] if i.get("field") == "Tier"]
        self.assertEqual(len(tier_entries), 1)


class GroupDefinitionWalkerTest(unittest.TestCase):
    def test_DE_reference_in_group_valuefield_collected(self):
        # UIGB drops DE: prefix per the asymmetry; sanitizer must still flag
        payload = {"uigb": {"definition": {"group": [
            {"valuefield": "Asset Tag", "valueformat": "customDataLabelsAsString"}
        ]}, "uiObjCode": "PROJ"}}
        result = sanitize_clone.sanitise(payload)
        self.assertTrue(any(
            i.get("field") == "Asset Tag" for i in result["parity_check"]
        ))


class HostRewriteBucketTest(unittest.TestCase):
    def test_hardcoded_https_URL_in_valueexpression_flagged(self):
        payload = {"uivw": {"definition": {"column": [
            {"displayname": "Proof Link", "textmode": "true",
             "valueexpression": "CONCAT(\"<a href='https://acme.my.workfront.com/document/\",{ID},\"'>View</a>\")",
             "valueformat": "HTML"}
        ]}, "uiObjCode": "DOCU"}}
        result = sanitize_clone.sanitise(payload)
        self.assertTrue(any(
            "acme.my.workfront.com" in (i.get("url") or "")
            for i in result["host_rewrite"]
        ))

    def test_image_truetext_with_static_path_flagged(self):
        payload = {"uivw": {"definition": {"column": [
            {"valuefield": "DE:Detail",
             "image": {"case": [{"comparison": {
                 "truetext": "/static/img/r15/icons/casebuilder/light_purple.gif"
             }}]}}
        ]}, "uiObjCode": "PROJ"}}
        result = sanitize_clone.sanitise(payload)
        self.assertTrue(any(
            "/static/" in (i.get("url") or "")
            for i in result["host_rewrite"]
        ))


class ReportDescriptionDEScanTest(unittest.TestCase):
    def test_de_ref_in_description_produces_parity_entry(self):
        payload = {
            "report": {
                "uiObjCode": "PROJ",
                "name": "Quarterly view",
                "description": "Filter on DE:Region and DE:Quarter to drill down.",
            }
        }
        result = sanitize_clone.sanitise(payload)
        parity_names = [p["field"] for p in result["parity_check"]]
        self.assertIn("Region", parity_names)
        self.assertIn("Quarter", parity_names)

    def test_description_without_de_refs_adds_zero_entries(self):
        payload = {
            "report": {
                "uiObjCode": "PROJ",
                "name": "Quarterly view",
                "description": "Standard quarterly review by portfolio.",
            }
        }
        result = sanitize_clone.sanitise(payload)
        self.assertEqual(result["parity_check"], [])


class ShapeContractTest(unittest.TestCase):
    def test_result_has_five_buckets(self):
        result = sanitize_clone.sanitise({})
        self.assertEqual(
            set(result.keys()),
            {"strip", "prompt", "parity_check", "host_rewrite", "cleaned"}
        )

    def test_empty_payload_returns_empty_lists(self):
        result = sanitize_clone.sanitise({})
        for key in ("strip", "prompt", "parity_check", "host_rewrite"):
            self.assertEqual(result[key], [])
        self.assertEqual(result["cleaned"], {})

    def test_null_uift_handled(self):
        payload = {"report": {"name": "X"}, "uift": None}
        result = sanitize_clone.sanitise(payload)
        self.assertNotIn("uift", result["cleaned"])  # null UIFT not propagated

    def test_view_only_payload_has_no_filter_or_group(self):
        payload = {"uivw": {"definition": {"column": [
            {"valuefield": "name", "valueformat": "HTML"}
        ]}, "uiObjCode": "OPTASK"}}
        result = sanitize_clone.sanitise(payload)
        # Should not crash; cleaned only has uivw
        self.assertIn("uivw", result["cleaned"])


if __name__ == "__main__":
    unittest.main()

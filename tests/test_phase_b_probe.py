"""Unit tests for skills/workfront-custom-forms/scripts/phase_b_probe.py.

The probe script has two modes that drive live API calls (not unit-testable).
This test file covers the pure-logic parts: matrix builder, displayType
verdict decision, JSON output shape, name-prefix application.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "skills/workfront-custom-forms/scripts/phase_b_probe.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("phase_b_probe", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def pb():
    return _load_script_module()


# --- name-prefix application ---


def test_category_name_for_coverage_matrix(pb):
    name = pb.build_category_name(mode="coverage-matrix", objcode="PROJ", ts="20260522T120000Z")
    assert name == "[wf-api-verify] phase-b PROJ 20260522T120000Z"


def test_category_name_for_displaytype_discovery(pb):
    name = pb.build_category_name(mode="displaytype-discovery", objcode="PROJ", ts="20260522T120000Z")
    assert name == "[wf-phase-b-probe] PROJ 20260522T120000Z"


def test_parameter_name_for_coverage_matrix_uses_snake_case_prefix(pb):
    name = pb.build_parameter_name(
        mode="coverage-matrix", data_type="TEXT", display_type="SLCT", ts="20260522T120000Z"
    )
    assert name.startswith("wf_verify_phase_b_")
    assert "TEXT" in name and "SLCT" in name


def test_parameter_name_for_displaytype_discovery_uses_snake_case_prefix(pb):
    name = pb.build_parameter_name(
        mode="displaytype-discovery", data_type="TEXT", display_type="HIERARCHY", ts="20260522T120000Z"
    )
    assert name.startswith("wf_phase_b_probe_")
    assert "HIERARCHY" in name


# --- displayType decision logic ---


def test_displaytype_verdict_accepted(pb):
    result = {"http_status": 200, "response": {"data": {"ID": "abc"}}, "error": None}
    assert pb.decide_displaytype_verdict(result) == "accepted"


def test_displaytype_verdict_unknown_displaytype(pb):
    result = {
        "http_status": 400,
        "response": {"error": {"message": "Unknown display type HIERARCHY"}},
        "error": None,
    }
    assert pb.decide_displaytype_verdict(result) == "absent"


def test_displaytype_verdict_missing_required_field(pb):
    result = {
        "http_status": 400,
        "response": {"error": {"message": "Missing required field 'locationConfig'"}},
        "error": None,
    }
    assert pb.decide_displaytype_verdict(result) == "present-but-needs-config"


def test_displaytype_verdict_other_error(pb):
    result = {
        "http_status": 500,
        "response": {"error": {"message": "Internal server error"}},
        "error": None,
    }
    assert pb.decide_displaytype_verdict(result) == "inconclusive"


# --- coverage-matrix builder ---


def test_matrix_builder_renders_table(pb):
    probe_results = [
        {"objcode": "PROJ", "data_type": "TEXT", "display_type": "TEXT", "http_status": 200, "accepted": True, "error": None},
        {"objcode": "PROJ", "data_type": "TEXT", "display_type": "SLCT", "http_status": 200, "accepted": True, "error": None},
        {"objcode": "TASK", "data_type": "TEXT", "display_type": "TEXT", "http_status": 200, "accepted": True, "error": None},
        {"objcode": "TASK", "data_type": "TEXT", "display_type": "SLCT", "http_status": 400, "accepted": False,
         "error": "Display type SLCT not allowed on TASK"},
    ]
    matrix = pb.build_matrix(probe_results)
    assert matrix[("TEXT", "TEXT")] == {"PROJ": "✓", "TASK": "✓"}
    assert matrix[("TEXT", "SLCT")] == {"PROJ": "✓", "TASK": "✗"}


def test_matrix_builder_handles_missing_combos(pb):
    probe_results = [
        {"objcode": "PROJ", "data_type": "NMBR", "display_type": "TEXT", "http_status": 200, "accepted": True, "error": None},
    ]
    matrix = pb.build_matrix(probe_results, objcodes=["PROJ", "TASK"])
    assert matrix[("NMBR", "TEXT")] == {"PROJ": "✓", "TASK": "—"}


# --- JSON output shape ---


def test_output_json_shape(pb, tmp_path):
    probe_results = [
        {"objcode": "PROJ", "data_type": "TEXT", "display_type": "TEXT",
         "http_status": 200, "accepted": True, "error": None,
         "param_id": "abc123", "category_id": "cat456", "cleanup_done": False},
    ]
    out_path = tmp_path / "result.json"
    pb.write_output_json(
        mode="coverage-matrix",
        tenant="example.my.workfront.com",
        ts="20260522T120000Z",
        probe_results=probe_results,
        out_path=out_path,
    )
    parsed = json.loads(out_path.read_text())
    assert parsed["mode"] == "coverage-matrix"
    assert parsed["tenant"] == "example.my.workfront.com"
    assert parsed["captured_at"] == "20260522T120000Z"
    assert len(parsed["probes"]) == 1
    assert parsed["probes"][0]["objcode"] == "PROJ"

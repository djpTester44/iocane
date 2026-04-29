"""Critic calibration ship-gate audit for the N=5 wire-tests sample.

Loads N ``eval_*.yaml`` files per test-type from ``.iocane/wire-tests/``,
applies the 4-item calibration checklist (rubric-gaming, rubric blind-spot,
correlated convergence, actionable critique_notes), and emits structured
per-target rows with multi-signal calibration fields per Appendix C of the
breakout doc (D-22 derivability split: auto / partial / manual).

CLI::

    run_critic_audit.py --test-type cdt|ct
                        [--eval-dir .iocane/wire-tests/]
                        [--sample-size 5]
                        [--output-path plans/.../critic-audit-<type>-<date>.yaml]

Exit codes:
    0: audit emitted; all 4 checklist items passed.
    1: audit emitted; one or more checklist items failed.
    2: usage/IO error; no audit emitted.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_parser import load_eval_report
from schemas import EvalReport

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Axis constants
# ---------------------------------------------------------------------------

_CDT_AXIS_NAMES: frozenset[str] = frozenset(
    {
        "payload_shape_covered",
        "invariants_asserted",
        "collaborator_mocks_speced",
        "raises_coverage_complete",
    }
)
_CT_AXIS_NAMES: frozenset[str] = frozenset(
    {
        "seam_fan_coverage",
        "cdt_ct_mock_spec_consistent",
        "integration_path_asserted",
    }
)
_ALL_AXIS_NAMES: frozenset[str] = _CDT_AXIS_NAMES | _CT_AXIS_NAMES

# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


class RubricAxisAResults(BaseModel, frozen=True):
    """Rubric-gaming check: per-axis booleans extracted from the eval report.

    Derivability: partial (auto-populated from eval YAML; reasoning requires
    manual confirmation that test file assertions actually match the claimed
    boolean values).
    """

    # CDT axes
    payload_shape_covered: bool | None = None
    invariants_asserted: bool | None = None
    collaborator_mocks_speced: bool | None = None
    raises_coverage_complete: bool | None = None
    # CT axes
    seam_fan_coverage: bool | None = None
    cdt_ct_mock_spec_consistent: bool | None = None
    integration_path_asserted: bool | None = None


class RubricAxisBResults(BaseModel, frozen=True):
    """Rubric blind-spot check result.

    Derivability: manual. Operator sets blind_spot_identified=true when the
    rubric ratifies a contract dimension it does not explicitly ask about.
    Defaults to False (no blind spot detected until operator confirms).
    """

    blind_spot_identified: bool = False
    notes: str = ""


class RubricAxisCResults(BaseModel, frozen=True):
    """Correlated convergence check: other target IDs sharing the same axis fingerprint.

    Derivability: partial (fingerprint matching is auto; judgment on whether
    correlation indicates a rubric defect requires manual reasoning).
    """

    correlated_with: list[str] = Field(default_factory=list)


class RubricAxisDResults(BaseModel, frozen=True):
    """Actionable critique_notes check.

    Derivability: auto (derived from critique_notes field on FAIL/AMBIGUOUS
    verdicts; actionable iff notes mention a specific axis name).
    """

    actionable: bool
    notes: str = ""


class PerTargetRow(BaseModel, frozen=True):
    """Per-target calibration row with all D-22 multi-signal fields.

    Auto fields are populated by run_critic_audit.py without operator input.
    Partial fields are heuristically auto-populated and need manual confirmation.
    Manual fields default to sentinels; operator fills during human review.
    """

    # Base / auto
    target_id: str
    target_type: Literal["cdt", "ct"]
    final_status: Literal["PASS", "FAIL", "AMBIGUOUS"]
    attempt_count: int  # auto: spawn-log dir count (D-22, rev-4 re-grounding)
    archive_step_observed: bool  # auto: archive dir presence per attempt (D-18)
    rubric_axis_d_results: RubricAxisDResults  # auto: from critique_notes

    # Partial
    b_axis_catch_incidence: bool  # partial: heuristic + manual confirm (D-12)
    rubric_axis_a_results: RubricAxisAResults  # partial: per-axis booleans + reasoning
    rubric_axis_c_results: RubricAxisCResults  # partial: across-N reasoning

    # Manual (D-07 trampoline-gap extensions at audit tier; default to sentinels)
    rubric_axis_b_results: RubricAxisBResults = Field(
        default_factory=RubricAxisBResults
    )
    prose_revised_between_attempts: bool = False
    menu_efficacy_flag: Literal[
        "caught_at_specify",
        "caught_at_architect",
        "caught_at_meso",
        "not_applicable",
    ] = "not_applicable"
    roadmap_tier_defect_logged: bool = False
    auditor_notes: str = ""


class Checklist(BaseModel, frozen=True):
    """4-item calibration ship-gate checklist.

    Each item resolves to 'pass' or 'fail'. Exit code 1 if any item fails.
    rubric_blind_spot defaults to 'pass' on initial emit (manual field;
    operator flips to 'fail' if a blind spot is found during review).
    """

    rubric_gaming: Literal["pass", "fail"]
    rubric_blind_spot: Literal["pass", "fail"]
    correlated_convergence: Literal["pass", "fail"]
    actionable_critique_notes: Literal["pass", "fail"]


class AuditReport(BaseModel, frozen=True):
    """Top-level calibration audit report."""

    test_type: Literal["cdt", "ct"]
    audit_date: str
    session_id: str
    sample_size: int
    checklist: Checklist
    per_target: list[PerTargetRow]


# ---------------------------------------------------------------------------
# Auto-derivable field helpers
# ---------------------------------------------------------------------------


def compute_attempt_count(target_id: str, eval_dir: Path, session_id: str) -> int:
    """Count Author-side spawn-log files to derive attempt count.

    Args:
        target_id: Target component/seam identifier.
        eval_dir: Base wire-tests directory (e.g. .iocane/wire-tests/).
        session_id: Orchestrator run SID; scopes the spawn-log subdir.

    Returns:
        Number of Author attempts logged. 0 if per-sid spawn-log dir absent.

    Per D-22 rev-4: grounded on Author spawn-log file count, not eval YAML
    history (Critic overwrites a single eval_<target>.yaml per spawn) and not
    archive count (D-18 archives only on FAIL, undercounting AMBIGUOUS runs).
    Per F3 Phase 4 hardening: scoped to per-sid spawn-log subdir to prevent
    cross-run history bleed in calibration.
    """
    sid_spawn_dir = eval_dir / "spawn-log" / session_id
    if not sid_spawn_dir.is_dir():
        return 0
    return len(list(sid_spawn_dir.glob(f"{target_id}-author-*.json")))


def compute_archive_step_observed(
    target_id: str,
    eval_dir: Path,
    session_id: str,
    attempt_count: int,
) -> bool:
    """Check whether the D-18 archive fence held for every retry.

    Args:
        target_id: Target component/seam identifier.
        eval_dir: Base wire-tests directory.
        session_id: Orchestrator run SID; scopes the archive subdir.
        attempt_count: Number of Author attempts (from spawn-log count).

    Returns:
        True iff the per-sid archive directory contains exactly
        ``attempt_count - 1`` archived test files (one per FAIL retry).
        When attempt_count == 1 this is vacuously True: no retries occurred,
        so no archives are expected, and the D-18 fence had nothing to verify.
        Per F3 Phase 4 hardening: scoped to per-sid archive subdir to prevent
        cross-run history bleed in calibration.
    """
    expected = max(0, attempt_count - 1)
    sid_archive_dir = eval_dir / "archive" / session_id
    if not sid_archive_dir.is_dir():
        return expected == 0
    found = len(list(sid_archive_dir.glob(f"test_{target_id}-attempt-*.py")))
    return found == expected


def compute_axis_d_results(report: EvalReport) -> RubricAxisDResults:
    """Derive actionable-critique_notes result from the eval report.

    Args:
        report: Validated EvalReport for this target.

    Returns:
        RubricAxisDResults with actionable=True iff the report is PASS OR
        its critique_notes mentions at least one recognized axis name.
    """
    if report.status == "PASS":
        return RubricAxisDResults(actionable=True, notes="")
    notes = report.critique_notes
    actionable = any(axis in notes for axis in _ALL_AXIS_NAMES)
    return RubricAxisDResults(actionable=actionable, notes=notes)


def compute_b_axis_catch_incidence(report: EvalReport, eval_dir: Path) -> bool:
    """Heuristic: did the (b)-axis defect class fire for this target?

    Returns True when raises_coverage_complete is False AND the current test
    file contains a hardcoded numeric literal inside a raise expression
    (``raise SomeType(<number>)``), suggesting the impl uses a literal
    divergent from a Settings-derived constant.

    Derivability: partial per D-22. Auto-flag from heuristic grep; residual
    manual confirmation required per D-12 Appendix A.10 evidence trigger.

    Args:
        report: Validated EvalReport for this target.
        eval_dir: Base wire-tests directory.
    """
    if report.target_type != "cdt":
        return False
    if report.raises_coverage_complete is not False:
        return False
    test_file = eval_dir / f"test_{report.target_id}.py"
    if not test_file.exists():
        return False
    content = test_file.read_text(encoding="utf-8")
    return bool(re.search(r"raise\s+\w+\s*\(\s*[0-9]", content))


def _axis_fingerprint(report: EvalReport) -> frozenset[tuple[str, bool | None]]:
    """Build a hashable fingerprint of applicable axis booleans."""
    if report.target_type == "cdt":
        return frozenset(
            {
                ("payload_shape_covered", report.payload_shape_covered),
                ("invariants_asserted", report.invariants_asserted),
                ("collaborator_mocks_speced", report.collaborator_mocks_speced),
                ("raises_coverage_complete", report.raises_coverage_complete),
            }
        )
    return frozenset(
        {
            ("seam_fan_coverage", report.seam_fan_coverage),
            ("cdt_ct_mock_spec_consistent", report.cdt_ct_mock_spec_consistent),
            ("integration_path_asserted", report.integration_path_asserted),
        }
    )


def _build_axis_a_results(report: EvalReport) -> RubricAxisAResults:
    """Extract per-axis booleans from the eval report."""
    if report.target_type == "cdt":
        return RubricAxisAResults(
            payload_shape_covered=report.payload_shape_covered,
            invariants_asserted=report.invariants_asserted,
            collaborator_mocks_speced=report.collaborator_mocks_speced,
            raises_coverage_complete=report.raises_coverage_complete,
        )
    return RubricAxisAResults(
        seam_fan_coverage=report.seam_fan_coverage,
        cdt_ct_mock_spec_consistent=report.cdt_ct_mock_spec_consistent,
        integration_path_asserted=report.integration_path_asserted,
    )


# ---------------------------------------------------------------------------
# Checklist computation
# ---------------------------------------------------------------------------


def _check_rubric_gaming(reports: list[EvalReport], eval_dir: Path) -> Literal["pass", "fail"]:
    """Cross-reference axis booleans vs test file assertion patterns.

    Args:
        reports: Sampled EvalReport list.
        eval_dir: Base wire-tests directory.

    Returns:
        'fail' if any True axis lacks a corresponding test file pattern;
        'pass' if all checked axes have supporting patterns or test files
        are absent (absence logged as warning; checklist not failed on
        missing files alone).
    """
    for report in reports:
        test_file = eval_dir / f"test_{report.target_id}.py"
        if not test_file.exists():
            log.warning("test file missing for %s; skipping rubric-gaming check", report.target_id)
            continue
        content = test_file.read_text(encoding="utf-8")
        if report.raises_coverage_complete is True and not re.search(r"pytest\.raises\(", content):
            return "fail"
        if report.collaborator_mocks_speced is True and not re.search(r"(?:Mock|MagicMock|patch)\s*\(", content):
            return "fail"
    return "pass"


def _check_correlated_convergence(
    reports: list[EvalReport],
) -> Literal["pass", "fail"]:
    """Fail if all N reports share the same axis boolean fingerprint.

    Args:
        reports: Sampled EvalReport list.

    Returns:
        'fail' if every report has an identical axis fingerprint (all wrong
        in the same way); 'pass' if any diversity exists.
    """
    if len(reports) < 2:
        return "pass"
    fingerprints = {_axis_fingerprint(r) for r in reports}
    return "fail" if len(fingerprints) == 1 else "pass"


def _check_actionable_critique_notes(rows: list[PerTargetRow]) -> Literal["pass", "fail"]:
    """Fail if any FAIL/AMBIGUOUS verdict has non-actionable critique_notes.

    Args:
        rows: Built per-target rows.

    Returns:
        'fail' if any row with a non-PASS final_status has
        rubric_axis_d_results.actionable == False.
    """
    for row in rows:
        if row.final_status != "PASS" and not row.rubric_axis_d_results.actionable:
            return "fail"
    return "pass"


# ---------------------------------------------------------------------------
# Core audit function
# ---------------------------------------------------------------------------


def run_audit(
    test_type: Literal["cdt", "ct"],
    eval_dir: Path,
    session_id: str,
    sample_size: int,
    output_path: Path,
) -> tuple[AuditReport, int]:
    """Execute the calibration audit and write the audit YAML.

    Args:
        test_type: Target type filter ('cdt' or 'ct').
        eval_dir: Directory containing eval_*.yaml files and subdirs
            spawn-log/, archive/.
        session_id: Orchestrator run SID; scopes spawn-log and archive subdirs.
        sample_size: Maximum number of targets to include in the sample.
        output_path: Destination YAML path; parent dirs are created.

    Returns:
        Tuple of (AuditReport, exit_code). exit_code is 0 on all-pass,
        1 on any checklist failure, 2 on IO/usage error (raises on 2).

    Raises:
        FileNotFoundError: when eval_dir does not exist.
        ValueError: when fewer than 1 valid eval YAML is found.
    """
    if not eval_dir.is_dir():
        raise FileNotFoundError(f"eval-dir not found: {eval_dir}")

    eval_files = sorted(eval_dir.glob("eval_*.yaml"))
    reports: list[EvalReport] = []
    for f in eval_files:
        try:
            r = load_eval_report(str(f))
        except Exception as exc:
            log.warning("skipping %s: %s", f.name, exc)
            continue
        if r.target_type == test_type:
            reports.append(r)
        if len(reports) >= sample_size:
            break

    if not reports:
        raise ValueError(f"no valid eval_{test_type}_*.yaml files found in {eval_dir}")

    # Precompute fingerprints for correlated_with pass
    fingerprints = {r.target_id: _axis_fingerprint(r) for r in reports}

    rows: list[PerTargetRow] = []
    for report in reports:
        target_id = report.target_id
        attempt_count = compute_attempt_count(target_id, eval_dir, session_id)
        archive_ok = compute_archive_step_observed(target_id, eval_dir, session_id, attempt_count)

        correlated_with = [
            other_id
            for other_id, fp in fingerprints.items()
            if other_id != target_id and fp == fingerprints[target_id]
        ]

        rows.append(
            PerTargetRow(
                target_id=target_id,
                target_type=report.target_type,
                final_status=report.status,
                attempt_count=attempt_count,
                archive_step_observed=archive_ok,
                rubric_axis_d_results=compute_axis_d_results(report),
                b_axis_catch_incidence=compute_b_axis_catch_incidence(report, eval_dir),
                rubric_axis_a_results=_build_axis_a_results(report),
                rubric_axis_c_results=RubricAxisCResults(correlated_with=correlated_with),
            )
        )

    checklist = Checklist(
        rubric_gaming=_check_rubric_gaming(reports, eval_dir),
        rubric_blind_spot="pass",  # manual: operator flips to 'fail' on blind-spot discovery
        correlated_convergence=_check_correlated_convergence(reports),
        actionable_critique_notes=_check_actionable_critique_notes(rows),
    )

    audit = AuditReport(
        test_type=test_type,
        audit_date=date.today().isoformat(),
        session_id=session_id,
        sample_size=len(rows),
        checklist=checklist,
        per_target=rows,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = audit.model_dump(mode="json", exclude_none=True)
    output_path.write_text(
        yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )

    checklist_values = [
        checklist.rubric_gaming,
        checklist.rubric_blind_spot,
        checklist.correlated_convergence,
        checklist.actionable_critique_notes,
    ]
    exit_code = 1 if any(v == "fail" for v in checklist_values) else 0
    return audit, exit_code


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _default_output_path(test_type: str) -> str:
    return (
        f"plans/v5-meso-pivot/audit/04-phase-4-wire-tests/"
        f"critic-audit-{test_type}-{date.today().isoformat()}.yaml"
    )


def main() -> int:
    """CLI entry point for run_critic_audit.py.

    Returns:
        Exit code: 0 (all pass), 1 (checklist failure), 2 (usage/IO error).
    """
    parser = argparse.ArgumentParser(
        description="Critic calibration ship-gate audit (N=5 wire-tests sample).",
    )
    parser.add_argument(
        "--test-type",
        required=True,
        choices=["cdt", "ct"],
        help="Target type to audit.",
    )
    parser.add_argument(
        "--session-id",
        required=True,
        help="Orchestrator run SID; scopes spawn-log and archive subdirs.",
    )
    parser.add_argument(
        "--eval-dir",
        default=".iocane/wire-tests/",
        help="Directory containing eval_*.yaml and spawn-log/, archive/ subdirs.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=5,
        help="Maximum number of targets to include in the sample.",
    )
    parser.add_argument(
        "--output-path",
        default=None,
        help="Destination YAML path. Defaults to plans/.../critic-audit-<type>-<date>.yaml.",
    )

    args = parser.parse_args()
    output = args.output_path or _default_output_path(args.test_type)

    try:
        _, exit_code = run_audit(
            test_type=args.test_type,
            eval_dir=Path(args.eval_dir),
            session_id=args.session_id,
            sample_size=args.sample_size,
            output_path=Path(output),
        )
    except FileNotFoundError as exc:
        log.error("IO error: %s", exc)
        return 2
    except ValueError as exc:
        log.error("usage error: %s", exc)
        return 2

    return exit_code


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())

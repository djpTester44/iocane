"""Parse and serialize wire-tests Critic eval reports.

YAML-based EvalReport I/O with Pydantic validation. Read by
``run_actor_critic_loop.sh`` (status branching), ``spawn-test-author.sh``
(retry --prior-eval-path consumption), and ``run_critic_audit.py``
(N=5 calibration ship-gate). Malformed eval YAMLs (FAIL/AMBIGUOUS with
empty critique_notes; non-applicable target_type axes set) raise
``pydantic.ValidationError`` -- caught by orchestrator and counted as
malformed verdict against MAX_TURNS.
"""

from pathlib import Path

import yaml
from schemas import EvalReport


def load_eval_report(path: str) -> EvalReport:
    """Load and validate a Critic-authored eval YAML.

    Args:
        path: filesystem path to .iocane/wire-tests/eval_<target_id>.yaml.

    Returns:
        Validated EvalReport instance.

    Raises:
        pydantic.ValidationError: on cross-field validator failures
            (FAIL with empty critique_notes; AMBIGUOUS with empty
            critique_notes; PASS with axis boolean false; non-applicable
            target_type axes set).
        yaml.YAMLError: on malformed YAML.
        FileNotFoundError: when path does not exist.
    """
    text = Path(path).read_text(encoding="utf-8")
    raw = yaml.safe_load(text)
    if raw is None:
        raise ValueError(f"empty eval report at {path}")
    return EvalReport.model_validate(raw)


def save_eval_report(path: str, report: EvalReport) -> None:
    """Serialize EvalReport to YAML and write to disk.

    Uses ``exclude_none=True`` so non-applicable axes (e.g., CT axes on
    a CDT report) are omitted from the YAML output.
    """
    data = report.model_dump(mode="json", exclude_none=True)
    Path(path).write_text(
        yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )

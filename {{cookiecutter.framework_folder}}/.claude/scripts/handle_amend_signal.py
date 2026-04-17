"""Sole owner of the AMEND attempt sidecar.

The Test Author emits ``.iocane/amend-signals/<stem>.yaml`` when a
Protocol is under-specified for a test-plan invariant. The architect's
AMEND sub-loop consumes those signals and amends the canonical
artifacts. This script is the ONLY writer of the retry counter at
``.iocane/amend-attempts.<stem>`` -- the counter is separated from the
signal YAML so architect cleanup (``rm -rf .iocane/amend-signals/``)
does not reset the retry budget.

CLI:

- ``--list``: enumerate current signals + per-stem counter values
- ``--consume <stem>``: load signal, increment sidecar, rewrite YAML
  with the new ``attempt`` field; exit 2 if new counter exceeds cap
- ``--clear <stem>``: delete sidecar (orchestrator calls this after
  the tester re-runs cleanly)
- ``--reset-all``: delete every ``amend-attempts.*`` sidecar (manual
  debug use only)

Config source: ``architect.amend_retries`` in
``.claude/iocane.config.yaml``. In-code default ``2`` when the key is
absent -- surfaced as a warning on stderr, not a crash.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from schemas import AmendSignalFile

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SIGNALS_DIR = Path(".iocane/amend-signals")
IOCANE_DIR = Path(".iocane")
CONFIG_FILE = Path(".claude/iocane.config.yaml")

DEFAULT_AMEND_RETRIES = 2


# ---------------------------------------------------------------------------
# Stem <-> path helpers
# ---------------------------------------------------------------------------


def stem_from_protocol(protocol: str) -> str:
    """Derive bare stem from the schema-validated ``.pyi`` path.

    ``"interfaces/icache.pyi"`` -> ``"icache"``. The tester writes the
    full path into the signal YAML (schema requires it); the counter
    filename uses the stem (slashes would create nested directories).
    """
    return Path(protocol).stem


def counter_path(stem: str) -> Path:
    """Sidecar path for one Protocol's retry counter."""
    return IOCANE_DIR / f"amend-attempts.{stem}"


def signal_path(stem: str) -> Path:
    """Signal YAML path for one Protocol."""
    return SIGNALS_DIR / f"{stem}.yaml"


# ---------------------------------------------------------------------------
# Counter I/O (sole writer is this module)
# ---------------------------------------------------------------------------


def read_counter(stem: str) -> int:
    """Read current attempt count; 0 if sidecar absent."""
    p = counter_path(stem)
    if not p.exists():
        return 0
    return int(p.read_text(encoding="utf-8").strip())


def write_counter(stem: str, val: int) -> None:
    """Write attempt count to the sidecar (creates parent dir)."""
    IOCANE_DIR.mkdir(exist_ok=True)
    counter_path(stem).write_text(str(val), encoding="utf-8")


def delete_counter(stem: str) -> bool:
    """Delete the sidecar. Returns True if it existed."""
    p = counter_path(stem)
    if p.exists():
        p.unlink()
        return True
    return False


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def read_amend_retries() -> int:
    """Read ``architect.amend_retries`` from iocane.config.yaml.

    Returns the in-code default ``2`` when the file or key is absent,
    surfacing the fallback via stderr so it is visible to operators
    without crashing.
    """
    if not CONFIG_FILE.exists():
        print(
            f"handle_amend_signal: WARN: {CONFIG_FILE} not found; "
            f"using default amend_retries={DEFAULT_AMEND_RETRIES}",
            file=sys.stderr,
        )
        return DEFAULT_AMEND_RETRIES

    try:
        raw = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        print(
            f"handle_amend_signal: WARN: could not parse {CONFIG_FILE}: {exc}; "
            f"using default amend_retries={DEFAULT_AMEND_RETRIES}",
            file=sys.stderr,
        )
        return DEFAULT_AMEND_RETRIES

    architect = raw.get("architect") or {}
    val = architect.get("amend_retries")
    if val is None:
        print(
            f"handle_amend_signal: WARN: architect.amend_retries not set in "
            f"{CONFIG_FILE}; using default amend_retries={DEFAULT_AMEND_RETRIES}",
            file=sys.stderr,
        )
        return DEFAULT_AMEND_RETRIES
    # Bounds check: non-integer, zero, or negative values break the
    # escalation semantics. int(True) == 1 and int(False) == 0, so
    # explicitly reject bools before the numeric coercion.
    if isinstance(val, bool):
        print(
            f"handle_amend_signal: WARN: architect.amend_retries={val!r} "
            f"is a bool; using default amend_retries={DEFAULT_AMEND_RETRIES}",
            file=sys.stderr,
        )
        return DEFAULT_AMEND_RETRIES
    try:
        result = int(val)
    except (TypeError, ValueError):
        print(
            f"handle_amend_signal: WARN: architect.amend_retries={val!r} "
            f"not int-convertible; using default "
            f"amend_retries={DEFAULT_AMEND_RETRIES}",
            file=sys.stderr,
        )
        return DEFAULT_AMEND_RETRIES
    if result < 1:
        print(
            f"handle_amend_signal: WARN: architect.amend_retries={result} "
            f"< 1 (would fire DESIGN on first consume); using default "
            f"amend_retries={DEFAULT_AMEND_RETRIES}",
            file=sys.stderr,
        )
        return DEFAULT_AMEND_RETRIES
    return result


# ---------------------------------------------------------------------------
# Signal I/O (read + rewrite to match counter)
# ---------------------------------------------------------------------------


def load_signal(stem: str) -> AmendSignalFile:
    """Load + validate a signal YAML via the Pydantic schema."""
    p = signal_path(stem)
    if not p.exists():
        msg = f"handle_amend_signal: signal not found: {p}"
        raise FileNotFoundError(msg)
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if raw is None:
        msg = f"handle_amend_signal: signal parsed as None: {p}"
        raise ValueError(msg)
    return AmendSignalFile.model_validate(raw)


def save_signal(stem: str, signal: AmendSignalFile) -> None:
    """Serialize and write the signal YAML."""
    data = signal.model_dump(mode="json")
    output = yaml.dump(
        data, default_flow_style=False, sort_keys=False, allow_unicode=True
    )
    signal_path(stem).write_text(output, encoding="utf-8")


def rewrite_attempt(stem: str, new_attempt: int) -> AmendSignalFile:
    """Rewrite the signal YAML with an updated ``attempt`` field.

    AmendSignalFile is ``frozen=True``; use ``model_copy(update=...)``
    to build the new instance. The rewrite is idempotent -- calling
    this twice with the same attempt value yields the same file.
    """
    original = load_signal(stem)
    updated = original.model_copy(update={"attempt": new_attempt})
    save_signal(stem, updated)
    return updated


# ---------------------------------------------------------------------------
# DESIGN escalation (cap exceeded)
# ---------------------------------------------------------------------------


def write_design_escalation(
    stem: str, signal: AmendSignalFile, new_attempt: int, cap: int
) -> None:
    """Append a DESIGN backlog entry when the retry cap is exceeded.

    The Protocol is genuinely under-specified -- no amount of
    architect self-amendment has converged. Surface to human review.
    """
    backlog = Path("plans/backlog.yaml")
    gap_lines = []
    for s in signal.signals:
        gap_lines.append(
            f"    - method={s.method} invariant={s.invariant_id} "
            f"kind={s.kind.value}: {s.description}"
        )
    gaps_block = "\n".join(gap_lines) if gap_lines else "    (no signals)"

    entry = (
        f"- tag: DESIGN\n"
        f"  status: open\n"
        f"  source: handle_amend_signal.py --consume {stem}\n"
        f"  severity: HIGH\n"
        f"  files:\n"
        f"    - {signal.protocol}\n"
        f"  detail: |\n"
        f"    AMEND retry cap exceeded for Protocol {stem} "
        f"(attempt {new_attempt} > cap {cap}).\n"
        f"    Protocol is under-specified and architect self-amendment "
        f"has not converged.\n"
        f"    Human design input required. Gaps:\n"
        f"{gaps_block}\n"
    )

    if backlog.exists():
        existing = backlog.read_text(encoding="utf-8")
        if not existing.endswith("\n"):
            existing += "\n"
        backlog.write_text(existing + entry, encoding="utf-8")
    else:
        backlog.parent.mkdir(parents=True, exist_ok=True)
        backlog.write_text(f"items:\n{entry}", encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI handlers
# ---------------------------------------------------------------------------


def cmd_list() -> int:
    """Enumerate current signals and their counters."""
    if not SIGNALS_DIR.exists():
        print("handle_amend_signal: no amend signals present.")
        return 0

    signals = sorted(SIGNALS_DIR.glob("*.yaml"))
    if not signals:
        print("handle_amend_signal: no amend signals present.")
        return 0

    cap = read_amend_retries()
    print(f"AMEND signals present ({len(signals)}); retry cap = {cap}")
    for sig_file in signals:
        stem = sig_file.stem
        counter = read_counter(stem)
        print(f"  {stem}: counter={counter} signal={sig_file}")
    return 0


def cmd_consume(stem: str) -> int:
    """Increment the counter and rewrite the signal YAML.

    Returns 0 on normal increment, 2 when the new counter exceeds the
    configured cap (DESIGN escalation).
    """
    cap = read_amend_retries()

    # Validate the signal up front -- malformed YAML means we should
    # not touch the counter.
    signal = load_signal(stem)

    current = read_counter(stem)
    new_attempt = current + 1
    write_counter(stem, new_attempt)

    # Rewrite the YAML to surface current attempt count to humans.
    rewrite_attempt(stem, new_attempt)

    if new_attempt > cap:
        write_design_escalation(stem, signal, new_attempt, cap)
        print(
            f"handle_amend_signal: {stem} attempt={new_attempt} > "
            f"cap={cap} -- DESIGN escalation written to plans/backlog.yaml",
            file=sys.stderr,
        )
        return 2

    print(
        f"handle_amend_signal: {stem} attempt={new_attempt}/{cap}",
        file=sys.stderr,
    )
    return 0


def cmd_clear(stem: str) -> int:
    """Delete the counter sidecar for one stem."""
    existed = delete_counter(stem)
    if existed:
        print(
            f"handle_amend_signal: cleared counter for {stem}",
            file=sys.stderr,
        )
    else:
        print(
            f"handle_amend_signal: no counter to clear for {stem}",
            file=sys.stderr,
        )
    return 0


def cmd_reset_all() -> int:
    """Delete every amend-attempts.* sidecar."""
    if not IOCANE_DIR.exists():
        return 0
    removed = 0
    for p in IOCANE_DIR.glob("amend-attempts.*"):
        p.unlink()
        removed += 1
    print(
        f"handle_amend_signal: reset-all removed {removed} counter(s)",
        file=sys.stderr,
    )
    return 0


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Sole owner of the AMEND attempt sidecar.",
    )
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--list",
        action="store_true",
        help="enumerate current signals and counters (read-only)",
    )
    mode.add_argument(
        "--consume",
        metavar="STEM",
        help="increment the counter for STEM and rewrite its signal YAML",
    )
    mode.add_argument(
        "--clear",
        metavar="STEM",
        help="delete the counter sidecar for STEM",
    )
    mode.add_argument(
        "--reset-all",
        action="store_true",
        help="delete every amend-attempts.* sidecar",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        return cmd_list()
    if args.consume:
        return cmd_consume(args.consume)
    if args.clear:
        return cmd_clear(args.clear)
    if args.reset_all:
        return cmd_reset_all()
    return 1


if __name__ == "__main__":
    sys.exit(main())

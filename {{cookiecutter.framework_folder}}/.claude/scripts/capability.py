#!/usr/bin/env python3
"""Capability state writer for the Iocane harness.

Sole writer for workflow capability state. All mutations (grant, revoke,
session lifecycle, orphan sweep, legacy migration) flow through this
script. Hooks read only the flat-text hot-path cache that this script
maintains atomically.

Capability state layout (all under <repo_root>/.iocane/sessions/):
  manifest.yaml                   -- LRU last-50 session metadata (YAML)
  .current-session-id             -- main-session id, for subagent env-export
  <session_id>.jsonl              -- per-session grant/revoke event log
  <session_id>.active.txt         -- hot-path cache (bash-grep friendly)
  archive/YYYY-MM/                -- archived event logs + frozen manifest snaps

Environment access policy: this script never reads env vars directly --
callers (hook shell scripts, workflow commands) resolve the environment
and pass relevant values via CLI flags (--repo-root, --cp-id,
--parent-session-id, --subagent). Keeps the script entrypoint-clean per
environ-gate.

Subcommands:
  grant        --template NAME [--session-id SID] [--cp-id X] [--subagent] [--parent-session-id X]
  revoke       --template NAME [--session-id SID]
  list-active  [--session-id SID] [--json]
  session-start [--session-id SID] [--source SRC] [--context TEXT] [--subagent] [--parent-session-id X] [--cp-id X]
  session-end  [--session-id SID]
  sweep-orphans
  migrate-legacy

Every subcommand accepts --repo-root PATH. If omitted, falls back to
`git rev-parse --show-toplevel` and then cwd.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import json
import os
import pathlib
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from typing import Any

import yaml

AUTHOR_TAG = "capability.py@v1.0.0"
DEFAULT_TTL_SECONDS = 3600
TTL_HARD_CEILING_SECONDS = 86400
LOCK_TIMEOUT_SECONDS = 10.0
LOCK_POLL_INTERVAL = 0.05
MANIFEST_MAX_ENTRIES = 50


def resolve_repo_root(explicit: str | None) -> pathlib.Path:
    """Resolve the canonical repo root.

    Precedence: --repo-root flag, then `git rev-parse --show-toplevel`,
    then cwd. Callers pass IOCANE_REPO_ROOT env var in via --repo-root.
    """
    if explicit:
        return pathlib.Path(explicit).resolve()
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if out:
            return pathlib.Path(out).resolve()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return pathlib.Path.cwd().resolve()


def sessions_dir(root: pathlib.Path) -> pathlib.Path:
    return root / ".iocane" / "sessions"


def manifest_path(root: pathlib.Path) -> pathlib.Path:
    return sessions_dir(root) / "manifest.yaml"


def current_session_id_path(root: pathlib.Path) -> pathlib.Path:
    return sessions_dir(root) / ".current-session-id"


def session_jsonl_path(root: pathlib.Path, sid: str) -> pathlib.Path:
    return sessions_dir(root) / f"{sid}.jsonl"


def session_active_path(root: pathlib.Path, sid: str) -> pathlib.Path:
    return sessions_dir(root) / f"{sid}.active.txt"


def archive_dir(root: pathlib.Path) -> pathlib.Path:
    return sessions_dir(root) / "archive"


def template_dir(root: pathlib.Path) -> pathlib.Path:
    return root / ".claude" / "capability-templates"


@contextlib.contextmanager
def capability_lock(root: pathlib.Path) -> Iterator[None]:
    """Acquire an exclusive lock on capability state.

    Uses O_CREAT|O_EXCL which is atomic on POSIX and Windows filesystems.
    Retries until LOCK_TIMEOUT_SECONDS elapses. PID is recorded in the
    lockfile for diagnostics; stale lockfiles older than the timeout are
    reclaimed (covers crash-mid-lock).
    """
    sdir = sessions_dir(root)
    sdir.mkdir(parents=True, exist_ok=True)
    lockfile = sdir / ".lock"
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    while True:
        try:
            fd = os.open(
                str(lockfile),
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o644,
            )
            os.write(fd, f"{os.getpid()}\n".encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                age = time.time() - lockfile.stat().st_mtime
            except FileNotFoundError:
                continue
            if age > LOCK_TIMEOUT_SECONDS:
                with contextlib.suppress(FileNotFoundError):
                    lockfile.unlink()
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"capability lock busy: {lockfile}") from None
            time.sleep(LOCK_POLL_INTERVAL)
    try:
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            lockfile.unlink()


def now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_epoch() -> int:
    return int(time.time())


def parse_iso(stamp: str | None) -> int | None:
    if not stamp:
        return None
    try:
        dt = datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.UTC
        )
    except ValueError:
        return None
    return int(dt.timestamp())


def load_template(root: pathlib.Path, name: str) -> dict[str, Any]:
    path = template_dir(root) / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"capability template not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"template must be a mapping: {path}")
    missing = {"workflow", "step", "grants"} - data.keys()
    if missing:
        raise ValueError(f"template {name} missing required keys: {sorted(missing)}")
    return data


def read_current_session_id(root: pathlib.Path) -> str | None:
    path = current_session_id_path(root)
    if not path.exists():
        return None
    sid = path.read_text(encoding="utf-8").strip()
    return sid or None


def resolve_session_id(root: pathlib.Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    sid = read_current_session_id(root)
    if not sid:
        raise RuntimeError(
            "no session id: pass --session-id or run `session-start` first"
        )
    return sid


def active_grants(root: pathlib.Path, sid: str) -> list[dict[str, Any]]:
    """Replay the session jsonl, return grants that are live now.

    A grant is live iff: a `type:grant` record exists with entry_id X,
    no `type:revoke` record exists with the same entry_id, and the
    current time is before granted_at + min(declared_ttl, 24h ceiling).
    """
    path = session_jsonl_path(root, sid)
    if not path.exists():
        return []
    grants: dict[str, dict[str, Any]] = {}
    revoked: set[str] = set()
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = rec.get("type")
            entry_id = rec.get("entry_id")
            if not entry_id:
                continue
            if kind == "grant":
                grants[entry_id] = rec
            elif kind == "revoke":
                revoked.add(entry_id)
    now = now_epoch()
    live: list[dict[str, Any]] = []
    for eid, grant in grants.items():
        if eid in revoked:
            continue
        granted_at = parse_iso(grant.get("granted_at"))
        if granted_at is None:
            continue
        declared_ttl = int(grant.get("declared_ttl_seconds") or DEFAULT_TTL_SECONDS)
        effective_ttl = min(declared_ttl, TTL_HARD_CEILING_SECONDS)
        if now > granted_at + effective_ttl:
            continue
        live.append(grant)
    return live


def rewrite_active_cache(root: pathlib.Path, sid: str) -> None:
    """Recompute <sid>.active.txt from jsonl; atomic write-to-tmp + replace.

    Force LF-only line endings: the cache is consumed by bash reset hooks
    whose `[[ $target == $pattern ]]` glob match treats any trailing \r
    as part of the pattern. On Windows, pathlib.Path.write_text would
    otherwise translate \n to \r\n and break the match.
    """
    sessions_dir(root).mkdir(parents=True, exist_ok=True)
    path = session_active_path(root, sid)
    lines: list[str] = []
    for grant in active_grants(root, sid):
        spec = grant.get("grants") or {}
        for op in ("write", "rm"):
            for pattern in spec.get(op) or []:
                lines.append(f"{op}:{pattern}")
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    body = "\n".join(lines) + ("\n" if lines else "")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    os.replace(tmp, path)


def append_jsonl(root: pathlib.Path, sid: str, record: dict[str, Any]) -> None:
    sessions_dir(root).mkdir(parents=True, exist_ok=True)
    path = session_jsonl_path(root, sid)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")) + "\n")


def cmd_grant(args: argparse.Namespace) -> int:
    root = resolve_repo_root(args.repo_root)
    template = load_template(root, args.template)
    sid = resolve_session_id(root, args.session_id)
    entry_id = f"g-{args.template}-{uuid.uuid4().hex[:8]}"
    record = {
        "type": "grant",
        "entry_id": entry_id,
        "session_id": sid,
        "workflow": template["workflow"],
        "step": str(template["step"]),
        "grants": template.get("grants") or {"write": [], "rm": []},
        "granted_at": now_iso(),
        "declared_ttl_seconds": int(template.get("ttl_seconds") or DEFAULT_TTL_SECONDS),
        "authored_by": AUTHOR_TAG,
        "cp_id": args.cp_id or None,
        "is_subagent": bool(args.subagent),
        "parent_session_id": args.parent_session_id or None,
        "template": args.template,
    }
    with capability_lock(root):
        append_jsonl(root, sid, record)
        rewrite_active_cache(root, sid)
    sys.stdout.write(
        f"granted: template={args.template} entry_id={entry_id} session={sid}\n"
    )
    return 0


def cmd_revoke(args: argparse.Namespace) -> int:
    root = resolve_repo_root(args.repo_root)
    sid = resolve_session_id(root, args.session_id)
    with capability_lock(root):
        revoked: list[str] = [
            g["entry_id"]
            for g in active_grants(root, sid)
            if g.get("template") == args.template
        ]
        for eid in revoked:
            append_jsonl(
                root,
                sid,
                {
                    "type": "revoke",
                    "entry_id": eid,
                    "revoked_at": now_iso(),
                    "authored_by": AUTHOR_TAG,
                },
            )
        rewrite_active_cache(root, sid)
    if revoked:
        sys.stdout.write(
            f"revoked {len(revoked)} grant(s) matching template={args.template}\n"
        )
    else:
        sys.stdout.write(f"no active grants matched template={args.template}\n")
    return 0


def cmd_list_active(args: argparse.Namespace) -> int:
    root = resolve_repo_root(args.repo_root)
    sid = resolve_session_id(root, args.session_id)
    grants = active_grants(root, sid)
    if args.json:
        sys.stdout.write(json.dumps(grants, indent=2) + "\n")
        return 0
    if not grants:
        sys.stdout.write(f"(no active grants for session {sid})\n")
        return 0
    for grant in grants:
        sys.stdout.write(
            f"  {grant.get('template')}  entry_id={grant.get('entry_id')}\n"
        )
        for op, patterns in (grant.get("grants") or {}).items():
            for pat in patterns or []:
                sys.stdout.write(f"    {op}: {pat}\n")
    return 0


def cmd_session_start(args: argparse.Namespace) -> int:
    root = resolve_repo_root(args.repo_root)
    sid = args.session_id or uuid.uuid4().hex
    source = args.source or "startup"
    sessions_dir(root).mkdir(parents=True, exist_ok=True)
    is_subagent = bool(args.subagent)
    parent_sid = args.parent_session_id or None
    cp_id = args.cp_id or None
    with capability_lock(root):
        if not is_subagent:
            current_session_id_path(root).write_text(sid, encoding="utf-8")
        manifest_add_entry(
            root,
            sid=sid,
            source=source,
            is_subagent=is_subagent,
            parent_session_id=parent_sid,
            cp_id=cp_id,
            context=args.context or "",
        )
        sweep_orphans_impl(root)
    sys.stdout.write(
        f"session-start: sid={sid} source={source} subagent={is_subagent}\n"
    )
    return 0


def cmd_session_end(args: argparse.Namespace) -> int:
    root = resolve_repo_root(args.repo_root)
    sid = resolve_session_id(root, args.session_id)
    with capability_lock(root):
        for grant in active_grants(root, sid):
            append_jsonl(
                root,
                sid,
                {
                    "type": "revoke",
                    "entry_id": grant["entry_id"],
                    "revoked_at": now_iso(),
                    "authored_by": AUTHOR_TAG,
                    "reason": "session-end",
                },
            )
        rewrite_active_cache(root, sid)
        archive_session(root, sid)
        if read_current_session_id(root) == sid:
            with contextlib.suppress(FileNotFoundError):
                current_session_id_path(root).unlink()
    sys.stdout.write(f"session-end: sid={sid} archived\n")
    return 0


def cmd_sweep_orphans(args: argparse.Namespace) -> int:
    root = resolve_repo_root(args.repo_root)
    with capability_lock(root):
        count = sweep_orphans_impl(root)
    sys.stdout.write(f"sweep-orphans: archived {count} stale session(s)\n")
    return 0


def cmd_migrate_legacy(args: argparse.Namespace) -> int:
    root = resolve_repo_root(args.repo_root)
    removed: list[str] = []
    for legacy in (root / ".iocane" / "validating",):
        if legacy.exists():
            legacy.unlink()
            removed.append(str(legacy))
    sys.stdout.write(f"migrate-legacy: removed {len(removed)} legacy artifact(s)\n")
    for path in removed:
        sys.stdout.write(f"  {path}\n")
    return 0


def load_manifest(root: pathlib.Path) -> dict[str, Any]:
    path = manifest_path(root)
    if not path.exists():
        return {"max_entries": MANIFEST_MAX_ENTRIES, "sessions": []}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        return {"max_entries": MANIFEST_MAX_ENTRIES, "sessions": []}
    data.setdefault("max_entries", MANIFEST_MAX_ENTRIES)
    data.setdefault("sessions", [])
    return data


def save_manifest(root: pathlib.Path, data: dict[str, Any]) -> None:
    sessions_dir(root).mkdir(parents=True, exist_ok=True)
    path = manifest_path(root)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    os.replace(tmp, path)


def manifest_add_entry(
    root: pathlib.Path,
    *,
    sid: str,
    source: str,
    is_subagent: bool,
    parent_session_id: str | None,
    cp_id: str | None,
    context: str,
) -> None:
    data = load_manifest(root)
    started_at = now_iso()
    entry = {
        "session_id": sid,
        "composite_key": f"{sid}|new|{started_at}",
        "started_at": started_at,
        "ended_at": None,
        "status": "active",
        "source": source,
        "workflows": [],
        "parent_session_id": parent_session_id,
        "cp_id": cp_id,
        "context": context,
        "keywords": [],
        "is_subagent": is_subagent,
    }
    sessions = [s for s in (data.get("sessions") or []) if s.get("session_id") != sid]
    sessions.insert(0, entry)
    max_entries = int(data.get("max_entries") or MANIFEST_MAX_ENTRIES)
    data["sessions"] = sessions[:max_entries]
    save_manifest(root, data)


def archive_session(root: pathlib.Path, sid: str) -> None:
    """Move jsonl + active.txt to archive/YYYY-MM/; freeze manifest snapshot."""
    ts = datetime.datetime.now(datetime.UTC)
    month_dir = archive_dir(root) / ts.strftime("%Y-%m")
    month_dir.mkdir(parents=True, exist_ok=True)
    jsonl = session_jsonl_path(root, sid)
    active = session_active_path(root, sid)
    if jsonl.exists():
        os.replace(jsonl, month_dir / f"{sid}.jsonl")
    if active.exists():
        with contextlib.suppress(FileNotFoundError):
            active.unlink()
    data = load_manifest(root)
    ended_at = now_iso()
    updated: list[dict[str, Any]] = []
    frozen: dict[str, Any] | None = None
    for session in data.get("sessions") or []:
        if session.get("session_id") == sid:
            session = dict(session)
            session["ended_at"] = ended_at
            session["status"] = "archived"
            frozen = session
        updated.append(session)
    data["sessions"] = updated
    save_manifest(root, data)
    if frozen is not None:
        snap_path = month_dir / f"{sid}.manifest-entry.json"
        with snap_path.open("w", encoding="utf-8") as f:
            json.dump(frozen, f, indent=2)


def sweep_orphans_impl(root: pathlib.Path) -> int:
    """Archive stale per-session files.

    A session is stale iff its jsonl has not been touched in >24h AND it
    has no currently-active grants. Covers crash-mid-step scenarios where
    neither session-end nor normal revoke fired.
    """
    sdir = sessions_dir(root)
    if not sdir.exists():
        return 0
    count = 0
    now = now_epoch()
    current = read_current_session_id(root)
    for jsonl in sdir.glob("*.jsonl"):
        sid = jsonl.stem
        if sid == current:
            continue
        try:
            mtime = int(jsonl.stat().st_mtime)
        except FileNotFoundError:
            continue
        if now - mtime <= TTL_HARD_CEILING_SECONDS:
            continue
        if active_grants(root, sid):
            continue
        archive_session(root, sid)
        count += 1
    return count


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--repo-root",
        help="Canonical repo root (default: git rev-parse --show-toplevel then cwd)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="capability.py", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("grant", help="issue capability from template")
    add_common_args(g)
    g.add_argument("--template", required=True)
    g.add_argument("--session-id")
    g.add_argument("--cp-id")
    g.add_argument("--parent-session-id")
    g.add_argument("--subagent", action="store_true")
    g.set_defaults(func=cmd_grant)

    r = sub.add_parser("revoke", help="revoke capability by template name")
    add_common_args(r)
    r.add_argument("--template", required=True)
    r.add_argument("--session-id")
    r.set_defaults(func=cmd_revoke)

    la = sub.add_parser("list-active", help="print currently-active grants")
    add_common_args(la)
    la.add_argument("--session-id")
    la.add_argument("--json", action="store_true")
    la.set_defaults(func=cmd_list_active)

    ss = sub.add_parser("session-start", help="bootstrap session state")
    add_common_args(ss)
    ss.add_argument("--session-id")
    ss.add_argument("--source", default="startup")
    ss.add_argument("--context", default="")
    ss.add_argument("--cp-id")
    ss.add_argument("--parent-session-id")
    ss.add_argument("--subagent", action="store_true")
    ss.set_defaults(func=cmd_session_start)

    se = sub.add_parser("session-end", help="revoke active + archive session")
    add_common_args(se)
    se.add_argument("--session-id")
    se.set_defaults(func=cmd_session_end)

    so = sub.add_parser("sweep-orphans", help="archive stale session files")
    add_common_args(so)
    so.set_defaults(func=cmd_sweep_orphans)

    ml = sub.add_parser("migrate-legacy", help="remove pre-refactor sentinel state")
    add_common_args(ml)
    ml.set_defaults(func=cmd_migrate_legacy)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())

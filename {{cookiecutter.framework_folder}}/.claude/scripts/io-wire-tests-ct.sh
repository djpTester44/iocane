#!/usr/bin/env bash
# .claude/scripts/io-wire-tests-ct.sh
#
# Orchestrator for /io-wire-tests-ct. Enumerates CT targets (seam edges) from
# plans/seams.yaml, applies STRICT precondition gate (D-20: CDT eval
# STATUS=PASS + no collision-tainted markers), fans out per-target Actor-Critic
# inner loops via xargs -P, applies implicit barrier at command boundary,
# performs post-batch collision detection (D-21 rev 4), and on all-PASS
# performs resolved-suffix sweep gated by no-collision.
#
# Usage:
#   io-wire-tests-ct.sh [--targets <edge1,edge2,...>]

set -euo pipefail

# ============================================================================
# Globals
# ============================================================================

REPO="${IOCANE_REPO_ROOT:-.}"
ORCHESTRATOR_NAME="io-wire-tests-ct"

TARGETS_ARG=""
MAX_TURNS_OVERRIDE=""
MAX_TARGETS_OVERRIDE=""
PARALLEL_OVERRIDE=""

# ============================================================================
# CLI Parsing
# ============================================================================

while [[ $# -gt 0 ]]; do
    case "$1" in
        --targets)      TARGETS_ARG="$2";          shift 2 ;;
        --max-turns)    MAX_TURNS_OVERRIDE="$2";   shift 2 ;;
        --max-targets)  MAX_TARGETS_OVERRIDE="$2"; shift 2 ;;
        --parallel)     PARALLEL_OVERRIDE="$2";    shift 2 ;;
        *)
            echo "ERROR: Unknown argument '$1'" >&2
            exit 1
            ;;
    esac
done

# Validate numeric overrides (positive integers if set)
_validate_pos_int() {
    if [[ -n "$2" ]] && ! [[ "$2" =~ ^[1-9][0-9]*$ ]]; then
        echo "ERROR: $1 must be a positive integer (got '$2')" >&2
        exit 1
    fi
}
_validate_pos_int "--max-turns"   "$MAX_TURNS_OVERRIDE"
_validate_pos_int "--max-targets" "$MAX_TARGETS_OVERRIDE"
_validate_pos_int "--parallel"    "$PARALLEL_OVERRIDE"

# ============================================================================
# Architect-mode sentinel preflight
# ============================================================================

ARCHITECT_MODE_FLAG="${REPO}/.iocane/architect-mode"
if [[ -f "$ARCHITECT_MODE_FLAG" ]]; then
    echo "ERROR: .iocane/architect-mode sentinel is set. /io-architect is mid-design." >&2
    echo "       Complete or abandon the architect pass and clear $ARCHITECT_MODE_FLAG before running wire tests." >&2
    exit 1
fi

# ============================================================================
# SESSION_ID UUID assignment (needed by mutex pidfile)
# ============================================================================

SESSION_ID=$(uv run python -c "import uuid; print(str(uuid.uuid4()))")

# ============================================================================
# Launch mutex (Phase E -- prevents accidental orchestrator stacking)
# ============================================================================
#
# Acquire-or-fail via `set -o noclobber` + `>` redirect. The redirect uses
# O_CREAT|O_EXCL at the kernel level -- atomic exclusive-create with no
# TOCTOU window between check and write. On contention, exactly one
# launch's redirect succeeds; the rest get a non-zero subshell exit and
# fall into the liveness-check + stale-reclaim path.
#
# Single shared pidfile across CDT and CT: D-20's CT-after-CDT-all-PASS
# precondition makes concurrent CDT+CT a workflow violation; the shared
# lock enforces that as a side-effect rather than relying on per-orchestrator
# bookkeeping.
#
# Trap removes the pidfile on graceful exit ONLY if the recorded PID still
# matches $$ -- guards against the trap unlinking another launch's pidfile
# in the rare case where a false-stale reclaim path was taken upstream.
# SIGKILL (panic-stop, TaskStop) bypasses the trap; the next launch's
# liveness check reclaims via mv-to-quarantine.

PIDFILE="${REPO}/.iocane/wire-tests/.orchestrator.pid"
mkdir -p "$(dirname "$PIDFILE")"
PIDFILE_TS=$(uv run python -c "from datetime import datetime, UTC; print(datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'))")

ACQUIRED=0
ATTEMPTS=0
MAX_ATTEMPTS=2

while [[ $ATTEMPTS -lt $MAX_ATTEMPTS && $ACQUIRED -eq 0 ]]; do
    ATTEMPTS=$((ATTEMPTS + 1))

    # Atomic exclusive-create. Subshell isolates `set -o noclobber` and the
    # error from a failed redirect. $$ in the subshell expands to the parent
    # shell's PID (bash semantics), so the recorded PID is the orchestrator's.
    if (set -o noclobber; printf '%s\t%s\t%s\t%s\n' "$$" "$SESSION_ID" "$ORCHESTRATOR_NAME" "$PIDFILE_TS" > "$PIDFILE") 2>/dev/null; then
        ACQUIRED=1
        break
    fi

    # Pidfile exists. Read the recorded process info.
    EXISTING_PID=$(awk -F'\t' '{print $1}' "$PIDFILE" 2>/dev/null || echo "")
    EXISTING_SID=$(awk -F'\t' '{print $2}' "$PIDFILE" 2>/dev/null || echo "")
    EXISTING_CMD=$(awk -F'\t' '{print $3}' "$PIDFILE" 2>/dev/null || echo "")
    EXISTING_TS=$(awk -F'\t' '{print $4}' "$PIDFILE" 2>/dev/null || echo "")

    if [[ -n "$EXISTING_PID" ]] && kill -0 "$EXISTING_PID" 2>/dev/null; then
        echo "ERROR: another wire-tests orchestrator is already running:" >&2
        echo "       PID:     $EXISTING_PID" >&2
        echo "       SID:     $EXISTING_SID" >&2
        echo "       Command: $EXISTING_CMD" >&2
        echo "       Started: $EXISTING_TS" >&2
        echo "" >&2
        echo "Wait for it to complete, OR force-stop with:" >&2
        echo "       powershell -NoProfile -File .claude/scripts/wire-tests-panic-stop.ps1" >&2
        exit 75
    fi

    # Recorded PID is dead -- stale pidfile. Reclaim via atomic mv-to-quarantine.
    # Two near-simultaneous reclaims race on the rename: only one mv succeeds
    # (rename is kernel-atomic), the other's source has already moved and mv
    # exits non-zero. The winner cleans the quarantine and loops back to retry
    # set-noclobber acquire. The loser's mv-fail also loops back; on the next
    # pass the pidfile either doesn't exist (winner hasn't rewritten yet, set -C
    # acquires) or contains the winner's PID (set -C fails, fall into liveness
    # check, refuse since winner is alive).
    QUARANTINE="${PIDFILE}.stale.$$.$ATTEMPTS"
    if mv "$PIDFILE" "$QUARANTINE" 2>/dev/null; then
        rm -f "$QUARANTINE"
        echo "WARN: stale pidfile from PID $EXISTING_PID (not alive); reclaimed" >&2
    fi
done

if [[ $ACQUIRED -eq 0 ]]; then
    echo "ERROR: failed to acquire wire-tests mutex after $ATTEMPTS attempts" >&2
    echo "       Another orchestrator likely won a contended reclaim race." >&2
    echo "       Re-run if you intended to launch." >&2
    exit 75
fi

_cleanup_pidfile() {
    # Ownership guard: only unlink if the recorded PID still matches $$.
    # Defends against the rare case where a false-stale reclaim caused
    # another launch to overwrite our pidfile while we were still alive --
    # in that case we must NOT remove their lock on our exit.
    if [[ -f "$PIDFILE" ]]; then
        local cur_pid
        cur_pid=$(awk -F'\t' '{print $1}' "$PIDFILE" 2>/dev/null || echo "")
        if [[ "$cur_pid" == "$$" ]]; then
            rm -f "$PIDFILE" 2>/dev/null || true
        fi
    fi
}
trap _cleanup_pidfile EXIT

# ============================================================================
# Session registration (orchestrator run identity for spawn-log correlation)
# ============================================================================

# Capture parent (the main Claude Code session that invoked us) before we
# register our own session, so manifest links the orchestrator under it.
PARENT_SID="$(cat "${REPO}/.iocane/sessions/.current-session-id" 2>/dev/null || echo "")"

# Register the orchestrator run as a subagent session. --subagent prevents
# capability.py from overwriting .current-session-id under fan-out. Fail-open:
# if registration fails, sweep-orphans cleans the per-run jsonl within 24h.
uv run python "${REPO}/.claude/scripts/capability.py" session-start \
    --session-id "$SESSION_ID" \
    --subagent \
    --parent-session-id "$PARENT_SID" \
    --source "io-wire-tests-ct" \
    >/dev/null 2>&1 || true

# ============================================================================
# Config loading
# ============================================================================

CONFIG="${REPO}/.claude/iocane.config.yaml"

LIMIT=4
_limit_raw=$(uv run python -c "
import yaml
try:
    cfg = yaml.safe_load(open('${CONFIG}'))
    wt = cfg.get('wire_tests', {})
    v = wt.get('parallel', {}).get('limit')
    if v is None:
        v = cfg.get('parallel', {}).get('limit', 4)
    print(int(v))
except Exception:
    print(4)
" 2>/dev/null) && LIMIT="$_limit_raw" || true

MAX_TURNS=5
_mt_raw=$(uv run python -c "
import yaml
try:
    cfg = yaml.safe_load(open('${CONFIG}'))
    print(int(cfg.get('wire_tests', {}).get('max_turns', 5)))
except Exception:
    print(5)
" 2>/dev/null) && MAX_TURNS="$_mt_raw" || true

# Apply CLI overrides (take precedence over config)
[[ -n "$MAX_TURNS_OVERRIDE" ]] && MAX_TURNS="$MAX_TURNS_OVERRIDE"
[[ -n "$PARALLEL_OVERRIDE" ]] && LIMIT="$PARALLEL_OVERRIDE"

# ============================================================================
# Target enumeration (seam edges from plans/seams.yaml)
# ============================================================================

SEAMS_FILE="${REPO}/plans/seams.yaml"
if [[ ! -f "$SEAMS_FILE" ]]; then
    echo "ERROR: ${SEAMS_FILE} not found" >&2
    exit 1
fi

declare -a CANDIDATE_TARGETS=()

if [[ -n "$TARGETS_ARG" ]]; then
    IFS=',' read -ra RAW_TARGETS <<< "$TARGETS_ARG"
    for id in "${RAW_TARGETS[@]}"; do
        id="${id// /}"
        if ! [[ "$id" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]]; then
            echo "ERROR: target edge id '${id}' fails identifier validation (^[A-Za-z_][A-Za-z0-9_-]*\$)" >&2
            exit 1
        fi
        CANDIDATE_TARGETS+=("$id")
    done
else
    ALL_EDGE_IDS=""
    ALL_EDGE_IDS=$(uv run python -c "
import sys
sys.path.insert(0, '${REPO}/.claude/scripts')
from seam_parser import load_seams, all_di_edges
seams = load_seams('${SEAMS_FILE}')
for comp, dep in all_di_edges(seams):
    print(f'{dep}__{comp}')
" | tr -d '\r') || {
        echo "ERROR: failed to enumerate CT targets from ${SEAMS_FILE}" >&2
        exit 1
    }

    EDGE_COUNT=0
    SKIP_COUNT=0
    while IFS= read -r edge_id; do
        [[ -z "$edge_id" ]] && continue
        EDGE_COUNT=$((EDGE_COUNT + 1))
        EVAL_FILE="${REPO}/.iocane/wire-tests/eval_${edge_id}.yaml"
        STATUS="UNKNOWN"
        if [[ -f "$EVAL_FILE" ]]; then
            _st=$(uv run python -c "
import sys
sys.path.insert(0, '${REPO}/.claude/scripts')
from eval_parser import load_eval_report
try:
    r = load_eval_report('${EVAL_FILE}')
    print(r.status)
except Exception:
    print('UNKNOWN')
" 2>/dev/null) && STATUS="$_st" || true
        fi
        if [[ "$STATUS" == "PASS" ]]; then
            echo "SKIP: ${edge_id} (CT STATUS=PASS)" >&2
            SKIP_COUNT=$((SKIP_COUNT + 1))
            continue
        fi
        CANDIDATE_TARGETS+=("$edge_id")
    done <<< "$ALL_EDGE_IDS"
fi

if [[ "${#CANDIDATE_TARGETS[@]}" -eq 0 ]]; then
    if [[ "${EDGE_COUNT:-0}" -eq 0 ]]; then
        echo "INFO: no CT targets to process (seams.yaml contains 0 DI edges; check injected_contracts authoring in plans/seams.yaml)" >&2
    elif [[ "${SKIP_COUNT:-0}" -eq "${EDGE_COUNT}" ]]; then
        echo "INFO: no CT targets to process (all ${EDGE_COUNT} edges already PASS via skip-loop)" >&2
    else
        echo "INFO: no CT targets to process" >&2
    fi
    exit 0
fi

# Apply --max-targets cap (pre-precondition gate; bounds blast radius for manual testing)
if [[ -n "$MAX_TARGETS_OVERRIDE" ]] && [[ "${#CANDIDATE_TARGETS[@]}" -gt "$MAX_TARGETS_OVERRIDE" ]]; then
    echo "INFO: --max-targets ${MAX_TARGETS_OVERRIDE} caps candidates (${#CANDIDATE_TARGETS[@]} unprocessed available; precondition gate may reduce further)" >&2
    CANDIDATE_TARGETS=("${CANDIDATE_TARGETS[@]:0:$MAX_TARGETS_OVERRIDE}")
fi

# ============================================================================
# Directories (needed before precondition FindingFile writes)
# ============================================================================

RUN_LOG_DIR="${REPO}/.iocane/wire-tests/run-log"
SPAWN_LOG_DIR="${REPO}/.iocane/wire-tests/spawn-log"
ARCHIVE_COLLISION_DIR="${REPO}/.iocane/wire-tests/archive/collision"
FINDINGS_DIR="${REPO}/.iocane/findings"
mkdir -p "$RUN_LOG_DIR" "$SPAWN_LOG_DIR" "$ARCHIVE_COLLISION_DIR" "$FINDINGS_DIR"

# ============================================================================
# Helper: emit precondition FindingFile (write-temp-then-rename for atomicity)
# ============================================================================

_emit_precondition_finding() {
    local edge_id="$1"
    local defect_kind="$2"
    local diagnosis_what="$3"
    local fix_step="$4"
    local TS
    TS=$(uv run python -c \
        "from datetime import datetime, UTC; print(datetime.now(UTC).strftime('%Y%m%dT%H%M%S'))")
    local FINDING_PATH="${FINDINGS_DIR}/wire_test_${defect_kind}-${edge_id}-${TS}.yaml"
    local TMP_FINDING="${FINDING_PATH}.tmp.$$"
    cat > "$TMP_FINDING" <<YAML_EOF
role: wire_test_author
context:
  edge_id: ${edge_id}
defect_kind: ${defect_kind}
diagnosis:
  what: "${diagnosis_what}"
remediation:
  root_cause_layer: wire_tests
  fix_steps:
    - "${fix_step}"
  re_entry_commands:
    - "bash .claude/scripts/io-wire-tests-ct.sh --targets ${edge_id}"
YAML_EOF
    mv "$TMP_FINDING" "$FINDING_PATH" 2>/dev/null || \
        echo "WARN: failed to persist precondition FindingFile for ${edge_id}" >&2
}

# ============================================================================
# STRICT precondition gate (D-20 + rev 4 collision-tainted check)
#
# Per edge: resolve src + dst from seams.yaml, then:
#   (1) tests/contracts/test_<src>.py AND test_<dst>.py exist
#   (2) .iocane/wire-tests/eval_<src>.yaml AND eval_<dst>.yaml STATUS=PASS
#   (3) No .collision-tainted marker on either CDT eval YAML
# Fail => emit FindingFile (distinct defect_kind per check) + skip target.
# Batch continues with remaining valid targets.
# ============================================================================

declare -a TARGETS=()

for edge_id in "${CANDIDATE_TARGETS[@]}"; do
    SRC_DST=$(uv run python -c "
import sys
sys.path.insert(0, '${REPO}/.claude/scripts')
from seam_parser import load_seams, all_di_edges
seams = load_seams('${SEAMS_FILE}')
lookup = {f'{dep}__{comp}': (dep, comp) for comp, dep in all_di_edges(seams)}
pair = lookup.get('${edge_id}')
if pair:
    print(pair[0])
    print(pair[1])
" 2>/dev/null | tr -d '\r') || SRC_DST=""

    if [[ -z "$SRC_DST" ]]; then
        echo "WARN: edge '${edge_id}' not resolvable in ${SEAMS_FILE}; skipping" >&2
        continue
    fi

    SRC=$(echo "$SRC_DST" | head -1)
    DST=$(echo "$SRC_DST" | tail -1)

    _precondition_ok=1

    # (1) CDT test files must exist on disk
    SRC_TEST="${REPO}/tests/contracts/test_${SRC}.py"
    DST_TEST="${REPO}/tests/contracts/test_${DST}.py"
    if [[ ! -f "$SRC_TEST" ]] || [[ ! -f "$DST_TEST" ]]; then
        _missing=""
        [[ ! -f "$SRC_TEST" ]] && _missing="${SRC}"
        [[ ! -f "$DST_TEST" ]] && _missing="${_missing:+${_missing},}${DST}"
        echo "SKIP: ${edge_id} (ct_precondition_cdt_missing: ${_missing})" >&2
        _emit_precondition_finding \
            "${edge_id}" \
            "ct_precondition_cdt_missing" \
            "CDT test file(s) missing for components: ${_missing}" \
            "bash .claude/scripts/io-wire-tests-cdt.sh --targets ${_missing}"
        _precondition_ok=0
    fi

    # (2) CDT eval YAMLs must be STATUS=PASS
    if [[ "$_precondition_ok" -eq 1 ]]; then
        _non_pass=""
        for _cid in "$SRC" "$DST"; do
            _ef="${REPO}/.iocane/wire-tests/eval_${_cid}.yaml"
            _st=$(uv run python -c "
import sys
sys.path.insert(0, '${REPO}/.claude/scripts')
from eval_parser import load_eval_report
try:
    r = load_eval_report('${_ef}')
    print(r.status)
except Exception:
    print('UNKNOWN')
" 2>/dev/null) || _st="UNKNOWN"
            if [[ "$_st" != "PASS" ]]; then
                _non_pass="${_non_pass:+${_non_pass},}${_cid}(${_st})"
            fi
        done
        if [[ -n "$_non_pass" ]]; then
            echo "SKIP: ${edge_id} (ct_precondition_cdt_not_pass: ${_non_pass})" >&2
            _emit_precondition_finding \
                "${edge_id}" \
                "ct_precondition_cdt_not_pass" \
                "CDT eval STATUS != PASS for: ${_non_pass}" \
                "Resolve CDT FAIL/AMBIGUOUS then re-run: bash .claude/scripts/io-wire-tests-cdt.sh --targets ${_non_pass%%(*}"
            _precondition_ok=0
        fi
    fi

    # (3) No collision-tainted markers on CDT eval YAMLs
    if [[ "$_precondition_ok" -eq 1 ]]; then
        _tainted=""
        for _cid in "$SRC" "$DST"; do
            if [[ -f "${REPO}/.iocane/wire-tests/eval_${_cid}.yaml.collision-tainted" ]]; then
                _tainted="${_tainted:+${_tainted},}${_cid}"
            fi
        done
        if [[ -n "$_tainted" ]]; then
            echo "SKIP: ${edge_id} (ct_precondition_cdt_collision_tainted: ${_tainted})" >&2
            _emit_precondition_finding \
                "${edge_id}" \
                "ct_precondition_cdt_collision_tainted" \
                "CDT eval collision-tainted for: ${_tainted}" \
                "Archive + re-author + re-run CDT to PASS for ${_tainted} before re-running CT"
            _precondition_ok=0
        fi
    fi

    [[ "$_precondition_ok" -eq 1 ]] && TARGETS+=("$edge_id")
done

if [[ "${#TARGETS[@]}" -eq 0 ]]; then
    if [[ -n "$MAX_TARGETS_OVERRIDE" ]]; then
        echo "WARN: --max-targets ${MAX_TARGETS_OVERRIDE} was set; 0 of ${#CANDIDATE_TARGETS[@]} capped candidate(s) passed the precondition gate" >&2
        echo "WARN: zero-work exit treated as failure when --max-targets is explicit (silent green exit on no-op suppressed)" >&2
        exit 1
    fi
    echo "INFO: no CT targets passed precondition gate (all skipped)" >&2
    exit 0
fi

echo "INFO: processing ${#TARGETS[@]} CT target(s): concurrency=${LIMIT} max_turns_per_target=${MAX_TURNS}" >&2

# ============================================================================
# Fan-out: xargs -P with implicit barrier at command boundary
# ============================================================================

export REPO SESSION_ID MAX_TURNS RUN_LOG_DIR

FANOUT_EXIT=0
printf '%s\n' "${TARGETS[@]}" | \
    xargs -P "$LIMIT" -I __TGT__ bash -c '
        bash "${REPO}/.claude/scripts/run_actor_critic_loop.sh" \
            --target-id __TGT__ \
            --target-type ct \
            --max-turns "${MAX_TURNS}" \
            --session-id "${SESSION_ID}" \
            > "${RUN_LOG_DIR}/__TGT__.log" 2>&1
    ' || FANOUT_EXIT=$?

if [[ "$FANOUT_EXIT" -ne 0 ]]; then
    echo "WARN: fan-out had infrastructure failure(s) (xargs exit ${FANOUT_EXIT}); check ${RUN_LOG_DIR}/" >&2
fi

# ============================================================================
# Post-batch collision detection (D-21 rev 4)
# ============================================================================

declare -A COLLISION_TARGETS=()

COLLISION_DATA=""
COLLISION_DATA=$(uv run python -c "
import json
from pathlib import Path
spawn_log = Path('${SPAWN_LOG_DIR}')
if not spawn_log.exists():
    import sys; sys.exit(0)
path_to_sids: dict[str, set[str]] = {}
for f in (spawn_log / '${SESSION_ID}').glob('*.json'):
    try:
        d = json.loads(f.read_text())
        wt = d.get('write_target_path', '')
        sid = d.get('sid', '')
        if wt and sid:
            path_to_sids.setdefault(wt, set()).add(sid)
    except Exception:
        pass
for path, sids in path_to_sids.items():
    if len(sids) > 1:
        print(path + '|' + ','.join(sorted(sids)))
" 2>/dev/null | tr -d '\r') || COLLISION_DATA=""

if [[ -n "$COLLISION_DATA" ]]; then
    echo "WARN: parallel write collisions detected; see ${FINDINGS_DIR}/ for FindingFiles" >&2

    while IFS='|' read -r collision_path sids; do
        [[ -z "$collision_path" ]] && continue

        bname=$(basename "$collision_path")
        target_id=$(echo "$bname" | sed -E 's/^(test_|eval_)//;s/\.(py|yaml)$//')
        COLLISION_TARGETS["$target_id"]=1

        echo "WARN: collision on '${collision_path}' (sids: ${sids})" >&2

        # Archive colliding CT test file
        TEST_FILE="${REPO}/tests/connectivity/test_${target_id}.py"
        FIRST_SID=$(echo "$sids" | cut -d',' -f1)
        if [[ -f "$TEST_FILE" ]]; then
            mkdir -p "${ARCHIVE_COLLISION_DIR}/${SESSION_ID}"
            mv "$TEST_FILE" \
               "${ARCHIVE_COLLISION_DIR}/${SESSION_ID}/test_${target_id}-${FIRST_SID}.py" 2>/dev/null || \
               echo "WARN: failed to archive ${TEST_FILE} to collision dir" >&2
        fi

        # Mark colliding CT eval YAML collision-tainted
        EVAL_FILE="${REPO}/.iocane/wire-tests/eval_${target_id}.yaml"
        if [[ -f "$EVAL_FILE" ]]; then
            mv "$EVAL_FILE" "${EVAL_FILE}.collision-tainted" 2>/dev/null || \
               echo "WARN: failed to taint ${EVAL_FILE}" >&2
        fi

        # Emit collision FindingFile (write-temp-then-rename for atomicity)
        TS=$(uv run python -c \
            "from datetime import datetime, UTC; print(datetime.now(UTC).strftime('%Y%m%dT%H%M%S'))")
        FINDING_PATH="${FINDINGS_DIR}/wire_test_collision-${target_id}-${TS}.yaml"
        TMP_FINDING="${FINDING_PATH}.tmp.$$"

        cat > "$TMP_FINDING" <<YAML_EOF
role: wire_test_author
context:
  test_file: tests/connectivity/test_${target_id}.py
defect_kind: parallel_write_collision
affected_artifacts:
  - ${collision_path}
diagnosis:
  what: "Parallel actors wrote to the same path during CT fan-out"
  where: "${collision_path}"
  why: "Multiple session ids (${sids}) claimed the same write_target_path; outputs are ambiguous"
remediation:
  root_cause_layer: wire_tests
  fix_steps:
    - "Restore authoritative test from ${ARCHIVE_COLLISION_DIR}/${SESSION_ID}/test_${target_id}-${FIRST_SID}.py"
    - "Re-run: bash .claude/scripts/io-wire-tests-ct.sh --targets ${target_id}"
  re_entry_commands:
    - "bash .claude/scripts/io-wire-tests-ct.sh --targets ${target_id}"
YAML_EOF

        mv "$TMP_FINDING" "$FINDING_PATH" 2>/dev/null || \
            echo "WARN: failed to persist collision FindingFile for ${target_id}" >&2

    done <<< "$COLLISION_DATA"
fi

# ============================================================================
# Resolved-suffix sweep (gated: CT STATUS=PASS + no collision)
# ============================================================================

for id in "${TARGETS[@]}"; do
    if [[ "${COLLISION_TARGETS[$id]+_}" ]]; then
        echo "SKIP resolved-sweep: ${id} (collision-tainted)" >&2
        continue
    fi

    EVAL_FILE="${REPO}/.iocane/wire-tests/eval_${id}.yaml"
    if [[ -f "${EVAL_FILE}.collision-tainted" ]]; then
        echo "SKIP resolved-sweep: ${id} (eval collision-tainted marker present)" >&2
        continue
    fi

    [[ -f "$EVAL_FILE" ]] || continue

    STATUS="UNKNOWN"
    _st=$(uv run python -c "
import sys
sys.path.insert(0, '${REPO}/.claude/scripts')
from eval_parser import load_eval_report
try:
    r = load_eval_report('${EVAL_FILE}')
    print(r.status)
except Exception:
    print('UNKNOWN')
" 2>/dev/null) && STATUS="$_st" || true

    [[ "$STATUS" != "PASS" ]] && continue

    swept=0
    while IFS= read -r -d '' finding; do
        [[ "$finding" == *.resolved ]] && continue
        mv "$finding" "${finding}.resolved" 2>/dev/null || \
            echo "WARN: failed to rename ${finding}" >&2
        swept=$(( swept + 1 ))
    done < <(find "${FINDINGS_DIR}" -maxdepth 1 \
        -name "wire_test_*-${id}-*.yaml" -print0 2>/dev/null)

    echo "INFO: resolved-sweep complete for ${id} (${swept} finding(s) archived)" >&2
done

# ============================================================================
# Session end (orchestrator run)
# ============================================================================

uv run python "${REPO}/.claude/scripts/capability.py" session-end \
    --session-id "$SESSION_ID" \
    >/dev/null 2>&1 || true

# ============================================================================
# Exit
# ============================================================================

# Non-zero only on infrastructure failures. Terminal states (PASS / FAIL-exhausted
# / AMBIGUOUS) from inner loops all exit 0 from run_actor_critic_loop.sh.
if [[ "$FANOUT_EXIT" -ne 0 ]]; then
    exit "$FANOUT_EXIT"
fi

exit 0

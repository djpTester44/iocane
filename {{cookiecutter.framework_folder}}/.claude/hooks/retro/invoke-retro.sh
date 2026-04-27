#!/usr/bin/env bash
# /lessons-retro pipeline orchestrator.
# Synchronous Pass 1 (Sonnet) -> Pass 2 (Opus xhigh).
# Detachment is the caller's responsibility (session-start.sh wraps with
# `nohup ... & disown` for the /clear-trigger path; /lessons-retro slash
# command runs synchronously for the manual path).
#
# Usage:
#   bash invoke-retro.sh           <prior_session_id> <prior_transcript_path>
#   bash invoke-retro.sh --manual  <session_id> <transcript_path>
#
# Exit codes: 0 on success or graceful no-op (cooldown, disabled).
# Non-zero only on hard failure (Pass 1/2 produced no output).

set -u

REPO_ROOT="${IOCANE_REPO_ROOT:-$(pwd)}"
cd "$REPO_ROOT" || exit 1

LESSONS_ENABLED=1
LESSONS_COOLDOWN_MINUTES=5
LESSONS_REVIEW_REMINDER_HOURS=24
LESSONS_AUTO_PROMOTE=0  # hard-coded; never overridable from config

if [ -f .lessons/config.yaml ]; then
    while IFS= read -r line; do
        case "$line" in
            enabled:*)
                LESSONS_ENABLED="$(printf '%s' "${line#enabled:}" | tr -d ' ')"
                ;;
            cooldown_minutes:*)
                LESSONS_COOLDOWN_MINUTES="$(printf '%s' "${line#cooldown_minutes:}" | tr -d ' ')"
                ;;
            review_reminder_hours:*)
                LESSONS_REVIEW_REMINDER_HOURS="$(printf '%s' "${line#review_reminder_hours:}" | tr -d ' ')"
                ;;
        esac
    done < .lessons/config.yaml
fi

MANUAL=0
if [ "${1:-}" = "--manual" ]; then
    MANUAL=1
    shift
fi

PRIOR_SID="${1:-}"
PRIOR_TRANSCRIPT="${2:-}"

if [ -z "$PRIOR_SID" ] || [ -z "$PRIOR_TRANSCRIPT" ]; then
    echo "usage: $0 [--manual] <session_id> <transcript_path>" >&2
    exit 2
fi

mkdir -p .lessons/tmp .lessons/retro-review .lessons/retro-review/archive .lessons/workspace-rules .lessons/debug

if [ "$LESSONS_ENABLED" != "1" ]; then
    exit 0
fi

NOW="$(date -u +%s)"
if [ "$MANUAL" != "1" ] && [ -f .lessons/.cooldown ]; then
    LAST="$(cat .lessons/.cooldown 2>/dev/null || echo 0)"
    AGE_MIN=$(( (NOW - LAST) / 60 ))
    if [ "$AGE_MIN" -lt "$LESSONS_COOLDOWN_MINUTES" ]; then
        TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        printf '%s skipped sid=%s reason=cooldown last_run=%dm_ago threshold=%dm\n' \
            "$TS" "$PRIOR_SID" "$AGE_MIN" "$LESSONS_COOLDOWN_MINUTES" \
            >> .lessons/.skip-log
        exit 0
    fi
fi

echo "$NOW" > .lessons/.cooldown

STAMP="$(date -u +%Y%m%d-%H%M)"
PASS1_OUT=".lessons/tmp/sesh-knowledge_${STAMP}.jsonl"
PASS2_OUT=".lessons/retro-review/${STAMP}-proposal.md"

export LESSONS_PRIOR_SID="$PRIOR_SID"
export LESSONS_PRIOR_TRANSCRIPT_PATH="$PRIOR_TRANSCRIPT"
export LESSONS_PASS1_OUT_PATH="$PASS1_OUT"
export LESSONS_PASS2_OUT_PATH="$PASS2_OUT"
export IOCANE_SUBAGENT=1

LOG=.lessons/debug/pipeline.log
log() {
    printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" >> "$LOG"
}

log "pipeline start sid=$PRIOR_SID manual=$MANUAL transcript=$PRIOR_TRANSCRIPT"

log "pass1 begin -> $PASS1_OUT"
timeout 300 claude -p "/lessons-pass1-extract $PRIOR_TRANSCRIPT $PASS1_OUT" \
    --model claude-sonnet-4-6 \
    --output-format json \
    --allowedTools "Bash,Read,Write" \
    > ".lessons/debug/pass1-${STAMP}.envelope.json" 2>> "$LOG"
PASS1_RC=$?
log "pass1 exit=$PASS1_RC"

if [ ! -s "$PASS1_OUT" ]; then
    log "pass1 produced no output -- abort"
    exit 1
fi

log "pass2 begin -> $PASS2_OUT"
timeout 600 claude -p "/lessons-pass2-triage $PASS1_OUT $PASS2_OUT" \
    --model claude-opus-4-7 \
    --output-format json \
    --allowedTools "Bash,Read,Write" \
    > ".lessons/debug/pass2-${STAMP}.envelope.json" 2>> "$LOG"
PASS2_RC=$?
log "pass2 exit=$PASS2_RC"

if [ ! -s "$PASS2_OUT" ]; then
    log "pass2 produced no output -- abort"
    exit 1
fi

touch .lessons/.pending-review
log "pipeline complete proposal=$PASS2_OUT"

exit 0

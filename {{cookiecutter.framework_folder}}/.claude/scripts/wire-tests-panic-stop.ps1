<#
.SYNOPSIS
    Iterative workers-first kill of wire-tests subprocesses.
    Up to 3 passes; exit 0 on first quiet pass.

.DESCRIPTION
    Each pass runs a workers-first kill sweep:

      Stage A  kill bash workers (orchestrators + xargs slot inner loops +
               spawn wrappers). With xargs and the orchestrator dead, no new
               'claude -p' can be dispatched.
      Stage B  kill any remaining 'claude -p' (now orphaned after Stage A).

    A 3-second settle then recounts both pools. If both reach 0, exit 0.
    Otherwise the pass repeats, up to 3 iterations total. Exit 1 only if
    residuals remain after the third pass.

    WHY WORKERS-FIRST. Leaves-first ordering triggered the same race the
    original incident exposed: killing a 'claude -p' caused its bash worker
    to die via 'set -e', which freed an xargs slot, which dispatched a
    replacement worker for the next target -- producing a fresh 'claude -p'
    in the gap between the leaf-kill snapshot and the worker-kill
    enumeration. Killing the orchestrator + xargs first eliminates the
    dispatcher; existing 'claude -p' children become orphans (no parent to
    respawn them) and are reaped in Stage B.

    REMAINING RACE WINDOW. Stage A's CIM enumeration is itself a synchronous
    WMI call (200ms-2s under load). A worker that's mid-spawn at the
    snapshot moment may produce a fresh 'claude -p' that's not in Stage A's
    snapshot. That fresh PID has no parent to respawn it (its parent is in
    Stage A's kill list), so it survives only until Stage B reaps it OR the
    next iteration's recount catches it. The 3-iteration loop converges
    where a single pass would not.

    Exit codes:
      0 -- both pools reached 0 within 3 iterations.
      1 -- residual processes after 3 iterations. Investigate manually:
           Get-CimInstance Win32_Process -Filter "name='bash.exe'" |
               Where-Object { $_.CommandLine -match '<workerPattern>' }
#>

$ErrorActionPreference = 'Continue'

# F-bis (Phase E): panic-stop audit state. Accumulates argv from each kill
# stage across passes; a single audit FindingFile is emitted after the
# convergence loop exits. Audit is best-effort -- write failure logs WARN
# but does not affect the kill outcome.
$script:scriptStart = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$script:allKills = @()
$script:repo = if ($env:IOCANE_REPO_ROOT) { $env:IOCANE_REPO_ROOT } else { (Get-Location).Path }

# Match bash invocations of harness wire-tests scripts ONLY -- the path prefix
# and .sh suffix prevent collateral kills of unrelated bash sessions whose
# command lines happen to contain a script name (e.g. `vim run_actor_critic_loop.sh`,
# `grep io-wire-tests`, log-tailing, etc.). Path matches both forward and back slash.
$workerPattern = '\.claude[/\\]scripts[/\\](run_actor_critic_loop|spawn-test-author|spawn-test-critic|io-wire-tests-cdt|io-wire-tests-ct)\.sh'
$leafPattern = ' -p '
$maxIterations = 3
$settleSeconds = 3

function Get-WireTestWorkers {
    @(Get-CimInstance Win32_Process -Filter "name='bash.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine -match $workerPattern })
}

function Get-WireTestLeaves {
    @(Get-CimInstance Win32_Process -Filter "name='claude.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine -match $leafPattern })
}

function Get-KillRecord {
    # Capture argv BEFORE Stop-Process so the audit has command-line context.
    # target_id is extracted from --target-id <id>; orchestrator processes
    # have no --target-id arg and are tagged as 'orchestrator'; null/missing
    # CommandLine yields 'unknown' (race or permission denial).
    param($p, [string]$stage, [int]$iter)
    $cmd = if ($p.CommandLine) { $p.CommandLine } else { '' }
    if ($cmd -match '--target-id\s+(\S+)') {
        $tid = $matches[1]
    } elseif ($cmd -match 'io-wire-tests-(cdt|ct)\.sh') {
        $tid = 'orchestrator'
    } else {
        $tid = 'unknown'
    }
    $excerpt = if ($cmd) { $cmd.Substring(0, [Math]::Min(200, $cmd.Length)) } else { '' }
    return [pscustomobject]@{
        PID = $p.ProcessId
        CommandExcerpt = $excerpt
        TargetId = $tid
        Pass = $iter
        Stage = $stage
    }
}

function Yaml-EscapeSingle {
    # YAML single-quoted strings escape only ' as ''. No backslash issues
    # (which makes single-quoted strings the right choice for Windows paths).
    param([string]$s)
    if ($null -eq $s) { return '' }
    return ($s -replace "'", "''")
}

function Emit-PanicStopAudit {
    param([bool]$converged, [int]$finalPass)

    if ($script:allKills.Count -eq 0) {
        Write-Host "panic-stop audit: no processes matched; skipping audit emission"
        return
    }

    $endTime = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
    $exitCode = if ($converged) { 0 } else { 1 }

    $findingsDir = Join-Path $script:repo '.iocane/findings'
    if (-not (Test-Path $findingsDir)) {
        try { New-Item -ItemType Directory -Path $findingsDir -Force | Out-Null }
        catch {
            Write-Host "WARN: panic-stop audit: failed to create $findingsDir; skipping audit emission ($_)"
            return
        }
    }
    $auditPath = Join-Path $findingsDir "wire_test_panic_stop_audit-$stamp.yaml"

    # result_file_state: snapshot of author-result + critic JSON files
    # remaining on disk at audit time. Any size could be partial-write --
    # mid-write SIGKILL can leave non-zero bytes that don't parse as JSON.
    # Operators should validate JSON parse before trusting any entry; size
    # is a hint, not a guarantee of completeness.
    $wireTestsDir = Join-Path $script:repo '.iocane/wire-tests'
    $resultFiles = @()
    if (Test-Path $wireTestsDir) {
        $resultFiles += @(Get-ChildItem -Path $wireTestsDir -Filter 'author-result-*.json' -ErrorAction SilentlyContinue)
        $resultFiles += @(Get-ChildItem -Path $wireTestsDir -Filter 'critic_*.json' -ErrorAction SilentlyContinue)
    }

    $cwd = (Get-Location).Path
    $invoker = if ($env:USERNAME) { $env:USERNAME } else { 'unknown' }

    $sb = New-Object System.Text.StringBuilder
    [void]$sb.AppendLine('role: wire_test_panic_stop')
    [void]$sb.AppendLine('context:')
    [void]$sb.AppendLine("  invoking_user: '$(Yaml-EscapeSingle $invoker)'")
    [void]$sb.AppendLine("  working_dir: '$(Yaml-EscapeSingle $cwd)'")
    [void]$sb.AppendLine("  start_time: '$($script:scriptStart)'")
    [void]$sb.AppendLine("  end_time: '$endTime'")
    [void]$sb.AppendLine("  pass_count: $finalPass")
    [void]$sb.AppendLine("  final_exit_code: $exitCode")
    [void]$sb.AppendLine('defect_kind: panic_stop_audit')
    [void]$sb.AppendLine('affected_artifacts: []')
    [void]$sb.AppendLine('diagnosis:')
    [void]$sb.AppendLine("  what: 'panic-stop killed $($script:allKills.Count) process(es) across $finalPass pass(es)'")
    [void]$sb.AppendLine("  where: 'wire-tests-panic-stop.ps1 invocation start=$($script:scriptStart) end=$endTime'")
    [void]$sb.AppendLine("  why: 'Operator-initiated force-stop of wire-tests run'")
    [void]$sb.AppendLine('remediation:')
    [void]$sb.AppendLine('  root_cause_layer: wire_tests')
    [void]$sb.AppendLine('  fix_steps:')
    [void]$sb.AppendLine("    - 'Review killed_processes list for what was running at kill time'")
    [void]$sb.AppendLine("    - 'Review result_file_state for 0-byte or partial-write artifacts to clean up before re-running'")
    [void]$sb.AppendLine('killed_processes:')
    foreach ($k in $script:allKills) {
        $excerpt = $k.CommandExcerpt -replace '[\r\n]', ' '
        [void]$sb.AppendLine("  - pid: $($k.PID)")
        [void]$sb.AppendLine("    command_excerpt: '$(Yaml-EscapeSingle $excerpt)'")
        [void]$sb.AppendLine("    target_id: '$(Yaml-EscapeSingle $k.TargetId)'")
        [void]$sb.AppendLine("    pass: $($k.Pass)")
        [void]$sb.AppendLine("    stage: '$($k.Stage)'")
    }
    if ($resultFiles.Count -eq 0) {
        [void]$sb.AppendLine('result_file_state: []')
    } else {
        [void]$sb.AppendLine('result_file_state:')
        foreach ($f in $resultFiles) {
            $relPath = ".iocane/wire-tests/$($f.Name)"
            [void]$sb.AppendLine("  - path: '$(Yaml-EscapeSingle $relPath)'")
            [void]$sb.AppendLine("    size_bytes: $($f.Length)")
        }
    }

    try {
        $tmp = "$auditPath.tmp"
        $utf8NoBom = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::WriteAllText($tmp, $sb.ToString(), $utf8NoBom)
        Move-Item -Path $tmp -Destination $auditPath -Force
        Write-Host "panic-stop audit: wrote $auditPath"
    }
    catch {
        Write-Host "WARN: panic-stop audit: failed to write $auditPath ($_)"
    }
}

function Invoke-Sweep {
    param([int]$iter)

    Write-Host "--- Pass $iter / $maxIterations ---"

    Write-Host "  Stage A: killing bash workers (parents)..."
    $workers = Get-WireTestWorkers
    foreach ($p in $workers) {
        $script:allKills += Get-KillRecord -p $p -stage 'A' -iter $iter
        Write-Host "    killing PID $($p.ProcessId)"
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Write-Host "    killed: $($workers.Count)"

    Write-Host "  Stage B: killing leaf 'claude -p' (orphaned)..."
    $leaves = Get-WireTestLeaves
    foreach ($p in $leaves) {
        $script:allKills += Get-KillRecord -p $p -stage 'B' -iter $iter
        Write-Host "    killing PID $($p.ProcessId)"
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Write-Host "    killed: $($leaves.Count)"

    Start-Sleep -Seconds $settleSeconds

    $workersRemaining = (Get-WireTestWorkers).Count
    $leavesRemaining  = (Get-WireTestLeaves).Count

    Write-Host "  remaining: workers=$workersRemaining leaves=$leavesRemaining"
    return ($workersRemaining + $leavesRemaining)
}

$converged = $false
$finalPass = 0
for ($i = 1; $i -le $maxIterations; $i++) {
    $residual = Invoke-Sweep -iter $i
    $finalPass = $i
    if ($residual -eq 0) {
        $converged = $true
        Write-Host ""
        Write-Host "OK: all wire-tests subprocesses terminated (converged at pass $i)."
        break
    }
}

# F-bis: emit single audit FindingFile after convergence (or exhaustion).
# Best-effort -- audit failure does not affect kill outcome.
Emit-PanicStopAudit -converged $converged -finalPass $finalPass

if (-not $converged) {
    Write-Host ""
    Write-Host "WARN: residual processes after $maxIterations passes."
    Write-Host "      Re-run this script, or investigate manually with: Get-Process bash, claude"
    exit 1
}
exit 0

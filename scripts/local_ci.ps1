[CmdletBinding()]
param(
    [ValidateSet("all", "test", "code-quality", "security-scan", "build-docs", "performance", "integration-test", "release")]
    [string[]]$Jobs = @("all"),
    [switch]$IncludeRelease,
    [switch]$SkipInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:SoftFailures = @()
$script:JobResults = @()
$script:JobState = @{}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

function Write-JobHeader {
    param([string]$Name)

    Write-Host ""
    Write-Host ("=" * 72) -ForegroundColor DarkGray
    Write-Host ("[JOB] {0}" -f $Name) -ForegroundColor Cyan
    Write-Host ("=" * 72) -ForegroundColor DarkGray
}

function Invoke-Step {
    param(
        [string]$JobName,
        [string]$StepName,
        [scriptblock[]]$Commands,
        [switch]$AllowFailure
    )

    Write-Host ("[{0}] {1}" -f $JobName, $StepName) -ForegroundColor Yellow

    $failureReason = $null
    foreach ($cmd in $Commands) {
        $commandText = ($cmd.ToString().Trim() -replace "\s+", " ")
        if ($commandText.Length -gt 140) {
            $commandText = $commandText.Substring(0, 137) + "..."
        }
        Write-Host ("  > {0}" -f $commandText) -ForegroundColor DarkGray

        $global:LASTEXITCODE = 0
        try {
            & $cmd
        } catch {
            $failureReason = $_.Exception.Message
            break
        }

        if ($LASTEXITCODE -ne 0) {
            $failureReason = "Exited with code $LASTEXITCODE"
            break
        }
    }

    if ($null -ne $failureReason) {
        $message = ("[{0}] {1} failed: {2}" -f $JobName, $StepName, $failureReason)
        if ($AllowFailure) {
            Write-Warning ($message + " (continue-on-error)")
            $script:SoftFailures += $message
            return
        }
        throw $message
    }

    Write-Host ("[{0}] {1} passed" -f $JobName, $StepName) -ForegroundColor Green
}

function Invoke-Job {
    param(
        [string]$Name,
        [scriptblock]$Body,
        [string[]]$Needs = @()
    )

    $missingDeps = @()
    foreach ($dep in $Needs) {
        if (-not $script:JobState.ContainsKey($dep) -or $script:JobState[$dep] -ne "passed") {
            $missingDeps += $dep
        }
    }

    if ($missingDeps.Count -gt 0) {
        Write-JobHeader $Name
        $reason = "skipped (needs: {0})" -f ($missingDeps -join ", ")
        Write-Host ("[{0}] {1}" -f $Name, $reason) -ForegroundColor DarkYellow
        $script:JobState[$Name] = "skipped"
        $script:JobResults += [PSCustomObject]@{
            Job      = $Name
            Status   = "skipped"
            Duration = 0
        }
        return
    }

    Write-JobHeader $Name
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        & $Body
        $sw.Stop()
        $script:JobState[$Name] = "passed"
        $script:JobResults += [PSCustomObject]@{
            Job      = $Name
            Status   = "passed"
            Duration = [Math]::Round($sw.Elapsed.TotalSeconds, 2)
        }
    } catch {
        $sw.Stop()
        $script:JobState[$Name] = "failed"
        $script:JobResults += [PSCustomObject]@{
            Job      = $Name
            Status   = "failed"
            Duration = [Math]::Round($sw.Elapsed.TotalSeconds, 2)
        }
        Write-Error $_
    }
}

function Resolve-SelectedJobs {
    $defaultOrder = @("test", "code-quality", "security-scan", "build-docs", "performance", "integration-test")
    if ($IncludeRelease) {
        $defaultOrder += "release"
    }

    if ($Jobs -contains "all") {
        return $defaultOrder
    }

    $selected = @()
    foreach ($candidate in $defaultOrder) {
        if ($Jobs -contains $candidate) {
            $selected += $candidate
        }
    }

    if (($Jobs -contains "release") -and ($selected -notcontains "release")) {
        $selected += "release"
    }

    return $selected
}

$selectedJobs = @(Resolve-SelectedJobs)

if ($selectedJobs.Count -eq 0) {
    throw "No runnable jobs selected."
}

Write-Host ("Repo root: {0}" -f $repoRoot) -ForegroundColor Gray
Write-Host ("Selected jobs: {0}" -f ($selectedJobs -join ", ")) -ForegroundColor Gray
Write-Host ("Skip install: {0}" -f $SkipInstall.IsPresent) -ForegroundColor Gray

foreach ($job in $selectedJobs) {
    switch ($job) {
        "test" {
            Invoke-Job -Name "test" -Body {
                if (-not $SkipInstall) {
                    Invoke-Step -JobName "test" -StepName "Install dependencies" -Commands @(
                        { python -m pip install --upgrade pip },
                        { pip install -r requirements.txt },
                        { pip install pytest pytest-cov pytest-xdist }
                    )
                }
                Invoke-Step -JobName "test" -StepName "Run tests" -Commands @(
                    { python -m pytest tests/ -v --tb=short }
                )
            }
        }
        "code-quality" {
            Invoke-Job -Name "code-quality" -Body {
                if (-not $SkipInstall) {
                    Invoke-Step -JobName "code-quality" -StepName "Install linting tools" -Commands @(
                        { python -m pip install --upgrade pip },
                        { pip install flake8 black isort mypy pylint }
                    )
                }
                Invoke-Step -JobName "code-quality" -StepName "Black check" -AllowFailure -Commands @(
                    { black --check src/ tests/ }
                )
                Invoke-Step -JobName "code-quality" -StepName "isort check" -AllowFailure -Commands @(
                    { isort --check-only src/ tests/ }
                )
                Invoke-Step -JobName "code-quality" -StepName "Flake8 lint" -AllowFailure -Commands @(
                    { flake8 src/ tests/ --max-line-length=120 --extend-ignore=E203,W503 }
                )
                Invoke-Step -JobName "code-quality" -StepName "Pylint" -AllowFailure -Commands @(
                    { pylint src/ --disable=C0111,R0913,R0914,R0915 }
                )
            }
        }
        "security-scan" {
            Invoke-Job -Name "security-scan" -Body {
                if (-not $SkipInstall) {
                    Invoke-Step -JobName "security-scan" -StepName "Install security tools" -Commands @(
                        { python -m pip install --upgrade pip },
                        { pip install bandit safety }
                    )
                }
                Invoke-Step -JobName "security-scan" -StepName "Bandit scan" -AllowFailure -Commands @(
                    { bandit -r src/ -f json -o bandit-report.json }
                )
                Invoke-Step -JobName "security-scan" -StepName "Safety check" -AllowFailure -Commands @(
                    { safety check --json }
                )
            }
        }
        "build-docs" {
            Invoke-Job -Name "build-docs" -Body {
                if (-not $SkipInstall) {
                    Invoke-Step -JobName "build-docs" -StepName "Install docs dependencies" -Commands @(
                        { python -m pip install --upgrade pip },
                        { pip install -r requirements.txt },
                        { pip install sphinx sphinx-rtd-theme }
                    )
                }
                Invoke-Step -JobName "build-docs" -StepName "Build docs" -AllowFailure -Commands @(
                    {
                        if (Test-Path "docs/conf.py") {
                            python -m sphinx -b html docs docs/_build/html
                        } else {
                            Write-Host "No Sphinx docs configured yet"
                        }
                    }
                )
            }
        }
        "performance" {
            Invoke-Job -Name "performance" -Needs @("test") -Body {
                if (-not $SkipInstall) {
                    Invoke-Step -JobName "performance" -StepName "Install dependencies" -Commands @(
                        { python -m pip install --upgrade pip },
                        { pip install -r requirements.txt }
                    )
                }
                Invoke-Step -JobName "performance" -StepName "Run benchmark gate" -Commands @(
                    {
                        if (-not (Test-Path "benchmark_baselines")) {
                            New-Item -ItemType Directory -Path "benchmark_baselines" | Out-Null
                        }
                    },
                    {
                        python scripts/benchmark_platform.py `
                            --jobs 20 --workers 2 --sleep-ms 5 `
                            --check-thresholds `
                            --save-baseline --baseline-dir benchmark_baselines `
                            --check-regression --baseline-dir benchmark_baselines
                    }
                )
            }
        }
        "integration-test" {
            Invoke-Job -Name "integration-test" -Needs @("test") -Body {
                if (-not $SkipInstall) {
                    Invoke-Step -JobName "integration-test" -StepName "Install dependencies" -Commands @(
                        { python -m pip install --upgrade pip },
                        { pip install -r requirements.txt }
                    )
                }
                Invoke-Step -JobName "integration-test" -StepName "Run integration tests" -AllowFailure -Commands @(
                    { python -m pytest tests/ -m "integration" -v }
                )
                Invoke-Step -JobName "integration-test" -StepName "Test CLI commands" -Commands @(
                    { python unified_backtest_framework.py --help },
                    { python unified_backtest_framework.py list-strategies }
                )
            }
        }
        "release" {
            Invoke-Job -Name "release" -Needs @("test", "code-quality", "security-scan", "performance") -Body {
                if (-not $SkipInstall) {
                    Invoke-Step -JobName "release" -StepName "Install build package" -Commands @(
                        { python -m pip install --upgrade pip build }
                    )
                }
                Invoke-Step -JobName "release" -StepName "Build dist package" -Commands @(
                    { python -m build }
                )
            }
        }
    }
}

Write-Host ""
Write-Host ("=" * 72) -ForegroundColor DarkGray
Write-Host "Summary" -ForegroundColor Cyan
Write-Host ("=" * 72) -ForegroundColor DarkGray

$script:JobResults | Format-Table -AutoSize

if ($script:SoftFailures.Count -gt 0) {
    Write-Host ""
    Write-Host "continue-on-error steps with failures:" -ForegroundColor DarkYellow
    foreach ($soft in $script:SoftFailures) {
        Write-Host ("- {0}" -f $soft) -ForegroundColor DarkYellow
    }
}

$hardFailedJobs = @($script:JobResults | Where-Object { $_.Status -eq "failed" })
if ($hardFailedJobs.Count -gt 0) {
    Write-Host ""
    Write-Error ("Local CI failed. Hard failed jobs: {0}" -f (($hardFailedJobs.Job) -join ", "))
    exit 1
}

Write-Host ""
Write-Host "Local CI finished without hard failures." -ForegroundColor Green
if ($script:SoftFailures.Count -gt 0) {
    Write-Host "Some continue-on-error steps failed. Review warnings above." -ForegroundColor DarkYellow
}
exit 0

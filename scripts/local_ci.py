#!/usr/bin/env python3
"""Cross-platform local CI runner.

This mirrors ``scripts/local_ci.ps1`` for macOS/Linux environments where
PowerShell is not installed. The job names and default ordering intentionally
match the PowerShell runner so documentation and GitHub Actions parity stay
simple.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

ALLOWED_JOBS = {
    "all",
    "test",
    "runtime-smoke",
    "gateway-integration",
    "code-quality",
    "security-scan",
    "build-docs",
    "frontend-check",
    "docker-validate",
    "performance",
    "integration-test",
    "preflight-gate",
    "release",
}
DEFAULT_ORDER = [
    "test",
    "runtime-smoke",
    "code-quality",
    "security-scan",
    "build-docs",
    "frontend-check",
    "docker-validate",
    "performance",
    "integration-test",
]


@dataclass
class Step:
    name: str
    commands: List[Sequence[str]]
    cwd: Path = REPO_ROOT
    allow_failure: bool = False


@dataclass
class JobResult:
    job: str
    status: str
    duration: float


class LocalCI:
    def __init__(self, *, jobs: List[str], skip_install: bool, include_release: bool) -> None:
        self.requested_jobs = jobs
        self.skip_install = skip_install
        self.include_release = include_release
        self.soft_failures: List[str] = []
        self.job_state: Dict[str, str] = {}
        self.results: List[JobResult] = []

    def resolve_jobs(self) -> List[str]:
        selected = list(DEFAULT_ORDER)
        if self.include_release:
            selected.append("release")
        if "all" not in self.requested_jobs:
            selected = [job for job in selected if job in self.requested_jobs]

        release_requested = "release" in self.requested_jobs or "release" in selected
        for optional_job in ("preflight-gate", "gateway-integration"):
            if optional_job in self.requested_jobs and optional_job not in selected:
                selected.append(optional_job)
        if "release" in self.requested_jobs and "release" not in selected:
            selected.append("release")

        if release_requested:
            selected = [job for job in selected if job != "preflight-gate"]
            try:
                release_index = selected.index("release")
            except ValueError:
                selected.append("preflight-gate")
            else:
                selected.insert(release_index, "preflight-gate")

        if not selected:
            raise SystemExit("No runnable jobs selected.")
        return selected

    def run(self) -> int:
        selected_jobs = self.resolve_jobs()
        print(f"Repo root: {REPO_ROOT}")
        print(f"Selected jobs: {', '.join(selected_jobs)}")
        print(f"Skip install: {self.skip_install}")

        job_map: Dict[str, Callable[[], None]] = {
            "test": self.job_test,
            "runtime-smoke": self.job_runtime_smoke,
            "gateway-integration": self.job_gateway_integration,
            "code-quality": self.job_code_quality,
            "security-scan": self.job_security_scan,
            "build-docs": self.job_build_docs,
            "frontend-check": self.job_frontend_check,
            "docker-validate": self.job_docker_validate,
            "performance": self.job_performance,
            "integration-test": self.job_integration_test,
            "preflight-gate": self.job_preflight_gate,
            "release": self.job_release,
        }

        needs = {
            "docker-validate": ["test"],
            "performance": ["test"],
            "integration-test": ["test"],
            "preflight-gate": ["test", "code-quality", "security-scan"],
            "release": ["test", "runtime-smoke", "code-quality", "security-scan", "performance", "preflight-gate"],
        }

        for job in selected_jobs:
            self.invoke_job(job, job_map[job], needs=needs.get(job, []))

        self.print_summary()
        hard_failed = [result.job for result in self.results if result.status == "failed"]
        if hard_failed:
            print(f"\nLocal CI failed. Hard failed jobs: {', '.join(hard_failed)}", file=sys.stderr)
            return 1
        print("\nLocal CI finished without hard failures.")
        if self.soft_failures:
            print("Some continue-on-error steps failed. Review warnings above.")
        return 0

    def invoke_job(self, name: str, body: Callable[[], None], *, needs: List[str]) -> None:
        missing = [dep for dep in needs if self.job_state.get(dep) != "passed"]
        self.write_header(name)
        if missing:
            reason = f"skipped (needs: {', '.join(missing)})"
            print(f"[{name}] {reason}")
            self.job_state[name] = "skipped"
            self.results.append(JobResult(name, "skipped", 0.0))
            return

        started = time.monotonic()
        try:
            body()
        except Exception as exc:
            self.job_state[name] = "failed"
            self.results.append(JobResult(name, "failed", round(time.monotonic() - started, 2)))
            print(f"[{name}] failed: {exc}", file=sys.stderr)
            return
        self.job_state[name] = "passed"
        self.results.append(JobResult(name, "passed", round(time.monotonic() - started, 2)))

    def invoke_step(self, job_name: str, step: Step) -> None:
        print(f"[{job_name}] {step.name}")
        failure: str | None = None
        for command in step.commands:
            display = " ".join(command)
            if len(display) > 160:
                display = display[:157] + "..."
            print(f"  > {display}")
            try:
                subprocess.run(command, cwd=step.cwd, check=True)
            except (OSError, subprocess.CalledProcessError) as exc:
                failure = str(exc)
                break

        if failure:
            message = f"[{job_name}] {step.name} failed: {failure}"
            if step.allow_failure:
                print(f"WARNING: {message} (continue-on-error)")
                self.soft_failures.append(message)
                return
            raise RuntimeError(message)
        print(f"[{job_name}] {step.name} passed")

    def maybe_install(self, job_name: str, commands: List[Sequence[str]], step_name: str = "Install dependencies") -> None:
        if not self.skip_install:
            self.invoke_step(job_name, Step(step_name, commands))

    def job_test(self) -> None:
        self.maybe_install(
            "test",
            [
                [PYTHON, "-m", "pip", "install", "--upgrade", "pip"],
                [PYTHON, "-m", "pip", "install", "-r", "requirements.txt"],
                [PYTHON, "-m", "pip", "install", "pytest", "pytest-cov", "pytest-xdist"],
            ],
        )
        self.invoke_step(
            "test",
            Step(
                "Run strategy smoke gate",
                [[PYTHON, "-m", "pytest", "tests/test_strategy_backtest_contracts.py", "-v", "--tb=short", "-x"]],
            ),
        )
        self.invoke_step(
            "test",
            Step(
                "Run tests",
                [[PYTHON, "-m", "pytest", "tests/", "-v", "--tb=short", "--ignore=tests/test_strategy_backtest_contracts.py"]],
            ),
        )

    def job_code_quality(self) -> None:
        self.maybe_install(
            "code-quality",
            [
                [PYTHON, "-m", "pip", "install", "--upgrade", "pip"],
                [PYTHON, "-m", "pip", "install", "ruff", "mypy", "types-PyYAML", "types-requests"],
                [PYTHON, "-m", "pip", "install", "-r", "requirements.txt"],
            ],
            "Install linting tools",
        )
        self.invoke_step("code-quality", Step("Ruff lint", [[PYTHON, "-m", "ruff", "check", "src/"]]))
        self.invoke_step(
            "code-quality",
            Step(
                "MyPy type check",
                [
                    [
                        PYTHON,
                        "-m",
                        "mypy",
                        "src/core/exceptions.py",
                        "src/core/input_sanitizer.py",
                        "src/core/plugin.py",
                        "--ignore-missing-imports",
                        "--follow-imports=skip",
                    ]
                ],
            ),
        )

    def job_runtime_smoke(self) -> None:
        self.maybe_install(
            "runtime-smoke",
            [[PYTHON, "-m", "pip", "install", "--upgrade", "pip"], [PYTHON, "-m", "pip", "install", "-r", "requirements.txt"]],
        )
        self.invoke_step(
            "runtime-smoke",
            Step(
                "Run gateway and realtime smoke tests",
                [
                    [
                        PYTHON,
                        "-m",
                        "pytest",
                        "tests/test_gateway_xtquant_smoke.py",
                        "tests/test_gateway_xtp_smoke.py",
                        "tests/test_gateway_uft_smoke.py",
                        "tests/test_gateway_mock_sdk.py",
                        "tests/test_realtime_data.py",
                        "tests/test_config_schema.py::TestGlobalConfig::test_default_config_valid",
                        "tests/test_config_schema.py::TestGlobalConfig::test_realtime_data_config_validation",
                        "tests/test_config_schema.py::TestGlobalConfig::test_realtime_data_default_bar_intervals",
                        "-v",
                        "--tb=short",
                        "-x",
                    ]
                ],
            ),
        )

    def job_gateway_integration(self) -> None:
        self.maybe_install(
            "gateway-integration",
            [[PYTHON, "-m", "pip", "install", "--upgrade", "pip"], [PYTHON, "-m", "pip", "install", "-r", "requirements.txt"]],
        )
        self.invoke_step(
            "gateway-integration",
            Step(
                "Run live SDK integration smoke",
                [
                    [
                        PYTHON,
                        "-m",
                        "pytest",
                        "tests/test_gateway_xtquant_integration.py",
                        "tests/test_gateway_xtp_integration.py",
                        "tests/test_gateway_uft_integration.py",
                        "-m",
                        "integration",
                        "-v",
                        "--tb=short",
                        "-x",
                    ]
                ],
            ),
        )

    def job_security_scan(self) -> None:
        self.maybe_install(
            "security-scan",
            [[PYTHON, "-m", "pip", "install", "--upgrade", "pip"], [PYTHON, "-m", "pip", "install", "bandit", "safety"]],
            "Install security tools",
        )
        self.invoke_step(
            "security-scan",
            Step("Bandit scan", [["bandit", "-r", "src/", "-f", "json", "-o", "bandit-report.json"]], allow_failure=True),
        )
        self.invoke_step("security-scan", Step("Safety check", [["safety", "check", "--json"]], allow_failure=True))

    def job_build_docs(self) -> None:
        self.maybe_install(
            "build-docs",
            [
                [PYTHON, "-m", "pip", "install", "--upgrade", "pip"],
                [PYTHON, "-m", "pip", "install", "-r", "requirements.txt"],
                [PYTHON, "-m", "pip", "install", "mkdocs", "mkdocs-material", "pymdown-extensions"],
            ],
            "Install docs dependencies",
        )
        self.invoke_step("build-docs", Step("Build MkDocs site", [[PYTHON, "-m", "mkdocs", "build", "--strict"]]))

    def job_frontend_check(self) -> None:
        if not self.skip_install:
            self.invoke_step("frontend-check", Step("Install frontend dependencies", [["npm", "ci"]], cwd=REPO_ROOT / "frontend"))
        self.invoke_step("frontend-check", Step("Type check frontend", [["npx", "vue-tsc", "-b", "--noEmit"]], cwd=REPO_ROOT / "frontend"))
        self.invoke_step("frontend-check", Step("Build frontend", [["npm", "run", "build"]], cwd=REPO_ROOT / "frontend"))

    def job_docker_validate(self) -> None:
        self.invoke_step("docker-validate", Step("Validate Dockerfile", [["docker", "build", "--target", "production", "-t", "quant-platform:test", "."]]))
        self.invoke_step("docker-validate", Step("Validate docker-compose", [["docker", "compose", "config"]]))

    def job_performance(self) -> None:
        self.maybe_install(
            "performance",
            [[PYTHON, "-m", "pip", "install", "--upgrade", "pip"], [PYTHON, "-m", "pip", "install", "-r", "requirements.txt"]],
        )
        (REPO_ROOT / "benchmark_baselines").mkdir(exist_ok=True)
        self.invoke_step(
            "performance",
            Step(
                "Run benchmark gate",
                [
                    [
                        PYTHON,
                        "scripts/benchmark_platform.py",
                        "--jobs",
                        "20",
                        "--workers",
                        "2",
                        "--sleep-ms",
                        "5",
                        "--check-thresholds",
                        "--save-baseline",
                        "--baseline-dir",
                        "benchmark_baselines",
                        "--check-regression",
                        "--baseline-dir",
                        "benchmark_baselines",
                    ]
                ],
            ),
        )

    def job_integration_test(self) -> None:
        self.maybe_install(
            "integration-test",
            [[PYTHON, "-m", "pip", "install", "--upgrade", "pip"], [PYTHON, "-m", "pip", "install", "-r", "requirements.txt"]],
        )
        self.invoke_step("integration-test", Step("Run integration tests", [[PYTHON, "-m", "pytest", "tests/", "-m", "integration", "-v"]], allow_failure=True))
        self.invoke_step(
            "integration-test",
            Step("Test CLI commands", [[PYTHON, "unified_backtest_framework.py", "--help"], [PYTHON, "unified_backtest_framework.py", "list-strategies"]]),
        )

    def job_preflight_gate(self) -> None:
        self.maybe_install(
            "preflight-gate",
            [[PYTHON, "-m", "pip", "install", "--upgrade", "pip"], [PYTHON, "-m", "pip", "install", "-r", "requirements.txt"]],
        )
        self.invoke_step(
            "preflight-gate",
            Step(
                "Run launch preflight decision gate",
                [
                    [
                        PYTHON,
                        "scripts/start_production.py",
                        "--preflight",
                        "--preflight-platform-run",
                        "--preflight-platform-limit",
                        "3",
                        "--preflight-auto-regression",
                        "--preflight-auto-rounds",
                        "2",
                        "--preflight-use-best",
                        "--preflight-decision-only",
                        "--preflight-fail-on-review",
                        "--preflight-decision-file",
                        "report/preflight_gate.json",
                        "--preflight-decision-seed-file",
                        "report/preflight_decision_latest.json",
                    ]
                ],
            ),
        )

    def job_release(self) -> None:
        if not self.skip_install:
            self.invoke_step("release", Step("Install build package", [[PYTHON, "-m", "pip", "install", "--upgrade", "pip", "build"]]))
        self.invoke_step("release", Step("Build dist package", [[PYTHON, "-m", "build"]]))

    @staticmethod
    def write_header(name: str) -> None:
        print()
        print("=" * 72)
        print(f"[JOB] {name}")
        print("=" * 72)

    def print_summary(self) -> None:
        print()
        print("=" * 72)
        print("Summary")
        print("=" * 72)
        width = max([len("Job"), *(len(result.job) for result in self.results)])
        print(f"{'Job'.ljust(width)}  Status   Duration")
        print(f"{'-' * width}  -------  --------")
        for result in self.results:
            print(f"{result.job.ljust(width)}  {result.status.ljust(7)}  {result.duration:.2f}s")
        if self.soft_failures:
            print("\ncontinue-on-error steps with failures:")
            for soft in self.soft_failures:
                print(f"- {soft}")


def parse_jobs(raw_jobs: Iterable[str]) -> List[str]:
    jobs: List[str] = []
    for raw in raw_jobs:
        jobs.extend(item.strip() for item in raw.split(",") if item.strip())
    return jobs or ["all"]


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cross-platform local CI runner")
    parser.add_argument("--jobs", "-Jobs", nargs="*", default=["all"], help="Jobs to run, comma-separated or space-separated")
    parser.add_argument("--include-release", "-IncludeRelease", action="store_true", help="Include release job when running all")
    parser.add_argument("--skip-install", "-SkipInstall", action="store_true", help="Skip dependency installation steps")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    jobs = parse_jobs(args.jobs)
    invalid = sorted(set(jobs) - ALLOWED_JOBS)
    if invalid:
        allowed = ", ".join(sorted(ALLOWED_JOBS))
        raise SystemExit(f"Unsupported job(s): {', '.join(invalid)}. Allowed jobs: {allowed}")

    os.chdir(REPO_ROOT)
    return LocalCI(jobs=jobs, skip_install=bool(args.skip_install), include_release=bool(args.include_release)).run()


if __name__ == "__main__":
    raise SystemExit(main())

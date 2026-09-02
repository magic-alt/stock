"""Contract tests for Gate 0 CI and repository-governance declarations."""
from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CI_PATH = ROOT / ".github" / "workflows" / "ci.yml"
DEPENDABOT_PATH = ROOT / ".github" / "dependabot.yml"
RULESET_PATH = ROOT / ".github" / "ruleset-main.example.json"
PACKAGE_JSON_PATH = ROOT / "frontend" / "package.json"
PACKAGE_LOCK_PATH = ROOT / "frontend" / "package-lock.json"
PYPROJECT_PATH = ROOT / "pyproject.toml"


def _load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_python_ci_matrix_matches_declared_supported_versions():
    workflow = _load_yaml(CI_PATH)
    versions = workflow["jobs"]["python-tests"]["strategy"]["matrix"]["python-version"]
    assert versions == ["3.10", "3.11", "3.12"]

    pyproject = PYPROJECT_PATH.read_text(encoding="utf-8")
    assert 'requires-python = ">=3.10"' in pyproject
    for version in versions:
        assert f'"Programming Language :: Python :: {version}"' in pyproject


def test_required_checks_is_stable_fail_closed_aggregate():
    workflow = _load_yaml(CI_PATH)
    required = workflow["jobs"]["required-checks"]
    assert required["name"] == "Required Checks"
    assert required["if"] == "always()"
    assert set(required["needs"]) == {
        "python-tests",
        "windows-tests",
        "code-quality",
        "security-gate",
        "frontend-check",
        "packaging-smoke",
        "build-docs",
        "docker-validate",
        "integration-test",
        "performance",
    }

    raw = CI_PATH.read_text(encoding="utf-8")
    assert 'if [ "${result}" != "success" ]' in raw
    assert "|| pip install -r requirements.txt" not in raw
    assert 'pytest tests/ -m "integration"' in raw
    assert '|| echo "No integration tests found"' not in raw


def test_security_gate_is_blocking_and_baseline_is_explicitly_informational():
    workflow = _load_yaml(CI_PATH)
    required_security = workflow["jobs"]["security-gate"]
    informational = workflow["jobs"]["security-baseline"]

    assert required_security["name"] == "Security Gate"
    assert "continue-on-error" not in required_security
    required_commands = "\n".join(
        str(step.get("run", "")) for step in required_security["steps"]
    )
    assert "bandit -r src/" in required_commands
    assert " -lll" in required_commands
    assert "pip-audit -r requirements.txt" in required_commands
    assert "|| true" not in required_commands

    assert "informational" in informational["name"].lower()
    assert "security-baseline" not in workflow["jobs"]["required-checks"]["needs"]


def test_frontend_lint_and_high_severity_audit_are_locked_and_required():
    workflow = _load_yaml(CI_PATH)
    frontend = workflow["jobs"]["frontend-check"]
    frontend_commands = "\n".join(str(step.get("run", "")) for step in frontend["steps"])
    assert "npm ci" in frontend_commands
    assert "npm run lint" in frontend_commands
    assert "vue-tsc -b --noEmit" in frontend_commands
    assert "npm run build" in frontend_commands

    package_json = json.loads(PACKAGE_JSON_PATH.read_text(encoding="utf-8"))
    package_lock = json.loads(PACKAGE_LOCK_PATH.read_text(encoding="utf-8"))
    scripts = package_json["scripts"]
    assert scripts["security:audit"] == "npm audit --audit-level=high"
    assert scripts["prelint"] == "npm run security:audit"
    assert scripts["lint"] == "eslint . --max-warnings=0"
    for dependency in ("eslint", "eslint-plugin-vue", "globals", "typescript-eslint"):
        assert dependency in package_json["devDependencies"]
        assert package_lock["packages"][""]["devDependencies"][dependency] == package_json["devDependencies"][dependency]


def test_packaging_smoke_builds_and_executes_installed_wheel():
    workflow = _load_yaml(CI_PATH)
    packaging = workflow["jobs"]["packaging-smoke"]
    assert packaging["strategy"]["matrix"]["python-version"] == ["3.10", "3.11", "3.12"]
    commands = "\n".join(str(step.get("run", "")) for step in packaging["steps"])
    assert "python -m build --wheel" in commands
    assert "python -m twine check dist/*" in commands
    assert "python -m pip install --force-reinstall dist/*.whl" in commands
    assert 'cd "${RUNNER_TEMP}"' in commands
    assert "quant-platform --version" in commands


def test_dependabot_covers_python_frontend_and_actions():
    config = _load_yaml(DEPENDABOT_PATH)
    ecosystems = {(item["package-ecosystem"], item["directory"]) for item in config["updates"]}
    assert ecosystems == {
        ("pip", "/"),
        ("npm", "/frontend"),
        ("github-actions", "/"),
    }


def test_declared_main_ruleset_requires_stable_aggregate():
    ruleset = json.loads(RULESET_PATH.read_text(encoding="utf-8"))
    assert ruleset["enforcement"] == "active"
    assert ruleset["conditions"]["ref_name"]["include"] == ["refs/heads/main"]

    by_type = {rule["type"]: rule for rule in ruleset["rules"]}
    assert "deletion" in by_type
    assert "non_fast_forward" in by_type
    assert by_type["pull_request"]["parameters"]["required_approving_review_count"] == 0
    assert by_type["pull_request"]["parameters"]["required_review_thread_resolution"] is True

    status = by_type["required_status_checks"]["parameters"]
    assert status["strict_required_status_checks_policy"] is True
    assert status["required_status_checks"] == [{"context": "Required Checks"}]

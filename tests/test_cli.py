from unittest.mock import patch

from typer.testing import CliRunner

from sentry_tool.__about__ import __version__
from sentry_tool.cli import app

runner = CliRunner()


# ===== Tests for --version flag =====


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"sentry-tool {__version__}" in result.stdout


def test_version_short_flag():
    result = runner.invoke(app, ["-V"])
    assert result.exit_code == 0
    assert f"sentry-tool {__version__}" in result.stdout


# ===== Tests for list command =====


def test_list_issues(mock_sentry_api):
    result = runner.invoke(app, ["list", "--project", "test-project", "-n", "3"])

    assert result.exit_code == 0
    assert "TEST-PROJECT-K" in result.stdout
    assert "failed to index" in result.stdout
    assert "Showing 3 issues" in result.stdout


def test_list_issues_with_status_filter(mock_config, requests_mock, sample_issue_list):
    requests_mock.get(
        "https://sentry.test.local/api/0/projects/test-org/test-project/issues/"
        "?query=is:unresolved",
        json=[sample_issue_list[0]],
    )
    result = runner.invoke(app, ["list", "--project", "test-project", "-s", "unresolved"])

    assert result.exit_code == 0
    assert "TEST-PROJECT-K" in result.stdout


def test_list_issues_empty(mock_config, requests_mock):
    requests_mock.get(
        "https://sentry.test.local/api/0/projects/test-org/test-project/issues/",
        json=[],
    )
    result = runner.invoke(app, ["list", "--project", "test-project"])

    assert result.exit_code == 0
    assert "No issues found" in result.stdout


# ===== Tests for show command =====


def test_show_issue(mock_sentry_api):
    result = runner.invoke(app, ["show", "20"])

    assert result.exit_code == 0
    assert "TEST-PROJECT-K" in result.stdout
    assert "failed to index document" in result.stdout
    assert "unresolved" in result.stdout
    assert "2713930" in result.stdout


def test_show_issue_raw_json(mock_sentry_api):
    result = runner.invoke(app, ["show", "20", "--format", "json"])

    assert result.exit_code == 0
    assert '"shortId": "TEST-PROJECT-K"' in result.stdout
    assert '"title": "failed to index document"' in result.stdout


# ===== Tests for event command =====


def test_show_event_latest(mock_sentry_api):
    result = runner.invoke(app, ["event", "20"])

    assert result.exit_code == 0
    assert "d3f1d81247ad4516b61da92f1db050dd" in result.stdout  # pragma: allowlist secret
    assert "failed to index document" in result.stdout
    assert "test-server-0" in result.stdout


def test_show_event_raw_json(mock_sentry_api):
    result = runner.invoke(app, ["event", "20", "--format", "json"])

    assert result.exit_code == 0
    assert '"eventID": "d3f1d81247ad4516b61da92f1db050dd"' in result.stdout  # pragma: allowlist secret  # fmt: skip


# ===== Tests for events command =====


def test_list_events(mock_sentry_api):
    result = runner.invoke(app, ["events", "20"])

    assert result.exit_code == 0
    assert "4ac1c8d259134c0f86da4247471b82c3" in result.stdout  # pragma: allowlist secret
    assert "3bc2d7e248023b1e75cb3146380a91b2" in result.stdout  # pragma: allowlist secret
    assert "Showing 3 events" in result.stdout


# ===== Tests for tags command =====


def test_show_tags_list(mock_sentry_api):
    result = runner.invoke(app, ["tags", "20"])

    assert result.exit_code == 0
    assert "environment" in result.stdout
    assert "server_name" in result.stdout
    assert "2717049" in result.stdout


def test_show_tags_detail(mock_sentry_api):
    result = runner.invoke(app, ["tags", "20", "server_name"])

    assert result.exit_code == 0
    assert "test-server-0" in result.stdout
    assert "1234567" in result.stdout
    assert "45.0%" in result.stdout
    assert "2717301" in result.stdout


# ===== Tests for profile CLI flag =====


def test_profile_flag_short_form(tmp_path, monkeypatch, requests_mock, sample_issue_list):
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
default_profile = "prod"

[profiles.staging]
url = "https://sentry-staging.test.local"
org = "staging-org"
project = "staging-project"
auth_token = "staging_token_123"  # pragma: allowlist secret
""")

    monkeypatch.setenv("HOME", str(tmp_path))

    requests_mock.get(
        "https://sentry-staging.test.local/api/0/projects/staging-org/staging-project/issues/",
        json=sample_issue_list,
    )

    result = runner.invoke(app, ["-P", "staging", "list", "-n", "3"])

    assert result.exit_code == 0
    assert "TEST-PROJECT-K" in result.stdout


def test_profile_flag_long_form(tmp_path, monkeypatch, requests_mock, sample_issue_list):
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.dev]
url = "https://sentry-dev.test.local"
org = "dev-org"
project = "dev-project"
auth_token = "dev_token_123"  # pragma: allowlist secret
""")

    monkeypatch.setenv("HOME", str(tmp_path))

    requests_mock.get(
        "https://sentry-dev.test.local/api/0/projects/dev-org/dev-project/issues/",
        json=sample_issue_list,
    )

    result = runner.invoke(app, ["--profile", "dev", "list", "-n", "3"])

    assert result.exit_code == 0


def test_profile_from_env_var(tmp_path, monkeypatch, requests_mock, sample_issue_list):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SENTRY_PROFILE", "staging")

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.staging]
url = "https://sentry-staging.test.local"
org = "staging-org"
project = "staging-project"
auth_token = "staging_token_123"  # pragma: allowlist secret
""")

    monkeypatch.setenv("HOME", str(tmp_path))

    requests_mock.get(
        "https://sentry-staging.test.local/api/0/projects/staging-org/staging-project/issues/",
        json=sample_issue_list,
    )

    result = runner.invoke(app, ["list", "-n", "3"])

    assert result.exit_code == 0


def test_profile_cli_flag_overrides_env_var(
    tmp_path, monkeypatch, requests_mock, sample_issue_list
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SENTRY_PROFILE", "staging")

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.staging]
url = "https://sentry-staging.test.local"
org = "staging-org"
project = "staging-project"
auth_token = "staging_token"  # pragma: allowlist secret

[profiles.prod]
url = "https://sentry-prod.test.local"
org = "prod-org"
project = "prod-project"
auth_token = "prod_token"  # pragma: allowlist secret
""")

    monkeypatch.setenv("HOME", str(tmp_path))

    # Mock prod URL - if staging was used, this would fail
    requests_mock.get(
        "https://sentry-prod.test.local/api/0/projects/prod-org/prod-project/issues/",
        json=sample_issue_list,
    )

    result = runner.invoke(app, ["--profile", "prod", "list", "-n", "3"])

    assert result.exit_code == 0


def test_default_profile_used_when_none_specified(
    tmp_path, monkeypatch, requests_mock, sample_issue_list
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SENTRY_PROFILE", raising=False)

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
default_profile = "staging"

[profiles.staging]
url = "https://sentry-staging.test.local"
org = "staging-org"
project = "staging-project"
auth_token = "staging_token"  # pragma: allowlist secret

[profiles.prod]
url = "https://sentry-prod.test.local"
org = "prod-org"
project = "prod-project"
auth_token = "prod_token"  # pragma: allowlist secret
""")

    monkeypatch.setenv("HOME", str(tmp_path))

    # Should use staging (default_profile)
    requests_mock.get(
        "https://sentry-staging.test.local/api/0/projects/staging-org/staging-project/issues/",
        json=sample_issue_list,
    )

    result = runner.invoke(app, ["list", "-n", "3"])

    assert result.exit_code == 0


def test_invalid_profile_name_exits_with_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.prod]
url = "https://sentry-prod.test.local"
org = "prod-org"
project = "prod-project"
auth_token = "prod_token"  # pragma: allowlist secret
""")

    monkeypatch.setenv("HOME", str(tmp_path))

    result = runner.invoke(app, ["--profile", "nonexistent", "list"])

    assert result.exit_code == 1
    assert "nonexistent" in result.stdout
    assert "prod" in result.stdout


def test_env_var_overrides_profile_url(tmp_path, monkeypatch, requests_mock, sample_issue_list):
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.staging]
url = "https://sentry-staging.test.local"
org = "staging-org"
project = "staging-project"
auth_token = "staging_token"  # pragma: allowlist secret
""")

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SENTRY_URL", "https://override.test.local")

    # Should use override URL, not profile URL
    requests_mock.get(
        "https://override.test.local/api/0/projects/staging-org/staging-project/issues/",
        json=sample_issue_list,
    )

    result = runner.invoke(app, ["--profile", "staging", "list", "-n", "3"])

    assert result.exit_code == 0


def test_backwards_compat_env_vars_only_no_config(
    tmp_path, monkeypatch, requests_mock, sample_issue_list
):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("SENTRY_PROFILE", raising=False)
    monkeypatch.setenv("SENTRY_URL", "https://sentry.test.local")
    monkeypatch.setenv("SENTRY_ORG", "test-org")
    monkeypatch.setenv("SENTRY_PROJECT", "test-project")
    monkeypatch.setenv("SENTRY_AUTH_TOKEN", "test_token_12345")

    requests_mock.get(
        "https://sentry.test.local/api/0/projects/test-org/test-project/issues/",
        json=sample_issue_list,
    )

    result = runner.invoke(app, ["list", "-n", "3"])

    assert result.exit_code == 0


def test_missing_auth_token_exits_with_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SENTRY_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("SENTRY_PROFILE", raising=False)

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.staging]
url = "https://sentry-staging.test.local"
org = "staging-org"
project = "staging-project"
# auth_token intentionally missing
""")

    monkeypatch.setenv("HOME", str(tmp_path))

    result = runner.invoke(app, ["--profile", "staging", "list"])

    assert result.exit_code == 1


# ===== Tests for --project/-p global flag =====


def test_project_flag_short_form(tmp_path, monkeypatch, requests_mock, sample_issue_list):
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.default]
url = "https://sentry.test.local"
org = "test-org"
project = "default-project"
auth_token = "test_token_123"  # pragma: allowlist secret
""")

    monkeypatch.setenv("HOME", str(tmp_path))

    # Mock API call for overridden project
    requests_mock.get(
        "https://sentry.test.local/api/0/projects/test-org/override-project/issues/",
        json=sample_issue_list,
    )

    result = runner.invoke(app, ["-p", "override-project", "list", "-n", "3"])

    assert result.exit_code == 0
    assert "TEST-PROJECT-K" in result.stdout


def test_project_flag_long_form(tmp_path, monkeypatch, requests_mock, sample_issue_list):
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.default]
url = "https://sentry.test.local"
org = "test-org"
project = "default-project"
auth_token = "test_token_123"  # pragma: allowlist secret
""")

    monkeypatch.setenv("HOME", str(tmp_path))

    requests_mock.get(
        "https://sentry.test.local/api/0/projects/test-org/cli-project/issues/",
        json=sample_issue_list,
    )

    result = runner.invoke(app, ["--project", "cli-project", "list", "-n", "3"])

    assert result.exit_code == 0


def test_project_flag_overrides_env_var(tmp_path, monkeypatch, requests_mock, sample_issue_list):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SENTRY_PROJECT", "env-project")

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.default]
url = "https://sentry.test.local"
org = "test-org"
project = "profile-project"
auth_token = "test_token"  # pragma: allowlist secret
""")

    monkeypatch.setenv("HOME", str(tmp_path))

    # Should use CLI flag, not env var or profile
    requests_mock.get(
        "https://sentry.test.local/api/0/projects/test-org/cli-project/issues/",
        json=sample_issue_list,
    )

    result = runner.invoke(app, ["--project", "cli-project", "list", "-n", "3"])

    assert result.exit_code == 0


def test_project_flag_with_profile_flag(tmp_path, monkeypatch, requests_mock, sample_issue_list):
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.staging]
url = "https://sentry-staging.test.local"
org = "staging-org"
project = "staging-project"
auth_token = "staging_token"  # pragma: allowlist secret

[profiles.prod]
url = "https://sentry-prod.test.local"
org = "prod-org"
project = "prod-project"
auth_token = "prod_token"  # pragma: allowlist secret
""")

    monkeypatch.setenv("HOME", str(tmp_path))

    # Use prod profile but override project
    requests_mock.get(
        "https://sentry-prod.test.local/api/0/projects/prod-org/custom-project/issues/",
        json=sample_issue_list,
    )

    result = runner.invoke(app, ["-P", "prod", "-p", "custom-project", "list", "-n", "3"])

    assert result.exit_code == 0


# ===== Tests for list-projects command =====


def test_list_projects(mock_config, requests_mock, sample_project_list):
    requests_mock.get(
        "https://sentry.test.local/api/0/organizations/test-org/projects/",
        json=sample_project_list,
    )

    result = runner.invoke(app, ["list-projects"])

    assert result.exit_code == 0
    assert "otel-collector" in result.stdout
    assert "web-frontend" in result.stdout
    assert "api-gateway" in result.stdout
    assert "3 projects" in result.stdout


def test_list_projects_raw_json(mock_config, requests_mock, sample_project_list):
    requests_mock.get(
        "https://sentry.test.local/api/0/organizations/test-org/projects/",
        json=sample_project_list,
    )

    result = runner.invoke(app, ["list-projects", "--format", "json"])

    assert result.exit_code == 0
    assert '"slug": "otel-collector"' in result.stdout
    assert '"platform": "go"' in result.stdout


def test_list_projects_empty(mock_config, requests_mock):
    requests_mock.get(
        "https://sentry.test.local/api/0/organizations/test-org/projects/",
        json=[],
    )

    result = runner.invoke(app, ["list-projects"])

    assert result.exit_code == 0
    assert "No projects found" in result.stdout


# ===== Tests for open command =====


@patch("sentry_tool.commands.projects.webbrowser.open")
def test_open_dashboard(mock_open, mock_config):
    result = runner.invoke(app, ["open"])

    assert result.exit_code == 0
    mock_open.assert_called_once_with("https://sentry.test.local/organizations/test-org/issues/")
    assert "Opened:" in result.stdout


@patch("sentry_tool.commands.projects.webbrowser.open")
def test_open_specific_issue(mock_open, mock_config):
    result = runner.invoke(app, ["open", "24"])

    assert result.exit_code == 0
    mock_open.assert_called_once_with("https://sentry.test.local/organizations/test-org/issues/24/")
    assert "Opened:" in result.stdout


# ===== Tests for list --all-projects/-A flag =====


def test_list_all_projects(mock_config, requests_mock):
    org_issues = [
        {
            "id": "30",
            "shortId": "WEB-5",
            "status": "unresolved",
            "level": "error",
            "count": 100,
            "title": "TypeError in render",
            "project": {"slug": "web"},
        },
        {
            "id": "20",
            "shortId": "OTEL-K",
            "status": "unresolved",
            "level": "error",
            "count": 200,
            "title": "failed to index",
            "project": {"slug": "otel"},
        },
    ]
    requests_mock.get(
        "https://sentry.test.local/api/0/organizations/test-org/issues/",
        json=org_issues,
    )

    result = runner.invoke(app, ["list", "-A"])

    assert result.exit_code == 0
    assert "WEB-5" in result.stdout
    assert "OTEL-K" in result.stdout
    assert "web" in result.stdout
    assert "otel" in result.stdout
    assert "Project" in result.stdout
    assert "Showing 2 issues" in result.stdout


def test_list_all_projects_long_flag(mock_config, requests_mock):
    requests_mock.get(
        "https://sentry.test.local/api/0/organizations/test-org/issues/",
        json=[],
    )

    result = runner.invoke(app, ["list", "--all-projects"])

    assert result.exit_code == 0
    assert "No issues found" in result.stdout


def test_list_all_projects_mutually_exclusive_with_project(mock_config):
    result = runner.invoke(app, ["list", "-A", "-p", "some-project"])

    assert result.exit_code == 1
    assert "mutually exclusive" in result.stdout

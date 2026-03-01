from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from sentry_tool.__about__ import __version__
from sentry_tool.cli import app
from sentry_tool.config import (
    EnvOverrides,
    get_profile,
    load_config,
    resolve_sentry_config,
)
from sentry_tool.exceptions import ConfigurationError

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


def test_list_issues(live_cli_env):
    result = runner.invoke(app, ["list", "-n", "3"])

    assert result.exit_code == 0
    assert "Showing" in result.stdout


def test_list_issues_with_status_filter(live_cli_env):
    result = runner.invoke(app, ["list", "-s", "unresolved"])

    assert result.exit_code == 0


# ===== Tests for show command =====


def test_show_issue(live_cli_env, live_issue_id):
    result = runner.invoke(app, ["show", live_issue_id])

    assert result.exit_code == 0
    assert "Issue" in result.stdout


def test_show_issue_raw_json(live_cli_env, live_issue_id):
    result = runner.invoke(app, ["show", live_issue_id, "--format", "json"])

    assert result.exit_code == 0
    assert '"title"' in result.stdout


# ===== Tests for event command =====


def test_show_event_latest(live_cli_env, live_issue_id):
    result = runner.invoke(app, ["event", live_issue_id])

    assert result.exit_code == 0


def test_show_event_raw_json(live_cli_env, live_issue_id):
    result = runner.invoke(app, ["event", live_issue_id, "--format", "json"])

    assert result.exit_code == 0
    assert '"eventID"' in result.stdout


# ===== Tests for events command =====


def test_list_events(live_cli_env, live_issue_id):
    result = runner.invoke(app, ["events", live_issue_id])

    assert result.exit_code == 0


# ===== Tests for tags command =====


def test_show_tags_list(live_cli_env, live_issue_id):
    result = runner.invoke(app, ["tags", live_issue_id])

    assert result.exit_code == 0


def test_show_tags_detail(live_cli_env, live_issue_id, live_tag_key):
    result = runner.invoke(app, ["tags", live_issue_id, live_tag_key])

    assert result.exit_code == 0


# ===== Tests for profile config resolution =====


def test_profile_resolution_by_name(tmp_path, monkeypatch):
    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.staging]
url = "https://sentry-staging.test.local"
org = "staging-org"
project = "staging-project"
auth_token = "staging_token_123"
""")  # pragma: allowlist secret

    monkeypatch.setenv("HOME", str(tmp_path))

    app_config = load_config()
    profile = get_profile(app_config, "staging")
    resolved = resolve_sentry_config(profile)

    assert resolved["url"] == "https://sentry-staging.test.local"
    assert resolved["org"] == "staging-org"
    assert resolved["project"] == "staging-project"


def test_profile_from_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv("SENTRY_PROFILE", "staging")

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.staging]
url = "https://sentry-staging.test.local"
org = "staging-org"
project = "staging-project"
auth_token = "staging_token_123"
""")  # pragma: allowlist secret

    monkeypatch.setenv("HOME", str(tmp_path))

    app_config = load_config()
    profile = get_profile(app_config)
    resolved = resolve_sentry_config(profile)

    assert resolved["url"] == "https://sentry-staging.test.local"


def test_profile_explicit_overrides_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SENTRY_PROFILE", "staging")

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.staging]
url = "https://sentry-staging.test.local"
auth_token = "staging_token"

[profiles.prod]
url = "https://sentry-prod.test.local"
auth_token = "prod_token"
""")  # pragma: allowlist secret

    monkeypatch.setenv("HOME", str(tmp_path))

    app_config = load_config()
    profile = get_profile(app_config, profile="prod")
    assert profile.url == "https://sentry-prod.test.local"


def test_default_profile_used_when_none_specified(tmp_path, monkeypatch):
    monkeypatch.delenv("SENTRY_PROFILE", raising=False)

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
default_profile = "staging"

[profiles.staging]
url = "https://sentry-staging.test.local"
auth_token = "staging_token"

[profiles.prod]
url = "https://sentry-prod.test.local"
auth_token = "prod_token"
""")  # pragma: allowlist secret

    monkeypatch.setenv("HOME", str(tmp_path))

    app_config = load_config()
    profile = get_profile(app_config)
    assert profile.url == "https://sentry-staging.test.local"


def test_invalid_profile_name_raises_error(tmp_path, monkeypatch):
    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.prod]
url = "https://sentry-prod.test.local"
auth_token = "prod_token"
""")  # pragma: allowlist secret

    monkeypatch.setenv("HOME", str(tmp_path))

    app_config = load_config()
    with pytest.raises(ConfigurationError, match="nonexistent"):
        get_profile(app_config, profile="nonexistent")


def test_env_url_overrides_profile(tmp_path, monkeypatch):
    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.staging]
url = "https://sentry-staging.test.local"
org = "staging-org"
project = "staging-project"
auth_token = "staging_token"
""")  # pragma: allowlist secret

    monkeypatch.setenv("HOME", str(tmp_path))

    app_config = load_config()
    profile = get_profile(app_config, "staging")
    overrides = EnvOverrides(url="https://override.test.local")
    resolved = resolve_sentry_config(profile, overrides)

    assert resolved["url"] == "https://override.test.local"


def test_env_vars_only_no_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("SENTRY_PROFILE", raising=False)

    app_config = load_config()
    profile = get_profile(app_config)
    overrides = EnvOverrides(
        url="https://sentry.test.local",
        org="test-org",
        project="test-project",
        auth_token="test_token_12345",
    )
    resolved = resolve_sentry_config(profile, overrides)

    assert resolved["url"] == "https://sentry.test.local"
    assert resolved["auth_token"] == "test_token_12345"


def test_missing_auth_token_raises_error(tmp_path, monkeypatch):
    monkeypatch.delenv("SENTRY_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("SENTRY_PROFILE", raising=False)

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.staging]
url = "https://sentry-staging.test.local"
org = "staging-org"
project = "staging-project"
""")

    monkeypatch.setenv("HOME", str(tmp_path))

    app_config = load_config()
    profile = get_profile(app_config, "staging")
    with pytest.raises(ConfigurationError, match="SENTRY_AUTH_TOKEN"):
        resolve_sentry_config(profile)


def test_project_override_via_cli(tmp_path, monkeypatch):
    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.default]
url = "https://sentry.test.local"
org = "test-org"
project = "profile-project"
auth_token = "test_token"
""")  # pragma: allowlist secret

    monkeypatch.setenv("HOME", str(tmp_path))

    app_config = load_config()
    profile = get_profile(app_config)
    overrides = EnvOverrides(cli_project="cli-project", project="env-project")
    resolved = resolve_sentry_config(profile, overrides)

    assert resolved["project"] == "cli-project"


def test_project_override_beats_profile(tmp_path, monkeypatch):
    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.default]
url = "https://sentry.test.local"
org = "test-org"
project = "profile-project"
auth_token = "test_token"
""")  # pragma: allowlist secret

    monkeypatch.setenv("HOME", str(tmp_path))

    app_config = load_config()
    profile = get_profile(app_config)
    overrides = EnvOverrides(cli_project="cli-project")
    resolved = resolve_sentry_config(profile, overrides)

    assert resolved["project"] == "cli-project"


def test_project_with_profile_selection(tmp_path, monkeypatch):
    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.prod]
url = "https://sentry-prod.test.local"
org = "prod-org"
project = "prod-project"
auth_token = "prod_token"
""")  # pragma: allowlist secret

    monkeypatch.setenv("HOME", str(tmp_path))

    app_config = load_config()
    profile = get_profile(app_config, "prod")
    overrides = EnvOverrides(cli_project="custom-project")
    resolved = resolve_sentry_config(profile, overrides)

    assert resolved["url"] == "https://sentry-prod.test.local"
    assert resolved["project"] == "custom-project"


# ===== Tests for list-projects command =====


def test_list_projects(live_cli_env):
    result = runner.invoke(app, ["list-projects"])

    assert result.exit_code == 0
    assert "projects" in result.stdout


def test_list_projects_raw_json(live_cli_env):
    result = runner.invoke(app, ["list-projects", "--format", "json"])

    assert result.exit_code == 0
    assert '"slug"' in result.stdout


# ===== Tests for open command =====


@patch("sentry_tool.commands.projects.webbrowser.open")
def test_open_dashboard(mock_open, live_cli_env):
    result = runner.invoke(app, ["open"])

    assert result.exit_code == 0
    mock_open.assert_called_once()
    assert "Opened:" in result.stdout


@patch("sentry_tool.commands.projects.webbrowser.open")
def test_open_specific_issue(mock_open, live_cli_env):
    result = runner.invoke(app, ["open", "24"])

    assert result.exit_code == 0
    mock_open.assert_called_once()
    assert "Opened:" in result.stdout


# ===== Tests for list --all-projects/-A flag =====


def test_list_all_projects(live_cli_env):
    result = runner.invoke(app, ["list", "-A"])

    assert result.exit_code == 0


def test_list_all_projects_mutually_exclusive_with_project(live_cli_env):
    result = runner.invoke(app, ["list", "-A", "-p", "some-project"])

    assert result.exit_code == 1
    assert "mutually exclusive" in result.stdout

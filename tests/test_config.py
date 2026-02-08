"""Tests for configuration management with profile support."""

import json as json_mod
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sentry_tool.cli import app
from sentry_tool.config import (
    AppConfig,
    SentryProfile,
    get_profile,
    load_config,
    resolve_sentry_config,
)
from sentry_tool.exceptions import ConfigurationError
from sentry_tool.utils import mask_token

config_runner = CliRunner()

EXPECTED_PROFILE_COUNT = 2


# ===== Tests for mask_token() =====


def test_mask_token_shows_last_four():
    assert mask_token("sntrys_abc123xyz9") == "***...xyz9"  # pragma: allowlist secret


def test_mask_token_short_token():
    assert mask_token("ab") == "***...ab"


def test_mask_token_none():
    assert mask_token(None) == "(not set)"


def test_mask_token_empty_string():
    assert mask_token("") == "(not set)"


# ===== Tests for load_config() =====


def test_load_config_returns_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    config = load_config()

    assert config.default_profile == "default"
    assert "default" in config.profiles
    assert config.profiles["default"].url == "https://sentry.io"


def test_load_config_loads_from_xdg_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    # Create config in XDG location
    config_dir = tmp_path / ".config" / "sentry-tool"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.toml"
    config_file.write_text("""
default_profile = "staging"

[profiles.staging]
url = "https://sentry-staging.example.com"
org = "test-org"
project = "test-project"
""")

    # Mock home to tmp_path
    monkeypatch.setenv("HOME", str(tmp_path))

    config = load_config()

    assert config.default_profile == "staging"
    assert config.profiles["staging"].url == "https://sentry-staging.example.com"


def test_load_config_prefers_explicit_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    custom_config = tmp_path / "custom.toml"
    custom_config.write_text("""
default_profile = "custom"

[profiles.custom]
url = "https://custom.example.com"
""")

    config = load_config(config_path=custom_config)

    assert config.default_profile == "custom"
    assert config.profiles["custom"].url == "https://custom.example.com"


def test_load_config_parses_multiple_profiles(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / "config.toml"
    config_file.write_text("""
default_profile = "prod"

[profiles.prod]
url = "https://sentry.prod.example.com"
org = "prod-org"
project = "prod-project"
auth_token = "prod_token_123"

[profiles.dev]
url = "http://localhost:9000"
org = "dev-org"
project = "dev-project"
""")

    config = load_config(config_path=config_file)

    assert len(config.profiles) == EXPECTED_PROFILE_COUNT
    assert config.profiles["prod"].url == "https://sentry.prod.example.com"
    assert config.profiles["dev"].url == "http://localhost:9000"


# ===== Tests for get_profile() =====


def test_get_profile_uses_explicit_name():
    config = AppConfig(
        default_profile="default",
        profiles={
            "default": SentryProfile(url="https://default.example.com"),
            "staging": SentryProfile(url="https://staging.example.com"),
        },
    )

    profile = get_profile(config, profile="staging")

    assert profile.url == "https://staging.example.com"


def test_get_profile_uses_env_var_when_no_explicit(monkeypatch):
    monkeypatch.setenv("SENTRY_PROFILE", "staging")

    config = AppConfig(
        default_profile="default",
        profiles={
            "default": SentryProfile(url="https://default.example.com"),
            "staging": SentryProfile(url="https://staging.example.com"),
        },
    )

    profile = get_profile(config, profile=None)

    assert profile.url == "https://staging.example.com"


def test_get_profile_uses_config_default_when_no_explicit_or_env(monkeypatch):
    monkeypatch.delenv("SENTRY_PROFILE", raising=False)

    config = AppConfig(
        default_profile="staging",
        profiles={
            "default": SentryProfile(url="https://default.example.com"),
            "staging": SentryProfile(url="https://staging.example.com"),
        },
    )

    profile = get_profile(config, profile=None)

    assert profile.url == "https://staging.example.com"


def test_get_profile_raises_when_profile_not_found():
    config = AppConfig(
        profiles={
            "default": SentryProfile(url="https://default.example.com"),
        }
    )

    with pytest.raises(ConfigurationError, match="Profile 'nonexistent' not found"):
        get_profile(config, profile="nonexistent")


def test_get_profile_error_lists_available_profiles():
    config = AppConfig(
        profiles={
            "prod": SentryProfile(),
            "staging": SentryProfile(),
            "dev": SentryProfile(),
        }
    )

    with pytest.raises(ConfigurationError, match="Available profiles: dev, prod, staging"):
        get_profile(config, profile="missing")


# ===== Tests for resolve_sentry_config() =====


def test_resolve_sentry_config_returns_profile_values():
    profile = SentryProfile(
        url="https://sentry.example.com",
        org="test-org",
        project="test-project",
        auth_token="profile_token_123",
    )

    resolved = resolve_sentry_config(profile)

    assert resolved["url"] == "https://sentry.example.com"
    assert resolved["org"] == "test-org"
    assert resolved["project"] == "test-project"
    assert resolved["auth_token"] == "profile_token_123"


def test_resolve_sentry_config_env_url_overrides_profile():
    profile = SentryProfile(url="https://profile.example.com", auth_token="token")

    resolved = resolve_sentry_config(profile, env_url="https://env.example.com")

    assert resolved["url"] == "https://env.example.com"


def test_resolve_sentry_config_env_org_overrides_profile():
    profile = SentryProfile(org="profile-org", auth_token="token")

    resolved = resolve_sentry_config(profile, env_org="env-org")

    assert resolved["org"] == "env-org"


def test_resolve_sentry_config_env_project_overrides_profile():
    profile = SentryProfile(project="profile-project", auth_token="token")

    resolved = resolve_sentry_config(profile, env_project="env-project")

    assert resolved["project"] == "env-project"


def test_resolve_sentry_config_cli_project_overrides_env():
    profile = SentryProfile(project="profile-project", auth_token="token")

    resolved = resolve_sentry_config(profile, cli_project="cli-project", env_project="env-project")

    assert resolved["project"] == "cli-project"


def test_resolve_sentry_config_cli_project_overrides_profile():
    profile = SentryProfile(project="profile-project", auth_token="token")

    resolved = resolve_sentry_config(profile, cli_project="cli-project")

    assert resolved["project"] == "cli-project"


def test_resolve_sentry_config_env_auth_token_overrides_profile():
    profile = SentryProfile(auth_token="profile_token")

    resolved = resolve_sentry_config(profile, env_auth_token="env_token")

    assert resolved["auth_token"] == "env_token"


def test_resolve_sentry_config_raises_when_token_missing():
    profile = SentryProfile(auth_token=None)

    with pytest.raises(ConfigurationError, match="SENTRY_AUTH_TOKEN not set"):
        resolve_sentry_config(profile)


def test_resolve_sentry_config_raises_when_token_empty():
    profile = SentryProfile(auth_token="")

    with pytest.raises(ConfigurationError, match="SENTRY_AUTH_TOKEN not set"):
        resolve_sentry_config(profile)


def test_resolve_sentry_config_strips_whitespace_from_token():
    profile = SentryProfile(auth_token="  token_with_spaces  ")

    resolved = resolve_sentry_config(profile)

    assert resolved["auth_token"] == "token_with_spaces"


# ===== Integration Tests for Full Resolution Flow =====


def test_full_resolution_with_profile_and_env_overrides(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / "config.toml"
    config_file.write_text("""
default_profile = "staging"

[profiles.staging]
url = "https://staging.example.com"
org = "staging-org"
project = "staging-project"
auth_token = "staging_token"
""")

    # Override URL and token via env
    monkeypatch.setenv("SENTRY_URL", "https://override.example.com")
    monkeypatch.setenv("SENTRY_AUTH_TOKEN", "override_token")

    app_config = load_config(config_path=config_file)
    profile = get_profile(app_config)
    resolved = resolve_sentry_config(
        profile,
        env_url="https://override.example.com",
        env_auth_token="override_token",
    )

    assert resolved["url"] == "https://override.example.com"
    assert resolved["org"] == "staging-org"  # From profile
    assert resolved["project"] == "staging-project"  # From profile
    assert resolved["auth_token"] == "override_token"  # Overridden


def test_backwards_compatibility_env_only_no_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("SENTRY_PROFILE", raising=False)

    # No config file exists, use defaults + env overrides
    app_config = load_config()  # Returns defaults
    profile = get_profile(app_config)  # Gets "default" profile

    resolved = resolve_sentry_config(
        profile,
        env_url="https://env.example.com",
        env_org="env-org",
        env_project="env-project",
        env_auth_token="env_token",
    )

    assert resolved["url"] == "https://env.example.com"
    assert resolved["org"] == "env-org"
    assert resolved["project"] == "env-project"
    assert resolved["auth_token"] == "env_token"


def test_profile_precedence_explicit_beats_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SENTRY_PROFILE", "staging")

    config_file = tmp_path / "config.toml"
    config_file.write_text("""
[profiles.staging]
url = "https://staging.example.com"
auth_token = "staging_token"

[profiles.prod]
url = "https://prod.example.com"
auth_token = "prod_token"
""")

    app_config = load_config(config_path=config_file)
    profile = get_profile(app_config, profile="prod")  # Explicit overrides env

    assert profile.url == "https://prod.example.com"


def test_profile_precedence_env_beats_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SENTRY_PROFILE", "dev")

    config_file = tmp_path / "config.toml"
    config_file.write_text("""
default_profile = "prod"

[profiles.prod]
url = "https://prod.example.com"
auth_token = "prod_token"

[profiles.dev]
url = "https://dev.example.com"
auth_token = "dev_token"
""")

    app_config = load_config(config_path=config_file)
    profile = get_profile(app_config, profile=None)  # No explicit, uses env

    assert profile.url == "https://dev.example.com"


# ===== Tests for SentryProfile Model =====


def test_sentry_profile_has_defaults():
    profile = SentryProfile()

    assert profile.url == "https://sentry.io"
    assert profile.org == "sentry"
    assert profile.project == "otel-collector"
    assert profile.auth_token is None


def test_sentry_profile_accepts_custom_values():
    profile = SentryProfile(
        url="https://custom.example.com",
        org="custom-org",
        project="custom-project",
        auth_token="custom_token",
    )

    assert profile.url == "https://custom.example.com"
    assert profile.org == "custom-org"
    assert profile.project == "custom-project"
    assert profile.auth_token == "custom_token"


# ===== Tests for AppConfig Model =====


def test_app_config_has_defaults():
    config = AppConfig()

    assert config.default_profile == "default"
    assert "default" in config.profiles
    assert isinstance(config.profiles["default"], SentryProfile)


def test_app_config_accepts_custom_profiles():
    config = AppConfig(
        default_profile="prod",
        profiles={
            "prod": SentryProfile(url="https://prod.example.com"),
            "dev": SentryProfile(url="https://dev.example.com"),
        },
    )

    assert config.default_profile == "prod"
    assert len(config.profiles) == EXPECTED_PROFILE_COUNT


# ===== Tests for config.example.toml Validity =====


def test_example_config_is_valid_toml():
    example_path = Path(__file__).parent.parent / "config.example.toml"

    with example_path.open("rb") as f:
        config_data = tomllib.load(f)

    assert "default_profile" in config_data
    assert "profiles" in config_data
    assert isinstance(config_data["profiles"], dict)


def test_example_config_profiles_have_required_fields():
    example_path = Path(__file__).parent.parent / "config.example.toml"

    with example_path.open("rb") as f:
        config_data = tomllib.load(f)

    for profile_name, profile_data in config_data["profiles"].items():
        assert "url" in profile_data, f"Profile {profile_name} missing 'url'"
        assert "org" in profile_data, f"Profile {profile_name} missing 'org'"
        assert "project" in profile_data, f"Profile {profile_name} missing 'project'"


# ===== Tests for config list-projects command =====


def test_config_list_projects_success(tmp_path, monkeypatch, requests_mock):
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

    requests_mock.get(
        "https://sentry-staging.test.local/api/0/organizations/staging-org/projects/",
        json=[{"slug": "web-app"}, {"slug": "api"}],
    )
    requests_mock.get(
        "https://sentry-prod.test.local/api/0/organizations/prod-org/projects/",
        json=[{"slug": "backend"}, {"slug": "frontend"}, {"slug": "mobile"}],
    )

    result = config_runner.invoke(app, ["config", "list-projects"])

    assert result.exit_code == 0
    assert "staging" in result.stdout
    assert "web-app" in result.stdout
    assert "api" in result.stdout
    assert "prod" in result.stdout
    assert "backend" in result.stdout
    assert "frontend" in result.stdout
    assert "mobile" in result.stdout


def test_config_list_projects_missing_token(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.staging]
url = "https://sentry-staging.test.local"
org = "staging-org"
project = "staging-project"
""")

    monkeypatch.setenv("HOME", str(tmp_path))

    result = config_runner.invoke(app, ["config", "list-projects"])

    assert result.exit_code == 0
    assert "staging" in result.stdout
    assert "no auth token" in result.stdout


def test_config_list_projects_org_not_found(tmp_path, monkeypatch, requests_mock):
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.staging]
url = "https://sentry-staging.test.local"
org = "nonexistent-org"
project = "staging-project"
auth_token = "staging_token"  # pragma: allowlist secret
""")

    monkeypatch.setenv("HOME", str(tmp_path))

    requests_mock.get(
        "https://sentry-staging.test.local/api/0/organizations/nonexistent-org/projects/",
        status_code=404,
    )

    result = config_runner.invoke(app, ["config", "list-projects"])

    assert result.exit_code == 0
    assert "staging" in result.stdout
    assert "not found" in result.stdout


def test_config_list_projects_empty_result(tmp_path, monkeypatch, requests_mock):
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

    requests_mock.get(
        "https://sentry-staging.test.local/api/0/organizations/staging-org/projects/",
        json=[],
    )

    result = config_runner.invoke(app, ["config", "list-projects"])

    assert result.exit_code == 0
    assert "staging" in result.stdout
    assert "no projects" in result.stdout


# ===== Tests for config validate command =====


def test_config_validate_success(tmp_path, monkeypatch, requests_mock):
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

    requests_mock.get(
        "https://sentry-staging.test.local/api/0/organizations/staging-org/projects/",
        json=[{"slug": "web-app"}],
    )
    requests_mock.get(
        "https://sentry-prod.test.local/api/0/organizations/prod-org/projects/",
        json=[{"slug": "backend"}, {"slug": "frontend"}],
    )

    result = config_runner.invoke(app, ["config", "validate"])

    assert result.exit_code == 0
    assert "staging" in result.stdout
    assert "1 projects" in result.stdout
    assert "web-app" in result.stdout
    assert "prod" in result.stdout
    assert "2 projects" in result.stdout
    assert "backend, frontend" in result.stdout


def test_config_validate_missing_token(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.staging]
url = "https://sentry-staging.test.local"
org = "staging-org"
project = "staging-project"
""")

    monkeypatch.setenv("HOME", str(tmp_path))

    result = config_runner.invoke(app, ["config", "validate"])

    assert result.exit_code == 0
    assert "staging" in result.stdout
    assert "No auth token configured" in result.stdout


def test_config_validate_org_not_found(tmp_path, monkeypatch, requests_mock):
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
[profiles.staging]
url = "https://sentry-staging.test.local"
org = "nonexistent-org"
project = "staging-project"
auth_token = "staging_token"  # pragma: allowlist secret
""")

    monkeypatch.setenv("HOME", str(tmp_path))

    requests_mock.get(
        "https://sentry-staging.test.local/api/0/organizations/nonexistent-org/projects/",
        status_code=404,
    )

    result = config_runner.invoke(app, ["config", "validate"])

    assert result.exit_code == 0
    assert "staging" in result.stdout
    assert "not found" in result.stdout


# ===== Tests for config show command =====


def test_config_show_table_displays_profiles(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SENTRY_PROFILE", raising=False)
    monkeypatch.delenv("SENTRY_URL", raising=False)
    monkeypatch.delenv("SENTRY_ORG", raising=False)
    monkeypatch.delenv("SENTRY_PROJECT", raising=False)
    monkeypatch.delenv("SENTRY_AUTH_TOKEN", raising=False)

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
default_profile = "staging"

[profiles.staging]
url = "https://sentry-staging.test.local"
org = "staging-org"
project = "staging-project"
auth_token = "staging_token_abcd"
""")  # pragma: allowlist secret

    monkeypatch.setenv("HOME", str(tmp_path))

    result = config_runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0
    assert "staging" in result.stdout
    assert "staging-org" in result.stdout
    assert "staging-project" in result.stdout
    assert "***...abcd" in result.stdout
    assert "Effective Settings" in result.stdout


def test_config_show_json_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SENTRY_PROFILE", raising=False)
    monkeypatch.delenv("SENTRY_URL", raising=False)
    monkeypatch.delenv("SENTRY_ORG", raising=False)
    monkeypatch.delenv("SENTRY_PROJECT", raising=False)
    monkeypatch.delenv("SENTRY_AUTH_TOKEN", raising=False)

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
default_profile = "prod"

[profiles.prod]
url = "https://sentry-prod.test.local"
org = "prod-org"
project = "prod-project"
auth_token = "prod_token_7890"
""")  # pragma: allowlist secret

    monkeypatch.setenv("HOME", str(tmp_path))

    result = config_runner.invoke(app, ["config", "show", "--format", "json"])

    assert result.exit_code == 0

    data = json_mod.loads(result.stdout)
    assert data["default_profile"] == "prod"
    assert data["active_profile"] == "prod"
    assert data["effective"]["url"] == "https://sentry-prod.test.local"
    assert data["effective"]["org"] == "prod-org"
    assert data["effective"]["auth_token"] == "***...7890"
    assert "prod" in data["profiles"]
    assert data["profiles"]["prod"]["url"] == "https://sentry-prod.test.local"


def test_config_show_with_env_overrides(tmp_path, monkeypatch):
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
auth_token = "staging_token_abcd"
""")  # pragma: allowlist secret

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SENTRY_URL", "https://override.test.local")
    monkeypatch.setenv("SENTRY_ORG", "override-org")
    monkeypatch.delenv("SENTRY_PROJECT", raising=False)
    monkeypatch.delenv("SENTRY_AUTH_TOKEN", raising=False)

    result = config_runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0
    assert "override.test.local" in result.stdout
    assert "override-org" in result.stdout
    assert "SENTRY_URL" in result.stdout
    assert "SENTRY_ORG" in result.stdout


def test_config_show_json_with_env_overrides(tmp_path, monkeypatch):
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
auth_token = "staging_token_abcd"
""")  # pragma: allowlist secret

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SENTRY_URL", "https://env-override.test.local")
    monkeypatch.delenv("SENTRY_ORG", raising=False)
    monkeypatch.delenv("SENTRY_PROJECT", raising=False)
    monkeypatch.delenv("SENTRY_AUTH_TOKEN", raising=False)

    result = config_runner.invoke(app, ["config", "show", "--format", "json"])

    assert result.exit_code == 0

    data = json_mod.loads(result.stdout)
    assert data["effective"]["url"] == "https://env-override.test.local"
    assert data["effective"]["org"] == "staging-org"


# ===== Tests for config profiles command =====


def test_config_profiles_table(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
default_profile = "prod"

[profiles.prod]
url = "https://sentry-prod.test.local"

[profiles.staging]
url = "https://sentry-staging.test.local"
""")

    monkeypatch.setenv("HOME", str(tmp_path))

    result = config_runner.invoke(app, ["config", "profiles"])

    assert result.exit_code == 0
    assert "prod" in result.stdout
    assert "staging" in result.stdout
    assert "2 profiles" in result.stdout


def test_config_profiles_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    config_file = tmp_path / ".config" / "sentry-tool" / "config.toml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("""
default_profile = "prod"

[profiles.prod]
url = "https://sentry-prod.test.local"

[profiles.dev]
url = "https://sentry-dev.test.local"
""")

    monkeypatch.setenv("HOME", str(tmp_path))

    result = config_runner.invoke(app, ["config", "profiles", "--format", "json"])

    assert result.exit_code == 0

    data = json_mod.loads(result.stdout)
    names = [row["name"] for row in data]
    assert "prod" in names
    assert "dev" in names


# ===== Tests for config list-projects --format json =====


def test_config_list_projects_json(tmp_path, monkeypatch, requests_mock):
    monkeypatch.chdir(tmp_path)

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

    requests_mock.get(
        "https://sentry-staging.test.local/api/0/organizations/staging-org/projects/",
        json=[{"slug": "web-app"}, {"slug": "api"}],
    )

    result = config_runner.invoke(app, ["config", "list-projects", "--format", "json"])

    assert result.exit_code == 0

    data = json_mod.loads(result.stdout)
    projects = [row["project"] for row in data]
    assert "web-app" in projects
    assert "api" in projects


def test_config_list_projects_generic_exception(tmp_path, monkeypatch, requests_mock):
    monkeypatch.chdir(tmp_path)

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

    requests_mock.get(
        "https://sentry-staging.test.local/api/0/organizations/staging-org/projects/",
        exc=ConnectionError("connection refused"),
    )

    result = config_runner.invoke(app, ["config", "list-projects"])

    assert result.exit_code == 0
    assert "staging" in result.stdout
    assert "error" in result.stdout.lower()


# ===== Tests for config validate --format json =====


def test_config_validate_json(tmp_path, monkeypatch, requests_mock):
    monkeypatch.chdir(tmp_path)

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

    requests_mock.get(
        "https://sentry-staging.test.local/api/0/organizations/staging-org/projects/",
        json=[{"slug": "web-app"}],
    )

    result = config_runner.invoke(app, ["config", "validate", "--format", "json"])

    assert result.exit_code == 0

    data = json_mod.loads(result.stdout)
    assert data[0]["profile"] == "staging"
    assert data[0]["status"] == "OK"
    assert "1 projects" in data[0]["projects"]


def test_config_validate_generic_exception(tmp_path, monkeypatch, requests_mock):
    monkeypatch.chdir(tmp_path)

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

    requests_mock.get(
        "https://sentry-staging.test.local/api/0/organizations/staging-org/projects/",
        exc=ConnectionError("connection refused"),
    )

    result = config_runner.invoke(app, ["config", "validate"])

    assert result.exit_code == 0
    assert "staging" in result.stdout
    assert "FAIL" in result.stdout

# Sentry Tool

CLI tool for querying and managing Sentry issues.

## Overview

Sentry Tool provides a command-line interface for interacting with Sentry's API to query issues, view events, and analyze error patterns. It's designed for DevOps engineers, developers, and SREs who need quick CLI access to Sentry data.

## Features

- **List issues**: View recent issues in a project or across all projects
- **Show issue details**: Get comprehensive information about specific issues
- **View events**: Examine event details and stacktraces
- **List events**: See recent events for an issue
- **Tag analysis**: Analyze tag distributions across issues
- **List projects**: View all projects in an organization
- **Open in browser**: Quick-launch Sentry web UI
- **Multi-instance support**: TOML-based profiles for multiple Sentry instances
- **Configuration management**: Validate connectivity, list projects across profiles

## Installation

### Requirements

- Python >= 3.13
- uv package manager

### Setup

```bash
# Clone or navigate to the sentry-tool directory
cd sentry-tool

# Install dependencies
uv sync

# Install dev dependencies (optional)
uv sync --group dev
```

## Configuration

Sentry Tool supports a TOML-based profile system for managing multiple Sentry instances, with environment variable overrides for flexibility.

### Profile Configuration (Recommended)

Create a TOML configuration file at `~/.config/sentry-tool/config.toml`:

```toml
default_profile = "my-sentry"

[profiles.my-sentry]
url = "https://sentry.example.com"
org = "my-org"
project = "my-project"
auth_token = "sntrys_..."

[profiles.cloud]
url = "https://sentry.io"
org = "my-cloud-org"
project = "web-app"
auth_token = "sntrys_..."
```

Each profile defines:

| Field | Description | Default |
|-------|-------------|---------|
| `url` | Sentry instance URL | `https://sentry.io` |
| `org` | Organization slug | `sentry` |
| `project` | Default project slug | *(none)* |
| `auth_token` | API authentication token | *(required)* |

### Environment Variable Overrides

Environment variables override profile values. This is useful for CI/CD or temporary overrides.

| Variable | Overrides | Description |
|----------|-----------|-------------|
| `SENTRY_AUTH_TOKEN` | `auth_token` | API authentication token |
| `SENTRY_URL` | `url` | Sentry instance URL |
| `SENTRY_ORG` | `org` | Organization slug |
| `SENTRY_PROJECT` | `project` | Default project slug |
| `SENTRY_PROFILE` | *(profile selection)* | Use this profile instead of default |

### Getting a Sentry Auth Token

1. Log into your Sentry instance
2. Navigate to Settings > Account > API > Auth Tokens
3. Create a new token with appropriate scopes (at minimum: `project:read`, `event:read`)
4. Add the token to your profile configuration or set `SENTRY_AUTH_TOKEN`

### Verifying Configuration

```bash
# Show current configuration and all profiles
sentry-tool config show

# Verify connectivity to all profiles
sentry-tool config validate
```

## Global Flags

These flags are available on the root command and apply to all subcommands.

| Flag | Short | Description |
|------|-------|-------------|
| `--profile` | `-P` | Use a named profile from config |
| `--project` | `-p` | Override the project slug from the active profile |

Most commands also accept:

| Flag | Short | Values | Description |
|------|-------|--------|-------------|
| `--format` | `-f` | `table`, `json` | Output format (default: `table`) |

## Usage

### `list` - List Recent Issues

List recent issues in a project. Use `--all-projects/-A` to list across all projects.

```bash
sentry-tool list
sentry-tool list -p my-project -n 5
sentry-tool list -s unresolved
sentry-tool list -A
sentry-tool list --format json
```

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--project` | `-p` | Project slug | profile default |
| `--all-projects` | `-A` | List issues across all projects (mutually exclusive with `-p`) | |
| `--max` | `-n` | Maximum issues to show | `10` |
| `--status` | `-s` | Filter by status: `resolved`, `unresolved`, `muted` | |
| `--format` | `-f` | Output format: `table`, `json` | `table` |

---

### `show` - Show Issue Details

Show comprehensive details for a specific issue.

```bash
sentry-tool show 24
sentry-tool show OTEL-COLLECTOR-Q
sentry-tool show 24 --format json
```

| Argument | Description |
|----------|-------------|
| `ISSUE_ID` | Issue ID (numeric like `24` or short ID like `OTEL-COLLECTOR-Q`) |

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--format` | `-f` | Output format: `table`, `json` | `table` |

**Output includes:** Title, Status, Level, Priority, Event count, First/Last seen, Tags, Release info, Permalink

---

### `event` - Show Event Details

Show event details for an issue. By default shows the latest event.

```bash
sentry-tool event 24
sentry-tool event OTEL-COLLECTOR-Q
sentry-tool event 24 -e abc123...
sentry-tool event 24 -c
sentry-tool event 24 --format json
```

| Argument | Description |
|----------|-------------|
| `ISSUE_ID` | Issue ID (numeric or short ID) |

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--event` | `-e` | Specific event ID | latest |
| `--context` | `-c` | Show only context/stacktrace | |
| `--format` | `-f` | Output format: `table`, `json` | `table` |

**Output includes:** Event ID, Title, Message, Date, Server, SDK info, Release, Context, Exception with stacktrace

---

### `events` - List Recent Events

List recent events for an issue.

```bash
sentry-tool events 24
sentry-tool events OTEL-COLLECTOR-Q -n 5
sentry-tool events 24 --format json
```

| Argument | Description |
|----------|-------------|
| `ISSUE_ID` | Issue ID (numeric or short ID) |

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--max` | `-n` | Maximum events to show | `10` |
| `--format` | `-f` | Output format: `table`, `json` | `table` |

**Output:** Table with Event ID, Date, Server

---

### `tags` - Show Tag Values

Show tag values for an issue. Lists available tags when no tag key is provided.

```bash
sentry-tool tags OTEL-COLLECTOR-14
sentry-tool tags OTEL-COLLECTOR-14 server_name
sentry-tool tags OTEL-COLLECTOR-14 release
sentry-tool tags 14 server_name --format json
```

| Argument | Description |
|----------|-------------|
| `ISSUE_ID` | Issue ID (numeric or short ID) |
| `TAG_KEY` | *(optional)* Tag key to show values for (e.g., `server_name`, `release`) |

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--format` | `-f` | Output format: `table`, `json` | `table` |

**Output:**
- Without `TAG_KEY`: Table of available tags with unique value counts
- With `TAG_KEY`: Table showing tag values with count and percentage distribution

---

### `list-projects` - List Projects

List all projects in the configured organization.

```bash
sentry-tool list-projects
sentry-tool list-projects --format json
```

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--format` | `-f` | Output format: `table`, `json` | `table` |

---

### `open` - Open in Browser

Open Sentry web UI in the default browser. Without arguments, opens the organization dashboard. With an issue ID, opens that issue directly.

```bash
sentry-tool open
sentry-tool open 24
```

| Argument | Description |
|----------|-------------|
| `ISSUE_ID` | *(optional)* Issue ID to open directly |

---

### `config` - Configuration Management

Subcommands for managing and verifying configuration.

#### `config show`

Display current configuration including active profile and all configured profiles.

```bash
sentry-tool config show
sentry-tool config show --format json
```

#### `config profiles`

List configured profile names with default marked.

```bash
sentry-tool config profiles
sentry-tool config profiles --format json
```

#### `config list-projects`

Enumerate Sentry projects for each configured profile. Profiles with missing auth tokens are skipped.

```bash
sentry-tool config list-projects
sentry-tool config list-projects --format json
```

#### `config validate`

Verify connectivity to all configured profiles by querying projects. Useful after initial setup.

```bash
sentry-tool config validate
sentry-tool config validate --format json
```

All `config` subcommands accept `--format/-f` (`table` or `json`, default: `table`).

---

### Common Workflows

**Investigate a New Issue:**
```bash
# 1. List recent unresolved issues
sentry-tool list -s unresolved

# 2. Show details for an issue
sentry-tool show OTEL-COLLECTOR-14

# 3. See the latest event with stack trace
sentry-tool event OTEL-COLLECTOR-14

# 4. Check which servers are affected
sentry-tool tags OTEL-COLLECTOR-14 server_name
```

**Cross-Instance Investigation:**
```bash
# List issues across all projects on a specific instance
sentry-tool -P production list -A

# Compare the same project on different instances
sentry-tool -P staging -p web-app list
sentry-tool -P production -p web-app list
```

**Export Data for Analysis:**
```bash
# Get issue details as JSON
sentry-tool show OTEL-COLLECTOR-14 --format json > issue.json

# Get event details as JSON
sentry-tool event OTEL-COLLECTOR-14 --format json > event.json
```

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow, testing, and contribution guidelines.

### Quick Start

```bash
# Install with dev dependencies
uv sync --group dev

# Run tests
uv run pytest

# Type checking
uv run mypy src

# Linting
uv run ruff check src tests

# Format code
uv run ruff format src tests
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

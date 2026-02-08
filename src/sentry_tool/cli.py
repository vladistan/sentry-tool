from typing import Annotated

import typer

from sentry_tool.commands import config, events, issues, projects
from sentry_tool.monitoring import setup_logging, setup_sentry
from sentry_tool.utils import set_active_profile, set_active_project

app = typer.Typer(
    help="Sentry Tool - Query and manage Sentry issues.",
    no_args_is_help=True,
)

app.add_typer(config.config_app, name="config")

app.command("list")(issues.list_issues)
app.command("show")(issues.show_issue)
app.command("event")(events.show_event)
app.command("events")(events.list_events)
app.command("tags")(events.show_tags)
app.command("list-projects")(projects.list_projects)
app.command("open")(projects.open_sentry)


@app.callback()
def callback(
    profile: Annotated[
        str | None,
        typer.Option("--profile", "-P", help="Use named profile from config"),
    ] = None,
    project: Annotated[
        str | None,
        typer.Option("--project", "-p", help="Override project slug from profile"),
    ] = None,
) -> None:
    set_active_profile(profile)
    set_active_project(project)


def cli() -> None:
    setup_logging()
    setup_sentry(environment="local")
    app()

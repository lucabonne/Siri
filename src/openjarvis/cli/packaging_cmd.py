"""CLI commands for local Siri packaging."""

from __future__ import annotations

import json
import subprocess

import click

from openjarvis.packaging import PackagingService


@click.group("package", help="Build and inspect the local Siri app bundle.")
def package_cmd() -> None:
    pass


@package_cmd.command("status")
def package_status() -> None:
    service = PackagingService()
    click.echo(json.dumps(service.status().to_dict(), indent=2, sort_keys=True))


@package_cmd.command("diagnostics")
def package_diagnostics() -> None:
    service = PackagingService()
    click.echo(json.dumps(service.diagnostics(), indent=2, sort_keys=True))


@package_cmd.command("release-diagnostics")
def package_release_diagnostics() -> None:
    service = PackagingService()
    click.echo(json.dumps(service.release_diagnostics(), indent=2, sort_keys=True))


@package_cmd.command("build")
@click.option(
    "--output-dir",
    default="",
    help="Directory that will receive Siri.app; defaults to build/packaging.",
)
def package_build(output_dir: str) -> None:
    service = PackagingService()
    result = service.build_app_bundle(output_dir=output_dir or None)
    click.echo(json.dumps(result, indent=2, sort_keys=True))


@package_cmd.command("install")
@click.option(
    "--destination",
    type=click.Choice(["user", "system"]),
    default="user",
    show_default=True,
    help="Install into ~/Applications or /Applications.",
)
@click.option(
    "--no-launch-agent",
    is_flag=True,
    default=False,
    help="Skip LaunchAgent install/update.",
)
@click.option(
    "--output-dir",
    default="",
    help="Temporary build output directory; defaults to build/packaging.",
)
def package_install(
    destination: str,
    no_launch_agent: bool,
    output_dir: str,
) -> None:
    service = PackagingService()
    result = service.install_app_bundle(
        destination=destination,
        install_launch_agent=not no_launch_agent,
        output_dir=output_dir or None,
    )
    click.echo(json.dumps(result, indent=2, sort_keys=True))


@package_cmd.command("uninstall")
@click.option(
    "--keep-launch-agent",
    is_flag=True,
    default=False,
    help="Remove app bundles but keep the LaunchAgent plist.",
)
@click.option(
    "--destination",
    type=click.Choice(["user", "system", "all"]),
    default="all",
    show_default=True,
    help="Which install location to remove.",
)
def package_uninstall(keep_launch_agent: bool, destination: str) -> None:
    service = PackagingService()
    destinations = None if destination == "all" else [destination]
    result = service.uninstall_app_bundle(
        remove_launch_agent=not keep_launch_agent,
        destinations=destinations,
    )
    click.echo(json.dumps(result, indent=2, sort_keys=True))


@package_cmd.command("launcher-state")
def package_launcher_state() -> None:
    service = PackagingService()
    click.echo(json.dumps(service.launcher_state(), indent=2, sort_keys=True))


@package_cmd.command("launch")
def package_launch() -> None:
    _run_launcher("launch")


@package_cmd.command("restart")
def package_restart() -> None:
    _run_launcher("restart")


def _run_launcher(action: str) -> None:
    service = PackagingService()
    subprocess.run([str(service.launcher_script), action], check=True)


__all__ = ["package_cmd"]

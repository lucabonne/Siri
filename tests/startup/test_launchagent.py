from __future__ import annotations

import plistlib

from openjarvis.startup.launchagent import LaunchAgentManager
from openjarvis.startup.models import LaunchAgentConfig


def test_launchagent_install_validate_and_remove(tmp_path) -> None:
    config = LaunchAgentConfig(
        label="com.openjarvis.test",
        program_arguments=["/bin/echo", "jarvis"],
    )
    manager = LaunchAgentManager(config=config, launch_agents_dir=tmp_path)

    installed = manager.install()

    assert installed.installed is True
    assert installed.valid is True
    with manager.plist_path.open("rb") as handle:
        payload = plistlib.load(handle)
    assert payload["Label"] == "com.openjarvis.test"
    assert payload["RunAtLoad"] is True
    assert payload["KeepAlive"] is False
    assert payload["ProgramArguments"] == ["/bin/echo", "jarvis"]

    removed = manager.remove()

    assert removed.installed is False
    assert manager.plist_path.exists() is False

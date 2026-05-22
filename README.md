# Siri Layer

Personal AI on personal devices.

Siri Layer is a customized local-first AI operating layer built from OpenJarvis. It is designed to run as a private assistant environment for coding, research, desktop awareness, automation, memory, and agent workflows.

The project keeps the original internal package and command structure stable while changing the visible product layer into Siri.

## What this build includes

### Mission Control

Mission Control is the central dashboard for controlling the system.

Current sections include:

- Home
- Today
- World Map
- Tasks
- Agents
- Memory
- Projects
- Terminal
- Research
- Settings
- Permissions

### Local-first agent workspace

The build is structured around a main orchestrator with specialized agents:

- Coding Agent
- Research Agent
- Engineering Agent
- Privacy and Security Agent
- Scheduler Agent
- CAD Agent
- Terminal Agent

### Permission system

The permission model has four levels:

| Level | Name | Purpose |
|---|---|---|
| 0 | Read-only | Analyze, summarize, inspect files, review context |
| 1 | Safe actions | Create notes, draft changes, prepare commands |
| 2 | Confirmed execution | Run shell commands, modify files, install packages, commit changes |
| 3 | Dangerous actions | Requires explicit confirmation for destructive or sensitive operations |

Destructive commands are blocked unless explicit confirmation is provided.

### Packaging and release layer

The build includes the first release and installer foundation:

- macOS install script
- macOS uninstall script
- app packaging script
- release diagnostics script
- backend packaging models
- packaging service updates
- release service updates
- packaging API routes
- packaging and release tests

### Developer tools

The developer layer is intended to support:

- Repo analysis
- Architecture maps
- Semantic search
- Test running
- Terminal error explanation
- Java, Fabric, Gradle, and Minecraft mod workflows
- Live debugging hooks

### Memory and knowledge system

The planned memory layer combines structured and semantic memory:

- SQLite structured memory
- Vector database semantic memory
- File and project index
- Source and citation storage
- Navigable memory UI

### Automation layer

The automation layer is designed for controlled local actions:

- Shell execution
- File operations
- App control
- Browser/search tools
- OS actions
- Permission gates
- Dry-run previews
- Execution logs

## Internal naming note

Visible UI branding is being changed to Siri Layer.

Internal names such as Python packages, CLI commands, imports, folders, and backend identifiers may still use OpenJarvis or Jarvis for compatibility. These should not be renamed until the migration is planned and tested.

## Project direction

### Product path

Installer, notarization, updater, and release app.

### Interaction path

Voice control, wake word or push-to-talk, personalization, and adaptive profiles.

### Intelligence path

Advanced planners, autonomy, long-horizon tasks, and agent coordination.

### Workspace path

CAD expansion, engineering tools, simulations, and project-specific assistants.

"""Built-in controlled automation workflow definitions."""

from __future__ import annotations

from openjarvis.workflows.models import WorkflowDefinition

_WORKFLOW_DATA = [
    {
        "id": "open_project_environment",
        "name": "Open project environment",
        "description": "Stage local project, repository, and terminal context.",
        "required_permissions": ["READ_ONLY"],
        "approval_requirements": [],
        "rollback_hints": ["No mutation is performed."],
        "allowed_agents": ["coding", "engineering", "terminal"],
        "mode_restrictions": ["focus", "coding", "engineering", "privacy"],
        "steps": [
            {
                "id": "project_context",
                "name": "Read project context",
                "tool_name": "terminal_context",
                "description": "Capture passive terminal and project metadata.",
                "required_permission": "READ_ONLY",
                "passive_only": True,
            },
            {
                "id": "git_status",
                "name": "Check repository status",
                "tool_name": "git_status",
                "description": "Inspect the current repository state.",
                "required_permission": "READ_ONLY",
                "passive_only": True,
            },
        ],
    },
    {
        "id": "run_tests",
        "name": "Run tests",
        "description": (
            "Prepare a local test command and queue approval before execution."
        ),
        "required_permissions": ["CONFIRMED_EXECUTION"],
        "approval_requirements": ["Approve the shell command before tests run."],
        "rollback_hints": ["Stop the process; no source files are modified."],
        "allowed_agents": ["coding", "terminal"],
        "mode_restrictions": ["coding", "engineering", "focus"],
        "steps": [
            {
                "id": "terminal_context",
                "name": "Read terminal context",
                "tool_name": "terminal_context",
                "description": (
                    "Review recent terminal history before suggesting tests."
                ),
                "required_permission": "READ_ONLY",
                "passive_only": True,
            },
            {
                "id": "pytest",
                "name": "Queue test command",
                "tool_name": "shell_exec",
                "description": "Request approval for the default Python test command.",
                "arguments": {"command": "python -m pytest -q"},
                "required_permission": "CONFIRMED_EXECUTION",
                "approval_required": True,
                "rollback_hint": "Cancel or deny the queued approval.",
            },
        ],
    },
    {
        "id": "summarize_repo",
        "name": "Summarize repo",
        "description": "Build a local repository summary and store a memory note.",
        "required_permissions": ["READ_ONLY", "CONFIRMED_EXECUTION"],
        "approval_requirements": ["Approve memory write for the generated summary."],
        "rollback_hints": ["Delete the workflow memory entry if it is not useful."],
        "allowed_agents": ["engineering", "coding", "privacy"],
        "mode_restrictions": ["focus", "coding", "engineering", "privacy"],
        "steps": [
            {
                "id": "repo_index",
                "name": "Read repo index",
                "tool_name": "repo_index_search",
                "description": "Use local repo indexing metadata.",
                "required_permission": "READ_ONLY",
                "passive_only": True,
            },
            {
                "id": "memory_summary",
                "name": "Queue summary memory",
                "tool_name": "memory_manage",
                "description": "Ask approval before writing the summary to memory.",
                "arguments": {"action": "create", "memory_type": "workflow_summary"},
                "required_permission": "CONFIRMED_EXECUTION",
                "approval_required": True,
                "rollback_hint": "Delete the created memory record.",
            },
        ],
    },
    {
        "id": "prepare_research_session",
        "name": "Prepare research session",
        "description": (
            "Set up local research context without starting external search."
        ),
        "required_permissions": ["READ_ONLY", "SAFE_ACTION"],
        "approval_requirements": [],
        "rollback_hints": ["Discard the prepared research context."],
        "allowed_agents": ["research", "engineering", "privacy"],
        "mode_restrictions": ["research", "engineering", "focus", "privacy"],
        "steps": [
            {
                "id": "memory_search",
                "name": "Read related memory",
                "tool_name": "knowledge_search",
                "description": "Gather local memory and source context.",
                "required_permission": "READ_ONLY",
                "passive_only": True,
            },
            {
                "id": "research_plan",
                "name": "Prepare local plan",
                "tool_name": "think",
                "description": "Prepare a source-aware local research plan.",
                "required_permission": "READ_ONLY",
                "passive_only": True,
            },
        ],
    },
    {
        "id": "collect_logs",
        "name": "Collect logs",
        "description": "Collect local terminal and permission logs for review.",
        "required_permissions": ["READ_ONLY"],
        "approval_requirements": [],
        "rollback_hints": ["No mutation is performed."],
        "allowed_agents": ["terminal", "engineering", "privacy"],
        "mode_restrictions": ["focus", "coding", "engineering", "privacy"],
        "steps": [
            {
                "id": "terminal_history",
                "name": "Read terminal history",
                "tool_name": "terminal_history",
                "description": "Collect passive terminal history.",
                "required_permission": "READ_ONLY",
                "passive_only": True,
            },
            {
                "id": "permission_audit",
                "name": "Read permission audit",
                "tool_name": "file_read",
                "description": "Read the local permission audit file when available.",
                "required_permission": "READ_ONLY",
                "passive_only": True,
            },
        ],
    },
    {
        "id": "backup_notes",
        "name": "Backup notes",
        "description": "Prepare a local notes backup and queue file-write approval.",
        "required_permissions": ["READ_ONLY", "CONFIRMED_EXECUTION"],
        "approval_requirements": ["Approve the file write before backup is created."],
        "rollback_hints": ["Delete the generated backup file."],
        "allowed_agents": ["terminal", "scheduler", "privacy"],
        "mode_restrictions": ["focus", "quiet", "privacy"],
        "steps": [
            {
                "id": "scan_notes",
                "name": "Read notes metadata",
                "tool_name": "file_read",
                "description": "Inspect local notes paths before backup.",
                "required_permission": "READ_ONLY",
                "passive_only": True,
            },
            {
                "id": "write_backup",
                "name": "Queue backup write",
                "tool_name": "file_write",
                "description": "Request approval before writing a local backup.",
                "arguments": {"path": "~/.openjarvis/backups/notes.json"},
                "required_permission": "CONFIRMED_EXECUTION",
                "approval_required": True,
                "rollback_hint": "Remove the backup file.",
            },
        ],
    },
    {
        "id": "launch_coding_workspace",
        "name": "Launch coding workspace",
        "description": "Stage coding agent, repo context, and terminal suggestions.",
        "required_permissions": ["READ_ONLY"],
        "approval_requirements": [],
        "rollback_hints": ["Switch back to the previous active agent or mode."],
        "allowed_agents": ["coding", "engineering", "terminal"],
        "mode_restrictions": ["coding", "engineering", "focus"],
        "steps": [
            {
                "id": "active_agent",
                "name": "Resolve coding agent",
                "tool_name": "file_read",
                "description": "Resolve allowed coding workspace agents.",
                "required_permission": "READ_ONLY",
                "passive_only": True,
            },
            {
                "id": "repo_context",
                "name": "Read repo context",
                "tool_name": "repo_index_search",
                "description": "Prepare local repository context.",
                "required_permission": "READ_ONLY",
                "passive_only": True,
            },
        ],
    },
    {
        "id": "start_morning_workflow",
        "name": "Start morning workflow",
        "description": "Prepare local morning context, briefing cache, and tasks.",
        "required_permissions": ["READ_ONLY", "SAFE_ACTION"],
        "approval_requirements": [],
        "rollback_hints": ["Discard generated local briefing context."],
        "allowed_agents": ["scheduler", "research", "engineering"],
        "mode_restrictions": ["focus", "research", "quiet", "privacy"],
        "steps": [
            {
                "id": "tasks",
                "name": "Read local tasks",
                "tool_name": "list_scheduled_tasks",
                "description": "Read local scheduled tasks.",
                "required_permission": "READ_ONLY",
                "passive_only": True,
            },
            {
                "id": "briefing",
                "name": "Collect local digest",
                "tool_name": "digest_collect",
                "description": "Collect locally available digest inputs.",
                "required_permission": "SAFE_ACTION",
                "local_only": True,
                "passive_only": True,
            },
        ],
    },
]


def builtin_workflows() -> list[WorkflowDefinition]:
    return [WorkflowDefinition.from_mapping(item) for item in _WORKFLOW_DATA]


def workflow_map() -> dict[str, WorkflowDefinition]:
    return {workflow.id: workflow for workflow in builtin_workflows()}


__all__ = ["builtin_workflows", "workflow_map"]

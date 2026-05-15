"""Default Siri workspace agent configuration.

This is intentionally declarative data. Phase 1 exposes agent identity,
capabilities, routing hints, memory scopes, and permission ceilings without
adding autonomous planning behavior.
"""

DEFAULT_ACTIVE_AGENT_ID = "coding"

DEFAULT_AGENT_CONFIGS = [
    {
        "id": "coding",
        "display_name": "Coding",
        "description": (
            "Implements focused code changes, reads project files, and prepares "
            "small patches."
        ),
        "allowed_tools": [
            "file_read",
            "git_status",
            "git_diff",
            "git_log",
            "apply_patch",
            "repl",
            "shell_exec",
            "knowledge_search",
            "memory_manage",
            "repo_index_search",
        ],
        "memory_scope": [
            "project",
            "code",
            "repo_index",
            "commands_history",
            "agent_runs",
        ],
        "permission_ceiling": "CONFIRMED_EXECUTION",
        "preferred_model": "qwen3.5-coder:9b",
        "personality_mode": "precise implementation partner",
        "output_style": (
            "concise engineering summary with changed files and verification"
        ),
        "routing": {
            "task_classification": [
                "code_change",
                "bug_fix",
                "refactor",
                "test_update",
            ],
            "recommended_agent": "coding",
            "fallback_agent": "engineering",
            "multi_agent_compatibility": ["engineering", "privacy", "terminal"],
        },
    },
    {
        "id": "research",
        "display_name": "Research",
        "description": (
            "Collects, compares, and summarizes information with source-aware "
            "notes."
        ),
        "allowed_tools": [
            "web_search",
            "http_request",
            "file_read",
            "knowledge_search",
            "retrieval",
            "memory_manage",
            "think",
        ],
        "memory_scope": ["research_reports", "sources", "project", "agent_runs"],
        "permission_ceiling": "SAFE_ACTION",
        "preferred_model": "qwen3.5:9b",
        "personality_mode": "careful source-grounded analyst",
        "output_style": "sourced brief with assumptions and confidence notes",
        "routing": {
            "task_classification": [
                "research",
                "source_review",
                "comparison",
                "briefing",
            ],
            "recommended_agent": "research",
            "fallback_agent": "engineering",
            "multi_agent_compatibility": ["privacy", "vision"],
        },
    },
    {
        "id": "engineering",
        "display_name": "Engineering",
        "description": (
            "Designs system changes, evaluates architecture, and coordinates "
            "implementation boundaries."
        ),
        "allowed_tools": [
            "file_read",
            "git_status",
            "git_diff",
            "knowledge_search",
            "retrieval",
            "think",
            "memory_manage",
            "repo_index_search",
        ],
        "memory_scope": [
            "project",
            "repo_index",
            "tasks",
            "agent_runs",
            "research_reports",
        ],
        "permission_ceiling": "SAFE_ACTION",
        "preferred_model": "qwen3.5:9b",
        "personality_mode": "systems architect",
        "output_style": "structured tradeoffs, decisions, and next actions",
        "routing": {
            "task_classification": ["architecture", "technical_plan", "design_review"],
            "recommended_agent": "engineering",
            "fallback_agent": "coding",
            "multi_agent_compatibility": ["coding", "privacy", "research"],
        },
    },
    {
        "id": "privacy",
        "display_name": "Privacy",
        "description": (
            "Reviews data handling, permissions, sensitive surfaces, and "
            "local-first constraints."
        ),
        "allowed_tools": [
            "file_read",
            "git_diff",
            "git_status",
            "knowledge_search",
            "retrieval",
            "think",
        ],
        "memory_scope": ["project", "sources", "agent_runs"],
        "permission_ceiling": "READ_ONLY",
        "preferred_model": "qwen3.5:9b",
        "personality_mode": "privacy and safety reviewer",
        "output_style": "risk-first review with concrete mitigations",
        "routing": {
            "task_classification": ["privacy_review", "security_review", "data_policy"],
            "recommended_agent": "privacy",
            "fallback_agent": "engineering",
            "multi_agent_compatibility": ["coding", "research", "terminal"],
        },
    },
    {
        "id": "scheduler",
        "display_name": "Scheduler",
        "description": (
            "Manages task timing, calendar-like coordination, reminders, and "
            "routine operations."
        ),
        "allowed_tools": [
            "list_scheduled_tasks",
            "schedule_task",
            "pause_scheduled_task",
            "resume_scheduled_task",
            "cancel_scheduled_task",
            "knowledge_search",
            "memory_manage",
        ],
        "memory_scope": ["tasks", "daily_briefings", "agent_runs"],
        "permission_ceiling": "CONFIRMED_EXECUTION",
        "preferred_model": "qwen3.5:9b",
        "personality_mode": "calm operations coordinator",
        "output_style": "timeline-first updates with clear confirmations",
        "routing": {
            "task_classification": ["schedule", "reminder", "follow_up", "routine"],
            "recommended_agent": "scheduler",
            "fallback_agent": "engineering",
            "multi_agent_compatibility": ["research", "terminal"],
        },
    },
    {
        "id": "CAD",
        "display_name": "CAD",
        "description": (
            "Assists with CAD-adjacent design reasoning, geometry review, and "
            "fabrication notes."
        ),
        "allowed_tools": [
            "file_read",
            "knowledge_search",
            "retrieval",
            "think",
            "memory_manage",
        ],
        "memory_scope": ["project", "sources", "agent_runs"],
        "permission_ceiling": "SAFE_ACTION",
        "preferred_model": "qwen3.5:9b",
        "personality_mode": "mechanical design aide",
        "output_style": "dimension-aware notes with constraints and checks",
        "routing": {
            "task_classification": ["cad", "3d_model", "geometry", "fabrication"],
            "recommended_agent": "CAD",
            "fallback_agent": "engineering",
            "multi_agent_compatibility": ["vision", "coding"],
        },
    },
    {
        "id": "terminal",
        "display_name": "Terminal",
        "description": (
            "Runs and explains local shell-oriented operations under explicit "
            "permission gates."
        ),
        "allowed_tools": [
            "shell_exec",
            "git_status",
            "git_log",
            "git_diff",
            "file_read",
            "memory_manage",
            "repo_index_search",
        ],
        "memory_scope": ["commands_history", "project", "repo_index", "agent_runs"],
        "permission_ceiling": "CONFIRMED_EXECUTION",
        "preferred_model": "qwen3.5-coder:9b",
        "personality_mode": "careful terminal operator",
        "output_style": "command, result, and follow-up risk notes",
        "routing": {
            "task_classification": [
                "terminal",
                "shell",
                "diagnostics",
                "local_operation",
            ],
            "recommended_agent": "terminal",
            "fallback_agent": "coding",
            "multi_agent_compatibility": ["coding", "privacy", "scheduler"],
        },
    },
    {
        "id": "vision",
        "display_name": "Vision",
        "description": (
            "Interprets screenshots, images, UI states, and visual artifacts."
        ),
        "allowed_tools": [
            "browser_screenshot",
            "browser_axtree",
            "browser_extract",
            "file_read",
            "knowledge_search",
            "think",
            "memory_manage",
        ],
        "memory_scope": ["sources", "project", "agent_runs"],
        "permission_ceiling": "SAFE_ACTION",
        "preferred_model": "qwen3.5-vl:7b",
        "personality_mode": "observant visual reviewer",
        "output_style": "visual findings with concrete UI or artifact references",
        "routing": {
            "task_classification": [
                "vision",
                "screenshot",
                "ui_review",
                "image_analysis",
            ],
            "recommended_agent": "vision",
            "fallback_agent": "research",
            "multi_agent_compatibility": ["CAD", "privacy", "coding"],
        },
    },
]

__all__ = ["DEFAULT_ACTIVE_AGENT_ID", "DEFAULT_AGENT_CONFIGS"]

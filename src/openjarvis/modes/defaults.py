"""Default Siri operating modes.

The mode system is intentionally declarative. Phase 1 exposes global behavior
metadata and policy hints without adding autonomous orchestration.
"""

DEFAULT_ACTIVE_MODE_ID = "focus"

DEFAULT_MODE_CONFIGS = [
    {
        "id": "focus",
        "display_name": "Focus",
        "description": "Keeps Siri direct, calm, and task-centered.",
        "verbosity_level": "concise",
        "proactive_level": "low",
        "interruption_policy": "priority_only",
        "preferred_agents": ["coding", "engineering"],
        "memory_behavior": {
            "read": True,
            "write": "important_only",
            "scopes": ["project", "tasks", "agent_runs"],
        },
        "privacy_network_policy": {
            "cloud_apis": "allowed",
            "remote_mcp": "allowed",
            "outbound_network": "allowed",
            "localhost_network": "allowed",
            "allowed_engines": ["ollama", "local", "cloud"],
        },
        "default_model_overrides": {
            "engine": "",
            "model": "",
            "temperature": 0.3,
        },
        "ui_theme_metadata": {
            "tone": "focused",
            "accent": "blue",
            "icon": "target",
        },
        "notification_behavior": {
            "level": "priority",
            "sound": False,
            "batch": True,
        },
    },
    {
        "id": "research",
        "display_name": "Research",
        "description": (
            "Prioritizes source gathering, comparisons, and careful synthesis."
        ),
        "verbosity_level": "detailed",
        "proactive_level": "medium",
        "interruption_policy": "normal",
        "preferred_agents": ["research", "engineering", "privacy"],
        "memory_behavior": {
            "read": True,
            "write": "sources_and_findings",
            "scopes": ["research_reports", "sources", "project", "agent_runs"],
        },
        "privacy_network_policy": {
            "cloud_apis": "allowed",
            "remote_mcp": "allowed",
            "outbound_network": "allowed",
            "localhost_network": "allowed",
            "allowed_engines": ["ollama", "local", "cloud"],
        },
        "default_model_overrides": {
            "engine": "",
            "model": "",
            "temperature": 0.2,
        },
        "ui_theme_metadata": {
            "tone": "analytical",
            "accent": "teal",
            "icon": "search",
        },
        "notification_behavior": {
            "level": "findings",
            "sound": False,
            "batch": True,
        },
    },
    {
        "id": "creative",
        "display_name": "Creative",
        "description": (
            "Opens up ideation, drafts, variants, and expressive exploration."
        ),
        "verbosity_level": "expanded",
        "proactive_level": "medium",
        "interruption_policy": "low_friction",
        "preferred_agents": ["research", "engineering"],
        "memory_behavior": {
            "read": True,
            "write": "drafts_and_preferences",
            "scopes": ["project", "sources", "agent_runs"],
        },
        "privacy_network_policy": {
            "cloud_apis": "allowed",
            "remote_mcp": "allowed",
            "outbound_network": "allowed",
            "localhost_network": "allowed",
            "allowed_engines": ["ollama", "local", "cloud"],
        },
        "default_model_overrides": {
            "engine": "",
            "model": "",
            "temperature": 0.8,
        },
        "ui_theme_metadata": {
            "tone": "expressive",
            "accent": "rose",
            "icon": "sparkles",
        },
        "notification_behavior": {
            "level": "normal",
            "sound": False,
            "batch": False,
        },
    },
    {
        "id": "quiet",
        "display_name": "Quiet",
        "description": "Minimizes interruptions and keeps responses short.",
        "verbosity_level": "minimal",
        "proactive_level": "off",
        "interruption_policy": "do_not_interrupt",
        "preferred_agents": ["privacy", "engineering"],
        "memory_behavior": {
            "read": True,
            "write": "manual_only",
            "scopes": ["project", "tasks"],
        },
        "privacy_network_policy": {
            "cloud_apis": "allowed",
            "remote_mcp": "allowed",
            "outbound_network": "allowed",
            "localhost_network": "allowed",
            "allowed_engines": ["ollama", "local", "cloud"],
        },
        "default_model_overrides": {
            "engine": "",
            "model": "",
            "temperature": 0.1,
        },
        "ui_theme_metadata": {
            "tone": "muted",
            "accent": "slate",
            "icon": "moon",
        },
        "notification_behavior": {
            "level": "critical_only",
            "sound": False,
            "batch": True,
        },
    },
    {
        "id": "coding",
        "display_name": "Coding",
        "description": (
            "Optimizes for code reading, implementation, tests, and patch summaries."
        ),
        "verbosity_level": "balanced",
        "proactive_level": "low",
        "interruption_policy": "normal",
        "preferred_agents": ["coding", "terminal", "engineering"],
        "memory_behavior": {
            "read": True,
            "write": "project_decisions",
            "scopes": ["project", "code", "commands_history", "agent_runs"],
        },
        "privacy_network_policy": {
            "cloud_apis": "allowed",
            "remote_mcp": "allowed",
            "outbound_network": "allowed",
            "localhost_network": "allowed",
            "allowed_engines": ["ollama", "local", "cloud"],
        },
        "default_model_overrides": {
            "engine": "",
            "model": "qwen3.5-coder:9b",
            "temperature": 0.2,
        },
        "ui_theme_metadata": {
            "tone": "implementation",
            "accent": "green",
            "icon": "code",
        },
        "notification_behavior": {
            "level": "task_changes",
            "sound": False,
            "batch": False,
        },
    },
    {
        "id": "engineering",
        "display_name": "Engineering",
        "description": (
            "Emphasizes systems thinking, tradeoffs, and implementation boundaries."
        ),
        "verbosity_level": "detailed",
        "proactive_level": "medium",
        "interruption_policy": "normal",
        "preferred_agents": ["engineering", "coding", "privacy"],
        "memory_behavior": {
            "read": True,
            "write": "decisions_and_risks",
            "scopes": ["project", "tasks", "research_reports", "agent_runs"],
        },
        "privacy_network_policy": {
            "cloud_apis": "allowed",
            "remote_mcp": "allowed",
            "outbound_network": "allowed",
            "localhost_network": "allowed",
            "allowed_engines": ["ollama", "local", "cloud"],
        },
        "default_model_overrides": {
            "engine": "",
            "model": "",
            "temperature": 0.25,
        },
        "ui_theme_metadata": {
            "tone": "systems",
            "accent": "amber",
            "icon": "cog",
        },
        "notification_behavior": {
            "level": "decisions",
            "sound": False,
            "batch": True,
        },
    },
    {
        "id": "privacy",
        "display_name": "Privacy",
        "description": (
            "Locks Siri to local-first behavior and blocks cloud or remote surfaces."
        ),
        "verbosity_level": "balanced",
        "proactive_level": "off",
        "interruption_policy": "priority_only",
        "preferred_agents": ["privacy", "engineering"],
        "memory_behavior": {
            "read": True,
            "write": "local_only",
            "scopes": ["project", "agent_runs"],
            "sensitive_retention": "minimize",
        },
        "privacy_network_policy": {
            "cloud_apis": "disabled",
            "remote_mcp": "disabled",
            "outbound_network": "localhost_only",
            "localhost_network": "allowed",
            "allowed_engines": ["ollama", "local", "llamacpp", "vllm"],
        },
        "voice_capture_behavior": {
            "enabled_by_default": False,
            "activation": "push_to_talk_only",
            "wake_word": "disabled",
            "background_recording": "disabled",
            "requires_explicit_approval": True,
            "raw_audio_storage": "off_by_default",
            "transcription": "local_only",
        },
        "default_model_overrides": {
            "engine": "ollama",
            "model": "",
            "temperature": 0.2,
            "allow_cloud": False,
        },
        "ui_theme_metadata": {
            "tone": "private",
            "accent": "emerald",
            "icon": "shield",
        },
        "notification_behavior": {
            "level": "security_only",
            "sound": False,
            "batch": True,
        },
    },
]

__all__ = ["DEFAULT_ACTIVE_MODE_ID", "DEFAULT_MODE_CONFIGS"]

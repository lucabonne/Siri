//! Minimal Rust permission policy for tool execution.
//!
//! This mirrors the Python `PermissionMiddleware` concepts without adding a
//! cross-language runtime dependency. Keep labels and path rules aligned with
//! `src/openjarvis/security/permissions.py` and `file_policy.py`.

use crate::file_policy::{has_path_traversal, is_protected_path, is_sensitive_path};
use once_cell::sync::Lazy;
use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashSet;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum PermissionLevel {
    ReadOnly,
    SafeAction,
    ConfirmedExecution,
    Dangerous,
}

impl PermissionLevel {
    pub fn as_str(&self) -> &'static str {
        match self {
            PermissionLevel::ReadOnly => "READ_ONLY",
            PermissionLevel::SafeAction => "SAFE_ACTION",
            PermissionLevel::ConfirmedExecution => "CONFIRMED_EXECUTION",
            PermissionLevel::Dangerous => "DANGEROUS",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PermissionAction {
    Allow,
    RequireConfirmation,
    Deny,
}

impl PermissionAction {
    pub fn as_str(&self) -> &'static str {
        match self {
            PermissionAction::Allow => "allow",
            PermissionAction::RequireConfirmation => "require_confirmation",
            PermissionAction::Deny => "deny",
        }
    }
}

#[derive(Debug, Clone)]
pub struct PermissionRequest<'a> {
    pub tool_name: &'a str,
    pub arguments: &'a Value,
    pub agent_id: Option<&'a str>,
    pub command: Option<&'a str>,
    pub source: &'a str,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PermissionDecision {
    pub action: PermissionAction,
    pub level: PermissionLevel,
    pub reason: String,
    pub matched_pattern: Option<String>,
    pub dry_run: bool,
    pub would_action: Option<PermissionAction>,
}

impl PermissionDecision {
    pub fn allowed(&self) -> bool {
        self.action == PermissionAction::Allow
    }

    pub fn denied(&self) -> bool {
        self.action == PermissionAction::Deny
    }

    pub fn requires_confirmation(&self) -> bool {
        self.action == PermissionAction::RequireConfirmation
    }
}

#[derive(Debug, Clone)]
pub struct PermissionPolicy {
    audit_log_path: PathBuf,
}

impl Default for PermissionPolicy {
    fn default() -> Self {
        Self {
            audit_log_path: default_audit_log_path(),
        }
    }
}

impl PermissionPolicy {
    pub fn new(audit_log_path: impl Into<PathBuf>) -> Self {
        Self {
            audit_log_path: audit_log_path.into(),
        }
    }

    pub fn audit_log_path(&self) -> &Path {
        &self.audit_log_path
    }

    pub fn check(&self, request: &PermissionRequest<'_>) -> PermissionDecision {
        let (level, mut reason, matched_pattern) = self.classify(request);
        let mut action = action_for_level(level);
        let dry_run = request
            .arguments
            .get("dry_run")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let mut would_action = None;

        if dry_run {
            reason = format!("dry_run: would {} ({})", action.as_str(), reason);
            would_action = Some(action);
            action = PermissionAction::Allow;
        }

        let decision = PermissionDecision {
            action,
            level,
            reason,
            matched_pattern,
            dry_run,
            would_action,
        };
        self.audit(request, &decision);
        decision
    }

    pub fn classify(
        &self,
        request: &PermissionRequest<'_>,
    ) -> (PermissionLevel, String, Option<String>) {
        let tool_name = request.tool_name;
        let command = request
            .command
            .map(ToOwned::to_owned)
            .unwrap_or_else(|| extract_command(request.arguments));

        if tool_name == "shell_exec" || looks_like_shell_tool(tool_name) {
            let (level, reason, matched) = classify_shell_command(&command);
            if tool_name != "shell_exec" && level == PermissionLevel::ConfirmedExecution {
                return (
                    level,
                    format!("MCP shell-style tool requires confirmation: {tool_name}"),
                    matched,
                );
            }
            return (level, reason, matched);
        }

        if tool_name == "file_read" {
            if let Some(path) = string_arg(request.arguments, "path") {
                let path = Path::new(path);
                if is_sensitive_path(path) {
                    return (
                        PermissionLevel::Dangerous,
                        "sensitive file read blocked".into(),
                        Some("sensitive-path".into()),
                    );
                }
            }
        }

        if matches!(tool_name, "file_write" | "apply_patch") {
            if let Some(reason) = blocked_file_write_reason(request.arguments) {
                return (
                    PermissionLevel::Dangerous,
                    reason,
                    Some("protected-path".into()),
                );
            }
        }

        if tool_name == "http_request" {
            let method = string_arg(request.arguments, "method")
                .unwrap_or("GET")
                .to_uppercase();
            if matches!(method.as_str(), "POST" | "PUT" | "PATCH" | "DELETE") {
                return (
                    PermissionLevel::ConfirmedExecution,
                    format!("http_request with mutating method {method}"),
                    None,
                );
            }
        }

        if tool_name == "memory_manage" {
            let action = string_arg(request.arguments, "action")
                .unwrap_or("read")
                .to_lowercase();
            if action == "read" {
                return (PermissionLevel::ReadOnly, "memory read".into(), None);
            }
            return (
                PermissionLevel::ConfirmedExecution,
                format!("memory {action}"),
                None,
            );
        }

        if READ_ONLY_TOOLS.contains(tool_name) {
            return (PermissionLevel::ReadOnly, "read-only tool".into(), None);
        }
        if SAFE_ACTION_TOOLS.contains(tool_name) {
            return (PermissionLevel::SafeAction, "safe action tool".into(), None);
        }
        if CONFIRMED_TOOLS.contains(tool_name) {
            return (
                PermissionLevel::ConfirmedExecution,
                "tool requires confirmation".into(),
                None,
            );
        }

        if let Some(level) = classify_mcp_style_tool(tool_name) {
            return (
                level,
                format!("MCP-style {} tool", level.as_str().to_lowercase()),
                None,
            );
        }

        (
            PermissionLevel::SafeAction,
            "unclassified tool defaults to safe action".into(),
            None,
        )
    }

    fn audit(&self, request: &PermissionRequest<'_>, decision: &PermissionDecision) {
        if let Some(parent) = self.audit_log_path.parent() {
            if std::fs::create_dir_all(parent).is_err() {
                return;
            }
            set_owner_only_dir_permissions(parent);
        }

        let argument_keys = request
            .arguments
            .as_object()
            .map(|obj| {
                let mut keys = obj.keys().cloned().collect::<Vec<_>>();
                keys.sort();
                keys
            })
            .unwrap_or_default();

        let command_preview = request
            .command
            .map(ToOwned::to_owned)
            .unwrap_or_else(|| extract_command(request.arguments))
            .chars()
            .take(200)
            .collect::<String>();

        let record = json!({
            "timestamp": chrono::Utc::now().to_rfc3339(),
            "agent_id": request.agent_id.unwrap_or(""),
            "tool": request.tool_name,
            "action": decision.action.as_str(),
            "level": decision.level.as_str(),
            "reason": decision.reason,
            "matched_pattern": decision.matched_pattern,
            "dry_run": decision.dry_run,
            "argument_keys": argument_keys,
            "command_preview": command_preview,
            "request_metadata": {"source": request.source},
            "metadata": {
                "would_action": decision.would_action.as_ref().map(PermissionAction::as_str),
                "would_level": if decision.dry_run { Some(decision.level.as_str()) } else { None },
            },
        });

        if let Ok(mut file) = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.audit_log_path)
        {
            let _ = writeln!(file, "{}", record);
            set_owner_only_permissions(&self.audit_log_path);
        }
    }
}

pub fn classify_shell_command(command: &str) -> (PermissionLevel, String, Option<String>) {
    let normalized = command.split_whitespace().collect::<Vec<_>>().join(" ");
    if normalized.is_empty() {
        return (
            PermissionLevel::SafeAction,
            "empty shell command".into(),
            None,
        );
    }

    for (label, pattern) in DANGEROUS_COMMAND_PATTERNS.iter() {
        if pattern.is_match(&normalized) {
            return (
                PermissionLevel::Dangerous,
                format!("dangerous shell command pattern: {label}"),
                Some((*label).into()),
            );
        }
    }

    (
        PermissionLevel::ConfirmedExecution,
        "shell command requires confirmation".into(),
        None,
    )
}

pub fn blocked_file_write_reason(arguments: &Value) -> Option<String> {
    let path = string_arg(arguments, "path")?;
    let path = Path::new(path);

    if has_path_traversal(path) {
        return Some("path traversal blocked".into());
    }
    if is_sensitive_path(path) {
        return Some("sensitive file write blocked".into());
    }
    if is_protected_path(path) {
        return Some("protected path write blocked".into());
    }

    None
}

fn action_for_level(level: PermissionLevel) -> PermissionAction {
    match level {
        PermissionLevel::Dangerous => PermissionAction::Deny,
        PermissionLevel::ConfirmedExecution => PermissionAction::RequireConfirmation,
        PermissionLevel::ReadOnly | PermissionLevel::SafeAction => PermissionAction::Allow,
    }
}

fn extract_command(arguments: &Value) -> String {
    for key in ["command", "cmd", "shell_command", "script"] {
        if let Some(value) = arguments.get(key) {
            return value
                .as_str()
                .map(ToOwned::to_owned)
                .unwrap_or_else(|| value.to_string());
        }
    }
    String::new()
}

fn string_arg<'a>(arguments: &'a Value, key: &str) -> Option<&'a str> {
    arguments.get(key).and_then(Value::as_str)
}

fn looks_like_shell_tool(tool_name: &str) -> bool {
    let normalized = tool_name.to_lowercase().replace('-', "_");
    ["shell", "terminal", "bash", "zsh", "run_command"]
        .iter()
        .any(|token| normalized.contains(token))
}

fn classify_mcp_style_tool(tool_name: &str) -> Option<PermissionLevel> {
    let normalized = tool_name.to_lowercase().replace('-', "_");
    if ["read_file", "get_file"]
        .iter()
        .any(|token| normalized.contains(token))
    {
        return Some(PermissionLevel::ReadOnly);
    }
    if [
        "write_file",
        "create_file",
        "edit_file",
        "patch_file",
        "delete_file",
        "remove_file",
        "apply_patch",
        "run_code",
        "execute_code",
        "python",
    ]
    .iter()
    .any(|token| normalized.contains(token))
    {
        return Some(PermissionLevel::ConfirmedExecution);
    }
    None
}

fn default_audit_log_path() -> PathBuf {
    std::env::var_os("OPENJARVIS_PERMISSION_AUDIT_LOG")
        .map(PathBuf::from)
        .or_else(|| {
            std::env::var_os("HOME")
                .map(PathBuf::from)
                .map(|home| home.join(".openjarvis/logs/permissions.log"))
        })
        .unwrap_or_else(|| PathBuf::from(".openjarvis/logs/permissions.log"))
}

#[cfg(unix)]
fn set_owner_only_permissions(path: &Path) {
    use std::os::unix::fs::PermissionsExt;

    if let Ok(metadata) = std::fs::metadata(path) {
        let mut permissions = metadata.permissions();
        permissions.set_mode(0o600);
        let _ = std::fs::set_permissions(path, permissions);
    }
}

#[cfg(not(unix))]
fn set_owner_only_permissions(_path: &Path) {}

#[cfg(unix)]
fn set_owner_only_dir_permissions(path: &Path) {
    use std::os::unix::fs::PermissionsExt;

    if let Ok(metadata) = std::fs::metadata(path) {
        let mut permissions = metadata.permissions();
        permissions.set_mode(0o700);
        let _ = std::fs::set_permissions(path, permissions);
    }
}

#[cfg(not(unix))]
fn set_owner_only_dir_permissions(_path: &Path) {}

static READ_ONLY_TOOLS: Lazy<HashSet<&'static str>> = Lazy::new(|| {
    HashSet::from([
        "browser_axtree",
        "browser_extract",
        "browser_screenshot",
        "calculator",
        "channel_list",
        "channel_status",
        "db_query",
        "file_read",
        "git_diff",
        "git_log",
        "git_status",
        "kg_neighbors",
        "kg_query",
        "knowledge_search",
        "list_scheduled_tasks",
        "retrieval",
        "scan_chunks",
        "think",
        "web_search",
    ])
});

static SAFE_ACTION_TOOLS: Lazy<HashSet<&'static str>> = Lazy::new(|| {
    HashSet::from([
        "agent_list",
        "browser_click",
        "browser_navigate",
        "browser_type",
        "digest_collect",
        "http_request",
        "knowledge_sql",
        "llm_tool",
        "mcp_adapter",
        "pdf_tool",
        "repl",
        "schedule_task",
        "skill_manage",
        "text_to_speech",
        "user_profile_manage",
    ])
});

static CONFIRMED_TOOLS: Lazy<HashSet<&'static str>> = Lazy::new(|| {
    HashSet::from([
        "agent_kill",
        "agent_send",
        "agent_spawn",
        "apply_patch",
        "cancel_scheduled_task",
        "channel_send",
        "code_interpreter",
        "code_interpreter_docker",
        "file_write",
        "git_commit",
        "kg_add_entity",
        "kg_add_relation",
        "memory_manage",
        "pause_scheduled_task",
        "repl",
        "resume_scheduled_task",
        "shell_exec",
        "storage_delete",
        "storage_put",
    ])
});

static DANGEROUS_COMMAND_PATTERNS: Lazy<Vec<(&'static str, Regex)>> = Lazy::new(|| {
    vec![
        (
            "recursive-root-delete",
            Regex::new(r"(?i)\brm\s+[^;&|]*-[^\s;&|]*r[f]?[^\s;&|]*\s+/(?:\s|$)").unwrap(),
        ),
        (
            "home-delete",
            Regex::new(r"(?i)\brm\s+[^;&|]*-[^\s;&|]*r[f]?[^\s;&|]*\s+~(?:/|\s|$)").unwrap(),
        ),
        (
            "force-clean-current-dir",
            Regex::new(r"(?i)\brm\s+[^;&|]*-[^\s;&|]*r[f]?[^\s;&|]*\s+\.(?:\s|$)").unwrap(),
        ),
        (
            "disk-format",
            Regex::new(r"(?i)\b(?:mkfs|fdisk|parted|diskutil\s+erase|diskutil\s+partition)\b")
                .unwrap(),
        ),
        (
            "raw-disk-write",
            Regex::new(r"(?i)\bdd\s+.*\bof=/dev/(?:disk|rdisk|sd|nvme)").unwrap(),
        ),
        (
            "privilege-escalation",
            Regex::new(r"(?i)\b(?:sudo|su)\b").unwrap(),
        ),
        (
            "permission-recursive-root",
            Regex::new(r"(?i)\b(?:chmod|chown|chgrp)\s+[^;&|]*-R[^;&|]*\s+/(?:\s|$)").unwrap(),
        ),
        (
            "shutdown",
            Regex::new(r"(?i)\b(?:shutdown|reboot|halt|poweroff)\b").unwrap(),
        ),
        (
            "fork-bomb",
            Regex::new(r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;?\s*:").unwrap(),
        ),
        (
            "pipe-to-shell",
            Regex::new(r"(?i)\b(?:curl|wget)\b.*\|\s*(?:sh|bash|zsh|python|perl)\b").unwrap(),
        ),
        (
            "git-destructive",
            Regex::new(r"(?i)\bgit\s+(?:reset\s+--hard|clean\s+-[^\s;&|]*f)").unwrap(),
        ),
        ("kill-all", Regex::new(r"(?i)\bkill\s+-9\s+-1\b").unwrap()),
    ]
});

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_shell_dangerous_detection() {
        let (level, reason, matched) = classify_shell_command("sudo rm -rf /");
        assert_eq!(level, PermissionLevel::Dangerous);
        assert!(reason.contains("dangerous shell command"));
        assert!(matched.is_some());
    }

    #[test]
    fn test_shell_requires_confirmation() {
        let (level, _, matched) = classify_shell_command("ls -la");
        assert_eq!(level, PermissionLevel::ConfirmedExecution);
        assert_eq!(matched, None);
    }

    #[test]
    fn test_file_write_protected_path() {
        let reason = blocked_file_write_reason(&json!({"path": "/etc/openjarvis.conf"}));
        assert_eq!(reason.as_deref(), Some("protected path write blocked"));
    }

    #[test]
    fn test_policy_writes_audit_log() {
        let dir = tempfile::tempdir().unwrap();
        let audit_path = dir.path().join("permissions.log");
        let policy = PermissionPolicy::new(&audit_path);
        let decision = policy.check(&PermissionRequest {
            tool_name: "calculator",
            arguments: &json!({"expression": "2+2"}),
            agent_id: Some("agent-1"),
            command: None,
            source: "test",
        });

        assert!(decision.allowed());
        let contents = std::fs::read_to_string(audit_path).unwrap();
        assert!(contents.contains("\"tool\":\"calculator\""));
        assert!(contents.contains("\"source\":\"test\""));
    }
}

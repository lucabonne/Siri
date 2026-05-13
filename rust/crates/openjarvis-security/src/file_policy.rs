//! File sensitivity policy — block access to secrets, credentials, keys,
//! and protected write locations.

use once_cell::sync::Lazy;
use std::collections::HashSet;
use std::path::{Component, Path, PathBuf};

static SENSITIVE_PATTERNS: Lazy<HashSet<&'static str>> = Lazy::new(|| {
    HashSet::from([
        ".env",
        ".secret",
        "id_rsa",
        "id_ed25519",
        ".htpasswd",
        ".pgpass",
        ".netrc",
    ])
});

static SENSITIVE_EXTENSIONS: Lazy<Vec<&'static str>> =
    Lazy::new(|| vec![".pem", ".key", ".p12", ".pfx", ".jks", ".secrets"]);

static SENSITIVE_PREFIXES: Lazy<Vec<&'static str>> = Lazy::new(|| vec![".env.", "credentials."]);

static PROTECTED_WRITE_ROOTS: Lazy<Vec<PathBuf>> = Lazy::new(|| {
    vec![
        PathBuf::from("/bin"),
        PathBuf::from("/etc"),
        PathBuf::from("/private/etc"),
        PathBuf::from("/sbin"),
        PathBuf::from("/System"),
        PathBuf::from("/usr"),
    ]
});

static PROTECTED_PATH_PARTS: Lazy<HashSet<&'static str>> =
    Lazy::new(|| HashSet::from([".aws", ".docker", ".gnupg", ".kube", ".ssh"]));

/// Return `true` if path matches a sensitive file pattern.
pub fn is_sensitive_file(path: &Path) -> bool {
    let name = match path.file_name().and_then(|n| n.to_str()) {
        Some(n) => n,
        None => return false,
    };

    if SENSITIVE_PATTERNS.contains(name) {
        return true;
    }

    for ext in SENSITIVE_EXTENSIONS.iter() {
        if name.ends_with(ext) {
            return true;
        }
    }

    for prefix in SENSITIVE_PREFIXES.iter() {
        if name.starts_with(prefix) {
            return true;
        }
    }

    false
}

/// Return `true` when a path includes explicit parent traversal.
pub fn has_path_traversal(path: &Path) -> bool {
    path.components()
        .any(|component| matches!(component, Component::ParentDir))
}

/// Return `true` when the input or resolved target is sensitive.
pub fn is_sensitive_path(path: &Path) -> bool {
    if is_sensitive_file(path) {
        return true;
    }

    match path.canonicalize() {
        Ok(resolved) => is_sensitive_file(&resolved),
        Err(_) => false,
    }
}

/// Return `true` for locations Rust tools should never write or patch.
pub fn is_protected_path(path: &Path) -> bool {
    let resolved = match path.canonicalize() {
        Ok(resolved) => resolved,
        Err(_) => canonicalize_best_effort(path),
    };

    if resolved.components().any(|component| {
        component
            .as_os_str()
            .to_str()
            .map(|part| PROTECTED_PATH_PARTS.contains(part))
            .unwrap_or(false)
    }) {
        return true;
    }

    PROTECTED_WRITE_ROOTS
        .iter()
        .any(|root| resolved == *root || resolved.starts_with(root))
}

fn canonicalize_best_effort(path: &Path) -> PathBuf {
    let expanded = expand_home(path);
    if expanded.exists() {
        return expanded.canonicalize().unwrap_or(expanded);
    }

    if let Some(parent) = expanded.parent() {
        if let Ok(parent) = parent.canonicalize() {
            if let Some(name) = expanded.file_name() {
                return parent.join(name);
            }
            return parent;
        }
    }

    if expanded.is_absolute() {
        expanded
    } else {
        std::env::current_dir()
            .map(|cwd| cwd.join(expanded))
            .unwrap_or_else(|_| path.to_path_buf())
    }
}

fn expand_home(path: &Path) -> PathBuf {
    let path_str = match path.to_str() {
        Some(path_str) => path_str,
        None => return path.to_path_buf(),
    };

    if path_str == "~" {
        return home_dir().unwrap_or_else(|| path.to_path_buf());
    }

    if let Some(rest) = path_str.strip_prefix("~/") {
        if let Some(home) = home_dir() {
            return home.join(rest);
        }
    }

    path.to_path_buf()
}

fn home_dir() -> Option<PathBuf> {
    std::env::var_os("HOME").map(PathBuf::from)
}

/// Return only non-sensitive paths.
pub fn filter_sensitive_paths<'a>(paths: &'a [&'a Path]) -> Vec<&'a Path> {
    paths
        .iter()
        .filter(|p| !is_sensitive_file(p))
        .copied()
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sensitive_files() {
        assert!(is_sensitive_file(Path::new(".env")));
        assert!(is_sensitive_file(Path::new(".env.local")));
        assert!(is_sensitive_file(Path::new("server.key")));
        assert!(is_sensitive_file(Path::new("cert.pem")));
        assert!(is_sensitive_file(Path::new("id_rsa")));
        assert!(is_sensitive_file(Path::new("credentials.json")));
    }

    #[test]
    fn test_safe_files() {
        assert!(!is_sensitive_file(Path::new("main.py")));
        assert!(!is_sensitive_file(Path::new("README.md")));
        assert!(!is_sensitive_file(Path::new("config.toml")));
    }

    #[test]
    fn test_path_traversal() {
        assert!(has_path_traversal(Path::new("../secret.txt")));
        assert!(has_path_traversal(Path::new("safe/../../secret.txt")));
        assert!(!has_path_traversal(Path::new("safe/file.txt")));
    }

    #[test]
    fn test_protected_paths() {
        assert!(is_protected_path(Path::new("/etc/hosts")));
        assert!(is_protected_path(Path::new("/tmp/.ssh/config")));
        assert!(!is_protected_path(Path::new("/tmp/openjarvis-safe.txt")));
    }
}

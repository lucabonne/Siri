"""Siri Knowledge Vault — local-first second brain layer.

This package provides:
- ``KnowledgeVaultService`` — the main service class
- Note types, backlinks, tags, daily notes, and Obsidian-compatible export

The vault is backed by a **separate** SQLite database
(``~/.openjarvis/knowledge_vault.db``) and never modifies the existing
``siri_memory.db``.
"""

from openjarvis.knowledge_vault.service import KnowledgeVaultService

__all__ = ["KnowledgeVaultService"]

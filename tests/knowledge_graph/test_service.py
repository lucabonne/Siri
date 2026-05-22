"""Tests for Knowledge Graph Phase 1 behavior."""

from __future__ import annotations

import pytest

from openjarvis.knowledge_graph.service import KnowledgeGraphService
from openjarvis.knowledge_vault.service import KnowledgeVaultService
from openjarvis.memory.service import MemoryService


@pytest.fixture()
def graph():
    svc = KnowledgeGraphService(db_path=":memory:")
    yield svc
    svc.close()


def test_node_lifecycle(graph):
    node = graph.create_node(
        node_type="concept",
        title="Local first memory",
        text="The graph augments memory.",
        pinned_root=True,
    )

    assert node["id"]
    assert node["pinned_root"] is True

    updated = graph.update_node(node["id"], title="Local graph root")
    assert updated["title"] == "Local graph root"
    assert graph.root_nodes()[0]["id"] == node["id"]

    assert graph.delete_node(node["id"]) is True
    with pytest.raises(KeyError):
        graph.get_node(node["id"])


def test_edge_creation(graph):
    source = graph.create_node(node_type="note", title="A")
    target = graph.create_node(node_type="note", title="B")

    edge = graph.create_edge(
        source_id=source["id"],
        target_id=target["id"],
        relationship="references",
        weight=0.8,
    )

    assert edge["relationship"] == "references"
    assert edge["weight"] == 0.8
    assert graph.list_edges(node_id=source["id"])[0]["id"] == edge["id"]


def test_graph_traversal(graph):
    a = graph.create_node(node_type="note", title="A")
    b = graph.create_node(node_type="memory", title="B")
    c = graph.create_node(node_type="source", title="C")
    graph.create_edge(source_id=a["id"], target_id=b["id"], relationship="related_to")
    graph.create_edge(source_id=b["id"], target_id=c["id"], relationship="sourced_from")

    one_hop = graph.traverse(a["id"], max_depth=1)
    assert {n["title"] for n in one_hop["nodes"]} == {"A", "B"}

    two_hop = graph.traverse(a["id"], max_depth=2)
    assert {n["title"] for n in two_hop["nodes"]} == {"A", "B", "C"}
    assert len(two_hop["edges"]) == 2


def test_timeline_behavior(graph):
    node = graph.create_node(node_type="project", title="OpenJarvis")
    event = graph.add_timeline_event(
        node_id=node["id"],
        project_id="openjarvis",
        event_type="milestone",
        title="Knowledge graph added",
        summary="Connected notes and memory.",
        occurred_at="2026-05-22T10:00:00Z",
    )

    assert event["node_id"] == node["id"]
    timeline = graph.list_timeline(project_id="openjarvis")
    assert timeline[0]["title"] == "Knowledge graph added"


def test_semantic_neighborhood_search(graph):
    root = graph.create_node(
        node_type="note",
        title="Project architecture",
        text="Decisions about local graph memory.",
        pinned_root=True,
    )
    nearby = graph.create_node(
        node_type="decision",
        title="No external DB",
        text="Use SQLite only for the graph.",
    )
    graph.create_edge(
        source_id=root["id"],
        target_id=nearby["id"],
        relationship="decided",
    )

    results = graph.neighborhood_search(
        "SQLite graph decision",
        start_node_id=root["id"],
    )

    titles = [item["node"]["title"] for item in results]
    assert "No external DB" in titles
    assert "Project architecture" in titles


def test_note_and_memory_relationship_integrations():
    vault = KnowledgeVaultService(db_path=":memory:")
    memory = MemoryService(db_path=":memory:", enable_semantic=False)
    graph = KnowledgeGraphService(
        db_path=":memory:",
        vault_service=vault,
        memory_service=memory,
    )
    try:
        note_a = vault.create_note("Architecture", content="Graph roots")
        note_b = vault.create_note("Memory", content="Pinned facts")
        mem = memory.create_memory("Remember local-only graph behavior")

        note_edge = graph.link_notes(note_a["id"], note_b["id"])
        memory_edge = graph.link_memory_to_note(mem["id"], note_a["id"])

        assert note_edge["relationship"] == "references"
        assert memory_edge["relationship"] == "related_to"
        assert len(graph.list_nodes(node_type="note")) == 2
        assert len(graph.list_nodes(node_type="memory")) == 1
    finally:
        graph.close()
        vault.close()
        memory.close()


def test_project_decision_tracking(graph):
    record = graph.record_project_decision(
        project_id="openjarvis",
        title="Use local graph",
        decision="Store graph in SQLite.",
        rationale="No cloud graph or external DB.",
    )

    assert record["project_id"] == "openjarvis"
    assert (
        graph.list_project_decisions(project_id="openjarvis")[0]["id"]
        == record["id"]
    )
    assert graph.list_timeline(project_id="openjarvis")[0]["event_type"] == "decision"

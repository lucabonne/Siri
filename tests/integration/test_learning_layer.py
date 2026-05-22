from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from openjarvis.learning_layer.service import LearningService


@pytest.fixture
def temp_learning_service():
    with TemporaryDirectory() as temp_dir:
        service = LearningService(state_dir=temp_dir)
        yield service, temp_dir


def test_feedback_lifecycle(temp_learning_service):
    service, temp_dir = temp_learning_service

    # Initial state should be empty
    assert service.get_learning_summary()["preferences"] == {}

    # Record feedback
    service.record_feedback(
        "research", "topic_quantum", "thumbs_up", {"topic": "quantum"}
    )

    # Preferences should reflect the feedback
    prefs = service.get_learning_summary()["preferences"]
    assert prefs["topic_quantum"] > 1.0

    # State should be persisted
    state_path = Path(temp_dir) / "learning_state.json"
    assert state_path.exists()

    # Load in new service instance to verify persistence
    service2 = LearningService(state_dir=temp_dir)
    assert (
        service2.get_learning_summary()["preferences"]["topic_quantum"]
        == prefs["topic_quantum"]
    )


def test_ranking_updates(temp_learning_service):
    service, _ = temp_learning_service

    # Set some initial feedback
    service.record_feedback(
        "workflow", "workflow_alpha", "thumbs_up", {"topic": "alpha"}
    )
    service.record_feedback(
        "workflow", "workflow_beta", "thumbs_down", {"topic": "beta"}
    )

    items = [
        {"id": "workflow_alpha", "name": "Alpha"},
        {"id": "workflow_beta", "name": "Beta"},
        {"id": "workflow_gamma", "name": "Gamma"},
    ]

    ranked = service.ranking.rank_items(
        items,
        key_fn=lambda x: f"topic_{x['id'].split('_')[1]}",
        preference_manager=service.preferences,
    )

    # alpha should be first, beta last
    assert ranked[0]["id"] == "workflow_alpha"
    assert ranked[-1]["id"] == "workflow_beta"


def test_memory_multipliers(temp_learning_service):
    service, _ = temp_learning_service

    # Boost memory 1, penalize memory 2
    service.record_feedback("memory_search", "1", "thumbs_up", {})
    service.record_feedback("memory_search", "2", "thumbs_down", {})

    memories = [
        {"id": "1", "score": 0.5, "content": "about A", "tags": ["topic_A"]},
        {"id": "2", "score": 0.5, "content": "about B", "tags": ["topic_B"]},
        {"id": "3", "score": 0.5, "content": "about C", "tags": []},
    ]

    adjusted = service.memory.apply_learning_to_memories(memories)

    scores = {m["id"]: m.get("score", 0.5) for m in adjusted}
    assert scores["1"] > 0.5  # boosted
    assert scores["2"] < 0.5  # penalized
    assert scores["3"] == 0.5  # unaffected


def test_reset_behavior(temp_learning_service):
    service, _ = temp_learning_service

    service.record_feedback("tool_execution", "shell_exec", "thumbs_up", {})
    assert len(service.get_learning_summary()["tool_scores"]) > 0

    service.reset_learning_state()
    assert len(service.get_learning_summary()["tool_scores"]) == 0


def test_export_import(temp_learning_service):
    service, _ = temp_learning_service

    service.record_feedback("tool_execution", "shell_exec", "thumbs_down", {})
    exported = service.export_state()

    # New service, import state
    with TemporaryDirectory() as temp_dir2:
        service2 = LearningService(state_dir=temp_dir2)
        service2.import_state(exported)

        assert (
            service2.get_learning_summary()["tool_scores"]
            == service.get_learning_summary()["tool_scores"]
        )

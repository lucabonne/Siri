from .models import MemoryWeights
from .profiles import get_active_profile


def get_active_memory_weights() -> MemoryWeights:
    """Get memory weights for the active profile, or system defaults if none active."""
    profile = get_active_profile()
    if profile:
        return profile.memory_weights
    return MemoryWeights()


def get_weight_for_memory_type(memory_type: str) -> float:
    """Get specific weight for a memory type based on active profile."""
    weights = get_active_memory_weights()
    # Assume memory_type corresponds to one of the weight fields or use default
    if memory_type == "user_fact":
        return weights.user_facts
    elif memory_type == "project_context":
        return weights.project_context
    elif memory_type == "coding_pattern":
        return weights.coding_patterns
    elif memory_type == "engineering_rule":
        return weights.engineering_rules
    return weights.default_weight

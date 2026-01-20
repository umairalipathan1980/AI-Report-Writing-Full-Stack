from typing import Any, Dict

from app.orchestrators.langgraph_orchestrator import create_langgraph_orchestrator
from app.orchestrators.sdk_orchestrator import create_sdk_orchestrator


def get_orchestrator(api_config: Dict[str, Any], verification_rounds: int, use_langgraph: bool):
    if use_langgraph:
        return create_langgraph_orchestrator(api_config, verification_rounds=verification_rounds)
    return create_sdk_orchestrator(api_config, verification_rounds=verification_rounds)

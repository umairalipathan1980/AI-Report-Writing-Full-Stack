import os
from typing import Any, Dict


def build_api_config(use_azure: bool, selected_model: str) -> Dict[str, Any]:
    openai_model_mapping = {
        "gpt-4.1": "gpt-4.1-2025-04-14",
        "gpt-5.1": "gpt-5-2025-08-07",
        "gpt-5.2": "gpt-5.2-2025-12-11",
    }

    if use_azure:
        return {
            "use_azure": True,
            "api_key": os.getenv("AZURE_API_KEY"),
            "azure_endpoint": "https://haagahelia-poc-gaik.openai.azure.com/",
            "azure_audio_endpoint": "https://haagahelia-poc-gaik.openai.azure.com/",
            "api_version": "2025-03-01-preview",
            "model": selected_model,
            "transcription_model": "whisper",
            "reasoning_effort": "low",
            "verbosity": "low",
            "max_completion_tokens": 4000,
        }

    return {
        "use_azure": False,
        "api_key": os.getenv("OPENAI_API_KEY"),
        "model": openai_model_mapping.get(selected_model, "gpt-4.1-2025-04-14"),
        "transcription_model": "whisper-1",
    }


def validate_api_keys(api_config: Dict[str, Any]) -> None:
    if api_config.get("use_azure"):
        if not api_config.get("api_key"):
            raise ValueError("AZURE_API_KEY not found in environment variables.")
    else:
        if not api_config.get("api_key"):
            raise ValueError("OPENAI_API_KEY not found in environment variables.")

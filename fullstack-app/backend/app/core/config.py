import os
from typing import Any, Dict, Optional


DEFAULT_WRITER_MODEL = os.getenv("WRITER_MODEL", "gpt-6-luna")
DEFAULT_REVIEWER_MODEL = os.getenv("REVIEWER_MODEL", os.getenv("REVIEW_MODEL", "gpt-6.1-sol"))
DEFAULT_REVISER_MODEL = os.getenv("REVISER_MODEL", "gpt-6-luna")


def is_reasoning_model(model: str) -> bool:
    """Reasoning models take reasoning_effort/verbosity instead of temperature."""
    return (model or "").startswith(("gpt-5", "gpt-6"))


def build_api_config(
    use_azure: bool,
    writer_model: Optional[str] = None,
    reviewer_model: Optional[str] = None,
    reviser_model: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the API config. 'model' is the writer; 'review_model' and
    'revision_model' are used by the verification and revision agents."""
    writer_model = writer_model or DEFAULT_WRITER_MODEL
    reviewer_model = reviewer_model or DEFAULT_REVIEWER_MODEL
    reviser_model = reviser_model or DEFAULT_REVISER_MODEL

    openai_model_mapping = {
        "gpt-4.1": "gpt-4.1-2025-04-14",
        "gpt-5.1": "gpt-5-2025-08-07",
        "gpt-5.2": "gpt-5.2-2025-12-11",
        "gpt-5.4": "gpt-5.4",
        "gpt-5.5": "gpt-5.5",
        "gpt-6-luna": "gpt-6-luna",
        "gpt-6.1-sol": "gpt-6.1-sol",
    }
    azure_model_mapping = {
        "gpt-5.5": "gpt-5.5-deployment",
    }

    if use_azure:
        return {
            "use_azure": True,
            "api_key": os.getenv("AZURE_API_KEY"),
            "azure_endpoint": "https://haagahelia-poc-gaik.openai.azure.com/",
            "azure_audio_endpoint": "https://haagahelia-poc-gaik.openai.azure.com/",
            "api_version": "2025-03-01-preview",
            "model": azure_model_mapping.get(writer_model, writer_model),
            "review_model": azure_model_mapping.get(reviewer_model, reviewer_model),
            "revision_model": azure_model_mapping.get(reviser_model, reviser_model),
            "transcription_model": "gpt-4o-transcribe",
            "reasoning_effort": "low",
            "verbosity": "low",
            "max_completion_tokens": 4000,
        }

    return {
        "use_azure": False,
        "api_key": os.getenv("OPENAI_API_KEY"),
        "model": openai_model_mapping.get(writer_model, "gpt-4.1-2025-04-14"),
        "review_model": openai_model_mapping.get(reviewer_model, reviewer_model),
        "revision_model": openai_model_mapping.get(reviser_model, reviser_model),
        "transcription_model": "gpt-4o-transcribe",
    }


def validate_api_keys(api_config: Dict[str, Any]) -> None:
    if api_config.get("use_azure"):
        if not api_config.get("api_key"):
            raise ValueError("AZURE_API_KEY not found in environment variables.")
    else:
        if not api_config.get("api_key"):
            raise ValueError("OPENAI_API_KEY not found in environment variables.")

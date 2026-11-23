import json
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import HTTPException, UploadFile

from app.core.config import build_api_config, validate_api_keys
from app.core.storage import OUTPUT_DIR, REPORT_STORE
from app.services.orchestrator import get_orchestrator


def create_report_from_transcript(payload: Dict[str, Any]) -> Dict[str, Any]:
    transcript = payload.get("transcript", "").strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="Transcript cannot be empty")

    api_config = build_api_config(
        payload.get("use_azure", True),
        writer_model=payload.get("writer_model") or payload.get("selected_model"),
        reviewer_model=payload.get("reviewer_model"),
        reviser_model=payload.get("reviser_model"),
    )
    try:
        validate_api_keys(api_config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    orchestrator = get_orchestrator(
        api_config,
        payload.get("verification_rounds", 5),
        payload.get("use_langgraph", True),
    )

    results = orchestrator.process_transcript(
        transcript=transcript,
        output_dir=str(OUTPUT_DIR),
        company_data=payload["company_data"],
        meeting_notes=payload.get("meeting_notes", "") or "",
        additional_instructions=payload.get("additional_instructions", "") or "",
    )

    report_id = payload["report_id"]
    REPORT_STORE[report_id] = {
        "status": results.get("status"),
        "results": results,
    }

    return REPORT_STORE[report_id]


def create_report_from_recording(
    report_id: str,
    file: UploadFile,
    company_payload: Dict[str, Any],
    meeting_notes: str,
    additional_instructions: str,
    use_azure: bool,
    writer_model: Optional[str],
    reviewer_model: Optional[str],
    reviser_model: Optional[str],
    verification_rounds: int,
    compress_audio: bool,
    use_langgraph: bool,
) -> Dict[str, Any]:
    api_config = build_api_config(use_azure, writer_model, reviewer_model, reviser_model)
    try:
        validate_api_keys(api_config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    orchestrator = get_orchestrator(api_config, verification_rounds, use_langgraph)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / file.filename
        temp_path.write_bytes(file.file.read())

        results = orchestrator.process_recording(
            file_path=str(temp_path),
            output_dir=str(OUTPUT_DIR),
            company_data=company_payload,
            meeting_notes=meeting_notes or "",
            additional_instructions=additional_instructions or "",
            compress_audio=compress_audio,
        )

    REPORT_STORE[report_id] = {
        "status": results.get("status"),
        "results": results,
    }

    return REPORT_STORE[report_id]


def parse_company_data(raw_company_data: str) -> Dict[str, Any]:
    try:
        return json.loads(raw_company_data)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="company_data must be valid JSON") from exc

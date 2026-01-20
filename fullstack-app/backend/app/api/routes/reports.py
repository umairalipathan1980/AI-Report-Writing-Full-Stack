from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from app.core.storage import REPORT_STORE
from app.core.security import require_auth
from app.formatting.formatter import format_report_as_html
from app.services.report_service import (
    create_report_from_recording,
    create_report_from_transcript,
    parse_company_data,
)


router = APIRouter(prefix="/reports", tags=["reports"])


class CompanyInfo(BaseModel):
    company_name: str
    country: str
    consultation_date: str
    experts: str
    customer_manager: str
    consultation_type: str


class TranscriptReportRequest(BaseModel):
    transcript: str
    company_data: CompanyInfo
    meeting_notes: Optional[str] = ""
    additional_instructions: Optional[str] = ""
    use_azure: bool = True
    selected_model: str = "gpt-5.1"
    verification_rounds: int = 5
    use_langgraph: bool = True


@router.post("/from-transcript")
async def report_from_transcript(request: TranscriptReportRequest, _: str = Depends(require_auth)):
    report_id = str(uuid4())
    payload = request.model_dump()
    payload["report_id"] = report_id
    store_entry = create_report_from_transcript(payload)
    return {"report_id": report_id, **store_entry}


@router.post("/from-recording")
async def report_from_recording(
    file: UploadFile = File(...),
    company_data: str = Form(...),
    meeting_notes: str = Form(""),
    additional_instructions: str = Form(""),
    use_azure: bool = Form(True),
    selected_model: str = Form("gpt-5.1"),
    verification_rounds: int = Form(5),
    compress_audio: bool = Form(True),
    use_langgraph: bool = Form(True),
    _: str = Depends(require_auth),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    company_payload = parse_company_data(company_data)
    report_id = str(uuid4())
    store_entry = create_report_from_recording(
        report_id=report_id,
        file=file,
        company_payload=company_payload,
        meeting_notes=meeting_notes,
        additional_instructions=additional_instructions,
        use_azure=use_azure,
        selected_model=selected_model,
        verification_rounds=verification_rounds,
        compress_audio=compress_audio,
        use_langgraph=use_langgraph,
    )
    return {"report_id": report_id, **store_entry}


@router.get("/{report_id}")
async def get_report(report_id: str, _: str = Depends(require_auth)):
    report = REPORT_STORE.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/{report_id}/download")
async def download_report(report_id: str):
    report = REPORT_STORE.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    doc_path = report.get("results", {}).get("final_report_path")
    if not doc_path:
        raise HTTPException(status_code=404, detail="Report file not found")

    return FileResponse(doc_path)


@router.get("/{report_id}/html")
async def report_html(report_id: str):
    report = REPORT_STORE.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    report_content = report.get("results", {}).get("final_report_content")
    company_data = report.get("results", {}).get("company_data")
    if not report_content or not company_data:
        raise HTTPException(status_code=404, detail="Report content not found")

    html_report = format_report_as_html(report_content, company_data)
    return HTMLResponse(content=html_report)

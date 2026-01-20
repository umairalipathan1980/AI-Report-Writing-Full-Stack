import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core import storage
from app.services import report_service


class StubOrchestrator:
    def _build_results(self, output_dir, company_data):
        doc_path = Path(output_dir) / "test_report.docx"
        doc_path.write_bytes(b"docx-content")
        return {
            "status": "success",
            "company_data": company_data,
            "final_report_content": "**AI Maturity Level:** n/a",
            "final_report_path": str(doc_path),
        }

    def process_transcript(self, transcript, output_dir, company_data, **kwargs):
        return self._build_results(output_dir, company_data)

    def process_recording(self, file_path, output_dir, company_data, **kwargs):
        return self._build_results(output_dir, company_data)


@pytest.fixture(autouse=True)
def reset_store(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    storage.REPORT_STORE.clear()
    storage.OUTPUT_DIR = tmp_path
    yield


@pytest.fixture()
def client(monkeypatch):
    def stub_get_orchestrator(api_config, verification_rounds, use_langgraph):
        return StubOrchestrator()

    monkeypatch.setattr(report_service, "get_orchestrator", stub_get_orchestrator)
    return TestClient(app)


def test_health_endpoints(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

    response = client.get("/test")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_create_report_from_transcript(client):
    payload = {
        "transcript": "Sample transcript text",
        "company_data": {
            "company_name": "Acme",
            "country": "Finland",
            "consultation_date": "01-01-2025",
            "experts": "Expert A",
            "customer_manager": "Manager B",
            "consultation_type": "Regular",
        },
        "use_azure": False,
        "selected_model": "gpt-4.1",
        "verification_rounds": 2,
        "use_langgraph": False,
    }

    response = client.post("/reports/from-transcript", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert "report_id" in body

    report_id = body["report_id"]
    stored = client.get(f"/reports/{report_id}")
    assert stored.status_code == 200
    assert stored.json()["status"] == "success"

    download = client.get(f"/reports/{report_id}/download")
    assert download.status_code == 200
    assert download.content == b"docx-content"


def test_create_report_from_recording(client, tmp_path):
    company_data = {
        "company_name": "Acme",
        "country": "Finland",
        "consultation_date": "01-01-2025",
        "experts": "Expert A",
        "customer_manager": "Manager B",
        "consultation_type": "Regular",
    }

    files = {
        "file": ("meeting.mp3", b"audio-bytes", "audio/mpeg"),
    }
    data = {
        "company_data": json.dumps(company_data),
        "use_azure": "false",
        "selected_model": "gpt-4.1",
        "verification_rounds": "2",
        "compress_audio": "true",
        "use_langgraph": "false",
    }

    response = client.post("/reports/from-recording", files=files, data=data)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

"""Mobile tachograph endpoint tests (blueprint §6.7, Phase 4A) — real DB.

Covers: multipart import (202 {job_id}) -> eager Celery job -> success
compliance result (REAL _process_driver_card logic, weekly limit 3360, verbatim
violation strings), dispatcher allowed / driver 403, invalid file type / driver
404, and the honest binary-missing error path.
"""
from __future__ import annotations

import json
import subprocess

import pytest

from tests.mobile.conftest import TACHO_CARD_FIXTURE, TACHO_FIXTURE_VIOLATIONS, TACHO_FIXTURE_WEEKLY_MINUTES

BASE = "/api/v1/mobile/tacho"


def _monkeypatch_parser(monkeypatch, fixture: dict) -> None:
    """Replace the parser binary path + execution with the fixture JSON so the
    REAL ``_process_driver_card`` logic runs against it."""
    from services.tacho_service import TachoService

    def _fake_resolve(self):
        return "/fake/tachograph.exe"

    def _fake_run(self, file_bytes):
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(fixture).encode(),
        )

    monkeypatch.setattr(TachoService, "_resolve_parser_path", _fake_resolve)
    monkeypatch.setattr(TachoService, "_run_parser", _fake_run)


def _force_missing_parser(monkeypatch) -> None:
    """Force the parser-missing branch of ``import_ddd_file`` (deterministic
    regardless of whether tools/tachograph/tachograph.exe exists locally)."""
    from services.tacho_service import TachoService

    monkeypatch.setattr(TachoService, "_resolve_parser_path", lambda self: None)


class TestImportTacho:
    def test_import_success_compliance_result(
        self, mobile_app, real_db, records_seed, dispatcher_client, monkeypatch,
    ):
        _monkeypatch_parser(monkeypatch, TACHO_CARD_FIXTURE)
        driver_id = records_seed["driver_Ion Popescu"]

        resp = dispatcher_client.post(
            f"{BASE}/import",
            data={"driver_id": str(driver_id)},
            files={"file": ("card.ddd", b"fake-ddd-bytes", "application/octet-stream")},
        )
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]

        st = dispatcher_client.get(f"{BASE}/import/{job_id}/status")
        assert st.status_code == 200
        body = st.json()
        assert body["status"] == "success"
        assert body["error"] is None

        result = body["result"]
        # REAL EU constant from services/tacho_service (Regulation 561/2006).
        assert result["weekly_limit_minutes"] == 3360
        assert result["weekly_driving_minutes"] == TACHO_FIXTURE_WEEKLY_MINUTES

        assert len(result["days"]) == 2
        assert result["days"][0] == {
            "date": "2026-07-01",
            "driving_minutes": 360,
            "working_minutes": 120,
            "rest_minutes": 780,
            "availability_minutes": 180,
        }
        assert result["days"][1]["driving_minutes"] == 600

        # VERBATIM violation strings produced by the REAL _process_driver_card.
        assert result["violations"] == TACHO_FIXTURE_VIOLATIONS

        # Activity rows really persisted by the REAL service pipeline.
        rows = dict(real_db.execute(
            "SELECT COUNT(*) AS cnt FROM tacho_driver_activity", (),
        ).fetchone())
        assert rows["cnt"] == 2
        imp = dict(real_db.execute(
            "SELECT file_type, parse_status FROM tacho_imports ORDER BY id DESC LIMIT 1",
        ).fetchone())
        assert imp["file_type"] == "driver_card"
        assert imp["parse_status"] == "ok"

    def test_weekly_limit_violation_verbatim(
        self, mobile_app, real_db, records_seed, dispatcher_client, monkeypatch,
    ):
        # 7 days x 500 min = 3500 > 3360 -> weekly violation string verbatim.
        weekly_fixture = {
            "type": "CARD",
            "driverCard": {
                "cardHolderName": {"holderSurname": "VOINESCU", "holderFirstNames": "ADRIAN"},
                "cardNumber": "RO-TACHO-WEEKLY-0002",
                "activityDailyRecords": [
                    {
                        "activityRecordDate": f"2026-06-{day:02d}",
                        "activityChangeInfo": [
                            {"activityType": 0, "duration": 500},
                            {"activityType": 3, "duration": 660},
                        ],
                    }
                    for day in range(1, 8)
                ],
            },
        }
        _monkeypatch_parser(monkeypatch, weekly_fixture)
        driver_id = records_seed["driver_Ion Popescu"]

        resp = dispatcher_client.post(
            f"{BASE}/import",
            data={"driver_id": str(driver_id)},
            files={"file": ("week.ddd", b"fake", "application/octet-stream")},
        )
        job_id = resp.json()["job_id"]
        result = dispatcher_client.get(f"{BASE}/import/{job_id}/status").json()["result"]
        assert result["weekly_driving_minutes"] == 3500
        assert "Weekly driving 58h20m exceeds 56h limit" in result["violations"]

    def test_import_invalid_file_type_422(self, mobile_app, real_db, records_seed, dispatcher_client):
        driver_id = records_seed["driver_Ion Popescu"]
        resp = dispatcher_client.post(
            f"{BASE}/import",
            data={"driver_id": str(driver_id)},
            files={"file": ("invoice.pdf", b"%PDF-fake", "application/pdf")},
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error_code"] == "invalid_file_type"

    def test_import_driver_not_found_404(self, mobile_app, real_db, dispatcher_client):
        resp = dispatcher_client.post(
            f"{BASE}/import",
            data={"driver_id": "999999"},
            files={"file": ("card.ddd", b"fake", "application/octet-stream")},
        )
        assert resp.status_code == 404
        assert resp.json()["detail"]["error_code"] == "driver_not_found"

    def test_import_driver_403(self, mobile_app, real_db, records_seed, driver_client):
        driver_id = records_seed["driver_Ion Popescu"]
        resp = driver_client.post(
            f"{BASE}/import",
            data={"driver_id": str(driver_id)},
            files={"file": ("card.ddd", b"fake", "application/octet-stream")},
        )
        assert resp.status_code == 403

    def test_status_driver_403(self, mobile_app, real_db, records_seed, driver_client):
        assert driver_client.get(f"{BASE}/import/1/status").status_code == 403


class TestBinaryMissingErrorPath:
    def test_parser_binary_missing_honest_error(
        self, mobile_app, real_db, records_seed, dispatcher_client, monkeypatch,
    ):
        """The parser binary is not installed -> job ends in a clear error.

        ``_resolve_parser_path`` is forced to return None so the REAL
        ``import_ddd_file`` "No tachograph parser found" branch runs; the job is
        marked error with the honest message and the status endpoint surfaces it.
        """
        _force_missing_parser(monkeypatch)
        driver_id = records_seed["driver_Ion Popescu"]

        resp = dispatcher_client.post(
            f"{BASE}/import",
            data={"driver_id": str(driver_id)},
            files={"file": ("card.ddd", b"fake", "application/octet-stream")},
        )
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]

        st = dispatcher_client.get(f"{BASE}/import/{job_id}/status")
        assert st.status_code == 200
        body = st.json()
        assert body["status"] == "error"
        assert body["result"] is None
        assert body["error"]
        assert "tachograph" in body["error"].lower() or "parser" in body["error"].lower()

    def test_status_unknown_job_404(self, mobile_app, real_db, dispatcher_client):
        assert dispatcher_client.get(f"{BASE}/import/999999/status").status_code == 404

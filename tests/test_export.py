from __future__ import annotations

from services.export import create_publication_export, export_all_tables


def test_export_creates_expected_csv_files(experiment_service, temp_db, tmp_path) -> None:
    code = temp_db.create_access_codes(1)[0]
    experiment_service.enter_code(code)
    exported = export_all_tables(temp_db, tmp_path / "exports")
    assert set(exported.keys()) == {"access_codes", "sessions", "messages", "survey_responses"}
    access_codes_content = exported["access_codes"].read_text(encoding="utf-8")
    assert "code" in access_codes_content
    assert "status" in access_codes_content


def test_publication_export_creates_zip_and_report(experiment_service, temp_db, tmp_path) -> None:
    code = temp_db.create_access_codes(1)[0]
    experiment_service.enter_code(code)
    experiment_service.record_consent(code)
    experiment_service.submit_user_message(code, "Hello")
    experiment_service.submit_user_message(code, "Second turn")
    experiment_service.submit_survey(
        code,
        {
            "q1": {"value": "2", "label": "High"},
            "q2": {"value": "Comment", "label": "Comment"},
        },
    )
    exported = create_publication_export(temp_db, tmp_path / "exports")
    assert exported["publication_export.zip"].exists()
    assert exported["study_report.html"].exists()
    report_html = exported["study_report.html"].read_text(encoding="utf-8")
    assert "Study Report" in report_html

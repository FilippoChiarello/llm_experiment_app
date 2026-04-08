from __future__ import annotations

import io
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict

import pandas as pd

from services.db import Database
from services.settings import EXPORTS_DIR


def export_all_tables(database: Database, export_dir: Path = EXPORTS_DIR) -> Dict[str, Path]:
    export_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_dir = export_dir / f"export_{stamp}"
    target_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for table_name in ["access_codes", "sessions", "messages", "survey_responses"]:
        path = target_dir / f"{table_name}.csv"
        database.export_table_to_csv(table_name, path)
        files[table_name] = path
    return files


def create_publication_export(database: Database, export_dir: Path = EXPORTS_DIR) -> Dict[str, Path]:
    raw_files = export_all_tables(database, export_dir)
    target_dir = next(iter(raw_files.values())).parent

    metrics = database.get_session_metrics()
    condition_df = pd.DataFrame(database.get_condition_analytics())
    daily_df = pd.DataFrame(database.get_daily_session_counts())
    turns_df = pd.DataFrame(database.get_turn_distribution())
    likert_df = pd.DataFrame(database.get_likert_summaries())
    open_text_df = pd.DataFrame(database.get_open_text_responses())

    executive_summary_df = pd.DataFrame(
        [
            {
                "metric": "total_sessions",
                "value": int(metrics["total_sessions"]),
            },
            {
                "metric": "completed_sessions",
                "value": int(metrics["completed_sessions"]),
            },
            {
                "metric": "completion_rate_percent",
                "value": round(
                    (metrics["completed_sessions"] / metrics["total_sessions"] * 100)
                    if metrics["total_sessions"]
                    else 0,
                    2,
                ),
            },
            {
                "metric": "average_turns_used",
                "value": round(metrics["average_turns_used"], 2),
            },
            {
                "metric": "average_latency_ms",
                "value": round(metrics["average_latency_ms"], 2),
            },
        ]
    )

    summary_files = {
        "executive_summary.csv": executive_summary_df,
        "condition_summary.csv": condition_df,
        "daily_activity.csv": daily_df,
        "turn_distribution.csv": turns_df,
        "likert_summary.csv": likert_df,
        "open_text_responses.csv": open_text_df,
    }
    generated_files: Dict[str, Path] = dict(raw_files)
    for file_name, dataframe in summary_files.items():
        path = target_dir / file_name
        dataframe.to_csv(path, index=False)
        generated_files[file_name] = path

    report_path = target_dir / "study_report.html"
    report_path.write_text(
        _build_html_report(
            executive_summary_df=executive_summary_df,
            condition_df=condition_df,
            daily_df=daily_df,
            turns_df=turns_df,
            likert_df=likert_df,
            open_text_df=open_text_df,
        ),
        encoding="utf-8",
    )
    generated_files["study_report.html"] = report_path

    zip_path = target_dir / "publication_export.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in generated_files.values():
            archive.write(path, arcname=path.name)
    generated_files["publication_export.zip"] = zip_path
    return generated_files


def _styled_table(dataframe: pd.DataFrame) -> str:
    if dataframe.empty:
        return "<p>No data available.</p>"
    return dataframe.to_html(index=False, classes="report-table", border=0)


def _build_html_report(
    *,
    executive_summary_df: pd.DataFrame,
    condition_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    turns_df: pd.DataFrame,
    likert_df: pd.DataFrame,
    open_text_df: pd.DataFrame,
) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    preview_comments = open_text_df.head(10) if not open_text_df.empty else open_text_df
    return f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Study Report</title>
  <style>
    body {{
      font-family: "Helvetica Neue", Arial, sans-serif;
      margin: 0;
      padding: 0;
      background: #f4f7fa;
      color: #213547;
    }}
    .page {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 32px;
    }}
    .hero {{
      background: linear-gradient(135deg, #e8f3ff, #fff2e6);
      border-radius: 24px;
      padding: 28px;
      margin-bottom: 24px;
      border: 1px solid #d8e4ef;
    }}
    .section {{
      background: white;
      border-radius: 20px;
      padding: 24px;
      margin-bottom: 20px;
      border: 1px solid #e3eaf0;
      box-shadow: 0 10px 25px rgba(33,53,71,0.05);
    }}
    .report-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    .report-table th {{
      background: #edf4fb;
      text-align: left;
      padding: 10px 12px;
      border-bottom: 1px solid #d6e2ec;
    }}
    .report-table td {{
      padding: 10px 12px;
      border-bottom: 1px solid #edf2f7;
      vertical-align: top;
    }}
    h1, h2 {{
      margin-top: 0;
    }}
    .muted {{
      color: #5c7083;
    }}
  </style>
</head>
<body>
  <div class="page">
    <div class="hero">
      <h1>Study Report</h1>
      <p class="muted">Generated at {generated_at}. This export combines raw data with publication-ready summary tables.</p>
    </div>
    <div class="section">
      <h2>Executive Summary</h2>
      {_styled_table(executive_summary_df)}
    </div>
    <div class="section">
      <h2>Condition Summary</h2>
      {_styled_table(condition_df)}
    </div>
    <div class="section">
      <h2>Daily Activity</h2>
      {_styled_table(daily_df)}
    </div>
    <div class="section">
      <h2>Turn Distribution</h2>
      {_styled_table(turns_df)}
    </div>
    <div class="section">
      <h2>Likert Summary</h2>
      {_styled_table(likert_df)}
    </div>
    <div class="section">
      <h2>Open-Text Response Preview</h2>
      {_styled_table(preview_comments)}
    </div>
  </div>
</body>
</html>
"""

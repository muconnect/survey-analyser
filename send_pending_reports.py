import base64
import os
from typing import List
from pathlib import Path

import pandas as pd
import requests

from app import generate_user_pdf_playwright, install_playwright, prepare_results


def load_local_env(env_path: str = ".env") -> None:
    path = Path(env_path)
    if not path.exists():
        return

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


load_local_env()


CONFIG = {
    "zepto_api_key": os.environ.get("ZEPTO_API_KEY", ""),
    "from_email": os.environ.get("FROM_EMAIL", "events@edxso.com"),
    "from_name": os.environ.get("FROM_NAME", "Team EDXSO"),
    "subject": os.environ.get(
        "EMAIL_SUBJECT",
        "Your School Evolution Score Report | Chhattisgarh Leadership Summit",
    ),
}


COL_EMAIL = 2
COL_NAME = 29
COL_STATUS = 31

EMAIL_TEMPLATE = """\
<!DOCTYPE html>
<html>
  <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <p><strong>Dear {name} Ji,</strong></p>

    <p>
      Thank you for participating in today's event and for completing the
      School Evolution Questionnaire Survey.
    </p>

    <p>
      We are pleased to share your personalized <strong>School Evolution Score Report</strong>
      in this email. The report provides key insights into your school's present
      growth stage, leadership readiness, and future development opportunities.
    </p>

    <p>
      We hope these findings will support your strategic planning and help
      strengthen your institution's journey towards excellence.
    </p>

    <p>
      Please find your report attached for your kind review.
    </p>

    <p>
      Thank you once again for your valuable participation.
    </p>

    <br>

    <p>
      Warm regards,<br>
      <strong>Team EDXSO</strong>
    </p>
  </body>
</html>
"""


def require_config(name: str) -> str:
    value = CONFIG[name]
    if not value:
        raise ValueError(
            f"Missing configuration for '{name}'. Set the matching environment variable first."
        )
    return value


def render_email_html(name: str) -> str:
    participant_name = (name or "Participant").strip()
    return EMAIL_TEMPLATE.format(name=participant_name)


def build_pdf_filename(display_name: str) -> str:
    safe_name = "_".join((display_name or "Participant").split())
    return f"RCube_Report_{safe_name}.pdf"


def find_column_name(df: pd.DataFrame, candidates: List[str]) -> str | None:
    normalized = {str(col).strip().lower(): col for col in df.columns}
    for candidate in candidates:
        match = normalized.get(candidate.strip().lower())
        if match is not None:
            return match
    return None


def get_series_value(row: pd.Series, index: int, column_name: str | None, default: str = "") -> str:
    if column_name is not None and column_name in row.index:
        value = row[column_name]
    elif index < len(row):
        value = row.iloc[index]
    else:
        value = default

    if pd.isna(value):
        return default
    return str(value).strip()


def send_email_with_attachment(email: str, name: str, file_name: str, file_bytes: bytes):
    payload = {
        "from": {"address": CONFIG["from_email"], "name": CONFIG["from_name"]},
        "to": [{"email_address": {"address": email, "name": name or ""}}],
        "subject": CONFIG["subject"],
        "htmlbody": render_email_html(name),
        "attachments": [
            {
                "name": file_name,
                "mime_type": "application/pdf",
                "content": base64.b64encode(file_bytes).decode("utf-8"),
            }
        ],
    }

    return requests.post(
        "https://api.zeptomail.in/v1.1/email",
        headers={
            "Authorization": require_config("zepto_api_key"),
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )


def send_pending_reports_from_dataframe(raw_df: pd.DataFrame) -> List[dict]:
    run_log = []

    if raw_df.empty:
        return [{"status": "info", "message": "No survey rows found in the uploaded CSV."}]

    results = prepare_results(raw_df)
    install_playwright()
    email_col = find_column_name(raw_df, ["email", "email address", "email_address", "mail"])
    name_col = find_column_name(raw_df, ["name", "full name", "full_name", "participant name"])
    status_col = find_column_name(raw_df, ["status", "mail status", "email status"])

    for row_idx, report_row in results.iterrows():
        source_row = raw_df.iloc[row_idx]
        email = get_series_value(source_row, COL_EMAIL, email_col)
        name = get_series_value(source_row, COL_NAME, name_col, report_row["Display_Name"])
        status = get_series_value(source_row, COL_STATUS, status_col, "Pending")

        if not email or status != "Pending":
            continue

        try:
            pdf_bytes = generate_user_pdf_playwright(report_row)
            response = send_email_with_attachment(
                email=email,
                name=name,
                file_name=build_pdf_filename(report_row["Display_Name"]),
                file_bytes=pdf_bytes,
            )

            if response.status_code in (200, 201):
                run_log.append(
                    {"status": "success", "message": f"Sent to {email}", "row_index": row_idx}
                )
            else:
                run_log.append(
                    {
                        "status": "error",
                        "message": (
                            f"ZeptoMail error for {email} ({response.status_code}): "
                            f"{response.text[:500]}"
                        ),
                        "row_index": row_idx,
                    }
                )
        except Exception as exc:
            run_log.append(
                {
                    "status": "error",
                    "message": f"Row {row_idx + 2} error: {exc}",
                    "row_index": row_idx,
                }
            )

    if not run_log:
        run_log.append({"status": "info", "message": "No rows with Pending status were found."})

    return run_log

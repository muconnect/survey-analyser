import logging
import os
import re
import socket
from typing import List
from pathlib import Path
from typing import Callable
import smtplib
from email.message import EmailMessage

import pandas as pd


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

LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
EMAIL_LOG_PATH = LOG_DIR / "email_send.log"

logger = logging.getLogger("survey_analyser.email")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(EMAIL_LOG_PATH)
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(file_handler)


CONFIG = {
    "zepto_api_key": os.environ.get("ZEPTO_API_KEY", ""),
    "smtp_host": os.environ.get("SMTP_HOST", ""),
    "smtp_port": os.environ.get("SMTP_PORT", ""),
    "smtp_username": os.environ.get("SMTP_USERNAME", ""),
    "smtp_password": os.environ.get("SMTP_PASSWORD", ""),
    "from_email": os.environ.get("FROM_EMAIL", "events@edxso.com"),
    "from_name": os.environ.get("FROM_NAME", "Team EDXSO"),
    "subject": os.environ.get(
        "EMAIL_SUBJECT",
        "Your School Evolution Score Report | Chhattisgarh Leadership Summit",
    ),
    "certificate_subject": os.environ.get(
        "CERTIFICATE_EMAIL_SUBJECT",
        "Thank You for Attending the CBA Session | Participation Certificate & Exclusive Workshop Invitation",
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

    <p>
      Warm regards,<br>
      <strong>Team EDXSO</strong>
    </p>
  </body>
</html>
"""

CERTIFICATE_EMAIL_TEMPLATE = """\
<!DOCTYPE html>
<html>
  <body style="font-family: Arial, sans-serif; line-height: 1.7; color: #222;">
    <p>Respected Educator,<br>Namaste!</p>

    <p>
      Thank you for being a part of our interactive session on
      <strong>Competency-Based Assessment (CBA)</strong>{date_fragment}.
      We truly appreciate your enthusiastic participation and engagement throughout the session.
    </p>

    <p>
      We hope the session provided valuable insights into competency-based teaching,
      learning, and assessment practices aligned with NEP recommendations.
    </p>

    <p><strong>Please find attached your Participation Certificate for the session.</strong></p>

    <p>
      We look forward to your continued participation in our teacher capacity-building initiatives.
    </p>

    <p>
      Warm regards,<br>
      Nidhi Jaiswal<br>
      Manager Education Solution<br>
      EDXSO<br>
      6299443670
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


def render_certificate_email_html(event_date: str) -> str:
    date_fragment = f" conducted on {event_date}" if (event_date or "").strip() else ""
    return CERTIFICATE_EMAIL_TEMPLATE.format(date_fragment=date_fragment)


def slugify_filename_part(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s-]+", "_", text.strip())
    return text.strip("_")


def build_pdf_filename(display_name: str, event_name: str = "") -> str:
    safe_name = slugify_filename_part(display_name or "Participant")
    safe_event = slugify_filename_part(event_name or "")
    if safe_event:
        return f"{safe_event}_{safe_name}.pdf"
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


class SimpleSendResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text


def smtp_is_configured() -> bool:
    return all(
        [
            CONFIG.get("smtp_host"),
            CONFIG.get("smtp_port"),
            CONFIG.get("smtp_username"),
            CONFIG.get("smtp_password"),
            CONFIG.get("from_email"),
        ]
    )


def send_email_with_smtp(
    email: str,
    name: str,
    file_name: str,
    file_bytes: bytes,
    subject: str,
    html_body: str,
    attachment_mime_type: str = "application/pdf",
):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{CONFIG['from_name']} <{CONFIG['from_email']}>"
    msg["To"] = f"{name} <{email}>" if name else email
    msg.set_content(
        "Please view this email in HTML format to read the full message and access the attached report."
    )
    msg.add_alternative(html_body, subtype="html")
    mime_type = (attachment_mime_type or "application/pdf").strip().lower()
    if "/" in mime_type:
        maintype, subtype = mime_type.split("/", 1)
    else:
        maintype, subtype = "application", "octet-stream"
    msg.add_attachment(file_bytes, maintype=maintype, subtype=subtype, filename=file_name)

    smtp_port = int(str(CONFIG["smtp_port"]).strip())
    ipv4_candidates = [
        item[4][0]
        for item in socket.getaddrinfo(
            CONFIG["smtp_host"],
            smtp_port,
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
        )
    ]
    smtp_connect_host = ipv4_candidates[0] if ipv4_candidates else CONFIG["smtp_host"]

    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(timeout=60) as server:
                server.connect(smtp_connect_host, smtp_port)
                server._host = CONFIG["smtp_host"]
                server.ehlo()
                server.login(CONFIG["smtp_username"], CONFIG["smtp_password"])
                server.send_message(msg)
        else:
            with smtplib.SMTP(timeout=60) as server:
                server.connect(smtp_connect_host, smtp_port)
                # Keep TLS SNI/hostname aligned with the real mail host while using an IPv4 socket.
                server._host = CONFIG["smtp_host"]
                server.ehlo()
                if smtp_port == 587:
                    server.starttls()
                    server.ehlo()
                server.login(CONFIG["smtp_username"], CONFIG["smtp_password"])
                server.send_message(msg)
    except Exception as exc:
        logger.exception(
            "SMTP send failed stage=connect/login/send host=%s port=%s to=%s name=%s file=%s",
            CONFIG.get("smtp_host", ""),
            smtp_port,
            email,
            name,
            file_name,
        )
        raise exc

    return SimpleSendResponse(200, "Sent via SMTP")


def send_email_with_attachment(
    email: str,
    name: str,
    file_name: str,
    file_bytes: bytes,
    subject: str | None = None,
    html_body: str | None = None,
    attachment_mime_type: str = "application/pdf",
):
    subject = subject or CONFIG["subject"]
    html_body = html_body or render_email_html(name)
    if not smtp_is_configured():
        logger.error(
            "SMTP not configured to=%s name=%s file=%s host=%s port=%s",
            email,
            name,
            file_name,
            CONFIG.get("smtp_host", ""),
            CONFIG.get("smtp_port", ""),
        )
        raise ValueError("SMTP is not fully configured. Set SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, and FROM_EMAIL in .env.")

    return send_email_with_smtp(
        email,
        name,
        file_name,
        file_bytes,
        subject,
        html_body,
        attachment_mime_type=attachment_mime_type,
    )


def send_certificate_email_with_attachment(
    email: str,
    name: str,
    file_name: str,
    file_bytes: bytes,
    event_date: str = "",
):
    return send_email_with_attachment(
        email=email,
        name=name,
        file_name=file_name,
        file_bytes=file_bytes,
        subject=CONFIG["certificate_subject"],
        html_body=render_certificate_email_html(event_date),
    )


def send_pending_reports_from_dataframe(
    raw_df: pd.DataFrame,
    progress_callback: Callable[[int, int, str, str], None] | None = None,
) -> List[dict]:
    from app import generate_user_pdf_playwright, install_playwright, prepare_results

    run_log = []

    if raw_df.empty:
        return [{"status": "info", "message": "No survey rows found in the uploaded CSV."}]

    results = prepare_results(raw_df)
    install_playwright()
    email_col = find_column_name(raw_df, ["email", "email address", "email_address", "mail"])
    name_col = find_column_name(raw_df, ["name", "full name", "full_name", "participant name"])
    status_col = find_column_name(raw_df, ["status", "mail status", "email status"])
    event_name_col = find_column_name(
        raw_df,
        [
            "event name",
            "event",
            "event title",
            "session name",
            "session title",
            "workshop name",
            "workshop title",
            "training name",
            "training title",
        ],
    )
    pending_targets = []

    for row_idx, report_row in results.iterrows():
        source_row = raw_df.iloc[row_idx]
        email = get_series_value(source_row, COL_EMAIL, email_col)
        status = get_series_value(source_row, COL_STATUS, status_col, "Pending")
        if email and status == "Pending":
            pending_targets.append((row_idx, report_row))

    total_targets = len(pending_targets)

    for position, (row_idx, report_row) in enumerate(pending_targets, start=1):
        source_row = raw_df.iloc[row_idx]
        email = get_series_value(source_row, COL_EMAIL, email_col)
        name = get_series_value(source_row, COL_NAME, name_col, report_row["Display_Name"])
        if progress_callback is not None:
            progress_callback(position, total_targets, report_row["Display_Name"], "sending")

        try:
            pdf_bytes = generate_user_pdf_playwright(report_row)
            event_name = get_series_value(source_row, len(source_row), event_name_col)
            response = send_email_with_attachment(
                email=email,
                name=name,
                file_name=build_pdf_filename(report_row["Display_Name"], event_name),
                file_bytes=pdf_bytes,
            )

            if response.status_code in (200, 201):
                run_log.append(
                    {"status": "success", "message": f"Sent to {email}", "row_index": row_idx}
                )
                if progress_callback is not None:
                    progress_callback(position, total_targets, report_row["Display_Name"], "sent")
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
                if progress_callback is not None:
                    progress_callback(position, total_targets, report_row["Display_Name"], "error")
        except Exception as exc:
            run_log.append(
                {
                    "status": "error",
                    "message": f"Row {row_idx + 2} error: {exc}",
                    "row_index": row_idx,
                }
            )
            if progress_callback is not None:
                progress_callback(position, total_targets, report_row["Display_Name"], "error")

    if not run_log:
        run_log.append({"status": "info", "message": "No rows with Pending status were found."})

    return run_log

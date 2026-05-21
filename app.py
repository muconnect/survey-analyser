import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import base64
import io
import sys
import asyncio
import warnings
import os
import json
import re
import html
import zipfile
from pathlib import Path
import requests

try:
    from google import genai
except Exception:
    genai = None

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

try:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
except Exception:
    FPDF = None
    XPos = None
    YPos = None

try:
    from playwright.sync_api import sync_playwright
except Exception as playwright_import_error:
    sync_playwright = None
    PLAYWRIGHT_IMPORT_ERROR = playwright_import_error
else:
    PLAYWRIGHT_IMPORT_ERROR = None

@st.cache_resource
def install_playwright():
    """Forces the Streamlit server to download the Chromium binary and dependencies on boot."""
    if sync_playwright is None:
        return False
    os.system("playwright install chromium")
    return True

# ─────────────────────────────────────────────
#  WINDOWS EVENT LOOP FIX (MUST COME FIRST)
# ─────────────────────────────────────────────
if sys.platform == "win32":
    # Mute the Python 3.14+ deprecation warnings to keep the console clean
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=DeprecationWarning)
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except AttributeError:
            pass # Failsafe just in case it gets fully removed in a future test build

import plotly.io as pio
from plotly.offline import get_plotlyjs

APP_PAGE_CONFIG = dict(
    page_title="R-Cube Strategic Intelligence",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.set_page_config(**APP_PAGE_CONFIG)


def ensure_playwright_ready():
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright is not installed in this Python environment. "
            "Install it with `pip install playwright` and then run `playwright install chromium`."
        ) from PLAYWRIGHT_IMPORT_ERROR


def load_local_env(env_path: str = ".env") -> None:
    if load_dotenv is not None:
        load_dotenv(env_path)
        return

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

GENERATED_PDF_DIR = Path("generated_pdfs")
EVENT_DATABASE_URL = os.environ.get("EVENT_DATABASE_URL", "").strip()
SUPABASE_URL = os.environ.get("VITE_SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_API_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    or os.environ.get("VITE_SUPABASE_PUBLISHABLE_KEY", "").strip()
)
 
# ─────────────────────────────────────────────
#  CUSTOM CSS
# ─────────────────────────────────────────────
CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');
 
/* Reset & Base */
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}
.stApp {
    background: #f8fafc;
    color: #0f172a;
}
 
/* Sidebar */
[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid #e2e8f0;
}
[data-testid="stSidebar"] * { color: #334155 !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { color: #0f172a !important; }
 
/* Main headings */
h1, h2, h3 { font-family: 'Playfair Display', serif !important; color: #0f172a !important; }
 
/* Hide Streamlit chrome */
#MainMenu, footer{ visibility: hidden; }
.block-container { padding-top: 2rem; padding-bottom: 2rem; }
 
/* ── KPI Cards ── */
.kpi-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    border-radius: 12px;
    padding: 1.5rem 1.75rem;
    position: relative;
    overflow: hidden;
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
}
.kpi-card.relevance::before  { background: #d97706; }
.kpi-card.reliability::before { background: #2563eb; }
.kpi-card.reputability::before { background: #7c3aed; }
.kpi-card.growth::before { background: #059669; }
.kpi-card.growth { text-align: center; }
.kpi-card.growth .kpi-label,
.kpi-card.growth .kpi-value,
.kpi-card.growth .kpi-band {
    margin-left: auto;
    margin-right: auto;
}
 
.kpi-label { font-family: 'DM Mono', monospace; font-size: 0.65rem; letter-spacing: 0.2em; text-transform: uppercase; color: #64748b; margin-bottom: 0.5rem; }
.kpi-value { font-family: 'Playfair Display', serif; font-size: 5.2rem; font-weight: 900; line-height: 1; margin-bottom: 0.3rem; }
.kpi-value.relevance  { color: #b45309; }
.kpi-value.reliability { color: #1d4ed8; }
.kpi-value.reputability { color: #6d28d9; }
.kpi-value.growth { color: #047857; }
 
.kpi-band { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.05em; padding: 2px 8px; border-radius: 4px; display: inline-block; margin-top: 0.25rem; }
.band-fragile     { background: #fef2f2; color: #dc2626; }
.band-emerging    { background: #fffbeb; color: #d97706; }
.band-developing  { background: #f0fdf4; color: #16a34a; }
.band-strong      { background: #eff6ff; color: #2563eb; }
.band-benchmark   { background: #faf5ff; color: #9333ea; }
 
/* ── Stage Bar ── */
.stage-bar-wrap { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.5rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02); height: 100%; }
.stage-profile-offset { margin-top: 44px; }
.stage-row { display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem; }
.stage-label { font-family: 'DM Mono', monospace; font-size: 0.65rem; letter-spacing: 0.15em; text-transform: uppercase; color: #475569; width: 130px; }
.stage-track { flex: 1; height: 8px; background: #f1f5f9; border-radius: 4px; }
.stage-fill { height: 100%; border-radius: 4px; }
.stage-val { font-family: 'DM Mono', monospace; font-size: 0.8rem; color: #0f172a; font-weight: 600; }
 
/* ── Status Badge ── */
.status-badge { display: inline-flex; align-items: center; gap: 0.6rem; padding: 0.7rem 1.45rem; border-radius: 10px; font-family: 'DM Mono', monospace; font-size: 0.95rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; }
.badge-benchmark  { background: #faf5ff; border: 1px solid #c084fc; color: #7e22ce; }
.badge-fragile    { background: #fef2f2; border: 1px solid #f87171; color: #b91c1c; }
.badge-efficient  { background: #f0fdf4; border: 1px solid #4ade80; color: #15803d; }
.badge-legacy     { background: #f0fdfa; border: 1px solid #2dd4bf; color: #0f766e; }
.badge-default    { background: #f8fafc; border: 1px solid #cbd5e1; color: #334155; }
.badge-desc { font-size: 1.05rem; color: #0f172a; font-weight: 700; }
.status-row { display: flex; align-items: center; flex-wrap: nowrap; gap: 0.8rem; margin-top: 1.25rem; }
 
/* ── Section headers ── */
.section-header { border-bottom: 2px solid #e2e8f0; padding-bottom: 0.5rem; margin-bottom: 1.5rem; }
.section-number { color: #94a3b8; font-family: 'DM Mono', monospace; font-weight: 600; }
.section-title { color: #0f172a; font-family: 'Playfair Display', serif; font-weight: 700; font-size: 1.5rem; margin-left: 0.5rem; }
 
/* ── Score Explanation ── */
.explain-wrap { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 1.5rem; margin-bottom: 1rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02); }
.explain-head { font-family: 'Playfair Display', serif; font-size: 1.6rem; font-weight: 900; color: #0f172a; line-height: 1.2; margin-bottom: 0.3rem; }
.explain-sub { font-family: 'DM Mono', monospace; font-size: 0.66rem; letter-spacing: 0.14em; text-transform: uppercase; color: #64748b; margin-bottom: 1.2rem; }
.explain-grid { display: grid; grid-template-columns: repeat(3, minmax(180px, 1fr)); gap: 1rem; }
.explain-card { background: #f8fafc; border: 1px solid #f1f5f9; border-radius: 10px; padding: 1rem; }
.explain-card h4 { margin: 0 0 0.6rem 0; font-family: 'DM Mono', monospace; letter-spacing: 0.08em; font-size: 0.75rem; text-transform: uppercase; font-weight: 600; }
.exp-rel h4 { color: #d97706; }
.exp-reli h4 { color: #2563eb; }
.exp-repu h4 { color: #7c3aed; }
.explain-card ul { margin: 0; padding-left: 1rem; color: #334155; font-size: 0.9rem; line-height: 1.6; }
@media (max-width: 980px) { .explain-grid { grid-template-columns: 1fr; } }

/* ── Growth Stage Focus Table ── */
.focus-wrap { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 1.5rem; margin-bottom: 1rem; overflow-x: auto; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02); }
.focus-title { font-family: 'Playfair Display', serif; font-size: 1.5rem; font-weight: 900; color: #0f172a; margin-bottom: 1rem; }
.focus-table { width: 100%; border-collapse: collapse; min-width: 860px; }
.focus-table th, .focus-table td { border: 1px solid #e2e8f0; padding: 0.75rem; vertical-align: top; color: #334155; line-height: 1.4; font-size: 0.9rem; }
.focus-table th { background: #f8fafc; font-family: 'DM Mono', monospace; font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase; color: #0f172a; }
.focus-stage { font-family: 'DM Mono', monospace; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; white-space: nowrap; background: #f1f5f9; }

/* Divider */
hr { border-color: #e2e8f0 !important; }

.stButton > button,
.stDownloadButton > button {
    background: #2563eb !important;
    color: #ffffff !important;
    border: 1px solid #2563eb !important;
}
.stButton > button p,
.stButton > button span,
.stDownloadButton > button p,
.stDownloadButton > button span,
[data-testid="stSidebar"] .stButton > button,
[data-testid="stSidebar"] .stButton > button p,
[data-testid="stSidebar"] .stButton > button span,
[data-testid="stSidebar"] .stDownloadButton > button,
[data-testid="stSidebar"] .stDownloadButton > button p,
[data-testid="stSidebar"] .stDownloadButton > button span {
    color: #ffffff !important;
}
.stButton > button:hover,
.stDownloadButton > button:hover {
    background: #1d4ed8 !important;
    color: #ffffff !important;
    border-color: #1d4ed8 !important;
}
.stButton > button:disabled,
.stDownloadButton > button:disabled {
    background: #93c5fd !important;
    color: #eff6ff !important;
    border-color: #93c5fd !important;
}
"""

# ─────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────
RESPONSE_MAP = {
    "Completely disagree": 1, "Disagree": 2,
    "Don't Know, Can't Say": 3, "don't know ,can't say": 3,
    "Don’t Know, Can’t Say": 3,  # Added to handle CSV export typography
    "Agree": 4, "Completely agree": 5, "Completely Agree": 5,
}
 
BAND_LABELS = {
    (0, 40):  ("Fragile",          "band-fragile"),
    (40, 60): ("Emerging",         "band-emerging"),
    (60, 75): ("Developing",       "band-developing"),
    (75, 90): ("Strong",           "band-strong"),
    (90, 101):("Benchmark",        "band-benchmark"),
}

PLOTLY_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="DM Sans", color="#334155", size=11),
    margin=dict(l=20, r=20, t=40, b=20),
)
 
# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def get_band(score):
    for (lo, hi), (label, css) in BAND_LABELS.items():
        if lo <= score < hi: return label, css
    return "Benchmark", "band-benchmark"

def fig_to_html(fig, w, h):
    """Converts a Plotly figure to an embeddable HTML string."""
    fig.update_layout(width=w, height=h)
    return fig.to_html(full_html=False, include_plotlyjs=False)

def fig_to_b64(fig, w, h):
    """Converts a Plotly figure to a base64 encoded PNG string."""
    img_bytes = fig.to_image(format="png", width=w, height=h, scale=2)
    return base64.b64encode(img_bytes).decode('utf-8')

def get_strategic_profile(row):
    gi = row['Growth_Index']
    rel  = row['Relevance']
    reli = row['Reliability_Adj']
    repu = row['Reputability_Adj']
 
    if gi >= 85: return "🏆 Benchmark Institution", "badge-benchmark", "Market leader and legacy institution setting the standard for peers."
    if rel > 70 and reli < 50: return "⚡ Fragile Starter", "badge-fragile", "Strong vision and relevance, but operational systems are failing to match ambition."
    if reli > 70 and rel < 50: return "⚙️ Efficient Machine", "badge-efficient", "Consistent delivery and strong systems, but at risk of becoming obsolete."
    if reli > 60 and repu > 60: return "📜 Legacy Builder", "badge-legacy", "Strong operational systems and actively building long-term market authority."
    if gi < 40: return "🛑 Fragile Foundation", "badge-fragile", "Immediate intervention required — core foundations are critically weak."
    return "🌱 Emerging", "badge-default", "Moving out of survival phase and stabilising core operations."
 
# ─────────────────────────────────────────────
#  SCORING ENGINE
# ─────────────────────────────────────────────
def calculate_metrics(df):
    df = df.copy()
    for i in [1, 2, 3, 4, 5]:
        df[f'S{i}'] = (5 - df[f'Q{i}']) * 25
    for i in range(6, 21):
        df[f'S{i}'] = (df[f'Q{i}'] - 1) * 25
 
    df['Relevance'] = df[['S1', 'S2', 'S5', 'S11', 'S13', 'S14']].mean(axis=1)
    df['Rel_Raw'] = df[['S3', 'S4', 'S6', 'S7', 'S8', 'S9', 'S10', 'S12', 'S14', 'S15']].mean(axis=1)
    df['Rep_Raw'] = df[['S16', 'S17', 'S18', 'S19', 'S20']].mean(axis=1)
 
    df['Reliability_Adj']   = df['Rel_Raw'] * (0.75 + 0.25 * df['Relevance'] / 100)
    min_floor               = df[['Relevance', 'Reliability_Adj']].min(axis=1)
    df['Reputability_Adj']  = df['Rep_Raw'] * (0.60 + 0.40 * min_floor / 100)
 
    df['Foundation']    = df[[f'Q{i}' for i in range(1, 6)]].mean(axis=1)
    df['Growth']        = df[[f'Q{i}' for i in range(6, 11)]].mean(axis=1)
    df['Acceleration']  = df[[f'Q{i}' for i in range(11, 16)]].mean(axis=1)
    df['Legacy']        = df[[f'Q{i}' for i in range(16, 21)]].mean(axis=1)
 
    df['Growth_Index'] = (0.35 * df['Relevance'] + 0.40 * df['Reliability_Adj'] + 0.25 * df['Reputability_Adj'])
    return df


def prepare_results(raw):
    raw = raw.copy()
    q_cols = raw.columns[8:28]
    raw = raw.rename(columns={q_cols[i]: f'Q{i+1}' for i in range(len(q_cols))})

    if 'name' in raw.columns:
        raw_names = raw['name'].fillna("Unknown").astype(str).tolist()
    else:
        try:
            raw_names = raw.iloc[:, 29].fillna("Unknown").astype(str).tolist()
        except IndexError:
            raw_names = [f"User {i+1}" for i in range(len(raw))]

    display_names = [name.title().strip() for name in raw_names]

    unique_ids = []
    seen = {}
    for name in display_names:
        if name in seen:
            seen[name] += 1
            unique_ids.append(f"{name} ({seen[name]})")
        else:
            seen[name] = 1
            unique_ids.append(name)

    raw.insert(0, 'UserID', unique_ids)
    raw.insert(1, 'Display_Name', display_names)

    for i in range(1, 21):
        q_key = f'Q{i}'
        if q_key not in raw.columns:
            raw[q_key] = 3
        else:
            raw[q_key] = raw[q_key].map(RESPONSE_MAP).fillna(3)

    return calculate_metrics(raw)


def make_unique_display_names(raw_names):
    def _clean_name(name, fallback_index):
        text = str(name or "").strip()
        if not text or text.lower() in {"nan", "none", "null", "unknown"}:
            return f"User {fallback_index}"
        return text.title()

    display_names = [_clean_name(name, index + 1) for index, name in enumerate(raw_names)]
    unique_ids = []
    seen = {}
    for name in display_names:
        if name in seen:
            seen[name] += 1
            unique_ids.append(f"{name} ({seen[name]})")
        else:
            seen[name] = 1
            unique_ids.append(name)
    return display_names, unique_ids


def resolve_record_display_name(record, fallback="Participant"):
    candidate_keys = ["name", "Display_Name", "display_name", "UserID", "user_id"]
    for key in candidate_keys:
        try:
            value = record.get(key) if hasattr(record, "get") else None
        except Exception:
            value = None
        text = str(value or "").strip()
        if text and text.lower() not in {"nan", "none", "null", "unknown"}:
            return text

    email_value = ""
    try:
        email_value = str((record.get("email") if hasattr(record, "get") else "") or (record.get("Email") if hasattr(record, "get") else "")).strip()
    except Exception:
        email_value = ""
    if email_value and "@" in email_value:
        return email_value.split("@", 1)[0]

    return fallback


def find_email_column(df):
    exact = find_column_name(df, ["email", "email address", "email_address", "mail"])
    if exact is not None:
        return exact
    for col in df.columns:
        normalized = str(col).strip().lower()
        if "email" in normalized or normalized.endswith("mail"):
            return col
    return None


def find_name_column(df):
    return find_column_name(df, ["name", "full name", "full_name", "participant name", "teacher name"])


def infer_single_survey_kind(raw):
    pre_matches = sum(1 for question in PRE_ASSESSMENT_KEY if get_matched_column(raw, question))
    post_matches = sum(1 for question in POST_ASSESSMENT_KEY if get_matched_column(raw, question))
    if pre_matches >= 8 and pre_matches >= post_matches:
        return "pre_assessment"
    if post_matches >= 8 and post_matches > pre_matches:
        return "post_assessment"
    return "rcube"


def prepare_assessment_results(raw, base_answer_key, current_api_key):
    raw = raw.copy()
    dynamic_answer_key = build_dynamic_answer_mapping(raw, base_answer_key, current_api_key)
    scored = generate_individual_graded_dataframe(raw, dynamic_answer_key)

    name_col = find_name_column(raw)
    email_col = find_email_column(raw)
    phone_col = find_phone_column(raw)

    raw_names = (
        raw[name_col].fillna("Unknown").astype(str).tolist()
        if name_col is not None
        else [f"User {i+1}" for i in range(len(raw))]
    )
    display_names, user_ids = make_unique_display_names(raw_names)

    scored.insert(0, "UserID", user_ids)
    scored.insert(1, "Display_Name", display_names)
    scored["Email"] = (
        raw[email_col].fillna("").astype(str).str.strip()
        if email_col is not None
        else pd.Series([""] * len(raw))
    )
    scored["Phone"] = (
        raw[phone_col].apply(normalize_phone)
        if phone_col is not None
        else pd.Series([""] * len(raw))
    )
    return scored, dynamic_answer_key


def prepare_certificate_only_results(raw):
    raw = raw.copy()
    name_col = find_name_column(raw)
    email_col = find_email_column(raw)
    phone_col = find_phone_column(raw)
    event_name_col = find_event_name_column(raw)
    date_col = find_date_column(raw)

    raw_names = []
    for index in range(len(raw)):
        name_value = raw.iloc[index][name_col] if name_col is not None else ""
        email_value = raw.iloc[index][email_col] if email_col is not None else ""
        phone_value = raw.iloc[index][phone_col] if phone_col is not None else ""
        text_name = "" if pd.isna(name_value) else str(name_value).strip()
        text_email = "" if pd.isna(email_value) else str(email_value).strip()
        text_phone = "" if pd.isna(phone_value) else normalize_phone(phone_value)
        if text_name:
            raw_names.append(text_name)
        elif text_email:
            raw_names.append(text_email.split("@", 1)[0])
        elif text_phone:
            raw_names.append(text_phone)
        else:
            raw_names.append(f"User {index + 1}")

    display_names, user_ids = make_unique_display_names(raw_names)

    return pd.DataFrame(
        {
            "UserID": user_ids,
            "Display_Name": display_names,
            "Email": (
                raw[email_col].fillna("").astype(str).str.strip().tolist()
                if email_col is not None
                else [""] * len(raw)
            ),
            "Phone": (
                raw[phone_col].apply(normalize_phone).tolist()
                if phone_col is not None
                else [""] * len(raw)
            ),
            "Event_Name": (
                raw[event_name_col].fillna("").astype(str).str.strip().tolist()
                if event_name_col is not None
                else [""] * len(raw)
            ),
            "Event_Date": (
                raw[date_col].apply(format_event_date).tolist()
                if date_col is not None
                else [""] * len(raw)
            ),
        }
    )


def find_column_name(df, candidates):
    for candidate in candidates:
        candidate_normalized = candidate.strip().lower()
        for col in df.columns:
            if str(col).strip().lower() == candidate_normalized:
                return col
    return None


def slugify_filename_part(value):
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s-]+", "_", text.strip())
    return text.strip("_")


def build_pdf_filename(name, event_name=""):
    safe_name = slugify_filename_part(name or "Participant")
    safe_event = slugify_filename_part(event_name or "")
    if safe_event:
        return f"{safe_event}_{safe_name}.pdf"
    return f"RCube_Report_{safe_name}.pdf"


def get_row_contact_details(raw, results, user_id):
    match = results[results["UserID"] == user_id]
    if match.empty:
        return {"email": "", "name": user_id}

    result_index = match.index[0]
    source_row = raw.iloc[result_index]
    email_col = find_email_column(raw)
    name_col = find_name_column(raw)

    email = ""
    if email_col is not None:
        value = source_row[email_col]
        email = "" if pd.isna(value) else str(value).strip()
    elif len(source_row) > 2:
        value = source_row.iloc[2]
        email = "" if pd.isna(value) else str(value).strip()

    display_name = match.iloc[0]["Display_Name"]
    if name_col is not None:
        value = source_row[name_col]
        name = display_name if pd.isna(value) else str(value).strip()
    elif len(source_row) > 29:
        value = source_row.iloc[29]
        name = display_name if pd.isna(value) else str(value).strip()
    else:
        name = display_name

    return {"email": email, "name": name}


def find_school_column(df):
    return find_column_name(
        df,
        [
            "school",
            "school name",
            "name of school",
            "school/institution",
            "institution",
            "institution name",
            "institute",
            "organisation",
            "organization",
        ],
    )


def find_date_column(df):
    return find_column_name(
        df,
        [
            "start date",
            "survey date",
            "date",
            "submission date",
            "submitted at",
            "timestamp",
            "created at",
        ],
    )


def find_event_name_column(df):
    return find_column_name(
        df,
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


def format_event_date(value):
    if value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() == "":
        return ""
    try:
        ts = pd.to_datetime(value, dayfirst=True, errors="coerce")
        if pd.isna(ts):
            ts = pd.to_datetime(value, errors="coerce")
        if pd.isna(ts):
            return str(value).strip()
        day = int(ts.day)
        if 10 <= day % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        return f"{day}{suffix} {ts.strftime('%B %Y')}"
    except Exception:
        return str(value).strip()


def to_display_case(value):
    text = str(value or "").strip()
    if not text:
        return ""
    pieces = re.split(r"(\s+)", text.lower())
    converted = []
    for piece in pieces:
        if not piece or piece.isspace():
            converted.append(piece)
            continue
        converted.append("-".join(part.capitalize() for part in piece.split("-")))
    return "".join(converted)


def infer_event_name_from_source_name(source_name):
    stem = Path(str(source_name or "Event")).stem
    stem = re.sub(r"(?i)\b(survey_report|survey|prereport|postreport|report|complete)\b", " ", stem)
    stem = re.sub(r"[_\-]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    return to_display_case(stem) if stem else ""


def is_fallback_event_name(event_name, source_name=""):
    candidate = str(event_name or "").strip()
    if not candidate:
        return True
    source_fallback = infer_event_name_from_source_name(source_name) if source_name else ""
    if source_fallback and candidate.casefold() == source_fallback.casefold():
        return True
    normalized = slugify_filename_part(candidate)
    return normalized.startswith("survey-report-") or normalized.startswith("prereport-") or normalized.startswith("survey26thapril")


def infer_event_date_from_source_name(source_name):
    source = str(source_name or "")
    match = re.search(r"(\d{1,2})(?:st|nd|rd|th)?([A-Za-z]+)", source)
    if not match:
        return ""
    day = int(match.group(1))
    month_raw = match.group(2)
    try:
        parsed = pd.to_datetime(f"{day} {month_raw} {pd.Timestamp.now().year}", dayfirst=True, errors="coerce")
        if pd.isna(parsed):
            return ""
        return format_event_date(parsed)
    except Exception:
        return ""


@st.cache_data(ttl=600, show_spinner=False)
def fetch_registration_details_from_event_db(email="", phone=""):
    if not EVENT_DATABASE_URL:
        return {}

    try:
        import psycopg
        from psycopg import sql
    except Exception:
        return {}

    email = str(email or "").strip().lower()
    phone_digits = normalize_phone(phone)
    phone_candidates = []
    if phone_digits:
        phone_candidates.append(phone_digits)
        if len(phone_digits) == 10:
            phone_candidates.append(f"91{phone_digits}")

    try:
        with psycopg.connect(EVENT_DATABASE_URL, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select column_name
                    from information_schema.columns
                    where table_schema = 'public' and table_name = 'registrations'
                    """
                )
                columns = {row[0] for row in cur.fetchall()}
                if not columns:
                    return {}

                def first_present(column_set, *candidates):
                    for candidate in candidates:
                        if candidate in column_set:
                            return candidate
                    return None

                registration_event_id_col = first_present(columns, "event_id", "eventid")
                event_table_name = None
                event_columns = set()
                for candidate_table in ("event", "events"):
                    cur.execute(
                        """
                        select column_name
                        from information_schema.columns
                        where table_schema = 'public' and table_name = %s
                        """,
                        (candidate_table,),
                    )
                    candidate_columns = {row[0] for row in cur.fetchall()}
                    if candidate_columns:
                        event_table_name = candidate_table
                        event_columns = candidate_columns
                        break

                registration_event_name_col = first_present(
                    columns, "event_name", "event", "event_title", "session_name", "workshop_name", "workshop_title", "program_name"
                )

                select_map = {
                    "full_name": first_present(columns, "full_name", "name"),
                    "email": first_present(columns, "email", "email_address"),
                    "phone": first_present(columns, "phone", "mobile", "phone_number"),
                    "school_name": first_present(columns, "school_name", "school", "institution_name", "schoolname"),
                    "event_name": registration_event_name_col,
                    "created_at": first_present(columns, "created_at"),
                    "registered_on": first_present(columns, "registered_on", "created_at"),
                }

                joined_event_name_col = None
                event_id_pk_col = None
                if event_table_name and registration_event_id_col:
                    event_id_pk_col = first_present(event_columns, "id", "event_id", "eventid")
                    joined_event_name_col = first_present(
                        event_columns,
                        "event_name",
                        "name",
                        "title",
                        "event_title",
                        "session_name",
                        "workshop_name",
                        "workshop_title",
                        "program_name",
                    )
                    if joined_event_name_col:
                        # Always prefer the canonical event title from the event table
                        # over any registration-side fallback field.
                        select_map["event_name"] = "__joined_event_name__"

                selected_pairs = [(alias, col) for alias, col in select_map.items() if col]
                if not selected_pairs:
                    return {}

                select_items = []
                for alias, col in selected_pairs:
                    if col == "__joined_event_name__":
                        select_items.append(
                            sql.SQL("evt.{} AS {}").format(
                                sql.Identifier(joined_event_name_col),
                                sql.Identifier(alias),
                            )
                        )
                    else:
                        select_items.append(
                            sql.SQL("r.{} AS {}").format(
                                sql.Identifier(col),
                                sql.Identifier(alias),
                            )
                        )

                where_clauses = []
                params = []
                if email and select_map["email"]:
                    where_clauses.append(
                        sql.SQL("lower(trim(coalesce(r.{}::text, ''))) = %s").format(
                            sql.Identifier(select_map["email"])
                        )
                    )
                    params.append(email)
                if phone_candidates and select_map["phone"]:
                    where_clauses.append(
                        sql.SQL(
                            "regexp_replace(coalesce(r.{}::text, ''), '[^0-9]', '', 'g') = ANY(%s)"
                        ).format(sql.Identifier(select_map["phone"]))
                    )
                    params.append(phone_candidates)
                if not where_clauses:
                    return {}

                query = sql.SQL("SELECT {fields} FROM public.registrations r").format(
                    fields=sql.SQL(", ").join(select_items),
                )
                if event_table_name and registration_event_id_col and event_id_pk_col and joined_event_name_col:
                    query += sql.SQL(" LEFT JOIN public.{} evt ON r.{} = evt.{}").format(
                        sql.Identifier(event_table_name),
                        sql.Identifier(registration_event_id_col),
                        sql.Identifier(event_id_pk_col),
                    )
                query += sql.SQL(" WHERE {conditions} LIMIT 1").format(
                    conditions=sql.SQL(" OR ").join(where_clauses)
                )
                cur.execute(query, params)
                row = cur.fetchone()
                if not row:
                    return {}

                aliases = [alias for alias, _ in selected_pairs]
                return dict(zip(aliases, row))
    except Exception:
        return {}


@st.cache_data(ttl=600, show_spinner=False)
def fetch_registration_details(email="", phone=""):
    db_record = fetch_registration_details_from_event_db(email=email, phone=phone)
    if db_record:
        return db_record

    if not SUPABASE_URL or not SUPABASE_API_KEY:
        return {}

    email = str(email or "").strip().lower()
    phone_digits = normalize_phone(phone)
    phone_candidates = []
    if phone_digits:
        phone_candidates.append(phone_digits)
        if len(phone_digits) == 10:
            phone_candidates.append(f"91{phone_digits}")

    base_url = f"{SUPABASE_URL}/rest/v1/registrations"
    headers = {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
    }

    def run_query(params):
        try:
            response = requests.get(base_url, headers=headers, params=params, timeout=20)
            if not response.ok:
                return {}
            payload = response.json()
            return payload[0] if payload else {}
        except Exception:
            return {}

    select_fields = "full_name,email,phone,school_name,created_at,registered_on"

    if email and phone_candidates:
        for candidate in phone_candidates:
            record = run_query(
                {
                    "select": select_fields,
                    "email": f"eq.{email}",
                    "phone": f"eq.{candidate}",
                    "limit": "1",
                }
            )
            if record:
                return record

    if email:
        record = run_query({"select": select_fields, "email": f"eq.{email}", "limit": "1"})
        if record:
            return record

    for candidate in phone_candidates:
        record = run_query({"select": select_fields, "phone": f"eq.{candidate}", "limit": "1"})
        if record:
            return record

    return {}


def enrich_certificate_details(details, source_name=""):
    enriched = dict(details or {})
    source_email = str(enriched.get("email", "") or "").strip()
    source_phone = normalize_phone(enriched.get("phone", ""))
    registration = fetch_registration_details(
        email=source_email,
        phone=source_phone,
    )

    if registration.get("full_name"):
        enriched["name"] = to_display_case(registration.get("full_name", ""))
    else:
        enriched["name"] = to_display_case(enriched.get("name", ""))

    if registration.get("school_name"):
        enriched["school"] = to_display_case(registration.get("school_name", ""))
    else:
        enriched["school"] = to_display_case(enriched.get("school", ""))

    enriched["phone"] = normalize_phone(
        registration.get("phone", "") or source_phone
    )
    enriched["email"] = source_email
    existing_event_name = str(enriched.get("event_name", "") or "").strip()
    if is_fallback_event_name(existing_event_name, source_name):
        existing_event_name = ""
    enriched["event_name"] = (
        str(registration.get("event_name", "") or "").strip()
        or existing_event_name
        or infer_event_name_from_source_name(source_name)
    )
    enriched["event_date"] = (
        enriched.get("event_date", "")
        or infer_event_date_from_source_name(source_name)
        or format_event_date(registration.get("registered_on") or registration.get("created_at"))
    )
    return enriched


def get_row_certificate_details(raw, results, user_id):
    return get_row_certificate_details_with_overrides(raw, results, user_id, None)


def get_row_certificate_details_with_overrides(raw, results, user_id, overrides=None):
    match = results[results["UserID"] == user_id]
    if match.empty:
        return {"school": "", "event_date": "", "phone": "", "event_name": ""}

    result_index = match.index[0]
    source_row = raw.iloc[result_index]
    school_col = find_school_column(raw)
    date_col = find_date_column(raw)
    phone_col = find_phone_column(raw)
    event_name_col = find_event_name_column(raw)

    school = ""
    if school_col is not None and school_col in source_row.index:
        value = source_row[school_col]
        school = "" if pd.isna(value) else str(value).strip()

    event_date = ""
    if date_col is not None and date_col in source_row.index:
        event_date = format_event_date(source_row[date_col])

    phone = ""
    if phone_col is not None and phone_col in source_row.index:
        phone = normalize_phone(source_row[phone_col])

    event_name = ""
    if event_name_col is not None and event_name_col in source_row.index:
        value = source_row[event_name_col]
        event_name = "" if pd.isna(value) else str(value).strip()

    overrides = overrides or {}
    override_event_date = str(overrides.get("event_date", "") or "").strip()
    override_event_name = str(overrides.get("event_name", "") or "").strip()
    if override_event_date:
        event_date = override_event_date
    if override_event_name:
        event_name = override_event_name

    return {"school": school, "event_date": event_date, "phone": phone, "event_name": event_name}


def get_comparison_contact_details(pre_df, post_df, phone, participant_name):
    email_candidates = ["email", "email address", "email_address", "mail"]
    name_candidates = ["name", "full name", "participant name", "teacher name"]

    def extract_contact(df):
        if df is None or df.empty:
            return {"email": "", "name": ""}
        phone_col = find_phone_column(df)
        if phone_col is None:
            return {"email": "", "name": ""}
        matches = df[df[phone_col].apply(normalize_phone) == phone]
        if matches.empty:
            return {"email": "", "name": ""}
        source_row = matches.iloc[0]
        email_col = find_column_name(df, email_candidates)
        name_col = find_column_name(df, name_candidates)
        email = ""
        name = ""
        if email_col is not None:
            value = source_row[email_col]
            email = "" if pd.isna(value) else str(value).strip()
        if name_col is not None:
            value = source_row[name_col]
            name = "" if pd.isna(value) else str(value).strip()
        return {"email": email, "name": name}

    pre_contact = extract_contact(pre_df)
    post_contact = extract_contact(post_df)
    return {
        "email": pre_contact["email"] or post_contact["email"],
        "name": pre_contact["name"] or post_contact["name"] or participant_name,
    }


def build_comparison_pdf_filename(name):
    safe_name = "_".join(str(name or "Participant").split())
    return f"PrePost_Comparison_{safe_name}.pdf"


def build_question_short_labels(base_answer_key):
    labels = []
    for index, question in enumerate(base_answer_key.keys(), start=1):
        cleaned = re.sub(r"\s+", " ", str(question)).strip().rstrip(":?.")
        if len(cleaned) > 72:
            cleaned = cleaned[:69].rstrip() + "..."
        labels.append({"id": f"Q{index}", "text": cleaned})
    return labels


def render_panel_header(eyebrow, title, subtitle):
    st.markdown(
        f"""
        <div style="margin-bottom: 1.25rem;">
            <div style="font-family: 'DM Mono', monospace; font-size: 0.72rem; color: #64748b; letter-spacing: 0.18em; text-transform: uppercase; margin-bottom: 0.35rem;">
                {eyebrow}
            </div>
            <div style="font-family: 'Playfair Display', serif; font-size: 2.35rem; font-weight: 900; color: #0f172a; line-height: 1.1; margin-bottom: 0.4rem;">
                {title}
            </div>
            <div style="font-size: 1rem; color: #475569; max-width: 760px; line-height: 1.7;">
                {subtitle}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_info_card(title, body):
    st.markdown(
        f"""
        <div class="explain-wrap" style="margin-bottom: 1rem;">
            <div class="explain-sub">{title}</div>
            <div style="color:#334155; line-height:1.7;">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_small_metric(label, value, help_text=""):
    hint_html = (
        f"<div style='font-size:0.86rem; color:#64748b; margin-top:0.4rem;'>{help_text}</div>"
        if help_text
        else ""
    )
    st.markdown(
        f"""
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:12px; padding:1rem 1.1rem; height:100%;">
            <div style="font-family:'DM Mono', monospace; font-size:0.66rem; color:#64748b; letter-spacing:0.16em; text-transform:uppercase; margin-bottom:0.35rem;">
                {label}
            </div>
            <div style="font-family:'Playfair Display', serif; font-size:1.85rem; font-weight:900; color:#0f172a; line-height:1.1;">
                {value}
            </div>
            {hint_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_progress_metric(panel, current, total):
    with panel.container():
        render_small_metric("PDF Progress", f"{current} / {total}")


def ensure_generated_pdf_dir(library_key=None):
    GENERATED_PDF_DIR.mkdir(exist_ok=True)
    if library_key:
        path = GENERATED_PDF_DIR / library_key
        path.mkdir(exist_ok=True)
        return path
    return GENERATED_PDF_DIR


def build_library_key(file_name, file_bytes):
    import hashlib

    digest = hashlib.sha1(file_bytes).hexdigest()[:12]
    safe_name = "".join(ch if ch.isalnum() else "-" for ch in str(file_name or "uploaded-list").lower()).strip("-")
    safe_name = safe_name[:40] or "uploaded-list"
    return f"{safe_name}-{digest}"


def get_library_paths(library_key):
    library_dir = ensure_generated_pdf_dir(library_key)
    return library_dir, library_dir / "index.json"


def get_library_meta_path(library_key):
    library_dir, _ = get_library_paths(library_key)
    return library_dir / "meta.json"


def infer_report_type(library_key, source_name=""):
    text = f"{library_key} {source_name}".lower()
    comparison_markers = [
        "comparison",
        "pre-post",
        "pre_post",
        "-pre-",
        "-post-",
        " vs ",
    ]
    if any(marker in text for marker in comparison_markers):
        return "comparison"
    return "single"


def infer_source_name_from_library_key(library_key):
    match = re.match(r"^(.*)-([0-9a-f]{12})$", library_key)
    base = match.group(1) if match else library_key
    if base.endswith("-csv"):
        return base[:-4].replace("-", "_") + ".csv"
    return base.replace("-", "_")


def persist_library_meta(library_key, source_name="", report_type="single"):
    meta_path = get_library_meta_path(library_key)
    payload = {
        "library_key": library_key,
        "source_name": source_name or library_key,
        "report_type": report_type,
    }
    meta_path.write_text(json.dumps(payload, indent=2))


def load_library_meta(library_key):
    meta_path = get_library_meta_path(library_key)
    if meta_path.exists():
        try:
            payload = json.loads(meta_path.read_text())
            payload.setdefault(
                "report_type",
                infer_report_type(library_key, payload.get("source_name", library_key)),
            )
            return payload
        except Exception:
            pass
    return {
        "library_key": library_key,
        "source_name": infer_source_name_from_library_key(library_key),
        "report_type": infer_report_type(library_key, library_key),
    }


def build_pdf_record_from_file(pdf_path):
    user_label = pdf_path.stem.replace("RCube_Report_", "").replace("PrePost_Comparison_", "")
    user_label = user_label.replace("_", " ").strip() or pdf_path.stem
    return {
        "file_name": pdf_path.name,
        "file_path": str(pdf_path.resolve()),
        "email": "",
        "name": user_label,
        "school": "",
        "event_date": "",
        "phone": "",
        "event_name": "",
    }


def normalize_person_label(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def normalize_email_value(value):
    text = str(value or "").strip()
    return text if "@" in text else ""


def candidate_person_lookup_keys(*values):
    keys = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        normalized = normalize_person_label(text)
        if normalized:
            keys.add(normalized)
        parts = [part for part in re.split(r"\s+", text) if part]
        if parts:
            first = normalize_person_label(parts[0])
            if first:
                keys.add(first)
        if len(parts) >= 2:
            first_two = normalize_person_label(" ".join(parts[:2]))
            if first_two:
                keys.add(first_two)
    return keys


def load_legacy_root_manifest():
    root_manifest = GENERATED_PDF_DIR / "index.json"
    if not root_manifest.exists():
        return {}
    try:
        return json.loads(root_manifest.read_text())
    except Exception:
        return {}


def find_source_csv_candidates(source_name):
    if not source_name:
        return []
    candidates = []
    search_roots = [
        Path.cwd(),
        Path("/Users/ritu/Downloads"),
        Path("/Users/ritu/Desktop"),
    ]
    for root in search_roots:
        try:
            direct = root / source_name
            if direct.exists():
                candidates.append(direct)
            for match in root.glob(f"**/{source_name}"):
                if match.exists() and match not in candidates:
                    candidates.append(match)
        except Exception:
            continue
    return candidates


def recover_library_record_contact(library_key, source_name, pdf_user, pdf_info):
    current_email = normalize_email_value(pdf_info.get("email", ""))
    if current_email:
        return {
            "email": current_email,
            "name": str(pdf_info.get("name", pdf_user) or pdf_user).strip(),
            "school": str(pdf_info.get("school", "") or "").strip(),
            "event_date": str(pdf_info.get("event_date", "") or "").strip(),
            "phone": str(pdf_info.get("phone", "") or "").strip(),
            "event_name": str(pdf_info.get("event_name", "") or "").strip(),
        }

    csv_lookup = {}
    for candidate in find_source_csv_candidates(source_name):
        csv_lookup = build_email_lookup_from_csv(candidate)
        if csv_lookup:
            break

    if not csv_lookup:
        return {
            "email": current_email,
            "name": str(pdf_info.get("name", pdf_user) or pdf_user).strip(),
            "school": str(pdf_info.get("school", "") or "").strip(),
            "event_date": str(pdf_info.get("event_date", "") or "").strip(),
            "phone": str(pdf_info.get("phone", "") or "").strip(),
            "event_name": str(pdf_info.get("event_name", "") or "").strip(),
        }

    current_phone = normalize_phone(pdf_info.get("phone", ""))
    if current_phone:
        for recovered in csv_lookup.values():
            if normalize_phone(recovered.get("phone", "")) == current_phone:
                recovered = dict(recovered)
                recovered["email"] = normalize_email_value(recovered.get("email", ""))
                if recovered["email"]:
                    return recovered

    for key in candidate_person_lookup_keys(
        pdf_user,
        pdf_info.get("name", ""),
        resolve_record_display_name(
            {"name": pdf_info.get("name", ""), "email": pdf_info.get("email", ""), "UserID": pdf_user},
            fallback=pdf_user,
        ),
    ):
        if key and key in csv_lookup:
            recovered = dict(csv_lookup[key])
            recovered["email"] = normalize_email_value(recovered.get("email", ""))
            return recovered

    candidate_keys = candidate_person_lookup_keys(pdf_user, pdf_info.get("name", ""))
    for key in candidate_keys:
        for lookup_key, recovered in csv_lookup.items():
            if key and lookup_key and (key.startswith(lookup_key) or lookup_key.startswith(key)):
                recovered = dict(recovered)
                recovered["email"] = normalize_email_value(recovered.get("email", ""))
                if recovered["email"]:
                    return recovered

    return {
        "email": current_email,
        "name": str(pdf_info.get("name", pdf_user) or pdf_user).strip(),
        "school": str(pdf_info.get("school", "") or "").strip(),
        "event_date": str(pdf_info.get("event_date", "") or "").strip(),
        "phone": str(pdf_info.get("phone", "") or "").strip(),
        "event_name": str(pdf_info.get("event_name", "") or "").strip(),
    }


def get_edxso_logo_data_uri():
    candidates = [
        Path("/Users/ritu/Documents/GitHub/landing-page/public/EDXSO.png"),
        Path("/Users/ritu/Documents/GitHub/landing-page-mu/public/EDXSO.png"),
        Path("/Users/ritu/Documents/GitHub/reporter-upgradation/EDXSO Logo.png"),
        Path("/Users/ritu/Documents/GitHub/edxso-login-redirect/src/assets/edxso-logo.png"),
        Path("/Users/ritu/Documents/GitHub/connect-edify-event/src/assets/edxso-logo.png"),
        Path("/Users/ritu/Documents/GitHub/Spark-Edxso/studentreport/edxso-logo.png"),
    ]
    mime_types = {
        ".png": "image/png",
        ".ico": "image/x-icon",
    }
    for path in candidates:
        try:
            if path.exists():
                encoded = base64.b64encode(path.read_bytes()).decode("ascii")
                mime_type = mime_types.get(path.suffix.lower(), "application/octet-stream")
                return f"data:{mime_type};base64,{encoded}"
        except Exception:
            continue
    return ""


def file_to_data_uri(path: Path):
    if not path.exists():
        return ""
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
    }.get(path.suffix.lower(), "application/octet-stream")
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def generate_certificate_pdf_playwright(
    participant_name,
    school_name="",
    event_date="",
    event_name="",
    workshop_title="Competency Based Assessment Session",
):
    participant_name = html.escape(str(participant_name or "Participant").strip())
    school_name = html.escape(str(school_name or "School").strip())
    event_date = html.escape(str(event_date or "").strip())
    event_name = html.escape(str(event_name or workshop_title or "").strip())
    template_path = Path(__file__).resolve().parent / "assets" / "certificate" / "template.html"
    if template_path.exists():
        html_doc = template_path.read_text()
        html_doc = html_doc.replace("{{LOGO_URI}}", get_edxso_logo_data_uri())
        html_doc = html_doc.replace(
            "{{BACKGROUND_URI}}",
            file_to_data_uri(Path(__file__).resolve().parent / "assets" / "certificate" / "background.png"),
        )
        html_doc = html_doc.replace(
            "{{SIGNATURE_URI}}",
            file_to_data_uri(Path(__file__).resolve().parent / "assets" / "certificate" / "signature.png"),
        )
        html_doc = html_doc.replace("{{NAME}}", participant_name)
        html_doc = html_doc.replace("{{SCHOOL}}", school_name)
        html_doc = html_doc.replace("{{DATE}}", event_date)
        html_doc = html_doc.replace("{{EVENT_NAME}}", event_name)
    else:
        raise FileNotFoundError(f"Certificate template not found: {template_path}")

    ensure_playwright_ready()
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--single-process"],
        )
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.set_content(html_doc, wait_until="load")
        page.wait_for_timeout(300)
        pdf_bytes = page.pdf(
            width="1280px",
            height="720px",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        browser.close()
    return pdf_bytes


def build_email_lookup_from_csv(csv_path):
    try:
        raw = pd.read_csv(csv_path)
    except Exception:
        return {}

    lookup = {}
    survey_kind = infer_single_survey_kind(raw)

    if survey_kind in {"pre_assessment", "post_assessment"}:
        api_key = os.getenv("GEMINI_API_KEY")
        answer_key = PRE_ASSESSMENT_KEY if survey_kind == "pre_assessment" else POST_ASSESSMENT_KEY
        try:
            results, _ = prepare_assessment_results(raw, answer_key, api_key)
        except Exception:
            return {}

        for _, result_row in results.iterrows():
            user_id = result_row["UserID"]
            display_name = result_row["Display_Name"]
            certificate = get_row_certificate_details(raw, results, user_id)
            combined = {
                "email": str(result_row.get("Email", "") or "").strip(),
                "name": display_name,
                "school": certificate.get("school", ""),
                "event_date": certificate.get("event_date", ""),
                "phone": certificate.get("phone", ""),
                "event_name": certificate.get("event_name", ""),
            }
            for key in candidate_person_lookup_keys(user_id, display_name, combined.get("name", "")):
                if key:
                    lookup[key] = combined
        return lookup

    try:
        results = prepare_results(raw)
    except Exception:
        return {}

    for _, result_row in results.iterrows():
        user_id = result_row["UserID"]
        display_name = result_row["Display_Name"]
        contact = get_row_contact_details(raw, results, user_id)
        certificate = get_row_certificate_details(raw, results, user_id)
        combined = {
            "email": contact.get("email", ""),
            "name": contact.get("name", display_name),
            "school": certificate.get("school", ""),
            "event_date": certificate.get("event_date", ""),
            "phone": certificate.get("phone", ""),
            "event_name": certificate.get("event_name", ""),
        }
        for key in candidate_person_lookup_keys(user_id, display_name, combined.get("name", "")):
            if key:
                lookup[key] = combined
    return lookup


def find_matching_result_user_id(results, pdf_user, pdf_info):
    if results is None or results.empty:
        return None

    if pdf_user in results["UserID"].values:
        return pdf_user

    record_phone = normalize_phone(pdf_info.get("phone", ""))
    if record_phone:
        for _, result_row in results.iterrows():
            if normalize_phone(result_row.get("Phone", "")) == record_phone:
                return result_row["UserID"]

    target_keys = set(
        candidate_person_lookup_keys(
            pdf_user,
            pdf_info.get("name", ""),
            pdf_info.get("email", ""),
        )
    )
    if not target_keys:
        return None

    for _, result_row in results.iterrows():
        result_keys = set(
            candidate_person_lookup_keys(
                result_row.get("UserID", ""),
                result_row.get("Display_Name", ""),
                result_row.get("Email", ""),
            )
        )
        if target_keys & result_keys:
            return result_row["UserID"]
        for target_key in target_keys:
            for result_key in result_keys:
                if (
                    target_key
                    and result_key
                    and (target_key.startswith(result_key) or result_key.startswith(target_key))
                ):
                    return result_row["UserID"]
    return None


def recover_contact_from_current_dataset(raw, results, pdf_user, pdf_info, certificate_overrides=None):
    matched_user_id = find_matching_result_user_id(results, pdf_user, pdf_info)
    if not matched_user_id:
        return {
            "email": normalize_email_value(pdf_info.get("email", "")),
            "name": str(pdf_info.get("name", "") or pdf_user).strip(),
            "school": str(pdf_info.get("school", "") or "").strip(),
            "event_date": str(pdf_info.get("event_date", "") or "").strip(),
            "phone": normalize_phone(pdf_info.get("phone", "")),
            "event_name": str(pdf_info.get("event_name", "") or "").strip(),
        }

    contact = get_row_contact_details(raw, results, matched_user_id)
    certificate = get_row_certificate_details_with_overrides(
        raw,
        results,
        matched_user_id,
        certificate_overrides,
    )
    return {
        "email": normalize_email_value(contact.get("email", "")),
        "name": str(contact.get("name", "") or matched_user_id).strip(),
        "school": str(certificate.get("school", "") or "").strip(),
        "event_date": str(certificate.get("event_date", "") or "").strip(),
        "phone": normalize_phone(certificate.get("phone", "")),
        "event_name": str(certificate.get("event_name", "") or "").strip(),
    }


def backfill_library_from_current_dataset(raw, results, library, survey_kind="rcube", certificate_overrides=None):
    if not library:
        return library, False

    updated = False
    for user_id, record in library.items():
        recovered = recover_contact_from_current_dataset(
            raw,
            results,
            user_id,
            record,
            certificate_overrides=certificate_overrides,
        )
        new_email = recovered.get("email", "")
        new_name = recovered.get("name", record.get("name", user_id))
        new_school = recovered.get("school", "") or record.get("school", "")
        new_event_date = recovered.get("event_date", "") or record.get("event_date", "")
        new_phone = recovered.get("phone", "") or record.get("phone", "")
        new_event_name = recovered.get("event_name", "") or record.get("event_name", "")
        if (
            new_email != record.get("email", "")
            or new_name != record.get("name", user_id)
            or new_school != record.get("school", "")
            or new_event_date != record.get("event_date", "")
            or new_phone != record.get("phone", "")
            or new_event_name != record.get("event_name", "")
        ):
            record["email"] = new_email
            record["name"] = new_name
            record["school"] = new_school
            record["event_date"] = new_event_date
            record["phone"] = new_phone
            record["event_name"] = new_event_name
            updated = True

    return library, updated


def backfill_library_contacts(library_key, library):
    if not library:
        return library

    meta = load_library_meta(library_key)
    report_type = meta.get("report_type", "single")
    if report_type != "single":
        return library

    updated = False
    legacy_manifest = load_legacy_root_manifest()
    legacy_lookup = {
        normalize_person_label(name): record for name, record in legacy_manifest.items()
    }

    csv_lookup = {}
    source_name = meta.get("source_name", infer_source_name_from_library_key(library_key))
    for candidate in find_source_csv_candidates(source_name):
        csv_lookup = build_email_lookup_from_csv(candidate)
        if csv_lookup:
            break

    for user_id, record in library.items():
        normalized = normalize_person_label(record.get("name", user_id))
        legacy_record = legacy_lookup.get(normalized, {})
        csv_record = csv_lookup.get(normalized, {})
        email = csv_record.get("email") or legacy_record.get("email") or ""
        name = csv_record.get("name") or legacy_record.get("name") or record.get("name", user_id)
        new_school = csv_record.get("school", record.get("school", ""))
        new_event_date = csv_record.get("event_date", record.get("event_date", ""))
        new_phone = csv_record.get("phone", record.get("phone", ""))
        new_event_name = csv_record.get("event_name", record.get("event_name", ""))
        if (
            email != record.get("email", "")
            or name != record.get("name", user_id)
            or new_school != record.get("school", "")
            or new_event_date != record.get("event_date", "")
            or new_phone != record.get("phone", "")
            or new_event_name != record.get("event_name", "")
        ):
            record["email"] = email
            record["name"] = name
            record["school"] = new_school
            record["event_date"] = new_event_date
            record["phone"] = new_phone
            record["event_name"] = new_event_name
            updated = True

    if updated:
        persist_generated_pdf_library(library, library_key)
        if not get_library_meta_path(library_key).exists():
            persist_library_meta(library_key, source_name, report_type="single")
    return library


def recover_generated_pdf_library_from_files(library_key):
    library_dir, _ = get_library_paths(library_key)
    recovered_library = {}
    for pdf_path in sorted(library_dir.glob("*.pdf")):
        record = build_pdf_record_from_file(pdf_path)
        recovered_library[record["name"]] = record
    return recovered_library


def load_generated_pdf_library(library_key):
    library_dir, index_path = get_library_paths(library_key)
    if not index_path.exists():
        recovered_library = recover_generated_pdf_library_from_files(library_key)
        if recovered_library:
            persist_generated_pdf_library(recovered_library, library_key)
        return recovered_library

    try:
        records = json.loads(index_path.read_text())
    except Exception:
        recovered_library = recover_generated_pdf_library_from_files(library_key)
        if recovered_library:
            persist_generated_pdf_library(recovered_library, library_key)
        return recovered_library

    library = {}
    for user_id, record in records.items():
        file_path = record.get("file_path", "")
        if file_path and Path(file_path).exists():
            library[user_id] = record

    recovered_library = recover_generated_pdf_library_from_files(library_key)
    updated = False
    for recovered_name, recovered_record in recovered_library.items():
        recovered_path = recovered_record["file_path"]
        if not any(record.get("file_path") == recovered_path for record in library.values()):
            library[recovered_name] = recovered_record
            updated = True
    if updated:
        persist_generated_pdf_library(library, library_key)
    return backfill_library_contacts(library_key, library)


def persist_generated_pdf_library(library, library_key):
    serializable = {}
    for user_id, record in library.items():
        serializable[user_id] = {
            "file_name": record["file_name"],
            "file_path": record["file_path"],
            "email": record.get("email", ""),
            "name": record.get("name", user_id),
            "school": record.get("school", ""),
            "event_date": record.get("event_date", ""),
            "phone": record.get("phone", ""),
            "event_name": record.get("event_name", ""),
        }
    _, index_path = get_library_paths(library_key)
    index_path.write_text(json.dumps(serializable, indent=2))


def save_generated_pdf_record(
    user_id,
    file_name,
    pdf_bytes,
    library_key,
    email="",
    name="",
    school="",
    event_date="",
    phone="",
    event_name="",
):
    library_dir, _ = get_library_paths(library_key)
    file_path = library_dir / file_name
    file_path.write_bytes(pdf_bytes)
    return {
        "file_name": file_name,
        "file_path": str(file_path.resolve()),
        "email": email,
        "name": name or user_id,
        "school": school,
        "event_date": event_date,
        "phone": phone,
        "event_name": event_name,
    }


def clear_generated_pdf_library(library_key):
    library_dir, index_path = get_library_paths(library_key)
    if library_dir.exists():
        for item in library_dir.iterdir():
            if item.is_file():
                item.unlink()
    index_path.write_text("{}")


def build_library_zip_bytes(records):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for _, record in records.items():
            file_path = Path(record["file_path"])
            if file_path.exists():
                zf.write(file_path, arcname=record["file_name"])
    return zip_buffer.getvalue()


def list_all_pdf_libraries(report_type=None):
    root = ensure_generated_pdf_dir()
    libraries = []
    for child in sorted(root.iterdir(), key=lambda path: path.name):
        if not child.is_dir():
            continue
        library_key = child.name
        records = load_generated_pdf_library(library_key)
        meta = load_library_meta(library_key)
        library_report_type = meta.get("report_type", "single")
        if report_type is not None and library_report_type != report_type:
            continue
        libraries.append(
            {
                "library_key": library_key,
                "source_name": meta.get("source_name", library_key),
                "report_type": library_report_type,
                "records": records,
            }
        )
    libraries = [item for item in libraries if item["records"]]
    libraries.sort(key=lambda item: item["source_name"].lower())
    return libraries


def render_generated_pdf_library(container, report_type="single", current_dataset=None):
    with container.container():
        all_libraries = list_all_pdf_libraries(report_type=report_type)
        if not all_libraries:
            st.info("No PDFs have been generated yet for this report type.")
            return

        st.markdown(section_header("04", "Generated PDFs"), unsafe_allow_html=True)
        current_library_key = st.session_state.get("current_library_key")
        current_library_size = len(st.session_state.generated_pdfs)
        certificate_overrides = (current_dataset or {}).get("certificate_overrides", {})
        if current_library_key:
            current_meta = load_library_meta(current_library_key)
            st.caption(
                f"Current uploaded survey: {current_meta.get('source_name', current_library_key)}"
            )
            st.caption(f"Saved for current survey: {current_library_size}")

        for library in all_libraries:
            library_key = library["library_key"]
            records = library["records"]
            is_current = library_key == current_library_key
            survey_title = library["source_name"]
            survey_label = "Current Survey" if is_current else "Previous Survey"
            certificate_enabled = report_type in {"single", "certificate_only"}
            library_updated = False
            expander_label = f"{survey_title} ({len(records)} reports)"
            with st.expander(expander_label, expanded=is_current):
                header_info_col, actions_col = st.columns([12, 1.8])
                with header_info_col:
                    st.caption(survey_label)
                    if certificate_enabled:
                        st.caption("Certificate email is available in this survey.")
                with actions_col:
                    download_col, delete_col = st.columns([1, 1], gap="small")
                    with download_col:
                        st.download_button(
                            "⬇",
                            data=build_library_zip_bytes(records),
                            file_name=f"{Path(survey_title).stem}_reports.zip",
                            mime="application/zip",
                            help=f"Download all reports for {survey_title} as a ZIP file",
                            key=f"download_zip_{library_key}",
                        )
                    with delete_col:
                        if st.button(
                            "🗑",
                            help=f"Delete all generated reports for {survey_title}",
                            key=f"delete_library_{library_key}",
                        ):
                            clear_generated_pdf_library(library_key)
                            if library_key == current_library_key:
                                st.session_state.generated_pdfs = {}
                            st.success(f"Deleted all generated reports for {survey_title}.")
                            st.rerun()

                if not records:
                    st.info("No PDFs are saved for this survey yet.")
                    continue

                for pdf_user, pdf_info in records.items():
                    if is_current and current_dataset:
                        live_contact = recover_contact_from_current_dataset(
                            current_dataset["raw"],
                            current_dataset["results"],
                            pdf_user,
                            pdf_info,
                            certificate_overrides=certificate_overrides,
                        )
                        if any(
                            live_contact.get(field, "") != str(pdf_info.get(field, "") or "").strip()
                            for field in ("email", "name", "school", "event_date", "phone", "event_name")
                        ):
                            for field in ("email", "name", "school", "event_date", "phone", "event_name"):
                                live_value = live_contact.get(field, "")
                                if live_value or not str(pdf_info.get(field, "") or "").strip():
                                    pdf_info[field] = live_value
                            library_updated = True
                    recovered_contact = recover_library_record_contact(library_key, survey_title, pdf_user, pdf_info)
                    if any(
                        recovered_contact.get(field, "") != str(pdf_info.get(field, "") or "").strip()
                        for field in ("email", "name", "school", "event_date", "phone", "event_name")
                    ):
                        for field in ("email", "name", "school", "event_date", "phone", "event_name"):
                            pdf_info[field] = recovered_contact.get(field, "")
                        library_updated = True
                    if certificate_enabled:
                        needs_enrichment = any(
                            not str(pdf_info.get(field, "") or "").strip()
                            for field in ("school", "event_date")
                        ) or is_fallback_event_name(pdf_info.get("event_name", ""), survey_title)
                        if needs_enrichment:
                            enriched_details = enrich_certificate_details(
                                {
                                    "name": pdf_info.get("name", ""),
                                    "school": pdf_info.get("school", ""),
                                    "event_date": pdf_info.get("event_date", ""),
                                    "email": pdf_info.get("email", ""),
                                    "phone": pdf_info.get("phone", ""),
                                    "event_name": pdf_info.get("event_name", ""),
                                },
                                source_name=survey_title,
                            )
                            for field in ("name", "school", "event_date", "email", "phone", "event_name"):
                                if enriched_details.get(field, "") != pdf_info.get(field, ""):
                                    pdf_info[field] = enriched_details.get(field, "")
                                    library_updated = True
                    pdf_label = resolve_record_display_name(
                        {"name": pdf_info.get("name", ""), "email": pdf_info.get("email", ""), "UserID": pdf_user},
                        fallback=pdf_user,
                    )
                    if report_type == "certificate_only":
                        label_col, download_col, cert_col = st.columns([1.4, 1, 1])
                    elif certificate_enabled:
                        label_col, download_col, send_col, cert_col = st.columns([1.4, 1, 1, 1])
                    else:
                        label_col, download_col, send_col = st.columns([1.4, 1, 1])
                    with label_col:
                        st.markdown(
                            f"""
                            <div class="explain-wrap" style="margin-bottom: 0.75rem;">
                                <div class="explain-sub">Generated Report</div>
                                <div style="font-size:1rem; color:#0f172a; font-weight:700;">{pdf_label}</div>
                                <div style="font-size:0.9rem; color:#64748b; margin-top:0.35rem;">{pdf_info['file_name']}</div>
                                <div style="font-size:0.85rem; color:#64748b; margin-top:0.25rem;">{pdf_info.get('email', 'No email found')}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    with download_col:
                        st.download_button(
                            label="Download Certificate" if report_type == "certificate_only" else "Download Report",
                            data=Path(pdf_info["file_path"]).read_bytes(),
                            file_name=pdf_info["file_name"],
                            mime="application/pdf",
                            use_container_width=True,
                            key=f"download_{library_key}_{pdf_user}",
                        )
                    if report_type != "certificate_only":
                        with send_col:
                            recipient_email = normalize_email_value(pdf_info.get("email", ""))
                            send_disabled = not recipient_email
                            if st.button(
                                "Send Email",
                                use_container_width=True,
                                key=f"send_{library_key}_{pdf_user}",
                                disabled=send_disabled,
                            ):
                                try:
                                    from send_pending_reports import send_email_with_attachment

                                    with st.spinner(f"Sending {pdf_label} to {recipient_email}..."):
                                        response = send_email_with_attachment(
                                            email=recipient_email,
                                            name=pdf_label,
                                            file_name=pdf_info["file_name"],
                                            file_bytes=Path(pdf_info["file_path"]).read_bytes(),
                                        )
                                    if response.status_code in (200, 201):
                                        st.success(f"Sent {pdf_label} to {recipient_email}")
                                    else:
                                        st.error(
                                            f"Failed for {pdf_label} ({response.status_code}): {response.text[:200]}"
                                        )
                                except Exception as e:
                                    st.error(f"Send failed for {pdf_label}: {e}")
                    if certificate_enabled:
                        with cert_col:
                            cert_recipient_email = normalize_email_value(pdf_info.get("email", ""))
                            send_cert_disabled = not cert_recipient_email
                            if st.button(
                                "Send Certificate",
                                use_container_width=True,
                                key=f"send_certificate_{library_key}_{pdf_user}",
                                disabled=send_cert_disabled,
                            ):
                                try:
                                    from send_pending_reports import send_certificate_email_with_attachment

                                    with st.spinner(f"Sending certificate to {cert_recipient_email}..."):
                                        certificate_details = enrich_certificate_details(
                                            {
                                                "name": pdf_label,
                                                "school": pdf_info.get("school", ""),
                                                "event_date": pdf_info.get("event_date", ""),
                                                "email": cert_recipient_email,
                                                "phone": pdf_info.get("phone", ""),
                                                "event_name": pdf_info.get("event_name", ""),
                                            },
                                            source_name=survey_title,
                                        )
                                        override_event_name = str(certificate_overrides.get("event_name", "") or "").strip()
                                        override_event_date = str(certificate_overrides.get("event_date", "") or "").strip()
                                        if is_current and override_event_name:
                                            certificate_details["event_name"] = override_event_name
                                        if is_current and override_event_date:
                                            certificate_details["event_date"] = override_event_date
                                        certificate_bytes = generate_certificate_pdf_playwright(
                                            certificate_details.get("name", pdf_label),
                                            school_name=certificate_details.get("school", ""),
                                            event_date=certificate_details.get("event_date", ""),
                                            event_name=certificate_details.get("event_name", ""),
                                            workshop_title="Competency Based Assessment Session",
                                        )
                                        certificate_name = (
                                            f"{slugify_filename_part(certificate_details.get('event_name', '') or 'Participation_Certificate')}"
                                            f"_Certificate_{slugify_filename_part(pdf_label)}.pdf"
                                        )
                                        response = send_certificate_email_with_attachment(
                                            email=cert_recipient_email,
                                            name=pdf_label,
                                            file_name=certificate_name,
                                            file_bytes=certificate_bytes,
                                            event_date=pdf_info.get("event_date", ""),
                                        )
                                    if response.status_code in (200, 201):
                                        st.success(f"Sent certificate to {cert_recipient_email}")
                                    else:
                                        st.error(
                                            f"Certificate send failed for {pdf_label} ({response.status_code}): {response.text[:200]}"
                                        )
                                except Exception as e:
                                    st.error(f"Certificate send failed for {pdf_label}: {e}")
                if library_updated:
                    persist_generated_pdf_library(records, library_key)


def render_saved_library_bulk_email_panel(report_type, key_prefix):
    libraries = list_all_pdf_libraries(report_type=report_type)
    if not libraries:
        st.info("No generated PDF libraries are available for bulk email yet.")
        return

    progress_panel = st.empty()
    status_panel = st.empty()
    log_panel = st.empty()

    for library in libraries:
        email_ready_records = {
            user_id: record
            for user_id, record in library["records"].items()
            if record.get("email") and Path(record["file_path"]).exists()
        }
        card_col, action_col = st.columns([1.4, 1])
        with card_col:
            st.markdown(
                f"""
                <div class="explain-wrap" style="margin-bottom: 0.75rem;">
                    <div class="explain-sub">Saved Survey</div>
                    <div style="font-size:1rem; color:#0f172a; font-weight:700;">{library['source_name']}</div>
                    <div style="font-size:0.9rem; color:#64748b; margin-top:0.35rem;">Generated reports: {len(library['records'])}</div>
                    <div style="font-size:0.85rem; color:#64748b; margin-top:0.25rem;">Email-ready reports: {len(email_ready_records)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with action_col:
            send_bulk_for_library = st.button(
                "Send Bulk Emails For This Survey",
                use_container_width=True,
                disabled=not email_ready_records,
                key=f"{key_prefix}_bulk_send_{library['library_key']}",
            )

        if send_bulk_for_library:
            try:
                from send_pending_reports import send_email_with_attachment

                sent_count = 0
                failed_count = 0
                run_log = []
                total_targets = len(email_ready_records)

                for index, (user_id, record) in enumerate(email_ready_records.items(), start=1):
                    status_panel.info(f"{index}/{total_targets}: Sending {user_id}")
                    progress_panel.progress(
                        index / max(total_targets, 1),
                        text=f"Sending emails: {index}/{total_targets}",
                    )
                    try:
                        response = send_email_with_attachment(
                            email=record["email"],
                            name=record.get("name", user_id),
                            file_name=record["file_name"],
                            file_bytes=Path(record["file_path"]).read_bytes(),
                        )
                        if response.status_code in (200, 201):
                            sent_count += 1
                            run_log.append(f"Sent: {user_id} ({record['email']})")
                        else:
                            failed_count += 1
                            run_log.append(f"Failed: {user_id} ({response.status_code})")
                    except Exception as e:
                        failed_count += 1
                        run_log.append(f"Failed: {user_id} ({e})")

                st.session_state.email_batch_log = run_log
                if sent_count:
                    st.success(f"Sent {sent_count} email(s) from {library['source_name']}.")
                if failed_count:
                    st.error(f"{failed_count} email(s) failed for {library['source_name']}.")
                status_panel.success(
                    f"Completed email run for {library['source_name']}: {sent_count} sent, {failed_count} failed."
                )
                with log_panel.container():
                    st.markdown("**Recent Email Activity**")
                    for line in run_log[-10:]:
                        st.write(f"- {line}")
            except Exception as e:
                st.error(f"Bulk email failed for {library['source_name']}: {e}")


def render_saved_library_bulk_certificate_panel(report_type, key_prefix):
    libraries = list_all_pdf_libraries(report_type=report_type)
    if not libraries:
        st.info("No generated certificate libraries are available for bulk send yet.")
        return

    progress_panel = st.empty()
    status_panel = st.empty()
    log_panel = st.empty()

    for library in libraries:
        email_ready_records = {
            user_id: record
            for user_id, record in library["records"].items()
            if record.get("email") and Path(record["file_path"]).exists()
        }
        card_col, action_col = st.columns([1.4, 1])
        with card_col:
            st.markdown(
                f"""
                <div class="explain-wrap" style="margin-bottom: 0.75rem;">
                    <div class="explain-sub">Saved Survey</div>
                    <div style="font-size:1rem; color:#0f172a; font-weight:700;">{library['source_name']}</div>
                    <div style="font-size:0.9rem; color:#64748b; margin-top:0.35rem;">Generated certificates: {len(library['records'])}</div>
                    <div style="font-size:0.85rem; color:#64748b; margin-top:0.25rem;">Email-ready certificates: {len(email_ready_records)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with action_col:
            send_bulk_for_library = st.button(
                "Send Bulk Certificates",
                use_container_width=True,
                disabled=not email_ready_records,
                key=f"{key_prefix}_bulk_certificate_{library['library_key']}",
            )

        if send_bulk_for_library:
            try:
                from send_pending_reports import send_certificate_email_with_attachment

                sent_count = 0
                failed_count = 0
                run_log = []
                total_targets = len(email_ready_records)

                for index, (user_id, record) in enumerate(email_ready_records.items(), start=1):
                    status_panel.info(f"{index}/{total_targets}: Sending certificate to {user_id}")
                    progress_panel.progress(
                        index / max(total_targets, 1),
                        text=f"Sending certificates: {index}/{total_targets}",
                    )
                    try:
                        response = send_certificate_email_with_attachment(
                            email=record["email"],
                            name=record.get("name", user_id),
                            file_name=record["file_name"],
                            file_bytes=Path(record["file_path"]).read_bytes(),
                            event_date=record.get("event_date", ""),
                        )
                        if response.status_code in (200, 201):
                            sent_count += 1
                            run_log.append(f"Sent: {user_id} ({record['email']})")
                        else:
                            failed_count += 1
                            run_log.append(f"Failed: {user_id} ({response.status_code})")
                    except Exception as e:
                        failed_count += 1
                        run_log.append(f"Failed: {user_id} ({e})")

                if sent_count:
                    st.success(f"Sent {sent_count} certificate email(s) from {library['source_name']}.")
                if failed_count:
                    st.error(f"{failed_count} certificate email(s) failed for {library['source_name']}.")
                status_panel.success(
                    f"Completed certificate run for {library['source_name']}: {sent_count} sent, {failed_count} failed."
                )
                with log_panel.container():
                    st.markdown("**Recent Certificate Activity**")
                    for line in run_log[-10:]:
                        st.write(f"- {line}")
            except Exception as e:
                st.error(f"Bulk certificate send failed for {library['source_name']}: {e}")


PRE_ASSESSMENT_KEY = {
    "Mental health is best understood as:": "emotional, social, and psychological well-being",
    "Which is a common source of stress for students today?": "academic demands, peer pressure, and family expectations",
    "Which is the clearest early warning sign a teacher may observe?": "showing sudden withdrawal over several days",
    "A student who is usually cheerful has become quiet, avoids friends, and has stopped submitting work. What should the teacher do first?": "watch the pattern and speak privately",
    "Which classroom practice is most likely to improve emotional safety?": "using respectful language and encouragement",
    "Before a test, a student says, \"I know I will not do well.\" What is the most helpful immediate teacher response?": "guide the student to begin with familiar questions",
    "Which approach is most appropriate while talking to parents about a concern?": "sharing observations and inviting partnership",
    "Which action should a teacher avoid when concerned about a student?": "deciding on a diagnosis from classroom signs",
    "Which assessment practice is most likely to reduce student stress?": "offering clear success criteria in advance",
    "One student is irritable, one is withdrawn, and one frequently reports headaches before tests. What is the best interpretation?": "they are showing possible signs of stress",
    "A teacher notices repeated emotional distress even after classroom support. What is the best next step?": "move the concern through school support channels",
    "Which statement best reflects a mentally healthy school culture?": "academic progress depends on emotional safety",
}

POST_ASSESSMENT_KEY = {
    "Good mental health in students is best reflected when they:": "manage emotions and function reasonably well",
    "Which description best matches burnout?": "exhaustion, detachment, and reduced motivation",
    "Which factor is most closely linked to healthy student development in school?": "consistent adult support and connection",
    "A student who usually participates well has stopped answering and avoids eye contact. What is the most appropriate first response?": "observe carefully and check in privately",
    "Which classroom practice best supports student emotional safety?": "acknowledging effort in a respectful way",
    "A teacher wants to speak to parents about a student's recent change in behaviour. Which opening is best?": "We have noticed some changes and want to support together.",
    "Which is the best example of a healthy teacher response to student stress?": "acknowledging the feeling and offering calm guidance",
    "Which assessment practice best supports student well-being?": "giving clear criteria and calm instructions",
    "A teacher notices one student becomes restless before tests, one becomes silent during group work, and one often says, \"I cannot do this.\" What is the best next move?": "respond to each pattern with appropriate support",
    "A school wants to become more mentally healthy. Which change is likely to have the strongest everyday effect?": "combining supportive teaching with referral systems",
    "A teacher has supported a student in class, checked in privately, and still sees persistent distress. What should the teacher conclude?": "the concern may need referral support",
    "Which statement best reflects the spirit of the workshop?": "teachers support mental health through daily practice",
}


PRE_QUESTION_LABELS = build_question_short_labels(PRE_ASSESSMENT_KEY)
POST_QUESTION_LABELS = build_question_short_labels(POST_ASSESSMENT_KEY)


def normalize_string(s):
    return re.sub(r"[^a-zA-Z0-9]", "", str(s)).lower()


def get_matched_column(df, question):
    q_clean = normalize_string(question)[:25]
    for col in df.columns:
        if q_clean in normalize_string(col):
            return col
    return None


@st.cache_data(ttl=300)
def fetch_google_sheet_data(url):
    try:
        if "export?format=csv" not in url:
            match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
            if match:
                doc_id = match.group(1)
                url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv"
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        return pd.read_csv(io.StringIO(response.text))
    except Exception as e:
        st.error(f"Failed to fetch data from Google Sheets: {e}")
        return None


def filter_out_unicode_responses(df):
    if df is None or df.empty:
        return df
    filtered = df.copy()

    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2026": "...",
        "\u00a0": " ",
    }

    def normalize_cell(value):
        if pd.isna(value) or not isinstance(value, str):
            return value
        normalized = value
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)
        normalized = normalized.encode("ascii", "ignore").decode("ascii")
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    for idx in range(filtered.shape[1]):
        series = filtered.iloc[:, idx]
        if series.dtype == object:
            filtered.iloc[:, idx] = series.apply(normalize_cell)

    return filtered


@st.cache_data(ttl=3600, show_spinner=False)
def build_dynamic_answer_mapping(df, base_answer_key, current_api_key):
    if genai is None or not current_api_key:
        return {question: [concept] for question, concept in base_answer_key.items()}

    client = genai.Client(api_key=current_api_key)
    dynamic_key = {}
    payload_to_grade = {}

    for question, correct_concept in base_answer_key.items():
        matched_col = get_matched_column(df, question)
        if not matched_col:
            dynamic_key[question] = [correct_concept]
            continue
        unique_responses = []
        for val in df[matched_col].dropna().astype(str):
            for v in val.split(","):
                candidate = v.strip()
                if candidate and candidate not in unique_responses:
                    unique_responses.append(candidate)
        payload_to_grade[question] = {
            "correct_concept": correct_concept,
            "user_responses": unique_responses,
        }

    prompt = (
        "You are a survey grading assistant. For each question, identify which user responses "
        "mean the same thing as the correct concept. Return raw JSON only.\n\n"
        f"{json.dumps(payload_to_grade, ensure_ascii=False)}"
    )

    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        text = response.text.strip()
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)
        approved_answers_dict = json.loads(text)
        for question, correct_concept in base_answer_key.items():
            approved = approved_answers_dict.get(question, [])
            dynamic_key[question] = [correct_concept] + (approved if isinstance(approved, list) else [])
    except Exception:
        for question, correct_concept in base_answer_key.items():
            dynamic_key.setdefault(question, [correct_concept])

    return dynamic_key


def apply_grid(fig):
    fig.update_layout(
        plot_bgcolor="white",
        xaxis=dict(showgrid=True, gridwidth=1, gridcolor="LightGray", zeroline=True, zerolinecolor="LightGray"),
        yaxis=dict(showgrid=True, gridwidth=1, gridcolor="LightGray", zeroline=True, zerolinecolor="LightGray"),
    )
    return fig


def get_question_metrics(df, dynamic_answer_key, base_answer_key):
    metrics = []
    total_responses = len(df)
    for i, (question, correct_answers) in enumerate(dynamic_answer_key.items()):
        matched_col = get_matched_column(df, question)
        accuracy = 0
        hover_str = f"<b>{question}</b><br><br><b>Target Concept:</b> <span style='color:#2ca02c;'>{base_answer_key.get(question, 'N/A')}</span>"
        if matched_col:
            correct_count = df[matched_col].astype(str).apply(
                lambda x: 1 if any(ans.lower() in x.lower() for ans in correct_answers) else 0
            ).sum()
            accuracy = (correct_count / total_responses) * 100 if total_responses > 0 else 0
        metrics.append(
            {
                "Question": question,
                "Question_Short": f"Q{i+1}",
                "Accuracy (%)": accuracy,
                "Hover_Data": hover_str,
            }
        )
    return pd.DataFrame(metrics)


def get_participant_scores(df, dynamic_answer_key):
    scores = []
    for _, row in df.iterrows():
        correct = 0
        for question, correct_answers in dynamic_answer_key.items():
            matched_col = get_matched_column(df, question)
            if matched_col and pd.notna(row[matched_col]):
                if any(ans.lower() in str(row[matched_col]).lower() for ans in correct_answers):
                    correct += 1
        scores.append(correct)
    return scores


def generate_graded_dataframe(df, dynamic_answer_key):
    graded_data = []
    for index, row in df.iterrows():
        participant_data = {"Participant_ID": f"Participant {index + 1}"}
        total_score = 0
        for i, (question, correct_answers) in enumerate(dynamic_answer_key.items()):
            q_short = f"Q{i+1}"
            matched_col = get_matched_column(df, question)
            is_correct = 0
            if matched_col and pd.notna(row[matched_col]):
                if any(ans.lower() in str(row[matched_col]).lower() for ans in correct_answers):
                    is_correct = 1
            participant_data[q_short] = is_correct
            total_score += is_correct
        participant_data["Total_Score"] = total_score
        graded_data.append(participant_data)
    return pd.DataFrame(graded_data)


def normalize_phone(value):
    if pd.isna(value):
        return ""

    if isinstance(value, (int, np.integer)):
        digits = str(int(value))
    elif isinstance(value, (float, np.floating)):
        digits = str(int(value)) if float(value).is_integer() else re.sub(r"\D", "", format(value, "f"))
    else:
        raw = str(value or "").strip()
        raw = re.sub(r"\.0+$", "", raw)
        digits = re.sub(r"\D", "", raw)

    if len(digits) > 10:
        digits = digits[-10:]
    return digits


def find_phone_column(df):
    return find_column_name(
        df,
        [
            "phone",
            "phone number",
            "mobile",
            "mobile number",
            "contact number",
            "whatsapp number",
        ],
    )


def find_name_column_for_comparison(df):
    return find_column_name(df, ["name", "full name", "participant name", "teacher name"])


def generate_individual_graded_dataframe(df, dynamic_answer_key):
    graded_df = generate_graded_dataframe(df, dynamic_answer_key)
    phone_col = find_phone_column(df)
    name_col = find_name_column_for_comparison(df)

    graded_df["Phone"] = (
        df[phone_col].apply(normalize_phone) if phone_col is not None else pd.Series([""] * len(df))
    )
    graded_df["Name"] = (
        df[name_col].fillna("Participant").astype(str).str.strip()
        if name_col is not None
        else pd.Series([f"Participant {i + 1}" for i in range(len(df))])
    )
    return graded_df


def generate_gemini_insights(pre_data, post_data, current_api_key):
    if genai is None or not current_api_key:
        return "Gemini is not configured. Add `GEMINI_API_KEY` to use AI insights."

    client = genai.Client(api_key=current_api_key)
    prompt = """
You are a Senior AI Data Analyst evaluating a teacher mental health training program.
Generate a highly skimmable professional report using these exact markdown headers:

### Attendee-Facing Highlights (Public)
### Presenter Internal Record: Data Trajectory (Private)
### Deep Dive: Critical Knowledge Gaps (Private)
### Strategic Action Plan (Private)
"""
    if pre_data:
        prompt += f"\nPre-Webinar Accuracy:\n{pre_data}\n"
    if post_data:
        prompt += f"\nPost-Webinar Accuracy:\n{post_data}\n"
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return response.text
    except Exception as e:
        return f"Error generating insights: {e}"


def create_insights_pdf(report_text):
    if FPDF is None:
        replacements = {
            "\u2018": "'",
            "\u2019": "'",
            "\u201c": '"',
            "\u201d": '"',
            "\u2013": "-",
            "\u2014": "-",
            "\u2022": "-",
            "\t": " ",
        }
        clean_text = report_text
        for old, new in replacements.items():
            clean_text = clean_text.replace(old, new)

        sections = []
        current_title = ""
        current_items = []
        current_paragraphs = []

        def flush_section():
            if current_title or current_items or current_paragraphs:
                items_html = "".join(f"<li>{html.escape(item)}</li>" for item in current_items)
                paragraphs_html = "".join(f"<p>{html.escape(p)}</p>" for p in current_paragraphs)
                sections.append(
                    f"""
                    <section class="report-section">
                        {f'<h2>{html.escape(current_title)}</h2>' if current_title else ''}
                        {paragraphs_html}
                        {f'<ul>{items_html}</ul>' if items_html else ''}
                    </section>
                    """
                )

        for raw_line in clean_text.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            if not line:
                continue
            if line.startswith("### "):
                flush_section()
                current_title = line.replace("### ", "", 1).strip()
                current_items = []
                current_paragraphs = []
            elif line.startswith("- "):
                current_items.append(line[2:].strip())
            else:
                current_paragraphs.append(line)
        flush_section()

        body_html = "".join(sections) or "<p>Comparison report</p>"
        pdf_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: Helvetica, Arial, sans-serif;
                    color: #172033;
                    margin: 0;
                    padding: 38px 44px;
                    background: #ffffff;
                }}
                .report-shell {{
                    border: 1px solid #dbe3f0;
                    border-radius: 16px;
                    padding: 28px 30px;
                    background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
                }}
                .eyebrow {{
                    font-size: 11px;
                    letter-spacing: 0.24em;
                    text-transform: uppercase;
                    color: #6b7a90;
                    margin-bottom: 8px;
                    font-weight: 700;
                }}
                h1 {{
                    margin: 0 0 10px 0;
                    font-size: 28px;
                    line-height: 1.15;
                    color: #0f172a;
                }}
                .summary {{
                    color: #516176;
                    font-size: 13px;
                    line-height: 1.6;
                    margin-bottom: 22px;
                }}
                .report-section {{
                    margin-top: 20px;
                    padding-top: 16px;
                    border-top: 1px solid #e2e8f0;
                }}
                .report-section:first-of-type {{
                    border-top: none;
                    margin-top: 0;
                    padding-top: 0;
                }}
                h2 {{
                    margin: 0 0 10px 0;
                    font-size: 17px;
                    color: #1d4ed8;
                }}
                p {{
                    margin: 0 0 10px 0;
                    font-size: 12px;
                    line-height: 1.7;
                }}
                ul {{
                    margin: 10px 0 0 18px;
                    padding: 0;
                }}
                li {{
                    margin: 0 0 7px 0;
                    font-size: 12px;
                    line-height: 1.55;
                }}
            </style>
        </head>
        <body>
            <div class="report-shell">
                <div class="eyebrow">EDXSO Insights Report</div>
                <h1>Teacher Mental Health Training - Insights Report</h1>
                <div class="summary">This report summarizes the participant's pre/post comparison in a clean printable format.</div>
                {body_html}
            </div>
        </body>
        </html>
        """

        ensure_playwright_ready()
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--single-process"],
            )
            page = browser.new_page()
            page.set_content(pdf_html, wait_until="load")
            page.wait_for_timeout(300)
            pdf_bytes = page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "18px", "right": "18px", "bottom": "18px", "left": "18px"},
            )
            browser.close()
        return pdf_bytes
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, "Teacher Mental Health Training - Insights Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(10)
    replacements = {"**": "", "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-", "\u2022": "-", "*": "-", "\t": " "}
    clean_text = report_text
    for old, new in replacements.items():
        clean_text = clean_text.replace(old, new)
    clean_text = clean_text.encode("latin-1", "ignore").decode("latin-1")
    pdf.set_font("helvetica", "", 12)
    for line in clean_text.split("\n"):
        line = line.strip()
        if not line or set(line) <= {"-", "_", " "}:
            pdf.ln(4)
            continue
        if line.startswith("### "):
            pdf.ln(4)
            pdf.set_font("helvetica", "B", 14)
            pdf.write(10, line.replace("### ", "") + "\n")
            pdf.set_font("helvetica", "", 12)
        else:
            pdf.write(8, line + "\n")
    return bytes(pdf.output())


def generate_comparison_pdf_playwright(record):
    record_pre = record["pre_row"]
    record_post = record["post_row"]
    participant_name = record["name"]
    participant_phone = record["phone"]
    pre_score = int(record_pre["Total_Score"])
    post_score = int(record_post["Total_Score"])
    delta = post_score - pre_score

    question_rows = []
    for i in range(1, 13):
        question_rows.append(
            {
                "Question": f"Q{i}",
                "Pre": int(record_pre[f"Q{i}"]),
                "Post": int(record_post[f"Q{i}"]),
                "PreLabel": PRE_QUESTION_LABELS[i - 1]["text"],
                "PostLabel": POST_QUESTION_LABELS[i - 1]["text"],
            }
        )
    comparison_df = pd.DataFrame(question_rows)
    comparison_long = comparison_df.melt(
        id_vars="Question",
        value_vars=["Pre", "Post"],
        var_name="Survey",
        value_name="Correct",
    )

    fig_compare = px.bar(
        comparison_long,
        x="Question",
        y="Correct",
        color="Survey",
        barmode="group",
        color_discrete_map={"Pre": "#2563eb", "Post": "#059669"},
        title="Question-by-Question Comparison",
    )
    fig_compare.update_layout(
        height=250,
        margin=dict(l=10, r=10, t=42, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans", color="#334155", size=9),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1),
    )
    fig_compare.update_yaxes(range=[0, 1], tickvals=[0, 1], ticktext=["Incorrect", "Correct"])
    compare_chart_html = fig_to_html(fig_compare, 820, 240)
    plotly_js = get_plotlyjs()

    improved_count = 0
    declined_count = 0
    unchanged_count = 0
    detail_rows = ""
    for row in question_rows:
        change = row["Post"] - row["Pre"]
        if change > 0:
            movement_label = "Improved"
            movement_class = "up"
            improved_count += 1
        elif change < 0:
            movement_label = "Dropped"
            movement_class = "down"
            declined_count += 1
        else:
            movement_label = "Unchanged"
            movement_class = "flat"
            unchanged_count += 1

        pre_badge = "Correct" if row["Pre"] else "Incorrect"
        post_badge = "Correct" if row["Post"] else "Incorrect"
        detail_rows += f"""
        <tr>
            <td class="q-col">{row['Question']}</td>
            <td class="movement-col"><span class="movement-pill {movement_class}">{movement_label}</span></td>
            <td class="text-col">
                <div class="question-label">Pre Survey</div>
                <div class="question-copy">{html.escape(row['PreLabel'])}</div>
                <div class="status-wrap"><span class="detail-status {'ok' if row['Pre'] else 'miss'}">{pre_badge}</span></div>
            </td>
            <td class="text-col">
                <div class="question-label">Post Survey</div>
                <div class="question-copy">{html.escape(row['PostLabel'])}</div>
                <div class="status-wrap"><span class="detail-status {'ok' if row['Post'] else 'miss'}">{post_badge}</span></div>
            </td>
        </tr>
        """

    delta_label = "Improved overall" if delta > 0 else "No score change" if delta == 0 else "Needs reinforcement"
    delta_class = "delta-up" if delta > 0 else "delta-flat" if delta == 0 else "delta-down"
    score_fill = max(0, min(post_score / 12, 1)) * 100
    logo_uri = get_edxso_logo_data_uri()
    logo_html = f'<img class="logo-mark" src="{logo_uri}" alt="EDXSO logo">' if logo_uri else ""

    html_doc = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <script type="text/javascript">{plotly_js}</script>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                font-family: 'DM Sans', Helvetica, Arial, sans-serif;
                color: #172033;
                margin: 0;
                padding: 10px 12px;
                background: #ffffff;
            }}
            .shell {{
                border: 1px solid #d7e2f3;
                border-radius: 16px;
                padding: 14px 16px 16px;
                background: #ffffff;
            }}
            .eyebrow {{
                font-size: 9px;
                letter-spacing: 0.20em;
                text-transform: uppercase;
                color: #64748b;
                font-weight: 700;
                margin-bottom: 6px;
            }}
            .hero {{
                display: grid;
                grid-template-columns: 1.35fr 0.85fr;
                gap: 10px;
                align-items: stretch;
                margin-bottom: 10px;
                break-inside: avoid;
                page-break-inside: avoid;
            }}
            .hero-copy {{
                background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 70%, #3b82f6 100%);
                color: #ffffff;
                border-radius: 14px;
                padding: 12px 14px;
            }}
            .brand-row {{
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 8px;
            }}
            .logo-mark {{
                width: 32px;
                height: 32px;
                object-fit: contain;
                border-radius: 8px;
                background: rgba(255,255,255,0.12);
                padding: 3px;
            }}
            .brand-title {{
                font-size: 10px;
                letter-spacing: 0.12em;
                text-transform: uppercase;
                color: rgba(255,255,255,0.82);
                font-weight: 700;
            }}
            .brand-sub {{
                font-size: 9px;
                color: rgba(255,255,255,0.72);
            }}
            h1 {{
                margin: 0 0 5px 0;
                font-size: 24px;
                line-height: 1.08;
                color: #ffffff;
            }}
            .sub {{
                margin: 0 0 8px 0;
                color: rgba(255,255,255,0.82);
                font-size: 10px;
                line-height: 1.4;
            }}
            .identity-row {{
                display: flex;
                gap: 6px;
                flex-wrap: wrap;
            }}
            .identity-pill {{
                border: 1px solid rgba(255,255,255,0.18);
                background: rgba(255,255,255,0.08);
                border-radius: 999px;
                padding: 4px 8px;
                font-size: 9px;
                color: #ffffff;
            }}
            .hero-side {{
                border: 1px solid #dbe3f0;
                border-radius: 14px;
                padding: 10px;
                background: #f8fbff;
            }}
            .hero-side-label {{
                font-size: 9px;
                letter-spacing: 0.16em;
                text-transform: uppercase;
                color: #64748b;
                font-weight: 700;
                margin-bottom: 6px;
            }}
            .delta-number {{
                font-size: 30px;
                font-weight: 900;
                line-height: 1;
                color: #0f172a;
                margin-bottom: 3px;
            }}
            .delta-pill {{
                display: inline-block;
                border-radius: 999px;
                padding: 4px 8px;
                font-size: 8px;
                font-weight: 800;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                margin-bottom: 6px;
            }}
            .delta-up {{ background: #dcfce7; color: #166534; }}
            .delta-flat {{ background: #e2e8f0; color: #334155; }}
            .delta-down {{ background: #fee2e2; color: #991b1b; }}
            .score-line {{
                display: flex;
                justify-content: space-between;
                font-size: 9px;
                color: #475569;
                margin-bottom: 5px;
            }}
            .score-track {{
                height: 7px;
                border-radius: 999px;
                background: #dbeafe;
                overflow: hidden;
                margin-bottom: 5px;
            }}
            .score-fill {{
                height: 100%;
                width: {score_fill:.1f}%;
                background: linear-gradient(90deg, #2563eb 0%, #059669 100%);
            }}
            .card-grid {{
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 7px;
                margin-bottom: 10px;
                break-inside: avoid;
                page-break-inside: avoid;
            }}
            .card {{
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 8px;
                background: #ffffff;
            }}
            .card-label {{
                font-size: 8px;
                letter-spacing: 0.18em;
                text-transform: uppercase;
                color: #64748b;
                margin-bottom: 4px;
                font-weight: 700;
            }}
            .card-value {{
                font-size: 20px;
                font-weight: 800;
                color: #0f172a;
                line-height: 1.05;
            }}
            .card-note {{
                margin-top: 4px;
                color: #64748b;
                font-size: 8px;
                line-height: 1.3;
            }}
            .section {{
                margin-top: 10px;
                padding-top: 7px;
                border-top: 1px solid #e2e8f0;
            }}
            .section h2 {{
                margin: 0 0 6px 0;
                font-size: 14px;
                color: #0f172a;
            }}
            .section-intro {{
                color: #475569;
                font-size: 9px;
                line-height: 1.35;
                margin-bottom: 6px;
            }}
            .movement-grid {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 7px;
                break-inside: avoid;
                page-break-inside: avoid;
            }}
            .movement-card {{
                border: 1px solid #e2e8f0;
                border-radius: 10px;
                padding: 8px;
                background: #ffffff;
            }}
            .movement-number {{
                font-size: 20px;
                font-weight: 900;
                color: #0f172a;
                line-height: 1;
                margin-bottom: 2px;
            }}
            .movement-label {{
                font-size: 8px;
                letter-spacing: 0.16em;
                text-transform: uppercase;
                color: #64748b;
                font-weight: 700;
                margin-bottom: 4px;
            }}
            .movement-desc {{
                font-size: 8px;
                line-height: 1.3;
                color: #475569;
            }}
            .detail-table {{
                width: 100%;
                border-collapse: separate;
                border-spacing: 0;
                table-layout: fixed;
                border: 1px solid #dbe3f0;
                border-radius: 10px;
                overflow: hidden;
            }}
            .detail-table thead th {{
                background: #f8fbff;
                color: #64748b;
                font-size: 8px;
                letter-spacing: 0.18em;
                text-transform: uppercase;
                font-weight: 800;
                padding: 6px 7px;
                border-bottom: 1px solid #dbe3f0;
                text-align: left;
            }}
            .detail-table tbody tr {{
                break-inside: avoid;
                page-break-inside: avoid;
            }}
            .detail-table tbody td {{
                border-bottom: 1px solid #e2e8f0;
                vertical-align: top;
                padding: 7px;
                background: #ffffff;
            }}
            .detail-table tbody tr:nth-child(even) td {{
                background: #fbfdff;
            }}
            .detail-table tbody tr:last-child td {{
                border-bottom: none;
            }}
            .q-col {{
                width: 7%;
                font-size: 11px;
                font-weight: 800;
                color: #0f172a;
            }}
            .movement-col {{
                width: 15%;
            }}
            .text-col {{
                width: 39%;
            }}
            .question-label {{
                font-size: 7px;
                letter-spacing: 0.14em;
                text-transform: uppercase;
                color: #64748b;
                font-weight: 700;
                margin-bottom: 3px;
            }}
            .question-copy {{
                font-size: 8px;
                color: #334155;
                line-height: 1.25;
                margin-bottom: 5px;
            }}
            .movement-pill {{
                display: inline-block;
                border-radius: 999px;
                padding: 3px 7px;
                font-size: 8px;
                font-weight: 800;
                letter-spacing: 0.06em;
                text-transform: uppercase;
            }}
            .movement-pill.up {{ background: #dcfce7; color: #166534; }}
            .movement-pill.flat {{ background: #e2e8f0; color: #334155; }}
            .movement-pill.down {{ background: #fee2e2; color: #991b1b; }}
            .detail-status {{
                display: inline-block;
                border-radius: 999px;
                padding: 3px 7px;
                font-size: 7px;
                font-weight: 800;
                letter-spacing: 0.04em;
                text-transform: uppercase;
            }}
            .detail-status.ok {{ background: #dcfce7; color: #166534; }}
            .detail-status.miss {{ background: #fee2e2; color: #991b1b; }}
            @page {{ margin: 8px; }}
            @media print {{
                .hero, .card-grid, .movement-grid, .section, .detail-table, .detail-table tr, .detail-table td {{
                    break-inside: avoid;
                    page-break-inside: avoid;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="shell">
            <div class="eyebrow">EDXSO Comparison Report</div>
            <div class="hero">
                <div class="hero-copy">
                    <div class="brand-row">
                        {logo_html}
                        <div>
                            <div class="brand-title">EDXSO Strategic Intelligence</div>
                            <div class="brand-sub">Pre/Post participant comparison report</div>
                        </div>
                    </div>
                    <h1>{html.escape(participant_name)}</h1>
                    <p class="sub">A compact participant-level comparison showing score movement, question-level shifts, and areas that may need reinforcement.</p>
                    <div class="identity-row">
                        <div class="identity-pill">Phone {html.escape(participant_phone)}</div>
                        <div class="identity-pill">Pre {pre_score}/12</div>
                        <div class="identity-pill">Post {post_score}/12</div>
                    </div>
                </div>
                <div class="hero-side">
                    <div class="hero-side-label">Overall Movement</div>
                    <div class="delta-number">{delta:+d}</div>
                    <div class="delta-pill {delta_class}">{delta_label}</div>
                    <div class="score-line">
                        <span>Post score strength</span>
                        <strong>{post_score}/12</strong>
                    </div>
                    <div class="score-track"><div class="score-fill"></div></div>
                    <div class="card-note">Final post-assessment score as a share of the full 12-point scale.</div>
                </div>
            </div>

            <div class="card-grid">
                <div class="card">
                    <div class="card-label">Phone</div>
                    <div class="card-value">{html.escape(participant_phone)}</div>
                    <div class="card-note">Matched across both uploaded survey files.</div>
                </div>
                <div class="card">
                    <div class="card-label">Pre Score</div>
                    <div class="card-value">{pre_score}/12</div>
                    <div class="card-note">Correct responses before the session.</div>
                </div>
                <div class="card">
                    <div class="card-label">Post Score</div>
                    <div class="card-value">{post_score}/12</div>
                    <div class="card-note">Correct responses after the session.</div>
                </div>
                <div class="card">
                    <div class="card-label">Improvement</div>
                    <div class="card-value">{delta:+d}</div>
                    <div class="card-note">Net score movement for this participant.</div>
                </div>
            </div>

            <div class="section">
                <h2>Performance Snapshot</h2>
                <div class="section-intro">A quick summary of how the participant moved between the pre and post assessments.</div>
                <div class="movement-grid">
                    <div class="movement-card">
                        <div class="movement-label">Improved Questions</div>
                        <div class="movement-number">{improved_count}</div>
                        <div class="movement-desc">Incorrect in pre, correct in post.</div>
                    </div>
                    <div class="movement-card">
                        <div class="movement-label">Unchanged Questions</div>
                        <div class="movement-number">{unchanged_count}</div>
                        <div class="movement-desc">Stayed consistent across both surveys.</div>
                    </div>
                    <div class="movement-card">
                        <div class="movement-label">Dropped Questions</div>
                        <div class="movement-number">{declined_count}</div>
                        <div class="movement-desc">Lower post result than pre.</div>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2>Question Movement Chart</h2>
                <div class="section-intro">Shared question indices are compared here as correct versus incorrect status across the two surveys.</div>
                {compare_chart_html}
            </div>

            <div class="section">
                <h2>Detailed Comparison Notes</h2>
                <div class="section-intro">Each row compares the aligned pre and post prompts plus the participant's correct or incorrect status.</div>
                <table class="detail-table">
                    <thead>
                        <tr>
                            <th>Q</th>
                            <th>Movement</th>
                            <th>Pre Survey</th>
                            <th>Post Survey</th>
                        </tr>
                    </thead>
                    <tbody>
                        {detail_rows}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """

    ensure_playwright_ready()
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--single-process"],
        )
        page = browser.new_page()
        page.set_content(html_doc, wait_until="load")
        page.wait_for_timeout(400)
        pdf_bytes = page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "18px", "right": "18px", "bottom": "18px", "left": "18px"},
        )
        browser.close()
    return pdf_bytes


def generate_assessment_pdf_playwright(record, survey_title, question_metrics_df, participant_scores, base_answer_key):
    total_score = int(record["Total_Score"])
    total_questions = 12
    percent_score = round((total_score / total_questions) * 100, 1)
    clean_participants = len(participant_scores)
    avg_score = round(sum(participant_scores) / clean_participants, 1) if clean_participants else 0
    highest_score = max(participant_scores) if participant_scores else 0
    survey_prefix = "Pre-Webinar" if "Pre" in survey_title else "Post-Webinar"
    chart_title = f"{survey_prefix}: Accuracy per Question"
    chart_subtitle = "Pre-Webinar Baseline" if "Pre" in survey_title else "Post-Webinar Results"

    if percent_score >= 85:
        label, badge_cls, desc = "High Readiness", "badge-benchmark", "Strong demonstrated understanding across the assessment."
    elif percent_score >= 65:
        label, badge_cls, desc = "Developing Readiness", "badge-strong", "Solid understanding with a few concepts still needing reinforcement."
    elif percent_score >= 45:
        label, badge_cls, desc = "Emerging Readiness", "badge-efficient", "Partial understanding is visible, but more support is still needed."
    else:
        label, badge_cls, desc = "Foundational Support Needed", "badge-fragile", "The participant may benefit from more targeted follow-up and revision."

    question_rows = []
    detail_rows = ""
    for i in range(1, total_questions + 1):
        prompt = record.get(f"QuestionText{i}", f"Question {i}")
        accuracy_row = question_metrics_df.iloc[i - 1] if i - 1 < len(question_metrics_df) else None
        accuracy_score = float(accuracy_row["Accuracy (%)"]) if accuracy_row is not None else 0.0
        is_correct = bool(int(record[f"Q{i}"]))
        status = "Correct" if is_correct else "Incorrect"
        status_class = "ok" if is_correct else "miss"
        correct_option = base_answer_key.get(prompt, "")
        question_rows.append({"Question": f"Q{i}", "Accuracy (%)": accuracy_score})
        detail_rows += f"""
        <tr>
            <td class="q-col">Q{i}</td>
            <td>{html.escape(prompt)}</td>
            <td class="status-col"><span class="status-pill {status_class}">{status}</span></td>
            <td class="correct-option-col">{html.escape(correct_option) if not is_correct else "-"}</td>
        </tr>
        """

    question_df = pd.DataFrame(question_rows)
    fig_question = px.bar(
        question_df,
        x="Question",
        y="Accuracy (%)",
        title="",
    )
    fig_question.update_layout(
        height=360,
        margin=dict(l=96, r=24, t=12, b=72),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans", color="#334155", size=12),
        showlegend=False,
        bargap=0.18,
    )
    fig_question.update_traces(
        marker_color="#4e79a7",
        marker_line_color="#1f2937",
        marker_line_width=1,
        hovertemplate="Question %{x}<br>Correct responses: %{y:.1f}%<extra></extra>",
    )
    fig_question.update_yaxes(
        range=[0, 100],
        title="Accuracy (%)",
        title_standoff=18,
        tickfont=dict(size=12),
        tickvals=[0, 20, 40, 60, 80, 100],
        showticklabels=True,
        automargin=True,
        gridcolor="rgba(148,163,184,0.18)",
        zeroline=False,
    )
    fig_question.update_xaxes(
        title="Questions",
        title_standoff=14,
        tickfont=dict(size=12),
        tickmode="array",
        tickvals=question_df["Question"].tolist(),
        ticktext=question_df["Question"].tolist(),
        showticklabels=True,
        automargin=True,
    )
    question_chart_html = fig_to_html(fig_question, 1100, 360)
    plotly_js = get_plotlyjs()

    pdf_css = CUSTOM_CSS.replace(
        "@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');",
        "",
    )
    logo_uri = get_edxso_logo_data_uri()
    logo_html = f'<img class="brand-logo" src="{logo_uri}" alt="EDXSO logo">' if logo_uri else ""

    score_explainer = f"""
    <div class="explain-wrap">
        <div class="explain-head">Participant Overview</div>
        <div class="explain-sub">{html.escape(survey_title)}</div>
        <div class="explain-grid">
            <div class="explain-card exp-rel">
                <h4>Clean Data Participants</h4>
                <ul>
                    <li>{clean_participants} usable participant records included.</li>
                    <li>The uploaded survey is summarized cohort-wide for benchmarking.</li>
                    <li>This participant scored {total_score}/{total_questions}.</li>
                </ul>
            </div>
            <div class="explain-card exp-reli">
                <h4>Average Score</h4>
                <ul>
                    <li>Cohort average: {avg_score:.1f} / {total_questions}.</li>
                    <li>Use this as the baseline for comparing individual performance.</li>
                    <li>Higher averages indicate stronger overall readiness.</li>
                </ul>
            </div>
            <div class="explain-card exp-repu">
                <h4>Highest Score</h4>
                <ul>
                    <li>Top cohort score: {highest_score} / {total_questions}.</li>
                    <li>Shows the current best observed outcome in the uploaded file.</li>
                    <li>Useful for understanding score spread and ceiling performance.</li>
                </ul>
            </div>
            <div class="explain-card exp-repu">
                <h4>Interpretation</h4>
                <ul>
                    <li>{html.escape(desc)}</li>
                    <li>Use the accuracy chart below to identify stronger and weaker question areas.</li>
                    <li>The table below restores per-question correctness and adds the correct option detail wherever the answer was incorrect.</li>
                </ul>
            </div>
        </div>
    </div>
    """

    pdf_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <script type="text/javascript">{plotly_js}</script>
        <style>
            {pdf_css}
            html, body {{ margin: 0 !important; padding: 0 !important; background: #ffffff; }}
            .pdf-container {{ padding: 50px; width: 100%; box-sizing: border-box; }}
            * {{ page-break-inside: avoid !important; page-break-before: auto !important; page-break-after: auto !important; }}
            .brand-row {{ display:flex; align-items:center; gap:12px; margin-bottom: 14px; }}
            .brand-logo {{
                width: 52px;
                height: 52px;
                object-fit: contain;
                border-radius: 12px;
                background: #f8fbff;
                border: 1px solid #dbe3f0;
                padding: 6px;
            }}
            .brand-copy {{ display:flex; flex-direction:column; gap:3px; }}
            .brand-name {{
                font-family: 'DM Mono', monospace;
                font-size: 0.68rem;
                color: #64748b;
                letter-spacing: 0.18em;
                text-transform: uppercase;
            }}
            .brand-tagline {{
                font-family: 'DM Sans', sans-serif;
                font-size: 0.92rem;
                color: #0f172a;
                font-weight: 600;
            }}
            .hero-score {{
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                padding: 18px 20px;
                margin-bottom: 24px;
            }}
            .hero-score .kpi-label {{ margin-bottom: 0.4rem; }}
            .hero-score .kpi-value {{ font-size: 4.4rem; }}
            .chart-section {{
                margin-top: 26px;
                margin-bottom: 28px;
                border-top: 1px solid #e5e7eb;
                padding-top: 22px;
            }}
            .chart-heading {{
                font-family: 'DM Sans', sans-serif;
                font-size: 18px;
                font-weight: 800;
                color: #1f2937;
                margin-bottom: 8px;
            }}
            .chart-subheading {{
                font-family: 'DM Sans', sans-serif;
                font-size: 13px;
                font-weight: 700;
                color: #374151;
                margin-bottom: 12px;
            }}
            .chart-col {{ display: block; border: none; border-radius: 0; padding: 0; overflow: visible; }}
            .detail-table {{ width: 100%; border-collapse: separate; border-spacing: 0; table-layout: fixed; border: 1px solid #dbe3f0; border-radius: 10px; overflow: hidden; }}
            .detail-table thead th {{ background: #f8fbff; color: #64748b; font-size: 0.65rem; letter-spacing: 0.14em; text-transform: uppercase; font-weight: 800; text-align: left; padding: 10px 12px; border-bottom: 1px solid #dbe3f0; }}
            .detail-table tbody td {{ padding: 10px 12px; border-bottom: 1px solid #e2e8f0; vertical-align: top; font-size: 0.82rem; line-height: 1.35; color:#334155; }}
            .detail-table tbody tr:last-child td {{ border-bottom: none; }}
            .q-col {{ width: 10%; font-weight: 800; color:#0f172a; }}
            .status-col {{ width: 16%; }}
            .correct-option-col {{ width: 26%; color:#475569; }}
            .status-pill {{ display: inline-block; border-radius: 999px; padding: 4px 9px; font-size: 0.68rem; letter-spacing: 0.04em; text-transform: uppercase; font-weight: 800; }}
            .status-pill.ok {{ background: #dcfce7; color: #166534; }}
            .status-pill.miss {{ background: #fee2e2; color: #991b1b; }}
        </style>
    </head>
    <body>
        <div class="pdf-container">
            <div class="brand-row">
                {logo_html}
                <div class="brand-copy">
                    <div class="brand-name">EDXSO Strategic Intelligence</div>
                    <div class="brand-tagline">Assessment Readiness Report</div>
                </div>
            </div>
            <div class="sub-title" style="font-family: 'DM Mono', monospace; font-size: 0.75rem; color: #64748b; letter-spacing: 0.2em; text-transform: uppercase;">Your Strategic Report</div>
            <h1 style="margin-top: 5px; margin-bottom: 15px;">{html.escape(record['Display_Name'])}</h1>

            <div class="status-row" style="margin-bottom: 35px;">
                <span class="status-badge {badge_cls}">{label}</span>
                <span class="badge-desc">{html.escape(desc)}</span>
            </div>

            <div class="hero-score">
                <div class="kpi-label">Assessment Score</div>
                <div class="kpi-value growth">{total_score}/{total_questions}</div>
            </div>

            <div class="section-header">
                <span class="section-number">01</span><span class="section-title">Assessment Highlights</span>
            </div>
            <div style="margin-top: 18px; margin-bottom: 28px;">{score_explainer}</div>

            <div class="chart-section">
                <div class="chart-heading">{chart_title}</div>
                <div class="chart-subheading">{chart_subtitle}</div>
                <div class="chart-col">
                    {question_chart_html}
                </div>
            </div>

            <div class="section-header">
                <span class="section-number">02</span><span class="section-title">Question Accuracy Review</span>
            </div>
            <div style="margin-top: 18px;">
                <table class="detail-table">
                    <thead><tr><th>Q</th><th>Question</th><th>Status</th><th>Correct Option</th></tr></thead>
                    <tbody>{detail_rows}</tbody>
                </table>
            </div>

            <div style="margin-top: 50px; text-align: center; font-family: 'DM Mono', monospace; font-size: 10px; color: #94a3b8; text-transform: uppercase; border-top: 1px solid #e2e8f0; padding-top: 20px;">
                R-Cube Strategic Intelligence · Edxso Analytics · Confidential Report
            </div>
        </div>
    </body>
    </html>
    """

    ensure_playwright_ready()
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--single-process"]
        )
        context = browser.new_context()
        page = context.new_page()
        page.set_content(pdf_html, wait_until="load")
        page.wait_for_timeout(1200)
        exact_height = page.evaluate("document.documentElement.scrollHeight")
        adjusted_height = exact_height + 40
        pdf_bytes = page.pdf(
            width="1100px",
            height=f"{adjusted_height}px",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"}
        )
        browser.close()
    return pdf_bytes


def render_comparison_report():
    api_key = os.getenv("GEMINI_API_KEY")
    load_attempted = st.session_state.get("comparison_load_attempted", False)
    render_panel_header(
        "Comparison Report",
        "Pre/Post Individual Comparison",
        "Upload the pre and post survey CSVs, match individuals by phone number, and generate a comparison report for one person at a time.",
    )

    with st.sidebar:
        st.markdown("---")
        st.markdown("`Comparison Inputs`")
        pre_file = st.file_uploader(
            "Upload Pre Survey CSV",
            type=["csv"],
            key="comparison_pre_csv",
        )
        post_file = st.file_uploader(
            "Upload Post Survey CSV",
            type=["csv"],
            key="comparison_post_csv",
        )
        generate_comparison_report = st.button(
            "Load Comparison Data",
            type="primary",
            use_container_width=True,
        )
        st.markdown("---")
        st.markdown("`Comparison Status`")
        st.caption(f"Gemini: {'Configured' if api_key else 'Missing'}")
        st.caption(f"Pre CSV: {'Uploaded' if pre_file is not None else 'Waiting'}")
        st.caption(f"Post CSV: {'Uploaded' if post_file is not None else 'Waiting'}")

    if generate_comparison_report:
        st.session_state["comparison_load_attempted"] = True
        st.session_state["comparison_process_clicked"] = True

    if not pre_file and not post_file:
        st.session_state.current_library_key = None
        st.session_state.generated_pdfs = {}
        report_tab, pdf_tab, email_tab = st.tabs(["Report", "PDF Library", "Email Delivery"])
        with report_tab:
            render_info_card(
                "How This Works",
                "Upload both pre and post survey CSVs to unlock the individual comparison report view and generate new comparison PDFs.",
            )
        with pdf_tab:
            render_info_card(
                "Saved Reports",
                "Previously generated comparison PDFs stay visible here even when no CSVs are uploaded. Upload the pre/post files only when you want to generate new comparison reports.",
            )
            library_panel = st.empty()
            render_generated_pdf_library(library_panel, report_type="comparison")
        with email_tab:
            render_info_card(
                "Email Delivery",
                "You can bulk-send from any saved comparison survey library below, even without uploading new pre/post CSVs. Upload files only when you want to generate fresh comparison reports.",
            )
            render_saved_library_bulk_email_panel("comparison", "comparison_saved")
        if load_attempted:
            st.warning("Upload both pre and post survey CSV files, then click `Load Comparison Data` again.")
        return

    if not st.session_state.get("comparison_process_clicked", False):
        render_info_card(
            "How This Works",
            "Use the sidebar to upload both CSV files. Once both are loaded, the app will match rows using the <b>phone</b> column and let you choose an individual comparison report.",
        )
        if pre_file is not None or post_file is not None:
            st.info("Both files are ready to be processed. Click `Load Comparison Data` in the sidebar to build the comparison workspace.")
        return

    pre_df = post_df = None
    pre_raw_count = post_raw_count = 0

    with st.spinner("Reading uploaded CSV files..."):
        if pre_file is not None:
            pre_source_df = pd.read_csv(io.BytesIO(pre_file.getvalue()))
            pre_raw_count = len(pre_source_df)
            pre_df = filter_out_unicode_responses(pre_source_df)
        if post_file is not None:
            post_source_df = pd.read_csv(io.BytesIO(post_file.getvalue()))
            post_raw_count = len(post_source_df)
            post_df = filter_out_unicode_responses(post_source_df)

    status_col1, status_col2 = st.columns(2)
    with status_col1:
        st.caption(
            f"Pre CSV rows: raw {pre_raw_count}, usable {0 if pre_df is None else len(pre_df)}"
        )
    with status_col2:
        st.caption(
            f"Post CSV rows: raw {post_raw_count}, usable {0 if post_df is None else len(post_df)}"
        )

    if pre_file is None or post_file is None:
        st.warning("Upload both pre and post CSV files to generate an individual comparison report.")
        return

    if pre_df is None or pre_df.empty:
        st.warning("The uploaded pre CSV has no usable rows after cleaning.")
        return

    if post_df is None or post_df.empty:
        st.warning("The uploaded post CSV has no usable rows after cleaning.")
        return

    comparison_source_name = f"Comparison · {pre_file.name} vs {post_file.name}"
    comparison_library_key = build_library_key(
        f"{pre_file.name}__{post_file.name}",
        pre_file.getvalue() + b"::" + post_file.getvalue(),
    )
    persist_library_meta(comparison_library_key, comparison_source_name, report_type="comparison")
    if st.session_state.get("current_library_key") != comparison_library_key:
        st.session_state.current_library_key = comparison_library_key
        st.session_state.generated_pdfs = load_generated_pdf_library(comparison_library_key)
        st.session_state.pdf_batch_log = []
        st.session_state.email_batch_log = []
        st.session_state.pdf_progress = {"current": 0, "total": 0, "message": "", "active": False}

    with st.spinner("Analyzing pre and post survey responses..."):
        dynamic_pre_key = build_dynamic_answer_mapping(pre_df, PRE_ASSESSMENT_KEY, api_key)
        dynamic_post_key = build_dynamic_answer_mapping(post_df, POST_ASSESSMENT_KEY, api_key)
        pre_graded_df = generate_individual_graded_dataframe(pre_df, dynamic_pre_key)
        post_graded_df = generate_individual_graded_dataframe(post_df, dynamic_post_key)

    pre_phone_col = find_phone_column(pre_df)
    post_phone_col = find_phone_column(post_df)
    pre_phone_set = {
        phone for phone in pre_graded_df["Phone"].tolist() if phone
    }
    post_phone_set = {
        phone for phone in post_graded_df["Phone"].tolist() if phone
    }

    matched_phones = sorted(
        {
            phone
            for phone in pre_graded_df["Phone"].tolist()
            if phone and phone in post_phone_set
        }
    )

    if not matched_phones:
        st.error("No matching individuals were found between pre and post CSVs using phone number.")
        debug_col1, debug_col2 = st.columns(2)
        with debug_col1:
            st.caption(f"Detected pre phone column: {pre_phone_col or 'Not found'}")
            st.caption(f"Unique normalized pre phones: {len(pre_phone_set)}")
            st.dataframe(
                pd.DataFrame({"Pre phone sample": sorted(list(pre_phone_set))[:10]}),
                width="stretch",
                hide_index=True,
            )
        with debug_col2:
            st.caption(f"Detected post phone column: {post_phone_col or 'Not found'}")
            st.caption(f"Unique normalized post phones: {len(post_phone_set)}")
            st.dataframe(
                pd.DataFrame({"Post phone sample": sorted(list(post_phone_set))[:10]}),
                width="stretch",
                hide_index=True,
            )
        return

    participant_records = []
    for phone in matched_phones:
        pre_row = pre_graded_df[pre_graded_df["Phone"] == phone].iloc[0]
        post_row = post_graded_df[post_graded_df["Phone"] == phone].iloc[0]
        participant_name = pre_row["Name"] or post_row["Name"] or "Participant"
        contact = get_comparison_contact_details(pre_df, post_df, phone, participant_name)
        participant_records.append(
            {
                "label": f"{participant_name} ({phone})",
                "phone": phone,
                "name": participant_name,
                "contact": contact,
                "pre_row": pre_row,
                "post_row": post_row,
                "user_id": f"{participant_name} ({phone})",
                "file_name": build_comparison_pdf_filename(participant_name),
            }
        )

    email_ready_count = sum(1 for item in participant_records if item["contact"].get("email"))

    with st.sidebar:
        st.markdown("---")
        selected_participant = st.selectbox(
            "Select User Report",
            [item["label"] for item in participant_records],
            help="The list shows only participants that exist in both uploaded CSVs after phone-number matching.",
        )
        st.caption(f"Matched individuals: {len(participant_records)}")
        st.caption(f"Email-ready rows: {email_ready_count}")
        st.caption("Bulk email is available in the Email Delivery tab.")

    selected_record = next(item for item in participant_records if item["label"] == selected_participant)
    selected_phone = selected_record["phone"]
    participant_name = selected_record["name"]
    pre_row = selected_record["pre_row"]
    post_row = selected_record["post_row"]
    contact = selected_record["contact"]
    comparison_user_id = selected_record["user_id"]
    comparison_file_name = selected_record["file_name"]

    top_metric_1, top_metric_2, top_metric_3, top_metric_4 = st.columns(4)
    with top_metric_1:
        render_small_metric("Selected User", participant_name)
    with top_metric_2:
        render_small_metric("Matched Individuals", len(matched_phones))
    with top_metric_3:
        render_small_metric("Pre CSV Usable Rows", len(pre_df))
    with top_metric_4:
        render_small_metric("Post CSV Usable Rows", len(post_df))

    def build_comparison_payload(record):
        record_pre = record["pre_row"]
        record_post = record["post_row"]
        question_rows = []
        for i in range(1, 13):
            q_key = f"Q{i}"
            question_rows.append(
                {
                    "Question": q_key,
                    "Pre": int(record_pre[q_key]),
                    "Post": int(record_post[q_key]),
                }
            )
        comparison_df = pd.DataFrame(question_rows)
        comparison_long = comparison_df.melt(
            id_vars="Question",
            value_vars=["Pre", "Post"],
            var_name="Survey",
            value_name="Correct",
        )
        insights_text = (
            f"### Individual Comparison Summary\n"
            f"- Participant: {record['name']}\n"
            f"- Phone: {record['phone']}\n"
            f"- Pre score: {int(record_pre['Total_Score'])}/12\n"
            f"- Post score: {int(record_post['Total_Score'])}/12\n"
            f"- Improvement: {int(record_post['Total_Score'] - record_pre['Total_Score'])}\n\n"
            f"### Question-by-Question Shift\n"
            + "\n".join(
                f"- Q{i}: Pre {int(record_pre[f'Q{i}'])}, Post {int(record_post[f'Q{i}'])}"
                for i in range(1, 13)
            )
        )
        return comparison_df, comparison_long, insights_text

    selected_comparison_df, selected_comparison_long, insights_text = build_comparison_payload(selected_record)
    insights_pdf = generate_comparison_pdf_playwright(selected_record)
    comparison_existing_pdf = st.session_state.generated_pdfs.get(comparison_user_id)

    report_tab, pdf_tab, email_tab = st.tabs(["Report", "PDF Library", "Email Delivery"])

    with report_tab:
        action_col, helper_col = st.columns([1.2, 1])
        with action_col:
            generate_single_comparison_pdf = False
            if comparison_existing_pdf and Path(comparison_existing_pdf["file_path"]).exists():
                st.download_button(
                    "Download Compiled PDF",
                    Path(comparison_existing_pdf["file_path"]).read_bytes(),
                    comparison_existing_pdf["file_name"],
                    "application/pdf",
                    use_container_width=True,
                    key="comparison_download_compiled_pdf",
                )
            else:
                generate_single_comparison_pdf = st.button(
                    "Compile Selected PDF",
                    type="primary",
                    use_container_width=True,
                    key="comparison_compile_selected_pdf",
                )
        with helper_col:
            render_info_card(
                "Current Selection",
                f"Previewing <b>{participant_name}</b>. Generate a comparison PDF here, then find it in the library just like the single report flow.",
            )

        st.markdown(section_header("01", participant_name), unsafe_allow_html=True)
        stat1, stat2, stat3 = st.columns(3)
        stat1.metric("Phone", selected_phone)
        stat2.metric("Pre Score", f"{int(pre_row['Total_Score'])} / 12")
        stat3.metric("Post Score", f"{int(post_row['Total_Score'])} / 12", delta=int(post_row["Total_Score"] - pre_row["Total_Score"]))
        fig_compare = px.bar(
            selected_comparison_long,
            x="Question",
            y="Correct",
            color="Survey",
            barmode="group",
            color_discrete_map={"Pre": "#1f77b4", "Post": "#2ca02c"},
            title="Pre/Post Individual Question Comparison",
        )
        fig_compare.update_yaxes(range=[0, 1], tickvals=[0, 1], ticktext=["Incorrect", "Correct"])
        st.plotly_chart(apply_grid(fig_compare), use_container_width=True)

        detail_df = pd.DataFrame(
            {
                "Question": [f"Q{i}" for i in range(1, 13)],
                "Pre": [int(pre_row[f"Q{i}"]) for i in range(1, 13)],
                "Post": [int(post_row[f"Q{i}"]) for i in range(1, 13)],
            }
        )
        st.subheader("Question Detail")
        st.dataframe(detail_df, use_container_width=True)

        st.subheader("Report Summary")
        st.markdown(insights_text)
        if generate_single_comparison_pdf:
            with st.spinner("Building comparison PDF..."):
                if not insights_pdf:
                    st.error("Comparison PDF could not be generated.")
                else:
                    try:
                        st.session_state.pdf_progress = {
                            "current": 1,
                            "total": 1,
                            "message": f"Generating selected PDF: {participant_name}",
                            "active": True,
                        }
                        st.session_state.generated_pdfs[comparison_user_id] = save_generated_pdf_record(
                            comparison_user_id,
                            comparison_file_name,
                            insights_pdf,
                            comparison_library_key,
                            email=contact["email"],
                            name=contact["name"],
                        )
                        persist_generated_pdf_library(
                            st.session_state.generated_pdfs,
                            comparison_library_key,
                        )
                        st.session_state.pdf_progress = {
                            "current": 1,
                            "total": 1,
                            "message": f"Generated selected PDF: {participant_name}",
                            "active": False,
                        }
                        st.success("Comparison PDF rendered successfully!")
                        st.rerun()
                    except Exception as e:
                        st.session_state.pdf_progress = {
                            "current": 0,
                            "total": 1,
                            "message": f"Selected PDF failed: {e}",
                            "active": False,
                        }
                        st.error(f"Could not save comparison PDF: {e}")

        if insights_pdf:
            st.download_button(
                "Download Report",
                insights_pdf,
                comparison_file_name,
                "application/pdf",
                use_container_width=True,
                key="comparison_download_selected_pdf",
            )

    with pdf_tab:
        pdf_progress_panel = st.empty()
        pdf_status_panel = st.empty()
        pdf_log_panel = st.empty()
        generated_list_panel = st.empty()
        st.markdown(section_header("02", "PDF Library"), unsafe_allow_html=True)
        action_left, action_mid, action_right = st.columns([1, 1, 1])
        with action_left:
            generate_all_comparison_pdfs = st.button(
                "Generate PDFs For All Rows",
                use_container_width=True,
                key="comparison_generate_all_pdfs",
            )
        with action_mid:
            clear_generated_pdfs = st.button(
                "Clear Generated PDF List",
                use_container_width=True,
                key="comparison_clear_generated_pdfs",
            )
        with action_right:
            render_info_card(
                "Library Scope",
                "This library is tied to the currently uploaded pre/post pair only. Running batch generation rebuilds the full set for this pair from scratch so the saved count always stays aligned.",
            )

        if st.session_state.pdf_progress["total"]:
            progress_total = max(st.session_state.pdf_progress["total"], 1)
            progress_current = min(st.session_state.pdf_progress["current"], progress_total)
            pdf_progress_panel.progress(
                progress_current / progress_total,
                text=f"Generating PDFs: {progress_current}/{progress_total}",
            )
            if st.session_state.pdf_progress["message"]:
                if st.session_state.pdf_progress["active"]:
                    pdf_status_panel.info(st.session_state.pdf_progress["message"])
                else:
                    pdf_status_panel.success(st.session_state.pdf_progress["message"])

        if generate_single_comparison_pdf and insights_pdf:
            try:
                st.session_state.generated_pdfs[comparison_user_id] = save_generated_pdf_record(
                    comparison_user_id,
                    comparison_file_name,
                    insights_pdf,
                    comparison_library_key,
                    email=contact["email"],
                    name=contact["name"],
                )
                persist_generated_pdf_library(
                    st.session_state.generated_pdfs,
                    comparison_library_key,
                )
                st.success("Comparison PDF saved to the library.")
            except Exception as e:
                st.error(f"Could not save comparison PDF: {e}")
        if clear_generated_pdfs:
            st.session_state.generated_pdfs = {}
            st.session_state.pdf_batch_log = []
            st.session_state.pdf_progress = {"current": 0, "total": 0, "message": "", "active": False}
            clear_generated_pdf_library(comparison_library_key)
            st.success("Cleared generated PDF list.")
        if generate_all_comparison_pdfs:
            total_reports = len(participant_records)
            st.session_state.generated_pdfs = {}
            clear_generated_pdf_library(comparison_library_key)
            batch_log = []
            generated_count = 0

            for position, record in enumerate(participant_records, start=1):
                current_name = record["name"]
                st.session_state.pdf_progress = {
                    "current": position,
                    "total": total_reports,
                    "message": f"Generating {position}/{total_reports}: {current_name}",
                    "active": True,
                }
                pdf_progress_panel.progress(position / total_reports, text=f"Generating PDFs: {position}/{total_reports}")
                pdf_status_panel.info(st.session_state.pdf_progress["message"])
                try:
                    record_pdf = generate_comparison_pdf_playwright(record)
                    st.session_state.generated_pdfs[record["user_id"]] = save_generated_pdf_record(
                        record["user_id"],
                        record["file_name"],
                        record_pdf,
                        comparison_library_key,
                        email=record["contact"]["email"],
                        name=record["contact"]["name"],
                    )
                    persist_generated_pdf_library(
                        st.session_state.generated_pdfs,
                        comparison_library_key,
                    )
                    generated_count += 1
                    batch_log.append(f"{position}/{total_reports} generated: {current_name}")
                    render_generated_pdf_library(generated_list_panel, report_type="comparison")
                except Exception as e:
                    batch_log.append(f"{position}/{total_reports} failed: {current_name} ({e})")

            st.session_state.pdf_batch_log = batch_log
            st.session_state.pdf_progress = {
                "current": total_reports,
                "total": total_reports,
                "message": f"Generated {generated_count}/{total_reports} PDF(s).",
                "active": False,
            }
            pdf_progress_panel.progress(1.0, text=f"Generating PDFs: {total_reports}/{total_reports}")
            pdf_status_panel.success(st.session_state.pdf_progress["message"])

        if st.session_state.pdf_batch_log:
            with pdf_log_panel.container():
                for line in st.session_state.pdf_batch_log[-10:]:
                    st.write(f"- {line}")
        render_generated_pdf_library(generated_list_panel, report_type="comparison")

    with email_tab:
        email_progress_panel = st.empty()
        email_status_panel = st.empty()
        email_log_panel = st.empty()
        st.markdown(section_header("03", "Email Delivery"), unsafe_allow_html=True)
        email_action_col, email_help_col = st.columns([1, 1.1])
        with email_action_col:
            send_bulk_comparison_emails = st.button(
                "Send Bulk Emails",
                use_container_width=True,
                key="comparison_send_bulk_emails",
            )
        with email_help_col:
            render_info_card(
                "Batch Sender",
                "This tab sends comparison PDFs as email attachments for all matched individuals that have an email address in either uploaded CSV.",
            )

        metric_a, metric_b = st.columns(2)
        with metric_a:
            render_small_metric("Email-Ready Rows", email_ready_count)
        with metric_b:
            render_small_metric("Email Mode", "Bulk Send")

        if send_bulk_comparison_emails:
            with st.spinner("Generating comparison PDFs and sending emails..."):
                try:
                    from send_pending_reports import send_email_with_attachment

                    total_targets = max(email_ready_count, 1)
                    email_progress = email_progress_panel.progress(
                        0,
                        text=f"Sending emails: 0/{email_ready_count}",
                    )
                    run_log = []
                    sent_count = 0
                    failed_count = 0
                    sendable_records = [item for item in participant_records if item["contact"].get("email")]

                    for index, record in enumerate(sendable_records, start=1):
                        email_status_panel.info(f"{index}/{email_ready_count}: Sending {record['name']}")
                        email_progress.progress(index / total_targets, text=f"Sending emails: {index}/{email_ready_count}")
                        try:
                            record_pdf = generate_comparison_pdf_playwright(record)
                            response = send_email_with_attachment(
                                email=record["contact"]["email"],
                                name=record["contact"]["name"],
                                file_name=record["file_name"],
                                file_bytes=record_pdf,
                            )
                            if response.status_code in (200, 201):
                                sent_count += 1
                                run_log.append(f"Sent: {record['name']} ({record['contact']['email']})")
                            else:
                                failed_count += 1
                                run_log.append(
                                    f"Failed: {record['name']} ({response.status_code})"
                                )
                        except Exception as e:
                            failed_count += 1
                            run_log.append(f"Failed: {record['name']} ({e})")

                    st.session_state.email_batch_log = run_log
                    if sent_count:
                        st.success(f"Sent {sent_count} email(s).")
                    if failed_count:
                        st.error(f"{failed_count} email(s) failed.")
                    email_status_panel.success(
                        f"Completed email run: {sent_count} sent, {failed_count} failed."
                    )
                except Exception as e:
                    st.error(f"Email sending failed: {e}")

        if st.session_state.email_batch_log:
            st.markdown("**Recent Email Activity**")
            with email_log_panel.container():
                for line in st.session_state.email_batch_log[-10:]:
                    st.write(f"- {line}")

# ─────────────────────────────────────────────
#  CHART BUILDERS
# ─────────────────────────────────────────────
def radar_chart(row):
    cats  = ['Foundation', 'Growth', 'Acceleration', 'Legacy']
    vals  = [row[c] for c in cats]
 
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals + [vals[0]], theta=cats + [cats[0]], fill='toself',
        fillcolor='rgba(37, 99, 235, 0.15)', line=dict(color='#2563eb', width=2),
        name='Profile', hovertemplate='%{theta}: %{r:.2f}<extra></extra>',
    ))
    bench = [4, 4, 4, 4]
    fig.add_trace(go.Scatterpolar(
        r=bench + [bench[0]], theta=cats + [cats[0]], line=dict(color='#94a3b8', width=1.5, dash='dash'),
        mode='lines', name='Benchmark ref', hoverinfo='skip',
    ))
    fig.update_layout(
        **PLOTLY_THEME,
        polar=dict(
            bgcolor='rgba(248, 250, 252, 0.8)',
            radialaxis=dict(visible=True, range=[0, 5], color='#64748b', gridcolor='#e2e8f0', tickfont=dict(size=9, color='#64748b')),
            angularaxis=dict(color='#475569', gridcolor='#e2e8f0'),
        ), showlegend=False, height=320,
    )
    return fig
 
def gauge_chart(value, title, color):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
        number=dict(font=dict(family="Playfair Display", size=36, color=color), suffix="", valueformat=".1f"),
        gauge=dict(
            axis=dict(range=[0, 100], tickwidth=0, tickcolor='rgba(0,0,0,0)', visible=False),
            bar=dict(color=color, thickness=0.65), bgcolor='rgba(0,0,0,0)', borderwidth=0,
            steps=[
                dict(range=[0, 40],  color='rgba(220, 38, 38, 0.1)'), dict(range=[40, 60], color='rgba(217, 119, 6, 0.1)'),
                dict(range=[60, 75], color='rgba(37, 99, 235, 0.1)'), dict(range=[75, 90], color='rgba(5, 150, 105, 0.1)'),
                dict(range=[90, 100],color='rgba(124, 58, 237, 0.1)'),
            ],
            threshold=dict(line=dict(color='#94a3b8', width=2), thickness=0.8, value=75),
        ),
    ))
    fig.update_layout(**PLOTLY_THEME, height=200, title=dict(text=title, font=dict(size=11, family='DM Mono', color='#475569', weight="bold"), x=0.5, y=0.95))
    return fig

def sigmoid_position_chart(value):
    x = np.linspace(0, 100, 400); k = 0.12
    y = 1 / (1 + np.exp(-k * (x - 50))); y_val = 1 / (1 + np.exp(-k * (value - 50)))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(color="#cbd5e1", width=3), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[value], y=[y_val], mode="markers", marker=dict(size=16, color="#059669", line=dict(color="#ffffff", width=3)), hovertemplate="Growth Index: %{x:.1f}<extra></extra>"))
    fig.add_annotation(
        x=value, y=y_val, text="<b>You are here</b>", showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5,
        arrowcolor="#059669", ax=65, ay=-35, font=dict(size=12, color="#059669", family="DM Sans"),
        bgcolor="rgba(255,255,255,0.9)", bordercolor="#059669", borderwidth=1,
    )
    fig.update_layout(
        paper_bgcolor=PLOTLY_THEME["paper_bgcolor"], plot_bgcolor=PLOTLY_THEME["plot_bgcolor"], font=PLOTLY_THEME["font"],
        height=238, margin=dict(l=30, r=10, t=12, b=28), xaxis=dict(range=[0, 100], title="Growth Index", gridcolor="#e2e8f0", zeroline=False),
        yaxis=dict(range=[0, 1], title="Maturity Momentum", gridcolor="#f1f5f9", zeroline=False, tickvals=[0, 0.25, 0.5, 0.75, 1.0], ticktext=["0", "0.25", "0.5", "0.75", "1.0"]),
        showlegend=False,
    )
    return fig

# ─────────────────────────────────────────────
#  HTML COMPONENTS
# ─────────────────────────────────────────────
def kpi_card(label, value, card_cls, val_cls):
    band_label, band_css = get_band(value)
    return f"""<div class="kpi-card {card_cls}"><div class="kpi-label">{label}</div><div class="kpi-value {val_cls}">{value:.0f}</div><span class="kpi-band {band_css}">{band_label}</span></div>"""
 
def section_header(num, title): 
    return f"""<div class="section-header"><span class="section-number">{num}</span><span class="section-title">{title}</span></div>"""
 
def stage_bar_html(row):
    stages = [
        ("Foundation Pressure",   row['Foundation'],   5, "#d97706"), 
        ("Growth Stability",      row['Growth'],       5, "#2563eb"), 
        ("Acceleration Readiness",row['Acceleration'], 5, "#7c3aed"), 
        ("Legacy Strength",       row['Legacy'],       5, "#059669")
    ]
    bars = ""
    for label, val, max_val, color in stages:
        pct = (val / max_val) * 100
        bars += f'<div class="stage-row"><span class="stage-label">{label}</span><div class="stage-track"><div class="stage-fill" style="width:{pct:.1f}%; background:{color};"></div></div><span class="stage-val">{val:.2f}</span></div>'
    return f'<div class="stage-bar-wrap stage-profile-offset">{bars}</div>'

def score_explanation_html():
    return (
        '<div class="explain-wrap"><div class="explain-head">How Your Scores Are Calculated</div><div class="explain-sub"></div><div class="explain-grid">'
        '<div class="explain-card exp-rel"><h4>Relevance</h4><ul><li>Meets immediate needs of parents and students.</li><li>Focus on curriculum alignment, compliance, visibility.</li><li>Creates a unique value proposition that differentiates.</li></ul></div>'
        '<div class="explain-card exp-reli"><h4>Reliability</h4><ul><li>Community trusts consistent delivery year after year.</li><li>Strong outcomes, defined SOPs, parent engagement.</li><li>Innovates and creates scalable systems.</li></ul></div>'
        '<div class="explain-card exp-repu"><h4>Reputability</h4><ul><li>Recognized at state, national, or international levels.</li><li>Engages in legacy-building initiatives.</li><li>Seen as a benchmark of excellence.</li></ul></div>'
        '</div></div>'
    )

def growth_stage_focus_html():
    return (
        '<div class="focus-wrap">'
        '<div class="focus-title">Growth Stages and Focus</div>'
        '<table class="focus-table">'
        '<thead>'
        '<tr>'
        '<th></th>'
        '<th>Management</th>'
        '<th>School Leader</th>'
        '<th>Faculty</th>'
        '</tr>'
        '</thead>'
        '<tbody>'
        '<tr>'
        '<td class="focus-stage">Foundation</td>'
        '<td>Focus on capital investment, brand positioning, community outreach, and long-term vision.</td>'
        '<td>Establish operational systems (admissions, timetable, discipline, communication).</td>'
        '<td>Adapt to school culture, set academic benchmarks, and engage parents directly.</td>'
        '</tr>'
        '<tr>'
        '<td class="focus-stage">Growth</td>'
        '<td>Shift from firefighting to governance - set clear policies, delegate authority, monitor performance.</td>'
        '<td>Drive academic quality, teacher mentoring, and parent engagement.</td>'
        '<td>Deliver consistent results; adopt professional development and modern pedagogy.</td>'
        '</tr>'
        '<tr>'
        '<td class="focus-stage">Acceleration</td>'
        '<td>Provide strategic investments for innovation; build alliances (universities, corporates, international partners).</td>'
        '<td>Shift to transformational leadership - focusing on culture, innovation, teacher empowerment, and visibility.</td>'
        '<td>Move from "teaching" to "mentoring and innovating"; collaborate on curriculum enrichment, research, and competitions.</td>'
        '</tr>'
        '<tr>'
        '<td class="focus-stage">Consolidation</td>'
        '<td>Focus on sustainability, diversification, succession planning, and creating a legacy.</td>'
        '<td>Become ambassadors and thought leaders in education forums; groom next-line leaders.</td>'
        '<td>Engage in advanced professional development, research, publications, and innovation in pedagogy.</td>'
        '</tr>'
        '</tbody>'
        '</table>'
        '</div>'
    )

# ─────────────────────────────────────────────
#  PLAYWRIGHT PDF GENERATOR ENGINE (SYNCHRONOUS & SINGLE PAGE)
# ─────────────────────────────────────────────
def generate_user_pdf_playwright(row):
    """Generates a high-fidelity, perfectly scaled single-page PDF using Playwright natively."""
    
    # 1. Generate HTML strings instead of Base64 images
    sig_html = fig_to_html(sigmoid_position_chart(row['Growth_Index']), 650, 260)
    g1_html = fig_to_html(gauge_chart(row['Relevance'], "RELEVANCE", "#d97706"), 220, 160)
    g2_html = fig_to_html(gauge_chart(row['Reliability_Adj'], "RELIABILITY", "#2563eb"), 220, 160)
    g3_html = fig_to_html(gauge_chart(row['Reputability_Adj'], "REPUTABILITY", "#7c3aed"), 220, 160)
    rad_html = fig_to_html(radar_chart(row), 450, 360)
    
    label, badge_cls, desc = get_strategic_profile(row)
    pdf_css = CUSTOM_CSS.replace(
        "@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');",
        "",
    )
    plotly_js = get_plotlyjs()
    logo_uri = get_edxso_logo_data_uri()
    logo_html = f'<img class="brand-logo" src="{logo_uri}" alt="EDXSO logo">' if logo_uri else ""
    
    # 2. Inject the HTML directly (No <img> tags needed!)
    pdf_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <script type="text/javascript">{plotly_js}</script>
        <style>
            {pdf_css}
            html, body {{ margin: 0 !important; padding: 0 !important; background: #ffffff; }}
            .pdf-container {{ padding: 50px; width: 100%; box-sizing: border-box; }}
            * {{ page-break-inside: avoid !important; page-break-before: auto !important; page-break-after: auto !important; }}
            .brand-row {{ display:flex; align-items:center; gap:12px; margin-bottom: 14px; }}
            .brand-logo {{
                width: 52px;
                height: 52px;
                object-fit: contain;
                border-radius: 12px;
                background: #f8fbff;
                border: 1px solid #dbe3f0;
                padding: 6px;
            }}
            .brand-copy {{ display:flex; flex-direction:column; gap:3px; }}
            .brand-name {{
                font-family: 'DM Mono', monospace;
                font-size: 0.68rem;
                color: #64748b;
                letter-spacing: 0.18em;
                text-transform: uppercase;
            }}
            .brand-tagline {{
                font-family: 'DM Sans', sans-serif;
                font-size: 0.92rem;
                color: #0f172a;
                font-weight: 600;
            }}
            .kpi-row {{ display: flex; gap: 20px; margin-bottom: 25px; align-items: stretch; }}
            .kpi-col {{ flex: 1; display: flex; flex-direction: column; }}
            .chart-col {{ flex: 1.5; display: flex; justify-content: center; align-items: center; border: 1px solid #e2e8f0; border-radius: 12px; }}
            .gauge-row {{ display: flex; justify-content: space-around; margin-top: 15px; margin-bottom: 25px; width: 100%; }}
            .gauge-item {{ width: 32%; }}
        </style>
    </head>
    <body>
        <div class="pdf-container">
            <div class="brand-row">
                {logo_html}
                <div class="brand-copy">
                    <div class="brand-name">EDXSO Strategic Intelligence</div>
                    <div class="brand-tagline">Growth and Readiness Report</div>
                </div>
            </div>
            <div class="sub-title" style="font-family: 'DM Mono', monospace; font-size: 0.75rem; color: #64748b; letter-spacing: 0.2em; text-transform: uppercase;">Your Strategic Report</div>
            <h1 style="margin-top: 5px; margin-bottom: 15px;">{row['Display_Name']}</h1>
            
            <div class="status-row" style="margin-bottom: 35px;">
                <span class="status-badge {badge_cls}">{label}</span>
                <span class="badge-desc">{desc}</span>
            </div>
            
            <div class="kpi-row">
                <div class="kpi-col">
                    <div class="kpi-card growth" style="height: 100%; display:flex; flex-direction:column; justify-content:center;">
                        <div class="kpi-label">Growth Index</div>
                        <div class="kpi-value growth">{row['Growth_Index']:.1f}</div>
                    </div>
                </div>
                <div class="chart-col">
                    {sig_html}
                </div>
            </div>
            
            <div class="section-header" style="margin-top: 40px;">
                <span class="section-number">01</span><span class="section-title">R-Cube Maturity Gauges</span>
            </div>
            
            <div class="gauge-row">
                <div class="gauge-item">{g1_html}</div>
                <div class="gauge-item">{g2_html}</div>
                <div class="gauge-item">{g3_html}</div>
            </div>
            
            <div style="margin-top: 20px; margin-bottom: 40px;">{score_explanation_html()}</div>

            <div class="section-header">
                <span class="section-number">02</span><span class="section-title">Growth Stage Profile</span>
            </div>
            
            <div class="kpi-row" style="align-items: center;">
                <div class="kpi-col">{stage_bar_html(row)}</div>
                <div class="chart-col">{rad_html}</div>
            </div>
            
            <div style="margin-top: 20px;">{growth_stage_focus_html()}</div>
            
            <div style="margin-top: 50px; text-align: center; font-family: 'DM Mono', monospace; font-size: 10px; color: #94a3b8; text-transform: uppercase; border-top: 1px solid #e2e8f0; padding-top: 20px;">
                R-Cube Strategic Intelligence · Edxso Analytics · Confidential Report
            </div>
        </div>
    </body>
    </html>
    """
    
    ensure_playwright_ready()
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--single-process"]
        )
        context = browser.new_context()
        page = context.new_page()
        
        page.set_content(pdf_html, wait_until="load")
        
        # Hard wait 2 seconds to let Plotly drawing animations finish
        page.wait_for_timeout(2000) 
        
        exact_height = page.evaluate("document.documentElement.scrollHeight")
        adjusted_height = exact_height + 50

        pdf_bytes = page.pdf(
            width="1100px",
            height=f"{adjusted_height}px",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"}
        )
        browser.close()
        return pdf_bytes


def build_assessment_pdf_filename(name, survey_kind, event_name=""):
    safe_name = slugify_filename_part(name or "Participant")
    safe_event = slugify_filename_part(event_name or "")
    prefix = "PreAssessment" if survey_kind == "pre_assessment" else "PostAssessment"
    if safe_event:
        return f"{safe_event}_{safe_name}.pdf"
    return f"{prefix}_{safe_name}.pdf"


def build_certificate_pdf_filename(name, event_name=""):
    safe_name = slugify_filename_part(name or "Participant")
    safe_event = slugify_filename_part(event_name or "")
    if safe_event:
        return f"{safe_event}_Certificate_{safe_name}.pdf"
    return f"Participation_Certificate_{safe_name}.pdf"


def render_assessment_single_report(raw, uploaded_file, current_library_key, survey_kind, certificate_overrides=None):
    api_key = os.getenv("GEMINI_API_KEY")
    answer_key = PRE_ASSESSMENT_KEY if survey_kind == "pre_assessment" else POST_ASSESSMENT_KEY
    survey_title = "Pre Assessment Survey" if survey_kind == "pre_assessment" else "Post Assessment Survey"
    certificate_overrides = certificate_overrides or {}

    results, dynamic_answer_key = prepare_assessment_results(raw, answer_key, api_key)
    question_metrics_df = get_question_metrics(raw, dynamic_answer_key, answer_key)
    participant_scores = get_participant_scores(raw, dynamic_answer_key)
    st.session_state.generated_pdfs, library_updated = backfill_library_from_current_dataset(
        raw,
        results,
        st.session_state.generated_pdfs,
        survey_kind=survey_kind,
        certificate_overrides=certificate_overrides,
    )
    if library_updated:
        persist_generated_pdf_library(st.session_state.generated_pdfs, current_library_key)
    status_col = find_column_name(raw, ["status", "mail status", "email status"])
    pending_count = raw[status_col].astype(str).str.strip().eq("Pending").sum() if status_col is not None else len(raw)

    with st.sidebar:
        st.markdown("---")
        user_choice = st.selectbox("Select User Report", results["UserID"].tolist())
        st.caption(f"Uploaded list rows: {len(results)}")
        st.caption(f"Pending email rows: {pending_count}")
        st.caption(f"Detected survey: {survey_title}")
        if certificate_overrides.get("event_name") or certificate_overrides.get("event_date"):
            st.caption(
                "Certificate defaults: "
                f"{certificate_overrides.get('event_name', 'No event name')} · "
                f"{certificate_overrides.get('event_date', 'No event date')}"
            )

    row = results[results["UserID"] == user_choice].iloc[0].copy()
    for i, question in enumerate(answer_key.keys(), start=1):
        row[f"QuestionText{i}"] = question

    total_questions = 12
    score = int(row["Total_Score"])
    percent_score = round((score / total_questions) * 100, 1)
    single_existing_pdf = st.session_state.generated_pdfs.get(user_choice)
    saved_pdf_count = len(st.session_state.generated_pdfs)

    render_panel_header(
        "Assessment Report",
        survey_title,
        "Review one participant at a time, generate PDFs in bulk, and send email attachments from the same workspace.",
    )
    top_a, top_b, top_c, top_d = st.columns(4)
    with top_a:
        render_small_metric("Participants", len(results))
    with top_b:
        assessment_progress_panel = st.empty()
        render_progress_metric(assessment_progress_panel, saved_pdf_count, len(results))
    with top_c:
        render_small_metric("Pending Emails", pending_count)
    with top_d:
        render_small_metric("Survey Type", "Pre Assessment" if survey_kind == "pre_assessment" else "Post Assessment")

    report_tab, pdf_tab, email_tab = st.tabs(["Report", "PDF Library", "Email Delivery"])

    with report_tab:
        action_col, helper_col = st.columns([1.2, 1])
        report_status_panel = st.empty()
        with action_col:
            generate_single_pdf = False
            if single_existing_pdf and Path(single_existing_pdf["file_path"]).exists():
                download_col, recompile_col = st.columns(2)
                with download_col:
                    st.download_button(
                        "Download Compiled PDF",
                        Path(single_existing_pdf["file_path"]).read_bytes(),
                        single_existing_pdf["file_name"],
                        "application/pdf",
                        use_container_width=True,
                        key=f"assessment_download_compiled_{user_choice}",
                    )
                with recompile_col:
                    generate_single_pdf = st.button(
                        "Recompile PDF",
                        type="primary",
                        use_container_width=True,
                        key=f"assessment_recompile_{user_choice}",
                    )
            else:
                generate_single_pdf = st.button(
                    "Compile Selected PDF",
                    type="primary",
                    use_container_width=True,
                    key=f"assessment_compile_{user_choice}",
                )
        with helper_col:
            render_info_card(
                "Detected Survey",
                f"This file was auto-identified as <b>{survey_title}</b>, so the app is using question headers and participant fields from column names instead of fixed positions.",
            )
            if single_existing_pdf and Path(single_existing_pdf["file_path"]).exists():
                st.caption("A previously saved PDF already exists for this participant. Use `Recompile PDF` to refresh it with the latest report template and branding.")

        st.markdown(section_header("01", row["Display_Name"]), unsafe_allow_html=True)
        m1, m2 = st.columns(2)
        m1.metric("Email", row.get("Email", "") or "-")
        m2.metric("Score", f"{score}/{total_questions}", delta=f"{percent_score}%")

        detail_df = pd.DataFrame(
            {
                "Question": [f"Q{i}" for i in range(1, total_questions + 1)],
                "Status": ["Correct" if int(row[f"Q{i}"]) else "Incorrect" for i in range(1, total_questions + 1)],
                "Prompt": list(answer_key.keys()),
            }
        )
        st.dataframe(detail_df, use_container_width=True, hide_index=True)

        if generate_single_pdf:
            report_status_panel.info(f"Recompiling PDF for {row['Display_Name']}...")
            with st.spinner("Rendering assessment PDF..."):
                try:
                    pdf_bytes = generate_assessment_pdf_playwright(
                        row,
                        survey_title,
                        question_metrics_df,
                        participant_scores,
                        answer_key,
                    )
                    certificate = get_row_certificate_details_with_overrides(
                        raw,
                        results,
                        user_choice,
                        certificate_overrides,
                    )
                    file_name = build_assessment_pdf_filename(
                        user_choice,
                        survey_kind,
                        certificate.get("event_name", ""),
                    )
                    st.session_state.generated_pdfs[user_choice] = save_generated_pdf_record(
                        user_choice,
                        file_name,
                        pdf_bytes,
                        current_library_key,
                        email=row.get("Email", ""),
                        name=row.get("Display_Name", user_choice),
                        school=certificate.get("school", ""),
                        event_date=certificate.get("event_date", ""),
                        phone=certificate.get("phone", ""),
                        event_name=certificate.get("event_name", ""),
                    )
                    persist_generated_pdf_library(st.session_state.generated_pdfs, current_library_key)
                    report_status_panel.success(f"Recompiled PDF for {row['Display_Name']}.")
                    st.success("PDF rendered successfully!")
                    st.rerun()
                except Exception as e:
                    report_status_panel.error(f"Recompile failed for {row['Display_Name']}: {e}")
                    st.error(f"Render failed: {e}")

    with pdf_tab:
        st.markdown(section_header("02", "PDF Library"), unsafe_allow_html=True)
        if st.button("Generate PDFs For All Rows", use_container_width=True, key="assessment_batch_pdf"):
            st.session_state.generated_pdfs = {}
            clear_generated_pdf_library(current_library_key)
            render_progress_metric(assessment_progress_panel, 0, len(results))
            batch_log = []
            generated_count = 0
            for position, (_, report_row) in enumerate(results.iterrows(), start=1):
                current_name = resolve_record_display_name(report_row, fallback=f"User {position}")
                try:
                    record = report_row.copy()
                    for i, question in enumerate(answer_key.keys(), start=1):
                        record[f"QuestionText{i}"] = question
                    row_certificate = get_row_certificate_details_with_overrides(
                        raw,
                        results,
                        report_row["UserID"],
                        certificate_overrides,
                    )
                    pdf_bytes = generate_assessment_pdf_playwright(
                        record,
                        survey_title,
                        question_metrics_df,
                        participant_scores,
                        answer_key,
                    )
                    st.session_state.generated_pdfs[report_row["UserID"]] = save_generated_pdf_record(
                        report_row["UserID"],
                        build_assessment_pdf_filename(
                            current_name,
                            survey_kind,
                            row_certificate.get("event_name", ""),
                        ),
                        pdf_bytes,
                        current_library_key,
                        email=report_row.get("Email", ""),
                        name=current_name,
                        school=row_certificate.get("school", ""),
                        event_date=row_certificate.get("event_date", ""),
                        phone=row_certificate.get("phone", ""),
                        event_name=row_certificate.get("event_name", ""),
                    )
                    generated_count += 1
                    render_progress_metric(assessment_progress_panel, generated_count, len(results))
                    batch_log.append(f"{position}/{len(results)} generated: {current_name}")
                except Exception as e:
                    render_progress_metric(assessment_progress_panel, generated_count, len(results))
                    batch_log.append(f"{position}/{len(results)} failed: {current_name} ({e})")
            persist_generated_pdf_library(st.session_state.generated_pdfs, current_library_key)
            st.session_state.pdf_batch_log = batch_log
            st.success("Batch PDF generation finished.")
        if st.button("Clear Generated PDF List", use_container_width=True, key="assessment_clear_pdf"):
            st.session_state.generated_pdfs = {}
            clear_generated_pdf_library(current_library_key)
            st.success("Cleared generated PDF list.")
        if st.session_state.pdf_batch_log:
            for line in st.session_state.pdf_batch_log[-10:]:
                st.write(f"- {line}")
        library_panel = st.empty()
        render_generated_pdf_library(
            library_panel,
            report_type="single",
            current_dataset={"raw": raw, "results": results},
        )

    with email_tab:
        st.markdown(section_header("03", "Email Delivery"), unsafe_allow_html=True)
        if st.button("Send Bulk Emails", use_container_width=True, key="assessment_bulk_email"):
            with st.spinner("Generating PDFs and sending emails..."):
                try:
                    from send_pending_reports import send_pending_reports_from_dataframe
                    run_log = send_pending_reports_from_dataframe(raw)
                    st.session_state.email_batch_log = [item["message"] for item in run_log]
                    st.success("Completed email run.")
                except Exception as e:
                    st.error(f"Email sending failed: {e}")
        if st.session_state.email_batch_log:
            for line in st.session_state.email_batch_log[-10:]:
                st.write(f"- {line}")


def render_certificate_only_report(raw, uploaded_file, current_library_key):
    results = prepare_certificate_only_results(raw)
    st.session_state.generated_pdfs, library_updated = backfill_library_from_current_dataset(
        raw,
        results,
        st.session_state.generated_pdfs,
        survey_kind="certificate_only",
    )
    if library_updated:
        persist_generated_pdf_library(st.session_state.generated_pdfs, current_library_key)

    pending_count = len(results)

    with st.sidebar:
        st.markdown("---")
        user_choice = st.selectbox("Select Certificate Recipient", results["UserID"].tolist())
        st.caption(f"Uploaded list rows: {len(results)}")
        st.caption(f"Pending certificate emails: {pending_count}")
        st.caption("School name will be fetched from the database using email/phone.")

    row = results[results["UserID"] == user_choice].iloc[0]
    single_existing_pdf = st.session_state.generated_pdfs.get(user_choice)
    saved_pdf_count = len(st.session_state.generated_pdfs)

    render_panel_header(
        "Certificate Only",
        "Certificate Delivery Workspace",
        "Upload a simple participant CSV, generate participation certificates, and send certificate emails from the same workspace.",
    )
    top_a, top_b, top_c, top_d = st.columns(4)
    with top_a:
        render_small_metric("Participants", len(results))
    with top_b:
        certificate_progress_panel = st.empty()
        render_progress_metric(certificate_progress_panel, saved_pdf_count, len(results))
    with top_c:
        render_small_metric("Pending Certificates", pending_count)
    with top_d:
        render_small_metric("Survey Type", "Certificate Only")

    report_tab, pdf_tab, email_tab = st.tabs(["Report", "PDF Library", "Email Delivery"])

    with report_tab:
        action_col, helper_col = st.columns([1.2, 1])
        report_status_panel = st.empty()
        with action_col:
            generate_single_certificate = False
            if single_existing_pdf and Path(single_existing_pdf["file_path"]).exists():
                download_col, recompile_col = st.columns(2)
                with download_col:
                    st.download_button(
                        "Download Compiled Certificate",
                        Path(single_existing_pdf["file_path"]).read_bytes(),
                        single_existing_pdf["file_name"],
                        "application/pdf",
                        use_container_width=True,
                        key=f"certificate_only_download_compiled_{user_choice}",
                    )
                with recompile_col:
                    generate_single_certificate = st.button(
                        "Recompile Certificate",
                        type="primary",
                        use_container_width=True,
                        key=f"certificate_only_recompile_{user_choice}",
                    )
            else:
                generate_single_certificate = st.button(
                    "Compile Selected Certificate",
                    type="primary",
                    use_container_width=True,
                    key=f"certificate_only_compile_{user_choice}",
                )
        with helper_col:
            render_info_card(
                "Certificate Inputs",
                "This mode uses only the uploaded participant fields for name, email, phone, event name, and event date. School name is enriched from the database before the certificate is generated.",
            )

        certificate_details = enrich_certificate_details(
            {
                "name": row["Display_Name"],
                "email": row.get("Email", ""),
                "phone": row.get("Phone", ""),
                "event_name": row.get("Event_Name", ""),
                "event_date": row.get("Event_Date", ""),
                "school": "",
            },
            source_name=uploaded_file.name,
        )

        st.markdown(section_header("01", certificate_details.get("name", row["Display_Name"])), unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Email", certificate_details.get("email", "") or "-")
        m2.metric("Phone", certificate_details.get("phone", "") or "-")
        m3.metric("Event Name", certificate_details.get("event_name", "") or "-")
        m4.metric("Event Date", certificate_details.get("event_date", "") or "-")
        st.caption(f"School from DB: {certificate_details.get('school', '') or 'Not found'}")

        if generate_single_certificate:
            report_status_panel.info(f"Compiling certificate for {certificate_details.get('name', row['Display_Name'])}...")
            with st.spinner("Rendering certificate PDF..."):
                try:
                    pdf_bytes = generate_certificate_pdf_playwright(
                        certificate_details.get("name", row["Display_Name"]),
                        school_name=certificate_details.get("school", ""),
                        event_date=certificate_details.get("event_date", ""),
                        event_name=certificate_details.get("event_name", ""),
                        workshop_title="Participation Certificate",
                    )
                    file_name = build_certificate_pdf_filename(
                        certificate_details.get("name", row["Display_Name"]),
                        certificate_details.get("event_name", ""),
                    )
                    st.session_state.generated_pdfs[user_choice] = save_generated_pdf_record(
                        user_choice,
                        file_name,
                        pdf_bytes,
                        current_library_key,
                        email=certificate_details.get("email", ""),
                        name=certificate_details.get("name", row["Display_Name"]),
                        school=certificate_details.get("school", ""),
                        event_date=certificate_details.get("event_date", ""),
                        phone=certificate_details.get("phone", ""),
                        event_name=certificate_details.get("event_name", ""),
                    )
                    persist_generated_pdf_library(st.session_state.generated_pdfs, current_library_key)
                    report_status_panel.success(f"Compiled certificate for {certificate_details.get('name', row['Display_Name'])}.")
                    st.rerun()
                except Exception as e:
                    report_status_panel.error(f"Certificate compile failed for {certificate_details.get('name', row['Display_Name'])}: {e}")

    with pdf_tab:
        st.markdown(section_header("02", "PDF Library"), unsafe_allow_html=True)
        if st.button("Generate Certificates For All Rows", use_container_width=True, key="certificate_only_batch_pdf"):
            st.session_state.generated_pdfs = {}
            clear_generated_pdf_library(current_library_key)
            render_progress_metric(certificate_progress_panel, 0, len(results))
            batch_log = []
            generated_count = 0
            for position, (_, report_row) in enumerate(results.iterrows(), start=1):
                current_name = resolve_record_display_name(report_row, fallback=f"User {position}")
                try:
                    row_details = enrich_certificate_details(
                        {
                            "name": current_name,
                            "email": report_row.get("Email", ""),
                            "phone": report_row.get("Phone", ""),
                            "event_name": report_row.get("Event_Name", ""),
                            "event_date": report_row.get("Event_Date", ""),
                            "school": "",
                        },
                        source_name=uploaded_file.name,
                    )
                    pdf_bytes = generate_certificate_pdf_playwright(
                        row_details.get("name", current_name),
                        school_name=row_details.get("school", ""),
                        event_date=row_details.get("event_date", ""),
                        event_name=row_details.get("event_name", ""),
                        workshop_title="Participation Certificate",
                    )
                    st.session_state.generated_pdfs[report_row["UserID"]] = save_generated_pdf_record(
                        report_row["UserID"],
                        build_certificate_pdf_filename(
                            row_details.get("name", current_name),
                            row_details.get("event_name", ""),
                        ),
                        pdf_bytes,
                        current_library_key,
                        email=row_details.get("email", ""),
                        name=row_details.get("name", current_name),
                        school=row_details.get("school", ""),
                        event_date=row_details.get("event_date", ""),
                        phone=row_details.get("phone", ""),
                        event_name=row_details.get("event_name", ""),
                    )
                    generated_count += 1
                    render_progress_metric(certificate_progress_panel, generated_count, len(results))
                    batch_log.append(f"{position}/{len(results)} generated: {row_details.get('name', current_name)}")
                except Exception as e:
                    render_progress_metric(certificate_progress_panel, generated_count, len(results))
                    batch_log.append(f"{position}/{len(results)} failed: {current_name} ({e})")
            persist_generated_pdf_library(st.session_state.generated_pdfs, current_library_key)
            st.session_state.pdf_batch_log = batch_log
            st.success("Batch certificate generation finished.")
        if st.button("Clear Generated PDF List", use_container_width=True, key="certificate_only_clear_pdf"):
            st.session_state.generated_pdfs = {}
            clear_generated_pdf_library(current_library_key)
            st.success("Cleared generated PDF list.")
        if st.session_state.pdf_batch_log:
            for line in st.session_state.pdf_batch_log[-10:]:
                st.write(f"- {line}")
        library_panel = st.empty()
        render_generated_pdf_library(
            library_panel,
            report_type="certificate_only",
            current_dataset={"raw": raw, "results": results},
        )

    with email_tab:
        st.markdown(section_header("03", "Email Delivery"), unsafe_allow_html=True)
        if st.button("Send Bulk Certificates", use_container_width=True, key="certificate_only_bulk_email"):
            progress_panel = st.empty()
            status_panel = st.empty()
            run_log = []
            total_targets = len(results)
            try:
                from send_pending_reports import send_certificate_email_with_attachment

                sent_count = 0
                failed_count = 0
                for index, (_, report_row) in enumerate(results.iterrows(), start=1):
                    row_details = enrich_certificate_details(
                        {
                            "name": resolve_record_display_name(report_row, fallback=f"User {index}"),
                            "email": report_row.get("Email", ""),
                            "phone": report_row.get("Phone", ""),
                            "event_name": report_row.get("Event_Name", ""),
                            "event_date": report_row.get("Event_Date", ""),
                            "school": "",
                        },
                        source_name=uploaded_file.name,
                    )
                    recipient_email = normalize_email_value(row_details.get("email", ""))
                    status_panel.info(f"{index}/{total_targets}: Sending certificate to {row_details.get('name', '')}")
                    progress_panel.progress(index / max(total_targets, 1), text=f"Sending certificates: {index}/{total_targets}")
                    if not recipient_email:
                        failed_count += 1
                        run_log.append(f"Failed: {row_details.get('name', '')} (No email found)")
                        continue
                    try:
                        pdf_bytes = generate_certificate_pdf_playwright(
                            row_details.get("name", ""),
                            school_name=row_details.get("school", ""),
                            event_date=row_details.get("event_date", ""),
                            event_name=row_details.get("event_name", ""),
                            workshop_title="Participation Certificate",
                        )
                        response = send_certificate_email_with_attachment(
                            email=recipient_email,
                            name=row_details.get("name", ""),
                            file_name=build_certificate_pdf_filename(
                                row_details.get("name", ""),
                                row_details.get("event_name", ""),
                            ),
                            file_bytes=pdf_bytes,
                            event_date=row_details.get("event_date", ""),
                        )
                        if response.status_code in (200, 201):
                            sent_count += 1
                            run_log.append(f"Sent: {row_details.get('name', '')} ({recipient_email})")
                        else:
                            failed_count += 1
                            run_log.append(f"Failed: {row_details.get('name', '')} ({response.status_code})")
                    except Exception as e:
                        failed_count += 1
                        run_log.append(f"Failed: {row_details.get('name', '')} ({e})")

                st.session_state.email_batch_log = run_log
                if sent_count:
                    st.success(f"Sent {sent_count} certificate email(s).")
                if failed_count:
                    st.error(f"{failed_count} certificate email(s) failed.")
            except Exception as e:
                st.error(f"Certificate sending failed: {e}")
        if st.session_state.email_batch_log:
            for line in st.session_state.email_batch_log[-10:]:
                st.write(f"- {line}")

def run_app():
    install_playwright()
    st.markdown(f"<style>{CUSTOM_CSS}</style>", unsafe_allow_html=True)
    if "generated_pdfs" not in st.session_state:
        st.session_state.generated_pdfs = {}
    if "pdf_batch_log" not in st.session_state:
        st.session_state.pdf_batch_log = []
    if "email_batch_log" not in st.session_state:
        st.session_state.email_batch_log = []
    if "pdf_progress" not in st.session_state:
        st.session_state.pdf_progress = {"current": 0, "total": 0, "message": "", "active": False}

    with st.sidebar:
        st.markdown("""
        <div style='padding: 0.5rem 0 1.5rem 0;'>
            <div style='font-family: Playfair Display, serif; font-size: 1.5rem; font-weight: 900; color: #0f172a; line-height: 1.1;'>
                R-Cube<br>Strategic Intelligence
            </div>
            <div style='font-family: DM Mono, monospace; font-size: 0.65rem; letter-spacing: 0.2em; color: #64748b; text-transform: uppercase; margin-top: 0.4rem;'>
                Screening Metric v2
            </div>
        </div>
        """, unsafe_allow_html=True)

        report_mode = st.radio(
            "Report Type",
            ["Single Report", "Pre/Post Comparison", "Certificate Only"],
            horizontal=True,
        )

        if report_mode in {"Single Report", "Certificate Only"}:
            uploaded_file = st.file_uploader("Upload Response CSV", type=["csv"])
        else:
            uploaded_file = None

    if report_mode == "Pre/Post Comparison":
        render_comparison_report()
        return

    if not uploaded_file:
        st.session_state.current_library_key = None
        st.session_state.generated_pdfs = {}
        mode_title = "Certificate Only" if report_mode == "Certificate Only" else "Single Report"
        mode_heading = "Certificate Delivery Workspace" if report_mode == "Certificate Only" else "R-Cube Strategic Command Centre"
        mode_description = (
            "Upload a participant CSV with name, email, phone, event name, and event date to generate and send certificates."
            if report_mode == "Certificate Only"
            else "Upload one survey CSV to review individual reports, generate a PDF library, and send emails from one place."
        )
        render_panel_header(mode_title, mode_heading, mode_description)
        report_tab, pdf_tab, email_tab = st.tabs(["Report", "PDF Library", "Email Delivery"])
        with report_tab:
            render_info_card(
                "Get Started",
                "Upload your participant CSV to unlock certificate generation and certificate email delivery."
                if report_mode == "Certificate Only"
                else "Upload your survey CSV to unlock the individual report view and generate new PDFs for selected users.",
            )
        with pdf_tab:
            render_info_card(
                "Saved Reports",
                "Previously generated certificate PDFs stay visible here even when no CSV is uploaded."
                if report_mode == "Certificate Only"
                else "Previously generated PDFs stay visible here even when no survey is uploaded. Upload a CSV only when you want to generate new reports.",
            )
            library_panel = st.empty()
            render_generated_pdf_library(
                library_panel,
                report_type="certificate_only" if report_mode == "Certificate Only" else "single",
            )
        with email_tab:
            render_info_card(
                "Email Delivery",
                "You can bulk-send certificates from any saved certificate library below, even without uploading a new CSV."
                if report_mode == "Certificate Only"
                else "You can bulk-send from any saved survey library below, even without uploading a new CSV. Upload a survey CSV only when you want to generate fresh reports first.",
            )
            if report_mode == "Certificate Only":
                render_saved_library_bulk_certificate_panel("certificate_only", "certificate_saved")
            else:
                render_saved_library_bulk_email_panel("single", "single_saved")
        return

    uploaded_file_bytes = uploaded_file.getvalue()
    current_library_key = build_library_key(uploaded_file.name, uploaded_file_bytes)
    persist_library_meta(
        current_library_key,
        uploaded_file.name,
        report_type="certificate_only" if report_mode == "Certificate Only" else "single",
    )
    if st.session_state.get("current_library_key") != current_library_key:
        st.session_state.current_library_key = current_library_key
        st.session_state.generated_pdfs = load_generated_pdf_library(current_library_key)
        st.session_state.pdf_batch_log = []
        st.session_state.pdf_progress = {"current": 0, "total": 0, "message": "", "active": False}

    raw = pd.read_csv(io.BytesIO(uploaded_file_bytes))
    if report_mode == "Certificate Only":
        render_certificate_only_report(raw, uploaded_file, current_library_key)
        st.markdown("""<div style='margin-top: 1rem; padding-top: 1.5rem; border-top: 1px solid #e2e8f0; font-family: DM Mono, monospace; font-size: 0.6rem; color: #94a3b8; letter-spacing: 0.15em; text-transform: uppercase; text-align: center;'>R-Cube Screening Metric · EDXSO Strategic Intelligence · Certificate Tool</div>""", unsafe_allow_html=True)
        return
    survey_kind = infer_single_survey_kind(raw)
    if survey_kind in {"pre_assessment", "post_assessment"}:
        date_col = find_date_column(raw)
        default_certificate_date = ""
        if date_col is not None and date_col in raw.columns and not raw.empty:
            default_certificate_date = format_event_date(raw.iloc[0][date_col])
        inferred_event_name = infer_event_name_from_source_name(uploaded_file.name)
        event_name_state_key = f"certificate_event_name_{current_library_key}"
        event_date_state_key = f"certificate_event_date_{current_library_key}"
        with st.sidebar:
            st.markdown("---")
            st.markdown(
                """
                <div style='font-family: DM Mono, monospace; font-size: 0.7rem; color: #64748b; letter-spacing: 0.2em; text-transform: uppercase; margin-bottom: 0.5rem;'>
                    Certificate Details
                </div>
                """,
                unsafe_allow_html=True,
            )
            certificate_event_name = st.text_input(
                "Certificate Event Name",
                value=st.session_state.get(event_name_state_key, inferred_event_name),
                help="Used in certificate PDFs and certificate emails for this uploaded survey.",
            )
            certificate_event_date = st.text_input(
                "Certificate Event Date",
                value=st.session_state.get(event_date_state_key, default_certificate_date),
                help="Used in certificate PDFs and certificate emails for this uploaded survey.",
            )
        st.session_state[event_name_state_key] = certificate_event_name
        st.session_state[event_date_state_key] = certificate_event_date
        render_assessment_single_report(
            raw,
            uploaded_file,
            current_library_key,
            survey_kind,
            certificate_overrides={
                "event_name": certificate_event_name,
                "event_date": certificate_event_date,
            },
        )
        st.markdown("""<div style='margin-top: 1rem; padding-top: 1.5rem; border-top: 1px solid #e2e8f0; font-family: DM Mono, monospace; font-size: 0.6rem; color: #94a3b8; letter-spacing: 0.15em; text-transform: uppercase; text-align: center;'>R-Cube Screening Metric · EDXSO Strategic Intelligence · Screening Tool</div>""", unsafe_allow_html=True)
        return

    results = prepare_results(raw)
    status_col = find_column_name(raw, ["status", "mail status", "email status"])
    pending_count = (
        raw[status_col].astype(str).str.strip().eq("Pending").sum()
        if status_col is not None
        else len(raw)
    )
    with st.sidebar:
        st.markdown("---")
        user_choice = st.selectbox("Select User Report", results['UserID'].tolist())
        st.caption(f"Uploaded list rows: {len(results)}")
        st.caption(f"Pending email rows: {pending_count}")
        st.caption("Bulk email is available in the Email Delivery tab.")
        with st.expander("Scoring model"):
            st.markdown("""
            <div style='font-size: 0.82rem; color: #64748b; line-height: 1.7;'>
            <b style='color:#d97706;'>Relevance</b> — Q1,2,5,11,13,14<br>
            <b style='color:#2563eb;'>Reliability</b> — Q3,4,6-10,12,14,15<br>
            <b style='color:#7c3aed;'>Reputability</b> — Q16–20<br><br>
            <span style='background: #f1f5f9; padding: 2px 4px; border-radius:4px; color:#0f172a;'>GI = 0.35·R + 0.40·Rel + 0.25·Rep</span>
            </div>
            """, unsafe_allow_html=True)

    row = results[results['UserID'] == user_choice].iloc[0]
    label, badge_cls, desc = get_strategic_profile(row)
    avg_gi = results['Growth_Index'].mean()
    rank = int(results['Growth_Index'].rank(ascending=False)[results['UserID'] == user_choice].values[0])
    single_existing_pdf = st.session_state.generated_pdfs.get(user_choice)
    saved_pdf_count = len(st.session_state.generated_pdfs)

    render_panel_header(
        "Single Report",
        "Survey Response Workspace",
        "Review one individual at a time, build PDFs in bulk, and handle email delivery from dedicated tabs instead of one long page.",
    )
    top_a, top_b, top_c, top_d = st.columns(4)
    with top_a:
        render_small_metric("Participants", len(results))
    with top_b:
        single_progress_panel = st.empty()
        render_progress_metric(single_progress_panel, saved_pdf_count, len(results))
    with top_c:
        render_small_metric("Pending Emails", pending_count)
    with top_d:
        render_small_metric("Cohort Avg GI", f"{avg_gi:.1f}")

    report_tab, pdf_tab, email_tab = st.tabs(["Report", "PDF Library", "Email Delivery"])

    with report_tab:
        action_col, helper_col = st.columns([1.2, 1])
        report_status_panel = st.empty()
        with action_col:
            generate_single_pdf = False
            if single_existing_pdf and Path(single_existing_pdf["file_path"]).exists():
                st.download_button(
                    "Download Compiled PDF",
                    Path(single_existing_pdf["file_path"]).read_bytes(),
                    single_existing_pdf["file_name"],
                    "application/pdf",
                    use_container_width=True,
                    key=f"download_compiled_{user_choice}",
                )
            else:
                generate_single_pdf = st.button(
                    "Compile Selected PDF",
                    type="primary",
                    use_container_width=True,
                )
        with helper_col:
            render_info_card(
                "Current Selection",
                f"Previewing <b>{row['Display_Name']}</b>. Use this tab when you want to inspect one person first, then create a PDF for that person only.",
            )

        st.markdown(f"""
        <div style='margin-bottom: 0.5rem; margin-top: 2rem;'>
            <div style='font-family: DM Mono, monospace; font-size: 0.7rem; color: #64748b; letter-spacing: 0.2em; text-transform: uppercase; margin-bottom: 0.3rem;'>
                Individual Strategic Report
            </div>
            <div style='font-family: Playfair Display, serif; font-size: 2.8rem; font-weight: 900; color: #0f172a; line-height: 1.1; margin-bottom: 0.6rem;'>
                {row['Display_Name']}
            </div>
        </div>
        """, unsafe_allow_html=True)

        k_left, k_right = st.columns([1, 1.45])
        with k_left:
            st.markdown(kpi_card("Growth Index", row['Growth_Index'], "growth", "growth"), unsafe_allow_html=True)
        with k_right:
            st.plotly_chart(sigmoid_position_chart(row['Growth_Index']), width='stretch')

        st.markdown(f"""<div class="status-row"><span class="status-badge {badge_cls}">{label}</span><span class="badge-desc">{desc}</span></div><br>""", unsafe_allow_html=True)
        st.markdown(section_header("01", "R-Cube Maturity Gauges"), unsafe_allow_html=True)
        g1, g2, g3 = st.columns(3)
        with g1:
            st.plotly_chart(gauge_chart(row['Relevance'], "RELEVANCE", "#d97706"), width='stretch')
        with g2:
            st.plotly_chart(gauge_chart(row['Reliability_Adj'], "RELIABILITY (ADJ)", "#2563eb"), width='stretch')
        with g3:
            st.plotly_chart(gauge_chart(row['Reputability_Adj'], "REPUTABILITY (ADJ)", "#7c3aed"), width='stretch')

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown(score_explanation_html(), unsafe_allow_html=True)
        st.markdown(section_header("02", "Growth Stage Profile"), unsafe_allow_html=True)
        col_a, col_b = st.columns([1, 1])
        with col_a:
            st.markdown(stage_bar_html(row), unsafe_allow_html=True)
        with col_b:
            st.plotly_chart(radar_chart(row), width='stretch')
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown(growth_stage_focus_html(), unsafe_allow_html=True)
        st.markdown("<hr>", unsafe_allow_html=True)

        if generate_single_pdf:
            report_status_panel.info(f"Compiling PDF for {row['Display_Name']}...")
            with st.spinner("Spinning up Playwright rendering engine..."):
                try:
                    st.session_state.pdf_progress = {
                        "current": 1,
                        "total": 1,
                        "message": f"Generating selected PDF: {row['Display_Name']}",
                        "active": True,
                    }
                    pdf_bytes = generate_user_pdf_playwright(row)
                    contact = get_row_contact_details(raw, results, user_choice)
                    certificate = get_row_certificate_details(raw, results, user_choice)
                    file_name = build_pdf_filename(user_choice, certificate.get("event_name", ""))
                    st.session_state.generated_pdfs[user_choice] = save_generated_pdf_record(
                        user_choice,
                        file_name,
                        pdf_bytes,
                        st.session_state.current_library_key,
                        email=contact["email"],
                        name=contact["name"],
                        school=certificate.get("school", ""),
                        event_date=certificate.get("event_date", ""),
                        phone=certificate.get("phone", ""),
                        event_name=certificate.get("event_name", ""),
                    )
                    persist_generated_pdf_library(
                        st.session_state.generated_pdfs,
                        st.session_state.current_library_key,
                    )
                    st.session_state.pdf_progress = {
                        "current": 1,
                        "total": 1,
                        "message": f"Generated selected PDF: {row['Display_Name']}",
                        "active": False,
                    }
                    report_status_panel.success(f"Compiled PDF for {row['Display_Name']}.")
                    st.success("PDF rendered successfully!")
                    st.rerun()
                except Exception as e:
                    st.session_state.pdf_progress = {
                        "current": 0,
                        "total": 1,
                        "message": f"Selected PDF failed: {e}",
                        "active": False,
                    }
                    report_status_panel.error(f"PDF compile failed for {row['Display_Name']}: {e}")
                    st.error(f"Render failed: {e}")

    with pdf_tab:
        pdf_progress_panel = st.empty()
        pdf_status_panel = st.empty()
        pdf_log_panel = st.empty()
        generated_list_panel = st.empty()
        st.markdown(section_header("02", "PDF Library"), unsafe_allow_html=True)
        action_left, action_mid, action_right = st.columns([1, 1, 1])
        with action_left:
            generate_all_pdfs = st.button("Generate PDFs For All Rows", use_container_width=True)
        with action_mid:
            clear_generated_pdfs = st.button("Clear Generated PDF List", use_container_width=True)
        with action_right:
            render_info_card(
                "Library Scope",
                "This library is tied to the currently uploaded CSV only. Running batch generation rebuilds the full survey set from scratch so the saved count always stays aligned.",
            )

        st.caption(f"Rows available in uploaded CSV: {len(results)}")
        if st.session_state.pdf_progress["total"]:
            progress_total = max(st.session_state.pdf_progress["total"], 1)
            progress_current = min(st.session_state.pdf_progress["current"], progress_total)
            pdf_progress_panel.progress(
                progress_current / progress_total,
                text=f"Generating PDFs: {progress_current}/{progress_total}",
            )
            if st.session_state.pdf_progress["message"]:
                if st.session_state.pdf_progress["active"]:
                    pdf_status_panel.info(st.session_state.pdf_progress["message"])
                else:
                    pdf_status_panel.success(st.session_state.pdf_progress["message"])

        if clear_generated_pdfs:
            st.session_state.generated_pdfs = {}
            st.session_state.pdf_batch_log = []
            st.session_state.pdf_progress = {"current": 0, "total": 0, "message": "", "active": False}
            clear_generated_pdf_library(st.session_state.current_library_key)
            render_progress_metric(single_progress_panel, 0, len(results))
            st.success("Cleared generated PDF list.")

        if generate_all_pdfs:
            total_reports = len(results)
            st.session_state.generated_pdfs = {}
            clear_generated_pdf_library(st.session_state.current_library_key)
            render_progress_metric(single_progress_panel, 0, total_reports)
            batch_log = []
            generated_count = 0

            for position, (_, report_row) in enumerate(results.iterrows(), start=1):
                current_name = resolve_record_display_name(report_row, fallback=f"User {position}")
                st.session_state.pdf_progress = {
                    "current": position,
                    "total": total_reports,
                    "message": f"Generating {position}/{total_reports}: {current_name}",
                    "active": True,
                }
                pdf_progress_panel.progress(position / total_reports, text=f"Generating PDFs: {position}/{total_reports}")
                pdf_status_panel.info(st.session_state.pdf_progress["message"])
                try:
                    pdf_bytes = generate_user_pdf_playwright(report_row)
                    pdf_user = report_row["UserID"]
                    contact = get_row_contact_details(raw, results, pdf_user)
                    certificate = get_row_certificate_details(raw, results, pdf_user)
                    st.session_state.generated_pdfs[pdf_user] = save_generated_pdf_record(
                        pdf_user,
                        build_pdf_filename(current_name, certificate.get("event_name", "")),
                        pdf_bytes,
                        st.session_state.current_library_key,
                        email=contact["email"],
                        name=resolve_record_display_name(
                            {"name": contact["name"], "Display_Name": current_name, "email": contact["email"], "UserID": pdf_user},
                            fallback=current_name,
                        ),
                        school=certificate.get("school", ""),
                        event_date=certificate.get("event_date", ""),
                        phone=certificate.get("phone", ""),
                        event_name=certificate.get("event_name", ""),
                    )
                    persist_generated_pdf_library(
                        st.session_state.generated_pdfs,
                        st.session_state.current_library_key,
                    )
                    generated_count += 1
                    render_progress_metric(single_progress_panel, generated_count, total_reports)
                    batch_log.append(f"{position}/{total_reports} generated: {current_name}")
                except Exception as e:
                    render_progress_metric(single_progress_panel, generated_count, total_reports)
                    batch_log.append(f"{position}/{total_reports} failed: {current_name} ({e})")

            st.session_state.pdf_batch_log = batch_log
            st.session_state.pdf_progress = {
                "current": total_reports,
                "total": total_reports,
                "message": f"Generated {generated_count}/{total_reports} PDF(s).",
                "active": False,
            }
            pdf_progress_panel.progress(1.0, text=f"Generating PDFs: {total_reports}/{total_reports}")
            pdf_status_panel.success(st.session_state.pdf_progress["message"])

        if st.session_state.pdf_batch_log:
            with pdf_log_panel.container():
                for line in st.session_state.pdf_batch_log[-10:]:
                    st.write(f"- {line}")

        render_generated_pdf_library(
            generated_list_panel,
            report_type="single",
            current_dataset={
                "raw": raw,
                "results": results,
                "certificate_overrides": certificate_overrides,
            },
        )

    with email_tab:
        email_progress_panel = st.empty()
        email_status_panel = st.empty()
        email_log_panel = st.empty()
        st.markdown(section_header("03", "Email Delivery"), unsafe_allow_html=True)
        email_action_col, email_help_col = st.columns([1, 1.1])
        with email_action_col:
            send_pending_emails = st.button("Send Bulk Emails", use_container_width=True)
        with email_help_col:
            render_info_card(
                "Batch Sender",
                "This tab sends PDFs as email attachments for all rows marked <b>Pending</b> in the uploaded CSV. Progress stays visible here while the bulk run is in progress.",
            )
        metric_a, metric_b = st.columns(2)
        with metric_a:
            render_small_metric("Pending Rows", pending_count)
        with metric_b:
            render_small_metric("Email Mode", "Bulk Send")

        if send_pending_emails:
            with st.spinner("Generating PDFs and sending emails..."):
                try:
                    from send_pending_reports import send_pending_reports_from_dataframe

                    total_targets = pending_count
                    email_progress = email_progress_panel.progress(
                        0,
                        text=f"Sending emails: 0/{total_targets}" if total_targets else "Sending emails: 0/0",
                    )

                    def update_email_progress(current, total, name, phase):
                        total = max(total, 1)
                        phase_label = {
                            "sending": "Sending",
                            "sent": "Sent",
                            "error": "Failed",
                        }.get(phase, "Sending")
                        email_status_panel.info(f"{current}/{total}: {phase_label} {name}")
                        email_progress.progress(current / total, text=f"Sending emails: {current}/{total}")

                    run_log = send_pending_reports_from_dataframe(raw, progress_callback=update_email_progress)
                    success_count = sum(1 for item in run_log if item["status"] == "success")
                    error_count = sum(1 for item in run_log if item["status"] == "error")
                    st.session_state.email_batch_log = [item["message"] for item in run_log]

                    if success_count:
                        st.success(f"Sent {success_count} email(s).")
                    if error_count:
                        st.error(f"{error_count} email(s) failed.")
                    if not success_count and not error_count and run_log:
                        st.info(run_log[0]["message"])
                    email_status_panel.success(f"Completed email run: {success_count} sent, {error_count} failed.")
                except Exception as e:
                    st.error(f"Email sending failed: {e}")

        if st.session_state.email_batch_log:
            st.markdown("**Recent Email Activity**")
            with email_log_panel.container():
                for line in st.session_state.email_batch_log[-10:]:
                    st.write(f"- {line}")

    st.markdown("""<div style='margin-top: 1rem; padding-top: 1.5rem; border-top: 1px solid #e2e8f0; font-family: DM Mono, monospace; font-size: 0.6rem; color: #94a3b8; letter-spacing: 0.15em; text-transform: uppercase; text-align: center;'>R-Cube Screening Metric · EDXSO Strategic Intelligence · Screening Tool</div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    run_app()

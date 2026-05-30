import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import base64
import io
import sys
import asyncio
import warnings
import os

@st.cache_resource
def install_playwright():
    """Forces the Streamlit server to download the Chromium binary and dependencies on boot."""
    # Installs the browser
    os.system("playwright install chromium")
    # Installs the required Linux system dependencies for the browser
    # os.system("playwright install-deps chromium")

install_playwright()

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

from playwright.sync_api import sync_playwright
import plotly.io as pio

# ─────────────────────────────────────────────
#  STREAMLIT CLOUD PLAYWRIGHT INSTALLER
# ─────────────────────────────────────────────
# This forces the Streamlit server to download the Chromium binary on boot
@st.cache_resource
def install_playwright():
    os.system("playwright install chromium")

# ─────────────────────────────────────────────
#  WINDOWS EVENT LOOP FIX (WITH WARNING MUTE)
# ─────────────────────────────────────────────
if sys.platform == "win32":
    # Mute the Python 3.14+ deprecation warnings to keep the console clean
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=DeprecationWarning)
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except AttributeError:
            pass # Failsafe just in case it gets fully removed in a future test build

# ─────────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="R-Cube Strategic Intelligence",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
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
"""

st.markdown(f"<style>{CUSTOM_CSS}</style>", unsafe_allow_html=True)
 
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
    fig.update_layout(width=w, height=h, margin=dict(l=0, r=0, t=30, b=0)) # Tighten margins
    # include_plotlyjs='cdn' pulls the rendering library directly into the HTML
    return fig.to_html(full_html=False, include_plotlyjs='cdn')

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
        '<div class="explain-wrap"><div class="explain-head">Teacher&#39;s Individual Dashboard</div><div class="explain-sub">How Your Scores Are Calculated</div><div class="explain-grid">'
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
    
    # 2. Inject the HTML directly (No <img> tags needed!)
    pdf_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            {CUSTOM_CSS}
            html, body {{ margin: 0 !important; padding: 0 !important; background: #ffffff; }}
            .pdf-container {{ padding: 50px; width: 100%; box-sizing: border-box; }}
            * {{ page-break-inside: avoid !important; page-break-before: auto !important; page-break-after: auto !important; }}
            .kpi-row {{ display: flex; gap: 20px; margin-bottom: 25px; align-items: stretch; }}
            .kpi-col {{ flex: 1; display: flex; flex-direction: column; }}
            .chart-col {{ flex: 1.5; display: flex; justify-content: center; align-items: center; border: 1px solid #e2e8f0; border-radius: 12px; }}
            .gauge-row {{ display: flex; justify-content: space-around; margin-top: 15px; margin-bottom: 25px; width: 100%; }}
            .gauge-item {{ width: 32%; }}
        </style>
    </head>
    <body>
        <div class="pdf-container">
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
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--single-process"]
        )
        context = browser.new_context()
        page = context.new_page()
        
        # networkidle ensures Playwright waits for Plotly CDN to download and render
        page.set_content(pdf_html, wait_until="networkidle")
        
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

# ─────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────
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
 
    uploaded_file = st.file_uploader("Upload Response CSV", type=["csv"])
 
    st.markdown("---")
    st.markdown("""
    <div style='font-family: DM Mono, monospace; font-size: 0.6rem; color: #475569; letter-spacing: 0.1em; text-transform: uppercase;'>
    Scoring Model
    </div>
    <div style='font-size: 0.78rem; color: #64748b; margin-top: 0.5rem; line-height: 1.6;'>
    <b style='color:#d97706;'>Relevance</b> — Q1,2,5,11,13,14<br>
    <b style='color:#2563eb;'>Reliability</b> — Q3,4,6-10,12,14,15<br>
    <b style='color:#7c3aed;'>Reputability</b> — Q16–20<br><br>
    <span style='background: #f1f5f9; padding: 2px 4px; border-radius:4px; color:#0f172a;'>GI = 0.35·R + 0.40·Rel + 0.25·Rep</span>
    </div>
    """, unsafe_allow_html=True)
 
# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
if not uploaded_file:
    st.markdown("""
    <div style='display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 70vh; text-align: center; padding: 2rem;'>
        <div style='font-family: Playfair Display, serif; font-size: 3.5rem; font-weight: 900; color: #0f172a; line-height: 1.1; max-width: 700px;'>
            R-Cube Strategic<br>Command Centre
        </div>
        <div style='font-family: DM Sans, sans-serif; font-size: 1.1rem; color: #475569; margin-top: 1rem; max-width: 480px; line-height: 1.7;'>
            Upload your response CSV to generate per-user strategic profiles, maturity-adjusted R-scores, and stage diagnostics.
        </div>
        <div style='margin-top: 2.5rem; font-family: DM Mono, monospace; font-size: 0.7rem; font-weight: 600; letter-spacing: 0.2em; text-transform: uppercase; color: #334155; border: 1px dashed #cbd5e1; background: #ffffff; padding: 0.75rem 1.5rem; border-radius: 8px;'>
            ← Upload CSV in sidebar to begin
        </div>
    </div>
    """, unsafe_allow_html=True)
 
else:
    raw = pd.read_csv(uploaded_file)
    q_cols = raw.columns[8:28]
    raw = raw.rename(columns={q_cols[i]: f'Q{i+1}' for i in range(len(q_cols))})
    # --- START NEW NAME EXTRACTION LOGIC ---
    if 'name' in raw.columns:
        raw_names = raw['name'].fillna("Unknown").astype(str).tolist()
    else:
        try:
            raw_names = raw.iloc[:, 29].fillna("Unknown").astype(str).tolist()
        except IndexError:
            raw_names = [f"User {i+1}" for i in range(len(raw))]
            
    # Clean names for the PDF (e.g., "John Doe")
    display_names = [name.title().strip() for name in raw_names]
            
    # Unique IDs for the Streamlit dropdown (e.g., "John Doe (2)")
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
    # --- END NEW NAME EXTRACTION LOGIC ---
    
    for i in range(1, 21): raw[f'Q{i}'] = raw[f'Q{i}'].map(RESPONSE_MAP).fillna(3)
 
    results = calculate_metrics(raw)
 
    # ── Sidebar: User Slicer
    with st.sidebar:
        st.markdown("---")
        user_choice = st.selectbox("Select User Report", results['UserID'].tolist())
        
        st.markdown(f"""
        <div style='font-family: DM Mono, monospace; font-size: 0.6rem; color: #64748b; letter-spacing: 0.1em; text-transform: uppercase; margin-top: 1rem;'>Cohort Size</div>
        <div style='font-family: Playfair Display, serif; font-size: 2rem; font-weight: 900; color: #0f172a;'>{len(results)}</div>
        """, unsafe_allow_html=True)
 
        avg_gi = results['Growth_Index'].mean()
        rank   = int(results['Growth_Index'].rank(ascending=False)[results['UserID'] == user_choice].values[0])
        st.markdown(f"""
        <div style='margin-top: 1rem;'><div style='font-family: DM Mono, monospace; font-size: 0.6rem; color: #64748b; letter-spacing: 0.1em; text-transform: uppercase;'>Cohort Avg GI</div><div style='font-family: Playfair Display, serif; font-size: 1.6rem; font-weight: 900; color: #0f172a;'>{avg_gi:.1f}</div></div>
        <div style='margin-top: 1rem;'><div style='font-family: DM Mono, monospace; font-size: 0.6rem; color: #64748b; letter-spacing: 0.1em; text-transform: uppercase;'>Current Rank</div><div style='font-family: Playfair Display, serif; font-size: 1.6rem; font-weight: 900; color: #059669;'>#{rank} / {len(results)}</div></div>
        """, unsafe_allow_html=True)
 
    row = results[results['UserID'] == user_choice].iloc[0]
    label, badge_cls, desc = get_strategic_profile(row)
    
    # ════════════════════════════════════
    #  HEADER
    # ════════════════════════════════════
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
 
    # ════════════════════════════════════
    #  KPI + POSITION CURVE
    # ════════════════════════════════════
    k_left, k_right = st.columns([1, 1.45])
    with k_left: st.markdown(kpi_card("Growth Index", row['Growth_Index'], "growth", "growth"), unsafe_allow_html=True)
    with k_right: st.plotly_chart(sigmoid_position_chart(row['Growth_Index']), width='stretch')

    st.markdown(f"""<div class="status-row"><span class="status-badge {badge_cls}">{label}</span><span class="badge-desc">{desc}</span></div><br>""", unsafe_allow_html=True)

    # ════════════════════════════════════
    #  SECTION 1 — R-Score Gauges
    # ════════════════════════════════════
    st.markdown(section_header("01", "R-Cube Maturity Gauges"), unsafe_allow_html=True)

    g1, g2, g3 = st.columns(3)
    with g1: st.plotly_chart(gauge_chart(row['Relevance'],       "RELEVANCE",       "#d97706"), width='stretch')
    with g2: st.plotly_chart(gauge_chart(row['Reliability_Adj'], "RELIABILITY (ADJ)", "#2563eb"), width='stretch')
    with g3: st.plotly_chart(gauge_chart(row['Reputability_Adj'], "REPUTABILITY (ADJ)", "#7c3aed"), width='stretch')

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(score_explanation_html(), unsafe_allow_html=True)

    # ════════════════════════════════════
    #  SECTION 2 — Stage Profile + Radar
    # ════════════════════════════════════
    st.markdown(section_header("02", "Growth Stage Profile"), unsafe_allow_html=True)

    col_a, col_b = st.columns([1, 1])
    with col_a: st.markdown(stage_bar_html(row), unsafe_allow_html=True)
    with col_b: st.plotly_chart(radar_chart(row), width='stretch')

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(growth_stage_focus_html(), unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)
 
    # ─────────────────────────────────────────────
    #  DYNAMIC PDF EXPORT BUTTON
    # ─────────────────────────────────────────────
    st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
    
    if st.button(f"📄 Compile High-Fidelity PDF for {user_choice}", type="primary"):
        with st.spinner("Spinning up Playwright rendering engine..."):
            try:
                # Pass the row data directly to the new HTML-based Playwright function
                pdf_bytes = generate_user_pdf_playwright(row)
                
                st.success("PDF rendered successfully!")
                
                st.download_button(
                    label="⬇️ Download PDF",
                    data=pdf_bytes,
                    file_name=f"RCube_Report_{user_choice.replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"Render failed: {e}")
        
    st.markdown("""<div style='margin-top: 1rem; padding-top: 1.5rem; border-top: 1px solid #e2e8f0; font-family: DM Mono, monospace; font-size: 0.6rem; color: #94a3b8; letter-spacing: 0.15em; text-transform: uppercase; text-align: center;'>R-Cube Screening Metric · EDXSO Strategic Intelligence · Screening Tool</div>""", unsafe_allow_html=True)
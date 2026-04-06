import copy
import streamlit as st

# ── Palette ───────────────────────────────────────────────────────────────────
BLUE   = "#3b82f6"
GREEN  = "#10b981"
RED    = "#ef4444"
PURPLE = "#8b5cf6"
AMBER  = "#f59e0b"
CYAN   = "#06b6d4"
SLATE  = "#1e293b"
CARD   = "#0f172a"
MUTED  = "#475569"

CHART_COLORS = [BLUE, GREEN, PURPLE, AMBER, CYAN, RED, "#ec4899", "#14b8a6", "#f97316"]


def theme_colors() -> dict:
    """Return a dict of theme-appropriate colors for Plotly charts & inline HTML.

    Call once at the top of each tab's render() function:
        tc = theme_colors()
    Then use tc["text"], tc["muted"], tc["card"], etc.
    """
    light = st.session_state.get("theme") == "light"
    return {
        # Text hierarchy (for Plotly textfont, annotations, labels)
        "text":       "#1e293b" if light else "#e2e8f0",
        "bright":     "#0f172a" if light else "#f1f5f9",
        "secondary":  "#334155" if light else "#cbd5e1",
        "muted":      "#64748b" if light else "#94a3b8",
        "faint":      "#94a3b8" if light else "#64748b",
        "subtle":     "#475569" if light else "#475569",
        # Backgrounds
        "card":       "#ffffff" if light else "#0f172a",
        "app":        "#f8fafc" if light else "#020817",
        "input":      "#f1f5f9" if light else "#111827",
        # Borders & lines
        "border":     "rgba(0,0,0,0.10)" if light else "rgba(255,255,255,0.07)",
        "grid":       "rgba(0,0,0,0.06)" if light else "rgba(255,255,255,0.05)",
        "zeroline":   "rgba(0,0,0,0.15)" if light else "rgba(255,255,255,0.15)",
        "connector":  "rgba(0,0,0,0.10)" if light else "rgba(255,255,255,0.10)",
        # Chart-specific
        "pie_border": "#ffffff" if light else "#020817",
        "target_bar": "rgba(0,0,0,0.10)" if light else "rgba(255,255,255,0.15)",
        "heatmap_bg": "rgba(248,250,252,1)" if light else "rgba(15,23,42,1)",
        "sankey_link":"rgba(0,0,0,0.06)" if light else "rgba(255,255,255,0.06)",
    }

# ── Base Plotly theme (nested dicts — use chart_layout() to merge safely) ─────
_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#cbd5e1", family="'Barlow', sans-serif", size=12),
    title=dict(text="", font=dict(color="#e2e8f0", size=14, family="'Barlow', sans-serif"), x=0.01),
    xaxis=dict(
        gridcolor="rgba(255,255,255,0.05)",
        zerolinecolor="rgba(255,255,255,0.15)",
        zerolinewidth=1,
        linecolor="rgba(255,255,255,0.06)",
        tickfont=dict(size=11),
        automargin=True,
    ),
    yaxis=dict(
        gridcolor="rgba(255,255,255,0.05)",
        zerolinecolor="rgba(255,255,255,0.15)",
        zerolinewidth=1,
        linecolor="rgba(255,255,255,0.06)",
        tickfont=dict(size=11),
        automargin=True,
    ),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        bordercolor="rgba(255,255,255,0.07)",
        font=dict(size=11, color="#cbd5e1"),
    ),
    hoverlabel=dict(
        bgcolor="#1e293b",
        bordercolor="#334155",
        font=dict(color="#f1f5f9", size=12, family="'Barlow', sans-serif"),
    ),
    margin=dict(l=20, r=90, t=48, b=20),
    colorway=CHART_COLORS,
)

# Keep for backward compat with any module still referencing PLOTLY_LAYOUT
PLOTLY_LAYOUT = _BASE


_LIGHT_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#334155", family="'Barlow', sans-serif", size=12),
    title=dict(text="", font=dict(color="#1e293b", size=14, family="'Barlow', sans-serif"), x=0.01),
    xaxis=dict(
        gridcolor="rgba(0,0,0,0.06)",
        zerolinecolor="rgba(0,0,0,0.15)",
        zerolinewidth=1,
        linecolor="rgba(0,0,0,0.08)",
        tickfont=dict(size=11, color="#475569"),
        automargin=True,
    ),
    yaxis=dict(
        gridcolor="rgba(0,0,0,0.06)",
        zerolinecolor="rgba(0,0,0,0.15)",
        zerolinewidth=1,
        linecolor="rgba(0,0,0,0.08)",
        tickfont=dict(size=11, color="#475569"),
        automargin=True,
    ),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        bordercolor="rgba(0,0,0,0.08)",
        font=dict(size=11, color="#475569"),
    ),
    hoverlabel=dict(
        bgcolor="#ffffff",
        bordercolor="#e2e8f0",
        font=dict(color="#1e293b", size=12, family="'Barlow', sans-serif"),
    ),
    margin=dict(l=20, r=90, t=48, b=20),
    colorway=CHART_COLORS,
)


def chart_layout(**overrides) -> dict:
    """Return a Plotly layout dict deep-merged with the theme base.

    Automatically selects dark or light base depending on session state.
    Nested dicts (xaxis, yaxis, legend, margin, font, title, hoverlabel)
    are merged key-by-key so partial overrides don't wipe base settings.
    """
    is_light = st.session_state.get("theme") == "light"
    base = copy.deepcopy(_LIGHT_BASE if is_light else _BASE)
    _NESTED = {"xaxis", "yaxis", "legend", "margin", "font", "title", "hoverlabel"}
    for key, val in overrides.items():
        if key == "title" and isinstance(val, str):
            base["title"] = {**base.get("title", {}), "text": val}
        elif key in _NESTED and isinstance(base.get(key), dict) and isinstance(val, dict):
            base[key] = {**base[key], **val}
        else:
            base[key] = val
    return base


def inject_css() -> None:
    theme = st.session_state.get("theme", "dark")
    _light_overrides = ""
    if theme == "light":
        _light_overrides = """
        /* ══ LIGHT MODE — full override ══════════════════════════════════════ */

        /* ── App / page background ─────────────────────────────────────────── */
        .stApp { background: #f8fafc !important; }

        /* ── Headings ──────────────────────────────────────────────────────── */
        h1 { color: #1e293b !important; border-bottom-color: rgba(0,0,0,0.1) !important; }
        h2 { color: #334155 !important; }
        h3 { color: #475569 !important; }

        /* ── Sidebar ───────────────────────────────────────────────────────── */
        [data-testid="stSidebar"] { background: #f1f5f9 !important; border-right-color: #e2e8f0 !important; }
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label { color: #334155 !important; }

        /* ── Metric cards ──────────────────────────────────────────────────── */
        [data-testid="metric-container"] { background: #ffffff !important; border-color: #e2e8f0 !important; box-shadow: 0 1px 3px rgba(0,0,0,0.08) !important; }
        [data-testid="metric-container"] label { color: #64748b !important; }
        [data-testid="metric-container"] [data-testid="stMetricValue"] { color: #1e293b !important; }

        /* ── Tabs ──────────────────────────────────────────────────────────── */
        [data-testid="stTabs"] [role="tablist"] { border-bottom-color: rgba(0,0,0,0.08) !important; }
        [data-testid="stTabs"] button[role="tab"] { color: #94a3b8 !important; }
        [data-testid="stTabs"] button[role="tab"]:hover { color: #334155 !important; }
        [data-testid="stTabs"] button[role="tab"][aria-selected="true"] { color: #1e293b !important; }

        /* ── Expanders ─────────────────────────────────────────────────────── */
        details { background: #ffffff !important; border-color: #e2e8f0 !important; }
        details summary { color: #334155 !important; }

        /* ── Inputs / selects ──────────────────────────────────────────────── */
        input, select, textarea { background: #ffffff !important; border-color: #cbd5e1 !important; color: #1e293b !important; }
        [data-testid="stNumberInput"] label,
        [data-testid="stTextInput"] label,
        [data-testid="stSelectbox"] label,
        [data-testid="stSlider"] label,
        [data-testid="stDateInput"] label { color: #64748b !important; }

        /* ── Buttons ───────────────────────────────────────────────────────── */
        [data-testid="stButton"] button { background: #f1f5f9 !important; border-color: #cbd5e1 !important; color: #334155 !important; }
        [data-testid="stButton"] button:hover { background: #3b82f6 !important; color: white !important; }

        /* ── Containers (border=True) ──────────────────────────────────────── */
        [data-testid="stVerticalBlock"] [data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff !important; border-color: #e2e8f0 !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
        }

        /* ── Dividers ──────────────────────────────────────────────────────── */
        hr { border-color: rgba(0,0,0,0.08) !important; }

        /* ── Progress bars ─────────────────────────────────────────────────── */
        [data-testid="stProgress"] > div > div { background: #e2e8f0 !important; }

        /* ── DataFrames ────────────────────────────────────────────────────── */
        [data-testid="stDataFrame"] { border-color: #e2e8f0 !important; }

        /* ── Alert boxes ───────────────────────────────────────────────────── */
        [data-testid="stSuccess"] { background: rgba(16,185,129,0.06) !important; border-color: rgba(16,185,129,0.2) !important; color: #059669 !important; }
        [data-testid="stWarning"] { background: rgba(245,158,11,0.06) !important; border-color: rgba(245,158,11,0.2) !important; color: #d97706 !important; }
        [data-testid="stError"]   { background: rgba(239,68,68,0.06) !important; border-color: rgba(239,68,68,0.2) !important; color: #dc2626 !important; }
        [data-testid="stInfo"]    { background: rgba(59,130,246,0.06) !important; border-color: rgba(59,130,246,0.2) !important; color: #2563eb !important; }

        /* ── KPI card HTML ─────────────────────────────────────────────────── */
        .kpi-card { background: linear-gradient(160deg, #ffffff 0%, #f8fafc 100%) !important;
                    border-color: #e2e8f0 !important; box-shadow: 0 1px 3px rgba(0,0,0,0.08) !important; }
        .kpi-label { color: #64748b !important; }
        .kpi-value { color: #1e293b !important; }
        .kpi-sub   { color: #64748b !important; }

        /* ── Section header ────────────────────────────────────────────────── */
        .section-header { color: #64748b !important; border-bottom-color: rgba(0,0,0,0.06) !important; }

        /* ── Badge chips ───────────────────────────────────────────────────── */
        .badge-green { background: rgba(16,185,129,0.1) !important; color: #059669 !important; }
        .badge-red   { background: rgba(239,68,68,0.1) !important; color: #dc2626 !important; }
        .badge-amber { background: rgba(245,158,11,0.1) !important; color: #d97706 !important; }
        .badge-blue  { background: rgba(59,130,246,0.1) !important; color: #2563eb !important; }

        /* ── Streamlit markdown / caption text ─────────────────────────────── */
        .stMarkdown, .stMarkdown p, .stCaption, [data-testid="stText"] { color: #334155 !important; }

        /* ══ INLINE HTML OVERRIDES ═══════════════════════════════════════════
           The tab files use inline style="color:#xxx" for dark-theme text.
           CSS !important on attribute selectors beats inline styles.
           ════════════════════════════════════════════════════════════════════ */

        /* Primary text — near-white → near-black */
        [style*="color:#f1f5f9"] { color: #0f172a !important; }
        [style*="color:#e2e8f0"] { color: #1e293b !important; }
        [style*="color: #f1f5f9"] { color: #0f172a !important; }
        [style*="color: #e2e8f0"] { color: #1e293b !important; }

        /* Secondary text */
        [style*="color:#cbd5e1"] { color: #334155 !important; }
        [style*="color: #cbd5e1"] { color: #334155 !important; }

        /* Muted text */
        [style*="color:#94a3b8"] { color: #64748b !important; }
        [style*="color: #94a3b8"] { color: #64748b !important; }

        /* Subtle text */
        [style*="color:#64748b"] { color: #475569 !important; }
        [style*="color: #64748b"] { color: #475569 !important; }
        [style*="color:#475569"] { color: #64748b !important; }
        [style*="color: #475569"] { color: #64748b !important; }

        /* ── Inline dark backgrounds → light ───────────────────────────────── */
        [style*="background:#0f172a"] { background: #e2e8f0 !important; }
        [style*="background:#0d1526"] { background: #f1f5f9 !important; }
        [style*="background:#111827"] { background: #f1f5f9 !important; }
        [style*="background:#020817"] { background: #f8fafc !important; }
        [style*="background:#1e293b"] { background: #e2e8f0 !important; }
        [style*="background: #0f172a"] { background: #e2e8f0 !important; }
        [style*="background: #0d1526"] { background: #f1f5f9 !important; }
        [style*="background: #111827"] { background: #f1f5f9 !important; }

        /* ── Inline dark border colors → light ─────────────────────────────── */
        [style*="border-color:rgba(255,255,255"] { border-color: rgba(0,0,0,0.1) !important; }
        [style*="border:1px solid rgba(255,255,255"] { border-color: rgba(0,0,0,0.1) !important; }

        /* ── Inline linear-gradient dark cards → light ─────────────────────── */
        [style*="linear-gradient(160deg, #0d1526"] { background: linear-gradient(160deg, #ffffff 0%, #f8fafc 100%) !important; }
        [style*="linear-gradient(160deg,#0d1526"]  { background: linear-gradient(160deg, #ffffff 0%, #f8fafc 100%) !important; }
        """

    _css = """
<style>
/* ── Fonts — Barlow (BlackRock / McKinsey style geometric sans) ──────────── */
@import url('https://fonts.googleapis.com/css2?family=Barlow:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=Barlow+Condensed:wght@500;600;700&display=swap');

html, body, [class*="css"], [class*="st-"] {
    font-family: 'Barlow', sans-serif !important;
}

/* ── App background ──────────────────────────────────────────────────────── */
.stApp {
    background: #020817;
}

.main .block-container {
    padding-top: 1.5rem;
    padding-bottom: 3rem;
    max-width: 100%;
}

/* ── Headings ────────────────────────────────────────────────────────────── */
h1 {
    font-family: 'Barlow Condensed', sans-serif !important;
    font-size: 1.9rem !important;
    font-weight: 700 !important;
    color: #f1f5f9 !important;
    letter-spacing: -0.01em !important;
    padding-bottom: 0.35rem;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 0 !important;
}

h2 {
    font-family: 'Barlow', sans-serif !important;
    font-size: 1.05rem !important;
    font-weight: 600 !important;
    color: #e2e8f0 !important;
    letter-spacing: 0.01em !important;
}

h3 {
    font-family: 'Barlow', sans-serif !important;
    font-size: 0.92rem !important;
    font-weight: 600 !important;
    color: #cbd5e1 !important;
}

/* ── Streamlit metric cards ──────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background: #0d1526;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px;
    padding: 1rem 1.25rem !important;
    box-shadow: 0 2px 16px rgba(0,0,0,0.35);
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

[data-testid="metric-container"]:hover {
    border-color: rgba(59,130,246,0.3);
    box-shadow: 0 4px 24px rgba(59,130,246,0.12);
}

[data-testid="metric-container"] label {
    font-family: 'Barlow', sans-serif !important;
    color: #94a3b8 !important;
    font-size: 0.65rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
}

[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-family: 'Barlow Condensed', sans-serif !important;
    color: #f1f5f9 !important;
    font-size: 1.75rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.01em !important;
    line-height: 1.1 !important;
}

[data-testid="metric-container"] [data-testid="stMetricDelta"] {
    font-size: 0.72rem !important;
    font-weight: 500 !important;
}

/* ── Tabs ────────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tablist"] {
    border-bottom: 1px solid rgba(255,255,255,0.06) !important;
    gap: 0.1rem;
    background: transparent !important;
}

[data-testid="stTabs"] button[role="tab"] {
    background: transparent !important;
    border: none !important;
    color: #64748b !important;
    font-family: 'Barlow', sans-serif !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.03em !important;
    padding: 0.55rem 1.1rem !important;
    border-radius: 0 !important;
    transition: color 0.15s ease;
}

[data-testid="stTabs"] button[role="tab"]:hover {
    color: #cbd5e1 !important;
}

[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: #e2e8f0 !important;
    border-bottom: 2px solid #3b82f6 !important;
}

/* ── Material icon font — restore for Streamlit icon glyphs ─────────────── */
[data-testid="stIconMaterial"] {
    font-family: 'Material Icons Rounded', 'Material Icons', 'Material Symbols Rounded' !important;
    font-style: normal !important;
    font-weight: 400 !important;
    display: inline-block;
}

/* ── Expanders ───────────────────────────────────────────────────────────── */
details {
    background: #0d1526 !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 10px !important;
    margin-bottom: 0.5rem;
}

details summary {
    color: #cbd5e1 !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    padding: 0.75rem 1rem !important;
    letter-spacing: 0.02em !important;
}

/* ── Inputs ──────────────────────────────────────────────────────────────── */
input, select, textarea {
    background: #111827 !important;
    border: 1px solid rgba(255,255,255,0.09) !important;
    color: #e2e8f0 !important;
    border-radius: 7px !important;
    font-family: 'Barlow', sans-serif !important;
}

input:focus, select:focus {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 2px rgba(59,130,246,0.2) !important;
}

[data-testid="stNumberInput"] label,
[data-testid="stTextInput"] label,
[data-testid="stSelectbox"] label,
[data-testid="stSlider"] label,
[data-testid="stDateInput"] label {
    color: #94a3b8 !important;
    font-family: 'Barlow', sans-serif !important;
    font-size: 0.68rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}

/* ── Buttons ─────────────────────────────────────────────────────────────── */
[data-testid="stButton"] button {
    background: #111827 !important;
    border: 1px solid rgba(255,255,255,0.09) !important;
    color: #94a3b8 !important;
    border-radius: 7px !important;
    font-family: 'Barlow', sans-serif !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em !important;
    transition: all 0.15s ease !important;
}

[data-testid="stButton"] button:hover {
    background: #1d4ed8 !important;
    border-color: #3b82f6 !important;
    color: white !important;
}

/* ── Alert boxes ─────────────────────────────────────────────────────────── */
[data-testid="stSuccess"] {
    background: rgba(16,185,129,0.08) !important;
    border: 1px solid rgba(16,185,129,0.25) !important;
    border-radius: 8px !important;
    color: #6ee7b7 !important;
    font-size: 0.85rem !important;
}

[data-testid="stWarning"] {
    background: rgba(245,158,11,0.08) !important;
    border: 1px solid rgba(245,158,11,0.25) !important;
    border-radius: 8px !important;
    color: #fcd34d !important;
    font-size: 0.85rem !important;
}

[data-testid="stError"] {
    background: rgba(239,68,68,0.08) !important;
    border: 1px solid rgba(239,68,68,0.25) !important;
    border-radius: 8px !important;
    color: #fca5a5 !important;
    font-size: 0.85rem !important;
}

[data-testid="stInfo"] {
    background: rgba(59,130,246,0.08) !important;
    border: 1px solid rgba(59,130,246,0.25) !important;
    border-radius: 8px !important;
    color: #93c5fd !important;
    font-size: 0.85rem !important;
}

/* ── Progress bar ────────────────────────────────────────────────────────── */
[data-testid="stProgress"] > div > div {
    background: #111827 !important;
    border-radius: 9999px !important;
    height: 6px !important;
}

[data-testid="stProgress"] > div > div > div {
    background: linear-gradient(90deg, #3b82f6, #06b6d4) !important;
    border-radius: 9999px !important;
}

/* ── DataFrames ──────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 10px !important;
    overflow: hidden;
}

/* ── Dividers ────────────────────────────────────────────────────────────── */
hr {
    border-color: rgba(255,255,255,0.06) !important;
    margin: 1.25rem 0 !important;
}

/* ── Containers (with border=True) ──────────────────────────────────────── */
[data-testid="stVerticalBlock"] [data-testid="stVerticalBlockBorderWrapper"] {
    background: #0d1526 !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 12px !important;
    padding: 1rem !important;
}

/* ── KPI Card HTML blocks ────────────────────────────────────────────────── */
.kpi-card {
    background: linear-gradient(160deg, #0d1526 0%, #111827 100%);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px;
    padding: 1.2rem 1.4rem;
    box-shadow: 0 2px 20px rgba(0,0,0,0.4);
    margin-bottom: 0.5rem;
    height: 100%;
}

.kpi-label {
    font-family: 'Barlow', sans-serif;
    color: #94a3b8;
    font-size: 0.62rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.5rem;
}

.kpi-value {
    font-family: 'Barlow Condensed', sans-serif;
    color: #f1f5f9;
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    line-height: 1;
}

.kpi-sub {
    font-family: 'Barlow', sans-serif;
    color: #94a3b8;
    font-size: 0.7rem;
    font-weight: 500;
    margin-top: 0.4rem;
}

/* ── Badge chips ─────────────────────────────────────────────────────────── */
.badge-green  { background:rgba(16,185,129,0.12); color:#34d399; padding:3px 10px; border-radius:9999px; font-size:0.68rem; font-weight:700; letter-spacing:0.04em; }
.badge-red    { background:rgba(239,68,68,0.12);  color:#f87171; padding:3px 10px; border-radius:9999px; font-size:0.68rem; font-weight:700; letter-spacing:0.04em; }
.badge-amber  { background:rgba(245,158,11,0.12); color:#fbbf24; padding:3px 10px; border-radius:9999px; font-size:0.68rem; font-weight:700; letter-spacing:0.04em; }
.badge-blue   { background:rgba(59,130,246,0.12); color:#60a5fa; padding:3px 10px; border-radius:9999px; font-size:0.68rem; font-weight:700; letter-spacing:0.04em; }

/* ── Section header label ────────────────────────────────────────────────── */
.section-header {
    font-family: 'Barlow', sans-serif;
    color: #94a3b8;
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 0.6rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid rgba(255,255,255,0.05);
}

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #080d1a !important;
    border-right: 1px solid rgba(255,255,255,0.05) !important;
}

""" + _light_overrides + """
</style>
"""
    st.markdown(_css, unsafe_allow_html=True)

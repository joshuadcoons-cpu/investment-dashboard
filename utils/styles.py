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


def inject_dashboard_v2_css() -> None:
    """Inject the redesigned dashboard CSS (hero, snapshot, KPI strip, etc.).

    Call once at the top of tabs/dashboard.render() to enable the new visual
    treatments. Uses scoped class names (.dv2-*) so it doesn't affect other
    tabs. Imports JetBrains Mono for tabular numerics.
    """
    light = st.session_state.get("theme") == "light"

    # Theme-aware colors
    if light:
        _bg          = "#f8fafc"
        _card        = "#ffffff"
        _card2       = "#f8fafc"
        _line        = "rgba(0,0,0,0.08)"
        _line_strong = "rgba(0,0,0,0.16)"
        _text        = "#0f172a"
        _text_2      = "#334155"
        _muted       = "#64748b"
        _faint       = "#94a3b8"
        _dim         = "#cbd5e1"
        _bar_track   = "rgba(0,0,0,0.05)"
        _hover_bg    = "rgba(0,0,0,0.025)"
        _accent_bg   = "rgba(0,0,0,0.04)"
        _shadow      = "0 1px 4px rgba(0,0,0,0.08)"
    else:
        _bg          = "#020817"
        _card        = "#0d1526"
        _card2       = "#111c33"
        _line        = "rgba(255,255,255,0.07)"
        _line_strong = "rgba(255,255,255,0.14)"
        _text        = "#f1f5f9"
        _text_2      = "#cbd5e1"
        _muted       = "#94a3b8"
        _faint       = "#64748b"
        _dim         = "#475569"
        _bar_track   = "rgba(255,255,255,0.04)"
        _hover_bg    = "rgba(255,255,255,0.025)"
        _accent_bg   = "rgba(255,255,255,0.03)"
        _shadow      = "0 4px 28px rgba(0,0,0,0.35)"

    css = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ── Dashboard v2 wrapper ──────────────────────────────────────────────── */
.dv2 {{
  --dv2-bg: {_bg};
  --dv2-card: {_card};
  --dv2-card2: {_card2};
  --dv2-line: {_line};
  --dv2-line-strong: {_line_strong};
  --dv2-text: {_text};
  --dv2-text-2: {_text_2};
  --dv2-muted: {_muted};
  --dv2-faint: {_faint};
  --dv2-dim: {_dim};
  --dv2-bar-track: {_bar_track};
  --dv2-hover-bg: {_hover_bg};
  --dv2-accent-bg: {_accent_bg};
  --dv2-shadow: {_shadow};

  --dv2-blue: #3b82f6;     --dv2-blue-2: #60a5fa;
  --dv2-green: #10b981;    --dv2-green-2: #34d399;
  --dv2-red: #ef4444;      --dv2-red-2: #f87171;
  --dv2-amber: #f59e0b;
  --dv2-purple: #8b5cf6;
  --dv2-cyan: #06b6d4;
  --dv2-pink: #ec4899;
  --dv2-teal: #14b8a6;
  --dv2-orange: #f97316;
  --dv2-purple-2: #a78bfa;

  font-family: 'Barlow', sans-serif;
  font-feature-settings: "tnum" 1, "kern" 1;
  -webkit-font-smoothing: antialiased;
}}
.dv2 .cond {{ font-family: 'Barlow Condensed', sans-serif; letter-spacing: -0.01em; }}
.dv2 .mono {{ font-family: 'JetBrains Mono', monospace; }}

/* ── Market ticker strip (top of dashboard) ───────────────────────────── */
.dv2-market {{
  display: flex; gap: 18px; align-items: center; flex-wrap: wrap;
  padding: 10px 16px;
  background: {('rgba(13,21,38,0.6)' if not light else 'rgba(255,255,255,0.6)')};
  border: 1px solid var(--dv2-line); border-radius: 12px;
  backdrop-filter: blur(8px);
  margin-bottom: 18px;
  font-family: 'JetBrains Mono', monospace; font-size: 0.72rem;
}}
.dv2-tick {{ display: inline-flex; align-items: baseline; gap: 6px; white-space: nowrap; }}
.dv2-tick .sym {{ color: var(--dv2-text-2); font-weight: 600; }}
.dv2-tick .px  {{ color: var(--dv2-muted); }}
.dv2-tick .chg {{ font-weight: 600; }}
.dv2-tick .up  {{ color: #34d399; }}
.dv2-tick .dn  {{ color: #f87171; }}

/* ── Hero card ───────────────────────────────────────────────────────── */
.dv2-card {{
  background: linear-gradient(160deg, var(--dv2-card) 0%, var(--dv2-card2) 100%);
  border: 1px solid var(--dv2-line);
  border-radius: 16px; padding: 22px;
  box-shadow: var(--dv2-shadow);
  position: relative; overflow: hidden;
  margin-bottom: 18px;
}}
.dv2-card::before {{
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(600px 200px at 80% -20%, rgba(59,130,246,0.08), transparent 70%);
}}

.dv2-eyebrow {{
  font-family: 'Barlow'; font-size: 0.7rem; color: var(--dv2-muted);
  text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 8px;
  display: flex; align-items: center; gap: 8px;
}}
.dv2-live {{
  display: inline-flex; align-items: center; gap: 5px; font-size: 0.62rem;
  background: rgba(16,185,129,0.1); color: var(--dv2-green-2);
  padding: 2px 8px; border-radius: 9999px; letter-spacing: 0.08em; font-weight: 700;
}}
.dv2-live .pulse {{
  width: 6px; height: 6px; border-radius: 50%; background: var(--dv2-green-2);
  animation: dv2-pulse 1.6s ease-in-out infinite;
}}
@keyframes dv2-pulse {{
  0%, 100% {{ opacity: 1; transform: scale(1); }}
  50% {{ opacity: .4; transform: scale(0.7); }}
}}
.dv2-hero-value {{
  font-family: 'Barlow Condensed'; font-weight: 700; font-size: 3.2rem;
  line-height: 1; letter-spacing: -0.02em; color: var(--dv2-text);
}}
.dv2-delta {{
  display: flex; align-items: baseline; gap: 10px; margin-top: 8px;
  font-family: 'JetBrains Mono'; font-size: 0.95rem; font-weight: 600;
}}
.dv2-delta .pct {{ padding: 3px 8px; border-radius: 6px; font-size: 0.85rem; }}
.dv2-delta.up .pct {{ background: rgba(16,185,129,0.12); color: var(--dv2-green-2); }}
.dv2-delta.dn .pct {{ background: rgba(239,68,68,0.12); color: var(--dv2-red-2); }}
.dv2-delta.up .amt {{ color: var(--dv2-green-2); }}
.dv2-delta.dn .amt {{ color: var(--dv2-red-2); }}
.dv2-delta .ts {{ color: var(--dv2-faint); font-family: 'Barlow'; font-weight: 500;
  font-size: 0.78rem; margin-left: 6px; }}

.dv2-meta {{
  display: flex; gap: 22px; margin-top: 14px; padding-top: 14px;
  border-top: 1px solid var(--dv2-line);
  font-family: 'Barlow'; font-size: 0.78rem; color: var(--dv2-muted); flex-wrap: wrap;
}}
.dv2-meta .m {{ display: flex; flex-direction: column; gap: 2px; }}
.dv2-meta .m b {{ color: var(--dv2-text); font-family: 'JetBrains Mono';
  font-size: 0.92rem; font-weight: 600; }}
.dv2-meta .m .lab {{ font-size: 0.62rem; text-transform: uppercase;
  letter-spacing: 0.1em; color: var(--dv2-faint); }}

/* ── Snapshot mini KPIs ─────────────────────────────────────────────── */
.dv2-snap-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
.dv2-snap {{
  background: var(--dv2-accent-bg); border: 1px solid var(--dv2-line);
  border-radius: 11px; padding: 14px 16px; position: relative; overflow: hidden;
}}
.dv2-snap.purple {{ border-top: 2px solid var(--dv2-purple); }}
.dv2-snap.green  {{ border-top: 2px solid var(--dv2-green); }}
.dv2-snap.blue   {{ border-top: 2px solid var(--dv2-blue); }}
.dv2-snap.amber  {{ border-top: 2px solid var(--dv2-amber); }}
.dv2-snap .lab {{ font-size: 0.6rem; color: var(--dv2-muted);
  text-transform: uppercase; letter-spacing: 0.12em; font-weight: 700; }}
.dv2-snap .val {{ font-family: 'Barlow Condensed'; font-size: 1.55rem;
  font-weight: 700; margin-top: 6px; line-height: 1; color: var(--dv2-text); }}
.dv2-snap .sub {{ font-size: 0.7rem; color: var(--dv2-faint); margin-top: 5px; }}

.dv2-meter {{ height: 6px; background: var(--dv2-bar-track); border-radius: 9999px;
  overflow: hidden; margin-top: 10px; }}
.dv2-meter .fill {{ height: 100%; border-radius: 9999px;
  background: linear-gradient(90deg, var(--dv2-green), var(--dv2-cyan)); }}
.dv2-meter.amber .fill {{ background: linear-gradient(90deg, var(--dv2-amber), #facc15); }}

.dv2-headline-row {{ display: flex; justify-content: space-between;
  align-items: center; margin-bottom: 8px; }}
.dv2-headline-row .lab {{ font-size: 0.6rem; color: var(--dv2-muted);
  text-transform: uppercase; letter-spacing: 0.12em; font-weight: 700; }}

/* ── KPI strip ───────────────────────────────────────────────────────── */
.dv2-kpi-grid {{
  display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px;
  margin-bottom: 20px;
}}
@media (max-width: 1100px) {{ .dv2-kpi-grid {{ grid-template-columns: repeat(3, 1fr); }} }}
@media (max-width: 680px) {{ .dv2-kpi-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
.dv2-kpi {{
  background: linear-gradient(160deg, var(--dv2-card) 0%, var(--dv2-card2) 100%);
  border: 1px solid var(--dv2-line); border-radius: 13px; padding: 14px 16px;
  position: relative; overflow: hidden; transition: all .2s ease;
  box-shadow: var(--dv2-shadow);
}}
.dv2-kpi:hover {{ transform: translateY(-1px); border-color: var(--dv2-line-strong); }}
.dv2-kpi .accent {{ position: absolute; top: 0; left: 0; right: 0; height: 2.5px; }}
.dv2-kpi .lab {{ font-size: 0.58rem; color: var(--dv2-muted);
  text-transform: uppercase; letter-spacing: 0.12em; font-weight: 700; }}
.dv2-kpi .val {{ font-family: 'Barlow Condensed'; font-size: 1.65rem;
  font-weight: 700; margin-top: 6px; line-height: 1.05; color: var(--dv2-text); }}
.dv2-kpi .sub {{ font-size: 0.66rem; color: var(--dv2-faint); margin-top: 4px; }}
.dv2-kpi .spark {{ position: absolute; right: 10px; top: 14px; opacity: .55; }}

/* ── Today's move strip ─────────────────────────────────────────────── */
.dv2-move {{
  display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
  background: linear-gradient(90deg, {_card} 0%, {_card2} 100%);
  border: 1px solid {_line};
  border-radius: 11px; padding: 14px 20px; margin-bottom: 22px;
}}
.dv2-move.up {{ border-left: 4px solid #10b981; }}
.dv2-move.dn {{ border-left: 4px solid #ef4444; }}
.dv2-move .ttl {{ font-size: 0.62rem; font-weight: 700; color: {_muted};
  text-transform: uppercase; letter-spacing: 0.12em; white-space: nowrap; }}
.dv2-move .big {{ font-family: 'Barlow Condensed'; font-size: 1.45rem; font-weight: 700; }}
.dv2-move.up .big {{ color: #34d399; }}
.dv2-move.dn .big {{ color: #f87171; }}
.dv2-move .pct {{ font-family: 'JetBrains Mono'; font-size: 0.82rem; margin-left: 6px; }}
.dv2-move.up .pct {{ color: #34d399; }}
.dv2-move.dn .pct {{ color: #f87171; }}
.dv2-move .sep {{ color: {_dim}; margin: 0 4px; }}
.dv2-move .acc {{ font-size: 0.78rem; color: {_muted}; font-family: 'Barlow'; }}
.dv2-move .acc b {{ font-family: 'JetBrains Mono'; font-weight: 600; margin-left: 4px; }}

/* ── Card header ─────────────────────────────────────────────────────── */
.dv2-h {{
  font-family: 'Barlow'; font-size: 0.7rem; color: var(--dv2-text-2);
  font-weight: 600; text-transform: uppercase; letter-spacing: 0.12em;
  margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center;
}}
.dv2-h .meta {{ color: var(--dv2-faint); font-weight: 500;
  text-transform: none; letter-spacing: 0.02em; font-size: 0.74rem; }}

/* ── Net worth bars ─────────────────────────────────────────────────── */
.dv2-nw-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 9px; font-size: 0.78rem; }}
.dv2-nw-row .name {{ width: 128px; color: var(--dv2-text-2); font-weight: 500;
  flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.dv2-nw-row .barwrap {{ flex: 1; height: 18px; background: var(--dv2-bar-track);
  border-radius: 5px; position: relative; overflow: hidden; }}
.dv2-nw-row .bar {{ height: 100%; border-radius: 5px; display: flex;
  align-items: center; padding: 0 8px; min-width: 2px; }}
.dv2-nw-row .bar.asset {{ background: linear-gradient(90deg, rgba(16,185,129,0.6), rgba(16,185,129,0.85)); }}
.dv2-nw-row .bar.liab  {{ background: linear-gradient(90deg, rgba(239,68,68,0.85), rgba(239,68,68,0.6));
  margin-left: auto; }}
.dv2-nw-row .amt {{ font-family: 'JetBrains Mono'; font-size: 0.72rem;
  font-weight: 600; color: #fff; }}
.dv2-nw-row.right .barwrap {{ display: flex; justify-content: flex-end; }}

.dv2-nw-summary {{ display: flex; justify-content: space-between;
  border-top: 1px solid var(--dv2-line); padding-top: 12px; margin-top: 14px; }}
.dv2-nw-summary .col {{ flex: 1; }}
.dv2-nw-summary .lab {{ font-size: 0.6rem; color: var(--dv2-muted);
  text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700; }}
.dv2-nw-summary .v {{ font-family: 'Barlow Condensed'; font-size: 1.35rem;
  font-weight: 700; margin-top: 4px; }}
.dv2-nw-summary .v.green  {{ color: var(--dv2-green-2); }}
.dv2-nw-summary .v.red    {{ color: var(--dv2-red-2); }}
.dv2-nw-summary .v.purple {{ color: var(--dv2-purple-2); }}

/* ── Sector allocation ──────────────────────────────────────────────── */
.dv2-sector-row {{ margin-bottom: 11px; }}
.dv2-sector-head {{ display: flex; justify-content: space-between;
  font-size: 0.74rem; margin-bottom: 5px; }}
.dv2-sector-head .nm {{ color: var(--dv2-text-2); font-weight: 500; }}
.dv2-sector-head .vs {{ color: var(--dv2-faint); font-family: 'JetBrains Mono'; font-size: 0.7rem; }}
.dv2-sector-head .vs b {{ color: var(--dv2-text); }}
.dv2-sector-bar {{ height: 14px; background: var(--dv2-bar-track);
  border-radius: 4px; position: relative; overflow: visible; }}
.dv2-sector-bar .target {{ position: absolute; top: -2px; bottom: -2px;
  width: 2px; background: {('rgba(0,0,0,0.45)' if light else 'rgba(255,255,255,0.4)')};
  z-index: 2; border-radius: 1px; }}
.dv2-sector-bar .cur {{ height: 100%;
  background: linear-gradient(90deg, var(--dv2-blue), var(--dv2-blue-2));
  border-radius: 4px; }}
.dv2-sector-bar .cur.over {{ background: linear-gradient(90deg, var(--dv2-amber), #fbbf24); }}

/* ── Donut center ────────────────────────────────────────────────────── */
.dv2-donut-stage {{ position: relative; width: 100%; }}
.dv2-donut-center {{
  position: absolute; inset: 0; display: flex; flex-direction: column;
  align-items: center; justify-content: center; pointer-events: none;
}}
.dv2-donut-center .lab {{ font-size: 0.58rem; color: var(--dv2-muted);
  text-transform: uppercase; letter-spacing: 0.14em; font-weight: 700; }}
.dv2-donut-center .v {{ font-family: 'Barlow Condensed'; font-size: 1.7rem;
  font-weight: 700; line-height: 1; margin-top: 3px; color: var(--dv2-text); }}
.dv2-donut-legend {{ display: flex; flex-direction: column; gap: 5px;
  font-size: 0.72rem; margin-top: 8px; }}
.dv2-donut-legend .lr {{ display: flex; align-items: center; gap: 8px;
  padding: 5px 8px; border-radius: 6px; }}
.dv2-donut-legend .lr:hover {{ background: var(--dv2-hover-bg); }}
.dv2-donut-legend .sw {{ width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0; }}
.dv2-donut-legend .nm {{ flex: 1; color: var(--dv2-text-2);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.dv2-donut-legend .pc {{ color: var(--dv2-faint);
  font-family: 'JetBrains Mono'; font-size: 0.68rem; }}

/* ── Debt payoff ─────────────────────────────────────────────────────── */
.dv2-debt {{ margin-bottom: 18px; }}
.dv2-debt-head {{ display: flex; justify-content: space-between;
  align-items: baseline; margin-bottom: 7px; }}
.dv2-debt-head .nm {{ font-size: 0.86rem; font-weight: 600; color: var(--dv2-text); }}
.dv2-debt-head .meta {{ color: var(--dv2-faint); font-size: 0.72rem; font-family: 'Barlow'; }}
.dv2-debt-bar {{ height: 22px; background: var(--dv2-bar-track);
  border-radius: 7px; overflow: hidden; position: relative; }}
.dv2-debt-bar .fl {{ height: 100%; border-radius: 7px; display: flex;
  align-items: center; justify-content: flex-end; padding-right: 9px; min-width: 5%; }}
.dv2-debt-bar .fl.mortgage {{ background: linear-gradient(90deg, var(--dv2-green), var(--dv2-cyan)); }}
.dv2-debt-bar .fl.other {{ background: linear-gradient(90deg, var(--dv2-amber), var(--dv2-green)); }}
.dv2-debt-bar .fl .pmt {{ font-family: 'JetBrains Mono'; font-size: 0.66rem;
  font-weight: 600; color: #fff; }}
.dv2-debt-foot {{ display: flex; justify-content: space-between;
  font-size: 0.72rem; margin-top: 5px; }}
.dv2-debt-foot .paid {{ color: var(--dv2-green-2);
  font-family: 'JetBrains Mono'; font-weight: 600; }}
.dv2-debt-foot .rem {{ color: var(--dv2-muted); font-family: 'JetBrains Mono'; }}

/* ── Account list ────────────────────────────────────────────────────── */
.dv2-acct-list {{ display: flex; flex-direction: column; gap: 10px; }}
.dv2-acct {{
  display: grid; grid-template-columns: 24px 1fr auto; gap: 14px; align-items: center;
  padding: 11px 13px; background: var(--dv2-accent-bg);
  border: 1px solid var(--dv2-line); border-radius: 10px;
  transition: all .15s ease;
}}
.dv2-acct:hover {{ border-color: var(--dv2-line-strong); background: var(--dv2-hover-bg); }}
.dv2-acct .swatch {{ width: 8px; height: 34px; border-radius: 3px; }}
.dv2-acct .nm {{ font-size: 0.86rem; font-weight: 600; color: var(--dv2-text); }}
.dv2-acct .ty {{ font-size: 0.66rem; color: var(--dv2-muted);
  text-transform: uppercase; letter-spacing: 0.08em; margin-top: 3px; }}
.dv2-acct .bal {{ font-family: 'Barlow Condensed'; font-size: 1.25rem;
  font-weight: 700; text-align: right; line-height: 1; color: var(--dv2-text); }}
.dv2-acct .day {{ font-family: 'JetBrains Mono'; font-size: 0.72rem;
  text-align: right; margin-top: 3px; }}

/* ── Holdings table ──────────────────────────────────────────────────── */
.dv2-holdings {{ width: 100%; border-collapse: collapse; font-size: 0.78rem; }}
.dv2-holdings th {{
  text-align: left; font-size: 0.6rem; color: var(--dv2-muted);
  text-transform: uppercase; letter-spacing: 0.12em; font-weight: 700;
  padding: 8px 10px; border-bottom: 1px solid var(--dv2-line);
}}
.dv2-holdings th.r {{ text-align: right; }}
.dv2-holdings td {{ padding: 10px;
  border-bottom: 1px solid var(--dv2-line); vertical-align: middle; color: var(--dv2-text-2); }}
.dv2-holdings td.r {{ text-align: right; font-family: 'JetBrains Mono';
  font-size: 0.74rem; }}
.dv2-holdings td.val {{ color: var(--dv2-text); font-weight: 600; }}
.dv2-holdings tr:hover td {{ background: var(--dv2-accent-bg); }}
.dv2-tk {{ display: inline-flex; align-items: center; gap: 8px; }}
.dv2-tk .ic {{
  width: 28px; height: 28px; border-radius: 7px; display: flex;
  align-items: center; justify-content: center;
  font-family: 'Barlow Condensed'; font-weight: 700; font-size: 0.72rem;
  color: #fff; flex-shrink: 0;
}}
.dv2-tk .nm {{ display: flex; flex-direction: column; line-height: 1.2; }}
.dv2-tk .nm .sym {{ font-family: 'JetBrains Mono'; font-weight: 600;
  font-size: 0.78rem; color: var(--dv2-text); }}
.dv2-tk .nm .nt {{ font-size: 0.64rem; color: var(--dv2-muted); }}

/* ── Milestone ───────────────────────────────────────────────────────── */
.dv2-ms {{
  margin-bottom: 10px;
  padding: 14px 16px;
  border-radius: 10px;
  border-left: 3px solid #3b82f6;
  background: rgba(59,130,246,0.06);
}}
.dv2-ms.done {{
  border-left-color: #10b981;
  background: rgba(16,185,129,0.06);
}}
.dv2-ms.future {{
  border-left-color: #475569;
  background: rgba(255,255,255,0.02);
}}

.dv2-ms .ms-chip {{
  display: inline-flex; align-items: center; gap: 5px;
  padding: 2px 9px; border-radius: 9999px;
  font-size: 0.58rem; font-weight: 700; letter-spacing: 0.1em;
  margin-bottom: 9px; text-transform: uppercase;
  background: rgba(59,130,246,0.15); color: #60a5fa;
}}
.dv2-ms.done .ms-chip {{
  background: rgba(16,185,129,0.15); color: #34d399;
}}
.dv2-ms.future .ms-chip {{
  background: rgba(71,85,105,0.2); color: #64748b;
}}
.dv2-ms .ms-chip .dot {{
  width: 5px; height: 5px; border-radius: 50%;
  background: currentColor; flex-shrink: 0;
}}

.dv2-ms .top {{ display: flex; justify-content: space-between;
  align-items: baseline; font-size: 0.78rem; margin-bottom: 10px; gap: 12px; }}
.dv2-ms .top .left {{ display: flex; flex-direction: column; gap: 3px; flex: 1; min-width: 0; }}
.dv2-ms .top .ttl {{ color: #f1f5f9; font-weight: 700; font-size: 0.82rem; }}
.dv2-ms.done .top .ttl {{ color: #34d399; }}
.dv2-ms.future .top .ttl {{ color: #94a3b8; }}
.dv2-ms .top .ev {{ color: #64748b; font-size: 0.72rem; font-weight: 400; }}
.dv2-ms .top .pc {{
  color: #60a5fa; font-family: 'JetBrains Mono'; font-size: 0.72rem;
  font-weight: 600; white-space: nowrap; text-align: right; flex-shrink: 0;
}}
.dv2-ms.done .top .pc {{ color: #34d399; }}
.dv2-ms.future .top .pc {{ color: #64748b; }}

.dv2-ms .mtrack {{ height: 10px; background: {_bar_track};
  border-radius: 9999px; overflow: hidden; }}
.dv2-ms .mfill {{ height: 100%;
  background: linear-gradient(90deg, #3b82f6, #60a5fa, #06b6d4);
  border-radius: 9999px;
  box-shadow: 0 0 10px rgba(59,130,246,0.5); }}
.dv2-ms.done .mfill {{
  background: linear-gradient(90deg, #10b981, #34d399, #06b6d4);
  box-shadow: 0 0 10px rgba(16,185,129,0.5); }}
.dv2-ms.future .mfill {{
  background: rgba(255,255,255,0.10);
  box-shadow: none; }}

/* ── Range pills (override Streamlit segmented_control / pills) ──────── */
.dv2 [data-testid="stRadio"] > div {{ flex-direction: row !important; gap: 2px; }}

/* Uniform vertical rhythm for cards */
.dv2-card {{ margin-bottom: 0 !important; }}

/* When .dv2 styling needs to apply, the host can be inside the border wrapper */
[data-testid="stVerticalBlockBorderWrapper"] .dv2-h,
[data-testid="stVerticalBlockBorderWrapper"] .dv2-eyebrow,
[data-testid="stVerticalBlockBorderWrapper"] .dv2-meta {{
  font-family: 'Barlow', sans-serif;
}}

/* ── Equal-height cards: stretch bordered containers within each row ─── */
[data-testid="stHorizontalBlock"] {{
  align-items: stretch !important;
}}
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
  display: flex;
  flex-direction: column;
}}
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"] > [data-testid="stVerticalBlock"] {{
  display: flex;
  flex-direction: column;
  flex: 1;
}}
[data-testid="stHorizontalBlock"] > [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"] {{
  flex: 1;
  height: 100%;
  box-sizing: border-box;
}}

/* ── Consistent section gap ─────────────────────────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {{
  margin-bottom: 0 !important;
}}
</style>
"""
    st.markdown(css, unsafe_allow_html=True)


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
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: linear-gradient(160deg, #ffffff 0%, #f8fafc 100%) !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 16px !important;
            padding: 22px !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08) !important;
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

/* ── Containers (with border=True) — dashboard card style ─────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: linear-gradient(160deg, #0d1526 0%, #111c33 100%) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 16px !important;
    padding: 22px !important;
    box-shadow: 0 4px 28px rgba(0,0,0,0.35) !important;
    position: relative; overflow: hidden;
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

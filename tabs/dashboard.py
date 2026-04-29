"""Dashboard v2 — Financial Dashboard polished redesign.

Layout (top → bottom):
    1. Market ticker strip
    2. Hero row: Growth chart (left) + Snapshot panel (right)
    3. KPI strip (6 cards with sparklines)
    4. Today's Move strip
    5. Row 3: Net Worth bars / Allocation donut / Sector allocation
    6. Row 2: Cash Flow Waterfall / Debt Payoff Timeline
    7. Row 2: Investment Accounts / Top Holdings table
    8. Milestone Tracker
"""

import math
import random
import html as _html
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import date, datetime, timedelta
from utils.calculations import (
    calc_monthly_payment, build_amortization, get_loan_status,
)
from utils.styles import (
    BLUE, GREEN, RED, PURPLE, AMBER, CYAN, CHART_COLORS,
    chart_layout, theme_colors, inject_dashboard_v2_css,
)


# ─── Constants ──────────────────────────────────────────────────────────────

SECTOR_COLORS = {
    "US Equity":         "#3b82f6",
    "Technology":        "#8b5cf6",
    "International":     "#06b6d4",
    "Emerging Markets":  "#ec4899",
    "Commodities":       "#f59e0b",
    "Crypto":            "#f97316",
    "Financials":        "#14b8a6",
    "Healthcare":        "#10b981",
    "Other":             "#64748b",
    "Unknown":           "#64748b",
}

ACCT_COLORS = ["#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#06b6d4", "#ec4899"]

DEFAULT_TARGET_ALLOC = {
    "US Equity": 35, "Technology": 15, "International": 10, "Emerging Markets": 5,
    "Commodities": 10, "Crypto": 10, "Financials": 5, "Healthcare": 5, "Other": 5,
}

CRYPTO_TICKERS = {"BTC", "ETH", "ADA", "XRP", "DOGE", "IBIT", "ETHA"}

MARKET_PICKS = ["VOO", "QQQM", "AAPL", "MSFT", "BTC", "ETH", "IAU"]

# Canonical sector overrides — fixes "Unknown" labels baked into the JSON
TICKER_SECTOR_MAP = {
    # US Equity
    "VOO": "US Equity", "SCHG": "US Equity", "AVUV": "US Equity",
    # Technology
    "QQQM": "Technology", "AAPL": "Technology", "MSFT": "Technology",
    "META": "Technology", "SMH": "Technology", "VGT": "Technology",
    # Financials / Healthcare
    "VFH": "Financials", "VHT": "Healthcare",
    # International / Emerging
    "VXUS": "International", "VWO": "Emerging Markets",
    # Commodities (incl. gold)
    "IAU": "Commodities", "PDBC": "Commodities",
    # Crypto (ETFs + direct)
    "IBIT": "Crypto", "ETHA": "Crypto",
    "BTC": "Crypto", "ETH": "Crypto",
    "ADA": "Crypto", "XRP": "Crypto", "DOGE": "Crypto",
}


# ─── Formatters ─────────────────────────────────────────────────────────────

def _fmt_k(v):
    """Compact dollar: $1.02M / $697k / $123."""
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1_000_000:
        return f"{sign}${a/1_000_000:.2f}M"
    if a >= 1_000:
        return f"{sign}${a/1_000:.0f}k"
    return f"{sign}${a:,.0f}"


def _fmt_dollar(v, dp=0):
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,.{dp}f}"


def _fmt_px(v):
    if v is None:
        return "—"
    if abs(v) < 1:
        return f"{v:.4f}"
    return f"{v:,.2f}"


def _parse_date(v):
    """Parse a date from str / {__date__: ...} dict / date object."""
    if v is None:
        return None
    if isinstance(v, date):
        return v
    if isinstance(v, dict) and "__date__" in v:
        return date.fromisoformat(v["__date__"])
    if isinstance(v, str):
        try:
            return date.fromisoformat(v)
        except ValueError:
            return None
    return None


def _holding_sector(h):
    """Resolve the canonical sector for a holding, correcting 'Unknown' labels."""
    tk = h.get("ticker")
    if tk and tk in TICKER_SECTOR_MAP:
        return TICKER_SECTOR_MAP[tk]
    sec = h.get("sector") or "Other"
    return "Other" if sec == "Unknown" else sec


# ─── Sparklines ─────────────────────────────────────────────────────────────

def _sparkline_svg(values, color, w=60, h=24):
    if not values:
        return ""
    mn, mx = min(values), max(values)
    rng = mx - mn or 1
    n = len(values)
    pts = " ".join(
        f"{(i/(n-1) if n > 1 else 0)*w:.1f},{h - ((v - mn)/rng) * h:.1f}"
        for i, v in enumerate(values)
    )
    return (
        f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" '
        f'style="width:60px;height:24px">'
        f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )


def _rand_spark(n=14, trend=1.0, seed=None):
    rng = random.Random(seed) if seed is not None else random
    out = [50.0]
    for _ in range(n - 1):
        out.append(out[-1] + (rng.random() - 0.5 + 0.1 * trend) * 5)
    return out


# ─── Growth chart simulator ─────────────────────────────────────────────────

_RANGE_CFG = {
    # (n_bars,  step,                 drift,   vol,    span)
    "1D":  (78,  timedelta(minutes=5),   0.00002, 0.0008, 0.012),
    "1W":  (56,  timedelta(hours=3),     0.00008, 0.0015, 0.025),
    "1M":  (30,  timedelta(days=1),      0.0007,  0.005,  0.06),
    "3M":  (65,  timedelta(hours=36),    0.0009,  0.007,  0.11),
    "YTD": (110, timedelta(days=1),      0.0008,  0.008,  0.13),
    "1Y":  (250, timedelta(days=1),      0.0006,  0.009,  0.22),
    "5Y":  (260, timedelta(weeks=1),     0.0018,  0.012,  0.95),
}


def _generate_growth_series(end_value, range_label, seed=None, portfolio_start_dt=None):
    """Return (datetimes, values, origin_idx) of a simulated path landing at end_value.

    If portfolio_start_dt is set and the range extends before it, the chart shows
    a near-flat $0 pre-section up to that date, then a biased GBM growth curve
    from there to now — so the story reads: "portfolio didn't exist yet, then it
    started growing from this moment."
    """
    rng = random.Random(seed) if seed is not None else random
    n, dt, drift, vol, span = _RANGE_CFG.get(range_label, _RANGE_CFG["1W"])

    now = datetime.now()
    times = [now - dt * (n - 1 - i) for i in range(n)]

    # ── Pre-origin flat section ───────────────────────────────────────────
    if portfolio_start_dt is not None:
        ps = portfolio_start_dt
        n_pre = sum(1 for t in times if t < ps)
        # Need at least 5 post-origin bars for a meaningful growth curve
        if 0 < n_pre < n - 5:
            n_post = n - n_pre
            pre_times  = times[:n_pre]
            post_times = times[n_pre:]
            seed_val   = end_value * 0.003   # ~0.3% of net worth (effectively $0)

            # Pre-section: nearly flat, very small values
            pre_vals = [seed_val * (0.9 + rng.random() * 0.2) for _ in range(n_pre)]
            pre_vals[-1] = seed_val           # pin last pre-point to seed_val

            # Post-section: biased GBM from seed_val → end_value
            v = seed_val
            path = [v]
            for _ in range(1, n_post):
                u1 = max(rng.random(), 1e-12)
                u2 = rng.random()
                z  = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)
                v  = v * (1 + drift + vol * z)
                path.append(v)

            correction = end_value / path[-1] if path[-1] else 1
            out_post = []
            for i, p in enumerate(path):
                w = i / (len(path) - 1) if len(path) > 1 else 1
                out_post.append(p * (1 + (correction - 1) * (0.5 + 0.5 * w)))
            out_post[-1] = end_value

            return pre_times + post_times, pre_vals + out_post, n_pre

    # ── Normal path (no pre-section needed) ──────────────────────────────
    start = end_value / (1 + span * (0.85 + rng.random() * 0.4))
    v = start
    path = [v]
    for _ in range(1, n):
        u1 = max(rng.random(), 1e-12)
        u2 = rng.random()
        z = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)
        v = v * (1 + drift + vol * z)
        path.append(v)

    correction = end_value / path[-1] if path[-1] else 1
    out = []
    for i, p in enumerate(path):
        w = i / (len(path) - 1) if len(path) > 1 else 1
        out.append(p * (1 + (correction - 1) * (0.6 + 0.4 * w)))
    out[-1] = end_value

    return times, out, 0


# ─── Render ─────────────────────────────────────────────────────────────────

def render():
    a  = st.session_state.assumptions
    tc = theme_colors()

    # Inject the redesigned dashboard CSS
    inject_dashboard_v2_css()

    today = date.today()

    # ═══════════════════════════════════════════════════════════════════════
    # Calculations (same as before — proven correct)
    # ═══════════════════════════════════════════════════════════════════════
    amort  = build_amortization(
        a["loan_original_amount"], a["loan_interest_rate"],
        a["loan_term_years"], a["loan_start_date"],
    )
    status = get_loan_status(amort, today)

    home_equity = max(a["home_current_value"] - status["current_balance"], 0)

    # Live prices (per-ticker market value)
    live_prices = st.session_state.get("live_prices", {})
    prev_prices = st.session_state.get("prev_prices", {})

    def _holding_mv(h):
        tk = h.get("ticker")
        if tk and live_prices.get(tk):
            return h["shares"] * live_prices[tk]
        if h.get("avg_cost"):
            return h["shares"] * h["avg_cost"]
        return 0

    def _acct_mv(acct):
        has_priced = any(
            h.get("ticker") and live_prices.get(h["ticker"])
            for h in acct.get("holdings", [])
        )
        if has_priced:
            mv = acct.get("cash_usd", 0)
            for h in acct.get("holdings", []):
                p = live_prices.get(h.get("ticker"))
                if p:
                    mv += h["shares"] * p
            return mv
        return acct.get("balance", 0)

    def _acct_day(acct):
        d = 0.0
        for h in acct.get("holdings", []):
            tk = h.get("ticker")
            if tk and live_prices.get(tk) and prev_prices.get(tk):
                d += (live_prices[tk] - prev_prices[tk]) * h["shares"]
        return d

    total_investments = sum(_acct_mv(acct) for acct in a["investment_accounts"])
    cost_basis = sum(
        acct.get("cash_usd", 0) + sum(
            h["shares"] * h.get("avg_cost", 0) for h in acct.get("holdings", [])
            if h.get("avg_cost") is not None
        )
        for acct in a["investment_accounts"]
    )

    # Income / cash flow
    take_home   = a["take_home_monthly"] + a["spouse_take_home_monthly"]
    passive     = a.get("parkwood_lp_monthly", 0) + a.get("family_gift_annual", 0) / 12
    monthly_in  = take_home + passive

    monthly_pi  = calc_monthly_payment(
        a["loan_original_amount"], a["loan_interest_rate"], a["loan_term_years"])
    monthly_tax = a["home_current_value"] * a["property_tax_rate"] / 100 / 12
    monthly_ins = a["home_insurance_annual"] / 12
    monthly_hoa = a["hoa_monthly"]
    monthly_mnt = a["home_current_value"] * a["maintenance_pct"] / 100 / 12
    housing     = monthly_pi + monthly_tax + monthly_ins + monthly_hoa + monthly_mnt
    debts       = sum(d["monthly_payment"] for d in a["other_debts"])
    budget      = sum(a["budget"].values())
    invest_mo   = sum(acct["monthly_contribution"] for acct in a["investment_accounts"])
    net_cf      = monthly_in - housing - debts - budget - invest_mo
    savings_rate = (
        (invest_mo + max(net_cf, 0)) / monthly_in * 100 if monthly_in else 0
    )

    sinking_fund = a.get("sinking_fund_balance", 0)
    liquid_cash  = a["emergency_fund_balance"] + sinking_fund + a["checking_savings_balance"]
    total_assets = a["home_current_value"] + total_investments + liquid_cash
    total_liab   = status["current_balance"] + sum(d["balance"] for d in a["other_debts"])
    net_worth    = total_assets - total_liab

    total_exp = housing + debts + budget
    ef_months = liquid_cash / total_exp if total_exp else 0

    # Daily P&L
    daily_gain = sum(_acct_day(acct) for acct in a["investment_accounts"])
    daily_pct  = (
        daily_gain / (total_investments - daily_gain) * 100
        if (total_investments - daily_gain) else 0
    )

    # Portfolio origin date (used to anchor the growth chart)
    _ps_date = _parse_date(a.get("loan_start_date"))
    portfolio_start_dt = (
        datetime.combine(_ps_date, datetime.min.time()) if _ps_date else None
    )

    # Mortgage % paid (computed here so both hero and debt timeline can use it)
    mort_pct = status["pct_paid"] if "pct_paid" in status else (
        (a["loan_original_amount"] - status["current_balance"]) / a["loan_original_amount"] * 100
        if a["loan_original_amount"] else 0
    )

    # Retirement projection
    yrs_to_ret = a["retirement_age"] - a["age"]
    retire = {"pct": 0, "ret_income": 0, "inflated": 0, "bal": 0}
    if yrs_to_ret > 0:
        r = a["investment_return_pct"] / 100 / 12
        bal = float(total_investments)
        for _ in range(yrs_to_ret * 12):
            bal = bal * (1 + r) + invest_mo
        safe_mo = bal * 0.04 / 12
        ss = a["social_security_monthly"] if (a["age"] + yrs_to_ret) >= a["social_security_start_age"] else 0
        lp_doubled = a.get("parkwood_lp_monthly", 0) * a.get("lp_net_pct", 100) / 100 * 2
        ret_income = safe_mo + ss + lp_doubled
        post_payoff = total_exp - monthly_pi
        inflated = post_payoff * (1 + a["inflation_pct"] / 100) ** yrs_to_ret
        retire = {
            "pct": (ret_income / inflated * 100) if inflated else 0,
            "ret_income": ret_income,
            "inflated": inflated,
            "bal": bal,
        }

    # ═══════════════════════════════════════════════════════════════════════
    # 1. MARKET TICKER STRIP
    # ═══════════════════════════════════════════════════════════════════════
    ticker_data = {}
    for acct in a["investment_accounts"]:
        for h in acct.get("holdings", []):
            tk = h.get("ticker")
            if tk and tk not in ticker_data:
                px_ = live_prices.get(tk)
                prev = prev_prices.get(tk)
                if px_:
                    chg = (px_ - prev) if prev else 0
                    pct = (chg / prev * 100) if prev else 0
                    ticker_data[tk] = {"px": px_, "chg": chg, "pct": pct}

    ticker_html = ""
    for sym in MARKET_PICKS:
        if sym in ticker_data:
            t = ticker_data[sym]
            cls = "up" if t["chg"] >= 0 else "dn"
            arrow = "▲" if t["chg"] >= 0 else "▼"
            sign = "+" if t["pct"] >= 0 else ""
            ticker_html += (
                f'<span class="dv2-tick"><span class="sym">{sym}</span>'
                f'<span class="px">{_fmt_px(t["px"])}</span>'
                f'<span class="chg {cls}">{arrow} {sign}{t["pct"]:.2f}%</span></span>'
            )
    if ticker_html:
        st.markdown(f'<div class="dv2 dv2-market">{ticker_html}</div>', unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 2. HERO ROW — Growth chart + Snapshot
    # ═══════════════════════════════════════════════════════════════════════
    hero_l, hero_r = st.columns([1.55, 1])

    with hero_l:
        # Range selector — use Streamlit pills if available, else radio
        if "growth_range" not in st.session_state:
            st.session_state.growth_range = "1W"

        ranges = ["1D", "1W", "1M", "3M", "YTD", "1Y", "5Y"]
        try:
            sel = st.pills(
                "Growth range", ranges,
                default=st.session_state.growth_range,
                label_visibility="collapsed",
                key="growth_range_pills",
            )
            if sel:
                st.session_state.growth_range = sel
        except Exception:
            sel = st.radio(
                "Growth range", ranges,
                index=ranges.index(st.session_state.growth_range),
                horizontal=True,
                label_visibility="collapsed",
                key="growth_range_radio",
            )
            st.session_state.growth_range = sel

        rng = st.session_state.growth_range
        seed_key = f"growth_seed_{rng}"
        if seed_key not in st.session_state:
            st.session_state[seed_key] = random.randint(0, 1_000_000)
        times, vals, origin_idx = _generate_growth_series(
            net_worth, rng, st.session_state[seed_key], portfolio_start_dt
        )

        # Use first post-origin value as "Open" so delta reflects real growth period
        start_v = vals[origin_idx]
        end_v   = vals[-1]
        change  = end_v - start_v
        chg_pct = (change / start_v * 100) if start_v else 0
        is_up   = change >= 0
        stroke  = "#34d399" if is_up else "#f87171"

        # Hero header HTML (eyebrow + value + delta)
        delta_cls = "up" if is_up else "dn"
        sign      = "+" if is_up else "−"

        with st.container(border=True):
            st.html(
                '<div class="dv2">'
                '<div class="dv2-eyebrow">Net Worth · Growth '
                '<span class="dv2-live"><span class="pulse"></span>LIVE</span>'
                '</div>'
                f'<div class="dv2-hero-value">{_fmt_dollar(net_worth)}</div>'
                f'<div class="dv2-delta {delta_cls}">'
                f'<span class="amt mono">{sign}{_fmt_dollar(abs(change))}</span>'
                f'<span class="pct mono">{sign if is_up else "−"}{abs(chg_pct):.2f}%</span>'
                f'<span class="ts">past {rng}</span>'
                '</div></div>'
            )

            # Plotly growth chart
            fig = go.Figure()
            fill_rgba = ("rgba(16,185,129,0.18)" if is_up else "rgba(239,68,68,0.18)")

            # Glow line (thicker, lower opacity)
            fig.add_trace(go.Scatter(
                x=times, y=vals,
                mode="lines",
                line=dict(color=stroke, width=5, shape="spline", smoothing=0.6),
                opacity=0.25, hoverinfo="skip", showlegend=False,
            ))
            # Filled area
            fig.add_trace(go.Scatter(
                x=times, y=vals,
                mode="lines",
                line=dict(color=stroke, width=2, shape="spline", smoothing=0.6),
                fill="tozeroy", fillcolor=fill_rgba,
                hovertemplate="<b>%{x|%a %b %d, %I:%M %p}</b><br>"
                              "$%{y:,.0f}<extra></extra>",
                hoverlabel=dict(
                    bgcolor="rgba(15,23,42,0.95)",
                    bordercolor=tc["border"],
                    font=dict(family="JetBrains Mono", size=12, color="#f1f5f9"),
                ),
                showlegend=False,
                name="Net Worth",
            ))
            # Endpoint dot
            fig.add_trace(go.Scatter(
                x=[times[-1]], y=[end_v],
                mode="markers",
                marker=dict(size=10, color=stroke,
                            line=dict(color="rgba(255,255,255,0.9)", width=2)),
                hoverinfo="skip", showlegend=False,
            ))

            # Y-axis range — tight around the data
            y_min = min(vals) * 0.996
            y_max = max(vals) * 1.004

            fig.update_layout(**chart_layout(
                height=280,
                margin=dict(l=10, r=10, t=10, b=20),
                showlegend=False,
                xaxis=dict(
                    showgrid=False, showline=False, zeroline=False,
                    tickfont=dict(size=10, color=tc["faint"]),
                ),
                yaxis=dict(
                    range=[y_min, y_max],
                    tickprefix="$", tickformat=",.0s",
                    gridcolor=tc["grid"], showline=False, zeroline=False,
                    tickfont=dict(size=10, color=tc["faint"]),
                ),
                hovermode="x unified",
            ))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            # Footer meta strip
            period_high = max(vals)
            period_low  = min(vals)
            period_rng  = period_high - period_low
            vol_pct     = (period_rng / start_v * 100) if start_v else 0
            chg_color   = "var(--dv2-green-2)" if is_up else "var(--dv2-red-2)"
            st.html(
                '<div class="dv2 dv2-meta">'
                f'<div class="m"><span class="lab">Open</span><b>{_fmt_k(start_v)}</b></div>'
                f'<div class="m"><span class="lab">High</span><b>{_fmt_k(period_high)}</b></div>'
                f'<div class="m"><span class="lab">Low</span><b>{_fmt_k(period_low)}</b></div>'
                f'<div class="m"><span class="lab">Range</span><b>{_fmt_k(period_rng)}</b></div>'
                f'<div class="m"><span class="lab">Volatility</span><b>{vol_pct:.2f}%</b></div>'
                f'<div class="m" style="margin-left:auto;color:{chg_color}">'
                '<span class="lab">Period change</span>'
                f'<b style="color:inherit">{sign}{_fmt_k(abs(change))} ({sign}{abs(chg_pct):.2f}%)</b>'
                '</div></div>'
            )

    with hero_r:
        snap_date = today.strftime("%B %d, %Y")
        port_gain = total_investments - cost_basis
        eq_pct    = home_equity / a["home_current_value"] * 100 if a["home_current_value"] else 0

        # Build compact NW breakdown bars for embedding in snapshot card
        _snap_nw = [
            ("Home Value",   a["home_current_value"],       "asset"),
            ("Investments",  total_investments,             "asset"),
            ("HYSA",         a["emergency_fund_balance"],   "asset"),
            ("Sinking Fund", sinking_fund,                  "asset"),
            ("Checking",     a["checking_savings_balance"], "asset"),
            ("Mortgage",     status["current_balance"],     "liab"),
        ]
        for _d in a["other_debts"]:
            _snap_nw.append((_d["name"], _d["balance"], "liab"))
        _snap_nw = [_it for _it in _snap_nw if _it[1] > 0]
        _snap_max = max(_it[1] for _it in _snap_nw) or 1

        _snap_bars = ""
        for _nm, _v, _typ in _snap_nw:
            _w = (_v / _snap_max) ** 0.45 * 100
            _rc = " right" if _typ == "liab" else ""
            _snap_bars += (
                f'<div class="dv2-nw-row{_rc}" style="margin-bottom:5px">'
                f'<div class="name" style="width:88px;font-size:0.7rem">{_html.escape(_nm)}</div>'
                f'<div class="barwrap" style="height:15px">'
                f'<div class="bar {_typ}" style="width:{_w:.1f}%;min-width:2px">'
                f'<span class="amt" style="font-size:0.62rem">{_fmt_k(_v)}</span>'
                f'</div></div></div>'
            )

        st.markdown(f"""
        <div class="dv2-card" style="margin-bottom:0">
          <div class="dv2-h">Snapshot <span class="meta">{snap_date}</span></div>
          <div class="dv2-snap-grid">
            <div class="dv2-snap purple">
              <div class="lab">Net Worth</div>
              <div class="val cond">{_fmt_k(net_worth)}</div>
              <div class="sub">Assets − Liabilities</div>
            </div>
            <div class="dv2-snap blue">
              <div class="lab">Portfolio</div>
              <div class="val cond">{_fmt_k(total_investments)}</div>
              <div class="sub">{len(a["investment_accounts"])} accounts · {_fmt_k(port_gain)} gain</div>
            </div>
            <div class="dv2-snap green">
              <div class="lab">Home Equity</div>
              <div class="val cond">{_fmt_k(home_equity)}</div>
              <div class="sub">{eq_pct:.1f}% of {_fmt_k(a["home_current_value"])}</div>
            </div>
            <div class="dv2-snap amber">
              <div class="lab">Liquid Cash</div>
              <div class="val cond">{_fmt_k(liquid_cash)}</div>
              <div class="sub">{ef_months:.1f} months runway</div>
            </div>
          </div>

          <div style="margin-top:16px">
            <div class="dv2-headline-row" style="margin-bottom:10px">
              <div class="lab">Net Worth Breakdown</div>
              <div class="mono" style="font-size:0.72rem;color:#a78bfa">{_fmt_k(net_worth)}</div>
            </div>
            {_snap_bars}
            <div style="display:flex;justify-content:space-between;border-top:1px solid rgba(255,255,255,0.07);
              padding-top:8px;margin-top:8px">
              <div style="text-align:left">
                <div style="font-size:0.58rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.1em;font-weight:700">Assets</div>
                <div style="font-family:\'Barlow Condensed\';font-size:1.15rem;font-weight:700;color:#34d399">{_fmt_k(total_assets)}</div>
              </div>
              <div style="text-align:center">
                <div style="font-size:0.58rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.1em;font-weight:700">Liabilities</div>
                <div style="font-family:\'Barlow Condensed\';font-size:1.15rem;font-weight:700;color:#f87171">−{_fmt_k(total_liab)}</div>
              </div>
              <div style="text-align:right">
                <div style="font-size:0.58rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.1em;font-weight:700">Net Worth</div>
                <div style="font-family:\'Barlow Condensed\';font-size:1.15rem;font-weight:700;color:#a78bfa">{_fmt_k(net_worth)}</div>
              </div>
            </div>
          </div>

          <div style="margin-top:14px">
            <div class="dv2-headline-row">
              <div class="lab">Mortgage paid off</div>
              <div class="mono" style="font-size:0.78rem;color:#06b6d4">{mort_pct:.1f}% paid</div>
            </div>
            <div class="dv2-meter amber"><div class="fill" style="width:{mort_pct}%"></div></div>
            <div style="display:flex;justify-content:space-between;margin-top:6px;font-size:0.68rem;color:#64748b">
              <span>{_fmt_k(a["loan_original_amount"] - status["current_balance"])} paid</span>
              <span>Payoff {status["payoff_date"].strftime("%b %Y")}</span>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 3. KPI STRIP — 6 cards with sparklines
    # ═══════════════════════════════════════════════════════════════════════
    ltv = status["current_balance"] / a["home_current_value"] * 100 if a["home_current_value"] else 0
    eq_pct = 100 - ltv

    cf_color  = "var(--dv2-green-2)" if net_cf >= 0 else "var(--dv2-red-2)"
    cf_accent = "#34d399" if net_cf >= 0 else "#f87171"
    sr_color  = "var(--dv2-green-2)" if savings_rate >= 15 else (
        "var(--dv2-amber)" if savings_rate >= 10 else "var(--dv2-red-2)")
    sr_accent = "#34d399" if savings_rate >= 15 else ("#f59e0b" if savings_rate >= 10 else "#f87171")
    ef_color  = "var(--dv2-green-2)" if ef_months >= a["emergency_fund_target_months"] else (
        "var(--dv2-amber)" if ef_months >= 3 else "var(--dv2-red-2)")
    ef_accent = "#34d399" if ef_months >= a["emergency_fund_target_months"] else (
        "#f59e0b" if ef_months >= 3 else "#f87171")

    kpis = [
        {"lab": "Net Worth",         "val": _fmt_k(net_worth),
         "sub": "Assets − Liabilities", "accent": "#a78bfa",
         "spark": _rand_spark(14, 1.4, 1)},
        {"lab": "Portfolio",         "val": _fmt_k(total_investments),
         "sub": f'{len(a["investment_accounts"])} accounts', "accent": "#60a5fa",
         "spark": _rand_spark(14, 1.0, 2)},
        {"lab": "Home Equity",       "val": _fmt_k(home_equity),
         "sub": f"{eq_pct:.1f}% equity · LTV {ltv:.1f}%", "accent": "#34d399",
         "spark": _rand_spark(14, 0.8, 3)},
        {"lab": "Monthly Cash Flow", "val": _fmt_dollar(net_cf),
         "sub": "Surplus" if net_cf >= 0 else "Deficit",
         "accent": cf_accent, "valColor": cf_color,
         "spark": _rand_spark(14, 1.2 if net_cf >= 0 else -0.5, 4)},
        {"lab": "Savings Rate",      "val": f"{savings_rate:.1f}%",
         "sub": "of monthly income", "accent": sr_accent, "valColor": sr_color,
         "spark": _rand_spark(14, 0.9, 5)},
        {"lab": "Emergency Fund",    "val": f"{ef_months:.1f} mo",
         "sub": f'goal: {a["emergency_fund_target_months"]} months',
         "accent": ef_accent, "valColor": ef_color,
         "spark": _rand_spark(14, 0.6, 6)},
    ]

    kpi_html = '<div class="dv2-kpi-grid">'
    for k in kpis:
        spark = _sparkline_svg(k["spark"], k["accent"])
        val_style = f'style="color:{k["valColor"]}"' if k.get("valColor") else ""
        kpi_html += f"""
        <div class="dv2-kpi">
          <div class="accent" style="background:{k['accent']}"></div>
          <div class="spark">{spark}</div>
          <div class="lab">{k['lab']}</div>
          <div class="val" {val_style}>{k['val']}</div>
          <div class="sub">{k['sub']}</div>
        </div>"""
    kpi_html += "</div>"
    st.markdown(kpi_html, unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 4. TODAY'S MOVE STRIP
    # ═══════════════════════════════════════════════════════════════════════
    if abs(daily_gain) > 0.5 and live_prices and prev_prices:
        is_up = daily_gain >= 0
        cls = "up" if is_up else "dn"
        arrow = "▲" if is_up else "▼"
        sign = "+" if is_up else "−"
        per_acct = []
        for acct in a["investment_accounts"]:
            d = _acct_day(acct)
            if abs(d) > 1:
                per_acct.append((acct["label"], d))
        acct_html = ""
        for lbl, d in per_acct:
            acct_color = "#34d399" if d >= 0 else "#f87171"
            sign_d = "+" if d >= 0 else "−"
            acct_html += (
                f'<span class="sep">·</span>'
                f'<span class="acc">{_html.escape(lbl)}: '
                f'<b style="color:{acct_color}">{sign_d}{_fmt_dollar(abs(d))}</b></span>'
            )
        st.markdown(f"""
        <div class="dv2 dv2-move {cls}">
          <span class="ttl">Today's Move</span>
          <span class="big">{arrow} {sign}{_fmt_dollar(abs(daily_gain))}
            <span class="pct">({sign}{abs(daily_pct):.2f}%)</span>
          </span>
          {acct_html}
        </div>
        """, unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # 5. ROW 3 — Allocation Donut / Sector allocation
    # ═══════════════════════════════════════════════════════════════════════
    r3b, r3c = st.columns([0.9, 1.1])

    # ── Allocation Donut ──────────────────────────────────────────────────
    with r3b:
        donut_items = []
        for i, acct in enumerate(a["investment_accounts"]):
            mv = _acct_mv(acct)
            if mv > 0:
                donut_items.append((acct["label"], mv, ACCT_COLORS[i % len(ACCT_COLORS)]))
        donut_items.append(("HYSA", a["emergency_fund_balance"], "#f43f5e"))
        if sinking_fund > 0:
            donut_items.append(("Sinking Fund", sinking_fund, "#f97316"))
        donut_items.append(("Checking/Savings", a["checking_savings_balance"], "#06b6d4"))
        donut_items = [d for d in donut_items if d[1] > 0]
        donut_total = sum(d[1] for d in donut_items)

        with st.container(border=True):
            st.html(
                '<div class="dv2 dv2-h">Allocation '
                '<span class="meta">All assets</span></div>'
            )

            fig_donut = go.Figure(go.Pie(
                labels=[d[0] for d in donut_items],
                values=[d[1] for d in donut_items],
                hole=0.66,
                marker=dict(
                    colors=[d[2] for d in donut_items],
                    line=dict(color=tc["card"], width=3),
                ),
                textinfo="none",
                sort=False,
                direction="clockwise",
                rotation=90,
                hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>",
            ))
            fig_donut.add_annotation(
                text=f"<b>{_fmt_k(donut_total)}</b>",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=20, color=tc["bright"], family="Barlow Condensed"),
            )
            fig_donut.update_layout(**chart_layout(
                height=240,
                margin=dict(l=10, r=10, t=10, b=10),
                showlegend=False,
            ))
            st.plotly_chart(fig_donut, use_container_width=True, config={"displayModeBar": False})

            # Legend
            legend_items = sorted(donut_items, key=lambda x: -x[1])
            leg_html = '<div class="dv2 dv2-donut-legend">'
            for nm, v, c in legend_items:
                pct = v / donut_total * 100 if donut_total else 0
                leg_html += (
                    f'<div class="lr">'
                    f'<span class="sw" style="background:{c}"></span>'
                    f'<span class="nm">{_html.escape(nm)}</span>'
                    f'<span class="pc">{_fmt_k(v)} · {pct:.1f}%</span>'
                    f'</div>'
                )
            leg_html += "</div>"
            st.html(leg_html)

    # ── Sector Allocation vs Target ───────────────────────────────────────
    with r3c:
        sector_targets = a.get("sector_targets") or DEFAULT_TARGET_ALLOC
        sector_vals = {}
        port_total = 0
        for acct in a["investment_accounts"]:
            for h in acct.get("holdings", []):
                sec = _holding_sector(h)
                mv = _holding_mv(h)
                sector_vals[sec] = sector_vals.get(sec, 0) + mv
                port_total += mv

        if port_total <= 0:
            port_total = 1

        # Build rows for sectors that have actual holdings (cur > 0)
        # Also include sectors from the target list only if they have holdings
        all_sectors = list(set(list(sector_targets.keys()) + list(sector_vals.keys())))
        rows = sorted([
            {"name": s, "cur": sector_vals.get(s, 0) / port_total * 100,
             "target": sector_targets.get(s, 0)}
            for s in all_sectors
            if sector_vals.get(s, 0) > 0   # only show sectors with actual holdings
        ], key=lambda r: -r["cur"])

        max_scale = max(40, max((max(r["cur"], r["target"]) for r in rows), default=40))

        sec_html = ""
        for r in rows:
            is_over = r["cur"] > r["target"] * 1.1 and r["target"] > 0
            cur_w = r["cur"] / max_scale * 100
            tgt_w = r["target"] / max_scale * 100
            over_cls = " over" if is_over else ""
            sec_html += (
                f'<div class="dv2-sector-row">'
                f'<div class="dv2-sector-head">'
                f'<span class="nm">{_html.escape(r["name"])}</span>'
                f'<span class="vs"><b>{r["cur"]:.1f}%</b> / {r["target"]}%</span>'
                f'</div>'
                f'<div class="dv2-sector-bar">'
                f'<div class="cur{over_cls}" style="width:{cur_w:.1f}%"></div>'
                f'<div class="target" style="left:{tgt_w:.1f}%"></div>'
                f'</div></div>'
            )

        legend_html = (
            '<div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--dv2-line);'
            'display:flex;align-items:center;gap:18px;font-size:0.68rem;color:var(--dv2-muted)">'
            '<span style="display:inline-flex;align-items:center;gap:6px">'
            '<span style="width:10px;height:8px;background:linear-gradient(90deg,var(--dv2-blue),var(--dv2-blue-2));border-radius:2px"></span>Current</span>'
            '<span style="display:inline-flex;align-items:center;gap:6px">'
            '<span style="width:2px;height:11px;background:var(--dv2-text-2)"></span>Target</span>'
            '<span style="display:inline-flex;align-items:center;gap:6px">'
            '<span style="width:10px;height:8px;background:linear-gradient(90deg,var(--dv2-amber),#fbbf24);border-radius:2px"></span>Over target</span>'
            '</div>'
        )

        with st.container(border=True):
            st.html(
                '<div class="dv2">'
                '<div class="dv2-h">Sector Allocation <span class="meta">vs target</span></div>'
                f'{sec_html}{legend_html}'
                '</div>'
            )

    # ═══════════════════════════════════════════════════════════════════════
    # 6. ROW 2 — Cash Flow Waterfall + Debt Payoff
    # ═══════════════════════════════════════════════════════════════════════
    r6a, r6b = st.columns([1, 1])

    # ── Cash Flow Waterfall (Plotly) ──────────────────────────────────────
    with r6a:
        with st.container(border=True):
            st.html(
                '<div class="dv2 dv2-h">Monthly Cash Flow '
                '<span class="meta">Monthly snapshot</span></div>'
            )

            wf_labels = ["Income", "Housing", "Other Debts", "Variable<br>Spending",
                         "Investments", "Net Surplus"]
            wf_values = [monthly_in, -housing, -debts, -budget, -invest_mo, net_cf]
            wf_measures = ["absolute", "relative", "relative", "relative", "relative", "total"]
            wf_text = [
                f"+{_fmt_dollar(monthly_in)}",
                f"−{_fmt_dollar(housing)}",
                f"−{_fmt_dollar(debts)}",
                f"−{_fmt_dollar(budget)}",
                f"−{_fmt_dollar(invest_mo)}",
                f"{'+' if net_cf >= 0 else '−'}{_fmt_dollar(abs(net_cf))}",
            ]

            fig_wf = go.Figure(go.Waterfall(
                x=wf_labels, y=wf_values, measure=wf_measures,
                text=wf_text, textposition="outside",
                textfont=dict(size=11, color=tc["text"], family="JetBrains Mono"),
                connector=dict(line=dict(color=tc["connector"], width=1)),
                increasing=dict(marker=dict(color=GREEN, line=dict(width=0))),
                decreasing=dict(marker=dict(color=RED,   line=dict(width=0))),
                totals=dict(marker=dict(color=GREEN if net_cf >= 0 else RED, line=dict(width=0))),
                cliponaxis=False,
            ))
            fig_wf.update_layout(**chart_layout(
                height=260,
                showlegend=False,
                margin=dict(l=10, r=10, t=30, b=20),
                yaxis=dict(tickprefix="$", tickformat=",.0s",
                           gridcolor=tc["grid"], showline=False, zeroline=False),
                xaxis=dict(showgrid=False, showline=False, zeroline=False,
                           tickfont=dict(size=10, color=tc["muted"])),
            ))
            st.plotly_chart(fig_wf, use_container_width=True, config={"displayModeBar": False})

            net_color = "var(--dv2-green-2)" if net_cf >= 0 else "var(--dv2-red-2)"
            st.html(
                '<div class="dv2" style="margin-top:12px;padding-top:12px;border-top:1px solid var(--dv2-line);'
                'display:flex;justify-content:space-around;font-size:0.7rem;color:var(--dv2-muted)">'
                '<div style="text-align:center">'
                f'<div style="font-family:\'Barlow Condensed\';font-size:1.25rem;font-weight:700;color:var(--dv2-green-2)">{_fmt_k(monthly_in)}</div>'
                '<div>Income</div></div>'
                '<div style="text-align:center">'
                f'<div style="font-family:\'Barlow Condensed\';font-size:1.25rem;font-weight:700;color:var(--dv2-red-2)">−{_fmt_k(housing + debts + budget)}</div>'
                '<div>Expenses</div></div>'
                '<div style="text-align:center">'
                f'<div style="font-family:\'Barlow Condensed\';font-size:1.25rem;font-weight:700;color:var(--dv2-amber)">−{_fmt_k(invest_mo)}</div>'
                '<div>Invested</div></div>'
                '<div style="text-align:center">'
                f'<div style="font-family:\'Barlow Condensed\';font-size:1.25rem;font-weight:700;color:{net_color}">{"+" if net_cf >= 0 else "−"}{_fmt_k(abs(net_cf))}</div>'
                '<div>Net surplus</div></div>'
                '</div>'
            )

    # ── Debt Payoff Timeline ──────────────────────────────────────────────
    with r6b:
        yrs_left = status["months_remaining"] / 12
        mort_paid = a["loan_original_amount"] - status["current_balance"]
        debt_html = (
            '<div class="dv2-debt">'
            '<div class="dv2-debt-head">'
            '<span class="nm">Mortgage</span>'
            f'<span class="meta">{yrs_left:.1f} yrs to go · payoff {status["payoff_date"].strftime("%b %Y")}</span>'
            '</div>'
            '<div class="dv2-debt-bar">'
            f'<div class="fl mortgage" style="width:{max(mort_pct, 0.5):.2f}%">'
            f'<span class="pmt">{_fmt_dollar(monthly_pi)}/mo</span>'
            '</div></div>'
            '<div class="dv2-debt-foot">'
            f'<span class="paid">Paid: {_fmt_k(mort_paid)} ({mort_pct:.2f}%)</span>'
            f'<span class="rem">Remaining: {_fmt_k(status["current_balance"])}</span>'
            '</div></div>'
        )
        for d in a["other_debts"]:
            if d["balance"] <= 0:
                continue
            r = d["rate_pct"] / 100 / 12
            if r > 0 and d["monthly_payment"] > d["balance"] * r:
                months_left = math.ceil(
                    -math.log(1 - d["balance"] * r / d["monthly_payment"]) / math.log(1 + r)
                )
            elif d["monthly_payment"] > 0:
                months_left = math.ceil(d["balance"] / d["monthly_payment"])
            else:
                months_left = 999
            yrs_left_d = months_left / 12
            from dateutil.relativedelta import relativedelta
            payoff_d = today + relativedelta(months=months_left)
            pct = 100 - (months_left / (months_left + 60)) * 100
            debt_html += (
                '<div class="dv2-debt">'
                '<div class="dv2-debt-head">'
                f'<span class="nm">{_html.escape(d["name"])}</span>'
                f'<span class="meta">{_fmt_k(d["balance"])} at {d["rate_pct"]}% · {yrs_left_d:.1f} yrs left</span>'
                '</div>'
                '<div class="dv2-debt-bar">'
                f'<div class="fl other" style="width:{pct:.1f}%">'
                f'<span class="pmt">{_fmt_dollar(d["monthly_payment"])}/mo</span>'
                '</div></div>'
                '<div class="dv2-debt-foot">'
                f'<span class="paid">{_fmt_dollar(d["monthly_payment"])}/mo payment</span>'
                f'<span class="rem">Payoff: ~{payoff_d.strftime("%b %Y")}</span>'
                '</div></div>'
            )

        with st.container(border=True):
            st.html(
                '<div class="dv2">'
                f'<div class="dv2-h">Debt Payoff Timeline <span class="meta">{_fmt_k(total_liab)} total</span></div>'
                f'{debt_html}'
                '</div>'
            )

    # ═══════════════════════════════════════════════════════════════════════
    # 7. ROW 2 — Investment Accounts + Top Holdings
    # ═══════════════════════════════════════════════════════════════════════
    r7a, r7b = st.columns([1, 1])

    # ── Investment Accounts ───────────────────────────────────────────────
    with r7a:
        acct_items = []
        for i, ac in enumerate(a["investment_accounts"]):
            mv = _acct_mv(ac)
            day = _acct_day(ac)
            day_pct = (day / (mv - day) * 100) if (mv - day) else 0
            acct_items.append({
                "ac": ac, "mv": mv, "day": day, "day_pct": day_pct,
                "color": ACCT_COLORS[i % len(ACCT_COLORS)],
            })
        acct_items.sort(key=lambda x: -x["mv"])

        acct_html = '<div class="dv2-acct-list">'
        for it in acct_items:
            ac = it["ac"]
            mv = it["mv"]
            day = it["day"]
            day_pct = it["day_pct"]
            day_color = "var(--dv2-green-2)" if day >= 0 else "var(--dv2-red-2)"
            day_sign = "+" if day >= 0 else "−"
            day_pct_sign = "+" if day_pct >= 0 else ""
            type_label = ac["account_type"]
            if ac["monthly_contribution"] > 0:
                type_label += f' · {_fmt_dollar(ac["monthly_contribution"])}/mo'
            acct_html += (
                '<div class="dv2-acct">'
                f'<div class="swatch" style="background:{it["color"]}"></div>'
                '<div>'
                f'<div class="nm">{_html.escape(ac["label"])}</div>'
                f'<div class="ty">{_html.escape(type_label)}</div>'
                '</div>'
                '<div>'
                f'<div class="bal cond">{_fmt_k(mv)}</div>'
                f'<div class="day" style="color:{day_color}">'
                f'{day_sign}{_fmt_dollar(abs(day))} ({day_pct_sign}{day_pct:.2f}%)'
                '</div></div></div>'
            )
        acct_html += "</div>"

        with st.container(border=True):
            st.html(
                '<div class="dv2">'
                f'<div class="dv2-h">Investment Accounts <span class="meta">{_fmt_k(total_investments)} · {len(acct_items)} accounts</span></div>'
                f'{acct_html}'
                '</div>'
            )

    # ── Top Holdings ──────────────────────────────────────────────────────
    with r7b:
        all_h = []
        for ac in a["investment_accounts"]:
            for h in ac.get("holdings", []):
                tk = h.get("ticker")
                if not tk:
                    continue
                px_ = live_prices.get(tk) or h.get("avg_cost") or 0
                prev = prev_prices.get(tk)
                mv = h["shares"] * px_
                day_chg = (px_ - prev) if prev else 0
                day_pct = ((px_ - prev) / prev * 100) if prev else 0
                all_h.append({
                    "ticker": tk,
                    "sector": _holding_sector(h),
                    "shares": h["shares"],
                    "px": px_,
                    "day_pct": day_pct,
                    "day_chg": day_chg,
                    "mv": mv,
                })
        all_h.sort(key=lambda x: -x["mv"])
        top = all_h[:10]

        rows_html = ""
        for h in top:
            sec_color = SECTOR_COLORS.get(h["sector"], "#64748b")
            ticker_disp = h["ticker"].lstrip("_")
            ic_text = ticker_disp[:3] if len(ticker_disp) <= 4 else ticker_disp[:2]
            day_color = "#34d399" if h["day_chg"] >= 0 else "#f87171"
            day_sign = "+" if h["day_pct"] >= 0 else ""
            rows_html += (
                '<tr><td>'
                '<span class="dv2-tk">'
                f'<span class="ic" style="background:{sec_color}">{_html.escape(ic_text)}</span>'
                '<span class="nm">'
                f'<span class="sym">{_html.escape(ticker_disp)}</span>'
                f'<span class="nt">{_html.escape(h["sector"])}</span>'
                '</span></span></td>'
                f'<td class="r">{h["shares"]:,.4f}</td>'
                f'<td class="r">{_fmt_px(h["px"])}</td>'
                f'<td class="r" style="color:{day_color}">{day_sign}{h["day_pct"]:.2f}%</td>'
                f'<td class="r val">{_fmt_k(h["mv"])}</td>'
                '</tr>'
            )

        with st.container(border=True):
            st.html(
                '<div class="dv2">'
                '<div class="dv2-h">Top Holdings <span class="meta">By market value</span></div>'
                '<table class="dv2-holdings">'
                '<thead><tr>'
                '<th>Position</th>'
                '<th class="r">Shares</th>'
                '<th class="r">Price</th>'
                '<th class="r">Day</th>'
                '<th class="r">Value</th>'
                '</tr></thead>'
                f'<tbody>{rows_html}</tbody>'
                '</table>'
                '</div>'
            )

    # ═══════════════════════════════════════════════════════════════════════
    # 8. MILESTONE TRACKER
    # ═══════════════════════════════════════════════════════════════════════
    milestones = a.get("milestones") or []
    if milestones:
        ms_sorted = sorted(milestones, key=lambda m: m["age"])
        ms_html = ""
        for m in ms_sorted:
            target = m["target_nw"]
            pct = min(net_worth / target * 100, 100) if target else 0
            done = net_worth >= target
            future = m["age"] > a["age"] and not done
            cls = "done" if done else ("future" if future else "")
            chip_label = "✓ Achieved" if done else ("● Active" if not future else "Upcoming")
            ms_html += (
                f'<div class="dv2-ms {cls}">'
                f'<div class="ms-chip"><span class="dot"></span>{chip_label}</div>'
                '<div class="top">'
                '<div class="left">'
                f'<span class="ttl">Age {m["age"]} · {_fmt_k(target)}</span>'
                f'<span class="ev">{_html.escape(m["event"])}</span>'
                '</div>'
                f'<span class="pc">{pct:.0f}%<br><span style="font-size:0.62rem;font-weight:400;opacity:0.8">{_fmt_k(net_worth)} of {_fmt_k(target)}</span></span>'
                '</div>'
                f'<div class="mtrack"><div class="mfill" style="width:{pct}%"></div></div>'
                '</div>'
            )

        with st.container(border=True):
            st.html(
                '<div class="dv2">'
                '<div class="dv2-h">Milestone Tracker <span class="meta">Path to financial independence</span></div>'
                f'{ms_html}'
                '</div>'
            )


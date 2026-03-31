import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import yfinance as yf
from datetime import date
from utils.calculations import ACCOUNT_LIMITS, calc_monthly_payment
from utils.styles import (
    BLUE, GREEN, RED, PURPLE, AMBER, CYAN, CHART_COLORS, chart_layout,
)
from utils.database import add_transaction, get_transactions, delete_transaction

ACCOUNT_COLORS = {
    "401k":      BLUE,
    "Roth 401k": PURPLE,
    "Trad IRA":  AMBER,
    "Roth IRA":  GREEN,
    "Brokerage": CYAN,
    "HSA":       "#f97316",
    "HYSA":      "#f43f5e",
    "Sinking":   "#f97316",
    "Crypto":    "#a855f7",
}

SP500_WEIGHTS = {
    "Technology": 32, "Financials": 13, "Healthcare": 12,
    "Consumer Cyclical": 10, "Industrials": 9, "Communication Services": 9,
    "Consumer Defensive": 6, "Energy": 4, "Utilities": 3,
    "Real Estate": 2, "Materials": 2,
}

# Yahoo Finance ticker mapping for crypto direct holdings
CRYPTO_YF_MAP = {
    "BTC": "BTC-USD", "ETH": "ETH-USD", "ADA": "ADA-USD",
    "XRP": "XRP-USD", "DOGE": "DOGE-USD",
}


@st.cache_data(ttl=300)
def _get_price(ticker: str) -> float | None:
    try:
        return yf.Ticker(ticker).fast_info.last_price
    except Exception:
        return None


@st.cache_data(ttl=300)
def _fetch_all_prices(tickers: tuple) -> tuple:
    """Fetch live prices and previous closes for all tickers (cached 5 min)."""
    prices = {}
    prev_closes = {}
    for t in tickers:
        yf_t = CRYPTO_YF_MAP.get(t, t)
        try:
            fi = yf.Ticker(yf_t).fast_info
            prices[t] = fi.last_price
            prev_closes[t] = fi.previous_close
        except Exception:
            prices[t] = None
            prev_closes[t] = None
    return prices, prev_closes


def _fv(pv: float, annual_pmt: float, rate: float, years: int) -> float:
    """Future value of a lump sum + constant annual contributions."""
    if rate == 0:
        return pv + annual_pmt * years
    return pv * (1 + rate) ** years + annual_pmt * ((1 + rate) ** years - 1) / rate


def render():
    a        = st.session_state.assumptions
    accounts = a["investment_accounts"]
    age      = int(a["age"])
    ret_age  = int(a.get("retirement_age", 65))

    st.header("Investment Accounts")

    if not accounts:
        st.info("Add investment accounts in the Setup tab.")
        return

    # ── Collect all tickers for batch price fetch ───────────────────────────
    all_tickers = set()
    for acct in accounts:
        for h in acct.get("holdings", []):
            if h.get("ticker"):
                all_tickers.add(h["ticker"])

    live_prices = {}
    prev_closes = st.session_state.get("prev_prices", {})
    if all_tickers:
        with st.spinner("Fetching live prices..."):
            live_prices, fetched_prev = _fetch_all_prices(tuple(sorted(all_tickers)))
            # Merge fetched prev closes (local fetch may have fresher data)
            prev_closes = {**prev_closes, **{k: v for k, v in fetched_prev.items() if v}}

    # ── Compute live market values per account ──────────────────────────────
    def _acct_market_value(acct):
        """Market value = sum(shares * live_price) + cash."""
        cash = acct.get("cash_usd", 0)
        total = cash
        for h in acct.get("holdings", []):
            tk = h.get("ticker")
            if tk and live_prices.get(tk):
                total += h["shares"] * live_prices[tk]
        return total

    def _acct_cost_basis(acct):
        """Total cost basis = sum(shares * avg_cost) + cash."""
        cash = acct.get("cash_usd", 0)
        total = cash
        for h in acct.get("holdings", []):
            if h.get("avg_cost") is not None:
                total += h["shares"] * h["avg_cost"]
        return total

    # Compute live balances (fall back to stored balance if no live prices)
    acct_mkt_values = {}
    acct_cost_bases = {}
    for acct in accounts:
        has_priced_holdings = any(
            h.get("ticker") and live_prices.get(h["ticker"])
            for h in acct.get("holdings", [])
        )
        if has_priced_holdings:
            acct_mkt_values[acct["_id"]] = _acct_market_value(acct)
        else:
            acct_mkt_values[acct["_id"]] = acct["balance"]
        acct_cost_bases[acct["_id"]] = _acct_cost_basis(acct)

    # ── LP -> Joint Brokerage flow ──────────────────────────────────────────
    lp_jb_pct        = a.get("lp_jb_pct", 85)
    lp_net_factor    = a.get("lp_net_pct", 100) / 100
    lp_gross_monthly = a.get("parkwood_lp_monthly", 0)
    lp_net_monthly   = lp_gross_monthly * lp_net_factor
    lp_to_jb_monthly = lp_net_monthly * lp_jb_pct / 100
    lp_to_jb_annual  = lp_to_jb_monthly * 12

    # ── HYSA / Emergency Fund ───────────────────────────────────────────────
    hysa_balance    = a.get("emergency_fund_balance", 0)
    sinking_balance = a.get("sinking_fund_balance", 0)
    hysa_target_mo  = a.get("emergency_fund_target_months", 6)

    # ── Portfolio totals (live) ─────────────────────────────────────────────
    total_mkt_value = sum(acct_mkt_values.values())
    total_cost_basis = sum(acct_cost_bases.values())
    total_unrealized = total_mkt_value - total_cost_basis
    total_monthly = sum(acct["monthly_contribution"] for acct in accounts)

    total_match = 0.0
    for acct in accounts:
        if acct["account_type"] in ("401k", "Roth 401k") and acct.get("employer_match_pct", 0) > 0:
            cap          = a["gross_income"] * acct.get("employer_match_ceiling_pct", 0) / 100 / 12
            total_match += min(acct["monthly_contribution"], cap) * acct["employer_match_pct"] / 100

    monthly_total_in = total_monthly + lp_to_jb_monthly + total_match
    annual_total_in  = monthly_total_in * 12
    ret_pct          = float(a.get("investment_return_pct", 7.0))
    years_left       = max(1, ret_age - age)
    est_at_retire    = _fv(total_mkt_value, annual_total_in, ret_pct / 100, years_left)

    grand_total = total_mkt_value + hysa_balance + sinking_balance

    # ── Daily gain across all priced holdings ──────────────────────────────
    daily_gain = 0.0
    for acct in accounts:
        for h in acct.get("holdings", []):
            tk = h.get("ticker")
            if tk and live_prices.get(tk) and prev_closes.get(tk):
                daily_gain += (live_prices[tk] - prev_closes[tk]) * h["shares"]

    # ── KPI Row ─────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Holdings", f"${grand_total:,.0f}",
              delta=f"Portfolio ${total_mkt_value:,.0f} + Cash ${hysa_balance + sinking_balance:,.0f}",
              delta_color="off")

    day_sign = "+" if daily_gain >= 0 else ""
    day_color = "normal" if daily_gain >= 0 else "inverse"
    day_pct = (daily_gain / (total_mkt_value - daily_gain) * 100
               if (total_mkt_value - daily_gain) != 0 else 0)
    k2.metric("Today's Move", f"{day_sign}${daily_gain:,.0f}",
              delta=f"{day_sign}{day_pct:.2f}% vs yesterday's close",
              delta_color=day_color)

    k3.metric("Monthly Into Market",
              f"${total_monthly + lp_to_jb_monthly:,.0f}",
              delta=f"${total_monthly:,.0f} + ${lp_to_jb_monthly:,.0f} LP",
              delta_color="off")
    k4.metric("Employer Match", f"${total_match:,.0f}/mo",
              delta=f"${total_match * 12:,.0f}/yr free", delta_color="off")
    k5.metric(f"Est. at {ret_age}",
              f"${est_at_retire / 1_000_000:.2f}M" if est_at_retire >= 1_000_000 else f"${est_at_retire:,.0f}",
              delta=f"{ret_pct:.0f}% return, {years_left}yr", delta_color="off")

    st.divider()

    # ── Allocation donut + Contribution Health ──────────────────────────────
    left_col, right_col = st.columns([1, 1])

    with left_col:
        alloc_rows = []
        for acct in accounts:
            mv = acct_mkt_values[acct["_id"]]
            if mv > 0:
                alloc_rows.append({"Account": acct["label"], "Type": acct["account_type"], "Balance": mv})
        if hysa_balance > 0:
            alloc_rows.append({"Account": "HYSA", "Type": "HYSA", "Balance": hysa_balance})
        if sinking_balance > 0:
            alloc_rows.append({"Account": "Sinking Fund", "Type": "Sinking", "Balance": sinking_balance})

        if alloc_rows:
            alloc_df = pd.DataFrame(alloc_rows)
            colors   = [ACCOUNT_COLORS.get(t, "#475569") for t in alloc_df["Type"]]
            n_accts  = len([ac for ac in accounts if acct_mkt_values[ac["_id"]] > 0])
            n_accts += (1 if hysa_balance > 0 else 0) + (1 if sinking_balance > 0 else 0)

            fig_donut = go.Figure(go.Pie(
                labels=alloc_df["Account"],
                values=alloc_df["Balance"],
                hole=0.62,
                marker=dict(colors=colors, line=dict(color="#020817", width=3)),
                textinfo="none",
                hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>",
            ))
            fig_donut.add_annotation(
                text=(f"<b>${grand_total / 1000:.0f}k</b><br>"
                      f"<span style='font-size:11px;color:#cbd5e1'>{n_accts} accounts</span>"),
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=18, color="#f1f5f9"),
                align="center",
            )
            fig_donut.update_layout(**chart_layout(
                title="Portfolio by Account",
                height=380,
                showlegend=True,
                legend=dict(
                    orientation="h",
                    x=0.5, y=-0.15,
                    xanchor="center",
                    font=dict(size=10, color="#e2e8f0"),
                    itemwidth=30,
                ),
                margin=dict(l=20, r=20, t=50, b=80),
            ))
            st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.info("Add balances in Setup to see allocation.")

    with right_col:
        st.markdown("##### Contribution Health")
        st.caption(f"YTD contributions vs {date.today().year} IRS limits")
        st.markdown("<br>", unsafe_allow_html=True)

        _today = date.today()
        _months_elapsed = (_today - date(_today.year, 1, 1)).days / 365 * 12

        for acct in accounts:
            if acct.get("skip_contribution"):
                continue

            acct_type    = acct["account_type"]
            color        = ACCOUNT_COLORS.get(acct_type, "#475569")
            limits       = ACCOUNT_LIMITS.get(acct_type, {})
            catchup_age  = 55 if acct_type == "HSA" else 50
            limit        = limits.get("catchup" if age >= catchup_age else "base")
            is_jb        = acct_type == "Brokerage"

            ytd_c        = acct.get("ytd_contributed",
                                    acct["monthly_contribution"] * _months_elapsed)
            display_ann  = acct["monthly_contribution"] * 12 + (lp_to_jb_annual if is_jb else 0)

            st.markdown(
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">'
                f'<span style="background:{color}33;color:{color};padding:2px 9px;'
                f'border-radius:9999px;font-size:0.7rem;font-weight:700;letter-spacing:.5px">'
                f'{acct_type}</span>'
                f'<span style="color:#e2e8f0;font-size:0.9rem;font-weight:600">'
                f'{acct["label"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            if limit:
                pct     = min(ytd_c / limit * 100, 100)
                room    = max(0, limit - ytd_c)
                bar_col = GREEN if pct >= 100 else (AMBER if pct >= 80 else BLUE)
                status  = "Maxed!" if room < 1 else f"${room:,.0f} left this year"
                st.markdown(
                    f'<div style="background:#1e293b;border-radius:6px;height:10px;overflow:hidden">'
                    f'<div style="background:{bar_col};width:{pct:.1f}%;height:10px;'
                    f'border-radius:6px"></div></div>'
                    f'<div style="display:flex;justify-content:space-between;'
                    f'color:#94a3b8;font-size:0.75rem;margin-top:4px;margin-bottom:16px">'
                    f'<span>${ytd_c:,.0f} of ${limit:,.0f} YTD</span>'
                    f'<span style="color:{"#22c55e" if room < 1 else "#94a3b8"}">{status}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                lp_note = (f" incl. ${lp_to_jb_annual:,.0f} LP inflow"
                           if is_jb and lp_to_jb_annual > 0 else "")
                st.markdown(
                    f'<div style="color:#64748b;font-size:0.8rem;margin-bottom:16px">'
                    f'${display_ann:,.0f}/yr · No IRS limit{lp_note}</div>',
                    unsafe_allow_html=True,
                )

    st.divider()

    # ── Growth Projection ───────────────────────────────────────────────────
    st.subheader("Growth Projection")
    st.caption(
        f"${total_monthly:,.0f}/mo contributions  ·  "
        f"${lp_to_jb_monthly:,.0f}/mo LP inflow  ·  "
        f"${total_match:,.0f}/mo employer match"
    )

    cur_year   = date.today().year
    years_list = list(range(years_left + 1))
    x_yrs      = [cur_year + y for y in years_list]

    def series(rate_pct):
        r = rate_pct / 100
        return [_fv(total_mkt_value, annual_total_in, r, y) for y in years_list]

    base_s = series(ret_pct)
    bull_s = series(ret_pct + 3)
    bear_s = series(max(1.0, ret_pct - 3))

    fig_g = go.Figure()
    fig_g.add_trace(go.Scatter(
        x=x_yrs + x_yrs[::-1],
        y=bull_s + bear_s[::-1],
        fill="toself", fillcolor="rgba(59,130,246,0.10)",
        line=dict(width=0), showlegend=True,
        name=f"Range ({max(ret_pct - 3, 1):.0f}%-{ret_pct + 3:.0f}%)",
        hoverinfo="skip",
    ))
    fig_g.add_trace(go.Scatter(
        x=x_yrs, y=base_s,
        mode="lines+markers",
        line=dict(color=BLUE, width=2.5),
        marker=dict(size=4, color=BLUE),
        name=f"Base ({ret_pct:.0f}%)",
        hovertemplate="%{x}: <b>$%{y:,.0f}</b><extra></extra>",
    ))
    fig_g.add_vline(
        x=cur_year + years_left, line_dash="dot",
        line_color="#475569", line_width=1.5,
        annotation_text=f"Retirement (age {ret_age})",
        annotation_font_color="#94a3b8",
        annotation_position="top right",
    )
    _y_max = max(bull_s) * 1.08
    _y_min = min(100_000, min(bear_s) * 0.92)
    for m in range(1_000_000, int(_y_max) + 1, 1_000_000):
        is_major = (m % 5_000_000 == 0)
        fig_g.add_hline(
            y=m,
            line_dash="dot" if not is_major else "dash",
            line_color="rgba(255,255,255,0.07)" if not is_major else "rgba(255,255,255,0.18)",
            line_width=1,
        )

    fig_g.update_layout(**chart_layout(
        height=380,
        yaxis=dict(
            range=[_y_min, _y_max],
            tickprefix="$",
            tickformat=",.0s",
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    x=0.5, xanchor="center"),
    ))
    st.plotly_chart(fig_g, use_container_width=True)

    st.divider()

    # ═════════════════════════════════════════════════════════════════════════
    # ACCOUNT DETAIL CARDS (with gains)
    # ═════════════════════════════════════════════════════════════════════════
    st.subheader("Account Details")

    _today = date.today()
    _months_elapsed = (_today - date(_today.year, 1, 1)).days / 365 * 12

    for acct in accounts:
        acct_type   = acct["account_type"]
        color       = ACCOUNT_COLORS.get(acct_type, "#475569")
        limits      = ACCOUNT_LIMITS.get(acct_type, {})
        catchup_age = 55 if acct_type == "HSA" else 50
        limit       = limits.get("catchup" if age >= catchup_age else "base")
        is_jb       = acct_type == "Brokerage"

        eff_monthly = acct["monthly_contribution"] + (lp_to_jb_monthly if is_jb else 0)
        eff_annual  = eff_monthly * 12

        match_mo = 0.0
        if acct_type in ("401k", "Roth 401k") and acct.get("employer_match_pct", 0) > 0:
            cap      = a["gross_income"] * acct.get("employer_match_ceiling_pct", 0) / 100 / 12
            match_mo = min(acct["monthly_contribution"], cap) * acct["employer_match_pct"] / 100

        mv = acct_mkt_values[acct["_id"]]
        cb = acct_cost_bases[acct["_id"]]
        gain = mv - cb
        gain_pct_acct = (gain / cb * 100) if cb > 0 else 0

        # Daily gain for this account
        acct_daily = sum(
            (live_prices[h["ticker"]] - prev_closes[h["ticker"]]) * h["shares"]
            for h in acct.get("holdings", [])
            if h.get("ticker") and live_prices.get(h["ticker"]) and prev_closes.get(h["ticker"])
        )

        with st.container(border=True):
            # Header row
            r1, r2, r3, r4, r5, r6 = st.columns([3, 2, 2, 2, 2, 2])

            r1.markdown(
                f'<div style="padding-top:6px">'
                f'<span style="font-size:1.05rem;font-weight:700;color:#f1f5f9">'
                f'{acct["label"]}</span>&nbsp;'
                f'<span style="background:{color}33;color:{color};padding:2px 8px;'
                f'border-radius:9999px;font-size:0.68rem;font-weight:700;letter-spacing:.4px">'
                f'{acct_type}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            r2.metric("Market Value", f"${mv:,.0f}")

            # Gain/Loss metric
            if cb > 0 and any(h.get("avg_cost") is not None for h in acct.get("holdings", [])):
                g_sign = "+" if gain >= 0 else ""
                g_color = GREEN if gain >= 0 else RED
                r3.markdown(
                    f'<div style="padding-top:6px">'
                    f'<div style="color:#94a3b8;font-size:0.82rem">Total Gain/Loss</div>'
                    f'<div style="color:{g_color};font-size:1.1rem;font-weight:700">'
                    f'{g_sign}${gain:,.0f}</div>'
                    f'<div style="color:{g_color};font-size:0.75rem">{g_sign}{gain_pct_acct:.1f}%</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                r3.metric("Monthly", f"${eff_monthly:,.0f}",
                          delta=f"${lp_to_jb_monthly:,.0f} LP" if is_jb and lp_to_jb_monthly > 0 else None,
                          delta_color="off")

            # Today's daily move for this account
            if acct_daily != 0:
                ad_sign = "+" if acct_daily >= 0 else ""
                ad_color = GREEN if acct_daily >= 0 else RED
                ad_pct = (acct_daily / (mv - acct_daily) * 100
                          if (mv - acct_daily) != 0 else 0)
                r4.markdown(
                    f'<div style="padding-top:6px">'
                    f'<div style="color:#94a3b8;font-size:0.82rem">Today\'s Move</div>'
                    f'<div style="color:{ad_color};font-size:1.1rem;font-weight:700">'
                    f'{ad_sign}${acct_daily:,.0f}</div>'
                    f'<div style="color:{ad_color};font-size:0.75rem">{ad_sign}{ad_pct:.2f}%</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                r4.metric("Annual", f"${eff_annual:,.0f}")

            r5.metric("Annual", f"${eff_annual:,.0f}")

            if match_mo > 0:
                r6.metric("+ Match", f"${match_mo:,.0f}/mo",
                          delta=f"${match_mo * 12:,.0f}/yr free")
            elif acct.get("cash_usd", 0) > 0:
                r6.metric("Cash", f"${acct['cash_usd']:,.0f}")

            # Notes
            if acct.get("notes"):
                st.caption(acct["notes"])

            # IRS limit progress bar
            if limit:
                card_ytd = acct.get("ytd_contributed",
                                    acct["monthly_contribution"] * _months_elapsed)
                pct      = min(card_ytd / limit * 100, 100)
                room     = max(0, limit - card_ytd)
                bar_col  = GREEN if pct >= 100 else (AMBER if pct >= 80 else BLUE)
                status   = "Maxed!" if room < 1 else f"${room:,.0f} left this year"
                st.markdown(
                    f'<div style="margin-top:10px;background:#0f172a;border-radius:6px;'
                    f'height:8px;overflow:hidden">'
                    f'<div style="background:{bar_col};width:{pct:.1f}%;height:8px;'
                    f'border-radius:6px"></div></div>'
                    f'<div style="display:flex;justify-content:space-between;'
                    f'color:#94a3b8;font-size:0.75rem;margin-top:4px">'
                    f'<span>${card_ytd:,.0f} of ${limit:,.0f} IRS limit YTD</span>'
                    f'<span style="color:{"#22c55e" if room < 1 else "#cbd5e1"}">{status}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            elif is_jb and lp_to_jb_monthly > 0:
                st.markdown(
                    f'<div style="margin-top:10px;color:#64748b;font-size:0.75rem">'
                    f'${lp_to_jb_monthly:,.0f}/mo LP inflow ({lp_jb_pct}% of distributions)  ·  '
                    f'${lp_to_jb_annual:,.0f}/yr  ·  No IRS limit'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # ── Per-holding gains table (for accounts with priced holdings) ─
            priced_holdings = [
                h for h in acct.get("holdings", [])
                if h.get("ticker") and live_prices.get(h["ticker"])
            ]
            if priced_holdings:
                rows = []
                for h in priced_holdings:
                    price = live_prices[h["ticker"]]
                    prev  = prev_closes.get(h["ticker"])
                    mkt = h["shares"] * price
                    cost = h["shares"] * h["avg_cost"] if h.get("avg_cost") is not None else None
                    gl = (mkt - cost) if cost is not None else None
                    gl_pct = (gl / cost * 100) if cost and cost > 0 else None
                    day_chg_usd = ((price - prev) * h["shares"]) if prev else None
                    day_chg_pct = ((price - prev) / prev * 100) if prev else None
                    rows.append({
                        "Ticker": h["ticker"],
                        "Shares": h["shares"],
                        "Price": price,
                        "Day Chg ($)": day_chg_usd,
                        "Day Chg (%)": day_chg_pct,
                        "Avg Cost": h.get("avg_cost"),
                        "Mkt Value": mkt,
                        "Gain ($)": gl,
                        "Gain (%)": gl_pct,
                    })

                h_df = pd.DataFrame(rows)

                # Format the dataframe for display
                fmt = {
                    "Shares": "{:.4f}",
                    "Price": "${:.2f}",
                    "Day Chg ($)": "${:+,.2f}",
                    "Day Chg (%)": "{:+.2f}%",
                    "Avg Cost": "${:.2f}",
                    "Mkt Value": "${:,.2f}",
                    "Gain ($)": "${:+,.2f}",
                    "Gain (%)": "{:+.1f}%",
                }

                def _color_gain(val):
                    if pd.isna(val) or val is None:
                        return ""
                    if isinstance(val, str):
                        return ""
                    return f"color: {GREEN}" if val >= 0 else f"color: {RED}"

                styled = (
                    h_df.style
                    .format(fmt, na_rep="--")
                    .map(_color_gain, subset=["Day Chg ($)", "Day Chg (%)", "Gain ($)", "Gain (%)"])
                )

                with st.expander(f"Holdings ({len(priced_holdings)} positions)", expanded=False):
                    st.dataframe(styled, use_container_width=True, hide_index=True)

            # 401k fund allocations (no live prices)
            fund_holdings = [
                h for h in acct.get("holdings", [])
                if h.get("ticker") is None and h.get("fund_name")
            ]
            if fund_holdings and acct["balance"] > 0:
                with st.expander("Fund Allocation", expanded=False):
                    for fh in fund_holdings:
                        alloc_val = acct["balance"] * fh["pct"] / 100
                        st.markdown(
                            f'<div style="display:flex;justify-content:space-between;'
                            f'padding:4px 0;color:#e2e8f0;font-size:0.85rem">'
                            f'<span>{fh["fund_name"]}</span>'
                            f'<span style="color:#94a3b8">{fh["pct"]}% · ${alloc_val:,.0f}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

    # ═════════════════════════════════════════════════════════════════════════
    # ETF HOLDINGS OVERLAP
    # ═════════════════════════════════════════════════════════════════════════
    st.divider()
    st.subheader("ETF Holdings Overlap")
    st.caption("Top holdings across your equity ETFs — highlights shared positions")

    @st.cache_data(ttl=86400, show_spinner=False)
    def _fetch_etf_holdings(etf_tickers: tuple) -> dict:
        """Fetch top holdings for each ETF (cached 24h)."""
        result = {}
        for etf in etf_tickers:
            try:
                fd = yf.Ticker(etf).funds_data
                h = fd.top_holdings
                if h is not None and len(h) > 0:
                    result[etf] = {
                        "holdings": list(h.index),
                        "weights": {sym: float(w) for sym, w in zip(h.index, h["Holding Percent"])},
                        "names": {sym: str(n) for sym, n in zip(h.index, h["Name"])},
                    }
            except Exception:
                pass
        return result

    # Identify ETFs from portfolio (exclude single stocks, crypto, commodities)
    _SKIP = {"AAPL", "BTC", "ETH", "ADA", "XRP", "DOGE", "IAU", "PDBC", "IBIT", "ETHA"}
    etf_tickers = []
    for acct in accounts:
        for h in acct.get("holdings", []):
            tk = h.get("ticker")
            if tk and tk not in _SKIP and tk not in etf_tickers:
                etf_tickers.append(tk)

    if etf_tickers:
        with st.spinner("Fetching ETF holdings data..."):
            etf_data = _fetch_etf_holdings(tuple(etf_tickers))

        if len(etf_data) >= 2:
            # Build overlap matrix: which stocks appear in which ETFs
            all_stocks = {}  # stock -> set of ETFs
            for etf, data in etf_data.items():
                for stock in data["holdings"]:
                    if stock not in all_stocks:
                        all_stocks[stock] = set()
                    all_stocks[stock].add(etf)

            # Sort stocks by overlap count (most shared first)
            sorted_stocks = sorted(all_stocks.items(), key=lambda x: (-len(x[1]), x[0]))
            overlap_stocks = [(s, etfs) for s, etfs in sorted_stocks if len(etfs) >= 2]
            unique_stocks  = [(s, etfs) for s, etfs in sorted_stocks if len(etfs) == 1]

            etf_list = sorted(etf_data.keys())

            if overlap_stocks:
                # Build heatmap data
                stock_names = [s for s, _ in overlap_stocks[:20]]
                z_data = []
                hover_data = []
                for stock, etfs in overlap_stocks[:20]:
                    row = []
                    hover_row = []
                    for etf in etf_list:
                        if etf in etfs:
                            w = etf_data[etf]["weights"].get(stock, 0) * 100
                            row.append(w)
                            name = etf_data[etf]["names"].get(stock, stock)
                            hover_row.append(f"{name}<br>{stock} in {etf}: {w:.1f}%")
                        else:
                            row.append(0)
                            hover_row.append(f"{stock} not in {etf}")
                    z_data.append(row)
                    hover_data.append(hover_row)

                fig_overlap = go.Figure(go.Heatmap(
                    z=z_data,
                    x=etf_list,
                    y=stock_names,
                    hovertext=hover_data,
                    hovertemplate="%{hovertext}<extra></extra>",
                    colorscale=[
                        [0, "rgba(15,23,42,1)"],
                        [0.01, "rgba(59,130,246,0.15)"],
                        [0.5, "rgba(59,130,246,0.5)"],
                        [1.0, BLUE],
                    ],
                    showscale=False,
                    xgap=2, ygap=2,
                    text=[[f"{v:.1f}%" if v > 0 else "" for v in row] for row in z_data],
                    texttemplate="%{text}",
                    textfont=dict(size=10, color="white"),
                ))
                fig_overlap.update_layout(**chart_layout(
                    title=f"Shared Holdings Across {len(etf_list)} ETFs",
                    height=max(300, len(stock_names) * 28 + 80),
                    xaxis=dict(side="top", tickangle=0),
                    yaxis=dict(autorange="reversed"),
                    margin=dict(l=60, r=20, t=60, b=20),
                ))
                st.plotly_chart(fig_overlap, use_container_width=True)

                # Overlap summary
                st.markdown(
                    f'<div style="color:#94a3b8;font-size:0.82rem;margin-top:0.5rem">'
                    f'<b>{len(overlap_stocks)}</b> stocks appear in 2+ ETFs · '
                    f'<b>{len(unique_stocks)}</b> unique to a single ETF · '
                    f'<b>{len(all_stocks)}</b> total distinct positions across {len(etf_list)} ETFs</div>',
                    unsafe_allow_html=True,
                )

                # Pairwise overlap counts
                with st.expander("Pairwise ETF Overlap", expanded=False):
                    pairs = []
                    for i, e1 in enumerate(etf_list):
                        s1 = set(etf_data[e1]["holdings"])
                        for e2 in etf_list[i + 1:]:
                            s2 = set(etf_data[e2]["holdings"])
                            shared = s1 & s2
                            if shared:
                                pairs.append({
                                    "ETF Pair": f"{e1} / {e2}",
                                    "Shared": len(shared),
                                    "Stocks": ", ".join(sorted(shared)[:8]) + ("..." if len(shared) > 8 else ""),
                                })
                    if pairs:
                        st.dataframe(pd.DataFrame(pairs), use_container_width=True, hide_index=True)
            else:
                st.info("No overlapping holdings found between your ETFs.")
        elif etf_data:
            st.info("Need at least 2 ETFs with holdings data for overlap analysis.")
        else:
            st.info("Could not fetch holdings data for your ETFs.")

    # ── HYSA / Emergency Fund Card ──────────────────────────────────────────
    st.divider()
    st.subheader("HYSA / Emergency Fund + Sinking Fund")

    monthly_pi    = calc_monthly_payment(
        a["loan_original_amount"], a["loan_interest_rate"], a["loan_term_years"])
    monthly_tax   = a["home_current_value"] * a["property_tax_rate"] / 100 / 12
    monthly_ins   = a["home_insurance_annual"] / 12
    monthly_maint = a["home_current_value"] * a.get("maintenance_pct", 1.0) / 100 / 12
    total_housing = monthly_pi + monthly_tax + monthly_ins + a.get("hoa_monthly", 0) + monthly_maint
    total_variable= sum(v for v in a.get("budget", {}).values())
    total_debts   = sum(d["monthly_payment"] for d in a.get("other_debts", []))
    monthly_exp   = total_housing + total_variable + total_debts

    months_covered = hysa_balance / monthly_exp if monthly_exp > 0 else 0
    target_balance = monthly_exp * hysa_target_mo
    pct_of_target  = min(hysa_balance / target_balance * 100, 100) if target_balance > 0 else 0
    gap            = max(0, target_balance - hysa_balance)
    hysa_color     = "#f43f5e"
    bar_col        = GREEN if pct_of_target >= 100 else (AMBER if pct_of_target >= 80 else RED)

    with st.container(border=True):
        hc1, hc2, hc3, hc4 = st.columns([3, 2, 2, 2])
        hc1.markdown(
            f'<div style="padding-top:6px">'
            f'<span style="font-size:1.05rem;font-weight:700;color:#f1f5f9">HYSA</span>&nbsp;'
            f'<span style="background:{hysa_color}33;color:{hysa_color};padding:2px 8px;'
            f'border-radius:9999px;font-size:0.68rem;font-weight:700;letter-spacing:.4px">'
            f'Emergency Fund</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        hc2.metric("Balance",  f"${hysa_balance:,.0f}")
        hc3.metric("Coverage", f"{months_covered:.1f} mo",
                   delta=f"Target: {hysa_target_mo} mo", delta_color="off")
        hc4.metric("Target",   f"${target_balance:,.0f}",
                   delta=f"${gap:,.0f} to go" if gap > 0 else "Fully funded",
                   delta_color="inverse" if gap > 0 else "off")

        st.markdown(
            f'<div style="margin-top:10px;background:#0f172a;border-radius:6px;'
            f'height:8px;overflow:hidden">'
            f'<div style="background:{bar_col};width:{pct_of_target:.1f}%;height:8px;'
            f'border-radius:6px"></div></div>'
            f'<div style="display:flex;justify-content:space-between;'
            f'color:#94a3b8;font-size:0.75rem;margin-top:4px">'
            f'<span>${hysa_balance:,.0f} of ${target_balance:,.0f} target</span>'
            f'<span style="color:{"#22c55e" if gap == 0 else "#cbd5e1"}">'
            f'{"Fully funded" if gap == 0 else f"${gap:,.0f} to fund {hysa_target_mo}mo target"}'
            f'</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Sector Allocation ───────────────────────────────────────────────────
    st.divider()
    st.subheader("Sector Allocation")

    all_holdings = []
    for acct in accounts:
        for h in acct.get("holdings", []):
            if h.get("ticker") and h.get("shares", 0) > 0:
                price = live_prices.get(h["ticker"]) or 0
                all_holdings.append({
                    "ticker":  h["ticker"],
                    "shares":  h["shares"],
                    "sector":  h.get("sector", "Unknown"),
                    "account": acct["label"],
                    "price":   price,
                    "value":   h["shares"] * price,
                })

    if not all_holdings:
        st.markdown(
            '<div style="background:#0f172a;border:1px dashed #334155;border-radius:10px;'
            'padding:32px;text-align:center;color:#64748b">'
            '<div style="font-size:2rem;margin-bottom:8px">No holdings added yet</div>'
            '<div style="font-size:0.85rem">Add tickers in Setup</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        hold_df   = pd.DataFrame(all_holdings)
        total_val = hold_df["value"].sum()

        if total_val == 0:
            st.warning("Prices unavailable. Try again later.")
        else:
            sector_df = (
                hold_df.groupby("sector")["value"]
                .sum().reset_index()
                .rename(columns={"value": "Value ($)"})
            )
            sector_df["Weight (%)"] = sector_df["Value ($)"] / total_val * 100
            sector_df = sector_df.sort_values("Value ($)", ascending=False)

            left, right = st.columns([1, 1])

            with left:
                ticker_df = hold_df.groupby(["sector", "ticker"])["value"].sum().reset_index()
                ticker_df = ticker_df[ticker_df["value"] > 0]
                fig_st = px.treemap(
                    ticker_df, path=["sector", "ticker"], values="value",
                    color="value",
                    color_continuous_scale=[[0, "#1e293b"], [0.5, PURPLE], [1, BLUE]],
                    title="Holdings by Sector",
                )
                fig_st.update_traces(
                    texttemplate="<b>%{label}</b><br>%{percentParent:.1%}",
                    textfont=dict(color="white"),
                    marker=dict(line=dict(color="#020817", width=2)),
                )
                fig_st.update_layout(**chart_layout(height=400, coloraxis_showscale=False))
                st.plotly_chart(fig_st, use_container_width=True)

                for _, row in sector_df.iterrows():
                    if row["Weight (%)"] > 30:
                        st.warning(
                            f"Heavy concentration in **{row['sector']}** "
                            f"({row['Weight (%)']:.1f}%) — consider diversifying"
                        )

            with right:
                all_sectors = list(SP500_WEIGHTS.keys()) + [
                    s for s in sector_df["sector"].tolist()
                    if s not in SP500_WEIGHTS
                ]
                all_sectors = list(dict.fromkeys(all_sectors))

                compare_rows = []
                for s in all_sectors:
                    your_w = sector_df.loc[sector_df["sector"] == s, "Weight (%)"].values
                    compare_rows.append({
                        "Sector":  s,
                        "Yours":   float(your_w[0]) if len(your_w) else 0.0,
                        "S&P 500": float(SP500_WEIGHTS.get(s, 0)),
                    })
                cmp_df = pd.DataFrame(compare_rows)
                cmp_df = cmp_df[cmp_df[["Yours", "S&P 500"]].sum(axis=1) > 0]
                cmp_df = cmp_df.sort_values("Yours", ascending=True)

                fig_cmp = go.Figure()
                fig_cmp.add_trace(go.Bar(
                    y=cmp_df["Sector"], x=cmp_df["Yours"],
                    name="Your Portfolio", orientation="h",
                    marker=dict(color=BLUE, opacity=0.9, line=dict(width=0)),
                ))
                fig_cmp.add_trace(go.Bar(
                    y=cmp_df["Sector"], x=cmp_df["S&P 500"],
                    name="S&P 500", orientation="h",
                    marker=dict(color="#334155", opacity=0.7, line=dict(width=0)),
                ))
                fig_cmp.update_layout(**chart_layout(
                    height=400, barmode="group",
                    title="Your Allocation vs S&P 500 (%)",
                    xaxis_ticksuffix="%",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                ))
                st.plotly_chart(fig_cmp, use_container_width=True)

            # ── Full Holdings Table with Gains ──────────────────────────────
            st.subheader("All Holdings")
            gain_rows = []
            for acct in accounts:
                for h in acct.get("holdings", []):
                    tk = h.get("ticker")
                    if not tk:
                        continue
                    price = live_prices.get(tk) or 0
                    mkt = h["shares"] * price
                    cost = h["shares"] * h["avg_cost"] if h.get("avg_cost") is not None else None
                    gl = (mkt - cost) if cost is not None else None
                    gl_pct = (gl / cost * 100) if cost and cost > 0 else None
                    gain_rows.append({
                        "Account": acct["label"],
                        "Ticker": tk,
                        "Shares": h["shares"],
                        "Price": price,
                        "Avg Cost": h.get("avg_cost"),
                        "Mkt Value": mkt,
                        "Cost Basis": cost,
                        "Gain ($)": gl,
                        "Gain (%)": gl_pct,
                    })

            if gain_rows:
                g_df = pd.DataFrame(gain_rows)
                fmt = {
                    "Shares": "{:.4f}",
                    "Price": "${:.2f}",
                    "Avg Cost": "${:.2f}",
                    "Mkt Value": "${:,.2f}",
                    "Cost Basis": "${:,.2f}",
                    "Gain ($)": "${:+,.2f}",
                    "Gain (%)": "{:+.1f}%",
                }

                def _color_gain(val):
                    if pd.isna(val) or val is None:
                        return ""
                    if isinstance(val, str):
                        return ""
                    return f"color: {GREEN}" if val >= 0 else f"color: {RED}"

                styled = (
                    g_df.style
                    .format(fmt, na_rep="--")
                    .map(_color_gain, subset=["Gain ($)", "Gain (%)"])
                )
                st.dataframe(styled, use_container_width=True, hide_index=True)

    # ── Tax-Loss Harvesting Alerts ──────────────────────────────────────────
    st.divider()
    st.subheader("Tax-Loss Harvesting Opportunities")

    tlh_hits = []
    for acct in accounts:
        if acct.get("account_type") != "Brokerage":
            continue
        for h in acct.get("holdings", []):
            tk = h.get("ticker")
            if not tk or h.get("avg_cost") is None:
                continue
            price = live_prices.get(tk)
            if not price:
                continue
            mkt  = h["shares"] * price
            cost = h["shares"] * h["avg_cost"]
            loss = mkt - cost
            if loss < -100:
                loss_pct = loss / cost * 100
                tlh_hits.append((acct["label"], tk, loss, loss_pct))

    if tlh_hits:
        for label, tk, loss, loss_pct in sorted(tlh_hits, key=lambda x: x[2]):
            st.warning(
                f"**{tk}** in *{label}* — unrealized loss "
                f"**${loss:,.0f}** ({loss_pct:.1f}%) — potential harvest candidate"
            )
    else:
        st.success("No taxable losses > $100 detected in Brokerage accounts.")

    # ── Rebalancing Advisor ─────────────────────────────────────────────────
    st.divider()
    st.subheader("Rebalancing Advisor")

    target_alloc = a.get("target_allocation", {})
    if not target_alloc:
        st.info("Set target allocations in Setup (target_allocation) to enable rebalancing advice.")
    elif not all_holdings:
        st.info("Add holdings with sector data to see rebalancing suggestions.")
    else:
        hold_df_rb = pd.DataFrame(all_holdings)
        total_val_rb = hold_df_rb["value"].sum()
        current_weights = (
            hold_df_rb.groupby("sector")["value"].sum() / total_val_rb * 100
        ).to_dict() if total_val_rb > 0 else {}

        all_sectors_rb = sorted(set(list(target_alloc.keys()) + list(current_weights.keys())))
        rb_rows = []
        for sec in all_sectors_rb:
            cur  = current_weights.get(sec, 0.0)
            tgt  = float(target_alloc.get(sec, 0.0))
            diff = cur - tgt
            rb_rows.append({"Sector": sec, "Current %": cur, "Target %": tgt, "Diff %": diff})

        rb_df = pd.DataFrame(rb_rows)

        def _color_diff(val):
            if pd.isna(val):
                return ""
            abs_v = abs(val)
            if abs_v <= 3:
                return f"color: {GREEN}"
            elif abs_v <= 5:
                return f"color: {AMBER}"
            return f"color: {RED}"

        styled_rb = (
            rb_df.style
            .format({"Current %": "{:.1f}%", "Target %": "{:.1f}%", "Diff %": "{:+.1f}%"})
            .map(_color_diff, subset=["Diff %"])
        )
        st.dataframe(styled_rb, use_container_width=True, hide_index=True)

        suggestions = [(r["Sector"], r["Diff %"]) for _, r in rb_df.iterrows() if abs(r["Diff %"]) > 3]
        if suggestions:
            st.caption("Suggested actions:")
            for sec, diff in sorted(suggestions, key=lambda x: abs(x[1]), reverse=True):
                if diff < 0:
                    st.markdown(f"- Consider **adding to {sec}** (underweight by {abs(diff):.1f}%)")
                else:
                    st.markdown(f"- Consider **trimming {sec}** (overweight by {abs(diff):.1f}%)")
        else:
            st.success("Portfolio is within 3% of all targets — no trades needed.")

    # ── Transaction Log ─────────────────────────────────────────────────────
    st.divider()
    st.subheader("Transaction Log")

    acct_labels = [acct["label"] for acct in accounts]
    with st.form("txn_form", clear_on_submit=True):
        fc1, fc2, fc3 = st.columns([2, 2, 2])
        txn_date   = fc1.date_input("Date", value=date.today())
        txn_acct   = fc2.selectbox("Account", acct_labels)
        txn_ticker = fc3.text_input("Ticker").upper().strip()
        fc4, fc5, fc6, fc7 = st.columns([1, 2, 2, 3])
        txn_action = fc4.selectbox("Action", ["Buy", "Sell"])
        txn_shares = fc5.number_input("Shares", min_value=0.0, step=0.0001, format="%.4f")
        txn_price  = fc6.number_input("Price ($)", min_value=0.0, step=0.01, format="%.2f")
        txn_notes  = fc7.text_input("Notes (optional)")
        submitted  = st.form_submit_button("Add Transaction")

    if submitted and txn_ticker and txn_shares > 0 and txn_price > 0:
        add_transaction(txn_date, txn_acct, txn_ticker, txn_action,
                        txn_shares, txn_price, txn_notes)
        st.success(f"Logged: {txn_action} {txn_shares:.4f} {txn_ticker} @ ${txn_price:.2f}")
        st.rerun()

    txns = get_transactions()
    if txns:
        txn_df = pd.DataFrame(txns)
        txn_df = txn_df.rename(columns={
            "id": "ID", "date": "Date", "account": "Account", "ticker": "Ticker",
            "action": "Action", "shares": "Shares", "price": "Price ($)", "notes": "Notes",
        })
        st.caption(f"{len(txns)} transaction{'s' if len(txns) != 1 else ''} recorded")
        st.dataframe(txn_df.drop(columns=["ID"]), use_container_width=True, hide_index=True)
    else:
        st.caption("No transactions recorded yet.")

    # ── Live Stock / ETF Lookup ─────────────────────────────────────────────
    st.divider()
    st.subheader("Live Stock / ETF Lookup")
    sc1, sc2   = st.columns([2, 1])
    ticker_in  = sc1.text_input("Ticker symbol (e.g. AAPL, VTI, BTC-USD)", "").upper().strip()
    period     = sc2.selectbox("Period", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=3)

    if ticker_in:
        try:
            t    = yf.Ticker(ticker_in)
            hist = t.history(period=period)
            info = t.fast_info

            if hist.empty:
                st.error(f"No data found for '{ticker_in}'.")
            else:
                price = info.last_price
                prev  = info.previous_close
                chg   = ((price - prev) / prev * 100) if prev else 0

                lc1, lc2, lc3, lc4 = st.columns(4)
                lc1.metric("Current Price", f"${price:.2f}", delta=f"{chg:+.2f}% today")
                lc2.metric("52-Wk High",    f"${info.fifty_two_week_high:.2f}")
                lc3.metric("52-Wk Low",     f"${info.fifty_two_week_low:.2f}")
                lc4.metric("Market Cap",
                           f"${info.market_cap / 1e9:.1f}B"
                           if hasattr(info, "market_cap") and info.market_cap else "N/A")

                fig_c = go.Figure(go.Candlestick(
                    x=hist.index,
                    open=hist["Open"], high=hist["High"],
                    low=hist["Low"],   close=hist["Close"],
                    name=ticker_in,
                    increasing=dict(line=dict(color=GREEN), fillcolor=GREEN + "55"),
                    decreasing=dict(line=dict(color=RED),   fillcolor=RED   + "55"),
                ))
                fig_c.update_layout(**chart_layout(
                    title=f"{ticker_in} — Price Chart",
                    xaxis_rangeslider_visible=False,
                    height=400, yaxis_tickprefix="$",
                ))
                st.plotly_chart(fig_c, use_container_width=True)
        except Exception:
            st.error(f"Could not load data for '{ticker_in}'. Check the symbol.")

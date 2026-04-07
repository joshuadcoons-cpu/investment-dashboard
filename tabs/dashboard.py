import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import date
from utils.calculations import (
    calc_monthly_payment, build_amortization, get_loan_status,
)
from utils.styles import BLUE, GREEN, RED, PURPLE, AMBER, CYAN, CHART_COLORS, chart_layout, theme_colors


def render():
    a = st.session_state.assumptions
    tc = theme_colors()

    # ── Shared calculations ───────────────────────────────────────────────────
    amort  = build_amortization(
        a["loan_original_amount"], a["loan_interest_rate"],
        a["loan_term_years"], a["loan_start_date"],
    )
    today  = date.today()
    status = get_loan_status(amort, today)

    home_equity       = max(a["home_current_value"] - status["current_balance"], 0)

    # Use live prices for investment totals when available
    _lp = st.session_state.get("live_prices", {})
    def _live_mv(acct):
        has_priced = any(
            h.get("ticker") and _lp.get(h["ticker"])
            for h in acct.get("holdings", [])
        )
        if has_priced:
            mv = acct.get("cash_usd", 0)
            for h in acct.get("holdings", []):
                p = _lp.get(h.get("ticker"))
                if p:
                    mv += h["shares"] * p
            return mv
        return acct["balance"]

    total_investments = sum(_live_mv(acct) for acct in a["investment_accounts"])
    total_take_home   = a["take_home_monthly"] + a["spouse_take_home_monthly"]

    # Passive income (LP distributions + annual gift) — must be in the cash flow
    passive_monthly   = a.get("parkwood_lp_monthly", 0) + a.get("family_gift_annual", 0) / 12
    total_monthly_in  = total_take_home + passive_monthly

    monthly_pi   = calc_monthly_payment(
        a["loan_original_amount"], a["loan_interest_rate"], a["loan_term_years"])
    monthly_tax  = a["home_current_value"] * a["property_tax_rate"] / 100 / 12
    monthly_ins  = a["home_insurance_annual"] / 12
    monthly_hoa  = a["hoa_monthly"]
    monthly_mnt  = a["home_current_value"] * a["maintenance_pct"] / 100 / 12
    total_housing = monthly_pi + monthly_tax + monthly_ins + monthly_hoa + monthly_mnt
    total_debts   = sum(d["monthly_payment"] for d in a["other_debts"])
    total_var     = sum(a["budget"].values())
    total_inv_contrib = sum(acct["monthly_contribution"] for acct in a["investment_accounts"])
    net_cash_flow = total_monthly_in - total_housing - total_debts - total_var - total_inv_contrib
    savings_rate  = (
        (total_inv_contrib + max(net_cash_flow, 0)) / total_monthly_in * 100
        if total_monthly_in else 0
    )

    total_liabilities = (status["current_balance"]
                         + sum(d["balance"] for d in a["other_debts"]))
    sinking_fund      = a.get("sinking_fund_balance", 0)
    total_assets      = (a["home_current_value"] + total_investments
                         + a["emergency_fund_balance"] + sinking_fund
                         + a["checking_savings_balance"])
    net_worth         = total_assets - total_liabilities

    total_exp = total_housing + total_debts + total_var
    # Emergency fund coverage uses EF balance only (dedicated bucket)
    liquid_savings = a["emergency_fund_balance"] + sinking_fund + a["checking_savings_balance"]
    ef_months = liquid_savings / total_exp if total_exp else 0

    # Retirement readiness (mortgage paid off before retirement → use post-payoff costs)
    post_payoff_exp = total_exp - monthly_pi
    years_to_ret = a["retirement_age"] - a["age"]
    readiness_pct = 0
    if years_to_ret > 0:
        r   = a["investment_return_pct"] / 100 / 12
        bal = float(total_investments)
        for _ in range(years_to_ret * 12):
            bal = bal * (1 + r) + total_inv_contrib
        ret_portfolio = bal
        safe_monthly  = ret_portfolio * 0.04 / 12
        ss = (a["social_security_monthly"]
              if (a["age"] + years_to_ret) >= a["social_security_start_age"] else 0)
        lp_doubled_net = a.get("parkwood_lp_monthly", 0) * a.get("lp_net_pct", 100) / 100 * 2
        ret_income    = safe_monthly + ss + lp_doubled_net
        inflated_exp  = post_payoff_exp * (1 + a["inflation_pct"] / 100) ** years_to_ret
        readiness_pct = (ret_income / inflated_exp * 100) if inflated_exp else 0

    # ── Section header ────────────────────────────────────────────────────────
    st.markdown(
        f'<p class="section-header">Financial Snapshot — {today.strftime("%B %d, %Y")}</p>',
        unsafe_allow_html=True,
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # ROW 1 — KPI Cards
    # ═══════════════════════════════════════════════════════════════════════════
    k1, k2, k3, k4, k5, k6 = st.columns(6)

    def _fmt_large(v):
        """Format large dollar values compactly: $1.02M, $697k, etc."""
        av = abs(v)
        sign = "-" if v < 0 else ""
        if av >= 1_000_000:
            return f"{sign}${av/1_000_000:.2f}M"
        if av >= 1_000:
            return f"{sign}${av/1_000:.0f}k"
        return f"{sign}${av:,.0f}"

    with k1:
        st.markdown(f"""
        <div class="kpi-card" style="border-top: 3px solid {PURPLE}">
            <div class="kpi-label">Net Worth</div>
            <div class="kpi-value">{_fmt_large(net_worth)}</div>
            <div class="kpi-sub">Assets − Liabilities</div>
        </div>""", unsafe_allow_html=True)

    with k2:
        st.markdown(f"""
        <div class="kpi-card" style="border-top: 3px solid {BLUE}">
            <div class="kpi-label">Portfolio Value</div>
            <div class="kpi-value">{_fmt_large(total_investments)}</div>
            <div class="kpi-sub">{len(a["investment_accounts"])} accounts</div>
        </div>""", unsafe_allow_html=True)

    with k3:
        ltv = status["current_balance"] / a["home_current_value"] * 100 if a["home_current_value"] else 0
        equity_pct = 100 - ltv
        st.markdown(f"""
        <div class="kpi-card" style="border-top: 3px solid {GREEN}">
            <div class="kpi-label">Home Equity</div>
            <div class="kpi-value">{_fmt_large(home_equity)}</div>
            <div class="kpi-sub">{equity_pct:.1f}% equity · LTV {ltv:.1f}%</div>
        </div>""", unsafe_allow_html=True)

    with k4:
        cf_color = GREEN if net_cash_flow >= 0 else RED
        cf_label = "Surplus" if net_cash_flow >= 0 else "Deficit"
        st.markdown(f"""
        <div class="kpi-card" style="border-top: 3px solid {cf_color}">
            <div class="kpi-label">Monthly Cash Flow</div>
            <div class="kpi-value" style="color:{cf_color}">${net_cash_flow:,.0f}</div>
            <div class="kpi-sub">{cf_label}</div>
        </div>""", unsafe_allow_html=True)

    with k5:
        sr_color = GREEN if savings_rate >= 15 else (AMBER if savings_rate >= 10 else RED)
        st.markdown(f"""
        <div class="kpi-card" style="border-top: 3px solid {sr_color}">
            <div class="kpi-label">Savings Rate</div>
            <div class="kpi-value" style="color:{sr_color}">{savings_rate:.1f}%</div>
            <div class="kpi-sub">of total monthly income</div>
        </div>""", unsafe_allow_html=True)

    with k6:
        ef_color = (GREEN if ef_months >= a["emergency_fund_target_months"]
                    else (AMBER if ef_months >= 3 else RED))
        st.markdown(f"""
        <div class="kpi-card" style="border-top: 3px solid {ef_color}">
            <div class="kpi-label">Emergency Fund</div>
            <div class="kpi-value" style="color:{ef_color}">{ef_months:.1f} mo</div>
            <div class="kpi-sub">goal: {a["emergency_fund_target_months"]} months</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # TODAY'S MOVE — daily gain/loss strip
    # ═══════════════════════════════════════════════════════════════════════════
    live_prices = st.session_state.get("live_prices", {})
    prev_prices = st.session_state.get("prev_prices", {})

    if live_prices and prev_prices:
        # Compute total daily gain and per-account daily gains
        daily_gain_total = 0.0
        per_acct_daily = []
        for acct in a["investment_accounts"]:
            acct_day = 0.0
            for h in acct.get("holdings", []):
                tk = h.get("ticker")
                if tk and live_prices.get(tk) and prev_prices.get(tk):
                    acct_day += (live_prices[tk] - prev_prices[tk]) * h["shares"]
            if acct_day != 0:
                per_acct_daily.append((acct["label"], acct_day))
            daily_gain_total += acct_day

        if daily_gain_total != 0:
            day_sign  = "+" if daily_gain_total >= 0 else ""
            day_color = GREEN if daily_gain_total >= 0 else RED
            day_pct   = (daily_gain_total / (total_investments - daily_gain_total) * 100
                         if (total_investments - daily_gain_total) != 0 else 0)
            day_arrow = "▲" if daily_gain_total >= 0 else "▼"

            st.markdown(
                f'<div style="background:#0f172a;border:1px solid rgba(255,255,255,0.07);'
                f'border-left:3px solid {day_color};border-radius:10px;'
                f'padding:0.65rem 1.2rem;margin-bottom:1rem;'
                f'display:flex;align-items:center;gap:1.5rem;flex-wrap:wrap">'
                f'<span style="color:#64748b;font-size:0.72rem;font-weight:700;'
                f'text-transform:uppercase;letter-spacing:.08em">Today\'s Move</span>'
                f'<span style="color:{day_color};font-size:1.25rem;font-weight:700">'
                f'{day_arrow} {day_sign}${abs(daily_gain_total):,.0f}'
                f'<span style="font-size:0.85rem;margin-left:6px">'
                f'({day_sign}{day_pct:.2f}%)</span></span>'
                + "".join(
                    f'<span style="color:#475569;font-size:0.8rem">·</span>'
                    f'<span style="color:{"#94a3b8"};font-size:0.8rem">'
                    f'{lbl}: <span style="color:{"#10b981" if v >= 0 else "#ef4444"};font-weight:600">'
                    f'{"+" if v >= 0 else ""}${v:,.0f}</span></span>'
                    for lbl, v in per_acct_daily
                )
                + f'</div>',
                unsafe_allow_html=True,
            )

    # ═══════════════════════════════════════════════════════════════════════════
    # ROW 2 — Charts
    # ═══════════════════════════════════════════════════════════════════════════
    c1, c2, c3 = st.columns([1.1, 0.9, 1.0])

    # ── Net Worth Diverging Bar ───────────────────────────────────────────────
    with c1:
        st.markdown('<p class="section-header">Net Worth Breakdown</p>', unsafe_allow_html=True)

        # Build items: assets (positive) and liabilities (negative)
        div_items = [
            ("Checking/Savings", a["checking_savings_balance"],  GREEN),
            ("HYSA",             a["emergency_fund_balance"],    GREEN),
            ("Home Value",       a["home_current_value"],        GREEN),
            ("Investments",      total_investments,              GREEN),
        ]
        if sinking_fund > 0:
            div_items.insert(1, ("Sinking Fund", sinking_fund, GREEN))
        if status["current_balance"] > 0:
            div_items.append(("Mortgage", -status["current_balance"], RED))
        for d in a["other_debts"]:
            if d["balance"] > 0:
                div_items.append((d["name"], -d["balance"], RED))

        # Sort ascending: negatives (liabilities) at top, positives (assets) at bottom
        div_items.sort(key=lambda x: x[1])
        div_labels = [d[0] for d in div_items]
        div_values = [d[1] for d in div_items]
        div_colors = [d[2] for d in div_items]

        def _fmt(v):
            av = abs(v)
            if av >= 1_000_000:
                return f"${av/1_000_000:.1f}M"
            if av >= 1_000:
                return f"${av/1_000:.0f}k"
            return f"${av:,.0f}"

        import math
        # Cube-root scale compresses large values aggressively so small
        # bars ($6k, $14k) are still clearly visible next to $1.7M.
        def _compress(v):
            return math.copysign(abs(v) ** (1/3), v)

        bar_x = [_compress(v) for v in div_values]
        bar_text = [_fmt(v) for v in div_values]

        # Place labels outside for assets, inside for liabilities (so they don't overlap y-axis)
        text_pos = ["outside" if v >= 0 else "inside" for v in div_values]

        fig_nw = go.Figure(go.Bar(
            y=div_labels,
            x=bar_x,
            orientation="h",
            marker=dict(color=div_colors, line=dict(width=0)),
            text=bar_text,
            textposition=text_pos,
            textfont=dict(size=10, color=tc["text"]),
            cliponaxis=False,
            hovertemplate="<b>%{y}</b><br>%{text}<extra></extra>",
        ))
        fig_nw.update_layout(**chart_layout(
            height=320,
            showlegend=False,
            margin=dict(l=80),
            xaxis=dict(
                showticklabels=False,
                zeroline=True,
                zerolinewidth=2,
                zerolinecolor=tc["zeroline"],
            ),
        ))
        st.plotly_chart(fig_nw, use_container_width=True)

    # ── All Assets Donut ────────────────────────────────────────────────────
    with c2:
        st.markdown('<p class="section-header">All Assets by Account</p>', unsafe_allow_html=True)

        alloc_labels = []
        alloc_values = []
        alloc_colors = []

        # Investment accounts — use live prices when available
        for acct in a["investment_accounts"]:
            mv = _live_mv(acct)
            if mv > 0:
                alloc_labels.append(acct["label"])
                alloc_values.append(mv)
        alloc_colors += list(CHART_COLORS[:len(alloc_labels) - len(alloc_colors)])

        # Cash / savings buckets
        _cash_buckets = [
            ("HYSA",           a["emergency_fund_balance"],     "#f43f5e"),
            ("Sinking Fund",   sinking_fund,                    "#f97316"),
            ("Checking / Savings", a["checking_savings_balance"], CYAN),
        ]
        for lbl, val, clr in _cash_buckets:
            if val > 0:
                alloc_labels.append(lbl)
                alloc_values.append(val)
                alloc_colors.append(clr)

        all_assets_total = sum(alloc_values)
        if alloc_values:
            fig_donut = go.Figure(go.Pie(
                labels=alloc_labels,
                values=alloc_values,
                hole=0.62,
                marker=dict(colors=alloc_colors, line=dict(color=tc["pie_border"], width=3)),
                textinfo="none",
                hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>",
            ))
            fig_donut.add_annotation(
                text=f"<b>${all_assets_total/1e3:.0f}k</b>",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=18, color=tc["bright"]),
            )
            fig_donut.update_layout(**chart_layout(
                height=380,
                showlegend=True,
                legend=dict(
                    orientation="h",
                    x=0.5, y=-0.15,
                    xanchor="center",
                    font=dict(size=10, color=tc["text"]),
                    itemwidth=30,
                ),
                margin=dict(t=10, b=80),
            ))
            st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.info("Add investment accounts in ⚙️ Setup.")

    # ── Budget Snapshot (annual) ─────────────────────────────────────────────
    with c3:
        st.markdown('<p class="section-header">Top Annual Budget Categories</p>', unsafe_allow_html=True)
        budget_items = {
            "Housing": total_housing * 12,
            **{k: v * 12 for k, v in sorted(a["budget"].items(), key=lambda x: -x[1])[:6] if v > 0},
            "Investments": total_inv_contrib * 12,
        }
        b_df = pd.DataFrame(list(budget_items.items()), columns=["Category", "Amount"])
        b_df = b_df[b_df["Amount"] > 0].sort_values("Amount")
        bar_colors = [BLUE if cat == "Housing" else
                      GREEN if cat == "Investments" else
                      tc["subtle"] for cat in b_df["Category"]]
        b_labels = [f"${v:,.0f}" for v in b_df["Amount"]]
        fig_b = go.Figure(go.Bar(
            y=b_df["Category"], x=b_df["Amount"],
            orientation="h",
            marker=dict(color=bar_colors, line=dict(width=0)),
            text=b_labels,
            textposition="outside",
            textfont=dict(size=11, color=tc["secondary"]),
            cliponaxis=False,
        ))
        fig_b.update_layout(**chart_layout(
            height=320,
            showlegend=False,
            xaxis=dict(tickprefix="$", tickformat=",.0f"),
        ))
        st.plotly_chart(fig_b, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # ROW 3 — Cash Flow Waterfall + Sector Allocation
    # ═══════════════════════════════════════════════════════════════════════════
    g1, g2 = st.columns([1, 1])

    # ── Cash Flow Waterfall ──────────────────────────────────────────────────
    with g1:
        st.markdown('<p class="section-header">Monthly Cash Flow Waterfall</p>', unsafe_allow_html=True)

        wf_labels  = ["Income", "Housing", "Debts", "Variable\nSpending",
                       "Investments", "Surplus"]
        wf_values  = [total_monthly_in, -total_housing, -total_debts,
                      -total_var, -total_inv_contrib, net_cash_flow]
        wf_measure = ["absolute", "relative", "relative",
                      "relative", "relative", "total"]
        wf_text    = [f"${abs(v):,.0f}" for v in wf_values]
        wf_colors  = [GREEN, RED, RED, RED, AMBER, GREEN if net_cash_flow >= 0 else RED]

        fig_wf = go.Figure(go.Waterfall(
            x=wf_labels, y=wf_values,
            measure=wf_measure,
            text=wf_text,
            textposition="outside",
            textfont=dict(size=10, color=tc["secondary"]),
            connector=dict(line=dict(color=tc["connector"], width=1)),
            increasing=dict(marker=dict(color=GREEN)),
            decreasing=dict(marker=dict(color=RED)),
            totals=dict(marker=dict(color=GREEN if net_cash_flow >= 0 else RED)),
            cliponaxis=False,
        ))
        fig_wf.update_layout(**chart_layout(
            height=340,
            showlegend=False,
            yaxis=dict(tickprefix="$", tickformat=",.0f"),
            margin=dict(t=20, b=40),
        ))
        st.plotly_chart(fig_wf, use_container_width=True)

    # ── Sector Allocation vs Target ──────────────────────────────────────────
    with g2:
        st.markdown('<p class="section-header">Sector Allocation vs Target</p>', unsafe_allow_html=True)

        # Map tickers to sectors
        _TICKER_SECTOR = {
            "VOO": "US Equity", "VTI": "US Equity", "SCHB": "US Equity",
            "QQQM": "Technology", "QQQ": "Technology", "VGT": "Technology",
            "SMH": "Technology", "AAPL": "Technology",
            "VFH": "Financials", "XLF": "Financials",
            "VHT": "Healthcare", "XLV": "Healthcare",
            "VXUS": "International", "IXUS": "International",
            "VWO": "Emerging Markets", "IEMG": "Emerging Markets",
            "IAU": "Commodities", "GLD": "Commodities", "PDBC": "Commodities",
            "IBIT": "Crypto", "ETHA": "Crypto",
            "BTC": "Crypto", "ETH": "Crypto", "ADA": "Crypto",
            "XRP": "Crypto", "DOGE": "Crypto",
            "VUG": "US Equity", "SCHG": "US Equity",
        }

        live_prices = st.session_state.get("live_prices", {})
        sector_values = {}
        for acct in a["investment_accounts"]:
            for h in acct.get("holdings", []):
                tk = h.get("ticker")
                if not tk:
                    continue
                price = live_prices.get(tk)
                if not price:
                    continue
                sector = _TICKER_SECTOR.get(tk, h.get("sector", "Other"))
                if sector == "Unknown":
                    sector = "Other"
                sector_values[sector] = sector_values.get(sector, 0) + h["shares"] * price

        target = a.get("target_allocation") or {
            "US Equity": 35, "Technology": 15, "International": 10,
            "Emerging Markets": 5, "Commodities": 10, "Crypto": 10,
            "Financials": 5, "Healthcare": 5, "Other": 5,
        }

        total_portfolio = sum(sector_values.values()) or 1
        all_sectors = sorted(set(list(target.keys()) + list(sector_values.keys())))

        current_pcts = [sector_values.get(s, 0) / total_portfolio * 100 for s in all_sectors]
        target_pcts  = [target.get(s, 0) for s in all_sectors]

        fig_alloc = go.Figure()
        fig_alloc.add_trace(go.Bar(
            y=all_sectors, x=current_pcts, orientation="h",
            name="Current", marker=dict(color=BLUE),
            text=[f"{v:.1f}%" for v in current_pcts],
            textposition="outside", textfont=dict(size=9, color=tc["muted"]),
            cliponaxis=False,
        ))
        fig_alloc.add_trace(go.Bar(
            y=all_sectors, x=target_pcts, orientation="h",
            name="Target", marker=dict(color=tc["target_bar"]),
            text=[f"{v:.0f}%" for v in target_pcts],
            textposition="outside", textfont=dict(size=9, color=tc["faint"]),
            cliponaxis=False,
        ))
        fig_alloc.update_layout(**chart_layout(
            height=340,
            barmode="group",
            showlegend=False,
            xaxis=dict(ticksuffix="%"),
            margin=dict(t=10, b=20),
        ))
        st.plotly_chart(fig_alloc, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # ROW 4 — Debt Payoff Timeline + Investment Return Attribution
    # ═══════════════════════════════════════════════════════════════════════════
    d1, d2 = st.columns([1, 1])

    # ── Debt Payoff Timeline ─────────────────────────────────────────────────
    with d1:
        st.markdown('<p class="section-header">Debt Payoff Timeline</p>', unsafe_allow_html=True)

        # Mortgage
        orig_mortgage = a["loan_original_amount"]
        mortgage_paid = orig_mortgage - status["current_balance"]
        mortgage_pct  = (mortgage_paid / orig_mortgage * 100) if orig_mortgage else 0
        payoff_date   = status["payoff_date"]
        years_left_m  = status["months_remaining"] / 12

        st.markdown(
            f'<div style="margin-bottom:1.2rem">'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px">'
            f'<span style="color:#e2e8f0;font-size:0.9rem;font-weight:700">Mortgage</span>'
            f'<span style="color:#64748b;font-size:0.78rem">'
            f'{years_left_m:.1f} yrs to go · payoff {payoff_date.strftime("%b %Y")}</span>'
            f'</div>'
            f'<div style="background:#0f172a;border-radius:6px;height:16px;overflow:hidden;position:relative">'
            f'<div style="width:{max(mortgage_pct, 0.5):.2f}%;height:100%;'
            f'background:linear-gradient(90deg,{GREEN},{CYAN});border-radius:6px"></div></div>'
            f'<div style="display:flex;justify-content:space-between;margin-top:5px">'
            f'<span style="color:{GREEN};font-size:0.78rem;font-weight:700">'
            f'Paid: ${mortgage_paid:,.0f} ({mortgage_pct:.2f}%)</span>'
            f'<span style="color:#94a3b8;font-size:0.78rem">'
            f'Remaining: ${status["current_balance"]:,.0f}</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

        # Other debts
        for d in a["other_debts"]:
            if d["balance"] <= 0:
                continue
            # Estimate original balance from payment schedule
            # Simple: assume original = balance + total paid so far (rough)
            rate_mo = d["rate_pct"] / 100 / 12
            if rate_mo > 0 and d["monthly_payment"] > 0:
                # Months to payoff
                if d["monthly_payment"] <= d["balance"] * rate_mo:
                    months_left = 999
                else:
                    import math as _math
                    months_left = _math.ceil(
                        -_math.log(1 - d["balance"] * rate_mo / d["monthly_payment"])
                        / _math.log(1 + rate_mo)
                    )
                years_left_d = months_left / 12
                from dateutil.relativedelta import relativedelta
                payoff_d = today + relativedelta(months=months_left)
            else:
                months_left = (d["balance"] / d["monthly_payment"]) if d["monthly_payment"] else 999
                years_left_d = months_left / 12
                payoff_d = today

            # Visual: we don't know original so show remaining timeline
            bar_pct = min(100, max(5, 100 - (months_left / (months_left + 12)) * 100))

            st.markdown(
                f'<div style="margin-bottom:1.2rem">'
                f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px">'
                f'<span style="color:#e2e8f0;font-size:0.9rem;font-weight:700">{d["name"]}</span>'
                f'<span style="color:#64748b;font-size:0.78rem">'
                f'${d["balance"]:,.0f} at {d["rate_pct"]}% · {years_left_d:.1f} yrs left</span>'
                f'</div>'
                f'<div style="background:#0f172a;border-radius:6px;height:16px;overflow:hidden">'
                f'<div style="width:{100 - months_left / max(months_left + 60, 1) * 100:.0f}%;height:100%;'
                f'background:linear-gradient(90deg,{AMBER},{GREEN});border-radius:6px;'
                f'display:flex;align-items:center;justify-content:center;'
                f'font-size:0.68rem;color:white;font-weight:700">'
                f'${d["monthly_payment"]:,.0f}/mo</div></div>'
                f'<div style="display:flex;justify-content:space-between;color:#475569;'
                f'font-size:0.72rem;margin-top:4px">'
                f'<span>${d["monthly_payment"]:,.0f}/mo payment</span>'
                f'<span>Payoff: ~{payoff_d.strftime("%b %Y")}</span>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

        if not a["other_debts"]:
            st.markdown(
                f'<div style="color:{GREEN};font-size:0.85rem;margin-top:0.5rem">'
                f'No other debts — only the mortgage remains.</div>',
                unsafe_allow_html=True,
            )

    # ── Investment Return Attribution ────────────────────────────────────────
    with d2:
        st.markdown('<p class="section-header">Investment Return Attribution</p>', unsafe_allow_html=True)

        total_cost_basis = 0
        for acct in a["investment_accounts"]:
            cash = acct.get("cash_usd", 0)
            total_cost_basis += cash
            for h in acct.get("holdings", []):
                if h.get("avg_cost") is not None:
                    total_cost_basis += h["shares"] * h["avg_cost"]

        market_gains = total_investments - total_cost_basis

        cb_pct = (total_cost_basis / total_investments * 100) if total_investments else 0
        mg_pct = (market_gains / total_investments * 100) if total_investments else 0
        gain_on_cost = (market_gains / total_cost_basis * 100) if total_cost_basis else 0

        # Stacked horizontal bar
        fig_attr = go.Figure()
        fig_attr.add_trace(go.Bar(
            y=["Portfolio"],
            x=[total_cost_basis],
            orientation="h",
            name="Your Contributions",
            marker=dict(color=BLUE),
            text=[f"${total_cost_basis:,.0f}"],
            textposition="inside",
            textfont=dict(size=12, color="white"),
            hovertemplate="Contributions: $%{x:,.0f}<extra></extra>",
        ))
        fig_attr.add_trace(go.Bar(
            y=["Portfolio"],
            x=[market_gains],
            orientation="h",
            name="Market Gains" if market_gains >= 0 else "Market Losses",
            marker=dict(color=GREEN if market_gains >= 0 else RED),
            text=[f"${market_gains:+,.0f}"],
            textposition="inside",
            textfont=dict(size=12, color="white"),
            hovertemplate="Market gains: $%{x:+,.0f}<extra></extra>",
        ))
        fig_attr.update_layout(**chart_layout(
            height=120,
            barmode="stack",
            showlegend=False,
            xaxis=dict(tickprefix="$", tickformat=",.0s"),
            yaxis=dict(visible=False),
            margin=dict(t=10, b=10, l=10, r=10),
        ))
        st.plotly_chart(fig_attr, use_container_width=True)

        # Attribution stats
        a1, a2, a3 = st.columns(3)
        a1.metric("Contributions", f"${total_cost_basis:,.0f}",
                  delta=f"{cb_pct:.0f}% of portfolio", delta_color="off")
        a2.metric("Market Gains", f"${market_gains:+,.0f}",
                  delta=f"{mg_pct:.0f}% of portfolio",
                  delta_color="normal" if market_gains >= 0 else "inverse")
        a3.metric("Return on Cost", f"{gain_on_cost:+.1f}%",
                  delta="since inception", delta_color="off")

    # ═══════════════════════════════════════════════════════════════════════════
    # MILESTONE TRACKER
    # ═══════════════════════════════════════════════════════════════════════════
    milestones = a.get("milestones", [])
    if milestones:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("Milestone Tracker", expanded=True):
            current_age = a["age"]
            for ms in sorted(milestones, key=lambda m: m.get("age", 0)):
                ms_age    = ms.get("age", 0)
                ms_target = ms.get("target_nw", 0)
                ms_event  = ms.get("event", "")
                pct       = min(net_worth / ms_target * 100, 100) if ms_target else 0
                completed = net_worth >= ms_target
                future    = ms_age > current_age and not completed
                bar_color = GREEN if completed else (BLUE if not future else tc["subtle"])
                label     = f"Age {ms_age} — ${ms_target/1e6:.2f}M" if ms_target >= 1e6 else f"Age {ms_age} — ${ms_target:,.0f}"
                sub       = f'<span style="color:#64748b;font-size:0.72rem"> · {ms_event}</span>' if ms_event else ""
                st.markdown(
                    f'<div style="margin-bottom:0.9rem">'
                    f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px">'
                    f'<span style="color:#e2e8f0;font-size:0.82rem;font-weight:600">{label}</span>{sub}'
                    f'<span style="color:#64748b;font-size:0.75rem">{pct:.0f}% · {_fmt_large(net_worth)} of {_fmt_large(ms_target)}</span>'
                    f'</div>'
                    f'<div style="background:#0f172a;border-radius:4px;height:8px;width:100%;overflow:hidden">'
                    f'<div style="width:{pct:.1f}%;height:100%;background:{bar_color};border-radius:4px;transition:width 0.3s"></div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

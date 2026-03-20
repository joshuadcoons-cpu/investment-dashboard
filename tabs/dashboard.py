import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import date
from utils.calculations import (
    calc_monthly_payment, build_amortization, get_loan_status,
)
from utils.styles import BLUE, GREEN, RED, PURPLE, AMBER, CYAN, CHART_COLORS, chart_layout


def render():
    a = st.session_state.assumptions

    # ── Shared calculations ───────────────────────────────────────────────────
    amort  = build_amortization(
        a["loan_original_amount"], a["loan_interest_rate"],
        a["loan_term_years"], a["loan_start_date"],
    )
    today  = date.today()
    status = get_loan_status(amort, today)

    home_equity       = max(a["home_current_value"] - status["current_balance"], 0)
    total_investments = sum(acct["balance"] for acct in a["investment_accounts"])
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

        max_abs = max(abs(v) for v in div_values) if div_values else 1
        bar_text = [_fmt(v) if abs(v) >= max_abs * 0.20 else "" for v in div_values]

        fig_nw = go.Figure(go.Bar(
            y=div_labels,
            x=div_values,
            orientation="h",
            marker=dict(color=div_colors, line=dict(width=0)),
            text=bar_text,
            textposition="inside",
            textfont=dict(size=10, color="white"),
            cliponaxis=False,
        ))
        fig_nw.update_layout(**chart_layout(
            height=320,
            showlegend=False,
            margin=dict(l=80),
            xaxis=dict(
                tickprefix="$",
                tickformat=",.0s",
                zeroline=True,
                zerolinewidth=2,
                zerolinecolor="rgba(255,255,255,0.3)",
            ),
        ))
        st.plotly_chart(fig_nw, use_container_width=True)

    # ── All Assets Donut ────────────────────────────────────────────────────
    with c2:
        st.markdown('<p class="section-header">All Assets by Account</p>', unsafe_allow_html=True)

        # Investment accounts
        alloc_labels = [acct["label"] for acct in a["investment_accounts"] if acct["balance"] > 0]
        alloc_values = [acct["balance"] for acct in a["investment_accounts"] if acct["balance"] > 0]
        alloc_colors = list(CHART_COLORS[:len(alloc_labels)])

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
                marker=dict(colors=alloc_colors, line=dict(color="#020817", width=3)),
                textinfo="none",
                hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>",
            ))
            fig_donut.add_annotation(
                text=f"<b>${all_assets_total/1e3:.0f}k</b>",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=18, color="#f1f5f9"),
            )
            fig_donut.update_layout(**chart_layout(
                height=380,
                showlegend=True,
                legend=dict(
                    orientation="h",
                    x=0.5, y=-0.15,
                    xanchor="center",
                    font=dict(size=10, color="#e2e8f0"),
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
                      "#475569" for cat in b_df["Category"]]
        b_labels = [f"${v:,.0f}" for v in b_df["Amount"]]
        fig_b = go.Figure(go.Bar(
            y=b_df["Category"], x=b_df["Amount"],
            orientation="h",
            marker=dict(color=bar_colors, line=dict(width=0)),
            text=b_labels,
            textposition="outside",
            textfont=dict(size=11, color="#cbd5e1"),
            cliponaxis=False,
        ))
        fig_b.update_layout(**chart_layout(
            height=320,
            showlegend=False,
            xaxis=dict(tickprefix="$", tickformat=",.0f"),
        ))
        st.plotly_chart(fig_b, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # ROW 3 — Retirement Gauge + Action Items
    # ═══════════════════════════════════════════════════════════════════════════
    g1, g2 = st.columns([1, 1.5])

    # ── Retirement Gauge ──────────────────────────────────────────────────────
    with g1:
        st.markdown('<p class="section-header">Retirement Readiness</p>', unsafe_allow_html=True)
        gauge_val    = min(readiness_pct, 150)
        needle_color = GREEN if readiness_pct >= 100 else (AMBER if readiness_pct >= 70 else RED)
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=gauge_val,
            number={"suffix": "%", "font": {"size": 28, "color": "#f1f5f9"}},
            delta={"reference": 100, "suffix": "%",
                   "increasing": {"color": GREEN}, "decreasing": {"color": RED}},
            gauge=dict(
                axis=dict(range=[0, 150], tickcolor="#475569",
                          tickfont=dict(color="#475569", size=10)),
                bar=dict(color=needle_color, thickness=0.25),
                bgcolor="rgba(0,0,0,0)",
                borderwidth=0,
                steps=[
                    dict(range=[0,   70],  color="rgba(239,68,68,0.15)"),
                    dict(range=[70,  100], color="rgba(245,158,11,0.15)"),
                    dict(range=[100, 150], color="rgba(16,185,129,0.15)"),
                ],
                threshold=dict(line=dict(color="white", width=2),
                               thickness=0.8, value=100),
            ),
        ))
        fig_gauge.update_layout(**chart_layout(
            height=260,
            margin=dict(l=20, r=20, t=20, b=20),
        ))
        st.plotly_chart(fig_gauge, use_container_width=True)
        st.markdown(
            f'<div style="text-align:center;color:#64748b;font-size:0.8rem;margin-top:-0.5rem">'
            f'<b>{years_to_ret} yrs</b> to retirement · target age {a["retirement_age"]}</div>',
            unsafe_allow_html=True,
        )

        if readiness_pct >= 100:
            st.success(f"✅ On track for retirement at {a['retirement_age']}")
        elif readiness_pct >= 70:
            st.warning("⚠️ Close — boost contributions to close the gap")
        else:
            st.error("❌ Significant gap — review projections tab for options")

    # ── Action Items ──────────────────────────────────────────────────────────
    with g2:
        st.markdown('<p class="section-header">Action Items & Alerts</p>', unsafe_allow_html=True)

        alerts = []

        # Emergency fund (dedicated bucket vs total liquid)
        ef_target    = total_exp * a["emergency_fund_target_months"]
        ef_mo_dedic  = a["emergency_fund_balance"] / total_exp if total_exp else 0
        if a["emergency_fund_balance"] >= ef_target:
            alerts.append(("green", "🛡️ Emergency Fund",
                           f"Fully funded — {ef_mo_dedic:.1f} mo dedicated + "
                           f"{ef_months - ef_mo_dedic:.1f} mo in other savings"))
        else:
            gap = ef_target - a["emergency_fund_balance"]
            alerts.append(("amber", "🛡️ Emergency Fund",
                           f"${gap:,.0f} short of {a['emergency_fund_target_months']}-month goal "
                           f"({ef_mo_dedic:.1f} mo dedicated, {ef_months:.1f} mo total liquid)"))


        # 401k match capture
        for acct in a["investment_accounts"]:
            if acct["account_type"] in ["401k", "Roth 401k"] and acct.get("employer_match_pct", 0) > 0:
                cap     = a["gross_income"] * acct["employer_match_ceiling_pct"] / 100 / 12
                matched = min(acct["monthly_contribution"], cap) * acct["employer_match_pct"] / 100
                if matched == 0:
                    alerts.append(("red", f"🤝 {acct['label']}",
                                  f"Not capturing match — contribute ≥ ${cap:,.0f}/mo"))
                else:
                    alerts.append(("green", f"🤝 {acct['label']}",
                                  f"Capturing ${matched:,.0f}/mo employer match"))

        # IRS contribution room (YTD-aware, skip flagged accounts)
        from utils.calculations import ACCOUNT_LIMITS
        _today_d = date.today()
        _months_in = (_today_d - date(_today_d.year, 1, 1)).days / 365 * 12

        for acct in a["investment_accounts"]:
            if acct.get("skip_contribution"):
                continue
            limits = ACCOUNT_LIMITS.get(acct["account_type"], {})
            limit  = limits.get("catchup" if a["age"] >= 50 else "base")
            if limit:
                ytd  = acct.get("ytd_contributed",
                                acct["monthly_contribution"] * _months_in)
                room = max(0, limit - ytd)
                if room < 1:
                    alerts.append(("green", f"📈 {acct['label']}",
                                  f"Maxed for {_today_d.year} at ${limit:,.0f} ✅"))
                elif ytd > 0:
                    pct = ytd / limit * 100
                    alerts.append(("blue", f"📈 {acct['label']}",
                                  f"${ytd:,.0f} of ${limit:,.0f} YTD ({pct:.0f}%) — "
                                  f"${room:,.0f} remaining"))
                else:
                    alerts.append(("amber", f"📈 {acct['label']}",
                                  f"No contributions yet (IRS limit: ${limit:,.0f}/yr)"))

        # High-rate debt
        for d in a["other_debts"]:
            if d["rate_pct"] > 7 and d["balance"] > 0:
                alerts.append(("red", f"💳 {d['name']}",
                              f"High-rate debt at {d['rate_pct']:.1f}% — consider paying down"))

        # Monthly cash flow
        if net_cash_flow < 0:
            alerts.append(("red", "💰 Cash Flow",
                          f"Deficit of ${abs(net_cash_flow):,.0f}/mo — expenses exceed income"))
        elif net_cash_flow > 1000:
            alerts.append(("blue", "💰 Cash Flow",
                          f"${net_cash_flow:,.0f}/mo unallocated — consider investing surplus"))

        for badge, title, msg in alerts[:8]:
            st.markdown(
                f'<div style="display:flex;align-items:flex-start;gap:10px;'
                f'background:#0f172a;border:1px solid rgba(255,255,255,0.07);'
                f'border-radius:10px;padding:0.75rem 1rem;margin-bottom:0.5rem;">'
                f'<div><div style="margin-bottom:2px">'
                f'<span class="badge-{badge}">{title}</span></div>'
                f'<div style="color:#94a3b8;font-size:0.8rem;line-height:1.4">{msg}</div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

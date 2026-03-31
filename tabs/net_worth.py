import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import date
from utils.calculations import (
    build_amortization, get_loan_status, calc_monthly_payment,
)
from utils.styles import BLUE, GREEN, RED, PURPLE, AMBER, CYAN, chart_layout
from utils.database import log_net_worth, get_net_worth_history


def render():
    a = st.session_state.assumptions
    st.header("🏦 Net Worth Overview")

    # ── Calculations ──────────────────────────────────────────────────────────
    amort = build_amortization(
        a["loan_original_amount"], a["loan_interest_rate"],
        a["loan_term_years"], a["loan_start_date"],
    )
    status = get_loan_status(amort, date.today())
    mortgage_bal      = status["current_balance"]
    home_equity       = max(a["home_current_value"] - mortgage_bal, 0)
    total_investments = sum(acct["balance"] for acct in a["investment_accounts"])

    sinking_fund = a.get("sinking_fund_balance", 0)

    assets = {
        "Home Value":          a["home_current_value"],
        "HYSA":                a["emergency_fund_balance"],
        "Sinking Fund":        sinking_fund,
        "Investment Accounts": total_investments,
        "Checking / Savings":  a["checking_savings_balance"],
    }
    liabilities = {"Mortgage Balance": mortgage_bal}
    liabilities.update({d["name"]: d["balance"] for d in a["other_debts"] if d["balance"] > 0})

    total_assets      = sum(assets.values())
    total_liabilities = sum(liabilities.values())
    net_worth         = total_assets - total_liabilities
    dta_ratio         = total_liabilities / total_assets * 100 if total_assets else 0

    cash_balance = (
        a["emergency_fund_balance"]
        + a.get("sinking_fund_balance", 0)
        + a["checking_savings_balance"]
    )
    log_net_worth(date.today(), net_worth, total_assets, total_liabilities,
                  total_investments, home_equity, cash_balance)

    # ═════════════════════════════════════════════════════════════════════════
    # ROW 1 — KPI Cards
    # ═════════════════════════════════════════════════════════════════════════
    c1, c2, c3, c4 = st.columns(4)
    liquid = a["emergency_fund_balance"] + sinking_fund + a["checking_savings_balance"] + total_investments
    c1.metric("💼 Net Worth", f"${net_worth:,.0f}",
              delta=f"Equity {home_equity/1000:.0f}k + Liquid {liquid/1000:.0f}k")
    c2.metric("💚 Total Assets", f"${total_assets:,.0f}")
    c3.metric("🔴 Total Liabilities", f"${total_liabilities:,.0f}")
    dta_label = "✅ Healthy" if dta_ratio < 50 else ("⚠️ Moderate" if dta_ratio < 75 else "🔴 High")
    c4.metric("📊 Debt-to-Asset", f"{dta_ratio:.1f}%", delta=dta_label,
              delta_color="normal" if dta_ratio < 50 else ("off" if dta_ratio < 75 else "inverse"))

    st.divider()

    # ═════════════════════════════════════════════════════════════════════════
    # ROW 2 — Diverging Horizontal Bar
    # ═════════════════════════════════════════════════════════════════════════
    def _fmt(v):
        av = abs(v)
        if av >= 1_000_000:
            return f"${av / 1_000_000:.2f}M"
        if av >= 1_000:
            return f"${av / 1_000:.0f}k"
        return f"${av:,.0f}"

    # Build items: assets positive, liabilities negative
    items = []
    for k, v in assets.items():
        if v > 0:
            items.append((k, v, GREEN))
    for k, v in liabilities.items():
        if v > 0:
            items.append((k, -v, RED))

    # Sort by absolute value descending (largest at top in horizontal bar = last in list)
    items.sort(key=lambda x: abs(x[1]))

    bar_labels = [i[0] for i in items]
    bar_values = [i[1] for i in items]
    bar_colors = [i[2] for i in items]
    bar_text   = [_fmt(v) for v in bar_values]

    fig_div = go.Figure(go.Bar(
        y=bar_labels,
        x=bar_values,
        orientation="h",
        marker=dict(color=bar_colors, line=dict(width=0)),
        text=bar_text,
        textposition="outside",
        textfont=dict(size=12, color="#cbd5e1"),
        cliponaxis=False,
    ))

    x_max = max(abs(v) for v in bar_values) * 1.3
    fig_div.update_layout(**chart_layout(
        title="Assets & Liabilities",
        height=max(280, len(items) * 50 + 80),
        showlegend=False,
        xaxis=dict(
            range=[-x_max, x_max],
            tickprefix="$",
            tickformat=",.0s",
            zeroline=True,
            zerolinewidth=2,
            zerolinecolor="rgba(255,255,255,0.25)",
        ),
    ))
    st.plotly_chart(fig_div, use_container_width=True)

    # ═════════════════════════════════════════════════════════════════════════
    # ROW 3 — Net Worth Composition Donut
    # ═════════════════════════════════════════════════════════════════════════
    st.divider()

    comp = {}
    comp["Home Equity"]        = home_equity
    comp["Investments"]        = total_investments
    comp["HYSA"]               = a["emergency_fund_balance"]
    comp["Sinking Fund"]       = sinking_fund
    comp["Checking / Savings"] = a["checking_savings_balance"]
    # Subtract non-mortgage debts from composition
    other_debt_total = sum(d["balance"] for d in a["other_debts"] if d["balance"] > 0)

    comp_colors = {
        "Home Equity": BLUE, "Investments": PURPLE,
        "HYSA": GREEN, "Sinking Fund": AMBER, "Checking / Savings": CYAN,
    }

    # Filter to positive values
    comp_labels = [k for k, v in comp.items() if v > 0]
    comp_values = [v for v in comp.values() if v > 0]
    colors      = [comp_colors.get(k, "#475569") for k in comp_labels]

    if other_debt_total > 0:
        comp_labels.append("Other Debt")
        comp_values.append(other_debt_total)
        colors.append(RED)

    fig_donut = go.Figure(go.Pie(
        labels=comp_labels,
        values=comp_values,
        hole=0.5,
        marker=dict(colors=colors, line=dict(color="#020817", width=2)),
        textinfo="label+percent",
        textposition="inside",
        insidetextorientation="horizontal",
        textfont=dict(size=13, color="white", family="Barlow"),
        hovertemplate="%{label}<br>$%{value:,.0f} (%{percent})<extra></extra>",
        sort=False,
    ))

    nw_display = f"${net_worth/1_000_000:.2f}M" if net_worth >= 1_000_000 else f"${net_worth/1000:.0f}k"
    fig_donut.add_annotation(
        text=f"<b>{nw_display}</b><br><span style='font-size:10px;color:#64748b'>net worth</span>",
        x=0.5, y=0.5, xref="paper", yref="paper",
        showarrow=False,
        font=dict(size=22, color="#f1f5f9", family="Barlow Condensed"),
    )
    fig_donut.update_layout(**chart_layout(
        title="Net Worth Composition",
        height=420,
        showlegend=False,
    ))
    st.plotly_chart(fig_donut, use_container_width=True)

    # ═════════════════════════════════════════════════════════════════════════
    # ROW 4 — Emergency Fund Status
    # ═════════════════════════════════════════════════════════════════════════
    st.divider()
    st.subheader("🛡️ Emergency Fund Status")

    monthly_pi    = calc_monthly_payment(
        a["loan_original_amount"], a["loan_interest_rate"], a["loan_term_years"])
    monthly_tax   = a["home_current_value"] * a["property_tax_rate"] / 100 / 12
    monthly_ins   = a["home_insurance_annual"] / 12
    monthly_hoa   = a["hoa_monthly"]
    monthly_maint = a["home_current_value"] * a["maintenance_pct"] / 100 / 12
    total_expenses = (
        monthly_pi + monthly_tax + monthly_ins + monthly_hoa + monthly_maint
        + sum(a["budget"].values())
        + sum(d["monthly_payment"] for d in a["other_debts"])
    )
    target     = total_expenses * a["emergency_fund_target_months"]
    coverage   = a["emergency_fund_balance"] / total_expenses if total_expenses else 0
    pct_funded = min(a["emergency_fund_balance"] / target * 100, 100) if target else 0

    ec1, ec2, ec3 = st.columns(3)
    ec1.metric("Current Balance",  f"${a['emergency_fund_balance']:,.0f}")
    ec2.metric("Target Balance",
               f"${target:,.0f}  ({a['emergency_fund_target_months']} months)")
    ec3.metric("Coverage",         f"{coverage:.1f} months")

    st.progress(pct_funded / 100, text=f"{pct_funded:.0f}% funded")

    if coverage >= a["emergency_fund_target_months"]:
        st.success(f"✅ Fully funded — {coverage:.1f} months of expenses covered")
    else:
        gap = target - a["emergency_fund_balance"]
        st.warning(
            f"⚠️ ${gap:,.0f} short of your {a['emergency_fund_target_months']}-month goal "
            f"(currently {coverage:.1f} months)"
        )

    # ═════════════════════════════════════════════════════════════════════════
    # ROW 5 — Net Worth History
    # ═════════════════════════════════════════════════════════════════════════
    st.divider()
    st.subheader("📈 Net Worth Over Time")

    history = get_net_worth_history()
    if len(history) <= 1:
        st.info("History will build over time as you visit this page.")
    else:
        dates = [r["date"] for r in history]
        fig_hist = go.Figure()
        fig_hist.add_trace(go.Scatter(
            x=dates, y=[r["net_worth"] for r in history],
            name="Net Worth", mode="lines+markers",
            line=dict(color=PURPLE, width=2),
        ))
        fig_hist.add_trace(go.Scatter(
            x=dates, y=[r["total_assets"] for r in history],
            name="Total Assets", mode="lines+markers",
            line=dict(color=GREEN, width=2),
        ))
        fig_hist.add_trace(go.Scatter(
            x=dates, y=[r["total_liabilities"] for r in history],
            name="Total Liabilities", mode="lines+markers",
            line=dict(color=RED, width=2),
        ))
        fig_hist.update_layout(**chart_layout(
            title="Net Worth History",
            height=340,
            showlegend=True,
            yaxis=dict(tickprefix="$", tickformat=",.0s"),
        ))
        st.plotly_chart(fig_hist, use_container_width=True)

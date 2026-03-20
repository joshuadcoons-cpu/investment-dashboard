import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import date
from utils.calculations import calc_monthly_payment, build_amortization, get_loan_status
from utils.styles import BLUE, GREEN, RED, AMBER, chart_layout


def render():
    a = st.session_state.assumptions
    st.header("🏡 Home & Mortgage")

    # ── Build amortization ────────────────────────────────────────────────────
    amort = build_amortization(
        a["loan_original_amount"], a["loan_interest_rate"],
        a["loan_term_years"], a["loan_start_date"],
    )
    today = date.today()
    status = get_loan_status(amort, today)

    monthly_pi    = calc_monthly_payment(
        a["loan_original_amount"], a["loan_interest_rate"], a["loan_term_years"])
    monthly_tax   = a["home_current_value"] * a["property_tax_rate"] / 100 / 12
    monthly_ins   = a["home_insurance_annual"] / 12
    monthly_hoa   = a["hoa_monthly"]
    monthly_maint = a["home_current_value"] * a["maintenance_pct"] / 100 / 12
    total_monthly = monthly_pi + monthly_tax + monthly_ins + monthly_hoa + monthly_maint

    equity = a["home_current_value"] - status["current_balance"]
    ltv    = (status["current_balance"] / a["home_current_value"] * 100) if a["home_current_value"] else 0
    equity_pct = 100 - ltv
    yr_rem = int(status["months_remaining"] // 12)
    mo_rem = int(status["months_remaining"] % 12)

    # ── Key Metrics (2 rows × 3) ─────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    c1.metric("🏠 Home Value",      f"${a['home_current_value']:,.0f}")
    c2.metric("💰 Home Equity",     f"${equity:,.0f}",
              delta=f"{equity_pct:.1f}% equity", delta_color="off")
    c3.metric("🏦 Loan Balance",    f"${status['current_balance']:,.0f}")

    c4, c5, c6 = st.columns(3)
    c4.metric("📊 LTV Ratio",       f"{ltv:.1f}%",
              delta=f"{'✅ No PMI' if ltv <= 80 else '⚠️ PMI likely'}", delta_color="off")
    c5.metric("📅 Payoff Date",     status["payoff_date"].strftime("%b %Y"),
              delta=f"{yr_rem}yr {mo_rem}mo remaining", delta_color="off")
    c6.metric("💵 Monthly Payment", f"${total_monthly:,.0f}",
              delta=f"P&I ${monthly_pi:,.0f} + costs ${total_monthly - monthly_pi:,.0f}",
              delta_color="off")

    st.divider()

    left, right = st.columns([1, 2])

    # ── Left: Cost Breakdown & Loan Summary ───────────────────────────────────
    with left:
        st.subheader("Monthly Housing Costs")
        cost_items = {
            "Principal & Interest": monthly_pi,
            "Property Tax":         monthly_tax,
            "Home Insurance":       monthly_ins,
            "HOA":                  monthly_hoa,
            "Maintenance Reserve":  monthly_maint,
        }
        cost_df = pd.DataFrame(
            [(k, v) for k, v in cost_items.items() if v > 0],
            columns=["Item", "Monthly ($)"]
        )
        st.dataframe(
            cost_df.style.format({"Monthly ($)": "${:,.2f}"}),
            use_container_width=True, hide_index=True
        )
        st.metric("**Total Monthly Housing Cost**", f"${total_monthly:,.2f}")

        st.divider()
        st.subheader("Loan Summary")
        st.info(f"**{yr_rem} years, {mo_rem} months** remaining")
        st.write(f"- Interest paid so far: **${status['total_interest_paid']:,.0f}**")
        st.write(f"- Interest remaining: **${status['total_interest_remaining']:,.0f}**")
        total_int = status["total_interest_paid"] + status["total_interest_remaining"]
        st.write(f"- Total lifetime interest: **${total_int:,.0f}**")
        st.write(f"- Payments made: **{status['months_paid']}** of "
                 f"**{a['loan_term_years'] * 12}**")

        fig_donut = go.Figure(go.Pie(
            labels=cost_df["Item"], values=cost_df["Monthly ($)"],
            hole=0.52,
            marker=dict(
                colors=[BLUE, AMBER, GREEN, "#f97316", "#06b6d4"],
                line=dict(color="#020817", width=3),
            ),
            textinfo="percent",
            textposition="inside",
            hovertemplate="<b>%{label}</b><br>$%{value:,.2f}/mo<br>%{percent}<extra></extra>",
        ))
        fig_donut.update_layout(**chart_layout(
            title="Cost Breakdown", height=280, showlegend=True,
            legend=dict(orientation="v", x=1.05, y=0.5, font=dict(size=10)),
        ))
        st.plotly_chart(fig_donut, use_container_width=True)

    # ── Right: Charts ─────────────────────────────────────────────────────────
    with right:
        st.subheader("Home Value vs. Loan Balance Over Time")

        # Annual summary
        annual = amort.groupby("year").last().reset_index()

        # Project home value from current value using appreciation rate
        annual["home_value"] = a["home_current_value"] * (
            (1 + a["home_appreciation_pct"] / 100) ** (annual["year"] - today.year)
        )
        annual["equity"] = (annual["home_value"] - annual["balance"]).clip(lower=0)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=annual["year"], y=annual["home_value"],
            name="Home Value", fill="tozeroy",
            fillcolor="rgba(16,185,129,0.12)", line=dict(color=GREEN, width=2.5),
        ))
        fig.add_trace(go.Scatter(
            x=annual["year"], y=annual["balance"],
            name="Loan Balance", fill="tozeroy",
            fillcolor="rgba(239,68,68,0.12)", line=dict(color=RED, width=2),
        ))
        fig.add_vline(x=today.year, line_dash="dash",
                      line_color="rgba(255,255,255,0.35)",
                      annotation_text="Today",
                      annotation_font=dict(color="#94a3b8", size=11),
                      annotation_position="top right")
        fig.update_layout(**chart_layout(
            yaxis=dict(tickprefix="$", tickformat=",.0f", title="Amount ($)"),
            height=360,
            xaxis_title="Year",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        ))
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Amortization Schedule (Year-End Summary)")
        display = annual[["year", "balance", "equity", "cum_interest"]].copy()
        display.columns = ["Year", "Remaining Balance ($)", "Home Equity ($)", "Cumul. Interest Paid ($)"]
        st.dataframe(
            display.style.format({
                "Remaining Balance ($)":    "${:,.0f}",
                "Home Equity ($)":          "${:,.0f}",
                "Cumul. Interest Paid ($)": "${:,.0f}",
            }),
            use_container_width=True, hide_index=True, height=300,
        )

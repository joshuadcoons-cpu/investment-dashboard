import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import date
from utils.calculations import calc_monthly_payment, build_amortization, get_loan_status
from utils.styles import BLUE, GREEN, RED, AMBER, chart_layout, theme_colors


def render():
    tc = theme_colors()
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
                line=dict(color=tc["pie_border"], width=3),
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
                      line_color=tc["zeroline"],
                      annotation_text="Today",
                      annotation_font=dict(color=tc["muted"], size=11),
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

    # ── Extra Payment Simulator ───────────────────────────────────────────────
    st.divider()
    st.subheader("What If: Extra Monthly Payment")
    extra = st.slider("Extra $/mo toward principal", 0, 5000, 0, step=100)

    if extra > 0:
        r = a["loan_interest_rate"] / 100 / 12
        pmt = calc_monthly_payment(
            a["loan_original_amount"], a["loan_interest_rate"], a["loan_term_years"]
        )
        balance = float(a["loan_original_amount"])
        accel_balances = []
        months = 0
        while balance > 0 and months < a["loan_term_years"] * 12:
            interest = balance * r
            principal_paid = min(pmt - interest + extra, balance)
            balance = max(balance - principal_paid, 0)
            months += 1
            accel_balances.append(balance)

        orig_months = a["loan_term_years"] * 12
        months_saved = orig_months - months
        years_saved = months_saved / 12

        orig_total_interest = status["total_interest_paid"] + status["total_interest_remaining"]
        accel_total_interest = sum(
            (a["loan_original_amount"] if i == 0 else accel_balances[i - 1]) *
            (a["loan_interest_rate"] / 100 / 12)
            for i in range(months)
        )
        interest_saved = orig_total_interest - accel_total_interest

        loan_start = date.fromisoformat(a["loan_start_date"])
        new_payoff = date(
            loan_start.year + (loan_start.month - 1 + months) // 12,
            (loan_start.month - 1 + months) % 12 + 1,
            1,
        )

        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Years Saved",       f"{years_saved:.1f} yrs",
                   delta=f"{months_saved} months", delta_color="normal")
        mc2.metric("Interest Saved",    f"${interest_saved:,.0f}",
                   delta_color="normal")
        mc3.metric("New Payoff Date",   new_payoff.strftime("%b %Y"),
                   delta=f"vs {status['payoff_date'].strftime('%b %Y')} original",
                   delta_color="off")

        orig_balances = amort["balance"].tolist()
        n = max(len(orig_balances), len(accel_balances))
        orig_padded  = orig_balances  + [0] * (n - len(orig_balances))
        accel_padded = accel_balances + [0] * (n - len(accel_balances))

        fig_sim = go.Figure()
        fig_sim.add_trace(go.Scatter(
            y=orig_padded, name="Original Schedule",
            line=dict(color=RED, width=2),
            hovertemplate="Month %{x}<br>Balance: $%{y:,.0f}<extra></extra>",
        ))
        fig_sim.add_trace(go.Scatter(
            y=accel_padded, name=f"With ${extra:,}/mo Extra",
            line=dict(color=GREEN, width=2.5),
            hovertemplate="Month %{x}<br>Balance: $%{y:,.0f}<extra></extra>",
        ))
        fig_sim.update_layout(**chart_layout(
            title=f"Balance Paydown: +${extra:,}/mo Extra",
            yaxis=dict(tickprefix="$", tickformat=",.0f", title="Remaining Balance ($)"),
            xaxis_title="Payment Month",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=340,
        ))
        st.plotly_chart(fig_sim, use_container_width=True)

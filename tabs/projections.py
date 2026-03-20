import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta
from utils.calculations import calc_monthly_payment
from utils.styles import BLUE, GREEN, RED, PURPLE, AMBER, CYAN, chart_layout


# ── Helpers ───────────────────────────────────────────────────────────────────

def _employer_match_mo(a, w2_growth_factor=1.0):
    """Monthly employer match, optionally scaled for income growth."""
    match = 0.0
    for ac in a.get("investment_accounts", []):
        if ac.get("employer_match_pct", 0) > 0 and ac.get("employer_match_ceiling_pct", 0) > 0:
            gross     = a["gross_income"] * w2_growth_factor
            ceiling   = gross * ac["employer_match_ceiling_pct"] / 100 / 12
            matchable = min(ac["monthly_contribution"], ceiling)
            match    += matchable * ac["employer_match_pct"] / 100
    return match


def _build_flow_schedule(months, params):
    """
    Build a detailed per-month nominal cash flow list.
    Models:  W2 income growth (income_growth_pct),  Q1 bonus,
             LP doubling + gift ending,  3-phase retirement.
    """
    p           = params
    w2_gr       = p["income_growth_mo"]     # monthly W2 growth rate
    infl_mo     = p["inflation_mo"]         # monthly CPI rate
    lp_double_m = p["lp_double_month"]      # month LP doubles (0 = never)
    w2_stop     = p["w2_stop_month"]
    ss_start    = p["ss_start_month"]

    # Base (today's) values
    lp_net_f   = p.get("lp_net_pct", 100) / 100        # after-tax fraction of LP income
    lp_base    = p["lp_monthly"] * lp_net_f             # after-tax LP income base
    gift_base  = p["gift_monthly"]                      # current gift (ends at LP doubling)
    w2_base    = p["w2_take_home"]
    match_base = p["employer_match"]
    costs_base = p["operating_costs"]
    post_costs = p.get("post_payoff_costs", costs_base) # costs after mortgage paid off
    payoff_mo  = p.get("payoff_month", 99999)           # months from today; 99999 = never
    burn_base  = p["burn_mo"]
    ss_base    = p["ss_monthly"]
    bonus_mo   = p["bonus_annual"] / 12                 # spread Q1 bonus evenly

    flows = []
    for m in range(months):
        infl         = (1 + infl_mo) ** m
        w2_growth    = (1 + w2_gr)   ** m   # W2 grows independently of CPI
        lp_doubled   = (lp_double_m > 0) and (m >= lp_double_m)

        # LP and gift in nominal terms (LP already net-of-tax via lp_base)
        lp_now   = lp_base * (2 if lp_doubled else 1) * infl
        gift_now = 0.0 if lp_doubled else gift_base * infl

        if m < w2_stop:
            # ── Phase 1: Working ──────────────────────────────────────────────
            w2_now     = w2_base   * w2_growth
            match_now  = match_base * w2_growth          # match scales with salary
            bonus_now  = bonus_mo  * w2_growth           # bonus scales with salary
            cur_costs  = post_costs if m >= payoff_mo else costs_base
            costs_now  = cur_costs * infl
            passive_now= lp_now + gift_now
            flow       = w2_now + passive_now + match_now + bonus_now - costs_now

        elif m < ss_start:
            # ── Phase 2: Passive only (no W2, no SS) ─────────────────────────
            burn_now   = burn_base * infl
            flow       = lp_now - burn_now               # gift already 0 post-LP-doubling

        else:
            # ── Phase 3: SS active ────────────────────────────────────────────
            burn_now   = burn_base * infl
            ss_now     = ss_base   * infl
            flow       = lp_now + ss_now - burn_now

        flows.append(flow)
    return flows


def _project(starting, annual_return_pct, flow_schedule):
    """Project portfolio balance month by month."""
    r      = annual_return_pct / 100 / 12
    values = [float(starting)]
    bal    = float(starting)
    for flow in flow_schedule:
        bal = max(bal * (1 + r) + flow, 0)
        values.append(bal)
    return values


def _payoff_with_extra(loan_amount, rate_pct, term_years, loan_start_date):
    """
    Build monthly balance schedule with one extra full P&I payment per year
    applied entirely to principal.  Returns (DataFrame[date, balance], payoff_date).
    """
    r   = rate_pct / 100 / 12
    n   = term_years * 12
    pmt = loan_amount * r / (1 - (1 + r) ** -n) if r > 0 else loan_amount / n
    bal, dates, bals = float(loan_amount), [], []
    payoff_date = loan_start_date + relativedelta(months=n)  # fallback

    for mo in range(n + 1):
        dt = loan_start_date + relativedelta(months=mo)
        dates.append(dt)
        bals.append(max(round(bal, 2), 0.0))

        if bal <= 0:
            payoff_date = dt
            break

        interest  = bal * r
        principal = min(pmt - interest, bal)
        bal      -= principal

        if bal <= 0:
            payoff_date = loan_start_date + relativedelta(months=mo + 1)
            dates.append(payoff_date)
            bals.append(0.0)
            break

        # Extra annual payment — full P&I applied to principal
        if (mo + 1) % 12 == 0:
            bal = max(bal - pmt, 0.0)
            if bal == 0.0:
                payoff_date = loan_start_date + relativedelta(months=mo + 1)
                dates.append(payoff_date)
                bals.append(0.0)
                break

    import pandas as _pd
    return _pd.DataFrame({"date": dates, "balance": bals}), payoff_date


def _phase_card(color_hex, title_html, value_str, value_color, subtitle, breakdown):
    st.markdown(f"""
    <div style="background:#0f172a;border:1px solid {color_hex}40;
                border-radius:12px;padding:20px;text-align:center;height:100%">
        <div style="color:{color_hex};font-size:10px;font-weight:700;letter-spacing:1.2px;
                    text-transform:uppercase;margin-bottom:10px">
            {title_html}
        </div>
        <div style="color:{value_color};font-size:28px;font-weight:700;line-height:1">
            {value_str}
        </div>
        <div style="color:#64748b;font-size:11px;margin-top:6px">{subtitle}</div>
        <div style="color:#475569;font-size:10.5px;margin-top:10px;line-height:1.6">
            {breakdown}
        </div>
    </div>
    """, unsafe_allow_html=True)


# ── Main render ───────────────────────────────────────────────────────────────

def render():
    a = st.session_state.assumptions
    st.header("🔮 Long-Term Projections")

    # ── Ages & key parameters ─────────────────────────────────────────────────
    age        = a["age"]
    ret_age    = a.get("retirement_age", 65)
    w2_ret_age = a.get("w2_retirement_age", 55)
    ss_age     = a.get("social_security_start_age", 67)

    if w2_ret_age <= age:
        st.warning("W2 retirement age must be greater than current age. Update in ⚙️ Setup.")
        return

    today        = date.today()
    horizon_yrs  = (ret_age - age) + 20
    total_months = horizon_yrs * 12

    w2_stop_mo   = (w2_ret_age - age) * 12
    ss_start_mo  = (ss_age     - age) * 12
    ret_mo       = (ret_age    - age) * 12

    x_years  = [today.year + m / 12 for m in range(total_months + 1)]
    w2_year  = today.year + (w2_ret_age - age)
    ret_year = today.year + (ret_age    - age)
    ss_year  = today.year + (ss_age     - age)

    # ── Income & passive assumptions ──────────────────────────────────────────
    lp_monthly     = a.get("parkwood_lp_monthly", 0)
    lp_net_pct_val = a.get("lp_net_pct", 100)
    lp_monthly_net = lp_monthly * lp_net_pct_val / 100   # after partial-shelter tax
    gift_monthly   = a.get("family_gift_annual", 0) / 12
    w2_take_home   = a.get("take_home_monthly", 0) + a.get("spouse_take_home_monthly", 0)
    match_today  = _employer_match_mo(a)
    burn_mo      = 0  # derived from post_payoff_costs below
    ss_monthly   = a.get("social_security_monthly", 0)
    bonus_annual = a.get("annual_bonus", 0)

    income_growth_mo = a.get("income_growth_pct", 3.0) / 100 / 12
    inflation_mo     = a.get("inflation_pct", 3.0) / 100 / 12
    base_rate        = a.get("investment_return_pct", 7.0)

    # LP doubling event
    lp_double_years = a.get("lp_double_years", 0)
    lp_double_month = lp_double_years * 12 if lp_double_years > 0 else 0

    # ── Operating costs ───────────────────────────────────────────────────────
    monthly_pi    = calc_monthly_payment(
        a["loan_original_amount"], a["loan_interest_rate"], a["loan_term_years"])
    monthly_tax   = a["home_current_value"] * a["property_tax_rate"] / 100 / 12
    monthly_ins   = a["home_insurance_annual"] / 12
    monthly_hoa   = a.get("hoa_monthly", 0)
    monthly_maint = a["home_current_value"] * a.get("maintenance_pct", 1) / 100 / 12
    total_housing = monthly_pi + monthly_tax + monthly_ins + monthly_hoa + monthly_maint
    total_debts   = sum(d["monthly_payment"] for d in a.get("other_debts", []))
    total_variable= sum(v for v in a.get("budget", {}).values())
    operating_costs   = total_housing + total_debts + total_variable
    post_payoff_costs = operating_costs - monthly_pi   # after mortgage paid off
    # Mortgage is paid off before W2 retirement, so Phase 2/3 burn = costs without P&I
    burn_mo = post_payoff_costs

    # ── Accelerated payoff: one extra P&I payment per year ────────────────────
    accel_amort, payoff_date = _payoff_with_extra(
        a["loan_original_amount"], a["loan_interest_rate"],
        a["loan_term_years"], a["loan_start_date"],
    )
    payoff_mo_from_today = (payoff_date.year - today.year) * 12 + (payoff_date.month - today.month)
    payoff_year = payoff_date.year + payoff_date.month / 12
    payoff_age  = age + payoff_mo_from_today / 12

    # ── Today's phase flows (for display in cards) — LP is after-tax ──────────
    passive_today   = lp_monthly_net + gift_monthly
    passive_post_lp = lp_monthly_net * 2      # after LP doubles, gift gone (net of tax)

    p1_flow_today = w2_take_home + passive_today + match_today + bonus_annual / 12 - operating_costs
    p2_flow_today = passive_post_lp - burn_mo          # in today's dollars, LP already doubled
    p3_flow_today = passive_post_lp + ss_monthly - burn_mo

    # ── Build flow schedule params ─────────────────────────────────────────────
    flow_params = dict(
        income_growth_mo  = income_growth_mo,
        inflation_mo      = inflation_mo,
        lp_double_month   = lp_double_month,
        w2_stop_month     = w2_stop_mo,
        ss_start_month    = ss_start_mo,
        lp_monthly        = lp_monthly,           # gross; lp_net_pct applied inside schedule
        lp_net_pct        = lp_net_pct_val,
        gift_monthly      = gift_monthly,
        w2_take_home      = w2_take_home,
        employer_match    = match_today,
        operating_costs   = operating_costs,
        post_payoff_costs = post_payoff_costs,
        payoff_month      = payoff_mo_from_today,
        burn_mo           = burn_mo,
        ss_monthly        = ss_monthly,
        bonus_annual      = bonus_annual,
    )

    # ── Project portfolio ──────────────────────────────────────────────────────
    total_balance = sum(acct["balance"] for acct in a.get("investment_accounts", []))
    base_flows    = _build_flow_schedule(total_months, flow_params)
    base_inv      = _project(total_balance, base_rate,            base_flows)
    conserv       = _project(total_balance, max(base_rate - 2, 1), base_flows)
    optimistic    = _project(total_balance, base_rate + 2,         base_flows)

    # ── Home equity (with accelerated payoff) ─────────────────────────────────
    h_r           = a["home_appreciation_pct"] / 100 / 12
    equity_values = []
    cur_hv        = float(a["home_current_value"])
    for m in range(total_months + 1):
        target = today + relativedelta(months=m)
        if target >= payoff_date:
            loan = 0.0
        else:
            past = accel_amort[accel_amort["date"] <= target]
            loan = float(past.iloc[-1]["balance"]) if not past.empty else float(a["loan_original_amount"])
        equity_values.append(max(cur_hv - loan, 0))
        cur_hv *= (1 + h_r)

    # ── Net worth ──────────────────────────────────────────────────────────────
    other_assets = (a.get("emergency_fund_balance", 0) + a.get("sinking_fund_balance", 0)
                    + a.get("checking_savings_balance", 0))
    nw_values    = [inv + eq + other_assets for inv, eq in zip(base_inv, equity_values)]

    # ── Chart ──────────────────────────────────────────────────────────────────
    fig = go.Figure()

    # Phase background bands — no built-in annotation_text (labels added manually below)
    fig.add_vrect(x0=today.year, x1=w2_year,
                  fillcolor="rgba(59,130,246,0.04)", line_width=0)
    fig.add_vrect(x0=w2_year, x1=ss_year,
                  fillcolor="rgba(245,158,11,0.05)", line_width=0)
    fig.add_vrect(x0=ss_year, x1=x_years[-1],
                  fillcolor="rgba(16,185,129,0.05)", line_width=0)

    # Phase header labels — centered in each band, pinned to top of plot area
    _bands = [
        ((today.year + w2_year) / 2, "PHASE 1 · WORKING",   "#3b82f6"),
        ((w2_year   + ss_year)  / 2, "PHASE 2 · PASSIVE",   "#f59e0b"),
        ((ss_year + x_years[-1]) / 2, "PHASE 3 · SS ACTIVE", "#10b981"),
    ]
    for bx, blabel, bcolor in _bands:
        fig.add_annotation(
            x=bx, y=0.99, xref="x", yref="paper",
            text=f"<b>{blabel}</b>", showarrow=False,
            font=dict(color=bcolor, size=13, family="Barlow"),
            xanchor="center", yanchor="top",
        )

    # Confidence band
    fig.add_trace(go.Scatter(
        x=x_years, y=optimistic,
        name=f"Return Range ({max(base_rate-2,1):.0f}–{base_rate+2:.0f}%)",
        line=dict(color="rgba(59,130,246,0)", width=0),
        mode="lines", showlegend=True, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=x_years, y=conserv,
        line=dict(color="rgba(59,130,246,0)", width=0),
        mode="lines", fill="tonexty",
        fillcolor="rgba(59,130,246,0.10)",
        showlegend=False, hoverinfo="skip",
    ))

    # Portfolio
    fig.add_trace(go.Scatter(
        x=x_years, y=base_inv,
        name=f"Portfolio ({base_rate:.0f}% return)",
        line=dict(color=BLUE, width=3), mode="lines",
    ))
    # Home equity
    fig.add_trace(go.Scatter(
        x=x_years, y=equity_values,
        name="Home Equity",
        line=dict(color=AMBER, width=2, dash="dot"), mode="lines",
    ))
    # Net worth
    fig.add_trace(go.Scatter(
        x=x_years, y=nw_values,
        name="Total Net Worth",
        line=dict(color=PURPLE, width=3), mode="lines",
    ))

    # ── Vertical event lines — labels use yref="paper" to prevent crowding ──
    # LP doubling (near left edge, label goes right)
    if lp_double_years > 0:
        lp_event_year = today.year + lp_double_years
        fig.add_vline(x=lp_event_year, line_dash="dot", line_color=CYAN, line_width=1.5)
        fig.add_annotation(
            x=lp_event_year, y=0.90, xref="x", yref="paper",
            text=f"<b>LP 2× · Gift Ends</b> (yr {lp_double_years})",
            showarrow=False, font=dict(color=CYAN, size=11),
            xanchor="left", yanchor="top",
        )

    # W2 ends (label goes right)
    fig.add_vline(x=w2_year, line_dash="dot", line_color=AMBER, line_width=1.5)
    fig.add_annotation(
        x=w2_year, y=0.90, xref="x", yref="paper",
        text=f"<b>W2 Ends</b> · Age {w2_ret_age}",
        showarrow=False, font=dict(color=AMBER, size=11),
        xanchor="left", yanchor="top",
    )

    # Formal retirement (label goes left, stepped lower to avoid SS overlap)
    if ret_age != w2_ret_age and ret_age != ss_age:
        fig.add_vline(x=ret_year, line_dash="dash",
                      line_color="rgba(255,255,255,0.25)", line_width=1.2)
        fig.add_annotation(
            x=ret_year, y=0.74, xref="x", yref="paper",
            text=f"<b>Retirement</b> · Age {ret_age}",
            showarrow=False, font=dict(color="#94a3b8", size=11),
            xanchor="right", yanchor="top",
        )

    # SS begins (label goes right)
    fig.add_vline(x=ss_year, line_dash="dot", line_color=GREEN, line_width=1.5)
    fig.add_annotation(
        x=ss_year, y=0.90, xref="x", yref="paper",
        text=f"<b>SS Begins</b> · Age {ss_age}",
        showarrow=False, font=dict(color=GREEN, size=11),
        xanchor="left", yanchor="top",
    )

    # Mortgage paid-off milestone (orange, stepped below event labels)
    _ORANGE = "#f97316"
    if payoff_year < x_years[-1]:
        fig.add_vline(x=payoff_year, line_dash="dot", line_color=_ORANGE, line_width=1.5)
        fig.add_annotation(
            x=payoff_year, y=0.80, xref="x", yref="paper",
            text=f"<b>🏠 Mortgage Free</b> · Age {int(payoff_age)}",
            showarrow=False, font=dict(color=_ORANGE, size=11),
            xanchor="left", yanchor="top",
        )

    fig.update_layout(**chart_layout(
        title="Three-Phase Wealth Trajectory",
        xaxis_title="Year",
        yaxis=dict(
            type="log",
            title="Value ($)",
            tickvals=[1e5, 3e5, 1e6, 3e6, 1e7, 3e7, 1e8, 3e8],
            ticktext=["$100K", "$300K", "$1M", "$3M", "$10M", "$30M", "$100M", "$300M"],
        ),
        height=560,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0.5, xanchor="center"),
    ))
    st.plotly_chart(fig, use_container_width=True)

    # ── Phase Summary Cards ────────────────────────────────────────────────────
    st.subheader("📐 Phase Breakdown")

    # LP doubling note for phase 1
    lp_note = ""
    if lp_double_years > 0 and lp_double_years < (w2_ret_age - age):
        lp_note = (f"LP doubles + gift ends at yr {lp_double_years} → "
                   f"passive rises to ${passive_post_lp:,.0f}/mo")

    ph1, ph2, ph3 = st.columns(3)

    with ph1:
        _phase_card(
            color_hex="#3b82f6",
            title_html=f"Phase 1 &nbsp;·&nbsp; Working<br>Age {age} – {w2_ret_age}",
            value_str=f"+${p1_flow_today:,.0f}/mo",
            value_color=GREEN,
            subtitle="wealth-building rate (today's $)",
            breakdown=(
                f"W2 &nbsp;${w2_take_home:,.0f} "
                f"+ Passive &nbsp;${passive_today:,.0f} "
                f"+ Match &nbsp;${match_today:,.0f} "
                f"+ Bonus &nbsp;${bonus_annual/12:,.0f} "
                f"− Costs &nbsp;${operating_costs:,.0f}"
                + (f"<br><span style='color:#06b6d4'>{lp_note}</span>" if lp_note else "")
            ),
        )

    with ph2:
        p2_color  = GREEN if p2_flow_today >= 0 else AMBER
        p2_prefix = "+" if p2_flow_today >= 0 else "−"
        p2_str    = f"{p2_prefix}${abs(p2_flow_today):,.0f}/mo"
        p2_pct    = passive_post_lp / burn_mo * 100 if burn_mo else 0
        _phase_card(
            color_hex="#f59e0b",
            title_html=f"Phase 2 &nbsp;·&nbsp; Passive Only<br>Age {w2_ret_age} – {ss_age}",
            value_str=p2_str,
            value_color=p2_color,
            subtitle="net monthly flow (today's $)",
            breakdown=(
                f"LP (2×) &nbsp;${passive_post_lp:,.0f} "
                f"− Burn (no mortgage) &nbsp;${burn_mo:,.0f} "
                f"· {p2_pct:.0f}% covered"
            ),
        )

    with ph3:
        p3_prefix = "+" if p3_flow_today >= 0 else "−"
        p3_str    = f"{p3_prefix}${abs(p3_flow_today):,.0f}/mo"
        p3_color  = GREEN if p3_flow_today >= 0 else RED
        p3_pct    = (passive_post_lp + ss_monthly) / burn_mo * 100 if burn_mo else 0
        _phase_card(
            color_hex="#10b981",
            title_html=f"Phase 3 &nbsp;·&nbsp; SS Active<br>Age {ss_age}+",
            value_str=p3_str,
            value_color=p3_color,
            subtitle="net monthly surplus (today's $)",
            breakdown=(
                f"LP (2×) &nbsp;${passive_post_lp:,.0f} "
                f"+ SS &nbsp;${ss_monthly:,.0f} "
                f"− Burn (no mortgage) &nbsp;${burn_mo:,.0f} "
                f"· {p3_pct:.0f}% covered"
            ),
        )

    st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)

    # ── Retirement Readiness ───────────────────────────────────────────────────
    st.subheader("🎯 Retirement Readiness")

    port_at_w2  = base_inv[min(w2_stop_mo, len(base_inv) - 1)]
    port_at_ret = base_inv[min(ret_mo,     len(base_inv) - 1)]
    safe_wd     = port_at_ret * 0.04 / 12

    yrs_to_ret       = ret_age - age
    infl_ret         = (1 + a.get("inflation_pct", 3) / 100) ** yrs_to_ret
    inflated_burn    = burn_mo * infl_ret
    passive_at_ret   = passive_post_lp * infl_ret   # LP already doubled by retirement
    ss_at_ret        = ss_monthly * infl_ret if ret_age >= ss_age else 0
    total_ret_income = passive_at_ret + ss_at_ret + safe_wd
    monthly_gap      = total_ret_income - inflated_burn
    p3_coverage      = (passive_post_lp + ss_monthly) / burn_mo * 100 if burn_mo else 0

    rc1, rc2, rc3, rc4 = st.columns(4)
    rc1.metric(f"Portfolio at W2 Retirement (Age {w2_ret_age})", f"${port_at_w2:,.0f}")
    rc2.metric(f"Portfolio at Formal Retirement (Age {ret_age})", f"${port_at_ret:,.0f}")
    rc3.metric(f"4% Safe Withdrawal at Age {ret_age}",            f"${safe_wd:,.0f}/mo")
    rc4.metric("LP (2×) + SS Coverage (Phase 3)",                f"{p3_coverage:.0f}%",
               delta="Self-sustaining ✅" if p3_coverage >= 100 else "Portfolio tops up gap",
               delta_color="normal" if p3_coverage >= 100 else "off")

    st.divider()

    exp_col, gap_col = st.columns(2)
    exp_col.metric(
        f"Monthly Expenses at Age {ret_age} (inflation-adjusted)",
        f"${inflated_burn:,.0f}",
        delta=f"Based on ${burn_mo:,.0f}/mo today × {infl_ret:.2f}× inflation ({yrs_to_ret} yrs)",
        delta_color="off",
    )
    gap_col.metric(
        f"Monthly Surplus at Age {ret_age} (all income sources)",
        f"${monthly_gap:,.0f}",
        delta="On track ✅" if monthly_gap >= 0 else "Minor shortfall ⚠️",
        delta_color="normal" if monthly_gap >= 0 else "inverse",
    )

    if p3_coverage >= 100:
        st.success(
            f"✅ Doubled LP income + Social Security covers **{p3_coverage:.0f}%** of the "
            f"${burn_mo:,.0f}/mo retirement burn in today's dollars — "
            f"the investment portfolio is **bonus wealth**, not a survival requirement."
        )
    elif p3_coverage >= 80:
        gap_income = (burn_mo - passive_post_lp - ss_monthly) * 12 / 0.04
        st.info(
            f"📊 LP (2×) + SS covers **{p3_coverage:.0f}%** of retirement burn. "
            f"You'd need ~${gap_income:,.0f} in portfolio to close the gap — "
            f"your projection shows this achieved well before retirement."
        )
    else:
        gap_income = (burn_mo - passive_post_lp - ss_monthly) * 12 / 0.04
        st.warning(
            f"⚠️ LP (2×) + SS covers **{p3_coverage:.0f}%** of retirement burn. "
            f"You'd need ~${gap_income:,.0f} more in portfolio at retirement to fully close the gap."
        )

    # ── Key Assumptions ───────────────────────────────────────────────────────
    with st.expander("📋 Projection Assumptions", expanded=False):
        ac1, ac2, ac3 = st.columns(3)
        ac1.markdown(f"""
**Income**
- W2 take-home: ${w2_take_home:,.0f}/mo
- W2 raise rate: {a.get('income_growth_pct', 3):.1f}%/yr
- Q1 Bonus: ${bonus_annual:,.0f}/yr
- Employer match: ${match_today:,.0f}/mo (${match_today*12:,.0f}/yr)
""")
        ac2.markdown(f"""
**Passive Income**
- LP gross: ${lp_monthly:,.0f}/mo · Net: ${lp_monthly_net:,.0f}/mo ({lp_net_pct_val:.0f}% after partial-shelter tax)
- LP doubles in: {lp_double_years} yr{' (yr ' + str(today.year + lp_double_years) + ')' if lp_double_years > 0 else ' (not modeled)'}
- LP post-event (net): ${passive_post_lp:,.0f}/mo
- Family gift: ${gift_monthly:,.0f}/mo → $0 after LP event
- Mortgage free: yr {payoff_date.year} (age {int(payoff_age)}) with 1 extra payment/yr
""")
        ac3.markdown(f"""
**Projection rates**
- Investment return: {base_rate:.1f}%/yr
- Inflation: {a.get('inflation_pct', 3):.1f}%/yr
- Retirement burn: ${burn_mo:,.0f}/mo (post-payoff, no mortgage P&I)
- Social Security: ${ss_monthly:,.0f}/mo at age {ss_age}
""")

    # ── Milestones Table ───────────────────────────────────────────────────────
    st.subheader("📅 Financial Milestones")
    milestones = []
    for m in range(0, total_months + 1, 12):
        yr     = today.year + m // 12
        age_at = age + m // 12
        note   = ""
        if lp_double_years > 0 and m == lp_double_month:
            note = "← LP income doubles, gift ends"
        elif yr == payoff_date.year:
            note = "← Mortgage paid off 🏠"
        elif m == w2_stop_mo:
            note = "← W2 income ends"
        elif m == ret_mo:
            note = "← Formal retirement"
        elif m == ss_start_mo:
            note = "← Social Security begins"
        milestones.append({
            "Year":            yr,
            "Age":             age_at,
            "Portfolio ($)":   round(base_inv[m]),
            "Home Equity ($)": round(equity_values[m]),
            "Net Worth ($)":   round(nw_values[m]),
            "Note":            note,
        })

    mile_df = pd.DataFrame(milestones)
    st.dataframe(
        mile_df.style.format({
            "Portfolio ($)":   "${:,.0f}",
            "Home Equity ($)": "${:,.0f}",
            "Net Worth ($)":   "${:,.0f}",
        }),
        use_container_width=True, hide_index=True,
    )

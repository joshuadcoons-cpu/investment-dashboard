import streamlit as st
import copy
import yfinance as yf
from datetime import date
from utils.defaults import DEFAULT_ASSUMPTIONS
from utils.calculations import (
    ACCOUNT_LIMITS, calc_federal_tax, calc_fica, calc_take_home_monthly,
    calc_monthly_payment, build_amortization, get_loan_status,
)
from utils.styles import BLUE, GREEN, RED, PURPLE, AMBER, CYAN, theme_colors

SECTORS = [
    "Technology", "Healthcare", "Financials", "Consumer Cyclical",
    "Consumer Defensive", "Industrials", "Communication Services",
    "Energy", "Utilities", "Real Estate", "Materials", "Unknown",
]

# All static widget keys — cleared on Reset Defaults so widgets reinitialise from defaults
_STATIC_KEYS = [
    "dashboard_name", "age", "retirement_age", "filing_status",
    "gross_income", "state_tax_pct", "spouse_gross_income", "income_growth_pct",
    "take_home_monthly_override", "spouse_take_home_monthly_override",
    "override_take_home", "override_spouse_take_home",
    "home_current_value", "home_appreciation_pct",
    "loan_original_amount", "loan_interest_rate", "loan_term_years", "loan_start_date",
    "property_tax_rate", "home_insurance_annual", "hoa_monthly", "maintenance_pct",
    "emergency_fund_balance", "emergency_fund_target_months", "checking_savings_balance",
    "investment_return_pct", "inflation_pct",
    "social_security_monthly", "social_security_start_age", "retirement_monthly_expenses",
]


@st.cache_data(ttl=3600)
def _fetch_sector(ticker: str) -> str:
    try:
        info = yf.Ticker(ticker).info
        return info.get("sector", "Unknown") or "Unknown"
    except Exception:
        return "Unknown"


def _fmt_k(v):
    """Format dollar values compactly: $1.2M, $350k, $0."""
    if v >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    if v >= 1_000:
        return f"${v / 1_000:.0f}k"
    return f"${v:,.0f}"


def render():
    a = st.session_state.assumptions
    tc = theme_colors()

    # ── Header row with reset button ─────────────────────────────────────────
    hdr_l, hdr_r = st.columns([5, 1])
    hdr_l.markdown(
        '<p class="section-header" style="margin-bottom:0.2rem">'
        'Setup & Assumptions</p>',
        unsafe_allow_html=True,
    )
    if hdr_r.button("↩️ Reset Defaults"):
        st.session_state.assumptions = copy.deepcopy(DEFAULT_ASSUMPTIONS)
        st.session_state.ui_ver = st.session_state.get("ui_ver", 0) + 1
        for k in _STATIC_KEYS:
            st.session_state.pop(k, None)
        for cat in DEFAULT_ASSUMPTIONS["budget"]:
            st.session_state.pop(f"bgt_{cat}", None)
        st.rerun()

    # ── Quick-glance summary ──────────────────────────────────────────────────
    total_inv = sum(acct["balance"] for acct in a["investment_accounts"])
    total_contrib = sum(acct["monthly_contribution"] for acct in a["investment_accounts"])
    monthly_budget = sum(a["budget"].values())
    monthly_pi = calc_monthly_payment(
        a["loan_original_amount"], a["loan_interest_rate"], a["loan_term_years"])
    monthly_tax_h = a["home_current_value"] * a["property_tax_rate"] / 100 / 12
    monthly_ins = a["home_insurance_annual"] / 12
    total_housing = monthly_pi + monthly_tax_h + monthly_ins + a["hoa_monthly"]
    total_take_home = a["take_home_monthly"] + a.get("spouse_take_home_monthly", 0)
    hh_income = a["gross_income"] + a.get("spouse_gross_income", 0)

    # Home equity
    amort = build_amortization(
        a["loan_original_amount"], a["loan_interest_rate"],
        a["loan_term_years"], a["loan_start_date"])
    status = get_loan_status(amort, date.today())
    home_equity = max(a["home_current_value"] - status["current_balance"], 0)

    # Liquid capital
    sinking = a.get("sinking_fund_balance", 0)
    liquid = a["emergency_fund_balance"] + a["checking_savings_balance"] + sinking

    # Passive income
    passive_mo = a.get("parkwood_lp_monthly", 0) + a.get("family_gift_annual", 0) / 12

    # Debt payments
    total_debt_pmts = sum(d["monthly_payment"] for d in a["other_debts"])

    # Savings rate
    total_out = total_housing + total_debt_pmts + monthly_budget + total_contrib
    net_cf = total_take_home + passive_mo - total_out + total_contrib  # add back contrib
    savings_rate = ((total_contrib + max(net_cf - total_contrib, 0))
                    / (total_take_home + passive_mo) * 100
                    if (total_take_home + passive_mo) else 0)

    def _kpi(col, label, value, color, sub=None):
        sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
        col.markdown(
            f'<div class="kpi-card" style="border-top:3px solid {color};padding:0.8rem 1rem">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value" style="font-size:1.5rem">{value}</div>'
            f'{sub_html}</div>',
            unsafe_allow_html=True,
        )

    # Row 1
    r1 = st.columns(4)
    _kpi(r1[0], "Age / Retire",     f"{int(a['age'])} → {int(a['retirement_age'])}", BLUE,
         f"{int(a['retirement_age']) - int(a['age'])} years to go")
    _kpi(r1[1], "Household Income", f"${hh_income:,.0f}",   GREEN,
         f"${total_take_home:,.0f}/mo take-home")
    _kpi(r1[2], "Home Equity",      _fmt_k(home_equity),     PURPLE,
         f"LTV {status['current_balance'] / a['home_current_value'] * 100:.0f}%"
         if a["home_current_value"] else None)
    _kpi(r1[3], "Portfolio",        _fmt_k(total_inv),        CYAN,
         f"${total_contrib:,.0f}/mo contributions")

    # Row 2
    st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)
    r2 = st.columns(4)
    _kpi(r2[0], "Passive Income",   f"${passive_mo:,.0f}/mo" if passive_mo else "$0",
         AMBER,  f"${passive_mo * 12:,.0f}/yr" if passive_mo else "Not configured")
    _kpi(r2[1], "Liquid Capital",   _fmt_k(liquid),           BLUE,
         f"HYSA + Checking + Sinking")
    sr_color = GREEN if savings_rate >= 20 else (AMBER if savings_rate >= 10 else RED)
    _kpi(r2[2], "Savings Rate",     f"{savings_rate:.1f}%",   sr_color,
         f"${total_contrib:,.0f}/mo invested")
    _kpi(r2[3], "Monthly Expenses", f"${total_housing + monthly_budget + total_debt_pmts:,.0f}",
         RED,    f"Housing + Budget + Debt")

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
    v = st.session_state.get("ui_ver", 0)

    # Helper: colored section accent bar before each expander
    def _section_accent(color):
        st.markdown(
            f'<div style="height:3px;background:linear-gradient(90deg,{color},{color}00);'
            f'border-radius:2px;margin:0.8rem 0 -0.3rem 0;width:80px"></div>',
            unsafe_allow_html=True,
        )

    # ── Personal ──────────────────────────────────────────────────────────────
    _section_accent(BLUE)
    with st.expander("👤 Personal Information", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        a["dashboard_name"] = c1.text_input(
            "Dashboard Label", a["dashboard_name"], key="dashboard_name")
        a["age"] = c2.number_input(
            "Your Age", 18, 85, int(a["age"]), key="age")
        a["retirement_age"] = c3.number_input(
            "Target Retirement Age", 45, 85, int(a["retirement_age"]), key="retirement_age")
        a["filing_status"] = c4.selectbox(
            "Filing Status",
            ["Single", "Married Filing Jointly", "Married Filing Separately", "Head of Household"],
            index=["Single", "Married Filing Jointly", "Married Filing Separately",
                   "Head of Household"].index(a["filing_status"]),
            key="filing_status",
        )

    # ── Income ────────────────────────────────────────────────────────────────
    _section_accent(GREEN)
    with st.expander("💵 Income", expanded=True):
        c1, c2, c3 = st.columns(3)
        a["gross_income"] = c1.number_input(
            "Your Gross Annual Income ($)", 0, 2_000_000, int(a["gross_income"]),
            step=1_000, key="gross_income")
        a["state_tax_pct"] = c2.number_input(
            "State Income Tax Rate (%)", 0.0, 15.0, float(a.get("state_tax_pct", 5.0)),
            step=0.25, format="%.2f", key="state_tax_pct",
            help="Your state's marginal rate. 0% in TX/FL/NV, ~5% national avg, ~13% in CA.")
        a["income_growth_pct"] = c3.slider(
            "Expected Annual Income Growth (%)", 0.0, 10.0,
            float(a["income_growth_pct"]), 0.5, key="income_growth_pct")

        # ── Auto-calculated take-home ──────────────────────────────────────
        state_pct = float(a.get("state_tax_pct", 5.0))
        take_home_calc = calc_take_home_monthly(a["gross_income"], a["filing_status"], state_pct)

        override = st.checkbox(
            "Override take-home manually",
            value=st.session_state.get("override_take_home", False),
            key="override_take_home",
            help="Check if your actual take-home differs (pre-tax benefits, extra withholding, etc.)")

        if override:
            a["take_home_monthly"] = st.number_input(
                "Your Monthly Take-Home ($)", 0, 200_000,
                int(a["take_home_monthly"]), step=100, key="take_home_monthly_override")
        else:
            a["take_home_monthly"] = round(take_home_calc)
            m1, m2, m3 = st.columns(3)
            m1.metric("Est. Monthly Take-Home", f"${take_home_calc:,.0f}")
            annual_tax = a["gross_income"] - take_home_calc * 12
            eff_rate = annual_tax / a["gross_income"] * 100 if a["gross_income"] > 0 else 0.0
            m2.metric("Effective Total Tax Rate", f"{eff_rate:.1f}%",
                      help="Federal + FICA + state combined")
            m3.metric("Annual Net Pay", f"${take_home_calc * 12:,.0f}")

        # ── Spouse / Partner Income ────────────────────────────────────────
        is_married = a["filing_status"] in ["Married Filing Jointly", "Married Filing Separately"]
        show_spouse = is_married or a.get("spouse_gross_income", 0) > 0
        if show_spouse:
            st.markdown("---")
            st.markdown("**Spouse / Partner Income**")
            s1, s2 = st.columns(2)
            a["spouse_gross_income"] = s1.number_input(
                "Spouse Gross Annual Income ($)", 0, 2_000_000,
                int(a.get("spouse_gross_income", 0)), step=1_000, key="spouse_gross_income")

            spouse_take_home_calc = calc_take_home_monthly(
                a["spouse_gross_income"], a["filing_status"], state_pct)

            spouse_override = st.checkbox(
                "Override spouse take-home manually",
                value=st.session_state.get("override_spouse_take_home", False),
                key="override_spouse_take_home")
            if spouse_override:
                a["spouse_take_home_monthly"] = s2.number_input(
                    "Spouse Monthly Take-Home ($)", 0, 200_000,
                    int(a.get("spouse_take_home_monthly", 0)),
                    step=100, key="spouse_take_home_monthly_override")
            else:
                a["spouse_take_home_monthly"] = round(spouse_take_home_calc)
                s2.metric("Est. Spouse Monthly Take-Home", f"${spouse_take_home_calc:,.0f}")

            if is_married:
                st.caption(
                    "MFJ tax is estimated per-person using MFJ brackets. "
                    "Actual withholding may differ — use the override if needed.")
        else:
            a["spouse_gross_income"] = 0
            a["spouse_take_home_monthly"] = 0

    # ── Home ──────────────────────────────────────────────────────────────────
    _section_accent(PURPLE)
    with st.expander("🏡 Home & Mortgage", expanded=False):
        c1, c2 = st.columns(2)
        a["home_current_value"] = c1.number_input(
            "Current Home Value ($)", 0, 5_000_000, int(a["home_current_value"]),
            step=5_000, key="home_current_value")
        a["home_appreciation_pct"] = c2.slider(
            "Expected Home Appreciation (%/yr)", 0.0, 10.0,
            float(a["home_appreciation_pct"]), 0.25, key="home_appreciation_pct")

        st.markdown("**Mortgage**")
        m1, m2, m3, m4 = st.columns(4)
        a["loan_original_amount"] = m1.number_input(
            "Original Loan Amount ($)", 0, 5_000_000, int(a["loan_original_amount"]),
            step=5_000, key="loan_original_amount")
        a["loan_interest_rate"] = m2.number_input(
            "Interest Rate (%)", 0.0, 20.0, float(a["loan_interest_rate"]),
            step=0.05, format="%.2f", key="loan_interest_rate")
        a["loan_term_years"] = m3.selectbox(
            "Loan Term (years)", [10, 15, 20, 25, 30],
            index=[10, 15, 20, 25, 30].index(int(a["loan_term_years"])),
            key="loan_term_years")
        a["loan_start_date"] = m4.date_input(
            "Loan Start Date", a["loan_start_date"], key="loan_start_date")

        st.markdown("**Other Housing Costs**")
        h1, h2, h3, h4 = st.columns(4)
        a["property_tax_rate"] = h1.number_input(
            "Property Tax Rate (%/yr)", 0.0, 5.0, float(a["property_tax_rate"]),
            step=0.05, format="%.2f", key="property_tax_rate")
        a["home_insurance_annual"] = h2.number_input(
            "Home Insurance ($/yr)", 0, 20_000, int(a["home_insurance_annual"]),
            step=50, key="home_insurance_annual")
        a["hoa_monthly"] = h3.number_input(
            "HOA ($/mo)", 0, 5_000, int(a["hoa_monthly"]),
            step=25, key="hoa_monthly")
        a["maintenance_pct"] = h4.number_input(
            "Maintenance Budget (%/yr of value)", 0.0, 5.0, float(a["maintenance_pct"]),
            step=0.1, format="%.1f", key="maintenance_pct")

    # ── Savings & Cash ────────────────────────────────────────────────────────
    _section_accent(BLUE)
    with st.expander("🛡️ Emergency Fund & Cash", expanded=False):
        e1, e2, e3 = st.columns(3)
        a["emergency_fund_balance"] = e1.number_input(
            "Emergency Fund Balance ($)", 0, 500_000, int(a["emergency_fund_balance"]),
            step=500, key="emergency_fund_balance")
        a["emergency_fund_target_months"] = e2.selectbox(
            "Target Coverage (months)", [3, 6, 9, 12],
            index=[3, 6, 9, 12].index(int(a["emergency_fund_target_months"])),
            key="emergency_fund_target_months")
        a["checking_savings_balance"] = e3.number_input(
            "Checking / Savings Balance ($)", 0, 1_000_000, int(a["checking_savings_balance"]),
            step=500, key="checking_savings_balance")

    # ── Other Debts ───────────────────────────────────────────────────────────
    _section_accent(RED)
    with st.expander("💳 Other Debts", expanded=False):
        debts = a["other_debts"]
        if not debts:
            st.caption("No debts added. Use the button below to add one.")
        for i, debt in enumerate(debts):
            dc1, dc2, dc3, dc4, dc5 = st.columns([3, 2, 2, 2, 1])
            debt["name"] = dc1.text_input("Name", debt["name"], key=f"dn_{i}_v{v}")
            debt["balance"] = dc2.number_input(
                "Balance ($)", 0, 1_000_000, int(debt["balance"]), step=100, key=f"db_{i}_v{v}")
            debt["rate_pct"] = dc3.number_input(
                "Rate (%)", 0.0, 30.0, float(debt["rate_pct"]), step=0.1, key=f"dr_{i}_v{v}")
            debt["monthly_payment"] = dc4.number_input(
                "Monthly Pmt ($)", 0, 10_000, int(debt["monthly_payment"]),
                step=25, key=f"dp_{i}_v{v}")
            if dc5.button("🗑️", key=f"dd_{i}_v{v}"):
                debts.pop(i)
                st.session_state.ui_ver = v + 1
                st.rerun()

        if st.button("➕ Add Debt"):
            debts.append({"name": "New Debt", "balance": 10_000,
                          "rate_pct": 5.0, "monthly_payment": 200})
            st.session_state.ui_ver = v + 1
            st.rerun()

    # ── Investment Accounts ───────────────────────────────────────────────────
    _section_accent(CYAN)
    with st.expander("📈 Investment Accounts", expanded=True):
        accounts = a["investment_accounts"]
        account_types = ["401k", "Roth 401k", "Trad IRA", "Roth IRA", "Brokerage", "HSA", "Crypto"]

        # ── IRS Contribution Tracker (per account type) ─────────────────
        cur_year = date.today().year
        age = int(a["age"])
        _today = date.today()
        _months_elapsed = (_today - date(_today.year, 1, 1)).days / 365 * 12

        # Group accounts by their shared IRS limit bucket
        # 401k + Roth 401k share one limit per employee
        # Trad IRA + Roth IRA share one limit PER PERSON (spouse gets own limit)
        # HSA separate
        # Skip accounts flagged with skip_contribution (e.g. rollovers)
        _is_spouse = lambda acct: any(tag in acct.get("label", "")
                                      for tag in ("Athena", "Wife", "Spouse"))
        _buckets = {}
        for acct in accounts:
            if acct.get("skip_contribution"):
                continue
            at = acct["account_type"]
            if at in ("401k", "Roth 401k"):
                bucket = "401k / Roth 401k"
            elif at in ("Trad IRA", "Roth IRA"):
                # Per-person IRA limit
                bucket = ("Spouse IRA" if _is_spouse(acct) else "Your IRA")
            elif at == "HSA":
                bucket = "HSA"
            else:
                continue  # Brokerage, Crypto — no IRS limit
            _buckets.setdefault(bucket, []).append(acct)

        if _buckets:
            st.caption(f"**{cur_year} IRS Contribution Limits**")
            for bucket_name, bucket_accts in _buckets.items():
                # Determine limit for this bucket
                sample_type = bucket_accts[0]["account_type"]
                limits = ACCOUNT_LIMITS.get(sample_type, {})
                catchup_age = 55 if sample_type == "HSA" else 50
                annual_limit = limits.get("catchup" if age >= catchup_age else "base")
                if not annual_limit:
                    continue

                # Use ytd_contributed if set, else estimate from monthly * months elapsed
                combined_ytd = sum(
                    acct.get("ytd_contributed",
                             acct["monthly_contribution"] * _months_elapsed)
                    for acct in bucket_accts
                )
                room = max(0, annual_limit - combined_ytd)
                pct_used = min(combined_ytd / annual_limit * 100, 100)
                over = combined_ytd > annual_limit

                bar_color = GREEN if room < 1 else (AMBER if pct_used >= 80 else BLUE)
                if over:
                    bar_color = RED

                # Compact row: label | progress bar | status
                lc, rc = st.columns([1, 3])
                if over:
                    lc.markdown(
                        f'<div style="padding-top:4px;font-size:0.85rem;font-weight:600;'
                        f'color:{RED}">{bucket_name}</div>',
                        unsafe_allow_html=True)
                elif room < 1:
                    lc.markdown(
                        f'<div style="padding-top:4px;font-size:0.85rem;font-weight:600;'
                        f'color:{GREEN}">{bucket_name}</div>',
                        unsafe_allow_html=True)
                else:
                    lc.markdown(
                        f'<div style="padding-top:4px;font-size:0.85rem;font-weight:600;'
                        f'color:{tc["text"]}">{bucket_name}</div>',
                        unsafe_allow_html=True)

                status_text = ("Over limit!" if over
                               else ("Maxed!" if room < 1
                                     else f"${room:,.0f} room"))
                rc.markdown(
                    f'<div style="margin-top:4px">'
                    f'<div style="display:flex;justify-content:space-between;'
                    f'color:{tc["muted"]};font-size:0.75rem;margin-bottom:3px">'
                    f'<span>${combined_ytd:,.0f} / ${annual_limit:,.0f} YTD</span>'
                    f'<span style="color:{bar_color};font-weight:600">{status_text}</span>'
                    f'</div>'
                    f'<div style="background:{tc["card"]};border-radius:4px;height:8px;overflow:hidden">'
                    f'<div style="background:{bar_color};width:{min(pct_used, 100):.1f}%;'
                    f'height:8px;border-radius:4px"></div></div></div>',
                    unsafe_allow_html=True,
                )

                # Show per-account breakdown if multiple accounts share a bucket
                if len(bucket_accts) > 1:
                    for ac in bucket_accts:
                        ac_ytd = ac.get("ytd_contributed",
                                        ac["monthly_contribution"] * _months_elapsed)
                        if ac_ytd > 0 or ac["monthly_contribution"] > 0:
                            st.caption(
                                f"  • **{ac['label']}** ({ac['account_type']}): "
                                f"${ac_ytd:,.0f} YTD  (${ac['monthly_contribution']:,.0f}/mo)")

            st.markdown("---")

        # ── Account cards ─────────────────────────────────────────────────
        for i, acct in enumerate(accounts):
            aid = acct.get("_id", i)
            acct_color = {
                "401k": BLUE, "Roth 401k": PURPLE, "Trad IRA": AMBER,
                "Roth IRA": GREEN, "Brokerage": CYAN, "HSA": "#f97316", "Crypto": AMBER,
            }.get(acct.get("account_type", ""), tc["subtle"])

            with st.container(border=True):
                # Header row: label + type badge + balance + remove
                top1, top2, top3 = st.columns([4, 1.5, 0.5])
                acct["label"] = top1.text_input(
                    "Label", acct.get("label", ""), key=f"al_{aid}_v{v}",
                    label_visibility="collapsed")
                top1.markdown(
                    f'<span style="background:{acct_color}22;color:{acct_color};'
                    f'padding:2px 10px;border-radius:9999px;font-size:0.7rem;'
                    f'font-weight:700;letter-spacing:.4px">'
                    f'{acct.get("account_type", "")}</span>',
                    unsafe_allow_html=True,
                )
                top2.metric("Balance", _fmt_k(acct["balance"]))
                if top3.button("🗑️", key=f"ra_{aid}_v{v}"):
                    accounts.pop(i)
                    st.session_state.ui_ver = v + 1
                    st.rerun()

                # Core fields
                ac1, ac2, ac3, ac4 = st.columns(4)
                acct["account_type"] = ac1.selectbox(
                    "Type", account_types,
                    index=account_types.index(acct.get("account_type", "Brokerage")),
                    key=f"at_{aid}_v{v}")
                acct["balance"] = ac2.number_input(
                    "Current Balance ($)", 0, 10_000_000, int(acct["balance"]),
                    step=500, key=f"ab_{aid}_v{v}")
                acct["monthly_contribution"] = ac3.number_input(
                    "Monthly Contribution ($)", 0, 20_000, int(acct["monthly_contribution"]),
                    step=50, key=f"ac_{aid}_v{v}")

                # YTD contributed (for accounts with IRS limits)
                has_limit = acct["account_type"] in [
                    "401k", "Roth 401k", "Trad IRA", "Roth IRA", "HSA"]
                if has_limit and not acct.get("skip_contribution"):
                    ytd_val = acct.get("ytd_contributed")
                    # Default: estimate from monthly * months elapsed
                    if ytd_val is None:
                        ytd_val = round(acct["monthly_contribution"] * _months_elapsed)
                    acct["ytd_contributed"] = ac4.number_input(
                        "YTD Contributed ($)", 0, 100_000, int(ytd_val),
                        step=100, key=f"ytd_{aid}_v{v}",
                        help="Actual contributions so far this year")

                # Cash in account
                if not has_limit or acct.get("account_type") in ("Brokerage",):
                    acct["cash_usd"] = ac4.number_input(
                        "Cash in Account ($)", 0, 10_000_000,
                        int(acct.get("cash_usd", 0)),
                        step=100, key=f"cash_{aid}_v{v}")

                # Employer match (only for 401k types)
                if acct["account_type"] in ["401k", "Roth 401k"]:
                    mc1, mc2, _, _ = st.columns(4)
                    acct["employer_match_pct"] = mc1.number_input(
                        "Employer Match %", 0, 100, int(acct.get("employer_match_pct", 0)),
                        step=5, key=f"em_{aid}_v{v}")
                    acct["employer_match_ceiling_pct"] = mc2.number_input(
                        "Match up to % of salary", 0, 25,
                        int(acct.get("employer_match_ceiling_pct", 0)),
                        step=1, key=f"ec_{aid}_v{v}")
                else:
                    acct["employer_match_pct"] = 0
                    acct["employer_match_ceiling_pct"] = 0

                # Holdings sub-section
                holdings = acct.setdefault("holdings", [])
                n_holdings = len(holdings)
                with st.expander(
                    f"Holdings ({n_holdings} ticker{'s' if n_holdings != 1 else ''})",
                    expanded=False,
                ):
                    if holdings:
                        for j, h in enumerate(holdings):
                            hc1, hc2, hc3, hc4, hc5 = st.columns([2, 1.5, 1.5, 2.5, 0.5])
                            h["ticker"] = hc1.text_input(
                                "Ticker", h.get("ticker") or "",
                                key=f"ht_{aid}_{j}_v{v}").upper().strip() or None
                            h["shares"] = hc2.number_input(
                                "Shares", 0.0, 1e7, float(h.get("shares", 0)),
                                step=0.01, format="%.4f", key=f"hs_{aid}_{j}_v{v}")
                            h["avg_cost"] = hc3.number_input(
                                "Avg Cost", 0.0, 1e6,
                                float(h.get("avg_cost", 0) or 0),
                                step=0.01, format="%.4f", key=f"hcb_{aid}_{j}_v{v}") or None
                            sec_idx = (SECTORS.index(h.get("sector", "Unknown"))
                                       if h.get("sector", "Unknown") in SECTORS
                                       else len(SECTORS) - 1)
                            h["sector"] = hc4.selectbox(
                                "Sector", SECTORS, index=sec_idx, key=f"hsc_{aid}_{j}_v{v}")
                            if hc5.button("🗑️", key=f"hd_{aid}_{j}_v{v}"):
                                holdings.pop(j)
                                st.session_state.ui_ver = v + 1
                                st.rerun()

                    st.caption("**Add holding:**")
                    na1, na2, na3, na4, na5 = st.columns([2, 1.5, 1.5, 2.5, 0.5])
                    nt = na1.text_input("Ticker", key=f"nt_{aid}_v{v}").upper().strip()
                    ns = na2.number_input("Shares", 0.0, 1e7, 0.0,
                                          step=0.01, format="%.4f", key=f"ns_{aid}_v{v}")
                    ncb = na3.number_input("Avg Cost", 0.0, 1e6, 0.0,
                                           step=0.01, format="%.4f", key=f"ncb_{aid}_v{v}")
                    nsc = na4.selectbox("Sector", SECTORS, index=0, key=f"nsc_{aid}_v{v}")
                    if na5.button("➕", key=f"ah_{aid}_v{v}") and nt:
                        next_hid = max((h.get("_id", 0) for h in holdings), default=-1) + 1
                        holdings.append({"ticker": nt, "shares": ns, "sector": nsc,
                                         "avg_cost": ncb or None, "_id": next_hid})
                        st.session_state.ui_ver = v + 1
                        st.rerun()

                    if nt:
                        if st.button(f"Auto-detect sector for {nt}", key=f"ads_{aid}_v{v}"):
                            detected = _fetch_sector(nt)
                            st.info(f"Detected sector for {nt}: **{detected}**")

        if st.button("➕ Add Investment Account"):
            next_id = max((acct.get("_id", 0) for acct in accounts), default=-1) + 1
            accounts.append({
                "account_type": "Brokerage", "label": "New Account",
                "balance": 0, "monthly_contribution": 0,
                "employer_match_pct": 0, "employer_match_ceiling_pct": 0,
                "cash_usd": 0, "_id": next_id, "holdings": [],
            })
            st.session_state.ui_ver = v + 1
            st.rerun()

    # ── Monthly Budget ────────────────────────────────────────────────────────
    _section_accent(AMBER)
    with st.expander("📋 Monthly Budget Categories", expanded=False):
        budget = a["budget"]
        cats = list(budget.keys())
        total_bgt = sum(budget.values())
        st.caption(f"Total: **${total_bgt:,.0f}/mo** · ${total_bgt * 12:,.0f}/yr")

        cols = st.columns(3)
        for idx, cat in enumerate(cats):
            budget[cat] = cols[idx % 3].number_input(
                cat, 0, 20_000, int(budget[cat]), step=25, key=f"bgt_{cat}")

        st.markdown("---")
        nc1, nc2, nc3 = st.columns([3, 2, 1])
        new_name = nc1.text_input("New category name", key="new_cat_name")
        new_amt = nc2.number_input("Monthly amount ($)", 0, 20_000, 0,
                                   step=25, key="new_cat_amt")
        if nc3.button("Add") and new_name and new_name not in budget:
            budget[new_name] = new_amt
            st.rerun()

    # ── Projection Assumptions ────────────────────────────────────────────────
    _section_accent(PURPLE)
    with st.expander("🔮 Projection Assumptions", expanded=False):
        p1, p2 = st.columns(2)
        a["investment_return_pct"] = p1.slider(
            "Expected Annual Investment Return (%)", 1.0, 15.0,
            float(a["investment_return_pct"]), 0.5, key="investment_return_pct")
        a["inflation_pct"] = p2.slider(
            "Expected Inflation Rate (%)", 1.0, 8.0,
            float(a["inflation_pct"]), 0.25, key="inflation_pct")

        p3, p4, p5 = st.columns(3)
        a["social_security_monthly"] = p3.number_input(
            "Est. Social Security Benefit ($/mo)", 0, 10_000,
            int(a["social_security_monthly"]), step=50, key="social_security_monthly")
        a["social_security_start_age"] = p4.selectbox(
            "SS Start Age", [62, 65, 66, 67, 70],
            index=[62, 65, 66, 67, 70].index(int(a["social_security_start_age"])),
            key="social_security_start_age")
        a["retirement_monthly_expenses"] = p5.number_input(
            "Monthly Retirement Expenses (today's $)", 0, 50_000,
            int(a["retirement_monthly_expenses"]), step=100,
            key="retirement_monthly_expenses",
            help="What you expect to spend per month in retirement, in today's dollars.")

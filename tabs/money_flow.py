import streamlit as st
import plotly.graph_objects as go
from utils.styles import BLUE, GREEN, RED, PURPLE, AMBER, CYAN, chart_layout, theme_colors
from utils.calculations import calc_take_home_monthly, calc_monthly_payment

# ── Colour palette ─────────────────────────────────────────────────────────────
_C = {
    "income":  "#10b981",   # green
    "tax":     "#ef4444",   # red
    "bank":    "#3b82f6",   # blue
    "invest":  "#8b5cf6",   # purple
    "expense": "#f43f5e",   # rose
    "crypto":  "#f59e0b",   # amber
    "match":   "#06b6d4",   # cyan — employer match (free money)
}


def _rgba(hex_color: str, alpha: float = 0.33) -> str:
    """Convert '#rrggbb' to 'rgba(r,g,b,alpha)' — Plotly Sankey links require this."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def render():
    a = st.session_state.assumptions
    tc = theme_colors()

    st.markdown('<p class="section-header">Annual Capital Flow</p>', unsafe_allow_html=True)
    st.markdown(
        f'<p style="color:{tc["faint"]};font-size:0.85rem;margin-top:-0.5rem;margin-bottom:1rem">'
        'Household income allocation, tax efficiency, and wealth-building pipeline</p>',
        unsafe_allow_html=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # INCOME SOURCES  (editable — stored in assumptions)
    # ══════════════════════════════════════════════════════════════════════════
    with st.expander("⚙️ Passive Income & Digital Asset Inputs", expanded=False):
        st.markdown("Sources not captured in Setup — feed directly into the flow map.")
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            pkw = st.number_input(
                "Parkwood LP — monthly dist. ($)",
                value=float(a.get("parkwood_lp_monthly", 0)),
                min_value=0.0, step=100.0, key="mf_parkwood",
            )
            a["parkwood_lp_monthly"] = pkw

        with c2:
            gift = st.number_input(
                "St. Clair Gift — annual ($)",
                value=float(a.get("family_gift_annual", 0)),
                min_value=0.0, step=500.0, key="mf_gift",
            )
            a["family_gift_annual"] = gift

        with c3:
            gemini = st.number_input(
                "Gemini balance ($)",
                value=float(a.get("gemini_balance", 0)),
                min_value=0.0, step=100.0, key="mf_gemini",
            )
            a["gemini_balance"] = gemini

        with c4:
            eth_mo = st.number_input(
                "Monthly ETH purchases ($)",
                value=float(a.get("crypto_eth_monthly", 0)),
                min_value=0.0, step=25.0, key="mf_eth_mo",
            )
            a["crypto_eth_monthly"] = eth_mo
            btc_mo = st.number_input(
                "Monthly BTC purchases ($)",
                value=float(a.get("crypto_btc_monthly", 0)),
                min_value=0.0, step=25.0, key="mf_btc_mo",
            )
            a["crypto_btc_monthly"] = btc_mo
            a["crypto_monthly"] = eth_mo + btc_mo

    # ══════════════════════════════════════════════════════════════════════════
    # CALCULATIONS
    # ══════════════════════════════════════════════════════════════════════════
    josh_gross_mo   = a["gross_income"] / 12
    athena_gross_mo = a.get("spouse_gross_income", 0) / 12
    pkw_mo          = a.get("parkwood_lp_monthly", 0)
    gift_mo         = a.get("family_gift_annual", 0) / 12
    eth_mo          = a.get("crypto_eth_monthly", 0)
    btc_mo          = a.get("crypto_btc_monthly", 0)
    crypto_mo       = eth_mo + btc_mo

    # After-tax take-home
    josh_th   = calc_take_home_monthly(a["gross_income"], a["filing_status"], a["state_tax_pct"])
    josh_401k = sum(ac["monthly_contribution"] for ac in a["investment_accounts"] if ac["_id"] == 0)
    josh_tax  = josh_gross_mo - josh_th
    josh_net  = josh_th - josh_401k   # cash to bank after 401k deferral

    athena_th  = calc_take_home_monthly(
        a.get("spouse_gross_income", 0), a["filing_status"], a["state_tax_pct"]
    ) if athena_gross_mo > 0 else 0
    athena_tax = athena_gross_mo - athena_th

    # ── Employer match (free money — must be tracked) ──────────────────────
    employer_match_mo = 0
    max_match_mo = 0
    for ac in a["investment_accounts"]:
        if ac["account_type"] in ("401k", "Roth 401k") and ac.get("employer_match_pct", 0) > 0:
            ceiling   = a["gross_income"] * ac["employer_match_ceiling_pct"] / 100 / 12
            matchable = min(ac["monthly_contribution"], ceiling)
            employer_match_mo += matchable * ac["employer_match_pct"] / 100
            max_match_mo      += ceiling  * ac["employer_match_pct"] / 100
    has_match = employer_match_mo > 0

    # Housing
    pi_mo  = calc_monthly_payment(
        a["loan_original_amount"], a["loan_interest_rate"], a["loan_term_years"])
    tax_mo = a["home_current_value"] * a["property_tax_rate"] / 100 / 12
    ins_mo = a["home_insurance_annual"] / 12
    mnt_mo = a["home_current_value"] * a["maintenance_pct"] / 100 / 12
    housing = pi_mo + tax_mo + ins_mo + mnt_mo

    budget_mo = sum(a["budget"].values())
    debt_mo   = sum(d["monthly_payment"] for d in a.get("other_debts", []))

    # IRA contributions
    roth_josh   = sum(ac["monthly_contribution"] for ac in a["investment_accounts"]
                      if ac["account_type"] == "Roth IRA"
                      and "Athena" not in ac["label"] and "Wife" not in ac["label"])
    roth_athena = sum(ac["monthly_contribution"] for ac in a["investment_accounts"]
                      if "Athena" in ac["label"] or "Wife" in ac["label"])

    # ── Account balance helper ─────────────────────────────────────────────
    def _bal(fragments):
        return sum(ac["balance"] for ac in a["investment_accounts"]
                   if any(f in ac["label"] for f in fragments))

    gemini_bal = a.get("gemini_balance", 0)

    # ── Cash flow routing ──────────────────────────────────────────────────
    roth_total = roth_josh + roth_athena

    # Navy Fed receives W2 net pay; if it runs short, BofA covers the deficit
    navy_out      = housing + budget_mo + debt_mo + roth_total + crypto_mo
    navy_w2_in    = josh_net + athena_th
    navy_deficit  = max(0, navy_out - navy_w2_in)
    navy_to_jb    = max(0, navy_w2_in - navy_out)

    # BofA receives all passive income; covers Navy Fed deficit, invests the rest
    bofa_in         = pkw_mo + gift_mo
    bofa_to_navyfed = min(bofa_in, navy_deficit)
    bofa_to_jb      = max(0, bofa_in - bofa_to_navyfed)

    # ══════════════════════════════════════════════════════════════════════════
    # SANKEY — 17 base nodes + optional employer match (18th)
    # ══════════════════════════════════════════════════════════════════════════
    # col 0 – sources | col 1 – deductions | col 2 – banking
    # col 3 – allocation | col 4 – destinations
    N = {
        "josh_salary":   0,   "athena_income": 1,   "parkwood": 2,   "gift": 3,   # col 0
        "taxes":         4,   "josh_401k":     5,                                   # col 1
        "navy_fed":      6,   "bofa":          7,                                   # col 2
        "housing":       8,   "expenses":      9,   "etrade": 10,   "crypto": 11,  # col 3
        "joint_brokerage": 12,                                                      # col 4
        "josh_roth": 13,   "athena_roth": 14,   "coinbase": 15,   "gemini": 16,
    }

    # Roth balance helpers
    josh_roth_bal   = sum(ac["balance"] for ac in a["investment_accounts"]
                         if ac["account_type"] == "Roth IRA"
                         and "Athena" not in ac["label"] and "Wife" not in ac["label"])
    athena_roth_bal = sum(ac["balance"] for ac in a["investment_accounts"]
                         if "Athena" in ac["label"] or "Wife" in ac["label"])

    labels = [
        # col 0 – income sources
        f"Josh W2<br><b>${josh_gross_mo*12:,.0f}/yr</b>",                          # 0
        f"Athena W2<br><b>${athena_gross_mo*12:,.0f}/yr</b>",                      # 1
        f"Parkwood LP<br><b>${pkw_mo*12:,.0f}/yr</b>",                             # 2
        f"St. Clair Gift<br><b>${gift_mo*12:,.0f}/yr</b>",                         # 3
        # col 1 – deductions
        f"Taxes & FICA<br><b>${(josh_tax+athena_tax)*12:,.0f}/yr</b>",             # 4
        f"401(k)<br><b>${_bal(['Company 401k']):,.0f} bal</b>",                     # 5
        # col 2 – banking
        f"Navy Federal<br><b>Operating Account</b>",                                # 6
        f"Bank of America<br><b>Passive Income Hub</b>",                            # 7
        # col 3 – allocation
        f"Housing<br><b>${housing*12:,.0f}/yr</b>",                                 # 8
        f"Living Expenses<br><b>${(budget_mo+debt_mo)*12:,.0f}/yr</b>",             # 9
        f"E*Trade<br><b>IRA Custodian</b>",                                         # 10
        f"Crypto<br><b>${crypto_mo*12:,.0f}/yr</b>"                                 # 11
            + (f"<br><i>${btc_mo*12:,.0f} BTC · ${eth_mo*12:,.0f} ETH</i>"
               if crypto_mo > 0 else ""),
        # col 4 – wealth-building destinations
        f"Joint Brokerage<br><b>${_bal(['Joint Brokerage']):,.0f} bal</b>"           # 12
            + (f"<br><i>+${(bofa_to_jb+navy_to_jb)*12:,.0f}/yr</i>"
               if (bofa_to_jb + navy_to_jb) > 0 else ""),
        f"Josh Roth IRA<br><b>${josh_roth_bal:,.0f}</b>",                           # 13
        f"Athena Roth IRA<br><b>${athena_roth_bal:,.0f}</b>",                       # 14
        f"Coinbase<br><b>BTC</b>",                                                  # 15
        f"Gemini<br><b>${gemini_bal:,.0f} · ETH</b>",                               # 16
    ]

    colors = [
        _C["income"],  _C["income"],  _C["income"],  _C["income"],   # 0-3  income
        _C["tax"],     _C["invest"],                                   # 4-5  deductions
        _C["bank"],    _C["bank"],                                     # 6-7  banking
        _C["expense"], _C["expense"], _C["invest"],  _C["crypto"],    # 8-11 allocation
        _C["invest"],                                                  # 12   joint brokerage
        _C["invest"],  _C["invest"],                                   # 13-14 roths
        _C["crypto"],  _C["crypto"],                                   # 15-16 exchanges
    ]

    x_pos = [
        0.02, 0.02, 0.02, 0.02,            # col 0 – income
        0.24, 0.24,                         # col 1 – deductions
        0.48, 0.48,                         # col 2 – banking
        0.70, 0.70, 0.70, 0.70,            # col 3 – allocation
        0.93, 0.93, 0.93, 0.93, 0.93,     # col 4 – destinations
    ]
    y_pos = [
        0.05, 0.19, 0.58, 0.74,            # income: Josh, Athena, Parkwood, Gift
        0.07, 0.23,                         # deductions: Taxes, 401k
        0.22, 0.72,                         # banking: NavyFed, BofA
        0.06, 0.24, 0.43, 0.62,            # allocation: Housing, Living, ETrade, Crypto
        0.10, 0.30, 0.50, 0.68, 0.84,     # destinations: JB, JoshRoth, AthenaRoth, Coinbase, Gemini
    ]

    # ── Conditionally add employer match node ──────────────────────────────
    if has_match:
        N["employer_match"] = len(labels)       # index 17
        labels.append(f"Employer Match<br><b>${employer_match_mo*12:,.0f}/yr</b>")
        colors.append(_C["match"])
        x_pos.append(0.02)                      # col 0 (income source)
        y_pos.append(0.38)                      # between Athena and Parkwood

    # ── Links ──────────────────────────────────────────────────────────────
    srcs, tgts, vals, ltexts, lcolors = [], [], [], [], []

    def link(s, t, v_mo, color, label=""):
        """v_mo is monthly — stored and displayed as annual."""
        v_yr = v_mo * 12
        if v_yr > 6:   # skip flows < $6/yr (effectively zero)
            srcs.append(N[s]);  tgts.append(N[t])
            vals.append(round(v_yr, 0))
            ltexts.append(f"${v_yr:,.0f}/yr" if not label else label)
            lcolors.append(_rgba(color))

    # W2 income → deductions + banking
    link("josh_salary",   "taxes",     josh_tax,   _C["tax"],    f"Withholding ${josh_tax*12:,.0f}/yr")
    link("josh_salary",   "josh_401k", josh_401k,  _C["invest"], f"Deferral ${josh_401k*12:,.0f}/yr")
    link("josh_salary",   "navy_fed",  josh_net,   _C["bank"],   f"Net pay ${josh_net*12:,.0f}/yr")

    link("athena_income", "taxes",     athena_tax, _C["tax"],    f"Withholding ${athena_tax*12:,.0f}/yr")
    link("athena_income", "navy_fed",  athena_th,  _C["bank"],   f"Net pay ${athena_th*12:,.0f}/yr")

    # Employer match → 401k (free money)
    if has_match:
        link("employer_match", "josh_401k", employer_match_mo, _C["match"],
             f"Employer match ${employer_match_mo*12:,.0f}/yr")

    # Passive income → BofA
    link("parkwood", "bofa", pkw_mo,  _C["income"], f"Distributions ${pkw_mo*12:,.0f}/yr")
    link("gift",     "bofa", gift_mo, _C["income"], f"Annual gift ${gift_mo*12:,.0f}/yr")

    # BofA → operating transfer (cover Navy Fed shortfall) + wealth building
    link("bofa", "navy_fed",        bofa_to_navyfed, _C["bank"],
         f"Operating transfer ${bofa_to_navyfed*12:,.0f}/yr")
    link("bofa", "joint_brokerage", bofa_to_jb,      _C["invest"],
         f"Wealth building ${bofa_to_jb*12:,.0f}/yr")

    # Navy Fed → allocation
    link("navy_fed", "housing",         housing,             _C["expense"],
         f"Housing ${housing*12:,.0f}/yr")
    link("navy_fed", "expenses",        budget_mo + debt_mo, _C["expense"],
         f"Living ${(budget_mo+debt_mo)*12:,.0f}/yr")
    link("navy_fed", "etrade",          roth_total,          _C["invest"],
         f"IRA funding ${roth_total*12:,.0f}/yr")
    link("navy_fed", "crypto",          crypto_mo,           _C["crypto"],
         f"Crypto ${crypto_mo*12:,.0f}/yr")
    link("navy_fed", "joint_brokerage", navy_to_jb,          _C["invest"],
         f"Net proceeds ${navy_to_jb*12:,.0f}/yr")

    # E*Trade → IRAs
    link("etrade", "josh_roth",   roth_josh,   _C["invest"], f"Josh Roth ${roth_josh*12:,.0f}/yr")
    link("etrade", "athena_roth", roth_athena, _C["invest"], f"Athena Roth ${roth_athena*12:,.0f}/yr")

    # Crypto → exchanges
    link("crypto", "coinbase", btc_mo, _C["crypto"], f"BTC ${btc_mo*12:,.0f}/yr")
    link("crypto", "gemini",   eth_mo, _C["crypto"], f"ETH ${eth_mo*12:,.0f}/yr")

    # ── Build Sankey figure ────────────────────────────────────────────────
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            pad=20,
            thickness=18,
            line=dict(color=tc["pie_border"], width=0.5),
            label=labels,
            color=colors,
            x=x_pos,
            y=y_pos,
            hovertemplate="<b>%{label}</b><extra></extra>",
        ),
        link=dict(
            source=srcs,
            target=tgts,
            value=vals,
            label=ltexts,
            color=lcolors,
            hovertemplate="<b>%{label}</b><extra></extra>",
        ),
    ))

    fig.update_layout(**chart_layout(
        height=700,
        margin=dict(l=10, r=10, t=10, b=10),
        font=dict(size=11),
    ))

    st.plotly_chart(fig, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════
    # COO SCORECARD — Row 1: Primary KPIs
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("<br>", unsafe_allow_html=True)

    # Aggregate metrics
    w2_income        = (josh_gross_mo + athena_gross_mo) * 12
    passive_income   = (pkw_mo + gift_mo) * 12
    match_income     = employer_match_mo * 12
    total_income     = w2_income + passive_income + match_income
    total_taxes      = (josh_tax + athena_tax) * 12
    operating_cost   = (housing + budget_mo + debt_mo) * 12
    total_wealth     = (josh_401k + employer_match_mo + roth_josh + roth_athena
                        + crypto_mo + bofa_to_jb + navy_to_jb) * 12
    tax_advantaged   = (josh_401k + employer_match_mo + roth_josh + roth_athena) * 12
    taxable_invested = total_wealth - tax_advantaged

    eff_tax_rate     = total_taxes / w2_income * 100 if w2_income else 0
    savings_rate     = total_wealth / total_income * 100 if total_income else 0
    passive_coverage = passive_income / operating_cost * 100 if operating_cost else 0
    tax_adv_pct      = tax_advantaged / total_wealth * 100 if total_wealth else 0

    k1, k2, k3, k4, k5, k6 = st.columns(6)

    with k1:
        st.markdown(f"""
        <div class="kpi-card" style="border-top:3px solid {BLUE}">
            <div class="kpi-label">Gross Household Income</div>
            <div class="kpi-value" style="font-size:1.3rem">${total_income:,.0f}</div>
            <div class="kpi-sub">W2 + passive + match</div>
        </div>""", unsafe_allow_html=True)

    with k2:
        st.markdown(f"""
        <div class="kpi-card" style="border-top:3px solid {RED}">
            <div class="kpi-label">Effective Tax Rate</div>
            <div class="kpi-value" style="font-size:1.3rem">{eff_tax_rate:.1f}%</div>
            <div class="kpi-sub">${total_taxes:,.0f} total withholding</div>
        </div>""", unsafe_allow_html=True)

    with k3:
        st.markdown(f"""
        <div class="kpi-card" style="border-top:3px solid #f43f5e">
            <div class="kpi-label">Operating Expenses</div>
            <div class="kpi-value" style="font-size:1.3rem">${operating_cost:,.0f}</div>
            <div class="kpi-sub">Housing + living + debt svc</div>
        </div>""", unsafe_allow_html=True)

    with k4:
        st.markdown(f"""
        <div class="kpi-card" style="border-top:3px solid {PURPLE}">
            <div class="kpi-label">Total Wealth Building</div>
            <div class="kpi-value" style="font-size:1.3rem">${total_wealth:,.0f}</div>
            <div class="kpi-sub">401k + match + IRAs + brokerage + crypto</div>
        </div>""", unsafe_allow_html=True)

    sr_color = GREEN if savings_rate >= 25 else (AMBER if savings_rate >= 15 else RED)
    with k5:
        st.markdown(f"""
        <div class="kpi-card" style="border-top:3px solid {sr_color}">
            <div class="kpi-label">Savings Rate</div>
            <div class="kpi-value" style="font-size:1.3rem;color:{sr_color}">{savings_rate:.1f}%</div>
            <div class="kpi-sub">of gross household income</div>
        </div>""", unsafe_allow_html=True)

    pc_color = GREEN if passive_coverage >= 100 else (AMBER if passive_coverage >= 50 else tc["faint"])
    with k6:
        st.markdown(f"""
        <div class="kpi-card" style="border-top:3px solid {pc_color}">
            <div class="kpi-label">Passive Coverage</div>
            <div class="kpi-value" style="font-size:1.3rem;color:{pc_color}">{passive_coverage:.0f}%</div>
            <div class="kpi-sub">passive income ÷ operating cost</div>
        </div>""", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # COO SCORECARD — Row 2: Strategic Metrics
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)

    # ── Income Composition ─────────────────────────────────────────────────
    w2_pct      = w2_income / total_income * 100 if total_income else 0
    passive_pct = passive_income / total_income * 100 if total_income else 0
    match_pct_  = match_income / total_income * 100 if total_income else 0

    with m1:
        st.markdown(f"""
        <div style="background:{tc["card"]};border:1px solid {tc["border"]};
                    border-radius:10px;padding:0.85rem 1rem;">
            <div style="color:{tc["subtle"]};font-size:0.6rem;font-weight:700;
                        text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.6rem">
                Income Composition</div>
            <div style="display:flex;height:6px;border-radius:3px;overflow:hidden;margin-bottom:0.5rem">
                <div style="width:{w2_pct}%;background:{BLUE}"></div>
                <div style="width:{passive_pct}%;background:{GREEN}"></div>
                <div style="width:{match_pct_}%;background:{CYAN}"></div>
            </div>
            <div style="display:flex;gap:0.7rem;flex-wrap:wrap">
                <span style="color:{tc["muted"]};font-size:0.7rem"><span style="color:{BLUE}">●</span> W2 {w2_pct:.0f}%</span>
                <span style="color:{tc["muted"]};font-size:0.7rem"><span style="color:{GREEN}">●</span> Passive {passive_pct:.0f}%</span>
                <span style="color:{tc["muted"]};font-size:0.7rem"><span style="color:{CYAN}">●</span> Match {match_pct_:.0f}%</span>
            </div>
        </div>""", unsafe_allow_html=True)

    # ── Investment Tax Efficiency ──────────────────────────────────────────
    with m2:
        st.markdown(f"""
        <div style="background:{tc["card"]};border:1px solid {tc["border"]};
                    border-radius:10px;padding:0.85rem 1rem;">
            <div style="color:{tc["subtle"]};font-size:0.6rem;font-weight:700;
                        text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.6rem">
                Investment Tax Efficiency</div>
            <div style="display:flex;height:6px;border-radius:3px;overflow:hidden;margin-bottom:0.5rem">
                <div style="width:{tax_adv_pct}%;background:{PURPLE}"></div>
                <div style="width:{100-tax_adv_pct}%;background:{AMBER}"></div>
            </div>
            <div style="display:flex;gap:0.7rem;flex-wrap:wrap">
                <span style="color:{tc["muted"]};font-size:0.7rem"><span style="color:{PURPLE}">●</span> Tax-advantaged {tax_adv_pct:.0f}%</span>
                <span style="color:{tc["muted"]};font-size:0.7rem"><span style="color:{AMBER}">●</span> Taxable {100-tax_adv_pct:.0f}%</span>
            </div>
        </div>""", unsafe_allow_html=True)

    # ── Dollar Allocation ──────────────────────────────────────────────────
    tax_share = total_taxes / total_income * 100 if total_income else 0
    ops_share = operating_cost / total_income * 100 if total_income else 0
    inv_share = total_wealth / total_income * 100 if total_income else 0
    oth_share = max(0, 100 - tax_share - ops_share - inv_share)

    with m3:
        st.markdown(f"""
        <div style="background:{tc["card"]};border:1px solid {tc["border"]};
                    border-radius:10px;padding:0.85rem 1rem;">
            <div style="color:{tc["subtle"]};font-size:0.6rem;font-weight:700;
                        text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.6rem">
                Where Every Dollar Goes</div>
            <div style="display:flex;height:6px;border-radius:3px;overflow:hidden;margin-bottom:0.5rem">
                <div style="width:{tax_share}%;background:{RED}"></div>
                <div style="width:{ops_share}%;background:#f43f5e"></div>
                <div style="width:{inv_share}%;background:{PURPLE}"></div>
                <div style="width:{oth_share}%;background:#334155"></div>
            </div>
            <div style="display:flex;gap:0.7rem;flex-wrap:wrap">
                <span style="color:{tc["muted"]};font-size:0.7rem"><span style="color:{RED}">●</span> Tax {tax_share:.0f}%</span>
                <span style="color:{tc["muted"]};font-size:0.7rem"><span style="color:#f43f5e">●</span> Ops {ops_share:.0f}%</span>
                <span style="color:{tc["muted"]};font-size:0.7rem"><span style="color:{PURPLE}">●</span> Invest {inv_share:.0f}%</span>
            </div>
        </div>""", unsafe_allow_html=True)

    # ── Employer Match Capture ─────────────────────────────────────────────
    match_capture  = employer_match_mo / max_match_mo * 100 if max_match_mo else 0
    cap_color      = GREEN if match_capture >= 100 else (AMBER if match_capture >= 50 else RED)
    cap_label      = "Fully captured" if match_capture >= 100 else f"{match_capture:.0f}% captured"
    uncaptured     = (max_match_mo - employer_match_mo) * 12

    with m4:
        st.markdown(f"""
        <div style="background:{tc["card"]};border:1px solid {tc["border"]};
                    border-radius:10px;padding:0.85rem 1rem;">
            <div style="color:{tc["subtle"]};font-size:0.6rem;font-weight:700;
                        text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.6rem">
                Employer Match Capture</div>
            <div style="display:flex;height:6px;border-radius:3px;overflow:hidden;
                        margin-bottom:0.5rem;background:{tc["card"]}">
                <div style="width:{min(match_capture,100)}%;background:{cap_color}"></div>
            </div>
            <div style="display:flex;justify-content:space-between">
                <span style="color:{cap_color};font-size:0.7rem;font-weight:600">{cap_label}</span>
                <span style="color:{tc["subtle"]};font-size:0.7rem">${match_income:,.0f}/yr free</span>
            </div>
            {"" if uncaptured <= 0 else f'<div style="color:#ef4444;font-size:0.65rem;margin-top:0.3rem">⚠ ${uncaptured:,.0f}/yr left on table — increase 401k deferral</div>'}
        </div>""", unsafe_allow_html=True)

    # ── Missing data nudge ─────────────────────────────────────────────────
    missing = []
    if athena_gross_mo == 0:
        missing.append("Athena's income — add in ⚙️ Setup → Spouse Income")
    if pkw_mo == 0:
        missing.append("Parkwood LP distributions — set above")
    if gift_mo == 0:
        missing.append("St. Clair annual gift — set above")
    if crypto_mo == 0:
        missing.append("Crypto purchases (ETH + BTC) — set above")

    if missing:
        st.markdown("<br>", unsafe_allow_html=True)
        items = "".join(f"<li style='margin-bottom:4px'>{m}</li>" for m in missing)
        st.markdown(
            f'<div style="background:{tc["card"]};border:1px solid rgba(245,158,11,0.3);'
            f'border-radius:10px;padding:1rem 1.25rem;">'
            f'<div style="color:{AMBER};font-weight:600;margin-bottom:0.5rem">'
            f'⚠️ Incomplete data — add these for an accurate flow map:</div>'
            f'<ul style="color:{tc["muted"]};font-size:0.85rem;margin:0;padding-left:1.2rem">'
            f'{items}</ul></div>',
            unsafe_allow_html=True,
        )

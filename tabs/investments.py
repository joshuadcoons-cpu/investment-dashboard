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

ACCOUNT_COLORS = {
    "401k":      BLUE,
    "Roth 401k": PURPLE,
    "Trad IRA":  AMBER,
    "Roth IRA":  GREEN,
    "Brokerage": CYAN,
    "HSA":       "#f97316",
    "HYSA":      "#f43f5e",   # rose — emergency fund / HYSA
    "Sinking":   "#f97316",   # orange — sinking fund
}

SP500_WEIGHTS = {
    "Technology": 32, "Financials": 13, "Healthcare": 12,
    "Consumer Cyclical": 10, "Industrials": 9, "Communication Services": 9,
    "Consumer Defensive": 6, "Energy": 4, "Utilities": 3,
    "Real Estate": 2, "Materials": 2,
}


@st.cache_data(ttl=300)
def _get_price(ticker: str) -> float | None:
    try:
        return yf.Ticker(ticker).fast_info.last_price
    except Exception:
        return None


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

    st.header("📈 Investment Accounts")

    if not accounts:
        st.info("Add investment accounts in the ⚙️ Setup tab.")
        return

    # ── LP → Joint Brokerage flow (after partial-shelter tax) ────────────────
    lp_jb_pct        = a.get("lp_jb_pct", 85)
    lp_net_factor    = a.get("lp_net_pct", 100) / 100   # e.g. 0.75 = 75% kept after tax
    lp_gross_monthly = a.get("parkwood_lp_monthly", 0)
    lp_net_monthly   = lp_gross_monthly * lp_net_factor
    lp_to_jb_monthly = lp_net_monthly * lp_jb_pct / 100
    lp_to_jb_annual  = lp_to_jb_monthly * 12

    # ── HYSA / Emergency Fund ─────────────────────────────────────────────────
    hysa_balance    = a.get("emergency_fund_balance", 0)
    sinking_balance = a.get("sinking_fund_balance", 0)
    hysa_target_mo  = a.get("emergency_fund_target_months", 6)

    # ── Investment account totals ─────────────────────────────────────────────
    total_balance = sum(acct["balance"] for acct in accounts)
    total_monthly = sum(acct["monthly_contribution"] for acct in accounts)

    total_match = 0.0
    for acct in accounts:
        if acct["account_type"] in ("401k", "Roth 401k") and acct.get("employer_match_pct", 0) > 0:
            cap          = a["gross_income"] * acct.get("employer_match_ceiling_pct", 0) / 100 / 12
            total_match += min(acct["monthly_contribution"], cap) * acct["employer_match_pct"] / 100

    # Growth projection inputs: regular + LP inflow + employer match
    monthly_total_in = total_monthly + lp_to_jb_monthly + total_match
    annual_total_in  = monthly_total_in * 12
    ret_pct          = float(a.get("investment_return_pct", 7.0))
    years_left       = max(1, ret_age - age)
    est_at_retire    = _fv(total_balance, annual_total_in, ret_pct / 100, years_left)

    # Grand total shown in headline (investments + HYSA + sinking fund)
    grand_total = total_balance + hysa_balance + sinking_balance

    # ── KPI Row ───────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💼 Total Holdings", f"${grand_total:,.0f}",
              delta=f"Invested ${total_balance:,.0f}  +  HYSA ${hysa_balance:,.0f}",
              delta_color="off")
    k2.metric("📥 Monthly Into Market",
              f"${total_monthly + lp_to_jb_monthly:,.0f}",
              delta=f"${total_monthly:,.0f} contributions  +  ${lp_to_jb_monthly:,.0f} LP inflow",
              delta_color="off")
    k3.metric("🤝 Employer Match", f"${total_match:,.0f}/mo",
              delta=f"${total_match * 12:,.0f}/yr free", delta_color="off")
    k4.metric(f"🎯 Est. at Retirement (age {ret_age})",
              f"${est_at_retire / 1_000_000:.2f}M" if est_at_retire >= 1_000_000 else f"${est_at_retire:,.0f}",
              delta=f"at {ret_pct:.1f}% return · {years_left}yr", delta_color="off")

    st.divider()

    # ── Allocation donut  +  Contribution Health ───────────────────────────────
    left_col, right_col = st.columns([1, 1])

    with left_col:
        alloc_rows = [
            {"Account": acct["label"], "Type": acct["account_type"], "Balance": acct["balance"]}
            for acct in accounts if acct["balance"] > 0
        ]
        if hysa_balance > 0:
            alloc_rows.append({"Account": "HYSA", "Type": "HYSA", "Balance": hysa_balance})
        if sinking_balance > 0:
            alloc_rows.append({"Account": "Sinking Fund", "Type": "Sinking", "Balance": sinking_balance})

        if alloc_rows:
            alloc_df = pd.DataFrame(alloc_rows)
            colors   = [ACCOUNT_COLORS.get(t, "#475569") for t in alloc_df["Type"]]
            n_accts  = len(accounts) + (1 if hysa_balance > 0 else 0) + (1 if sinking_balance > 0 else 0)

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
                height=340,
                showlegend=True,
                legend=dict(
                    orientation="h",
                    x=0.5, y=-0.08,
                    xanchor="center",
                    font=dict(size=11, color="#e2e8f0"),
                ),
                margin=dict(l=20, r=20, t=50, b=20),
            ))
            st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.info("Add balances in ⚙️ Setup to see allocation.")

    with right_col:
        st.markdown("##### Contribution Health")
        st.caption(f"YTD contributions vs {date.today().year} IRS limits")
        st.markdown("<br>", unsafe_allow_html=True)

        # Months elapsed in current calendar year (e.g. March 18 ≈ 2.58 months)
        _today = date.today()
        _months_elapsed = (_today - date(_today.year, 1, 1)).days / 365 * 12

        for acct in accounts:
            # Rollover IRA (or any account flagged) — skip contribution tracking
            if acct.get("skip_contribution"):
                continue

            acct_type    = acct["account_type"]
            color        = ACCOUNT_COLORS.get(acct_type, "#475569")
            limits       = ACCOUNT_LIMITS.get(acct_type, {})
            catchup_age  = 55 if acct_type == "HSA" else 50
            limit        = limits.get("catchup" if age >= catchup_age else "base")
            is_jb        = acct_type == "Brokerage"

            # YTD actual: use explicit ytd_contributed field if set, else infer from months elapsed
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
                status  = "✅ Maxed!" if room < 1 else f"${room:,.0f} left this year"
                st.markdown(
                    f'<div style="background:#1e293b;border-radius:6px;height:10px;overflow:hidden">'
                    f'<div style="background:{bar_col};width:{pct:.1f}%;height:10px;'
                    f'border-radius:6px"></div></div>'
                    f'<div style="display:flex;justify-content:space-between;'
                    f'color:#94a3b8;font-size:0.75rem;margin-top:4px;margin-bottom:16px">'
                    f'<span>${ytd_c:,.0f} of ${limit:,.0f} YTD · {pct:.0f}%</span>'
                    f'<span style="color:{"#22c55e" if room < 1 else "#94a3b8"}">{status}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                lp_note = (f" · incl. ${lp_to_jb_annual:,.0f} LP inflow"
                           if is_jb and lp_to_jb_annual > 0 else "")
                st.markdown(
                    f'<div style="color:#64748b;font-size:0.8rem;margin-bottom:16px">'
                    f'${display_ann:,.0f}/yr · No IRS limit{lp_note}</div>',
                    unsafe_allow_html=True,
                )

    st.divider()

    # ── Growth Projection ─────────────────────────────────────────────────────
    st.subheader("📊 Growth Projection")
    st.caption(
        f"${total_monthly:,.0f}/mo regular contributions  ·  "
        f"${lp_to_jb_monthly:,.0f}/mo LP inflow ({lp_jb_pct}% of quarterly distributions)  ·  "
        f"${total_match:,.0f}/mo employer match"
    )

    cur_year   = date.today().year
    years_list = list(range(years_left + 1))
    x_yrs      = [cur_year + y for y in years_list]

    def series(rate_pct):
        r = rate_pct / 100
        return [_fv(total_balance, annual_total_in, r, y) for y in years_list]

    base_s = series(ret_pct)
    bull_s = series(ret_pct + 3)
    bear_s = series(max(1.0, ret_pct - 3))

    fig_g = go.Figure()
    fig_g.add_trace(go.Scatter(
        x=x_yrs + x_yrs[::-1],
        y=bull_s + bear_s[::-1],
        fill="toself", fillcolor="rgba(59,130,246,0.10)",
        line=dict(width=0), showlegend=True,
        name=f"Range ({max(ret_pct - 3, 1):.0f}%–{ret_pct + 3:.0f}%)",
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
    # Milestone lines: subtle at $1M, stronger at $5M
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

    # ── Account Detail Cards ──────────────────────────────────────────────────
    st.subheader("🗂️ Account Details")

    for acct in accounts:
        acct_type  = acct["account_type"]
        color      = ACCOUNT_COLORS.get(acct_type, "#475569")
        limits     = ACCOUNT_LIMITS.get(acct_type, {})
        catchup_age= 55 if acct_type == "HSA" else 50
        limit      = limits.get("catchup" if age >= catchup_age else "base")
        annual_c   = acct["monthly_contribution"] * 12
        is_jb      = acct_type == "Brokerage"

        # Effective monthly shown on card (includes LP inflow for JB)
        eff_monthly = acct["monthly_contribution"] + (lp_to_jb_monthly if is_jb else 0)
        eff_annual  = eff_monthly * 12

        match_mo = 0.0
        if acct_type in ("401k", "Roth 401k") and acct.get("employer_match_pct", 0) > 0:
            cap      = a["gross_income"] * acct.get("employer_match_ceiling_pct", 0) / 100 / 12
            match_mo = min(acct["monthly_contribution"], cap) * acct["employer_match_pct"] / 100

        with st.container(border=True):
            r1, r2, r3, r4, r5 = st.columns([3, 2, 2, 2, 2])

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
            r2.metric("Balance", f"${acct['balance']:,.0f}")
            r3.metric("Monthly", f"${eff_monthly:,.0f}",
                      delta=f"${lp_to_jb_monthly:,.0f} LP inflow" if is_jb and lp_to_jb_monthly > 0 else None,
                      delta_color="off")
            r4.metric("Annual",  f"${eff_annual:,.0f}")

            if match_mo > 0:
                r5.metric("+ Match", f"${match_mo:,.0f}/mo",
                          delta=f"${match_mo * 12:,.0f}/yr free")
            elif acct_type in ("401k", "Roth 401k") and acct.get("employer_match_ceiling_pct", 0) > 0:
                cap_mo = a["gross_income"] * acct.get("employer_match_ceiling_pct", 0) / 100 / 12
                r5.metric("Match available", f"${cap_mo:,.0f}/mo needed",
                          delta="not yet captured", delta_color="inverse")

            if limit:
                card_ytd = acct.get("ytd_contributed",
                                    acct["monthly_contribution"] * _months_elapsed)
                pct      = min(card_ytd / limit * 100, 100)
                room     = max(0, limit - card_ytd)
                bar_col  = GREEN if pct >= 100 else (AMBER if pct >= 80 else BLUE)
                status   = "✅ Maxed out!" if room < 1 else f"${room:,.0f} left this year"
                st.markdown(
                    f'<div style="margin-top:10px;background:#0f172a;border-radius:6px;'
                    f'height:8px;overflow:hidden">'
                    f'<div style="background:{bar_col};width:{pct:.1f}%;height:8px;'
                    f'border-radius:6px"></div></div>'
                    f'<div style="display:flex;justify-content:space-between;'
                    f'color:#94a3b8;font-size:0.75rem;margin-top:4px">'
                    f'<span>${card_ytd:,.0f} of ${limit:,.0f} IRS limit YTD · {pct:.0f}%</span>'
                    f'<span style="color:{"#22c55e" if room < 1 else "#cbd5e1"}">{status}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            elif is_jb and lp_to_jb_monthly > 0:
                st.markdown(
                    f'<div style="margin-top:10px;color:#64748b;font-size:0.75rem">'
                    f'💧 ${lp_to_jb_monthly:,.0f}/mo LP inflow ({lp_jb_pct}% of quarterly '
                    f'distributions)  ·  ${lp_to_jb_annual:,.0f}/yr  ·  No IRS limit'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ── HYSA / Emergency Fund Card ────────────────────────────────────────────
    st.divider()
    st.subheader("🏦 HYSA / Emergency Fund + Sinking Fund")

    # Estimate monthly living expenses for coverage calculation
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
        hc2.metric("Balance",      f"${hysa_balance:,.0f}")
        hc3.metric("Coverage",     f"{months_covered:.1f} mo",
                   delta=f"Target: {hysa_target_mo} mo", delta_color="off")
        hc4.metric("Target",       f"${target_balance:,.0f}",
                   delta=f"${gap:,.0f} to go" if gap > 0 else "✅ Fully funded",
                   delta_color="inverse" if gap > 0 else "off")

        st.markdown(
            f'<div style="margin-top:10px;background:#0f172a;border-radius:6px;'
            f'height:8px;overflow:hidden">'
            f'<div style="background:{bar_col};width:{pct_of_target:.1f}%;height:8px;'
            f'border-radius:6px"></div></div>'
            f'<div style="display:flex;justify-content:space-between;'
            f'color:#94a3b8;font-size:0.75rem;margin-top:4px">'
            f'<span>${hysa_balance:,.0f} of ${target_balance:,.0f} target · {pct_of_target:.0f}%</span>'
            f'<span style="color:{"#22c55e" if gap == 0 else "#cbd5e1"}">'
            f'{"✅ Fully funded" if gap == 0 else f"${gap:,.0f} to fund {hysa_target_mo}mo target"}'
            f'</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Sector Allocation ─────────────────────────────────────────────────────
    st.divider()
    st.subheader("🗺️ Sector Allocation")

    all_holdings = []
    for acct in accounts:
        for h in acct.get("holdings", []):
            if h.get("ticker") and h.get("shares", 0) > 0:
                all_holdings.append({
                    "ticker":  h["ticker"],
                    "shares":  h["shares"],
                    "sector":  h.get("sector", "Unknown"),
                    "account": acct["label"],
                })

    if not all_holdings:
        st.markdown(
            '<div style="background:#0f172a;border:1px dashed #334155;border-radius:10px;'
            'padding:32px;text-align:center;color:#64748b">'
            '<div style="font-size:2rem;margin-bottom:8px">📂</div>'
            '<div style="font-size:1rem;font-weight:600;color:#94a3b8;margin-bottom:4px">'
            'No holdings added yet</div>'
            '<div style="font-size:0.85rem">Add tickers in ⚙️ Setup → Investment Accounts → Holdings</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        with st.spinner("Fetching live prices…"):
            rows = []
            for h in all_holdings:
                price = _get_price(h["ticker"]) or 0
                value = price * h["shares"]
                rows.append({
                    "Ticker":  h["ticker"],
                    "Account": h["account"],
                    "Sector":  h["sector"],
                    "Shares":  h["shares"],
                    "Price":   price,
                    "Value":   value,
                })

        hold_df   = pd.DataFrame(rows)
        total_val = hold_df["Value"].sum()

        if total_val == 0:
            st.warning("Prices unavailable — check ticker symbols or try again later.")
        else:
            sector_df = (
                hold_df.groupby("Sector")["Value"]
                .sum().reset_index()
                .rename(columns={"Value": "Value ($)"})
            )
            sector_df["Weight (%)"] = sector_df["Value ($)"] / total_val * 100
            sector_df = sector_df.sort_values("Value ($)", ascending=False)

            left, right = st.columns([1, 1])

            with left:
                ticker_df = hold_df.groupby(["Sector", "Ticker"])["Value"].sum().reset_index()
                ticker_df = ticker_df[ticker_df["Value"] > 0]
                fig_st = px.treemap(
                    ticker_df, path=["Sector", "Ticker"], values="Value",
                    color="Value",
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
                            f"⚠️ Heavy concentration in **{row['Sector']}** "
                            f"({row['Weight (%)']:.1f}%) — consider diversifying"
                        )

            with right:
                all_sectors = list(SP500_WEIGHTS.keys()) + [
                    s for s in sector_df["Sector"].tolist()
                    if s not in SP500_WEIGHTS
                ]
                all_sectors = list(dict.fromkeys(all_sectors))

                compare_rows = []
                for s in all_sectors:
                    your_w = sector_df.loc[sector_df["Sector"] == s, "Weight (%)"].values
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

            st.subheader("Holdings Detail")
            disp = hold_df[["Ticker", "Account", "Sector", "Shares", "Price", "Value"]].copy()
            disp["Value"] = disp["Value"].round(2)
            st.dataframe(
                disp.style.format({
                    "Shares": "{:.4f}", "Price": "${:.2f}", "Value": "${:,.2f}",
                }),
                use_container_width=True, hide_index=True,
            )

    # ── Live Stock / ETF Lookup ───────────────────────────────────────────────
    st.divider()
    st.subheader("🔍 Live Stock / ETF Lookup")
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

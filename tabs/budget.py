import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import date
from utils.calculations import calc_monthly_payment
from utils.styles import BLUE, GREEN, RED, PURPLE, AMBER, CYAN, CHART_COLORS, chart_layout


def render():
    a = st.session_state.assumptions
    st.header("💵 Monthly Budget")

    # ── Income ────────────────────────────────────────────────────────────────
    total_take_home  = a["take_home_monthly"] + a["spouse_take_home_monthly"]
    lp_net_monthly   = a.get("parkwood_lp_monthly", 0) * a.get("lp_net_pct", 100) / 100
    passive_monthly  = lp_net_monthly + a.get("family_gift_annual", 0) / 12
    total_monthly_in = total_take_home + passive_monthly

    # ── Fixed: Housing ────────────────────────────────────────────────────────
    monthly_pi    = calc_monthly_payment(
        a["loan_original_amount"], a["loan_interest_rate"], a["loan_term_years"])
    monthly_tax   = a["home_current_value"] * a["property_tax_rate"] / 100 / 12
    monthly_ins   = a["home_insurance_annual"] / 12
    monthly_hoa   = a["hoa_monthly"]
    monthly_maint = a["home_current_value"] * a["maintenance_pct"] / 100 / 12
    total_housing = monthly_pi + monthly_tax + monthly_ins + monthly_hoa + monthly_maint

    # ── Fixed: Debts ──────────────────────────────────────────────────────────
    total_debt_pmts  = sum(d["monthly_payment"] for d in a["other_debts"])
    total_variable   = sum(v for v in a["budget"].values())
    total_investments = sum(acct["monthly_contribution"] for acct in a["investment_accounts"])

    total_out     = total_housing + total_debt_pmts + total_variable + total_investments
    net_cash_flow = total_monthly_in - total_out
    savings_rate  = (
        (total_investments + max(net_cash_flow, 0)) / total_monthly_in * 100
        if total_monthly_in else 0
    )

    # ── Top Metrics ───────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💵 Monthly Income", f"${total_monthly_in:,.0f}",
              delta=f"+${passive_monthly:,.0f} passive" if passive_monthly > 0 else None)
    c2.metric("🏠 Total Housing",     f"${total_housing:,.0f}")
    c3.metric(
        "💰 Net Cash Flow", f"${net_cash_flow:,.0f}",
        delta="Surplus ✅" if net_cash_flow >= 0 else "Deficit ⚠️",
        delta_color="normal" if net_cash_flow >= 0 else "inverse",
    )
    c4.metric("📊 Savings Rate", f"{savings_rate:.1f}%")

    st.divider()

    left, right = st.columns([1, 1])

    # ── Left: Yearly Budget Pie ──────────────────────────────────────────────
    with left:
        raw = {}
        raw["Housing"] = total_housing * 12
        for k, v in a["budget"].items():
            if v > 0:
                raw[k] = v * 12
        for d in a["other_debts"]:
            if d["monthly_payment"] > 0:
                raw[f"Debt: {d['name']}"] = d["monthly_payment"] * 12
        for acct in a["investment_accounts"]:
            if acct["monthly_contribution"] > 0:
                raw[acct["label"]] = acct["monthly_contribution"] * 12
        if net_cash_flow > 0:
            raw["Surplus"] = net_cash_flow * 12

        annual_total = sum(raw.values())
        threshold = 20_000  # group items < $20k/yr into Other

        pie_data = {}
        other_sum = 0
        for k, v in raw.items():
            if v >= threshold or k in ("Housing", "Surplus"):
                pie_data[k] = v
            else:
                other_sum += v
        if other_sum > 0:
            pie_data["Other"] = other_sum

        acct_labels_set = {acct["label"] for acct in a["investment_accounts"]}

        # Assign colors
        _color_map = {
            "Housing": BLUE, "Surplus": CYAN, "Other": "#475569",
            "Travel & Vacations": AMBER, "Groceries": GREEN,
        }
        pie_colors = []
        for cat in pie_data:
            if cat in _color_map:
                pie_colors.append(_color_map[cat])
            elif cat.startswith("Debt:"):
                pie_colors.append(RED)
            elif cat in acct_labels_set:
                pie_colors.append(PURPLE)
            else:
                pie_colors.append("#334155")

        p_labels = list(pie_data.keys())
        p_values = list(pie_data.values())

        fig_pie = go.Figure(go.Pie(
            labels=p_labels,
            values=p_values,
            hole=0.45,
            marker=dict(colors=pie_colors, line=dict(color="#020817", width=2)),
            textinfo="label+percent",
            textposition="inside",
            insidetextorientation="horizontal",
            textfont=dict(size=13, color="white", family="Barlow"),
            hovertemplate="%{label}<br>$%{value:,.0f}/yr (%{percent})<extra></extra>",
            sort=False,
        ))
        fig_pie.add_annotation(
            text=f"<b>${annual_total/1000:,.0f}k</b><br><span style='font-size:10px;color:#64748b'>per year</span>",
            x=0.5, y=0.5, xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=20, color="#f1f5f9", family="Barlow Condensed"),
        )
        fig_pie.update_layout(**chart_layout(
            title="Annual Budget Breakdown",
            height=480,
            showlegend=False,
        ))
        st.plotly_chart(fig_pie, use_container_width=True)

    # ── Right: Cash-Flow Sankey ──────────────────────────────────────────────
    with right:
        def _rgba(hex_color, alpha=0.35):
            h = hex_color.lstrip("#")
            return f"rgba({int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)},{alpha})"

        # Nodes: income sources (left) → destinations (right)
        nodes = []  # (label, amount, color)
        nodes.append(("W2 Income", total_take_home, BLUE))
        n_income = 1
        if passive_monthly > 0:
            nodes.append(("Passive Income", passive_monthly, GREEN))
            n_income = 2

        # Destination nodes (right side)
        dest_items = [
            ("Housing",     total_housing,      RED),
            ("Living",      total_variable,     AMBER),
            ("Investments", total_investments,   PURPLE),
            ("Debt",        total_debt_pmts,     "#64748b"),
        ]
        for label, amt, color in dest_items:
            if amt > 0:
                nodes.append((label, amt, color))
        if net_cash_flow > 0:
            nodes.append(("Surplus", net_cash_flow, CYAN))

        node_labels = [f"{n[0]}  ${n[1]:,.0f}" for n in nodes]
        node_colors = [n[2] for n in nodes]

        # Links: each income source → each destination (proportional split)
        lk_src, lk_tgt, lk_val, lk_col = [], [], [], []
        for si in range(n_income):
            share = nodes[si][1] / total_monthly_in if total_monthly_in else 0
            for ti in range(n_income, len(nodes)):
                v = nodes[ti][1] * share
                if v > 0:
                    lk_src.append(si)
                    lk_tgt.append(ti)
                    lk_val.append(round(v, 2))
                    lk_col.append(_rgba(nodes[ti][2], 0.30))

        fig_flow = go.Figure(go.Sankey(
            arrangement="snap",
            node=dict(
                pad=18,
                thickness=22,
                line=dict(color="rgba(255,255,255,0.06)", width=0.5),
                label=node_labels,
                color=node_colors,
            ),
            link=dict(
                source=lk_src,
                target=lk_tgt,
                value=lk_val,
                color=lk_col,
            ),
        ))
        fig_flow.update_layout(**chart_layout(
            title="Monthly Cash Flow",
            height=420,
        ))
        st.plotly_chart(fig_flow, use_container_width=True)

    # ── Full Budget Table ─────────────────────────────────────────────────────
    st.subheader("Full Monthly Budget Breakdown")
    rows = [("💵 W2 Take-Home", total_take_home, "Income")]
    if passive_monthly > 0:
        rows.append(("💰 Passive Income (LP + Gift)", passive_monthly, "Income"))
    rows += [
        ("🏠 Mortgage P&I",       -monthly_pi,    "Fixed – Housing"),
        ("🏠 Property Tax",       -monthly_tax,   "Fixed – Housing"),
        ("🏠 Home Insurance",     -monthly_ins,   "Fixed – Housing"),
    ]
    if monthly_hoa:
        rows.append(("🏠 HOA",            -monthly_hoa,   "Fixed – Housing"))
    if monthly_maint:
        rows.append(("🏠 Maintenance",    -monthly_maint, "Fixed – Housing"))
    for d in a["other_debts"]:
        if d["monthly_payment"]:
            rows.append((f"💳 {d['name']}", -d["monthly_payment"], "Fixed – Debt"))
    for acct in a["investment_accounts"]:
        if acct["monthly_contribution"]:
            rows.append((f"📈 {acct['label']}", -acct["monthly_contribution"], "Investment"))
    for cat, amt in a["budget"].items():
        if amt:
            rows.append((f"  {cat}", -amt, "Variable"))
    rows.append(("💰 NET CASH FLOW", net_cash_flow, ""))

    tbl = pd.DataFrame(rows, columns=["Category", "Amount ($)", "Type"])
    st.dataframe(
        tbl.style
        .format({"Amount ($)": "${:,.0f}"})
        .map(
            lambda v: f"color: {GREEN}" if isinstance(v, (int, float)) and v > 0
            else (f"color: {RED}" if isinstance(v, (int, float)) and v < 0 else ""),
            subset=["Amount ($)"],
        ),
        use_container_width=True, hide_index=True,
    )

import streamlit as st
import copy
import yfinance as yf
from utils.defaults import DEFAULT_ASSUMPTIONS
from utils.database import load_assumptions, save_assumptions
from utils.styles import inject_css
from tabs import dashboard, setup, home, budget, investments, net_worth, projections, money_flow

st.set_page_config(
    page_title="Personal Finance Dashboard",
    page_icon="💰",
    layout="wide",
)

# ── Inject custom CSS ─────────────────────────────────────────────────────────
inject_css()

# ── Session state: load from SQLite or use defaults ───────────────────────────
if "assumptions" not in st.session_state:
    saved = load_assumptions()
    st.session_state.assumptions = saved if saved else copy.deepcopy(DEFAULT_ASSUMPTIONS)
if "ui_ver" not in st.session_state:
    st.session_state.ui_ver = 0


# ── Auto-refresh investment balances from live prices (once per session) ──────
CRYPTO_YF = {"BTC": "BTC-USD", "ETH": "ETH-USD", "ADA": "ADA-USD",
             "XRP": "XRP-USD", "DOGE": "DOGE-USD"}

@st.cache_data(ttl=300, show_spinner=False)
def _fetch_prices(tickers: tuple) -> tuple:
    """Returns (prices, prev_closes) dicts keyed by ticker."""
    prices = {}
    prev_closes = {}
    for t in tickers:
        yf_t = CRYPTO_YF.get(t, t)
        try:
            fi = yf.Ticker(yf_t).fast_info
            prices[t] = fi.last_price
            prev_closes[t] = fi.previous_close
        except Exception:
            pass
    return prices, prev_closes

if "prices_refreshed" not in st.session_state:
    a = st.session_state.assumptions
    all_tickers = set()
    for acct in a.get("investment_accounts", []):
        for h in acct.get("holdings", []):
            if h.get("ticker"):
                all_tickers.add(h["ticker"])
    if all_tickers:
        prices, prev_closes = _fetch_prices(tuple(sorted(all_tickers)))
        st.session_state.live_prices = prices
        st.session_state.prev_prices = prev_closes
        for acct in a["investment_accounts"]:
            has_priced = any(
                h.get("ticker") and prices.get(h["ticker"])
                for h in acct.get("holdings", [])
            )
            if has_priced:
                mv = acct.get("cash_usd", 0)
                for h in acct.get("holdings", []):
                    p = prices.get(h.get("ticker"))
                    if p:
                        mv += h["shares"] * p
                acct["balance"] = round(mv, 2)
    st.session_state.prices_refreshed = True


a = st.session_state.assumptions

# ── Dark / Light mode toggle ─────────────────────────────────────────────────
if "theme" not in st.session_state:
    st.session_state.theme = "dark"

with st.sidebar:
    st.markdown(f"### {a['dashboard_name']}")
    theme_label = "🌙 Dark" if st.session_state.theme == "dark" else "☀️ Light"
    if st.button(f"Switch to {'☀️ Light' if st.session_state.theme == 'dark' else '🌙 Dark'} Mode"):
        st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"
        st.rerun()
    st.caption(f"Theme: {theme_label}")

    # ── PDF Export ────────────────────────────────────────────────────────────
    st.divider()
    st.markdown("##### Export")

    from utils.calculations import calc_monthly_payment, build_amortization, get_loan_status
    from datetime import date

    total_inv = sum(ac["balance"] for ac in a["investment_accounts"])
    amort = build_amortization(
        a["loan_original_amount"], a["loan_interest_rate"],
        a["loan_term_years"], a["loan_start_date"],
    )
    status = get_loan_status(amort, date.today())
    sinking = a.get("sinking_fund_balance", 0)
    total_assets = (a["home_current_value"] + total_inv
                    + a["emergency_fund_balance"] + sinking
                    + a["checking_savings_balance"])
    total_liab = status["current_balance"] + sum(d["balance"] for d in a["other_debts"])
    nw = total_assets - total_liab

    def _fmt_k(v):
        if abs(v) >= 1_000_000:
            return f"${v/1e6:.2f}M"
        return f"${v:,.0f}"

    report_date = date.today().strftime("%B %d, %Y")
    html_report = f"""
    <html><head><meta charset='utf-8'>
    <style>
    body {{ font-family: Arial, sans-serif; padding: 40px; color: #1a1a2e; }}
    h1 {{ color: #1a1a2e; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; }}
    h2 {{ color: #334155; margin-top: 24px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
    th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
    th {{ background: #f1f5f9; font-weight: 600; }}
    .positive {{ color: #10b981; }} .negative {{ color: #ef4444; }}
    .summary {{ display: flex; gap: 20px; flex-wrap: wrap; }}
    .card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; min-width: 180px; }}
    .card-label {{ font-size: 12px; color: #64748b; text-transform: uppercase; }}
    .card-value {{ font-size: 24px; font-weight: 700; color: #1a1a2e; }}
    </style></head><body>
    <h1>{a['dashboard_name']}</h1>
    <p>Financial snapshot as of {report_date}</p>

    <div class='summary'>
    <div class='card'><div class='card-label'>Net Worth</div><div class='card-value'>{_fmt_k(nw)}</div></div>
    <div class='card'><div class='card-label'>Portfolio</div><div class='card-value'>{_fmt_k(total_inv)}</div></div>
    <div class='card'><div class='card-label'>Home Equity</div><div class='card-value'>{_fmt_k(a["home_current_value"] - status["current_balance"])}</div></div>
    <div class='card'><div class='card-label'>Emergency Fund</div><div class='card-value'>{_fmt_k(a["emergency_fund_balance"])}</div></div>
    </div>

    <h2>Assets</h2>
    <table>
    <tr><th>Asset</th><th>Value</th></tr>
    <tr><td>Home Value</td><td>{_fmt_k(a["home_current_value"])}</td></tr>
    <tr><td>Investments</td><td>{_fmt_k(total_inv)}</td></tr>
    <tr><td>HYSA (Emergency Fund)</td><td>{_fmt_k(a["emergency_fund_balance"])}</td></tr>
    <tr><td>Sinking Fund</td><td>{_fmt_k(sinking)}</td></tr>
    <tr><td>Checking / Savings</td><td>{_fmt_k(a["checking_savings_balance"])}</td></tr>
    <tr><th>Total Assets</th><th>{_fmt_k(total_assets)}</th></tr>
    </table>

    <h2>Investment Accounts</h2>
    <table>
    <tr><th>Account</th><th>Type</th><th>Balance</th></tr>
    {"".join(f'<tr><td>{ac["label"]}</td><td>{ac["account_type"]}</td><td>{_fmt_k(ac["balance"])}</td></tr>' for ac in a["investment_accounts"] if ac["balance"] > 0)}
    </table>

    <h2>Liabilities</h2>
    <table>
    <tr><th>Liability</th><th>Balance</th></tr>
    <tr><td>Mortgage</td><td class='negative'>{_fmt_k(status["current_balance"])}</td></tr>
    {"".join(f'<tr><td>{d["name"]}</td><td class="negative">{_fmt_k(d["balance"])}</td></tr>' for d in a["other_debts"])}
    <tr><th>Total Liabilities</th><th class='negative'>{_fmt_k(total_liab)}</th></tr>
    </table>

    <p style='margin-top:30px;color:#94a3b8;font-size:12px'>
    Generated from {a['dashboard_name']} on {report_date}
    </p>
    </body></html>
    """

    st.download_button(
        "Download Report (HTML)",
        data=html_report,
        file_name=f"financial_snapshot_{date.today().isoformat()}.html",
        mime="text/html",
    )


st.title(f"💰 {a['dashboard_name']}")

# ── Tabs ──────────────────────────────────────────────────────────────────────
t0, t1, t2, t3, t4, t5, t6, t7 = st.tabs([
    "📊 Dashboard",
    "⚙️ Setup",
    "🏡 Home",
    "💵 Budget",
    "📈 Investments",
    "🏦 Net Worth",
    "🔮 Projections",
    "💸 Money Flow",
])

with t0: dashboard.render()
with t1: setup.render()
with t2: home.render()
with t3: budget.render()
with t4: investments.render()
with t5: net_worth.render()
with t6: projections.render()
with t7: money_flow.render()

# ── Auto-save to SQLite on every interaction ──────────────────────────────────
save_assumptions(st.session_state.assumptions)

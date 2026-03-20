import streamlit as st
import copy
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

a = st.session_state.assumptions
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

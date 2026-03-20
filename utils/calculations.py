import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta

# ── 2025 Federal Tax Brackets (taxable income after standard deduction) ───────
_TAX_BRACKETS = {
    "Single": [
        (11_925, 0.10), (48_475, 0.12), (103_350, 0.22),
        (197_300, 0.24), (250_525, 0.32), (626_350, 0.35), (float("inf"), 0.37),
    ],
    "Married Filing Jointly": [
        (23_850, 0.10), (96_950, 0.12), (206_700, 0.22),
        (394_600, 0.24), (501_050, 0.32), (751_600, 0.35), (float("inf"), 0.37),
    ],
    "Married Filing Separately": [
        (11_925, 0.10), (48_475, 0.12), (103_350, 0.22),
        (197_300, 0.24), (250_525, 0.32), (375_800, 0.35), (float("inf"), 0.37),
    ],
    "Head of Household": [
        (17_000, 0.10), (64_850, 0.12), (103_350, 0.22),
        (197_300, 0.24), (250_500, 0.32), (626_350, 0.35), (float("inf"), 0.37),
    ],
}

# ── 2025 Standard Deductions ──────────────────────────────────────────────────
_STANDARD_DEDUCTIONS = {
    "Single": 15_000,
    "Married Filing Jointly": 30_000,
    "Married Filing Separately": 15_000,
    "Head of Household": 22_500,
}

_SS_WAGE_BASE = 176_100  # 2025 Social Security wage base


def calc_federal_tax(gross: float, filing_status: str) -> float:
    """Estimate 2025 federal income tax using the standard deduction."""
    deduction = _STANDARD_DEDUCTIONS.get(filing_status, 15_000)
    taxable = max(0.0, gross - deduction)
    brackets = _TAX_BRACKETS.get(filing_status, _TAX_BRACKETS["Single"])
    tax, prev = 0.0, 0.0
    for limit, rate in brackets:
        if taxable <= prev:
            break
        tax += (min(taxable, limit) - prev) * rate
        prev = limit
    return tax


def calc_fica(gross: float) -> float:
    """Social Security (6.2%) + Medicare (1.45%) + Additional Medicare (0.9% > $200k)."""
    ss = min(gross, _SS_WAGE_BASE) * 0.062
    medicare = gross * 0.0145 + max(0.0, gross - 200_000) * 0.009
    return ss + medicare


def calc_take_home_monthly(gross: float, filing_status: str,
                           state_tax_pct: float = 5.0) -> float:
    """Estimate monthly take-home after federal tax, FICA, and state income tax."""
    if gross <= 0:
        return 0.0
    federal = calc_federal_tax(gross, filing_status)
    fica = calc_fica(gross)
    state = gross * state_tax_pct / 100
    return max(0.0, gross - federal - fica - state) / 12


# ── 2025 IRS Contribution Limits ──────────────────────────────────────────────
ACCOUNT_LIMITS = {
    "401k":      {"base": 23_500, "catchup": 31_000},   # catchup age 50+
    "Roth 401k": {"base": 23_500, "catchup": 31_000},
    "Trad IRA":  {"base":  7_000, "catchup":  8_000},
    "Roth IRA":  {"base":  7_000, "catchup":  8_000},
    "HSA":       {"base":  4_300, "catchup":  5_300},   # catchup age 55+
    "Brokerage": {"base": None,   "catchup": None},     # no limit
}


def calc_monthly_payment(principal: float, annual_rate_pct: float, years: int) -> float:
    if principal <= 0:
        return 0.0
    r = annual_rate_pct / 100 / 12
    n = years * 12
    if r == 0:
        return principal / n
    return principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)


def build_amortization(
    principal: float,
    annual_rate_pct: float,
    years: int,
    start_date: date,
) -> pd.DataFrame:
    """Full amortization schedule. Each row = one month's payment."""
    r = annual_rate_pct / 100 / 12
    payment = calc_monthly_payment(principal, annual_rate_pct, years)
    rows = []
    balance = float(principal)
    cum_interest = 0.0
    # First payment is one month after the loan start date
    current_date = start_date + relativedelta(months=1)

    for month_num in range(1, years * 12 + 1):
        interest = balance * r
        principal_paid = min(payment - interest, balance)
        balance = max(balance - principal_paid, 0.0)
        cum_interest += interest
        rows.append({
            "month_num":      month_num,
            "date":           current_date,
            "year":           current_date.year,
            "payment":        round(payment, 2),
            "principal_paid": round(principal_paid, 2),
            "interest_paid":  round(interest, 2),
            "balance":        round(balance, 2),
            "cum_interest":   round(cum_interest, 2),
        })
        current_date += relativedelta(months=1)
        if balance <= 0:
            break

    return pd.DataFrame(rows)


def get_loan_status(amort_df: pd.DataFrame, as_of: date) -> dict:
    """Current loan metrics as of a given date."""
    past = amort_df[amort_df["date"] <= as_of]
    future = amort_df[amort_df["date"] > as_of]

    if past.empty:
        original_balance = amort_df.iloc[0]["balance"] + amort_df.iloc[0]["principal_paid"]
        return {
            "current_balance":          original_balance,
            "months_paid":              0,
            "months_remaining":         len(amort_df),
            "payoff_date":              amort_df.iloc[-1]["date"],
            "total_interest_paid":      0.0,
            "total_interest_remaining": amort_df["interest_paid"].sum(),
        }

    current = past.iloc[-1]
    return {
        "current_balance":          current["balance"],
        "months_paid":              len(past),
        "months_remaining":         len(future),
        "payoff_date":              amort_df.iloc[-1]["date"],
        "total_interest_paid":      current["cum_interest"],
        "total_interest_remaining": future["interest_paid"].sum(),
    }

from datetime import date

DEFAULT_ASSUMPTIONS = {
    # ── Personal ──────────────────────────────────────────────────────────────
    "dashboard_name": "My Finance Dashboard",
    "age": 35,
    "retirement_age": 65,
    "w2_retirement_age": 55,          # age W2 income trails off (semi-retirement)
    "filing_status": "Married Filing Jointly",

    # ── Income ────────────────────────────────────────────────────────────────
    "gross_income": 100_000,
    "state_tax_pct": 5.0,            # % state income tax (varies by state)
    "take_home_monthly": 6_250,      # auto-calculated from gross unless overridden
    "spouse_gross_income": 0,
    "spouse_take_home_monthly": 0,
    "income_growth_pct": 3.0,
    "annual_bonus": 0,               # Q1 bonus/yr invested into portfolio (0 = none)
    "lp_double_years": 0,            # years from now when LP income doubles (e.g. inheritance event); 0 = never
    "lp_jb_pct": 85,                 # % of LP distributions routed to Joint Brokerage each quarter

    # ── Home & Mortgage ───────────────────────────────────────────────────────
    "home_current_value": 350_000,
    "loan_original_amount": 240_000,
    "loan_interest_rate": 6.5,
    "loan_term_years": 30,
    "loan_start_date": date(2020, 1, 1),
    "property_tax_rate": 1.2,        # % of home value per year
    "home_insurance_annual": 1_500,
    "hoa_monthly": 0,
    "maintenance_pct": 1.0,          # % of home value per year
    "home_appreciation_pct": 3.0,

    # ── Emergency Fund & Cash ─────────────────────────────────────────────────
    "emergency_fund_balance": 15_000,
    "emergency_fund_target_months": 6,
    "sinking_fund_balance": 0,           # Earmarked savings (car, vacation, repairs, etc.)
    "checking_savings_balance": 10_000,  # General savings / HYSA remainder

    # ── Other Debts ───────────────────────────────────────────────────────────
    # Each: {name, balance, rate_pct, monthly_payment}
    "other_debts": [],

    # ── Investment Accounts ───────────────────────────────────────────────────
    # Each: {account_type, label, balance, monthly_contribution,
    #         employer_match_pct, employer_match_ceiling_pct, _id}
    "investment_accounts": [
        {
            "account_type": "401k",
            "label": "Company 401k",
            "balance": 50_000,
            "monthly_contribution": 1_000,
            "employer_match_pct": 50,
            "employer_match_ceiling_pct": 6,
            "_id": 0,
            # Each holding: {ticker, shares, sector, _id}
            "holdings": [],
        },
        {
            "account_type": "Roth IRA",
            "label": "Roth IRA",
            "balance": 25_000,
            "monthly_contribution": 583,
            "employer_match_pct": 0,
            "employer_match_ceiling_pct": 0,
            "_id": 1,
            "holdings": [],
        },
    ],

    # ── Monthly Budget ────────────────────────────────────────────────────────
    "budget": {
        "Groceries": 600,
        "Dining Out": 300,
        "Entertainment & Hobbies": 200,
        "Transportation (gas/parking)": 300,
        "Auto Insurance": 150,
        "Utilities (electric/gas/water)": 200,
        "Internet & Phone": 150,
        "Subscriptions (streaming/etc)": 80,
        "Healthcare & Pharmacy": 200,
        "Clothing & Shopping": 150,
        "Personal Care": 100,
        "Travel & Vacations": 250,
        "Gifts & Donations": 100,
        "Pet Care": 0,
        "Childcare & Education": 0,
        "Miscellaneous": 150,
    },

    # ── Projection Assumptions ────────────────────────────────────────────────
    "investment_return_pct": 7.0,
    "inflation_pct": 3.0,
    "social_security_monthly": 2_000,
    "social_security_start_age": 67,
    "retirement_monthly_expenses": 5_000,  # in today's dollars
}

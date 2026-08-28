import streamlit as st
import pandas as pd
import numpy as np
import calendar
from datetime import date, timedelta

# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="Home Loan Wealth Calculator",
    page_icon="🏠",
    layout="wide",
)

# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>
    .metric-card {
        padding: 16px;
        border-radius: 12px;
        border: 1px solid rgba(128,128,128,.25);
        margin-bottom: 10px;
    }

    .section-title {
        font-size: 1.35rem;
        font-weight: 700;
        margin-top: 20px;
        margin-bottom: 10px;
    }

    .small-note {
        color: #777;
        font-size: 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# HELPERS
# ============================================================

def money(x):
    if x is None or not np.isfinite(float(x)):
        return "₹0"
    return f"₹{float(x):,.0f}"


def money2(x):
    if x is None or not np.isfinite(float(x)):
        return "₹0"
    return f"₹{float(x):,.2f}"


def add_months(d, months):
    """
    Correctly handles dates such as:
    31 Jan -> 28 Feb
    31 Jan -> 29 Feb in leap year
    """

    month_index = d.month - 1 + months

    year = d.year + month_index // 12

    month = month_index % 12 + 1

    day = min(
        d.day,
        calendar.monthrange(year, month)[1]
    )

    return date(year, month, day)


def month_end(d):
    return date(
        d.year,
        d.month,
        calendar.monthrange(
            d.year,
            d.month
        )[1]
    )


def calculate_emi(
    principal,
    annual_rate,
    tenure_months
):

    if tenure_months <= 0:
        return 0

    if annual_rate == 0:
        return principal / tenure_months

    r = annual_rate / 100 / 12

    return (
        principal
        * r
        * (1 + r) ** tenure_months
        / (
            (1 + r) ** tenure_months
            - 1
        )
    )


# ============================================================
# BUILD EMI PAYMENT DATES
# ============================================================

def build_payment_dates(
    start_date,
    tenure_months
):

    dates = []

    for i in range(1, tenure_months + 1):

        dates.append(
            add_months(
                start_date,
                i
            )
        )

    return dates


# ============================================================
# LOAN ENGINE
# ============================================================

def simulate_loan(
    loan_amount,
    annual_rate,
    tenure_months,
    start_date,
    prepayments=None,
    maxgain_transactions=None,
    emi=None,
    allow_emi_recast=False,
):

    prepayments = prepayments or {}

    maxgain_transactions = (
        maxgain_transactions or {}
    )

    if emi is None:

        emi = calculate_emi(
            loan_amount,
            annual_rate,
            tenure_months
        )

    payment_dates = set(
        build_payment_dates(
            start_date,
            tenure_months
        )
    )

    loan_balance = float(
        loan_amount
    )

    maxgain_balance = 0.0

    total_interest = 0.0

    total_interest_without_maxgain = 0.0

    total_prepayment = 0.0

    total_emi_paid = 0.0

    total_maxgain_deposits = 0.0

    total_maxgain_withdrawals = 0.0

    total_maxgain_saving = 0.0

    current_emi = float(emi)

    rows = []

    current_date = start_date

    day_number = 0

    max_days = (
        tenure_months * 31
        + 730
    )

    while (
        loan_balance > 0.01
        and day_number < max_days
    ):

        day_number += 1

        # ----------------------------------------------------
        # TRANSACTIONS BEFORE DAILY INTEREST
        # ----------------------------------------------------

        mg_deposit = 0.0
        mg_withdrawal = 0.0

        if current_date in maxgain_transactions:

            transactions = (
                maxgain_transactions[
                    current_date
                ]
            )

            for transaction in transactions:

                amount = float(
                    transaction["amount"]
                )

                if amount <= 0:
                    continue

                if (
                    transaction["type"]
                    == "Deposit"
                ):

                    maxgain_balance += amount

                    mg_deposit += amount

                    total_maxgain_deposits += amount

                else:

                    withdrawal = min(
                        amount,
                        maxgain_balance
                    )

                    maxgain_balance -= (
                        withdrawal
                    )

                    mg_withdrawal += (
                        withdrawal
                    )

                    total_maxgain_withdrawals += (
                        withdrawal
                    )

        # ----------------------------------------------------
        # DAILY INTEREST
        # ----------------------------------------------------

        daily_rate = (
            annual_rate
            / 100
            / 365
        )

        opening_balance = loan_balance

        effective_balance = max(
            loan_balance
            - maxgain_balance,
            0
        )

        interest_without_maxgain = (
            loan_balance
            * daily_rate
        )

        daily_interest = (
            effective_balance
            * daily_rate
        )

        daily_saving = (
            interest_without_maxgain
            - daily_interest
        )

        total_interest_without_maxgain += (
            interest_without_maxgain
        )

        total_interest += daily_interest

        total_maxgain_saving += (
            daily_saving
        )

        # ----------------------------------------------------
        # EMI
        # ----------------------------------------------------

        emi_payment = 0.0

        principal_component = 0.0

        if current_date in payment_dates:

            emi_payment = min(
                current_emi,
                loan_balance
                + daily_interest
            )

            principal_component = max(
                emi_payment
                - daily_interest,
                0
            )

            principal_component = min(
                principal_component,
                loan_balance
            )

            loan_balance -= (
                principal_component
            )

            total_emi_paid += (
                emi_payment
            )

            # Optional EMI recast
            if allow_emi_recast:

                remaining_months = max(
                    tenure_months
                    - len(
                        [
                            x
                            for x in payment_dates
                            if x > current_date
                        ]
                    ),
                    1
                )

                current_emi = calculate_emi(
                    loan_balance,
                    annual_rate,
                    remaining_months
                )

        # ----------------------------------------------------
        # PREPAYMENT
        # ----------------------------------------------------

        prepayment = 0.0

        if current_date in prepayments:

            requested = float(
                prepayments[
                    current_date
                ]
            )

            prepayment = min(
                requested,
                loan_balance
            )

            loan_balance -= (
                prepayment
            )

            total_prepayment += (
                prepayment
            )

        # ----------------------------------------------------
        # END OF DAY
        # ----------------------------------------------------

        rows.append(
            {
                "Date": current_date,

                "Day": day_number,

                "Opening Loan Balance":
                    opening_balance,

                "EMI":
                    emi_payment,

                "Interest":
                    daily_interest,

                "Principal":
                    principal_component,

                "Prepayment":
                    prepayment,

                "Loan Balance":
                    max(
                        loan_balance,
                        0
                    ),

                "MaxGain Deposit":
                    mg_deposit,

                "MaxGain Withdrawal":
                    mg_withdrawal,

                "MaxGain Balance":
                    maxgain_balance,

                "Effective Interest Balance":
                    effective_balance,

                "Interest Without MaxGain":
                    interest_without_maxgain,

                "MaxGain Interest Saving":
                    daily_saving,
            }
        )

        current_date += timedelta(
            days=1
        )

    df = pd.DataFrame(rows)

    if len(df):

        closure_date = (
            df.iloc[-1]["Date"]
        )

    else:

        closure_date = start_date

    return {
        "emi": emi,

        "total_interest":
            total_interest,

        "interest_without_maxgain":
            total_interest_without_maxgain,

        "maxgain_interest_saving":
            total_maxgain_saving,

        "total_prepayment":
            total_prepayment,

        "total_emi":
            total_emi_paid,

        "maxgain_deposits":
            total_maxgain_deposits,

        "maxgain_withdrawals":
            total_maxgain_withdrawals,

        "final_maxgain_balance":
            maxgain_balance,

        "closure_date":
            closure_date,

        "df":
            df,
    }


# ============================================================
# SESSION STATE
# ============================================================

if "prepayments" not in st.session_state:

    st.session_state.prepayments = []


if "maxgain_transactions" not in st.session_state:

    st.session_state.maxgain_transactions = []


# ============================================================
# FUNCTIONS
# ============================================================

def add_prepayment():

    st.session_state.prepayments.append(
        {
            "date": date.today(),
            "amount": 10000.0
        }
    )


def add_maxgain_transaction():

    st.session_state.maxgain_transactions.append(
        {
            "date": date.today(),
            "type": "Deposit",
            "amount": 10000.0
        }
    )


# ============================================================
# HEADER
# ============================================================

st.title(
    "🏠 Home Loan Wealth Calculator"
)

st.caption(
    "Daily interest • Prepayment • MaxGain • "
    "Loan closure • Interest savings"
)


# ============================================================
# LOAN INPUT
# ============================================================

st.markdown(
    '<div class="section-title">'
    '1. Loan Details'
    '</div>',
    unsafe_allow_html=True
)

c1, c2, c3, c4 = st.columns(4)

with c1:

    loan_amount = st.number_input(
        "Loan Amount (₹)",
        min_value=10000.0,
        value=5000000.0,
        step=10000.0
    )

with c2:

    annual_rate = st.number_input(
        "Interest Rate (%)",
        min_value=0.0,
        max_value=30.0,
        value=8.0,
        step=0.05
    )

with c3:

    tenure_years = st.number_input(
        "Tenure (Years)",
        min_value=1,
        max_value=40,
        value=20,
        step=1
    )

with c4:

    start_date = st.date_input(
        "Loan Start Date",
        value=date.today()
    )


tenure_months = (
    int(tenure_years)
    * 12
)


# ============================================================
# EMI SETTINGS
# ============================================================

st.markdown(
    '<div class="section-title">'
    '2. EMI Settings'
    '</div>',
    unsafe_allow_html=True
)

emi = calculate_emi(
    loan_amount,
    annual_rate,
    tenure_months
)

e1, e2 = st.columns(2)

with e1:

    st.metric(
        "Calculated EMI",
        money(emi)
    )

with e2:

    allow_emi_recast = st.checkbox(
        "Recalculate EMI after prepayment",
        value=False,
        help=(
            "Keep OFF if your bank normally "
            "keeps EMI unchanged and reduces tenure."
        )
    )


# ============================================================
# NORMAL PREPAYMENTS
# ============================================================

st.markdown(
    '<div class="section-title">'
    '3. Normal Loan Prepayments'
    '</div>',
    unsafe_allow_html=True
)

st.write(
    "A normal prepayment permanently reduces "
    "your outstanding loan."
)

if st.button(
    "➕ Add Prepayment"
):

    add_prepayment()

    st.rerun()


if st.session_state.prepayments:

    for i, item in enumerate(
        st.session_state.prepayments
    ):

        c1, c2, c3 = st.columns(
            [2, 2, 0.5]
        )

        with c1:

            item["date"] = st.date_input(
                "Date",
                value=item["date"],
                key=f"prep_date_{i}"
            )

        with c2:

            item["amount"] = st.number_input(
                "Amount",
                min_value=0.0,
                value=float(
                    item["amount"]
                ),
                step=1000.0,
                key=f"prep_amount_{i}"
            )

        with c3:

            if st.button(
                "🗑️",
                key=f"prep_delete_{i}"
            ):

                st.session_state.prepayments.pop(
                    i
                )

                st.rerun()

else:

    st.info(
        "No normal prepayments added."
    )


# ============================================================
# MAXGAIN
# ============================================================

st.markdown(
    '<div class="section-title">'
    '4. MaxGain / OD Account'
    '</div>',
    unsafe_allow_html=True
)

st.write(
    "Deposits remain accessible but reduce the "
    "balance on which daily interest is calculated."
)

if st.button(
    "➕ Add MaxGain Transaction"
):

    add_maxgain_transaction()

    st.rerun()


if st.session_state.maxgain_transactions:

    for i, item in enumerate(
        st.session_state.maxgain_transactions
    ):

        c1, c2, c3, c4 = st.columns(
            [2, 1.5, 2, 0.5]
        )

        with c1:

            item["date"] = st.date_input(
                "Date",
                value=item["date"],
                key=f"mg_date_{i}"
            )

        with c2:

            item["type"] = st.selectbox(
                "Type",
                [
                    "Deposit",
                    "Withdrawal"
                ],
                index=(
                    0
                    if item["type"]
                    == "Deposit"
                    else 1
                ),
                key=f"mg_type_{i}"
            )

        with c3:

            item["amount"] = st.number_input(
                "Amount",
                min_value=0.0,
                value=float(
                    item["amount"]
                ),
                step=1000.0,
                key=f"mg_amount_{i}"
            )

        with c4:

            if st.button(
                "🗑️",
                key=f"mg_delete_{i}"
            ):

                st.session_state.maxgain_transactions.pop(
                    i
                )

                st.rerun()

else:

    st.info(
        "No MaxGain transactions added."
    )


# ============================================================
# CONVERT INPUTS
# ============================================================

prepayment_dict = {}

for item in st.session_state.prepayments:

    amount = float(
        item["amount"]
    )

    if amount <= 0:
        continue

    d = item["date"]

    prepayment_dict[d] = (
        prepayment_dict.get(
            d,
            0
        )
        + amount
    )


maxgain_dict = {}

for item in (
    st.session_state.maxgain_transactions
):

    amount = float(
        item["amount"]
    )

    if amount <= 0:
        continue

    d = item["date"]

    if d not in maxgain_dict:

        maxgain_dict[d] = []

    maxgain_dict[d].append(
        {
            "type": item["type"],
            "amount": amount
        }
    )


# ============================================================
# CALCULATE THREE SCENARIOS
# ============================================================

baseline = simulate_loan(
    loan_amount,
    annual_rate,
    tenure_months,
    start_date
)

prepay_scenario = simulate_loan(
    loan_amount,
    annual_rate,
    tenure_months,
    start_date,
    prepayments=prepayment_dict,
    allow_emi_recast=allow_emi_recast
)

maxgain_scenario = simulate_loan(
    loan_amount,
    annual_rate,
    tenure_months,
    start_date,
    maxgain_transactions=maxgain_dict,
    allow_emi_recast=False
)

combined_scenario = simulate_loan(
    loan_amount,
    annual_rate,
    tenure_months,
    start_date,
    prepayments=prepayment_dict,
    maxgain_transactions=maxgain_dict,
    allow_emi_recast=allow_emi_recast
)


# ============================================================
# RESULTS
# ============================================================

st.markdown(
    '<div class="section-title">'
    '5. Scenario Comparison'
    '</div>',
    unsafe_allow_html=True
)

comparison = pd.DataFrame(
    {
        "Metric": [
            "EMI",
            "Total Interest",
            "Interest Saved",
            "Closure Date",
            "Days Saved",
            "Total Prepayment",
            "MaxGain Interest Saving",
            "Final MaxGain Balance",
        ],

        "Normal Loan": [
            baseline["emi"],
            baseline["total_interest"],
            0,
            baseline["closure_date"],
            0,
            0,
            0,
            0,
        ],

        "Prepayment": [
            prepay_scenario["emi"],
            prepay_scenario["total_interest"],
            baseline["total_interest"]
            - prepay_scenario[
                "total_interest"
            ],
            prepay_scenario[
                "closure_date"
            ],
            (
                baseline["closure_date"]
                - prepay_scenario[
                    "closure_date"
                ]
            ).days,
            prepay_scenario[
                "total_prepayment"
            ],
            0,
            0,
        ],

        "MaxGain": [
            maxgain_scenario["emi"],
            maxgain_scenario["total_interest"],
            baseline["total_interest"]
            - maxgain_scenario[
                "total_interest"
            ],
            maxgain_scenario[
                "closure_date"
            ],
            (
                baseline["closure_date"]
                - maxgain_scenario[
                    "closure_date"
                ]
            ).days,
            0,
            maxgain_scenario[
                "maxgain_interest_saving"
            ],
            maxgain_scenario[
                "final_maxgain_balance"
            ],
        ],
    }
)

display_comparison = comparison.copy()

for col in [
    "Normal Loan",
    "Prepayment",
    "MaxGain"
]:

    for i in [
        0,
        1,
        2,
        5,
        6,
        7
    ]:

        value = display_comparison.loc[
            i,
            col
        ]

        if isinstance(
            value,
            (float, int, np.number)
        ):

            display_comparison.loc[
                i,
                col
            ] = money(value)

display_comparison.loc[
    3
] = display_comparison.loc[
    3
].apply(
    lambda x:
    x.strftime("%d %b %Y")
    if hasattr(
        x,
        "strftime"
    )
    else x
)

display_comparison.loc[
    4
] = display_comparison.loc[
    4
].apply(
    lambda x:
    f"{int(x)} days"
    if isinstance(
        x,
        (float, int, np.number)
    )
    else x
)

st.dataframe(
    display_comparison,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# COMBINED RESULT
# ============================================================

st.markdown(
    '<div class="section-title">'
    '6. Combined Strategy'
    '</div>',
    unsafe_allow_html=True
)

combined_interest_saved = (
    baseline["total_interest"]
    - combined_scenario[
        "total_interest"
    ]
)

combined_days_saved = (
    baseline["closure_date"]
    - combined_scenario[
        "closure_date"
    ]
).days

a1, a2, a3, a4 = st.columns(4)

with a1:

    st.metric(
        "Interest Saved",
        money(
            combined_interest_saved
        )
    )

with a2:

    st.metric(
        "Days Saved",
        f"{max(combined_days_saved, 0):,}"
    )

with a3:

    st.metric(
        "Prepaid",
        money(
            combined_scenario[
                "total_prepayment"
            ]
        )
    )

with a4:

    st.metric(
        "MaxGain Balance",
        money(
            combined_scenario[
                "final_maxgain_balance"
            ]
        )
    )


# ============================================================
# STRATEGY INSIGHT
# ============================================================

st.markdown(
    '<div class="section-title">'
    '7. What Is Better?'
    '</div>',
    unsafe_allow_html=True
)

prepay_saving = (
    baseline["total_interest"]
    - prepay_scenario[
        "total_interest"
    ]
)

maxgain_saving = (
    baseline["total_interest"]
    - maxgain_scenario[
        "total_interest"
    ]
)

if prepay_saving > maxgain_saving:

    st.success(
        f"Based purely on interest cost, "
        f"your entered prepayment strategy saves "
        f"{money(prepay_saving - maxgain_saving)} "
        f"more interest than the MaxGain strategy."
    )

elif maxgain_saving > prepay_saving:

    st.success(
        f"Based purely on interest cost, "
        f"your entered MaxGain strategy saves "
        f"{money(maxgain_saving - prepay_saving)} "
        f"more interest."
    )

else:

    st.info(
        "The two strategies produce approximately "
        "the same interest saving."
    )

st.caption(
    "MaxGain has an additional advantage: "
    "the deposited money remains accessible, unlike "
    "a permanent loan prepayment."
)


# ============================================================
# BALANCE CHART
# ============================================================

st.markdown(
    '<div class="section-title">'
    '8. Loan Balance Comparison'
    '</div>',
    unsafe_allow_html=True
)

b1 = baseline["df"].copy()

b2 = prepay_scenario["df"].copy()

b3 = maxgain_scenario["df"].copy()

b4 = combined_scenario["df"].copy()

max_len = max(
    len(b1),
    len(b2),
    len(b3),
    len(b4)
)

chart = pd.DataFrame()

if len(b1):

    chart["Normal Loan"] = (
        b1["Loan Balance"]
        .reindex(
            range(max_len)
        )
        .ffill()
    )

if len(b2):

    chart["Prepayment"] = (
        b2["Loan Balance"]
        .reindex(
            range(max_len)
        )
        .ffill()
    )

if len(b3):

    chart["MaxGain"] = (
        b3["Loan Balance"]
        .reindex(
            range(max_len)
        )
        .ffill()
    )

if len(b4):

    chart["Combined"] = (
        b4["Loan Balance"]
        .reindex(
            range(max_len)
        )
        .ffill()
    )

chart.index.name = "Day"

st.line_chart(
    chart
)


# ============================================================
# MAXGAIN CHART
# ============================================================

if len(maxgain_scenario["df"]):

    st.markdown(
        '<div class="section-title">'
        '9. MaxGain Account vs Interest-Bearing Balance'
        '</div>',
        unsafe_allow_html=True
    )

    mg_chart = (
        maxgain_scenario["df"][
            [
                "MaxGain Balance",
                "Effective Interest Balance"
            ]
        ]
    )

    st.line_chart(
        mg_chart
    )


# ============================================================
# CUMULATIVE INTEREST
# ============================================================

st.markdown(
    '<div class="section-title">'
    '10. Cumulative Interest'
    '</div>',
    unsafe_allow_html=True
)

interest_chart = pd.DataFrame()

if len(b1):

    interest_chart[
        "Normal Loan"
    ] = (
        b1["Interest"]
        .cumsum()
    )

if len(b2):

    interest_chart[
        "Prepayment"
    ] = (
        b2["Interest"]
        .cumsum()
    )

if len(b3):

    interest_chart[
        "MaxGain"
    ] = (
        b3["Interest"]
        .cumsum()
    )

if len(b4):

    interest_chart[
        "Combined"
    ] = (
        b4["Interest"]
        .cumsum()
    )

st.line_chart(
    interest_chart
)


# ============================================================
# MONTHLY SUMMARY
# ============================================================

st.markdown(
    '<div class="section-title">'
    '11. Monthly Summary'
    '</div>',
    unsafe_allow_html=True
)

df = combined_scenario["df"]

if len(df):

    monthly = (
        df
        .assign(
            Month=df[
                "Date"
            ].apply(
                lambda x:
                x.strftime(
                    "%Y-%m"
                )
            )
        )
        .groupby("Month")
        .agg(
            {
                "EMI": "sum",
                "Interest": "sum",
                "Principal": "sum",
                "Prepayment": "sum",
                "MaxGain Deposit": "sum",
                "MaxGain Withdrawal": "sum",
                "MaxGain Interest Saving": "sum",
                "Loan Balance": "last",
                "MaxGain Balance": "last",
                "Effective Interest Balance": "last",
            }
        )
        .reset_index()
    )

    st.dataframe(
        monthly,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# TRANSACTION SUMMARY
# ============================================================

st.markdown(
    '<div class="section-title">'
    '12. Transaction Summary'
    '</div>',
    unsafe_allow_html=True
)

transactions = []

for item in (
    st.session_state.prepayments
):

    transactions.append(
        {
            "Date":
                item["date"],
            "Category":
                "Loan Prepayment",
            "Type":
                "Prepayment",
            "Amount":
                item["amount"]
        }
    )

for item in (
    st.session_state.maxgain_transactions
):

    transactions.append(
        {
            "Date":
                item["date"],
            "Category":
                "MaxGain",
            "Type":
                item["type"],
            "Amount":
                item["amount"]
        }
    )

if transactions:

    tx_df = pd.DataFrame(
        transactions
    ).sort_values(
        "Date"
    )

    st.dataframe(
        tx_df,
        use_container_width=True,
        hide_index=True
    )

else:

    st.caption(
        "No extra transactions entered."
    )


# ============================================================
# DAILY SCHEDULE
# ============================================================

with st.expander(
    "📅 View Full Daily Calculation"
):

    if len(df):

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# DOWNLOAD
# ============================================================

if len(df):

    csv = df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        "⬇️ Download Daily Schedule",
        data=csv,
        file_name=(
            "home_loan_daily_schedule.csv"
        ),
        mime="text/csv"
    )


# ============================================================
# HOW IT WORKS
# ============================================================

with st.expander(
    "ℹ️ Calculation Method"
):

    st.markdown(
        """
### Daily interest

The simulator calculates interest every day:

**Daily Interest = Effective Balance × Annual Rate ÷ 365**

### Normal prepayment

A normal prepayment permanently reduces the outstanding loan.

Example:

**15 Sep → ₹1,00,000**

The loan balance immediately falls by ₹1 lakh.

### MaxGain

A MaxGain deposit remains available to withdraw.

Example:

Loan outstanding:

**₹50 lakh**

MaxGain balance:

**₹5 lakh**

Interest-bearing balance:

**₹45 lakh**

If you withdraw ₹2 lakh later, the effective balance becomes:

**₹47 lakh**

### Important

Actual bank products can differ in:

- daily interest convention
- transaction cut-off time
- EMI date
- interest posting date
- MaxGain/OD rules
- withdrawal rules
- EMI vs tenure recalculation

Therefore this calculator should be treated as a **simulation**, not an exact bank statement.
        """
    )

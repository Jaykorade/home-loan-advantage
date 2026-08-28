import streamlit as st
import pandas as pd
import numpy as np
import calendar
from datetime import date, timedelta

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Home Loan Planner",
    page_icon="🏠",
    layout="wide",
)

# ============================================================
# HELPERS
# ============================================================

def money(value):
    try:
        return f"₹{float(value):,.0f}"
    except Exception:
        return "₹0"


def add_months(original_date, months):
    """
    Add months while preserving the original EMI day where possible.

    Examples:
        29-Aug-2026 -> 29-Sep-2026
        31-Jan-2026 -> 28-Feb-2026
        31-Jan-2028 -> 29-Feb-2028
    """

    month_index = (
        original_date.month - 1 + months
    )

    year = (
        original_date.year
        + month_index // 12
    )

    month = (
        month_index % 12
        + 1
    )

    day = min(
        original_date.day,
        calendar.monthrange(
            year,
            month
        )[1]
    )

    return date(
        year,
        month,
        day
    )


def calculate_emi(
    principal,
    annual_rate,
    months
):

    if months <= 0:
        return 0

    if annual_rate == 0:
        return principal / months

    monthly_rate = (
        annual_rate / 100 / 12
    )

    return (
        principal
        * monthly_rate
        * (1 + monthly_rate) ** months
        /
        (
            (1 + monthly_rate) ** months
            - 1
        )
    )


# ============================================================
# CONTRACTUAL EMI DATES
# ============================================================

def get_emi_dates(
    start_date,
    tenure_months
):

    return [
        add_months(
            start_date,
            i
        )
        for i in range(
            1,
            tenure_months + 1
        )
    ]


# ============================================================
# DAILY LOAN SIMULATOR
# ============================================================

def simulate_loan(
    loan_amount,
    annual_rate,
    tenure_months,
    start_date,
    prepayments=None,
    maxgain_transactions=None,
    emi=None,
):
    """
    Daily reducing balance model.

    IMPORTANT:

    - Tenure = exact number of scheduled EMI payments.
    - EMI dates are generated explicitly.
    - Daily interest is calculated using actual calendar days.
    - Normal prepayment permanently reduces loan balance.
    - MaxGain deposits offset the interest-bearing balance.
    - MaxGain money remains available for withdrawal.
    """

    prepayments = (
        prepayments
        if prepayments is not None
        else {}
    )

    maxgain_transactions = (
        maxgain_transactions
        if maxgain_transactions is not None
        else {}
    )

    if emi is None:

        emi = calculate_emi(
            loan_amount,
            annual_rate,
            tenure_months
        )

    emi_dates = get_emi_dates(
        start_date,
        tenure_months
    )

    emi_date_set = set(
        emi_dates
    )

    # --------------------------------------------------------
    # State
    # --------------------------------------------------------

    balance = float(
        loan_amount
    )

    maxgain_balance = 0.0

    total_interest = 0.0
    total_interest_without_maxgain = 0.0

    total_emi = 0.0
    total_prepayment = 0.0

    total_maxgain_deposit = 0.0
    total_maxgain_withdrawal = 0.0
    total_maxgain_saving = 0.0

    rows = []

    current_date = start_date

    # Safety limit:
    # contractual tenure + 2 years
    max_date = add_months(
        start_date,
        tenure_months + 24
    )

    while (
        current_date <= max_date
        and balance > 0.01
    ):

        # ====================================================
        # TRANSACTIONS AT START OF DAY
        # ====================================================

        mg_deposit = 0.0
        mg_withdrawal = 0.0

        transactions = (
            maxgain_transactions.get(
                current_date,
                []
            )
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

                total_maxgain_deposit += (
                    amount
                )

            elif (
                transaction["type"]
                == "Withdrawal"
            ):

                actual_withdrawal = min(
                    amount,
                    maxgain_balance
                )

                maxgain_balance -= (
                    actual_withdrawal
                )

                mg_withdrawal += (
                    actual_withdrawal
                )

                total_maxgain_withdrawal += (
                    actual_withdrawal
                )

        # ====================================================
        # DAILY INTEREST
        # ====================================================

        daily_rate = (
            annual_rate
            / 100
            / 365
        )

        opening_balance = balance

        effective_balance = max(
            balance
            - maxgain_balance,
            0
        )

        interest_without_maxgain = (
            balance
            * daily_rate
        )

        actual_interest = (
            effective_balance
            * daily_rate
        )

        maxgain_saving = (
            interest_without_maxgain
            - actual_interest
        )

        total_interest_without_maxgain += (
            interest_without_maxgain
        )

        total_interest += (
            actual_interest
        )

        total_maxgain_saving += (
            maxgain_saving
        )

        # ====================================================
        # EMI
        # ====================================================

        emi_paid = 0.0
        principal_paid = 0.0

        if current_date in emi_date_set:

            # EMI includes the day's interest
            payment_needed = (
                balance
                + actual_interest
            )

            emi_paid = min(
                float(emi),
                payment_needed
            )

            principal_paid = max(
                emi_paid
                - actual_interest,
                0
            )

            principal_paid = min(
                principal_paid,
                balance
            )

            balance -= (
                principal_paid
            )

            total_emi += (
                emi_paid
            )

        # ====================================================
        # NORMAL PREPAYMENT
        # ====================================================

        prepayment = 0.0

        if current_date in prepayments:

            requested = float(
                prepayments[
                    current_date
                ]
            )

            prepayment = min(
                requested,
                max(balance, 0)
            )

            balance -= (
                prepayment
            )

            total_prepayment += (
                prepayment
            )

        # ====================================================
        # STORE DAILY RECORD
        # ====================================================

        rows.append(
            {
                "Date":
                    current_date,

                "Day":
                    (
                        current_date
                        - start_date
                    ).days,

                "Opening Loan Balance":
                    opening_balance,

                "EMI":
                    emi_paid,

                "Interest":
                    actual_interest,

                "Principal":
                    principal_paid,

                "Prepayment":
                    prepayment,

                "Loan Balance":
                    max(
                        balance,
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
                    maxgain_saving,
            }
        )

        current_date += timedelta(
            days=1
        )

    # ========================================================
    # FINAL DATE
    # ========================================================

    df = pd.DataFrame(
        rows
    )

    if len(df):

        closure_date = (
            df.iloc[-1]["Date"]
        )

    else:

        closure_date = start_date

    return {
        "emi":
            emi,

        "total_interest":
            total_interest,

        "total_interest_without_maxgain":
            total_interest_without_maxgain,

        "total_emi":
            total_emi,

        "total_prepayment":
            total_prepayment,

        "maxgain_deposit":
            total_maxgain_deposit,

        "maxgain_withdrawal":
            total_maxgain_withdrawal,

        "maxgain_interest_saving":
            total_maxgain_saving,

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
# ADD FUNCTIONS
# ============================================================

def add_prepayment():

    st.session_state.prepayments.append(
        {
            "date":
                date.today(),

            "amount":
                10000.0,
        }
    )


def add_maxgain_transaction():

    st.session_state.maxgain_transactions.append(
        {
            "date":
                date.today(),

            "type":
                "Deposit",

            "amount":
                10000.0,
        }
    )


# ============================================================
# HEADER
# ============================================================

st.title(
    "🏠 Home Loan Planner"
)

st.caption(
    "Daily interest • Prepayment • MaxGain • "
    "Scenario comparison"
)


# ============================================================
# LOAN DETAILS
# ============================================================

st.header(
    "1. Loan Details"
)

c1, c2, c3, c4 = st.columns(4)

with c1:

    loan_amount = st.number_input(
        "Loan Amount (₹)",
        min_value=10000.0,
        value=5000000.0,
        step=10000.0,
    )

with c2:

    annual_rate = st.number_input(
        "Interest Rate (%)",
        min_value=0.0,
        max_value=30.0,
        value=8.0,
        step=0.05,
    )

with c3:

    tenure_years = st.number_input(
        "Tenure (Years)",
        min_value=1,
        max_value=40,
        value=20,
        step=1,
    )

with c4:

    start_date = st.date_input(
        "Loan Start Date",
        value=date.today(),
    )


tenure_months = int(
    tenure_years * 12
)


# ============================================================
# EMI
# ============================================================

emi = calculate_emi(
    loan_amount,
    annual_rate,
    tenure_months
)

contractual_emi_dates = (
    get_emi_dates(
        start_date,
        tenure_months
    )
)

contractual_end_date = (
    contractual_emi_dates[-1]
)


c1, c2, c3 = st.columns(3)

with c1:

    st.metric(
        "Monthly EMI",
        money(emi)
    )

with c2:

    st.metric(
        "Number of EMIs",
        tenure_months
    )

with c3:

    st.metric(
        "Contractual Final EMI",
        contractual_end_date.strftime(
            "%d %b %Y"
        )
    )


st.info(
    f"Your {tenure_years}-year loan has exactly "
    f"{tenure_months} scheduled EMIs. "
    f"The final scheduled EMI date is "
    f"**{contractual_end_date.strftime('%d %b %Y')}**."
)


# ============================================================
# NORMAL PREPAYMENTS
# ============================================================

st.header(
    "2. Normal Loan Prepayments"
)

st.write(
    "Enter the exact date and amount."
)

if st.button(
    "➕ Add Prepayment",
    key="add_prepayment_button"
):

    add_prepayment()

    st.rerun()


for i, item in enumerate(
    st.session_state.prepayments
):

    c1, c2, c3 = st.columns(
        [2, 2, 0.5]
    )

    with c1:

        item["date"] = st.date_input(
            "Prepayment Date",
            value=item["date"],
            key=f"prepayment_date_{i}"
        )

    with c2:

        item["amount"] = st.number_input(
            "Amount (₹)",
            min_value=0.0,
            value=float(
                item["amount"]
            ),
            step=1000.0,
            key=f"prepayment_amount_{i}"
        )

    with c3:

        if st.button(
            "🗑️",
            key=f"delete_prepayment_{i}"
        ):

            st.session_state.prepayments.pop(
                i
            )

            st.rerun()


# ============================================================
# MAXGAIN
# ============================================================

st.header(
    "3. MaxGain / OD Account"
)

st.write(
    "Deposits offset the loan for interest calculation "
    "while remaining available for withdrawal."
)

if st.button(
    "➕ Add MaxGain Transaction",
    key="add_maxgain_button"
):

    add_maxgain_transaction()

    st.rerun()


for i, item in enumerate(
    st.session_state.maxgain_transactions
):

    c1, c2, c3, c4 = st.columns(
        [2, 1.5, 2, 0.5]
    )

    with c1:

        item["date"] = st.date_input(
            "Transaction Date",
            value=item["date"],
            key=f"maxgain_date_{i}"
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
            key=f"maxgain_type_{i}"
        )

    with c3:

        item["amount"] = st.number_input(
            "Amount (₹)",
            min_value=0.0,
            value=float(
                item["amount"]
            ),
            step=1000.0,
            key=f"maxgain_amount_{i}"
        )

    with c4:

        if st.button(
            "🗑️",
            key=f"delete_maxgain_{i}"
        ):

            st.session_state.maxgain_transactions.pop(
                i
            )

            st.rerun()


# ============================================================
# PREPARE PREPAYMENTS
# ============================================================

prepayment_dict = {}

for item in st.session_state.prepayments:

    amount = float(
        item["amount"]
    )

    if amount <= 0:
        continue

    transaction_date = (
        item["date"]
    )

    prepayment_dict[
        transaction_date
    ] = (
        prepayment_dict.get(
            transaction_date,
            0
        )
        + amount
    )


# ============================================================
# PREPARE MAXGAIN
# ============================================================

maxgain_dict = {}

for item in (
    st.session_state.maxgain_transactions
):

    amount = float(
        item["amount"]
    )

    if amount <= 0:
        continue

    transaction_date = (
        item["date"]
    )

    if (
        transaction_date
        not in maxgain_dict
    ):

        maxgain_dict[
            transaction_date
        ] = []

    maxgain_dict[
        transaction_date
    ].append(
        {
            "type":
                item["type"],

            "amount":
                amount,
        }
    )


# ============================================================
# SCENARIOS
# ============================================================

baseline = simulate_loan(
    loan_amount=
        loan_amount,

    annual_rate=
        annual_rate,

    tenure_months=
        tenure_months,

    start_date=
        start_date,
)


prepayment_scenario = simulate_loan(
    loan_amount=
        loan_amount,

    annual_rate=
        annual_rate,

    tenure_months=
        tenure_months,

    start_date=
        start_date,

    prepayments=
        prepayment_dict,
)


maxgain_scenario = simulate_loan(
    loan_amount=
        loan_amount,

    annual_rate=
        annual_rate,

    tenure_months=
        tenure_months,

    start_date=
        start_date,

    maxgain_transactions=
        maxgain_dict,
)


combined_scenario = simulate_loan(
    loan_amount=
        loan_amount,

    annual_rate=
        annual_rate,

    tenure_months=
        tenure_months,

    start_date=
        start_date,

    prepayments=
        prepayment_dict,

    maxgain_transactions=
        maxgain_dict,
)


# ============================================================
# SCENARIO COMPARISON
# ============================================================

st.header(
    "4. Scenario Comparison"
)

def days_saved(
    scenario
):

    return max(
        (
            baseline[
                "closure_date"
            ]
            -
            scenario[
                "closure_date"
            ]
        ).days,
        0
    )


comparison = pd.DataFrame(
    [
        {
            "Metric":
                "Monthly EMI",

            "Normal Loan":
                baseline["emi"],

            "Prepayment":
                prepayment_scenario["emi"],

            "MaxGain":
                maxgain_scenario["emi"],

            "Combined":
                combined_scenario["emi"],
        },

        {
            "Metric":
                "Total Interest",

            "Normal Loan":
                baseline[
                    "total_interest"
                ],

            "Prepayment":
                prepayment_scenario[
                    "total_interest"
                ],

            "MaxGain":
                maxgain_scenario[
                    "total_interest"
                ],

            "Combined":
                combined_scenario[
                    "total_interest"
                ],
        },

        {
            "Metric":
                "Interest Saved",

            "Normal Loan":
                0,

            "Prepayment":
                baseline[
                    "total_interest"
                ]
                -
                prepayment_scenario[
                    "total_interest"
                ],

            "MaxGain":
                baseline[
                    "total_interest"
                ]
                -
                maxgain_scenario[
                    "total_interest"
                ],

            "Combined":
                baseline[
                    "total_interest"
                ]
                -
                combined_scenario[
                    "total_interest"
                ],
        },

        {
            "Metric":
                "Closure Date",

            "Normal Loan":
                baseline[
                    "closure_date"
                ],

            "Prepayment":
                prepayment_scenario[
                    "closure_date"
                ],

            "MaxGain":
                maxgain_scenario[
                    "closure_date"
                ],

            "Combined":
                combined_scenario[
                    "closure_date"
                ],
        },

        {
            "Metric":
                "Days Saved",

            "Normal Loan":
                0,

            "Prepayment":
                days_saved(
                    prepayment_scenario
                ),

            "MaxGain":
                days_saved(
                    maxgain_scenario
                ),

            "Combined":
                days_saved(
                    combined_scenario
                ),
        },

        {
            "Metric":
                "Normal Prepayment",

            "Normal Loan":
                0,

            "Prepayment":
                prepayment_scenario[
                    "total_prepayment"
                ],

            "MaxGain":
                0,

            "Combined":
                combined_scenario[
                    "total_prepayment"
                ],
        },

        {
            "Metric":
                "MaxGain Interest Saving",

            "Normal Loan":
                0,

            "Prepayment":
                0,

            "MaxGain":
                maxgain_scenario[
                    "maxgain_interest_saving"
                ],

            "Combined":
                combined_scenario[
                    "maxgain_interest_saving"
                ],
        },

        {
            "Metric":
                "Final MaxGain Balance",

            "Normal Loan":
                0,

            "Prepayment":
                0,

            "MaxGain":
                maxgain_scenario[
                    "final_maxgain_balance"
                ],

            "Combined":
                combined_scenario[
                    "final_maxgain_balance"
                ],
        },
    ]
)


display = comparison.copy()


for column in [
    "Normal Loan",
    "Prepayment",
    "MaxGain",
    "Combined",
]:

    for row in range(
        len(display)
    ):

        metric = display.loc[
            row,
            "Metric"
        ]

        value = display.loc[
            row,
            column
        ]

        if metric in [
            "Monthly EMI",
            "Total Interest",
            "Interest Saved",
            "Normal Prepayment",
            "MaxGain Interest Saving",
            "Final MaxGain Balance",
        ]:

            display.loc[
                row,
                column
            ] = money(value)

        elif metric == "Days Saved":

            display.loc[
                row,
                column
            ] = f"{int(value):,} days"

        elif metric == "Closure Date":

            display.loc[
                row,
                column
            ] = value.strftime(
                "%d %b %Y"
            )


st.dataframe(
    display,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# KEY RESULTS
# ============================================================

st.header(
    "5. Key Results"
)

interest_saved = (
    baseline[
        "total_interest"
    ]
    -
    combined_scenario[
        "total_interest"
    ]
)

saved_days = days_saved(
    combined_scenario
)

r1, r2, r3, r4 = st.columns(4)

with r1:

    st.metric(
        "Interest Saved",
        money(
            interest_saved
        )
    )

with r2:

    st.metric(
        "Days Saved",
        f"{saved_days:,}"
    )

with r3:

    st.metric(
        "Final Loan Closure",
        combined_scenario[
            "closure_date"
        ].strftime(
            "%d %b %Y"
        )
    )

with r4:

    st.metric(
        "MaxGain Balance",
        money(
            combined_scenario[
                "final_maxgain_balance"
            ]
        )
    )


# ============================================================
# LOAN BALANCE CHART
# ============================================================

st.header(
    "6. Loan Balance Comparison"
)

baseline_df = (
    baseline["df"]
)

prepay_df = (
    prepayment_scenario["df"]
)

maxgain_df = (
    maxgain_scenario["df"]
)

combined_df = (
    combined_scenario["df"]
)


chart = pd.DataFrame()

if len(baseline_df):

    chart["Normal Loan"] = (
        baseline_df[
            "Loan Balance"
        ]
        .reindex(
            range(
                max(
                    len(baseline_df),
                    len(prepay_df),
                    len(maxgain_df),
                    len(combined_df)
                )
            )
        )
        .ffill()
    )


if len(prepay_df):

    chart["Prepayment"] = (
        prepay_df[
            "Loan Balance"
        ]
        .reindex(
            chart.index
        )
        .ffill()
    )


if len(maxgain_df):

    chart["MaxGain"] = (
        maxgain_df[
            "Loan Balance"
        ]
        .reindex(
            chart.index
        )
        .ffill()
    )


if len(combined_df):

    chart["Combined"] = (
        combined_df[
            "Loan Balance"
        ]
        .reindex(
            chart.index
        )
        .ffill()
    )


chart.index.name = "Day"

st.line_chart(
    chart
)


# ============================================================
# MAXGAIN
# ============================================================

if len(maxgain_df):

    st.header(
        "7. MaxGain Account"
    )

    mg_chart = maxgain_df[
        [
            "MaxGain Balance",
            "Effective Interest Balance",
        ]
    ]

    st.line_chart(
        mg_chart
    )


# ============================================================
# CUMULATIVE INTEREST
# ============================================================

st.header(
    "8. Cumulative Interest"
)

interest_chart = pd.DataFrame()

if len(baseline_df):

    interest_chart[
        "Normal Loan"
    ] = (
        baseline_df[
            "Interest"
        ]
        .cumsum()
    )


if len(prepay_df):

    interest_chart[
        "Prepayment"
    ] = (
        prepay_df[
            "Interest"
        ]
        .cumsum()
        .reindex(
            interest_chart.index
        )
        .ffill()
    )


if len(maxgain_df):

    interest_chart[
        "MaxGain"
    ] = (
        maxgain_df[
            "Interest"
        ]
        .cumsum()
        .reindex(
            interest_chart.index
        )
        .ffill()
    )


if len(combined_df):

    interest_chart[
        "Combined"
    ] = (
        combined_df[
            "Interest"
        ]
        .cumsum()
        .reindex(
            interest_chart.index
        )
        .ffill()
    )


st.line_chart(
    interest_chart
)


# ============================================================
# MONTHLY SUMMARY
# ============================================================

st.header(
    "9. Monthly Summary"
)

if len(combined_df):

    monthly = (
        combined_df
        .assign(
            Month=
                combined_df[
                    "Date"
                ].apply(
                    lambda x:
                    x.strftime(
                        "%Y-%m"
                    )
                )
        )
        .groupby(
            "Month"
        )
        .agg(
            {
                "EMI":
                    "sum",

                "Interest":
                    "sum",

                "Principal":
                    "sum",

                "Prepayment":
                    "sum",

                "MaxGain Deposit":
                    "sum",

                "MaxGain Withdrawal":
                    "sum",

                "MaxGain Interest Saving":
                    "sum",

                "Loan Balance":
                    "last",

                "MaxGain Balance":
                    "last",

                "Effective Interest Balance":
                    "last",
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
# TRANSACTIONS
# ============================================================

st.header(
    "10. Transactions"
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
                "Loan",

            "Type":
                "Prepayment",

            "Amount":
                item["amount"],
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
                item["amount"],
        }
    )


if transactions:

    tx = pd.DataFrame(
        transactions
    ).sort_values(
        "Date"
    )

    st.dataframe(
        tx,
        use_container_width=True,
        hide_index=True
    )

else:

    st.caption(
        "No additional transactions."
    )


# ============================================================
# DAILY DATA
# ============================================================

with st.expander(
    "📅 Full Daily Calculation"
):

    st.dataframe(
        combined_df,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# DOWNLOAD
# ============================================================

if len(combined_df):

    csv = combined_df.to_csv(
        index=False
    ).encode(
        "utf-8"
    )

    st.download_button(
        "⬇️ Download Daily Schedule",
        data=csv,
        file_name=
            "home_loan_daily_schedule.csv",
        mime=
            "text/csv"
    )


# ============================================================
# EXPLANATION
# ============================================================

with st.expander(
    "ℹ️ How this calculator works"
):

    st.markdown(
        """
### 1. Loan tenure

A 20-year loan means:

**20 × 12 = 240 scheduled EMIs**

The app explicitly creates those 240 EMI dates.

For example:

**Start: 29-Aug-2026**

Final scheduled EMI:

**29-Aug-2046**

---

### 2. Daily interest

Interest is calculated using:

**Daily Interest = Effective Balance × Annual Rate ÷ 365**

The calculation therefore accounts for the actual number of
calendar days.

---

### 3. Normal prepayment

A prepayment permanently reduces your loan.

Example:

**26th month → ₹10,000**

The ₹10,000 is removed from the outstanding loan.

---

### 4. MaxGain

A MaxGain deposit does not permanently repay the loan.

Example:

Loan = ₹50 lakh

MaxGain = ₹5 lakh

Interest-bearing balance:

**₹45 lakh**

If ₹2 lakh is withdrawn later:

**₹47 lakh**

becomes the effective interest-bearing balance.

---

### Important

This is a mathematical simulator.

Actual bank calculations can differ because of:

- bank-specific daily interest methodology
- EMI posting date
- transaction cut-off time
- interest posting rules
- MaxGain/OD product terms
- tax treatment
- EMI/tenure reset rules

Use your bank's loan statement and sanction agreement
for the final exact figures.
        """
    )

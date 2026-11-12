"""
AskCI - Mock investment data for CI Financial demo.
Creates a SQLite database with funds, holdings, transactions, and clients.
"""
import sqlite3
import os
import random
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "askci_demo.db")

FUND_NAMES = [
    ("CI Canadian Equity Fund", "Equity", "CAD", 15.42),
    ("CI Global Growth Fund", "Equity", "CAD", 22.87),
    ("CI Canadian Bond Fund", "Fixed Income", "CAD", 10.15),
    ("CI Balanced Fund", "Balanced", "CAD", 18.33),
    ("CI US Equity Fund", "Equity", "USD", 31.50),
    ("CI International Fund", "Equity", "CAD", 14.78),
    ("CI Money Market Fund", "Money Market", "CAD", 10.00),
    ("CI Global Fixed Income Fund", "Fixed Income", "USD", 9.85),
    ("CI Canadian Dividend Fund", "Equity", "CAD", 19.60),
    ("CI Emerging Markets Fund", "Equity", "USD", 12.44),
    ("CI Tech Innovation Fund", "Equity", "CAD", 27.15),
    ("CI Real Estate Fund", "Alternative", "CAD", 16.90),
]

CLIENT_NAMES = [
    ("James", "Chen", "Aggressive", "Toronto"),
    ("Sarah", "Williams", "Moderate", "Vancouver"),
    ("Michael", "Singh", "Conservative", "Calgary"),
    ("Emily", "Brown", "Moderate", "Montreal"),
    ("David", "Kim", "Aggressive", "Toronto"),
    ("Lisa", "Anderson", "Conservative", "Ottawa"),
    ("Robert", "Taylor", "Moderate", "Toronto"),
    ("Jennifer", "Lee", "Aggressive", "Vancouver"),
    ("William", "Martin", "Moderate", "Calgary"),
    ("Maria", "Garcia", "Conservative", "Toronto"),
    ("Thomas", "Wilson", "Aggressive", "Montreal"),
    ("Amanda", "Davis", "Moderate", "Toronto"),
    ("Daniel", "Thompson", "Conservative", "Vancouver"),
    ("Michelle", "White", "Moderate", "Ottawa"),
    ("Kevin", "Harris", "Aggressive", "Toronto"),
]

BENCHMARKS = [
    ("S&P/TSX Composite", "TSX", "Equity"),
    ("S&P 500", "SPX", "Equity"),
    ("FTSE Canada Universe Bond", "FTSE_BOND", "Fixed Income"),
    ("MSCI World", "MSCI_W", "Equity"),
    ("MSCI Emerging Markets", "MSCI_EM", "Equity"),
]


def create_database():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE funds (
            fund_id INTEGER PRIMARY KEY,
            fund_name TEXT NOT NULL,
            category TEXT NOT NULL,
            currency TEXT NOT NULL,
            nav_per_unit REAL NOT NULL,
            total_aum REAL NOT NULL,
            mgmt_fee_pct REAL NOT NULL,
            ytd_return_pct REAL NOT NULL,
            one_year_return_pct REAL NOT NULL,
            three_year_return_pct REAL NOT NULL,
            inception_date TEXT NOT NULL,
            risk_rating TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE clients (
            client_id INTEGER PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            risk_profile TEXT NOT NULL,
            city TEXT NOT NULL,
            account_type TEXT NOT NULL,
            advisor_name TEXT NOT NULL,
            onboarding_date TEXT NOT NULL,
            total_portfolio_value REAL NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE holdings (
            holding_id INTEGER PRIMARY KEY,
            client_id INTEGER NOT NULL,
            fund_id INTEGER NOT NULL,
            units REAL NOT NULL,
            market_value REAL NOT NULL,
            book_cost REAL NOT NULL,
            gain_loss REAL NOT NULL,
            gain_loss_pct REAL NOT NULL,
            as_of_date TEXT NOT NULL,
            FOREIGN KEY (client_id) REFERENCES clients(client_id),
            FOREIGN KEY (fund_id) REFERENCES funds(fund_id)
        )
    """)

    c.execute("""
        CREATE TABLE transactions (
            txn_id INTEGER PRIMARY KEY,
            client_id INTEGER NOT NULL,
            fund_id INTEGER NOT NULL,
            txn_type TEXT NOT NULL,
            units REAL NOT NULL,
            price_per_unit REAL NOT NULL,
            total_amount REAL NOT NULL,
            txn_date TEXT NOT NULL,
            settlement_date TEXT NOT NULL,
            FOREIGN KEY (client_id) REFERENCES clients(client_id),
            FOREIGN KEY (fund_id) REFERENCES funds(fund_id)
        )
    """)

    c.execute("""
        CREATE TABLE benchmarks (
            benchmark_id INTEGER PRIMARY KEY,
            benchmark_name TEXT NOT NULL,
            ticker TEXT NOT NULL,
            asset_class TEXT NOT NULL,
            ytd_return_pct REAL NOT NULL,
            one_year_return_pct REAL NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE data_quality_log (
            log_id INTEGER PRIMARY KEY,
            table_name TEXT NOT NULL,
            check_type TEXT NOT NULL,
            status TEXT NOT NULL,
            records_checked INTEGER NOT NULL,
            issues_found INTEGER NOT NULL,
            details TEXT,
            check_date TEXT NOT NULL
        )
    """)

    random.seed(42)

    risk_map = {"Equity": "Medium-High", "Fixed Income": "Low", "Balanced": "Medium",
                "Money Market": "Low", "Alternative": "Medium-High"}
    advisors = ["John Roberts", "Priya Patel", "Marc Tremblay", "Susan Li", "Ahmed Hassan"]

    for i, (name, cat, cur, nav) in enumerate(FUND_NAMES):
        aum = round(random.uniform(500, 8000), 1)
        fee = round(random.uniform(0.5, 2.5), 2)
        ytd = round(random.uniform(-8, 18), 2)
        one_yr = round(random.uniform(-5, 25), 2)
        three_yr = round(random.uniform(2, 15), 2)
        inception = f"{random.randint(1995, 2020)}-{random.randint(1,12):02d}-01"
        risk = risk_map.get(cat, "Medium")
        c.execute("INSERT INTO funds VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (i+1, name, cat, cur, nav, aum, fee, ytd, one_yr, three_yr, inception, risk))

    for i, (first, last, risk, city) in enumerate(CLIENT_NAMES):
        acct = random.choice(["RRSP", "TFSA", "Non-Registered", "RESP"])
        advisor = random.choice(advisors)
        onboard = f"{random.randint(2015, 2024)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
        portfolio_val = round(random.uniform(50000, 2000000), 2)
        c.execute("INSERT INTO clients VALUES (?,?,?,?,?,?,?,?,?)",
                  (i+1, first, last, risk, city, acct, advisor, onboard, portfolio_val))

    holding_id = 1
    for client_id in range(1, len(CLIENT_NAMES)+1):
        num_funds = random.randint(2, 5)
        fund_ids = random.sample(range(1, len(FUND_NAMES)+1), num_funds)
        for fund_id in fund_ids:
            nav = FUND_NAMES[fund_id-1][3]
            units = round(random.uniform(100, 5000), 2)
            market_val = round(units * nav, 2)
            book_cost = round(market_val * random.uniform(0.75, 1.15), 2)
            gain = round(market_val - book_cost, 2)
            gain_pct = round((gain / book_cost) * 100, 2)
            c.execute("INSERT INTO holdings VALUES (?,?,?,?,?,?,?,?,?)",
                      (holding_id, client_id, fund_id, units, market_val, book_cost,
                       gain, gain_pct, "2026-10-31"))
            holding_id += 1

    txn_id = 1
    for client_id in range(1, len(CLIENT_NAMES)+1):
        num_txns = random.randint(5, 15)
        for _ in range(num_txns):
            fund_id = random.randint(1, len(FUND_NAMES))
            txn_type = random.choice(["Buy", "Buy", "Buy", "Sell", "Dividend"])
            nav = FUND_NAMES[fund_id-1][3]
            price = round(nav * random.uniform(0.9, 1.1), 2)
            units = round(random.uniform(10, 500), 2)
            total = round(units * price, 2)
            days_ago = random.randint(1, 365)
            txn_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            settle_date = (datetime.now() - timedelta(days=days_ago-2)).strftime("%Y-%m-%d")
            c.execute("INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?)",
                      (txn_id, client_id, fund_id, txn_type, units, price, total,
                       txn_date, settle_date))
            txn_id += 1

    for i, (name, ticker, asset_class) in enumerate(BENCHMARKS):
        ytd = round(random.uniform(3, 15), 2)
        one_yr = round(random.uniform(5, 20), 2)
        c.execute("INSERT INTO benchmarks VALUES (?,?,?,?,?,?)",
                  (i+1, name, ticker, asset_class, ytd, one_yr))

    # ---- NEW v2 TABLES ----

    c.execute("""
        CREATE TABLE quality_scores (
            id INTEGER PRIMARY KEY,
            table_name TEXT NOT NULL,
            dimension TEXT NOT NULL,
            score REAL NOT NULL,
            details TEXT,
            checked_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE sla_tracking (
            id INTEGER PRIMARY KEY,
            pipeline_name TEXT NOT NULL,
            table_name TEXT NOT NULL,
            expected_refresh TEXT NOT NULL,
            actual_refresh TEXT,
            status TEXT NOT NULL,
            delay_minutes INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE lineage_map (
            id INTEGER PRIMARY KEY,
            source_system TEXT NOT NULL,
            source_table TEXT,
            intermediate_steps TEXT,
            target_table TEXT NOT NULL,
            transform_type TEXT,
            last_updated TEXT
        )
    """)

    c.execute("""
        CREATE TABLE governance_metadata (
            id INTEGER PRIMARY KEY,
            table_name TEXT NOT NULL,
            owner_team TEXT,
            data_classification TEXT,
            compliance_frameworks TEXT,
            pii_columns TEXT,
            last_audit_date TEXT,
            access_policy TEXT
        )
    """)

    c.execute("""
        CREATE TABLE anomaly_log (
            id INTEGER PRIMARY KEY,
            detected_at TEXT NOT NULL,
            table_name TEXT NOT NULL,
            anomaly_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            description TEXT,
            affected_rows INTEGER DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'open'
        )
    """)

    # -- quality_scores: 4 dimensions per table --
    qs_data = [
        ("funds", "completeness", 98, "All 12 funds have complete records", "2026-11-04 06:15:00"),
        ("funds", "accuracy", 95, "NAV values within expected 0.5% range", "2026-11-04 06:15:00"),
        ("funds", "timeliness", 92, "Last refresh 2h ago, target <4h", "2026-11-04 06:15:00"),
        ("funds", "consistency", 96, "AUM totals match holdings aggregation", "2026-11-04 06:15:00"),
        ("clients", "completeness", 93, "2 clients missing risk_profile", "2026-11-04 06:18:00"),
        ("clients", "accuracy", 95, "Email and phone formats validated", "2026-11-04 06:18:00"),
        ("clients", "timeliness", 88, "3 client records not updated in 90+ days", "2026-11-04 06:18:00"),
        ("clients", "consistency", 89, "Portfolio values match holdings sum for 13/15 clients", "2026-11-04 06:18:00"),
        ("holdings", "completeness", 96, "All holdings have required fields", "2026-11-04 06:20:00"),
        ("holdings", "accuracy", 82, "4 holdings gain/loss mismatch >0.01", "2026-11-04 06:20:00"),
        ("holdings", "timeliness", 90, "As-of dates within 24h", "2026-11-04 06:20:00"),
        ("holdings", "consistency", 85, "Some holdings don't match latest NAV", "2026-11-04 06:20:00"),
        ("transactions", "completeness", 88, "5 transactions missing settlement_date", "2026-11-04 06:22:00"),
        ("transactions", "accuracy", 62, "12 duplicate transaction IDs detected", "2026-11-04 06:22:00"),
        ("transactions", "timeliness", 75, "Settlement backlog of 8 transactions", "2026-11-04 06:22:00"),
        ("transactions", "consistency", 65, "Transaction totals don't match units*price for 15 rows", "2026-11-04 06:22:00"),
        ("benchmarks", "completeness", 100, "All benchmark records complete", "2026-11-04 06:25:00"),
        ("benchmarks", "accuracy", 90, "Return values within expected ranges", "2026-11-04 06:25:00"),
        ("benchmarks", "timeliness", 72, "Market data delayed 6h, target <2h", "2026-11-04 06:25:00"),
        ("benchmarks", "consistency", 94, "Ticker symbols validated against exchange", "2026-11-04 06:25:00"),
    ]
    for i, (tbl, dim, score, det, ts) in enumerate(qs_data):
        c.execute("INSERT INTO quality_scores VALUES (?,?,?,?,?,?)", (i+1, tbl, dim, score, det, ts))

    # -- sla_tracking --
    sla_data = [
        ("Trading Ingest", "funds", "06:00 daily", "05:48", "on_time", 0),
        ("Trading Ingest", "transactions", "06:00 daily", "06:22", "delayed", 22),
        ("CRM Sync", "clients", "07:00 daily", "06:55", "on_time", 0),
        ("Holdings Calc", "holdings", "08:00 daily", "07:45", "on_time", 0),
        ("Market Data Feed", "benchmarks", "06:30 daily", "06:28", "on_time", 0),
        ("Quality Scan", "data_quality_log", "09:00 daily", "09:02", "on_time", 2),
        ("Risk Calc", "holdings", "08:30 daily", "08:25", "on_time", 0),
        ("NAV Calc", "funds", "07:00 daily", "06:58", "on_time", 0),
        ("Compliance Check", "clients", "09:30 daily", "09:28", "on_time", 0),
        ("Settlement Proc", "transactions", "10:00 daily", "09:55", "on_time", 0),
        ("Benchmark Refresh", "benchmarks", "07:00 daily", "06:52", "on_time", 0),
        ("Client Enrichment", "clients", "08:00 daily", "07:58", "on_time", 0),
        ("Audit Trail", "data_quality_log", "10:00 daily", "09:58", "on_time", 0),
        ("Perf Attribution", "funds", "09:00 daily", "08:55", "on_time", 0),
        ("FX Rate Sync", "benchmarks", "06:00 daily", "05:59", "on_time", 0),
        ("Dividend Process", "transactions", "11:00 daily", "10:58", "on_time", 0),
        ("Portfolio Rebal", "holdings", "12:00 daily", "11:55", "on_time", 0),
    ]
    for i, (pipe, tbl, exp, act, stat, delay) in enumerate(sla_data):
        c.execute("INSERT INTO sla_tracking VALUES (?,?,?,?,?,?,?)", (i+1, pipe, tbl, exp, act, stat, delay))

    # -- lineage_map --
    lineage_data = [
        ("Trading API", "raw_trades", '["S3 raw/trades/", "Glue ETL: clean + dedupe"]', "funds", "glue", "2026-11-04 05:48:00"),
        ("Trading API", "raw_trades", '["S3 raw/trades/", "Glue ETL: normalize"]', "transactions", "glue", "2026-11-04 06:22:00"),
        ("CRM Export", "crm_clients", '["S3 raw/crm/", "dbt staging: stg_clients"]', "clients", "dbt", "2026-11-04 06:55:00"),
        ("Portfolio Engine", "calc_holdings", '["S3 raw/holdings/", "Lambda: calc gains"]', "holdings", "lambda", "2026-11-04 07:45:00"),
        ("Market Feed", "market_prices", '["S3 raw/market/", "Lambda: parse + validate"]', "benchmarks", "lambda", "2026-11-04 09:15:00"),
        ("Quality Engine", "scan_results", '["Lambda: run checks"]', "data_quality_log", "lambda", "2026-11-04 09:02:00"),
    ]
    for i, (src, stbl, steps, tgt, ttype, ts) in enumerate(lineage_data):
        c.execute("INSERT INTO lineage_map VALUES (?,?,?,?,?,?,?)", (i+1, src, stbl, steps, tgt, ttype, ts))

    # -- governance_metadata --
    gov_data = [
        ("funds", "Data Engineering", "Internal", "OSC", "[]", "2026-10-15", "role_based"),
        ("clients", "Client Services", "PII", "PIPEDA,OSC", '["first_name","last_name","city"]', "2026-10-20", "restricted"),
        ("holdings", "Portfolio Mgmt", "Sensitive", "OSC,SOX", "[]", "2026-10-18", "role_based"),
        ("transactions", "Trading Ops", "Sensitive", "OSC,SOX", "[]", "2026-10-22", "role_based"),
        ("benchmarks", "Market Data", "Public", "", "[]", "2026-09-30", "open"),
        ("data_quality_log", "Data Engineering", "Internal", "", "[]", "2026-10-25", "role_based"),
    ]
    for i, (tbl, owner, cls, comp, pii, audit, policy) in enumerate(gov_data):
        c.execute("INSERT INTO governance_metadata VALUES (?,?,?,?,?,?,?,?)",
                  (i+1, tbl, owner, cls, comp, pii, audit, policy))

    # -- anomaly_log --
    anomaly_data = [
        ("2026-11-04 06:22:00", "transactions", "duplicate", "critical",
         "12 duplicate transaction IDs detected in morning batch", 12, "open"),
        ("2026-11-04 06:20:00", "funds", "spike", "warning",
         "CI Tech Innovation Fund NAV spike +47% vs previous day", 1, "open"),
        ("2026-11-04 06:18:00", "clients", "missing", "warning",
         "3 clients missing risk_profile after CRM sync", 3, "open"),
        ("2026-11-03 06:15:00", "holdings", "drift", "info",
         "Holdings gain/loss drift >1% for 4 records", 4, "acknowledged"),
        ("2026-11-03 06:10:00", "benchmarks", "missing", "warning",
         "MSCI EM benchmark missing 2 trading days of data", 2, "acknowledged"),
        ("2026-11-02 09:00:00", "transactions", "duplicate", "critical",
         "Batch duplicate check found 5 repeat settlement records", 5, "resolved"),
        ("2026-11-01 14:30:00", "funds", "drift", "info",
         "CI Bond Fund NAV deviation >2 std dev from 30-day mean", 1, "resolved"),
    ]
    for i, (ts, tbl, atype, sev, desc, rows, stat) in enumerate(anomaly_data):
        c.execute("INSERT INTO anomaly_log VALUES (?,?,?,?,?,?,?,?)",
                  (i+1, ts, tbl, atype, sev, desc, rows, stat))

    quality_checks = [
        ("funds", "completeness", "PASS", 12, 0, "All fields populated"),
        ("funds", "validity", "PASS", 12, 0, "NAV values within expected range"),
        ("clients", "completeness", "PASS", 15, 0, "All required fields present"),
        ("clients", "uniqueness", "PASS", 15, 0, "No duplicate client records"),
        ("holdings", "referential_integrity", "PASS", 45, 0, "All foreign keys valid"),
        ("holdings", "accuracy", "WARNING", 45, 2, "2 holdings have gain/loss mismatch > 0.01"),
        ("transactions", "completeness", "PASS", 120, 0, "All fields populated"),
        ("transactions", "timeliness", "WARNING", 120, 3, "3 transactions missing settlement date"),
        ("transactions", "validity", "FAIL", 120, 1, "1 transaction with negative unit count"),
        ("benchmarks", "completeness", "PASS", 5, 0, "All benchmark data current"),
    ]
    for i, (table, check, status, records, issues, details) in enumerate(quality_checks):
        c.execute("INSERT INTO data_quality_log VALUES (?,?,?,?,?,?,?,?)",
                  (i+1, table, check, status, records, issues, details, "2026-10-31"))

    # ---- NEW v3 TABLES: AI Insights ----

    # 1. fund_daily_nav — 90 days of daily NAV for trend analysis
    c.execute("""
        CREATE TABLE fund_daily_nav (
            id INTEGER PRIMARY KEY,
            fund_id INTEGER NOT NULL,
            nav_date TEXT NOT NULL,
            nav_value REAL NOT NULL,
            daily_return_pct REAL,
            cumulative_return_pct REAL,
            volume REAL,
            FOREIGN KEY (fund_id) REFERENCES funds(fund_id)
        )
    """)

    nav_id = 1
    from datetime import date
    start_date = date(2026, 8, 7)
    num_days = 90
    for fund_idx in range(len(FUND_NAMES)):
        fund_id = fund_idx + 1
        base_nav = FUND_NAMES[fund_idx][3]
        category = FUND_NAMES[fund_idx][1]
        fund_name = FUND_NAMES[fund_idx][0]
        nav = base_nav * random.uniform(0.92, 0.98)
        if category in ("Fixed Income", "Money Market"):
            drift = 0.0001
            volatility = 0.001
        elif category == "Balanced":
            drift = 0.0003
            volatility = 0.005
        else:
            drift = 0.0005
            volatility = 0.012
        first_nav = nav
        for day_i in range(num_days):
            d = start_date + timedelta(days=day_i)
            if d.weekday() >= 5:
                continue
            shock = 0
            if "Tech Innovation" in fund_name and day_i >= 85:
                shock = random.uniform(0.02, 0.06)
            elif "Emerging Markets" in fund_name and day_i >= 80:
                shock = random.uniform(-0.04, -0.01)
            daily_ret = drift + random.gauss(0, volatility) + shock
            nav = nav * (1 + daily_ret)
            cum_ret = round(((nav / first_nav) - 1) * 100, 4)
            vol = round(random.uniform(50, 500) * (base_nav / 15), 1)
            c.execute("INSERT INTO fund_daily_nav VALUES (?,?,?,?,?,?,?)",
                      (nav_id, fund_id, d.strftime("%Y-%m-%d"),
                       round(nav, 4), round(daily_ret * 100, 4), cum_ret, vol))
            nav_id += 1

    # 2. performance_attribution — Brinson-style for each fund per period
    c.execute("""
        CREATE TABLE performance_attribution (
            id INTEGER PRIMARY KEY,
            fund_id INTEGER NOT NULL,
            period TEXT NOT NULL,
            total_return_pct REAL,
            benchmark_return_pct REAL,
            allocation_effect_pct REAL,
            selection_effect_pct REAL,
            interaction_effect_pct REAL,
            currency_effect_pct REAL,
            active_return_pct REAL,
            FOREIGN KEY (fund_id) REFERENCES funds(fund_id)
        )
    """)

    pa_id = 1
    periods = ["Q3 2026", "Q2 2026", "Q1 2026", "2025"]
    outperformers = {1, 2, 5, 9, 11}
    for fund_idx in range(len(FUND_NAMES)):
        fund_id = fund_idx + 1
        category = FUND_NAMES[fund_idx][1]
        for period in periods:
            if category == "Money Market":
                bench_ret = round(random.uniform(0.8, 1.3), 2)
                total_ret = round(bench_ret + random.uniform(-0.1, 0.15), 2)
            elif category == "Fixed Income":
                bench_ret = round(random.uniform(0.5, 3.0), 2)
                total_ret = round(bench_ret + random.uniform(-0.8, 1.0), 2)
            else:
                if "2025" in period:
                    bench_ret = round(random.uniform(2.0, 8.0), 2)
                else:
                    bench_ret = round(random.uniform(-2.0, 6.0), 2)
                if fund_id in outperformers:
                    total_ret = round(bench_ret + random.uniform(0.3, 3.5), 2)
                else:
                    total_ret = round(bench_ret + random.uniform(-3.0, 0.5), 2)
            active = round(total_ret - bench_ret, 2)
            alloc = round(random.uniform(-0.5, 1.5), 2)
            selection = round(active - alloc + random.uniform(-0.3, 0.3), 2)
            interaction = round(active - alloc - selection, 2)
            currency = round(random.uniform(-0.3, 0.3), 2)
            c.execute("INSERT INTO performance_attribution VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (pa_id, fund_id, period, total_ret, bench_ret,
                       alloc, selection, interaction, currency, active))
            pa_id += 1

    # 3. redemption_risk — Risk scoring for each fund
    c.execute("""
        CREATE TABLE redemption_risk (
            id INTEGER PRIMARY KEY,
            fund_id INTEGER NOT NULL,
            risk_score INTEGER NOT NULL,
            redemption_velocity REAL,
            performance_vs_benchmark REAL,
            advisor_concentration REAL,
            flow_trend TEXT,
            risk_level TEXT NOT NULL,
            last_updated TEXT NOT NULL,
            FOREIGN KEY (fund_id) REFERENCES funds(fund_id)
        )
    """)

    risk_profiles = {
        1:  (22, 0.8, 2.1, 15.0, "Inflow", "Low"),
        2:  (18, 0.5, 3.5, 12.0, "Inflow", "Low"),
        3:  (30, 1.2, -0.5, 20.0, "Stable", "Low"),
        4:  (35, 1.5, 0.8, 18.0, "Stable", "Medium"),
        5:  (25, 0.9, 1.8, 10.0, "Inflow", "Low"),
        6:  (45, 2.1, -1.2, 25.0, "Outflow", "Medium"),
        7:  (15, 0.3, 0.1, 8.0, "Stable", "Low"),
        8:  (40, 1.8, -0.8, 22.0, "Stable", "Medium"),
        9:  (28, 1.0, 1.5, 14.0, "Inflow", "Low"),
        10: (78, 4.5, -3.2, 35.0, "Heavy Outflow", "High"),
        11: (55, 2.8, 4.8, 30.0, "Outflow", "Medium"),
        12: (85, 5.2, -4.1, 42.0, "Heavy Outflow", "Critical"),
    }
    for fund_id, (score, vel, perf, conc, trend, level) in risk_profiles.items():
        c.execute("INSERT INTO redemption_risk VALUES (?,?,?,?,?,?,?,?,?)",
                  (fund_id, fund_id, score, vel, perf, conc, trend, level,
                   "2026-11-04 08:00:00"))

    # 4. fund_flows — Monthly net flows for anomaly detection
    c.execute("""
        CREATE TABLE fund_flows (
            id INTEGER PRIMARY KEY,
            fund_id INTEGER NOT NULL,
            flow_month TEXT NOT NULL,
            gross_inflow REAL,
            gross_outflow REAL,
            net_flow REAL,
            FOREIGN KEY (fund_id) REFERENCES funds(fund_id)
        )
    """)

    flow_id = 1
    months = ["2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05",
              "2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11"]
    for fund_idx in range(len(FUND_NAMES)):
        fund_id = fund_idx + 1
        fund_name = FUND_NAMES[fund_idx][0]
        category = FUND_NAMES[fund_idx][1]
        base_inflow = random.uniform(20, 120)
        base_outflow = random.uniform(15, 80)
        for m_idx, month in enumerate(months):
            inflow = round(base_inflow * random.uniform(0.7, 1.4), 1)
            outflow = round(base_outflow * random.uniform(0.7, 1.3), 1)
            if "Emerging Markets" in fund_name and month == "2026-10":
                outflow = round(base_outflow * random.uniform(4.0, 6.0), 1)
                inflow = round(base_inflow * random.uniform(0.2, 0.4), 1)
            elif "Real Estate" in fund_name and month in ("2026-09", "2026-10"):
                outflow = round(base_outflow * random.uniform(3.0, 4.5), 1)
            elif "Tech Innovation" in fund_name and month in ("2026-10", "2026-11"):
                inflow = round(base_inflow * random.uniform(2.5, 4.0), 1)
            net = round(inflow - outflow, 1)
            c.execute("INSERT INTO fund_flows VALUES (?,?,?,?,?,?)",
                      (flow_id, fund_id, month, inflow, outflow, net))
            flow_id += 1

    conn.commit()
    conn.close()
    return DB_PATH


def get_connection():
    if not os.path.exists(DB_PATH):
        create_database()
    return sqlite3.connect(DB_PATH)


def get_schema_info():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in c.fetchall()]
    schema = []
    for table in tables:
        c.execute(f"PRAGMA table_info({table})")
        cols = c.fetchall()
        col_info = ", ".join([f"{col[1]} ({col[2]})" for col in cols])
        c.execute(f"SELECT COUNT(*) FROM {table}")
        count = c.fetchone()[0]
        schema.append(f"Table: {table} ({count} rows)\n  Columns: {col_info}")
    conn.close()
    return "\n\n".join(schema)


if __name__ == "__main__":
    path = create_database()
    print(f"Database created at: {path}")
    print(f"\nSchema:\n{get_schema_info()}")

"""
AskCI - Local NL-to-SQL engine. No API needed.
Parses natural language questions and generates SQL queries against the CI Financial database.
"""
import re
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "askci_demo.db")


def get_conn():
    return sqlite3.connect(DB_PATH)


# Column mappings for fuzzy matching
COLUMN_ALIASES = {
    "return": "ytd_return_pct", "performance": "ytd_return_pct", "ytd": "ytd_return_pct",
    "1 year": "one_year_return_pct", "one year": "one_year_return_pct", "1y": "one_year_return_pct",
    "3 year": "three_year_return_pct", "three year": "three_year_return_pct", "3y": "three_year_return_pct",
    "aum": "total_aum", "asset": "total_aum", "size": "total_aum",
    "fee": "mgmt_fee_pct", "cost": "mgmt_fee_pct", "expense": "mgmt_fee_pct",
    "nav": "nav_per_unit", "price": "nav_per_unit",
    "risk": "risk_rating", "risk profile": "risk_profile",
    "city": "city", "location": "city",
    "portfolio": "total_portfolio_value", "value": "total_portfolio_value",
    "account": "account_type", "type": "account_type",
    "advisor": "advisor_name",
    "gain": "gain_loss", "loss": "gain_loss", "profit": "gain_loss",
    "unit": "units",
}

CITIES = ["toronto", "vancouver", "calgary", "montreal", "ottawa"]
CATEGORIES = ["equity", "fixed income", "balanced", "money market", "alternative"]
RISK_LEVELS = ["aggressive", "moderate", "conservative"]
ACCOUNT_TYPES = ["rrsp", "tfsa", "non-registered", "resp"]
TXN_TYPES = ["buy", "sell", "dividend"]


def _detect_intent(q):
    """Classify the question into an intent category."""
    q = q.lower().strip()

    if any(w in q for w in ["quality", "issue", "problem", "check", "governance", "monitor", "fail", "warning", "error"]):
        return "data_quality"
    if any(w in q for w in ["benchmark", "index", "s&p", "tsx", "msci", "ftse"]):
        return "benchmark"
    if any(w in q for w in ["transaction", "trade", "recent", "activity", "bought", "sold"]):
        return "transaction"
    if any(w in q for w in ["holding", "position", "owns", "invested in"]):
        return "holding"
    if any(w in q for w in ["client", "customer", "investor", "who"]):
        return "client"
    if any(w in q for w in ["category", "breakdown", "allocation", "distribute", "composition", "mix"]):
        return "category"
    if any(w in q for w in ["fund", "top", "best", "worst", "bottom", "highest", "lowest",
                             "perform", "return", "aum", "asset", "fee", "nav", "expensive",
                             "cheap", "large", "small", "biggest", "smallest"]):
        return "fund"
    if any(w in q for w in ["how many", "count", "total", "sum", "average", "avg", "mean"]):
        return "aggregate"

    return "fund"


def _detect_sort(q):
    """Detect sort direction."""
    q = q.lower()
    if any(w in q for w in ["worst", "lowest", "bottom", "least", "smallest", "cheapest", "minimum", "min"]):
        return "ASC"
    return "DESC"


def _detect_limit(q):
    """Extract limit number from question."""
    m = re.search(r'\b(\d+)\b', q)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 100:
            return n
    if any(w in q for w in ["all", "every", "each", "full", "complete"]):
        return 50
    return 5


def _detect_city(q):
    q = q.lower()
    for city in CITIES:
        if city in q:
            return city.title()
    return None


def _detect_category(q):
    q = q.lower()
    for cat in CATEGORIES:
        if cat in q:
            return cat.title() if cat != "fixed income" else "Fixed Income"
    return None


def _detect_risk(q):
    q = q.lower()
    for r in RISK_LEVELS:
        if r in q:
            return r.title()
    return None


def _detect_sort_col(q, intent):
    q = q.lower()
    for alias, col in COLUMN_ALIASES.items():
        if alias in q:
            return col
    if intent == "fund":
        if any(w in q for w in ["large", "big", "size", "aum", "asset"]):
            return "total_aum"
        if any(w in q for w in ["fee", "expense", "cost", "cheap"]):
            return "mgmt_fee_pct"
        return "ytd_return_pct"
    return None


def generate_query(question):
    """Generate SQL and answer template from a natural language question."""
    q = question.lower().strip()
    intent = _detect_intent(q)
    direction = _detect_sort(q)
    limit = _detect_limit(q)
    city = _detect_city(q)
    category = _detect_category(q)
    risk = _detect_risk(q)

    if intent == "data_quality":
        where = ""
        if any(w in q for w in ["fail", "error", "critical"]):
            where = " WHERE status = 'FAIL'"
        elif any(w in q for w in ["warning", "warn"]):
            where = " WHERE status = 'WARNING'"
        elif any(w in q for w in ["pass", "good", "ok"]):
            where = " WHERE status = 'PASS'"
        else:
            where = " WHERE status != 'PASS'"

        sql = f"SELECT table_name, check_type, status, issues_found, details FROM data_quality_log{where} ORDER BY CASE status WHEN 'FAIL' THEN 0 WHEN 'WARNING' THEN 1 ELSE 2 END"
        tmpl = "Data quality scan results: {summary}. The transactions table should be prioritized for remediation."
        return sql, tmpl

    if intent == "benchmark":
        sql = "SELECT benchmark_name, ticker, asset_class, ytd_return_pct, one_year_return_pct FROM benchmarks ORDER BY ytd_return_pct DESC"
        tmpl = "Benchmark performance overview: {summary}. These indices serve as reference points for evaluating fund alpha."
        return sql, tmpl

    if intent == "transaction":
        wheres = []
        if any(w in q for w in ["buy", "bought", "purchase"]):
            wheres.append("t.txn_type = 'Buy'")
        elif any(w in q for w in ["sell", "sold"]):
            wheres.append("t.txn_type = 'Sell'")
        elif any(w in q for w in ["dividend"]):
            wheres.append("t.txn_type = 'Dividend'")
        if city:
            wheres.append(f"c.city = '{city}'")

        where_clause = (" WHERE " + " AND ".join(wheres)) if wheres else ""
        sql = f"""SELECT t.txn_date, c.first_name || ' ' || c.last_name as client, f.fund_name,
                  t.txn_type, ROUND(t.total_amount, 2) as amount
                  FROM transactions t
                  JOIN clients c ON t.client_id = c.client_id
                  JOIN funds f ON t.fund_id = f.fund_id
                  {where_clause}
                  ORDER BY t.txn_date DESC LIMIT {limit}"""
        tmpl = "Here are the most recent transactions: {summary}."
        return sql, tmpl

    if intent == "holding":
        wheres = []
        if city:
            wheres.append(f"c.city = '{city}'")
        if risk:
            wheres.append(f"c.risk_profile = '{risk}'")

        where_clause = (" WHERE " + " AND ".join(wheres)) if wheres else ""
        sql = f"""SELECT c.first_name || ' ' || c.last_name as client, f.fund_name,
                  h.units, ROUND(h.market_value, 2) as market_value,
                  ROUND(h.gain_loss_pct, 2) as gain_loss_pct
                  FROM holdings h
                  JOIN clients c ON h.client_id = c.client_id
                  JOIN funds f ON h.fund_id = f.fund_id
                  {where_clause}
                  ORDER BY h.market_value {direction} LIMIT {limit}"""
        tmpl = "Holdings overview: {summary}."
        return sql, tmpl

    if intent == "client":
        wheres = []
        if city:
            wheres.append(f"city = '{city}'")
        if risk:
            wheres.append(f"risk_profile = '{risk}'")

        where_clause = (" WHERE " + " AND ".join(wheres)) if wheres else ""
        sort_col = "total_portfolio_value"
        sql = f"""SELECT first_name || ' ' || last_name as client, city, risk_profile,
                  account_type, advisor_name, ROUND(total_portfolio_value, 2) as portfolio_value
                  FROM clients{where_clause}
                  ORDER BY {sort_col} {direction} LIMIT {limit}"""
        tmpl = "Client overview: {summary}."
        return sql, tmpl

    if intent == "category":
        sql = """SELECT category, COUNT(*) as fund_count,
                 ROUND(SUM(total_aum), 1) as total_aum_m,
                 ROUND(AVG(ytd_return_pct), 2) as avg_ytd_return,
                 ROUND(AVG(mgmt_fee_pct), 2) as avg_fee
                 FROM funds GROUP BY category ORDER BY total_aum_m DESC"""
        tmpl = "Fund category breakdown: {summary}."
        return sql, tmpl

    if intent == "aggregate":
        if "client" in q or "customer" in q:
            if city:
                sql = f"SELECT COUNT(*) as count, ROUND(AVG(total_portfolio_value),2) as avg_portfolio, ROUND(SUM(total_portfolio_value),2) as total FROM clients WHERE city = '{city}'"
            elif risk:
                sql = f"SELECT COUNT(*) as count, ROUND(AVG(total_portfolio_value),2) as avg_portfolio FROM clients WHERE risk_profile = '{risk}'"
            else:
                sql = "SELECT COUNT(*) as total_clients, ROUND(AVG(total_portfolio_value),2) as avg_portfolio, ROUND(SUM(total_portfolio_value),2) as total_value FROM clients"
            tmpl = "Client statistics: {summary}."
            return sql, tmpl

        sql = """SELECT COUNT(*) as total_funds,
                 ROUND(SUM(total_aum), 1) as total_aum_m,
                 ROUND(AVG(ytd_return_pct), 2) as avg_ytd,
                 ROUND(MIN(ytd_return_pct), 2) as min_ytd,
                 ROUND(MAX(ytd_return_pct), 2) as max_ytd
                 FROM funds"""
        tmpl = "Fund statistics: {summary}."
        return sql, tmpl

    # Default: fund query
    sort_col = _detect_sort_col(q, intent)
    wheres = []
    if category:
        wheres.append(f"category = '{category}'")

    where_clause = (" WHERE " + " AND ".join(wheres)) if wheres else ""
    sql = f"""SELECT fund_name, ytd_return_pct, one_year_return_pct, total_aum,
              category, mgmt_fee_pct, risk_rating
              FROM funds{where_clause}
              ORDER BY {sort_col} {direction} LIMIT {limit}"""

    if "worst" in q or "bottom" in q or "lowest" in q:
        tmpl = "The lowest performing funds: {summary}. Market headwinds in these segments are worth monitoring."
    elif "best" in q or "top" in q or "highest" in q:
        tmpl = "The top performing funds: {summary}. Strong performance driven by favorable market conditions."
    elif "fee" in q or "expense" in q or "cost" in q:
        tmpl = "Fund fee comparison: {summary}."
    elif "aum" in q or "asset" in q or "large" in q:
        tmpl = "Funds by AUM: {summary}."
    else:
        tmpl = "Fund data: {summary}."

    return sql, tmpl


def _make_summary(columns, rows):
    """Generate a human-readable summary from query results."""
    if not rows:
        return "No results found matching your criteria."

    parts = []
    for i, row in enumerate(rows[:5]):
        items = []
        for j, col in enumerate(columns):
            val = row[j]
            if val is None:
                continue
            col_lower = col.lower()
            if isinstance(val, float):
                if "pct" in col_lower or "return" in col_lower or "fee" in col_lower or "gain" in col_lower:
                    items.append(f"{col.replace('_', ' ')}: {val:+.2f}%")
                elif "aum" in col_lower or "value" in col_lower or "amount" in col_lower or "portfolio" in col_lower or "total" in col_lower:
                    if abs(val) >= 1000000:
                        items.append(f"${val/1000000:.2f}M")
                    elif abs(val) >= 1000:
                        items.append(f"${val:,.0f}")
                    else:
                        items.append(f"${val:.2f}")
                else:
                    items.append(f"{val:.2f}")
            elif isinstance(val, int):
                if "count" in col_lower or "found" in col_lower:
                    items.append(f"{val} records")
                else:
                    items.append(str(val))
            else:
                items.append(str(val))

        if items:
            parts.append(", ".join(items))

    if len(rows) > 5:
        parts.append(f"... and {len(rows) - 5} more")

    return "; ".join(parts) if parts else "Query returned data."


def ask_local(question):
    """Process a natural language question without any external API."""
    try:
        sql, tmpl = generate_query(question)
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        conn.close()

        summary = _make_summary(columns, rows)
        answer = tmpl.replace("{summary}", summary)

        return {
            "success": True,
            "sql": sql.strip(),
            "answer": answer,
            "columns": columns,
            "rows": [tuple(r) for r in rows],
        }
    except Exception as e:
        return {
            "success": False,
            "sql": "",
            "answer": f"I had trouble processing that question. Try asking about funds, clients, transactions, or data quality. Error: {str(e)}",
            "columns": [],
            "rows": [],
        }

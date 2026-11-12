"""
AskCI - AI Agent that translates natural language to SQL queries.
Uses LangChain + Gemini to query CI Financial mock investment data.
"""
import sqlite3
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from askci_v3.mock_data import get_connection, get_schema_info, create_database, DB_PATH

SYSTEM_PROMPT = """You are AskCI, an AI data assistant for CI Financial's Data, Analytics & AI team.
You help business users query investment data using natural language.

You have access to a SQLite database with these tables:

{schema}

RULES:
1. Generate ONLY valid SQLite SQL. No markdown, no explanation, just the SQL query.
2. Always use proper column names from the schema above.
3. For money values, round to 2 decimal places.
4. For percentages, include the % sign in aliases.
5. Limit results to 20 rows unless the user asks for more.
6. If the question is about data quality, query the data_quality_log table.
7. When joining tables, always use explicit JOIN syntax.
8. For fund performance comparisons, include the benchmark data when relevant.
9. Return SQL only. No preamble, no markdown code fences.
"""

ANSWER_PROMPT = """You are AskCI, a friendly AI data assistant for CI Financial.
Given the user's question and the query results, provide a clear, professional answer.

User question: {question}
Query results: {results}
SQL used: {sql}

RULES:
1. Summarize the key findings in plain English. Use bullet points or numbered lists for multiple items.
2. Format dollar amounts with $ and commas (e.g. $5,268M). Format percentages with % sign (e.g. +14.40%).
3. If comparing funds, rank them clearly with the fund name bolded.
4. Keep the answer concise - 3-5 sentences, or a short bulleted list.
5. If data quality issues exist, flag severity clearly.
6. Use Canadian dollar (CAD) formatting where applicable.
7. Do not show the SQL to the user unless they ask.
8. End with one brief insight or recommendation.
9. Never dump raw column names. Use human-readable labels like "YTD Return" instead of "ytd_return_pct".
"""


import time as _time
_gemini_cooldown_until = 0
_gemini_probed = False

def _probe_gemini():
    """Quick HTTP probe to check if Gemini API quota is available."""
    global _gemini_cooldown_until, _gemini_probed
    if _gemini_probed:
        return
    _gemini_probed = True
    key = os.getenv("GEMINI_API_KEY", "")
    if not key or key.startswith("TEST_"):
        return
    try:
        import urllib.request, urllib.error, json
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={key}"
        data = json.dumps({"contents": [{"parts": [{"text": "hi"}]}]}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
        print("Gemini API probe: OK")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            _gemini_cooldown_until = _time.time() + 3600
            print("Gemini API probe: quota exhausted — cooldown 1 hour")
        elif e.code == 404:
            print(f"Gemini API probe: model not found, skipping probe")
        else:
            print(f"Gemini API probe: HTTP {e.code}")
    except Exception as e:
        print(f"Gemini API probe: {e}")

def init_agent(api_key=None):
    global _gemini_cooldown_until
    if _time.time() < _gemini_cooldown_until:
        print(f"Gemini on cooldown until {_time.ctime(_gemini_cooldown_until)}, skipping")
        return None
    key = api_key or os.getenv("GEMINI_API_KEY", "")
    if not key or key.startswith("TEST_"):
        return None
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash",
        google_api_key=key,
        temperature=0,
        timeout=10,
        max_retries=0,
    )
    return llm


def ensure_db():
    if not os.path.exists(DB_PATH):
        create_database()


def generate_sql(llm, question: str) -> str:
    ensure_db()
    schema = get_schema_info()
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{question}")
    ])
    chain = prompt | llm | StrOutputParser()
    sql = chain.invoke({"schema": schema, "question": question})
    sql = sql.strip()
    if sql.startswith("```"):
        sql = sql.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return sql


def execute_sql(sql: str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        conn.close()
        return columns, rows, None
    except Exception as e:
        conn.close()
        return [], [], str(e)


def generate_answer(llm, question: str, sql: str, columns: list, rows: list) -> str:
    results_str = f"Columns: {columns}\nData: {rows[:20]}"
    prompt = ChatPromptTemplate.from_messages([
        ("system", ANSWER_PROMPT),
        ("human", "Please analyze and answer.")
    ])
    chain = prompt | llm | StrOutputParser()
    answer = chain.invoke({
        "question": question,
        "results": results_str,
        "sql": sql,
    })
    return answer


CHAT_PROMPT = """You are AskCI, a friendly AI data assistant for CI Financial's Data, Analytics & AI team.
You help business users with data questions AND general conversation.

If the user is asking a DATA question (about funds, clients, transactions, performance, quality, etc.),
respond with exactly: DATA_QUERY

If the user is having a normal conversation (greeting, asking who you are, chatting, etc.),
respond naturally as AskCI — be friendly, professional, and brief (2-3 sentences).

User message: {question}
"""


def ask(llm, question: str) -> dict:
    try:
        classify_prompt = ChatPromptTemplate.from_messages([
            ("system", CHAT_PROMPT),
            ("human", "{question}")
        ])
        chain = classify_prompt | llm | StrOutputParser()
        response = chain.invoke({"question": question})

        if "DATA_QUERY" not in response:
            return {
                "success": True,
                "sql": "",
                "answer": response.strip(),
                "columns": [],
                "rows": [],
            }

        sql = generate_sql(llm, question)
        columns, rows, error = execute_sql(sql)
        if error:
            return {
                "success": False,
                "error": f"SQL execution error: {error}",
                "sql": sql,
                "answer": f"I generated a query but it failed: {error}. Let me try rephrasing.",
                "columns": [],
                "rows": [],
            }
        answer = generate_answer(llm, question, sql, columns, rows)
        return {
            "success": True,
            "sql": sql,
            "answer": answer,
            "columns": columns,
            "rows": rows,
        }
    except Exception as e:
        global _gemini_cooldown_until
        err_str = str(e).lower()
        if "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str:
            _gemini_cooldown_until = _time.time() + 3600
            print(f"Gemini quota exceeded — cooldown for 1 hour")
        else:
            _gemini_cooldown_until = _time.time() + 60
            print(f"Gemini error: {e} — cooldown for 1 minute")
        return {
            "success": False,
            "error": str(e),
            "sql": "",
            "answer": "",
            "columns": [],
            "rows": [],
        }


# Sandbox mode: runs real SQL against SQLite for live demo feel
SANDBOX_QUERIES = [
    {
        "keywords": ["top", "best", "highest", "performing"],
        "sql": "SELECT fund_name, ytd_return_pct, category, total_aum FROM funds ORDER BY ytd_return_pct DESC LIMIT 5",
        "template": "The top performing funds year-to-date are: {rows_text}. The tech and US equity funds are leading, driven by strong North American market performance.",
        "row_fmt": lambda r: f"{r[0]} ({r[1]:+.2f}%)",
    },
    {
        "keywords": ["worst", "lowest", "bottom", "poor", "underperform"],
        "sql": "SELECT fund_name, ytd_return_pct, category FROM funds ORDER BY ytd_return_pct ASC LIMIT 5",
        "template": "The lowest performing funds year-to-date are: {rows_text}. Emerging markets and fixed income have been under pressure due to rising interest rates and global uncertainty.",
        "row_fmt": lambda r: f"{r[0]} ({r[1]:+.2f}%)",
    },
    {
        "keywords": ["total", "aum", "asset", "manage"],
        "sql": "SELECT fund_name, total_aum, category FROM funds ORDER BY total_aum DESC",
        "template": "CI Financial's total assets under management across all {count} funds is approximately ${total}M CAD. The largest fund by AUM is {top_fund} at ${top_aum}M, followed by {second_fund} at ${second_aum}M.",
        "row_fmt": None,
    },
    {
        "keywords": ["quality", "issue", "problem", "check", "governance", "monitor"],
        "sql": "SELECT table_name, check_type, status, issues_found, details FROM data_quality_log WHERE status != 'PASS' ORDER BY CASE status WHEN 'FAIL' THEN 0 ELSE 1 END",
        "template": "Data quality scan found {count} issues across the platform. {details_text} The transactions table needs immediate attention for data integrity.",
        "row_fmt": lambda r: f"({r[0]}.{r[1]}: {r[2]} - {r[4]})",
    },
    {
        "keywords": ["toronto", "client", "customer"],
        "sql": "SELECT first_name || ' ' || last_name as client, risk_profile, account_type, ROUND(total_portfolio_value, 2) as portfolio_value FROM clients WHERE city = 'Toronto' ORDER BY total_portfolio_value DESC",
        "template": "There are {count} clients based in Toronto. The largest portfolio belongs to {top_client} at ${top_val} ({top_risk}, {top_acct}). Most Toronto clients lean toward aggressive or moderate risk profiles.",
        "row_fmt": None,
    },
    {
        "keywords": ["risk", "profile", "conservative", "aggressive", "moderate"],
        "sql": "SELECT risk_profile, COUNT(*) as client_count, ROUND(AVG(total_portfolio_value), 2) as avg_portfolio FROM clients GROUP BY risk_profile ORDER BY avg_portfolio DESC",
        "template": "Client risk profile breakdown: {rows_text}. The portfolio shows a healthy distribution across risk appetites.",
        "row_fmt": lambda r: f"{r[0]}: {r[1]} clients (avg ${r[2]:,.0f})",
    },
    {
        "keywords": ["transaction", "recent", "trade", "buy", "sell"],
        "sql": "SELECT t.txn_date, c.first_name || ' ' || c.last_name as client, f.fund_name, t.txn_type, ROUND(t.total_amount, 2) as amount FROM transactions t JOIN clients c ON t.client_id = c.client_id JOIN funds f ON t.fund_id = f.fund_id ORDER BY t.txn_date DESC LIMIT 10",
        "template": "Here are the {count} most recent transactions. Total activity shows a mix of buys, sells, and dividend reinvestments across the platform.",
        "row_fmt": None,
    },
    {
        "keywords": ["category", "type", "breakdown", "allocation"],
        "sql": "SELECT category, COUNT(*) as fund_count, ROUND(SUM(total_aum), 1) as total_aum, ROUND(AVG(ytd_return_pct), 2) as avg_return FROM funds GROUP BY category ORDER BY total_aum DESC",
        "template": "Fund category breakdown: {rows_text}. Equity funds dominate the AUM allocation.",
        "row_fmt": lambda r: f"{r[0]}: {r[1]} funds, ${r[2]}M AUM, {r[3]:+.2f}% avg YTD",
    },
    {
        "keywords": ["benchmark", "index", "compare"],
        "sql": "SELECT benchmark_name, ticker, asset_class, ytd_return_pct, one_year_return_pct FROM benchmarks ORDER BY ytd_return_pct DESC",
        "template": "Benchmark performance: {rows_text}. Use these to evaluate fund alpha generation.",
        "row_fmt": lambda r: f"{r[0]} ({r[1]}): YTD {r[3]:+.2f}%, 1Y {r[4]:+.2f}%",
    },
    {
        "keywords": ["holding", "position", "portfolio"],
        "sql": "SELECT c.first_name || ' ' || c.last_name as client, f.fund_name, h.units, ROUND(h.market_value, 2) as market_value, ROUND(h.gain_loss_pct, 2) as gain_loss_pct FROM holdings h JOIN clients c ON h.client_id = c.client_id JOIN funds f ON h.fund_id = f.fund_id ORDER BY h.market_value DESC LIMIT 10",
        "template": "Top {count} holdings by market value across all clients. The largest positions show significant concentration in growth-oriented funds.",
        "row_fmt": None,
    },
]


CHAT_RESPONSES = [
    # ---- How are you (before greetings — multi-word phrases match first) ----
    {
        "keywords": ["how are you", "how's it going", "how do you do", "how you doing", "你怎么样", "你好吗", "最近怎么样"],
        "answer": "I'm doing great, thanks for asking! 😊 Ready to help you explore CI Financial's data. "
                  "What would you like to know — fund performance, client insights, or data quality?",
    },
    # ---- Greetings ----
    {
        "keywords": ["hello", "hey", "hi", "good morning", "good afternoon", "good evening", "你好", "嗨", "哈喽", "早上好", "下午好", "晚上好"],
        "answer": "Hey there! 👋 I'm **AskCI**, CI Financial's AI data assistant. "
                  "I can help you query fund performance, analyze client portfolios, check data quality, and more. "
                  "What can I help you with today?",
    },
    # ---- Farewell ----
    {
        "keywords": ["bye", "goodbye", "see you", "good night", "再见", "拜拜", "回见", "晚安"],
        "answer": "Goodbye! Feel free to come back anytime you need data insights. Have a great day! 👋",
    },
    # ---- Thanks ----
    {
        "keywords": ["thank", "thanks", "thx", "appreciate", "谢谢", "感谢", "多谢"],
        "answer": "You're welcome! Let me know if you need anything else. I'm here to help you navigate CI Financial's data landscape.",
    },
    # ---- Identity ----
    {
        "keywords": ["who are you", "about you", "your name", "introduce yourself", "你是谁", "介绍一下", "你叫什么", "what is askci", "what's askci"],
        "answer": "I'm **AskCI** — CI Financial's AI Data Intelligence Assistant, built by the Data, Analytics & AI team.\n\n"
                  "I use **natural language processing** to translate your questions into SQL queries against our investment data warehouse. "
                  "I can analyze fund performance, client portfolios, transaction history, and data quality metrics.\n\n"
                  "Under the hood, I'm powered by **LangChain + Google Gemini**, with a local fallback engine for reliability.",
    },
    # ---- Age ----
    {
        "keywords": ["how old", "你多大", "几岁", "your age", "when were you born", "年龄", "when were you created"],
        "answer": "I'm **AskCI**, CI Financial's AI Data Intelligence Assistant — I don't have an age, but I was built in 2024 by the Data, Analytics & AI team! "
                  "I'm always learning and improving. Ask me about fund performance, client data, or data quality — that's where I really shine.",
    },
    # ---- Help / Capabilities ----
    {
        "keywords": ["what can you do", "how to use", "what do you do", "capabilities", "你能做什么", "怎么用", "功能", "how does this work"],
        "answer": "I'm **AskCI**, an AI-powered data intelligence assistant. Here's what I can do:\n\n"
                  "**Data Query Tools:**\n"
                  "- Natural language to SQL translation\n"
                  "- Fund performance analysis and ranking\n"
                  "- Client portfolio insights\n"
                  "- Transaction history search\n\n"
                  "**Monitoring Tools:**\n"
                  "- Data quality scoring (completeness, accuracy, timeliness, consistency)\n"
                  "- Anomaly detection and alerting\n"
                  "- SLA tracking for data pipelines\n\n"
                  "**Governance Tools:**\n"
                  "- PII detection and classification\n"
                  "- PIPEDA / SOX compliance tracking\n"
                  "- Data lineage tracing\n\n"
                  "Just ask in plain English — no SQL required!",
    },
    # ---- AI / Technology ----
    {
        "keywords": ["what is ai", "artificial intelligence", "machine learning", "人工智能", "什么是ai"],
        "answer": "Great question! **AI (Artificial Intelligence)** is technology that enables computers to learn from data and make intelligent decisions. "
                  "At CI Financial, we use AI to:\n\n"
                  "- **Natural Language Processing** — So you can ask questions in plain English\n"
                  "- **Anomaly Detection** — Automatically flagging unusual data patterns\n"
                  "- **Predictive Analytics** — Forecasting trends in fund performance\n\n"
                  "AskCI itself is an AI-powered tool that translates your questions into SQL queries!",
    },
    # ---- Market / Finance chat ----
    {
        "keywords": ["market", "stock market", "economy", "economic", "recession", "inflation", "interest rate", "市场", "经济", "股市"],
        "answer": "That's a great topic! While I focus on CI Financial's internal data, I can share that our platform tracks:\n\n"
                  "- **Fund performance** against market benchmarks (S&P/TSX, MSCI)\n"
                  "- **Asset allocation** across equities, fixed income, and alternatives\n"
                  "- **Risk metrics** including volatility and Sharpe ratios\n\n"
                  "Try asking *\"Compare fund performance vs benchmarks\"* or *\"Show risk profiles\"* for specific data!",
    },
    # ---- About CI Financial ----
    {
        "keywords": ["about ci financial", "what is ci financial", "tell me about ci", "ci financial"],
        "answer": "**CI Financial** is one of Canada's largest independent investment management firms, managing over **$400 billion** in assets.\n\n"
                  "Key facts:\n"
                  "- **Headquarters** — Toronto, Ontario, Canada\n"
                  "- **Founded** — 1965\n"
                  "- **Services** — Asset management, wealth management, financial advisory\n"
                  "- **Clients** — Individual investors, institutions, and financial advisors\n\n"
                  "The Data, Analytics & AI team builds tools like AskCI to empower data-driven decision making across the organization.",
    },
    # ---- Team / Who built ----
    {
        "keywords": ["who built", "who made", "who created", "your team", "your creator", "谁做的", "谁开发的"],
        "answer": "I was built by CI Financial's **Data, Analytics & AI team**! The team specializes in:\n\n"
                  "- Building data pipelines and ETL processes on **AWS**\n"
                  "- Creating data models with **dbt** and analytics dashboards\n"
                  "- Developing AI tools like AskCI using **LangChain + Gemini**\n"
                  "- Ensuring data governance and compliance (PIPEDA, SOX)\n\n"
                  "We're passionate about making data accessible to everyone at CI Financial.",
    },
    # ---- Jokes / Fun ----
    {
        "keywords": ["joke", "funny", "make me laugh", "tell me a joke", "讲个笑话", "笑话"],
        "answer": "Here's a data joke for you: Why did the SQL query go to therapy? Because it had too many **inner joins** and couldn't handle the **relationships**! 😄\n\n"
                  "But seriously, I'm better at querying data than telling jokes. Try *\"Show me the worst performing fund\"* — that might be funnier! 📊",
    },
    # ---- Weather ----
    {
        "keywords": ["weather", "天气", "下雨", "温度"],
        "answer": "I don't have access to weather data, but I *do* know the forecast for your **data quality** — let me check! "
                  "Try asking *\"Show me data quality scores\"* or *\"Any data anomalies today?\"* 🌤️",
    },
    # ---- Time ----
    {
        "keywords": ["what time", "几点了", "现在几点", "what day"],
        "answer": "I don't have a clock, but I can tell you when your **data was last updated**! "
                  "Try asking *\"When was the last data refresh?\"* or check the **Overview** page for the latest pipeline status.",
    },
    # ---- Yes / OK / Agree ----
    {
        "keywords": ["ok", "okay", "sure", "sounds good", "got it", "understood", "好的", "明白", "知道了", "行"],
        "answer": "Great! What would you like to know? Feel free to ask about fund performance, client data, transactions, or data quality — I'm here to help!",
    },
    # ---- Sorry ----
    {
        "keywords": ["sorry", "对不起", "抱歉", "不好意思"],
        "answer": "No need to apologize! I'm here to help. Go ahead and ask me anything about CI Financial's data — funds, clients, transactions, or data quality. 😊",
    },
    # ---- Awesome / Great ----
    {
        "keywords": ["awesome", "great", "amazing", "wonderful", "excellent", "nice", "cool", "棒", "厉害", "太好了", "不错"],
        "answer": "Thank you! I'm glad I could help. Want to dig deeper into the data? Try asking about specific funds, client segments, or data quality metrics!",
    },
    # ---- What is data quality ----
    {
        "keywords": ["what is data quality", "data quality mean", "数据质量是什么"],
        "answer": "**Data Quality** measures how reliable and accurate our data is. At CI Financial, we track four dimensions:\n\n"
                  "- **Completeness** — Are all required fields filled?\n"
                  "- **Accuracy** — Do values match the source of truth?\n"
                  "- **Timeliness** — Is data arriving on schedule?\n"
                  "- **Consistency** — Do values match across systems?\n\n"
                  "Check the **Quality** page for live scores, or ask *\"Show me data quality issues\"*.",
    },
    # ---- What is data lineage ----
    {
        "keywords": ["what is data lineage", "data lineage mean", "数据血缘", "数据流向"],
        "answer": "**Data Lineage** tracks where data comes from, how it's transformed, and where it goes. Think of it as the data's family tree.\n\n"
                  "At CI Financial, we trace data from:\n"
                  "- **Source** — Trading API, CRM, portfolio engine, market feeds\n"
                  "- **Processing** — AWS Glue ETL, Lambda quality checks\n"
                  "- **Modeling** — dbt staging and curated tables\n"
                  "- **Serving** — Dashboard, reporting, analytics\n\n"
                  "Check the **Lineage** page for interactive flowcharts!",
    },
    # ---- Pipeline / ETL ----
    {
        "keywords": ["pipeline", "etl", "data flow", "ingestion", "数据管道"],
        "answer": "CI Financial's data pipeline architecture:\n\n"
                  "**1. Ingestion** — Trading API, CRM exports, portfolio engine, and market feeds push raw data to **Amazon S3**\n"
                  "**2. ETL Processing** — **AWS Glue** cleans, deduplicates, and normalizes the data\n"
                  "**3. Transformation** — **AWS Lambda** handles serverless quality checks and derived calculations\n"
                  "**4. Modeling** — **dbt** builds the curated data models and staging tables\n"
                  "**5. Serving** — Clean data lands in the curated store (funds, clients, transactions, holdings, benchmarks)\n\n"
                  "Check the **Data Lineage** page for visual flowcharts of each pipeline.",
    },
    # ---- Compliance ----
    {
        "keywords": ["compliance", "regulation", "pipeda", "sox", "pii", "privacy", "合规"],
        "answer": "CI Financial's data governance covers:\n\n"
                  "- **PIPEDA** — Personal Information Protection and Electronic Documents Act (Canadian privacy law)\n"
                  "- **SOX** — Sarbanes-Oxley Act compliance for financial reporting integrity\n"
                  "- **PII Detection** — Automated scanning flags tables containing personal identifiable information\n"
                  "- **Data Classification** — Every table is tagged: Public, Internal, Confidential, or Restricted\n\n"
                  "Visit the **Governance** page to see the full compliance matrix.",
    },
    # ---- SQL data queries (with SQL) ----
    {
        "keywords": ["how many fund", "fund count", "number of fund"],
        "answer": None,
        "sql": "SELECT COUNT(*) as total_funds, ROUND(SUM(total_aum),1) as total_aum_m FROM funds",
        "template": "CI Financial currently manages **{count} funds** with a total AUM of **${total}M CAD** across equity, fixed income, balanced, and alternative categories.",
    },
    {
        "keywords": ["how many client", "client count", "number of client"],
        "answer": None,
        "sql": "SELECT COUNT(*) as total, ROUND(AVG(total_portfolio_value),2) as avg_val, ROUND(SUM(total_portfolio_value),2) as total_val FROM clients",
        "template": "We have **{count} active clients** with an average portfolio value of **${avg}** and total assets of **${total_val}**.",
    },
]


def sandbox_ask(question: str) -> dict:
    import re
    ensure_db()
    q = question.lower()

    for chat in CHAT_RESPONSES:
        if any(re.search(r'(?:^|[\s,;!?])' + re.escape(w) + r'(?:$|[\s,;!?.])', q) for w in chat["keywords"]):
            if chat.get("answer") and not chat.get("sql"):
                return {
                    "success": True, "sql": "", "answer": chat["answer"],
                    "columns": [], "rows": [],
                }
            if chat.get("sql"):
                columns, rows, error = execute_sql(chat["sql"])
                if not error and rows:
                    ans = chat.get("template", "")
                    try:
                        ans = ans.replace("{count}", str(rows[0][0]))
                        if len(rows[0]) > 1:
                            ans = ans.replace("{avg}", f"{rows[0][1]:,.2f}")
                        if len(rows[0]) > 2:
                            ans = ans.replace("{total_val}", f"{rows[0][2]:,.2f}")
                        ans = ans.replace("{total}", f"{rows[0][1]:,.1f}" if len(rows[0]) > 1 else "")
                    except Exception:
                        pass
                    return {
                        "success": True, "sql": chat["sql"], "answer": ans,
                        "columns": columns, "rows": [tuple(r) for r in rows],
                    }

    matched = None
    for entry in SANDBOX_QUERIES:
        if any(w in q for w in entry["keywords"]):
            matched = entry
            break
    if not matched:
        return {
            "success": True, "sql": "", "answer":
            "That's an interesting question! I'm **AskCI**, and I specialize in CI Financial's data. "
            "I'd love to help — here are some things I'm great at:\n\n"
            "📊 **Fund performance** — *\"What are the top performing funds?\"*\n"
            "👥 **Client insights** — *\"How many clients are in Toronto?\"*\n"
            "✅ **Data quality** — *\"Show me data quality issues\"*\n"
            "💹 **Transactions** — *\"Show recent trades\"*\n"
            "⚖️ **Risk profiles** — *\"What's the risk profile breakdown?\"*\n\n"
            "Or just chat with me — I'm happy to talk about data, AI, or CI Financial!",
            "columns": [], "rows": [],
        }

    sql = matched["sql"]
    columns, rows, error = execute_sql(sql)

    if error:
        return {
            "success": False, "sql": sql, "error": error,
            "answer": f"Query failed: {error}", "columns": [], "rows": [],
        }

    answer = matched["template"]
    try:
        if matched["row_fmt"] and rows:
            answer = answer.replace("{rows_text}", ", ".join(matched["row_fmt"](r) for r in rows))
        answer = answer.replace("{count}", str(len(rows)))
        if "total" in answer and columns and rows:
            if any("aum" in c.lower() for c in columns):
                aum_idx = next(i for i, c in enumerate(columns) if "aum" in c.lower())
                total = sum(r[aum_idx] for r in rows)
                answer = answer.replace("{total}", f"{total:,.1f}")
                answer = answer.replace("{top_fund}", str(rows[0][0]))
                answer = answer.replace("{top_aum}", f"{rows[0][aum_idx]:,.1f}")
                if len(rows) > 1:
                    answer = answer.replace("{second_fund}", str(rows[1][0]))
                    answer = answer.replace("{second_aum}", f"{rows[1][aum_idx]:,.1f}")
        if rows and "{top_client}" in answer:
            answer = answer.replace("{top_client}", str(rows[0][0]))
            answer = answer.replace("{top_val}", f"{rows[0][3]:,.2f}" if len(rows[0]) > 3 else "N/A")
            answer = answer.replace("{top_risk}", str(rows[0][1]) if len(rows[0]) > 1 else "")
            answer = answer.replace("{top_acct}", str(rows[0][2]) if len(rows[0]) > 2 else "")
        if rows and "{details_text}" in answer:
            details = "; ".join(f"({r[0]}: {r[4]})" for r in rows if len(r) > 4)
            answer = answer.replace("{details_text}", details)
    except Exception:
        pass

    return {
        "success": True, "sql": sql, "answer": answer,
        "columns": columns, "rows": [tuple(r) for r in rows],
    }

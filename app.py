"""
CI Data Intelligence Platform (AskCI v2)
Enterprise-grade Data Intelligence for CI Financial
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import sys
import json
import base64
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from askci_v3.mock_data import create_database, get_connection, DB_PATH
from askci_v3.agent import init_agent, ask, sandbox_ask, _probe_gemini
from askci_v3.nl_engine import ask_local

_probe_gemini()

st.set_page_config(
    page_title="CI Data Intelligence",
    page_icon="askci_v3/icon.png" if os.path.exists("askci_v3/icon.png") else None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- COLOR SCHEME (Dark Theme) ----
C = {
    "bg": "#0f1117",
    "surface": "#1a1d27",
    "card": "#222636",
    "border": "#2e3348",
    "text": "#e4e6f0",
    "muted": "#8a8fa8",
    "accent": "#4f8cff",
    "green": "#2dd4a0",
    "amber": "#f5a623",
    "red": "#ef4444",
    "purple": "#a78bfa",
}

# ---- STATE ----
if not os.path.exists(DB_PATH):
    create_database()
for k, v in [("messages", []), ("show_sql", False), ("page", "overview"),
             ("api_key", os.getenv("GEMINI_API_KEY", "")), ("sandbox", True)]:
    if k not in st.session_state:
        st.session_state[k] = v
if st.session_state.api_key and not st.session_state.api_key.startswith("TEST_"):
    st.session_state.sandbox = False



def _ask(question):
    import re
    from askci_v3.agent import CHAT_RESPONSES
    q = question.lower()
    for chat in CHAT_RESPONSES:
        if any(re.search(r'(?:^|[\s,;!?])' + re.escape(w) + r'(?:$|[\s,;!?.])', q) for w in chat["keywords"]):
            if chat.get("answer") and not chat.get("sql"):
                return {
                    "success": True, "sql": "", "answer": chat["answer"],
                    "columns": [], "rows": [], "_source": "chat",
                }

    api_key = st.session_state.get("api_key", "")
    if api_key and not api_key.startswith("TEST_"):
        import threading, traceback
        result_box = [None]
        error_box = [None]
        def _try_gemini():
            try:
                llm = init_agent(api_key)
                if llm:
                    result_box[0] = ask(llm, question)
            except Exception as e:
                error_box[0] = str(e)
                print(f"Gemini error: {e}")
                traceback.print_exc()
        t = threading.Thread(target=_try_gemini, daemon=True)
        t.start()
        t.join(timeout=6)
        if result_box[0] is not None and result_box[0].get("success"):
            result_box[0]["_source"] = "gemini"
            return result_box[0]
        if result_box[0] is not None and result_box[0].get("answer"):
            result_box[0]["_source"] = "gemini"
            result_box[0]["success"] = True
            return result_box[0]
        err_msg = error_box[0] or ("timeout" if t.is_alive() else "unknown")
        print(f"Gemini failed ({err_msg}), falling back")

    result = sandbox_ask(question)
    if result.get("success") and result.get("answer"):
        result["_source"] = "local"
        return result

    return {
        "success": True, "sql": "", "_source": "local",
        "answer": "I'm **AskCI**, CI Financial's AI data assistant. "
                  "I can help you query fund performance, client data, transactions, "
                  "and data quality metrics. Try asking something like:\n\n"
                  "- *\"What are the top 5 performing funds?\"*\n"
                  "- *\"How many clients are in Toronto?\"*\n"
                  "- *\"Show me data quality issues\"*",
        "columns": [], "rows": [],
    }


def _send(q):
    st.session_state.messages.append({"role": "user", "content": q})
    r = _ask(q)
    st.session_state.messages.append({
        "role": "assistant", "content": r["answer"],
        "sql": r.get("sql", ""), "columns": r.get("columns", []),
        "rows": r.get("rows", []),
    })


@st.cache_data
def _icon_b64():
    p = os.path.join(os.path.dirname(__file__), "icon.png")
    if os.path.exists(p):
        with open(p, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None


# ---- GLOBAL CSS (DARK THEME) ----
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
*,*::before,*::after{{box-sizing:border-box}}
.stApp{{background:{C["bg"]};font-family:'Inter',-apple-system,sans-serif;color:{C["text"]}}}
#MainMenu{{visibility:hidden}}footer{{visibility:hidden}}
.stDeployButton{{display:none}}
header[data-testid="stHeader"]{{display:none}}
div[data-testid="stToolbar"]{{display:none}}

/* Sidebar */
[data-testid="stSidebar"]{{background:{C["surface"]};border-right:1px solid {C["border"]}}}
[data-testid="stSidebar"] *{{color:{C["text"]}!important}}

/* Sidebar buttons - dark nav style */
[data-testid="stSidebar"] button[kind="secondary"]{{
    background:{C["card"]}!important;border:1px solid {C["border"]}!important;
    color:{C["text"]}!important;border-radius:8px!important;font-weight:500!important;
    transition:all .15s!important;
}}
[data-testid="stSidebar"] button[kind="secondary"]:hover{{
    background:rgba(79,140,255,0.12)!important;border-color:{C["accent"]}!important;
    color:{C["accent"]}!important;
}}
[data-testid="stSidebar"] button[kind="secondary"] p{{color:{C["text"]}!important}}
[data-testid="stSidebar"] button[kind="secondary"]:hover p{{color:{C["accent"]}!important}}

/* All inputs dark */
[data-testid="stSidebar"] input{{
    background:{C["card"]}!important;border:1px solid {C["border"]}!important;
    color:{C["text"]}!important;border-radius:6px!important;
}}

/* Main area buttons */
button[kind="secondary"]{{
    background:{C["card"]}!important;border:1px solid {C["border"]}!important;
    color:{C["text"]}!important;border-radius:8px!important;
}}
button[kind="secondary"]:hover{{
    background:rgba(79,140,255,0.12)!important;border-color:{C["accent"]}!important;
    color:{C["accent"]}!important;
}}
button[kind="secondary"] p{{color:{C["text"]}!important}}
button[kind="secondary"]:hover p{{color:{C["accent"]}!important}}
button[kind="primary"]{{
    background:{C["accent"]}!important;border:none!important;
    color:#fff!important;border-radius:8px!important;
}}

/* Chat input dark - override the white bottom bar */
[data-testid="stChatInput"]{{background:{C["card"]}!important;border:1px solid {C["border"]}!important;border-radius:10px!important}}
[data-testid="stChatInput"] textarea{{background:transparent!important;color:{C["text"]}!important;caret-color:{C["text"]}!important}}
[data-testid="stChatInput"] textarea::placeholder{{color:{C["muted"]}!important;opacity:1!important}}
[data-testid="stChatInput"] button{{background:{C["accent"]}!important}}
[data-testid="stChatInput"] *{{background:transparent!important;color:{C["text"]}!important}}
[data-testid="stChatInput"] button *{{color:#fff!important}}
[data-testid="stBottom"]>div{{background:{C["bg"]}!important}}
[data-testid="stBottom"] div{{background:{C["bg"]}!important}}
[data-testid="stBottom"] [data-testid="stChatInput"]{{background:{C["card"]}!important}}
[data-testid="stBottom"] [data-testid="stChatInput"] div{{background:transparent!important}}
.stChatInput{{background:{C["card"]}!important}}
.stChatInput textarea{{color:{C["text"]}!important;caret-color:{C["text"]}!important}}
.stChatInput textarea::placeholder{{color:{C["muted"]}!important;opacity:1!important}}

/* Expander dark */
details{{background:{C["card"]}!important;border:1px solid {C["border"]}!important;border-radius:8px!important}}
details summary{{color:{C["muted"]}!important}}
details summary span{{color:{C["muted"]}!important}}

/* Container/scrollable dark */
[data-testid="stVerticalBlockBorderWrapper"]>div{{background:{C["card"]}!important;border-color:{C["border"]}!important}}

/* Dataframe dark */
[data-testid="stDataFrame"]{{background:{C["card"]}!important;border:1px solid {C["border"]}!important;border-radius:8px!important}}

/* Remove default streamlit padding */
.block-container{{padding-top:1rem;padding-bottom:1rem}}

/* ---- NAV ITEMS ---- */
.nav-item{{
    display:flex;align-items:center;gap:10px;padding:10px 16px;
    border-radius:8px;margin:2px 0;cursor:pointer;font-size:13px;
    font-weight:500;color:{C["muted"]};transition:all .15s;
    text-decoration:none;border:none;background:none;width:100%;text-align:left;
}}
.nav-item:hover{{background:rgba(79,140,255,0.08);color:{C["text"]}}}
.nav-item.active{{
    background:rgba(79,140,255,0.12);color:{C["accent"]};
    border-left:3px solid {C["accent"]};padding-left:13px;
}}

/* ---- KPI CARDS ---- */
.kpi-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0}}
.kpi-card{{
    background:{C["card"]};border:1px solid {C["border"]};border-radius:10px;
    padding:16px 18px;position:relative;
}}
.kpi-label{{font-size:11px;color:{C["muted"]};text-transform:uppercase;letter-spacing:.5px;font-weight:500}}
.kpi-value{{font-size:26px;font-weight:700;color:{C["text"]};margin:6px 0 2px;letter-spacing:-.5px}}
.kpi-delta{{font-size:11px;font-weight:600;padding:2px 8px;border-radius:4px;display:inline-block}}
.kpi-up{{background:rgba(45,212,160,0.12);color:{C["green"]}}}
.kpi-down{{background:rgba(239,68,68,0.12);color:{C["red"]}}}

/* ---- SECTION TITLE ---- */
.sec-title{{
    font-size:12px;font-weight:600;color:{C["muted"]};text-transform:uppercase;
    letter-spacing:.7px;margin:20px 0 10px;display:flex;align-items:center;gap:7px;
}}
.sec-title::before{{content:'';width:5px;height:5px;border-radius:50%;background:{C["accent"]}}}

/* ---- CARD ---- */
.dark-card{{
    background:{C["card"]};border:1px solid {C["border"]};border-radius:10px;
    padding:16px;overflow:hidden;
}}
.dark-card-header{{
    font-size:13px;font-weight:600;color:{C["text"]};margin-bottom:12px;
    display:flex;align-items:center;gap:8px;
}}

/* ---- ALERT ROW ---- */
.alert-row{{
    display:flex;align-items:center;gap:10px;padding:10px 14px;
    border-bottom:1px solid {C["border"]};font-size:12px;
}}
.alert-row:last-child{{border-bottom:none}}
.alert-dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0}}
.dot-critical{{background:{C["red"]}}}
.dot-warning{{background:{C["amber"]}}}
.dot-info{{background:{C["purple"]}}}

/* ---- BADGE ---- */
.badge{{padding:3px 8px;border-radius:4px;font-size:10px;font-weight:600;display:inline-block}}
.badge-green{{background:rgba(45,212,160,0.12);color:{C["green"]}}}
.badge-amber{{background:rgba(245,166,35,0.12);color:{C["amber"]}}}
.badge-red{{background:rgba(239,68,68,0.12);color:{C["red"]}}}
.badge-blue{{background:rgba(79,140,255,0.12);color:{C["accent"]}}}
.badge-purple{{background:rgba(167,139,250,0.12);color:{C["purple"]}}}

/* ---- QUALITY BAR ---- */
.qbar-wrap{{display:flex;align-items:center;gap:10px;margin:6px 0}}
.qbar-label{{font-size:12px;color:{C["text"]};min-width:100px;font-weight:500}}
.qbar-track{{flex:1;height:8px;background:{C["surface"]};border-radius:4px;overflow:hidden}}
.qbar-fill{{height:100%;border-radius:4px;transition:width .3s}}
.qbar-score{{font-size:12px;font-weight:600;min-width:36px;text-align:right}}

/* ---- LINEAGE FLOWCHART ---- */
.fc-title{{font-size:15px;font-weight:700;color:{C["text"]};margin:18px 0 8px}}
.fc-sub{{font-size:11px;color:{C["muted"]};margin-bottom:12px}}
.fc-row{{display:flex;align-items:stretch;gap:0;margin:0 0 10px;position:relative}}
.fc-node{{
    padding:8px 10px;border-radius:10px;font-size:11px;font-weight:600;
    text-align:center;min-width:60px;display:flex;flex-direction:column;
    align-items:center;justify-content:center;line-height:1.3;position:relative;
    white-space:nowrap;
}}
.fc-node small{{font-size:8px;font-weight:400;opacity:.7;margin-top:2px}}
.fc-arrow{{display:flex;align-items:center;padding:0 1px}}
.fc-arrow svg{{width:28px;height:16px}}
.ln-src{{background:rgba(79,140,255,0.12);color:{C["accent"]};border:1px solid rgba(79,140,255,0.25)}}
.ln-s3{{background:rgba(245,166,35,0.12);color:{C["amber"]};border:1px solid rgba(245,166,35,0.25)}}
.ln-etl{{background:rgba(167,139,250,0.12);color:{C["purple"]};border:1px solid rgba(167,139,250,0.25)}}
.ln-tgt{{background:rgba(45,212,160,0.12);color:{C["green"]};border:1px solid rgba(45,212,160,0.25)}}
.ln-lambda{{background:rgba(239,68,68,0.10);color:{C["red"]};border:1px solid rgba(239,68,68,0.2)}}
.fc-badge{{font-size:9px;padding:2px 8px;border-radius:4px;font-weight:500;margin-top:4px}}
.fc-group{{background:{C["card"]};border:1px solid {C["border"]};border-radius:14px;padding:20px 24px;margin-bottom:18px}}
.fc-ts{{font-size:10px;color:{C["muted"]};margin-top:6px;text-align:right}}

/* ---- ARCHITECTURE ---- */
.arch-container{{font-family:Inter,sans-serif;color:{C["text"]}}}
.arch-layer{{background:{C["card"]};border:1px solid {C["border"]};border-radius:14px;padding:18px 22px;margin-bottom:14px}}
.arch-layer-title{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:14px;display:flex;align-items:center;gap:8px}}
.arch-layer-title .dot{{width:8px;height:8px;border-radius:50%;display:inline-block}}
.arch-boxes{{display:flex;gap:10px;flex-wrap:wrap;justify-content:center}}
.arch-box{{padding:12px 16px;border-radius:10px;text-align:center;min-width:110px;flex:1;display:flex;flex-direction:column;align-items:center;gap:4px}}
.arch-box .ab-icon{{font-size:20px;margin-bottom:2px}}
.arch-box .ab-name{{font-size:12px;font-weight:700}}
.arch-box .ab-desc{{font-size:9px;opacity:.7;line-height:1.3}}
.arch-sep{{text-align:center;color:{C["muted"]};font-size:18px;letter-spacing:6px;padding:2px 0}}

/* ---- GOV TABLE ---- */
.gov-table{{width:100%;border-collapse:collapse;font-size:12px}}
.gov-table th{{
    text-align:left;padding:8px 10px;color:{C["muted"]};font-weight:500;
    border-bottom:1px solid {C["border"]};font-size:10px;text-transform:uppercase;letter-spacing:.5px;
}}
.gov-table td{{padding:8px 10px;border-bottom:1px solid {C["border"]};color:{C["text"]}}}
.gov-table tr:hover td{{background:rgba(79,140,255,0.04)}}

/* ---- STATUS PILL ---- */
.status-pill{{
    display:inline-flex;align-items:center;gap:5px;padding:4px 12px;
    border-radius:20px;font-size:11px;font-weight:500;
}}
.pill-healthy{{background:rgba(45,212,160,0.1);color:{C["green"]};border:1px solid rgba(45,212,160,0.2)}}
.pill-alert{{background:rgba(239,68,68,0.1);color:{C["red"]};border:1px solid rgba(239,68,68,0.2)}}

/* ---- CHAT ---- */
.chat-bar{{
    background:{C["card"]};border:1px solid {C["border"]};border-radius:10px;
    padding:12px 16px;margin-top:16px;display:flex;align-items:center;gap:10px;
}}

/* ---- Plotly override ---- */
.stPlotlyChart{{background:transparent!important}}

/* Streamlit native overrides for dark */
.stDataFrame{{background:{C["card"]}!important;border:1px solid {C["border"]}!important;border-radius:8px!important}}
.stExpander{{background:{C["card"]}!important;border:1px solid {C["border"]}!important;border-radius:8px!important}}

/* ---- CHAT WIDGET (v1 style) ---- */
.chat-widget{{
    background:{C["card"]};border:1px solid {C["border"]};border-radius:16px;
    box-shadow:0 8px 40px rgba(0,0,0,0.25), 0 2px 8px rgba(0,0,0,0.15);
    overflow:hidden;
}}
.cw-hdr{{
    background:linear-gradient(135deg,#0A1628 0%,#1E3A5F 100%);
    padding:14px 18px;display:flex;align-items:center;gap:10px;position:relative;
}}
.cw-hdr-dot{{position:absolute;top:10px;right:14px;display:flex;gap:3px}}
.cw-hdr-dot span{{width:4px;height:4px;border-radius:50%;background:rgba(255,255,255,0.4)}}
.cw-title{{color:#fff;font-size:14px;font-weight:600}}
.cw-status{{color:{C["green"]};font-size:10px;display:flex;align-items:center;gap:4px}}
.cw-status::before{{content:'';width:5px;height:5px;border-radius:50%;background:{C["green"]}}}

.cw-welcome{{
    background:{C["surface"]};margin:12px;padding:12px;border-radius:10px;
    font-size:12px;color:{C["text"]};line-height:1.5;display:flex;gap:8px;align-items:flex-start;
}}

/* Chat messages */
.mr{{display:flex;gap:8px;margin:8px 14px;align-items:flex-start}}
.mr.u{{flex-direction:row-reverse}}
.m-av{{flex-shrink:0;margin-top:2px}}
.m-uav{{width:28px;height:28px;border-radius:50%;background:{C["accent"]};
    display:flex;align-items:center;justify-content:center;font-weight:700;
    color:#fff;font-size:10px}}
.mb{{max-width:80%;padding:8px 12px;font-size:13px;line-height:1.55;border-radius:12px}}
.mb.b{{background:{C["surface"]};color:{C["text"]};border:1px solid {C["border"]};border-bottom-left-radius:3px}}
.mb.u{{background:{C["accent"]};color:#fff;border-bottom-right-radius:3px}}

.msg-user{{
    background:{C["accent"]};color:#fff;padding:8px 14px;border-radius:12px 12px 2px 12px;
    font-size:13px;max-width:75%;margin-left:auto;display:block;text-align:right;
}}
.msg-bot{{
    background:{C["surface"]};color:{C["text"]};padding:8px 14px;border-radius:12px 12px 12px 2px;
    font-size:13px;max-width:85%;border:1px solid {C["border"]};
}}
</style>
""", unsafe_allow_html=True)

# ---- SIDEBAR NAVIGATION ----
with st.sidebar:
    _ib64 = _icon_b64()
    if _ib64:
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;padding:8px 0 16px">
            <img src="data:image/png;base64,{_ib64}" style="width:32px;height:32px;border-radius:8px"/>
            <div>
                <div style="font-size:16px;font-weight:700;color:{C['text']}">CI Data Intel</div>
                <div style="font-size:10px;color:{C['muted']}">Intelligence Platform</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;padding:8px 0 16px">
            <div style="width:32px;height:32px;border-radius:8px;background:linear-gradient(135deg,{C['accent']},{C['purple']});
                display:flex;align-items:center;justify-content:center;font-weight:800;color:#fff;font-size:13px">CI</div>
            <div>
                <div style="font-size:16px;font-weight:700;color:{C['text']}">CI Data Intel</div>
                <div style="font-size:10px;color:{C['muted']}">Intelligence Platform</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(f'<div style="height:1px;background:{C["border"]};margin:4px 0 12px"></div>', unsafe_allow_html=True)

    nav_items = [
        ("overview", "Overview", "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1"),
        ("query", "Data Query", "M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"),
        ("quality", "Quality", "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"),
        ("lineage", "Lineage", "M13 10V3L4 14h7v7l9-11h-7z"),
        ("governance", "Governance", "M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"),
        ("alerts", "Alerts", "M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"),
        ("architecture", "Architecture", "M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"),
        ("ai_insights", "✨ AI Insights", "M13 10V3L4 14h7v7l9-11h-7z"),
    ]
    for key, label, path in nav_items:
        active = "active" if st.session_state.page == key else ""
        if st.button(f"{'> ' if active else ''}{label}", key=f"nav_{key}", use_container_width=True):
            st.session_state.page = key
            st.rerun()

    st.markdown(f'<div style="height:1px;background:{C["border"]};margin:12px 0"></div>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:10px;color:{C["muted"]};padding:4px 0">Settings</div>', unsafe_allow_html=True)
    api_key_input = st.text_input("Gemini API Key", value=st.session_state.api_key, type="password", label_visibility="collapsed")
    if api_key_input and not api_key_input.startswith("TEST_"):
        st.session_state.api_key = api_key_input
        st.session_state.sandbox = False
    else:
        st.session_state.sandbox = True
    mode_label = "Live (Gemini)" if not st.session_state.sandbox else "Demo mode"
    st.markdown(f'<div style="font-size:10px;color:{C["green"] if not st.session_state.sandbox else C["muted"]};padding:2px 0">{mode_label}</div>', unsafe_allow_html=True)

@st.cache_data(ttl=300)
def _q(sql):
    c = get_connection()
    df = pd.read_sql(sql, c)
    c.close()
    return df

conn = get_connection()

# ==================================================================
# PAGE: OVERVIEW DASHBOARD
# ==================================================================
if st.session_state.page == "overview":

    # Top bar with status pills
    fund_count = _q("SELECT COUNT(*) as c FROM funds").iloc[0, 0]
    total_aum = _q("SELECT ROUND(SUM(total_aum),1) as a FROM funds").iloc[0, 0]
    anomaly_critical = _q("SELECT COUNT(*) as c FROM anomaly_log WHERE severity='critical' AND status='open'").iloc[0, 0]
    anomaly_warning = _q("SELECT COUNT(*) as c FROM anomaly_log WHERE severity='warning' AND status='open'").iloc[0, 0]
    sla_delayed = _q("SELECT COUNT(*) as c FROM sla_tracking WHERE status='delayed'").iloc[0, 0]
    sla_total = _q("SELECT COUNT(*) as c FROM sla_tracking").iloc[0, 0]
    sla_pct = round((sla_total - sla_delayed) / sla_total * 100) if sla_total else 100

    st.markdown(f"""
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
        <div>
            <div style="font-size:22px;font-weight:700;color:{C['text']}">Data Intelligence Overview</div>
            <div style="font-size:12px;color:{C['muted']}">Last updated: Nov 4, 2026 09:30 EST</div>
        </div>
        <div style="display:flex;gap:8px">
            <span class="status-pill pill-healthy">
                <span style="width:6px;height:6px;border-radius:50%;background:{C['green']}"></span>
                {sla_total - sla_delayed}/{sla_total} Pipelines Healthy
            </span>
            <span class="status-pill pill-alert">
                <span style="width:6px;height:6px;border-radius:50%;background:{C['red']}"></span>
                {anomaly_critical + anomaly_warning} Active Alerts
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # -- 4 KPI Cards --
    avg_quality = _q("SELECT ROUND(AVG(score),0) as s FROM quality_scores").iloc[0, 0]
    table_count = _q("SELECT COUNT(DISTINCT table_name) as c FROM quality_scores").iloc[0, 0]
    anomaly_24h = _q("SELECT COUNT(*) as c FROM anomaly_log WHERE detected_at >= '2026-11-03'").iloc[0, 0]

    st.markdown(f"""
    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-label">Overall Quality Score</div>
            <div class="kpi-value">{int(avg_quality)}<span style="font-size:14px;color:{C['muted']}">/100</span></div>
            <span class="kpi-delta kpi-up">+3 vs last week</span>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Tables Monitored</div>
            <div class="kpi-value">{table_count}</div>
            <span style="font-size:11px;color:{C['muted']}">across 3 schemas</span>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Anomalies (24h)</div>
            <div class="kpi-value">{anomaly_24h}</div>
            <span class="badge badge-red">{anomaly_critical} critical</span>
            <span class="badge badge-amber">{anomaly_warning} warning</span>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">SLA Compliance</div>
            <div class="kpi-value">{sla_pct}%</div>
            <span class="kpi-delta {"kpi-up" if sla_pct >= 90 else "kpi-down"}">{sla_delayed} pipeline{"s" if sla_delayed != 1 else ""} delayed</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # -- Row 2: Quality scores by table + Recent anomalies --
    col_q, col_a = st.columns(2, gap="medium")

    with col_q:
        st.markdown('<div class="sec-title">Quality Scores by Table</div>', unsafe_allow_html=True)
        df_qs = _q("""
            SELECT table_name, ROUND(AVG(score),0) as avg_score
            FROM quality_scores GROUP BY table_name ORDER BY avg_score DESC
        """)
        html = '<div class="dark-card">'
        for _, row in df_qs.iterrows():
            s = int(row["avg_score"])
            color = C["green"] if s >= 85 else (C["amber"] if s >= 70 else C["red"])
            html += f"""
            <div class="qbar-wrap">
                <span class="qbar-label">{row["table_name"]}</span>
                <div class="qbar-track"><div class="qbar-fill" style="width:{s}%;background:{color}"></div></div>
                <span class="qbar-score" style="color:{color}">{s}</span>
            </div>"""
        html += '</div>'
        st.markdown(html, unsafe_allow_html=True)

    with col_a:
        st.markdown('<div class="sec-title">Recent Anomalies</div>', unsafe_allow_html=True)
        df_anom = _q("""
            SELECT detected_at, table_name, anomaly_type, severity, description, status
            FROM anomaly_log WHERE status != 'resolved'
            ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
            detected_at DESC LIMIT 5
        """)
        html = '<div class="dark-card">'
        for _, row in df_anom.iterrows():
            dot_cls = {"critical": "dot-critical", "warning": "dot-warning", "info": "dot-info"}.get(row["severity"], "dot-info")
            badge_cls = {"critical": "badge-red", "warning": "badge-amber", "info": "badge-purple"}.get(row["severity"], "badge-blue")
            html += f"""
            <div class="alert-row">
                <span class="alert-dot {dot_cls}"></span>
                <div style="flex:1">
                    <div style="font-weight:500;color:{C['text']}">{row["description"]}</div>
                    <div style="font-size:10px;color:{C['muted']};margin-top:2px">{row["table_name"]} &middot; {row["detected_at"][:16]}</div>
                </div>
                <span class="badge {badge_cls}">{row["severity"]}</span>
            </div>"""
        html += '</div>'
        st.markdown(html, unsafe_allow_html=True)

    # -- Row 3: Data Lineage snapshot + Governance metadata --
    col_l, col_g = st.columns(2, gap="medium")

    with col_l:
        st.markdown('<div class="sec-title">Data Lineage</div>', unsafe_allow_html=True)
        _ov_arrow = f'<span class="fc-arrow"><svg viewBox="0 0 36 18"><line x1="0" y1="9" x2="28" y2="9" stroke="{C["muted"]}" stroke-width="1.5"/><polygon points="28,4 36,9 28,14" fill="{C["muted"]}"/></svg></span>'
        df_lin = _q("SELECT source_system, target_table FROM lineage_map")
        html = '<div class="dark-card" style="padding:14px 16px">'
        for _, row in df_lin.iterrows():
            html += f'<div class="fc-row" style="margin-bottom:6px">'
            html += f'<div class="fc-node ln-src" style="padding:5px 10px;font-size:10px;min-width:70px">{row["source_system"]}</div>'
            html += _ov_arrow
            html += f'<div class="fc-node ln-tgt" style="padding:5px 10px;font-size:10px;min-width:70px">curated.{row["target_table"]}</div>'
            html += '</div>'
        html += '</div>'
        st.markdown(html, unsafe_allow_html=True)

    with col_g:
        st.markdown('<div class="sec-title">Governance Metadata</div>', unsafe_allow_html=True)
        df_gov = _q("SELECT table_name, owner_team, data_classification, compliance_frameworks FROM governance_metadata")
        html = '<div class="dark-card"><table class="gov-table"><tr><th>Table</th><th>Owner</th><th>Classification</th><th>Compliance</th></tr>'
        for _, row in df_gov.iterrows():
            cls_badge = {"PII": "badge-red", "Sensitive": "badge-amber", "Internal": "badge-blue", "Public": "badge-green"}.get(row["data_classification"], "badge-blue")
            html += f"""<tr>
                <td style="font-weight:500">{row["table_name"]}</td>
                <td>{row["owner_team"]}</td>
                <td><span class="badge {cls_badge}">{row["data_classification"]}</span></td>
                <td style="color:{C['muted']}">{row["compliance_frameworks"] or "—"}</td>
            </tr>"""
        html += '</table></div>'
        st.markdown(html, unsafe_allow_html=True)



# ==================================================================
# PAGE: DATA QUERY (NL-to-SQL Chat)
# ==================================================================
elif st.session_state.page == "query":

    st.markdown(f"""
    <div style="font-size:22px;font-weight:700;color:{C['text']};margin-bottom:4px">Data Query</div>
    <div style="font-size:12px;color:{C['muted']};margin-bottom:16px">Natural language to SQL &mdash; AI Data Assistant</div>
    """, unsafe_allow_html=True)

    _ib64 = _icon_b64()
    _av = (
        f'<img src="data:image/png;base64,{_ib64}" style="width:32px;height:32px;border-radius:50%"/>'
        if _ib64
        else f'<div style="width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,{C["accent"]},{C["purple"]});display:flex;align-items:center;justify-content:center;font-weight:700;color:#fff;font-size:11px">CI</div>'
    )
    _av_sm = (
        f'<img src="data:image/png;base64,{_ib64}" style="width:28px;height:28px;border-radius:50%"/>'
        if _ib64
        else f'<div style="width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,{C["accent"]},{C["purple"]});display:flex;align-items:center;justify-content:center;font-weight:700;color:#fff;font-size:9px">CI</div>'
    )

    chat_col, detail_col = st.columns([6, 6], gap="medium")

    with chat_col:
        # Chat widget header
        st.markdown(f"""
        <div class="chat-widget">
            <div class="cw-hdr">
                {_av}
                <div>
                    <div class="cw-title">Chatting with CI Financial</div>
                    <div class="cw-status">Online</div>
                </div>
                <div class="cw-hdr-dot"><span></span><span></span><span></span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Welcome message
        if not st.session_state.messages:
            st.markdown(f"""
            <div class="cw-welcome">
                {_av_sm}
                <div>
                    <div style="font-size:10px;color:{C["muted"]};margin-bottom:4px">CI Financial just joined the conversation</div>
                    <div>Welcome to CI Financial. I'm your virtual capybara agent. This e-chat may be saved for training and to help me serve you better.</div>
                    <div style="margin-top:8px;font-weight:500">How can I assist with your financial inquiries today?</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Quick actions
        qa2 = [
            ("Top 5 funds", "What are the top 5 performing funds?"),
            ("Data quality", "Show me data quality issues"),
            ("Toronto clients", "Which clients are in Toronto?"),
            ("Total AUM", "What is our total AUM?"),
            ("Worst fund", "Which fund has the worst YTD return?"),
            ("Risk profiles", "Show all client risk profiles"),
        ]
        qc2 = st.columns(3)
        for i, (lbl, q) in enumerate(qa2):
            with qc2[i % 3]:
                if st.button(lbl, key=f"cw_{i}", use_container_width=True):
                    _send(q)
                    st.rerun()

        # Messages area
        chat_box = st.container(height=360)
        with chat_box:
            for msg in st.session_state.messages:
                if msg["role"] == "user":
                    st.markdown(f'<div class="mr u"><div class="m-av"><div class="m-uav">You</div></div><div class="mb u">{msg["content"]}</div></div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="mr"><div class="m-av">{_av_sm}</div><div class="mb b">{msg["content"]}</div></div>', unsafe_allow_html=True)
                    if msg.get("sql"):
                        with st.expander("Show SQL", expanded=False):
                            st.code(msg["sql"], language="sql")

        # Input
        ui = st.chat_input("Type your message here...", key="query_input")
        if ui:
            _send(ui)
            st.rerun()

        # Action buttons
        ec1, ec2 = st.columns(2)
        with ec1:
            if st.button("Clear chat", key="clr", use_container_width=True):
                st.session_state.messages = []
                st.rerun()
        with ec2:
            if st.button("Export", key="export_btn", use_container_width=True):
                pass

    with detail_col:
        st.markdown('<div class="sec-title">Query Results</div>', unsafe_allow_html=True)
        last_bot = None
        for msg in reversed(st.session_state.messages):
            if msg["role"] == "assistant" and msg.get("columns") and msg.get("rows"):
                last_bot = msg
                break

        if last_bot:
            df = pd.DataFrame(last_bot["rows"], columns=last_bot["columns"])
            st.dataframe(df, use_container_width=True, hide_index=True, height=min(len(df) * 38 + 40, 400))

            num_cols = [c for i, c in enumerate(last_bot["columns"])
                        if any(isinstance(row[i], (int, float)) for row in last_bot["rows"])]
            str_cols = [c for c in last_bot["columns"] if c not in num_cols]
            if str_cols and num_cols:
                try:
                    fig = px.bar(df, x=str_cols[0], y=num_cols[0],
                                 color_discrete_sequence=[C["accent"]])
                    fig.update_layout(
                        height=280, margin=dict(l=0, r=0, t=8, b=8),
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(tickangle=-35, tickfont=dict(size=10, color=C["muted"]),
                                   showgrid=False, title=""),
                        yaxis=dict(showgrid=True, gridcolor=C["border"], title="",
                                   tickfont=dict(color=C["muted"])),
                        font=dict(family="Inter", size=11, color=C["text"]),
                    )
                    fig.update_traces(marker=dict(cornerradius=4))
                    st.plotly_chart(fig, use_container_width=True, key="q_chart")
                except Exception:
                    pass
        else:
            st.markdown(f"""
            <div style="text-align:center;padding:80px 30px">
                <div style="font-size:40px;opacity:0.3">&#128203;</div>
                <p style="font-size:14px;color:{C['muted']};margin-top:12px">Query results appear here</p>
                <p style="font-size:12px;color:{C['muted']}">Ask a question to see tables, charts, and insights</p>
            </div>
            """, unsafe_allow_html=True)


# ==================================================================
# PAGE: QUALITY
# ==================================================================
elif st.session_state.page == "quality":

    st.markdown(f"""
    <div style="font-size:22px;font-weight:700;color:{C['text']};margin-bottom:4px">Data Quality</div>
    <div style="font-size:12px;color:{C['muted']};margin-bottom:16px">4-dimension quality scoring: Completeness, Accuracy, Timeliness, Consistency</div>
    """, unsafe_allow_html=True)

    df_qs = _q("SELECT * FROM quality_scores ORDER BY table_name, dimension")
    tables = df_qs["table_name"].unique()

    for tbl in tables:
        tbl_data = df_qs[df_qs["table_name"] == tbl]
        avg = int(tbl_data["score"].mean())
        color = C["green"] if avg >= 85 else (C["amber"] if avg >= 70 else C["red"])

        st.markdown(f"""
        <div class="dark-card" style="margin-bottom:12px">
            <div class="dark-card-header">
                <span style="font-size:15px">{tbl}</span>
                <span class="badge {"badge-green" if avg >= 85 else ("badge-amber" if avg >= 70 else "badge-red")}">{avg}/100</span>
            </div>
        """, unsafe_allow_html=True)

        cols = st.columns(4)
        for idx, (_, row) in enumerate(tbl_data.iterrows()):
            s = int(row["score"])
            dim_color = C["green"] if s >= 85 else (C["amber"] if s >= 70 else C["red"])
            with cols[idx % 4]:
                st.markdown(f"""
                <div style="text-align:center;padding:8px">
                    <div style="font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.5px">{row["dimension"]}</div>
                    <div style="font-size:24px;font-weight:700;color:{dim_color};margin:4px 0">{s}</div>
                    <div style="font-size:10px;color:{C['muted']}">{row["details"][:40]}...</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

    # Quality trend chart
    st.markdown('<div class="sec-title">Quality Distribution</div>', unsafe_allow_html=True)
    fig = px.bar(df_qs, x="table_name", y="score", color="dimension",
                 barmode="group",
                 color_discrete_sequence=[C["accent"], C["green"], C["amber"], C["purple"]])
    fig.update_layout(
        height=320, margin=dict(l=0, r=0, t=8, b=8),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title="", tickfont=dict(color=C["muted"]), showgrid=False),
        yaxis=dict(title="Score", tickfont=dict(color=C["muted"]), showgrid=True,
                   gridcolor=C["border"], range=[0, 105]),
        font=dict(family="Inter", color=C["text"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    font=dict(color=C["muted"])),
    )
    st.plotly_chart(fig, use_container_width=True, key="quality_chart")


# ==================================================================
# PAGE: LINEAGE
# ==================================================================
elif st.session_state.page == "lineage":

    st.markdown(f"""
    <div style="font-size:22px;font-weight:700;color:{C['text']};margin-bottom:4px">Data Lineage</div>
    <div style="font-size:12px;color:{C['muted']};margin-bottom:20px">End-to-end data flow from source systems to curated tables</div>
    """, unsafe_allow_html=True)

    _arrow_svg = f'<span class="fc-arrow"><svg viewBox="0 0 36 18"><line x1="0" y1="9" x2="28" y2="9" stroke="{C["muted"]}" stroke-width="1.5"/><polygon points="28,4 36,9 28,14" fill="{C["muted"]}"/></svg></span>'

    # ── Flowchart 1: Trading Pipeline ──
    st.markdown(f"""
    <div class="fc-group">
        <div class="fc-title">Trading Data Pipeline</div>
        <div class="fc-sub">Trading API &rarr; S3 &rarr; AWS Glue &rarr; funds &amp; transactions</div>
        <div class="fc-row">
            <div class="fc-node ln-src">Trading API<small>raw_trades</small></div>
            {_arrow_svg}
            <div class="fc-node ln-s3">S3<small>raw/trades/</small></div>
            {_arrow_svg}
            <div class="fc-node ln-etl">Glue ETL<small>clean + dedupe</small></div>
            {_arrow_svg}
            <div class="fc-node ln-tgt">curated.funds</div>
        </div>
        <div class="fc-row">
            <div class="fc-node ln-src">Trading API<small>raw_trades</small></div>
            {_arrow_svg}
            <div class="fc-node ln-s3">S3<small>raw/trades/</small></div>
            {_arrow_svg}
            <div class="fc-node ln-etl">Glue ETL<small>normalize</small></div>
            {_arrow_svg}
            <div class="fc-node ln-tgt">curated.transactions</div>
        </div>
        <div class="fc-ts">Last updated: 2026-11-04 06:22</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Flowchart 2: Client & Portfolio Pipeline ──
    st.markdown(f"""
    <div class="fc-group">
        <div class="fc-title">Client &amp; Portfolio Pipeline</div>
        <div class="fc-sub">CRM &amp; Portfolio Engine &rarr; S3 &rarr; dbt / Lambda &rarr; clients &amp; holdings</div>
        <div class="fc-row">
            <div class="fc-node ln-src">CRM Export<small>crm_clients</small></div>
            {_arrow_svg}
            <div class="fc-node ln-s3">S3<small>raw/crm/</small></div>
            {_arrow_svg}
            <div class="fc-node ln-etl">dbt<small>stg_clients</small></div>
            {_arrow_svg}
            <div class="fc-node ln-tgt">curated.clients</div>
        </div>
        <div class="fc-row">
            <div class="fc-node ln-src">Portfolio Engine<small>calc_holdings</small></div>
            {_arrow_svg}
            <div class="fc-node ln-s3">S3<small>raw/holdings/</small></div>
            {_arrow_svg}
            <div class="fc-node ln-lambda">Lambda<small>calc gains</small></div>
            {_arrow_svg}
            <div class="fc-node ln-tgt">curated.holdings</div>
        </div>
        <div class="fc-ts">Last updated: 2026-11-04 07:45</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Flowchart 3: Market Data & Quality Pipeline ──
    st.markdown(f"""
    <div class="fc-group">
        <div class="fc-title">Market Data &amp; Quality Pipeline</div>
        <div class="fc-sub">Market Feed &amp; Quality Engine &rarr; Lambda &rarr; benchmarks &amp; quality log</div>
        <div class="fc-row">
            <div class="fc-node ln-src">Market Feed<small>market_prices</small></div>
            {_arrow_svg}
            <div class="fc-node ln-s3">S3<small>raw/market/</small></div>
            {_arrow_svg}
            <div class="fc-node ln-lambda">Lambda<small>parse + validate</small></div>
            {_arrow_svg}
            <div class="fc-node ln-tgt">curated.benchmarks</div>
        </div>
        <div class="fc-row">
            <div class="fc-node ln-src">Quality Engine<small>scan_results</small></div>
            {_arrow_svg}
            <div class="fc-node ln-lambda">Lambda<small>run checks</small></div>
            {_arrow_svg}
            <div class="fc-node ln-tgt">curated.data_quality_log</div>
        </div>
        <div class="fc-ts">Last updated: 2026-11-04 09:15</div>
    </div>
    """, unsafe_allow_html=True)


# ==================================================================
# PAGE: GOVERNANCE
# ==================================================================
elif st.session_state.page == "governance":

    st.markdown(f"""
    <div style="font-size:22px;font-weight:700;color:{C['text']};margin-bottom:4px">Data Governance</div>
    <div style="font-size:12px;color:{C['muted']};margin-bottom:16px">Metadata, classification, compliance, and access policies</div>
    """, unsafe_allow_html=True)

    df_gov = _q("SELECT * FROM governance_metadata")

    html = '<div class="dark-card"><table class="gov-table">'
    html += '<tr><th>Table</th><th>Owner Team</th><th>Classification</th><th>Compliance</th><th>PII Columns</th><th>Last Audit</th><th>Access Policy</th></tr>'
    for _, row in df_gov.iterrows():
        cls_badge = {"PII": "badge-red", "Sensitive": "badge-amber", "Internal": "badge-blue", "Public": "badge-green"}.get(row["data_classification"], "badge-blue")
        pii = json.loads(row["pii_columns"]) if row["pii_columns"] else []
        pii_str = ", ".join(pii) if pii else "—"
        policy_badge = {"restricted": "badge-red", "role_based": "badge-amber", "open": "badge-green"}.get(row["access_policy"], "badge-blue")
        html += f"""<tr>
            <td style="font-weight:600">{row["table_name"]}</td>
            <td>{row["owner_team"]}</td>
            <td><span class="badge {cls_badge}">{row["data_classification"]}</span></td>
            <td>{row["compliance_frameworks"] or "—"}</td>
            <td style="font-size:11px;color:{C['muted']}">{pii_str}</td>
            <td style="color:{C['muted']}">{row["last_audit_date"]}</td>
            <td><span class="badge {policy_badge}">{row["access_policy"]}</span></td>
        </tr>"""
    html += '</table></div>'
    st.markdown(html, unsafe_allow_html=True)

    # Classification breakdown
    st.markdown('<div class="sec-title">Classification Distribution</div>', unsafe_allow_html=True)
    cls_counts = df_gov["data_classification"].value_counts().reset_index()
    cls_counts.columns = ["classification", "count"]
    fig = px.pie(cls_counts, values="count", names="classification",
                 color_discrete_sequence=[C["red"], C["amber"], C["accent"], C["green"]])
    fig.update_layout(
        height=280, margin=dict(l=0, r=0, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color=C["text"]),
        legend=dict(font=dict(color=C["muted"])),
    )
    fig.update_traces(textfont=dict(color=C["text"]))
    st.plotly_chart(fig, use_container_width=True, key="gov_pie")


# ==================================================================
# PAGE: ALERTS
# ==================================================================
elif st.session_state.page == "alerts":

    st.markdown(f"""
    <div style="font-size:22px;font-weight:700;color:{C['text']};margin-bottom:4px">Alert History</div>
    <div style="font-size:12px;color:{C['muted']};margin-bottom:16px">Anomaly detection log with severity, timestamps, and affected tables</div>
    """, unsafe_allow_html=True)

    df_alerts = _q("""
        SELECT * FROM anomaly_log
        ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
        detected_at DESC
    """)

    # Summary cards
    open_count = len(df_alerts[df_alerts["status"] == "open"])
    ack_count = len(df_alerts[df_alerts["status"] == "acknowledged"])
    resolved_count = len(df_alerts[df_alerts["status"] == "resolved"])

    st.markdown(f"""
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px">
        <div class="kpi-card">
            <div class="kpi-label">Open</div>
            <div class="kpi-value" style="color:{C['red']}">{open_count}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Acknowledged</div>
            <div class="kpi-value" style="color:{C['amber']}">{ack_count}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Resolved</div>
            <div class="kpi-value" style="color:{C['green']}">{resolved_count}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Alert list
    for _, row in df_alerts.iterrows():
        sev_color = {"critical": C["red"], "warning": C["amber"], "info": C["purple"]}.get(row["severity"], C["muted"])
        status_badge = {"open": "badge-red", "acknowledged": "badge-amber", "resolved": "badge-green"}.get(row["status"], "badge-blue")
        sev_badge = {"critical": "badge-red", "warning": "badge-amber", "info": "badge-purple"}.get(row["severity"], "badge-blue")

        st.markdown(f"""
        <div class="dark-card" style="margin-bottom:8px;padding:12px 16px">
            <div style="display:flex;align-items:center;gap:10px">
                <span class="alert-dot" style="background:{sev_color}"></span>
                <div style="flex:1">
                    <div style="font-weight:500;color:{C['text']};font-size:13px">{row["description"]}</div>
                    <div style="font-size:10px;color:{C['muted']};margin-top:3px">
                        {row["table_name"]} &middot; {row["anomaly_type"]} &middot; {row["affected_rows"]} rows affected &middot; {row["detected_at"][:16]}
                    </div>
                </div>
                <span class="badge {sev_badge}">{row["severity"]}</span>
                <span class="badge {status_badge}">{row["status"]}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)


# ==================================================================
# PAGE: ARCHITECTURE
# ==================================================================
elif st.session_state.page == "architecture":

    st.markdown(f"""
    <div style="font-size:22px;font-weight:700;color:{C['text']};margin-bottom:4px">System Architecture</div>
    <div style="font-size:12px;color:{C['muted']};margin-bottom:20px">CI Data Intelligence Platform — End-to-end technical design</div>
    """, unsafe_allow_html=True)

    # Architecture diagram — build as string to avoid markdown parsing
    _a, _m, _am, _p, _g, _r = C["accent"], C["muted"], C["amber"], C["purple"], C["green"], C["red"]
    _blue_bg, _blue_bd = "rgba(79,140,255,0.1)", "rgba(79,140,255,0.2)"
    _amb_bg, _amb_bd = "rgba(245,166,35,0.1)", "rgba(245,166,35,0.2)"
    _pur_bg, _pur_bd = "rgba(167,139,250,0.1)", "rgba(167,139,250,0.2)"
    _grn_bg, _grn_bd = "rgba(45,212,160,0.08)", "rgba(45,212,160,0.2)"
    _red_bg, _red_bd = "rgba(239,68,68,0.08)", "rgba(239,68,68,0.2)"

    def _box(bg, bd, clr, icon, name, desc):
        ic = f'<div class="ab-icon">{icon}</div>' if icon else ""
        return f'<div class="arch-box" style="background:{bg};border:1px solid {bd}">{ic}<div class="ab-name" style="color:{clr}">{name}</div><div class="ab-desc">{desc}</div></div>'

    def _layer(dot, title, sub, boxes):
        return f'<div class="arch-layer"><div class="arch-layer-title"><span class="dot" style="background:{dot}"></span><span style="color:{dot}">{title}</span><span style="color:{_m};font-weight:400;text-transform:none;font-size:9px;letter-spacing:0"> &mdash; {sub}</span></div><div class="arch-boxes">{boxes}</div></div>'

    def _pill(label, bg, bd, clr):
        return f'<span style="font-size:10px;padding:4px 12px;border-radius:20px;background:{bg};border:1px solid {bd};color:{clr}">{label}</span>'

    sep = '<div class="arch-sep">▼ ▼ ▼</div>'

    l1 = _layer(_a, "Data Sources", "External systems feeding raw data",
        _box(_blue_bg,_blue_bd,_a,"\U0001f4ca","Trading API","Real-time trades &amp; fund data") +
        _box(_blue_bg,_blue_bd,_a,"\U0001f464","CRM Export","Client profiles &amp; accounts") +
        _box(_blue_bg,_blue_bd,_a,"\U0001f4bc","Portfolio Engine","Holdings &amp; gain/loss calc") +
        _box(_blue_bg,_blue_bd,_a,"\U0001f4c8","Market Feed","Benchmark prices &amp; indices"))

    l2 = _layer(_am, "Ingestion &amp; Storage", "AWS cloud data pipeline",
        _box(_amb_bg,_amb_bd,_am,"\U0001faa3","Amazon S3","Raw data lake, partitioned by date") +
        _box(_pur_bg,_pur_bd,_p,"⚙️","AWS Glue","ETL: clean, dedupe, normalize") +
        _box(_pur_bg,_pur_bd,_p,"λ","AWS Lambda","Serverless transforms &amp; checks") +
        _box(_amb_bg,_amb_bd,_am,"\U0001f5c4️","dbt","Data modeling &amp; staging"))

    l3 = _layer(_g, "Curated Data Store", "Clean, governed, query-ready tables",
        _box(_grn_bg,_grn_bd,_g,"","funds","10 funds, AUM, returns") +
        _box(_grn_bg,_grn_bd,_g,"","clients","Investors &amp; profiles") +
        _box(_grn_bg,_grn_bd,_g,"","transactions","Buy / sell / dividend") +
        _box(_grn_bg,_grn_bd,_g,"","holdings","Positions &amp; P&amp;L") +
        _box(_grn_bg,_grn_bd,_g,"","benchmarks","Market indices"))

    l4 = _layer(_r, "Intelligence &amp; AI Layer", "NL-to-SQL, anomaly detection, governance",
        _box(_red_bg,_red_bd,_r,"\U0001f916","Gemini AI","NL-to-SQL via LangChain agent") +
        _box(_red_bg,_red_bd,_r,"\U0001f50d","Quality Engine","4-dim scoring &amp; anomaly detection") +
        _box(_red_bg,_red_bd,_r,"\U0001f6e1️","Governance","PII classification, PIPEDA/SOX") +
        _box(_red_bg,_red_bd,_r,"⚡","SLA Monitor","Pipeline latency &amp; freshness"))

    _b2, _bd2 = "rgba(79,140,255,0.08)", "rgba(79,140,255,0.15)"
    l5_boxes = "".join(_box(_b2,_bd2,_a,"",pg,"") for pg in ["Overview","Data Query","Quality","Lineage","Governance","Alerts","Architecture"])
    l5 = f'<div class="arch-layer" style="border-color:rgba(79,140,255,0.3)"><div class="arch-layer-title"><span class="dot" style="background:{_a}"></span><span style="color:{_a}">Presentation Layer</span><span style="color:{_m};font-weight:400;text-transform:none;font-size:9px;letter-spacing:0"> &mdash; Streamlit dashboard with 7 interactive pages</span></div><div class="arch-boxes">{l5_boxes}</div></div>'

    pills = '<div style="margin-top:16px;display:flex;gap:8px;flex-wrap:wrap;justify-content:center">'
    for t in ["Python 3.11","Streamlit","LangChain","Google Gemini","Plotly","SQLite"]:
        pills += _pill(t,_blue_bg,_blue_bd,_a)
    for t in ["AWS S3","AWS Glue","AWS Lambda"]:
        pills += _pill(t,_amb_bg,_amb_bd,_am)
    pills += _pill("dbt",_pur_bg,_pur_bd,_p)
    for t in ["PIPEDA","SOX"]:
        pills += _pill(t,_grn_bg,_grn_bd,_g)
    pills += '</div>'

    arch_html = f'<div class="arch-container">{l1}{sep}{l2}{sep}{l3}{sep}{l4}{sep}{l5}{pills}</div>'
    st.markdown(arch_html, unsafe_allow_html=True)

# ==================================================================
# PAGE: AI INSIGHTS
# ==================================================================
elif st.session_state.page == "ai_insights":
    import numpy as np

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:4px">
        <div style="font-size:22px;font-weight:700;color:{C['text']}">✨ AI Insights</div>
        <span style="background:linear-gradient(135deg,{C['accent']},{C['purple']});color:#fff;font-size:10px;
            padding:3px 10px;border-radius:10px;font-weight:600">Powered by AI</span>
    </div>
    <div style="font-size:12px;color:{C['muted']};margin-bottom:16px">
        Intelligent analytics inspired by Bloomberg ASKB, BlackRock Aladdin &amp; Morgan Stanley AI
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <style>
    div[data-baseweb="tab-list"] {
        overflow-x: auto !important;
        gap: 0 !important;
    }
    div[data-baseweb="tab-list"] button[data-baseweb="tab"] {
        font-size: 14px !important;
        font-weight: 600 !important;
        color: rgba(255,255,255,0.65) !important;
        padding: 10px 16px !important;
        white-space: nowrap !important;
    }
    div[data-baseweb="tab-list"] button[aria-selected="true"] {
        color: #fff !important;
        font-weight: 700 !important;
        background: transparent !important;
    }
    div[data-baseweb="tab-highlight"] {
        background-color: #4F8CFF !important;
        height: 3px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    ai_tab = st.tabs(["📈 Trend Analysis", "📊 Performance Attribution", "🔔 Anomaly Detection", "⚠️ Redemption Risk"])

    # ---- TAB 1: TREND ANALYSIS ----
    with ai_tab[0]:
        st.markdown(f'<div style="font-size:16px;font-weight:600;color:{C["text"]};margin:12px 0 8px">Fund NAV Trend Analysis</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:11px;color:{C["muted"]};margin-bottom:16px">90-day historical NAV with AI-detected trend signals and risk indicators</div>', unsafe_allow_html=True)

        funds_list = _q("SELECT fund_id, fund_name FROM funds ORDER BY fund_name")
        fund_options = {row.iloc[1]: row.iloc[0] for _, row in funds_list.iterrows()}
        selected_funds = st.multiselect("Select funds to compare", list(fund_options.keys()),
            default=list(fund_options.keys())[:3], key="trend_funds")

        if selected_funds:
            fund_ids = [fund_options[f] for f in selected_funds]
            placeholders = ",".join(str(fid) for fid in fund_ids)

            try:
                nav_data = _q(f"""
                    SELECT d.nav_date, d.nav_value, d.daily_return_pct, f.fund_name
                    FROM fund_daily_nav d JOIN funds f ON d.fund_id = f.fund_id
                    WHERE d.fund_id IN ({placeholders}) ORDER BY d.nav_date
                """)

                if not nav_data.empty:
                    # Normalize to 100 base for comparison
                    fig = go.Figure()
                    for fname in nav_data['fund_name'].unique():
                        fd = nav_data[nav_data['fund_name'] == fname].copy()
                        fd['normalized'] = (fd['nav_value'] / fd['nav_value'].iloc[0]) * 100
                        fig.add_trace(go.Scatter(
                            x=fd['nav_date'], y=fd['normalized'],
                            name=fname.replace("CI ", ""), mode='lines',
                            line=dict(width=2),
                            hovertemplate='%{x}<br>%{y:.1f}<extra>%{fullData.name}</extra>'
                        ))
                    fig.update_layout(
                        title=None, height=380,
                        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(color=C['text'], size=11),
                        legend=dict(orientation="h", y=-0.15, font=dict(size=10)),
                        xaxis=dict(gridcolor=C['border'], showgrid=True),
                        yaxis=dict(gridcolor=C['border'], showgrid=True, title="Normalized (Base=100)"),
                        margin=dict(l=50, r=20, t=10, b=60),
                        hovermode='x unified',
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # AI Summary cards
                    c1, c2, c3 = st.columns(3)
                    for i, fname in enumerate(selected_funds[:3]):
                        fd = nav_data[nav_data['fund_name'] == fname]
                        if fd.empty:
                            continue
                        total_ret = ((fd['nav_value'].iloc[-1] / fd['nav_value'].iloc[0]) - 1) * 100
                        volatility = fd['daily_return_pct'].std() * (252 ** 0.5) if 'daily_return_pct' in fd.columns else 0
                        last_5 = fd['daily_return_pct'].tail(5).mean() if len(fd) >= 5 else 0
                        trend = "📈 Uptrend" if last_5 > 0.1 else ("📉 Downtrend" if last_5 < -0.1 else "➡️ Stable")
                        color = C['green'] if total_ret > 0 else C['red']
                        col = [c1, c2, c3][i]
                        col.markdown(f"""
                        <div style="background:{C['card']};border:1px solid {C['border']};border-radius:10px;padding:14px">
                            <div style="font-size:11px;color:{C['muted']};margin-bottom:6px">{fname.replace('CI ','')}</div>
                            <div style="font-size:20px;font-weight:700;color:{color}">{total_ret:+.1f}%</div>
                            <div style="font-size:10px;color:{C['muted']};margin-top:4px">90-day return</div>
                            <div style="margin-top:8px;font-size:11px;color:{C['text']}">{trend}</div>
                            <div style="font-size:10px;color:{C['muted']}">Vol: {volatility:.1f}% ann.</div>
                        </div>
                        """, unsafe_allow_html=True)

                    # AI narrative
                    st.markdown(f"""
                    <div style="background:rgba(79,140,255,0.08);border:1px solid rgba(79,140,255,0.2);border-radius:10px;
                        padding:14px;margin-top:16px">
                        <div style="font-size:12px;font-weight:600;color:{C['accent']};margin-bottom:6px">🤖 AI Trend Summary</div>
                        <div style="font-size:12px;color:{C['text']};line-height:1.6">
                            Based on 90-day analysis: <b>Equity funds</b> show broad upward momentum driven by strong Q3 earnings.
                            <b>CI Tech Innovation Fund</b> displays elevated volatility with a sharp recent spike — recommend monitoring for mean reversion.
                            <b>Fixed Income</b> funds remain stable with low volatility, consistent with the current rate environment.
                            <b>Risk signal:</b> CI Emerging Markets Fund shows a deteriorating trend with increasing downside pressure over the last 2 weeks.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.info("No NAV history data available. Please regenerate the database.")
            except Exception as e:
                st.info(f"Trend data not yet available — regenerate the database to include NAV history. ({e})")

    # ---- TAB 2: PERFORMANCE ATTRIBUTION ----
    with ai_tab[1]:
        st.markdown(f'<div style="font-size:16px;font-weight:600;color:{C["text"]};margin:12px 0 8px">Brinson Performance Attribution</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:11px;color:{C["muted"]};margin-bottom:16px">Decomposing fund returns into allocation, selection, and currency effects — inspired by BlackRock Aladdin Auto Commentary</div>', unsafe_allow_html=True)

        try:
            attr_data = _q("""
                SELECT pa.*, f.fund_name FROM performance_attribution pa
                JOIN funds f ON pa.fund_id = f.fund_id
                ORDER BY f.fund_name, pa.period
            """)

            if not attr_data.empty:
                period_sel = st.selectbox("Period", attr_data['period'].unique().tolist(), key="attr_period")
                pdata = attr_data[attr_data['period'] == period_sel]

                # Waterfall chart for top fund
                if not pdata.empty:
                    fig2 = go.Figure()
                    funds_sorted = pdata.sort_values('active_return_pct', ascending=True)
                    colors = [C['green'] if v >= 0 else C['red'] for v in funds_sorted['active_return_pct']]
                    fig2.add_trace(go.Bar(
                        y=[n.replace("CI ", "") for n in funds_sorted['fund_name']],
                        x=funds_sorted['active_return_pct'],
                        orientation='h', marker_color=colors,
                        text=[f"{v:+.2f}%" for v in funds_sorted['active_return_pct']],
                        textposition='outside',
                        hovertemplate='%{y}<br>Active Return: %{x:.2f}%<extra></extra>'
                    ))
                    fig2.update_layout(
                        title=None, height=350,
                        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(color=C['text'], size=11),
                        xaxis=dict(gridcolor=C['border'], title="Active Return vs Benchmark (%)"),
                        yaxis=dict(gridcolor=C['border']),
                        margin=dict(l=160, r=60, t=10, b=40),
                    )
                    st.plotly_chart(fig2, use_container_width=True)

                    # Attribution breakdown table
                    st.markdown(f'<div style="font-size:13px;font-weight:600;color:{C["text"]};margin:12px 0 8px">Attribution Breakdown — {period_sel}</div>', unsafe_allow_html=True)

                    for _, row in pdata.iterrows():
                        active = row['active_return_pct']
                        ac = C['green'] if active >= 0 else C['red']
                        st.markdown(f"""
                        <div style="background:{C['card']};border:1px solid {C['border']};border-radius:8px;padding:12px;margin-bottom:8px">
                            <div style="display:flex;justify-content:space-between;align-items:center">
                                <div style="font-size:13px;font-weight:600;color:{C['text']}">{row['fund_name']}</div>
                                <div style="font-size:14px;font-weight:700;color:{ac}">{active:+.2f}% active</div>
                            </div>
                            <div style="display:flex;gap:16px;margin-top:8px;font-size:11px">
                                <span style="color:{C['muted']}">Fund: <b style="color:{C['text']}">{row['total_return_pct']:.2f}%</b></span>
                                <span style="color:{C['muted']}">Bench: <b style="color:{C['text']}">{row['benchmark_return_pct']:.2f}%</b></span>
                                <span style="color:{C['muted']}">Alloc: <b style="color:{C['accent']}">{row['allocation_effect_pct']:+.2f}%</b></span>
                                <span style="color:{C['muted']}">Select: <b style="color:{C['purple']}">{row['selection_effect_pct']:+.2f}%</b></span>
                                <span style="color:{C['muted']}">FX: <b style="color:{C['amber']}">{row['currency_effect_pct']:+.2f}%</b></span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    # AI narrative
                    top_fund = pdata.loc[pdata['active_return_pct'].idxmax()]
                    worst_fund = pdata.loc[pdata['active_return_pct'].idxmin()]
                    st.markdown(f"""
                    <div style="background:rgba(79,140,255,0.08);border:1px solid rgba(79,140,255,0.2);border-radius:10px;
                        padding:14px;margin-top:12px">
                        <div style="font-size:12px;font-weight:600;color:{C['accent']};margin-bottom:6px">🤖 AI Attribution Commentary</div>
                        <div style="font-size:12px;color:{C['text']};line-height:1.6">
                            <b>{period_sel} highlights:</b> <b>{top_fund['fund_name']}</b> led with {top_fund['active_return_pct']:+.2f}% active return,
                            driven primarily by strong security selection ({top_fund['selection_effect_pct']:+.2f}%).
                            <b>{worst_fund['fund_name']}</b> underperformed at {worst_fund['active_return_pct']:+.2f}%,
                            with adverse allocation ({worst_fund['allocation_effect_pct']:+.2f}%) being the main drag.
                            Currency effects were {'significant' if abs(top_fund['currency_effect_pct']) > 0.3 else 'modest'} across the complex.
                            <br><b>Recommendation:</b> Review {worst_fund['fund_name'].replace('CI ','')} sector positioning and consider rebalancing.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No attribution data available.")
        except Exception as e:
            st.info(f"Attribution data not yet available — regenerate the database. ({e})")

    # ---- TAB 3: ANOMALY DETECTION ----
    with ai_tab[2]:
        st.markdown(f'<div style="font-size:16px;font-weight:600;color:{C["text"]};margin:12px 0 8px">AI Anomaly Detection</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:11px;color:{C["muted"]};margin-bottom:16px">Statistical anomaly detection on fund flows using z-score analysis — inspired by Bloomberg ASKB</div>', unsafe_allow_html=True)

        try:
            flow_data = _q("""
                SELECT ff.*, f.fund_name FROM fund_flows ff
                JOIN funds f ON ff.fund_id = f.fund_id
                ORDER BY f.fund_name, ff.flow_month
            """)

            if not flow_data.empty:
                # Net flow chart
                latest_month = flow_data['flow_month'].max()
                latest_flows = flow_data[flow_data['flow_month'] == latest_month].sort_values('net_flow')

                fig3 = go.Figure()
                colors3 = [C['green'] if v >= 0 else C['red'] for v in latest_flows['net_flow']]
                fig3.add_trace(go.Bar(
                    y=[n.replace("CI ", "") for n in latest_flows['fund_name']],
                    x=latest_flows['net_flow'],
                    orientation='h', marker_color=colors3,
                    text=[f"${v:,.0f}M" for v in latest_flows['net_flow']],
                    textposition='outside',
                ))
                fig3.update_layout(
                    title=f"Net Fund Flows — {latest_month}", height=350,
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color=C['text'], size=11),
                    xaxis=dict(gridcolor=C['border'], title="Net Flow ($M)"),
                    margin=dict(l=160, r=60, t=35, b=40),
                )
                st.plotly_chart(fig3, use_container_width=True)

                # Z-score anomaly detection
                st.markdown(f'<div style="font-size:13px;font-weight:600;color:{C["text"]};margin:8px 0">🔍 Detected Anomalies</div>', unsafe_allow_html=True)

                anomaly_count = 0
                for fname in flow_data['fund_name'].unique():
                    fd = flow_data[flow_data['fund_name'] == fname]
                    if len(fd) < 3:
                        continue
                    mean_flow = fd['net_flow'].mean()
                    std_flow = fd['net_flow'].std()
                    if std_flow == 0:
                        continue
                    latest = fd[fd['flow_month'] == latest_month]
                    if latest.empty:
                        continue
                    z = (latest['net_flow'].iloc[0] - mean_flow) / std_flow
                    if abs(z) > 1.5:
                        anomaly_count += 1
                        severity = "critical" if abs(z) > 2.5 else ("warning" if abs(z) > 2 else "info")
                        sev_color = {"critical": C['red'], "warning": C['amber'], "info": C['accent']}[severity]
                        direction = "outflow spike" if z < 0 else "inflow spike"
                        st.markdown(f"""
                        <div style="background:{C['card']};border-left:3px solid {sev_color};border-radius:0 8px 8px 0;padding:12px;margin-bottom:8px">
                            <div style="display:flex;justify-content:space-between;align-items:center">
                                <div>
                                    <span style="font-size:13px;font-weight:600;color:{C['text']}">{fname}</span>
                                    <span style="background:{sev_color}22;color:{sev_color};font-size:9px;padding:2px 8px;
                                        border-radius:8px;margin-left:8px;font-weight:600">{severity.upper()}</span>
                                </div>
                                <div style="font-size:12px;color:{sev_color};font-weight:600">z-score: {z:.1f}</div>
                            </div>
                            <div style="font-size:11px;color:{C['muted']};margin-top:4px">
                                Unusual {direction} detected — net flow ${latest['net_flow'].iloc[0]:,.0f}M vs 12-month avg ${mean_flow:,.0f}M
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                if anomaly_count == 0:
                    st.markdown(f'<div style="color:{C["green"]};font-size:12px;padding:8px">✅ No significant flow anomalies detected this month</div>', unsafe_allow_html=True)

                # AI narrative
                st.markdown(f"""
                <div style="background:rgba(79,140,255,0.08);border:1px solid rgba(79,140,255,0.2);border-radius:10px;
                    padding:14px;margin-top:12px">
                    <div style="font-size:12px;font-weight:600;color:{C['accent']};margin-bottom:6px">🤖 AI Anomaly Analysis</div>
                    <div style="font-size:12px;color:{C['text']};line-height:1.6">
                        Flow analysis identified <b>{anomaly_count} anomalies</b> across the fund complex.
                        Emerging Markets and alternative strategies show elevated outflow patterns, potentially driven by
                        risk-off sentiment and rising rate expectations.
                        <b>Action items:</b> (1) Investigate large redemption sources for advisor concentration risk,
                        (2) Cross-reference with performance data to identify return-driven redemptions,
                        (3) Consider proactive advisor outreach for affected funds.
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("No flow data available.")
        except Exception as e:
            st.info(f"Flow data not yet available — regenerate the database. ({e})")

    # ---- TAB 4: REDEMPTION RISK ----
    with ai_tab[3]:
        st.markdown(f'<div style="font-size:16px;font-weight:600;color:{C["text"]};margin:12px 0 8px">Redemption Risk Scoring</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:11px;color:{C["muted"]};margin-bottom:16px">Composite risk scoring combining flow velocity, performance, and concentration metrics</div>', unsafe_allow_html=True)

        try:
            risk_data = _q("""
                SELECT r.*, f.fund_name, f.total_aum, f.ytd_return_pct
                FROM redemption_risk r JOIN funds f ON r.fund_id = f.fund_id
                ORDER BY r.risk_score DESC
            """)

            if not risk_data.empty:
                # Risk gauge cards
                for _, row in risk_data.iterrows():
                    score = row['risk_score']
                    level = row['risk_level']
                    lc = {"Low": C['green'], "Medium": C['amber'], "High": C['red'], "Critical": "#ff2222"}
                    bar_color = lc.get(level, C['muted'])
                    flow_icon = {"Inflow": "📈", "Stable": "➡️", "Outflow": "📉", "Heavy Outflow": "🔻"}.get(row['flow_trend'], "")

                    st.markdown(f"""
                    <div style="background:{C['card']};border:1px solid {C['border']};border-radius:10px;padding:14px;margin-bottom:8px">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                            <div>
                                <span style="font-size:14px;font-weight:600;color:{C['text']}">{row['fund_name']}</span>
                                <span style="background:{bar_color}22;color:{bar_color};font-size:10px;padding:2px 10px;
                                    border-radius:8px;margin-left:8px;font-weight:600">{level}</span>
                            </div>
                            <div style="font-size:22px;font-weight:800;color:{bar_color}">{score}</div>
                        </div>
                        <div style="background:{C['border']};border-radius:4px;height:6px;overflow:hidden;margin-bottom:8px">
                            <div style="background:{bar_color};height:100%;width:{score}%;border-radius:4px;
                                transition:width 0.5s ease"></div>
                        </div>
                        <div style="display:flex;gap:20px;font-size:11px;color:{C['muted']}">
                            <span>AUM: <b style="color:{C['text']}">${row['total_aum']:,.0f}M</b></span>
                            <span>YTD: <b style="color:{C['green'] if row['ytd_return_pct'] >= 0 else C['red']}">{row['ytd_return_pct']:+.1f}%</b></span>
                            <span>Flow: <b style="color:{C['text']}">{flow_icon} {row['flow_trend']}</b></span>
                            <span>Advisor Conc: <b style="color:{C['text']}">{row['advisor_concentration']:.0f}%</b></span>
                            <span>Perf vs Bench: <b style="color:{C['green'] if row['performance_vs_benchmark'] >= 0 else C['red']}">{row['performance_vs_benchmark']:+.1f}%</b></span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                # AI narrative
                high_risk = risk_data[risk_data['risk_level'].isin(["High", "Critical"])]
                total_aum_at_risk = high_risk['total_aum'].sum() if not high_risk.empty else 0
                st.markdown(f"""
                <div style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.2);border-radius:10px;
                    padding:14px;margin-top:12px">
                    <div style="font-size:12px;font-weight:600;color:{C['red']};margin-bottom:6px">🤖 AI Risk Assessment</div>
                    <div style="font-size:12px;color:{C['text']};line-height:1.6">
                        <b>{len(high_risk)} fund{'s' if len(high_risk) != 1 else ''}</b> flagged as high/critical redemption risk,
                        representing <b>${total_aum_at_risk:,.0f}M</b> in AUM.
                        Key drivers: underperformance vs benchmark, elevated advisor concentration, and accelerating outflow velocity.
                        <br><b>Immediate actions:</b> (1) Schedule advisor retention calls for top-concentrated positions,
                        (2) Prepare performance attribution talking points for client meetings,
                        (3) Evaluate fee competitiveness for at-risk funds against peer group.
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("No risk scoring data available.")
        except Exception as e:
            st.info(f"Risk data not yet available — regenerate the database. ({e})")


conn.close()

# ---- FLOATING ASKCI BUTTON (all pages except query) ----
if st.session_state.page != "query":
    import streamlit.components.v1 as _components
    _ico = _icon_b64()
    _avatar_src = f'data:image/png;base64,{_ico}' if _ico else ''
    _avatar_img = f'<img src="{_avatar_src}" style="width:34px;height:34px;border-radius:50%;object-fit:cover;border:2px solid rgba(255,255,255,0.3)">' if _ico else '<span style="font-size:22px">🐹</span>'
    # Visual floating button via st.markdown (renders in main document)
    st.markdown(f"""
    <style>
    .askci-fab{{
        position:fixed;bottom:32px;right:32px;z-index:9999;
        display:flex;align-items:center;gap:10px;
        background:linear-gradient(135deg,{C['accent']},{C['purple']});
        padding:8px 20px 8px 8px;border-radius:40px;
        cursor:pointer;box-shadow:0 4px 20px rgba(79,140,255,0.4);
        transition:all 0.3s ease;text-decoration:none;border:none;
    }}
    .askci-fab:hover{{
        transform:translateY(-3px);
        box-shadow:0 8px 32px rgba(79,140,255,0.6);
    }}
    .askci-fab span{{
        color:#fff;font-weight:600;font-size:14px;font-family:'Inter',sans-serif;
    }}
    </style>
    <div class="askci-fab" id="askci-fab">
        {_avatar_img}
        <span>AskCI</span>
    </div>
    """, unsafe_allow_html=True)
    # Invisible iframe just for the click handler script
    _components.html("""
    <script>
    (function() {
        var fab = window.parent.document.querySelector('.askci-fab');
        if (fab && !fab._bound) {
            fab._bound = true;
            fab.addEventListener('click', function() {
                var btns = window.parent.document.querySelectorAll('button');
                for (var i = 0; i < btns.length; i++) {
                    if (btns[i].textContent.trim().indexOf('Data Query') !== -1) {
                        btns[i].click();
                        break;
                    }
                }
            });
        }
    })();
    </script>
    """, height=0)

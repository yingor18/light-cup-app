import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
import requests
from datetime import datetime

# 設定網頁
st.set_page_config(page_title="燈閪盃落注系統", layout="wide")
st_autorefresh(interval=30000, key="datarefresh")

# ==================== 🔗 核心設定區 ====================
SHEET_ID = "1ZkA6GA8JXs2oCh2rNSr_4XA7HNuxBdUjeZF4y-UyBh0"
GOOGLE_FORM_ID = "1FAIpQLSd2UfBYkCEUGk-Tda5c93u-uqhucltNgpKKtNpXLNSFWp7LIw"

# 剛才搵到嘅 ID
ENTRY_NAME = "entry.1567871226"
ENTRY_MATCH = "entry.846620228"
ENTRY_BET = "entry.254969876"
# ======================================================

# 讀取數據函數
@st.cache_data(ttl=0)
def load_data(sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        if sheet_name == "表單回覆 1":
            if df.columns[0] in ["時間戳記", "Timestamp"]: df = df.iloc[:, 1:]
            if len(df.columns) >= 3: df.columns = ["人名", "場次", "投注"] + list(df.columns[3:])
        return df
    except: return pd.DataFrame()

# 載入所有資料
df_matches = load_data("Matches")
df_bets = load_data("表單回覆 1")
df_players = load_data("Players")
players = df_players["人名"].dropna().astype(str).tolist() if "人名" in df_players.columns else []

st.title("🏆 世界盃 - 燈閪盃系統")

# 1. 側邊欄落注
st.sidebar.header("🔥 兄弟落注")
with st.sidebar.form("bet_form", clear_on_submit=True):
    u = st.selectbox("你是誰？", ["請選擇"] + players)
    m = st.selectbox("選場次", df_matches["場次"].tolist() if not df_matches.empty else [])
    b = st.radio("選盤", ["上盤", "下盤"])
    sub = st.form_submit_button("確認落注")
    
    if sub:
        if u == "請選擇": st.error("請選名字！")
        else:
            # 自動生成連結
            url = f"https://docs.google.com/forms/d/{GOOGLE_FORM_ID}/viewform?usp=pp_url&{ENTRY_NAME}={requests.utils.quote(u)}&{ENTRY_MATCH}={requests.utils.quote(m)}&{ENTRY_BET}={requests.utils.quote(b)}"
            st.success("準備好喇！")
            st.markdown(f"[👉 點我提交落注]({url})")
            st.info("撳入去記得按「提交」先會寫入後台！")

# 2. 顯示內容
tab1, tab2 = st.tabs(["📊 燈閪榜", "📋 全部紀錄"])

with tab1:
    st.subheader("👑 積分榜")
    st.info("系統已連線，落注後撳提交，稍候即可計分。")

with tab2:
    st.subheader("📋 落注清單")
    if not df_bets.empty: st.dataframe(df_bets)
    else: st.warning("目前未有落注紀錄。")

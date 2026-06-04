import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
import requests
from datetime import datetime

# ==================== 設定區 ====================
SHEET_ID = "1ZkA6GA8JXs2oCh2rNSr_4XA7HNuxBdUjeZF4y-UyBh0"
GAS_URL = "https://script.google.com/macros/s/AKfycbziToDdXkbc-tG9G_snGu8CnEFAMHjAjVGT-uBecEB6CmPMt4xed_6U8VYAef45cW02gA/exec"

st.set_page_config(page_title="燈閪盃落注系統", layout="wide")
st_autorefresh(interval=30000, key="datarefresh")

st.title("🏆 世界盃 - 燈閪盃系統")

@st.cache_data(ttl=0)
def load_data(sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        return df
    except: return pd.DataFrame()

df_matches = load_data("Matches")
df_bets = load_data("表單回覆 1")
df_players = load_data("Players")
players_list = df_players["人名"].dropna().astype(str).tolist() if "人名" in df_players.columns else []

# 封盤邏輯
active_matches = []
if not df_matches.empty:
    for _, row in df_matches.iterrows():
        m_name = str(row["場次"]).strip()
        is_expired = False
        if "開賽時間" in df_matches.columns and pd.notna(row["開賽時間"]):
            try:
                if datetime.now() >= datetime.strptime(str(row["開賽時間"]).strip(), "%Y-%m-%d %H:%M"):
                    is_expired = True
            except: pass
        if not is_expired: active_matches.append(m_name)

# 側邊欄落注
st.sidebar.header("🎲 兄弟落注")
with st.sidebar.form("bet_form", clear_on_submit=True):
    u = st.selectbox("你是哪位？", ["選擇名字"] + players_list)
    m = st.selectbox("選場次", active_matches)
    b = st.radio("盤口", ["上盤", "下盤"])
    if st.form_submit_button("🔥 一鍵提交"):
        if u == "選擇名字": st.error("請揀名！")
        else:
            try:
                requests.get(GAS_URL, params={'name': u, 'match': m, 'bet': b}, timeout=10)
                st.success("✅ 落注成功！")
            except: st.error("❌ 連線錯誤")

# 顯示介面
tab1, tab2 = st.tabs(["📊 燈閪榜", "📋 落注紀錄"])

with tab1:
    st.write("系統已連線。")
    if not df_bets.empty: st.dataframe(df_bets)

with tab2:
    if not df_bets.empty: st.dataframe(df_bets)

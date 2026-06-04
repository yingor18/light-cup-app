import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
import requests
from datetime import datetime

# ==================== 設定區 ====================
SHEET_ID = "1ZkA6GA8JXs2oCh2rNSr_4XA7HNuxBdUjeZF4y-UyBh0"
GAS_URL = "https://script.google.com/macros/s/AKfycbziToDdXkbc-tG9G_snGu8CnEFAMHjAjVGT-uBecEB6CmPMt4xed_6U8VYAef45cW02gA/exec"

st.set_page_config(page_title="世界盃亞盤燈閪盃 🏆", layout="wide")
st_autorefresh(interval=30000, key="datarefresh")

st.title("🏆 世界盃 - 讓球亞盤「燈閪盃」")
st.subheader("全自動流：夠鐘自動封盤 | 莊家入波膽自動計分")

# 數據讀取
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

df_matches = load_data("Matches")
df_bets = load_data("表單回覆 1")
df_players = load_data("Players")
players_list = df_players["人名"].dropna().astype(str).tolist() if "人名" in df_players.columns else []

# 封盤邏輯
now = datetime.now()
active_matches = []
match_status_dict = {}
if not df_matches.empty:
    for _, row in df_matches.iterrows():
        m_name = str(row["場次"]).strip()
        is_expired = False
        if "開賽時間" in df_matches.columns and pd.notna(row["開賽時間"]):
            try:
                if now >= datetime.strptime(str(row["開賽時間"]).strip(), "%Y-%m-%d %H:%M"): is_expired = True
            except: pass
        match_status_dict[m_name] = "🔒 封盤" if is_expired else "🟢 投注中"
        if not is_expired: active_matches.append(m_name)

# 側邊欄落注 (GAS 版本)
st.sidebar.header("🎲 兄弟落注")
with st.sidebar.form("bet_form", clear_on_submit=True):
    u = st.selectbox("你是哪位？", ["選擇名字"] + players_list)
    m = st.selectbox("選場次", active_matches)
    b = st.radio("盤口", ["上盤", "下盤"])
    if st.form_submit_button("🔥 一鍵提交"):
        if u == "選擇名字": st.error("請揀名！")
        else:
            try:
                res = requests.get(GAS_URL, params={'name': u, 'match': m, 'bet': b}, timeout=10)
                st.success("✅ 落注成功！")
            except: st.error("❌ 連線錯誤")

# 核心計分邏輯
def calculate_score(h_score, a_score, handicap, is_fav, bet):
    diff = (h_score - a_score + handicap) if is_fav else (a_score - h_score + handicap)
    status = "贏全" if diff >= 0.5 else "贏半" if diff == 0.25 else "走盤" if diff == 0 else "輸半" if diff == -0.25 else "輸全"
    pts_map = {"上盤": {"贏全": 10, "贏半": 5, "走盤": 0, "輸半": -5, "輸全": -10},
               "下盤": {"贏全": -10, "贏半": -5, "走盤": 0, "輸半": 5, "輸全": 10}}
    return pts_map.get(bet, {}).get(status, 0)

# 顯示介面
tab1, tab2, tab3 = st.tabs(["📊 燈閪榜", "📋 落注紀錄", "⚽ 賽程狀態"])

with tab1:
    scores = {p: 0 for p in players_list}
    if not df_matches.empty and "賽果分數" in df_matches.columns:
        for _, m in df_matches.

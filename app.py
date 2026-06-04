import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
import requests

# ==================== 設定區 ====================
SHEET_ID = "1ZkA6GA8JXs2oCh2rNSr_4XA7HNuxBdUjeZF4y-UyBh0"
GAS_URL = "https://script.google.com/macros/s/AKfycbziToDdXkbc-tG9G_snGu8CnEFAMHjAjVGT-uBecEB6CmPMt4xed_6U8VYAef45cW02gA/exec"

st.set_page_config(page_title="燈閪盃落注系統", layout="wide")
st_autorefresh(interval=30000, key="datarefresh")

st.title("🏆 世界盃 - 燈閪盃全自動系統")

# 讀取數據
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

# 側邊欄落注
st.sidebar.header("🎲 兄弟落注")
with st.sidebar.form("bet_form", clear_on_submit=True):
    u = st.selectbox("你是哪位？", ["選擇名字"] + players_list)
    m = st.selectbox("選場次", df_matches["場次"].unique().tolist() if not df_matches.empty else [])
    b = st.radio("盤口", ["上盤", "下盤"])
    if st.form_submit_button("🔥 一鍵提交"):
        if u == "選擇名字": st.error("請揀名！")
        else:
            try:
                requests.get(GAS_URL, params={'name': u, 'match': m, 'bet': b}, timeout=10)
                st.success("✅ 落注成功，請刷新睇紀錄！")
            except: st.error("❌ 連線錯誤，請確認 GAS 權限")

# 顯示介面
tab1, tab2, tab3 = st.tabs(["📋 落注紀錄", "⚽ 賽程表", "📊 積分榜"])

with tab1:
    st.header("📋 全部落注紀錄")
    st.dataframe(df_bets, use_container_width=True)

with tab2:
    st.header("⚽ 完整賽程")
    st.dataframe(df_matches, use_container_width=True)

with tab3:
    st.header("📊 簡單積分榜 (正在開發)")
    st.write("已成功連接數據庫，稍後會自動計算積分。")

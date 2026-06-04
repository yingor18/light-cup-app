import streamlit as st
import pandas as pd
from datetime import datetime
import requests
import urllib.parse

# 設定
SHEET_ID = "1ZkA6GA8JXs2oCh2rNSr_4XA7HNuxBdUjeZF4y-UyBh0"
GAS_URL = "https://script.google.com/macros/s/AKfycbziToDdXkbc-tG9G_snGu8CnEFAMHjAjVGT-uBecEB6CmPMt4xed_6U8VYAef45cW02gA/exec"

st.set_page_config(layout="wide", page_title="燈閪盃系統")
st.title("🏆 世界盃 - 燈閪盃全自動系統")

@st.cache_data(ttl=0)
def load_data(sheet):
    encoded_sheet = urllib.parse.quote(sheet)
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_sheet}"
    return pd.read_csv(url)

# 載入資料
df_matches = load_data("Matches")
df_bets = load_data("表單回覆 1")
df_players = load_data("Players")
players = df_players["人名"].dropna().tolist()

# 計分邏輯
def get_points(res):
    mapping = {"贏全": 10, "贏半": 5, "走盤": 0, "輸半": -5, "輸全": -10}
    return mapping.get(str(res).strip(), 0)

# 計算總分
if not df_bets.empty and "結果分類" in df_matches.columns:
    # 建立合併表
    merged = df_bets.merge(df_matches[['場次', '結果分類']], on='場次', how='left')
    merged['得分'] = merged['結果分類'].apply(get_points)
    leaderboard = merged.groupby('人名')['得分'].sum().reset_index().sort_values(by='得分', ascending=False)
else:
    leaderboard = pd.DataFrame(columns=["人名", "得分"])

# 頁面內容
tab1, tab2 = st.tabs(["📊 積分榜", "📋 原始紀錄"])
with tab1:
    st.table(leaderboard)
with tab2:
    st.dataframe(df_bets, use_container_width=True)

# 側邊欄落注 (保持穩定)
with st.sidebar.form("bet_form", clear_on_submit=True):
    u = st.selectbox("兄弟", ["選擇"] + players)
    m = st.selectbox("場次", df_matches["場次"].unique().tolist())
    b = st.radio("盤口", ["上盤", "下盤"])
    if st.form_submit_button("🔥 提交"):
        requests.get(GAS_URL, params={'name': u, 'match': m, 'bet': b})
        st.success("提交成功！")

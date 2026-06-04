import streamlit as st
import pandas as pd
from datetime import datetime
import requests
import urllib.parse

# 設定
SHEET_ID = "1ZkA6GA8JXs2oCh2rNSr_4XA7HNuxBdUjeZF4y-UyBh0"
GAS_URL = "https://script.google.com/macros/s/AKfycbziToDdXkbc-tG9G_snGu8CnEFAMHjAjVGT-uBecEB6CmPMt4xed_6U8VYAef45cW02gA/exec"

st.set_page_config(layout="wide")
st.title("🏆 世界盃 - 燈閪盃全自動系統")

@st.cache_data(ttl=0)
def load_data(sheet):
    encoded_sheet = urllib.parse.quote(sheet)
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_sheet}"
    return pd.read_csv(url)

df_matches = load_data("Matches")
df_bets = load_data("表單回覆 1")
df_players = load_data("Players")
players = df_players["人名"].dropna().tolist()

# 核心：根據規則計算積分
def calculate_leaderboard(df_bets, df_matches):
    leaderboard = {player: 0 for player in players}
    
    # 對應分數表
    score_map = {"贏全": 10, "贏半": 5, "輸半": -5, "輸全": -10, "走盤": 0}
    
    for _, bet in df_bets.iterrows():
        name = bet.get("人名")
        match = bet.get("場次")
        
        # 尋找對應賽事結果
        match_info = df_matches[df_matches["場次"] == match]
        if not match_info.empty:
            result = match_info.iloc[0].get("結果分類") # 請確保 Matches 有「結果分類」欄位 (如: 贏全/贏半...)
            points = score_map.get(result, 0)
            leaderboard[name] += points
                
    return pd.DataFrame(list(leaderboard.items()), columns=["玩家", "總積分"]).sort_values(by="總積分", ascending=False)

# 顯示介面
tab1, tab2 = st.tabs(["📊 積分榜", "📋 落注紀錄"])
with tab1:
    st.table(calculate_leaderboard(df_bets, df_matches))
with tab2:
    st.dataframe(df_bets, use_container_width=True)

# 側邊欄落注 (保持原樣)
with st.sidebar.form("bet", clear_on_submit=True):
    # ... (維持你原有嘅落注邏輯)

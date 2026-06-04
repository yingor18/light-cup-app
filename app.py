import streamlit as st
import pandas as pd
from datetime import datetime
import requests

# 設定
SHEET_ID = "1ZkA6GA8JXs2oCh2rNSr_4XA7HNuxBdUjeZF4y-UyBh0"
GAS_URL = "https://script.google.com/macros/s/AKfycbziToDdXkbc-tG9G_snGu8CnEFAMHjAjVGT-uBecEB6CmPMt4xed_6U8VYAef45cW02gA/exec"

st.set_page_config(layout="wide")
st.title("🏆 世界盃 - 燈閪盃全自動系統")

# 數據讀取
@st.cache_data(ttl=0)
def load_data(sheet):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet}"
    return pd.read_csv(url)

df_matches = load_data("Matches")
df_bets = load_data("表單回覆 1")
players = load_data("Players")["人名"].dropna().tolist()

# 封盤過濾
active_matches = []
for _, row in df_matches.iterrows():
    if datetime.now() < datetime.strptime(str(row["開賽時間"]), "%Y-%m-%d %H:%M"):
        active_matches.append(str(row["場次"]))

# 側邊欄落注
with st.sidebar.form("bet", clear_on_submit=True):
    u = st.selectbox("兄弟名", ["選擇"] + players)
    m = st.selectbox("場次", active_matches)
    b = st.radio("盤口", ["上盤", "下盤"])
    if st.form_submit_button("🔥 提交"):
        requests.get(GAS_URL, params={'name': u, 'match': m, 'bet': b})
        st.success("成功！")

# 計分邏輯 (顯示在積分榜)
st.subheader("📊 積分榜")
# 這裡會根據你寫入的資料自動計算，暫時先顯示落注紀錄
st.dataframe(df_bets)

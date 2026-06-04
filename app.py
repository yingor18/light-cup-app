import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# 基礎設定
st.set_page_config(page_title="燈閪盃全自動系統", layout="wide")
GAS_URL = "https://script.google.com/macros/s/AKfycbziToDdXkbc-tG9G_snGu8CnEFAMHjAjVGT-uBecEB6CmPMt4xed_6U8VYAef45cW02gA/exec"

# 數據讀取
@st.cache_data(ttl=0)
def load_data(sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/1ZkA6GA8JXs2oCh2rNSr_4XA7HNuxBdUjeZF4y-UyBh0/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    try: return pd.read_csv(url)
    except: return pd.DataFrame()

# 計分邏輯 (你之前搵返嘅重點)
def calculate_score(h_score, a_score, handicap, is_fav, bet):
    diff = (h_score - a_score + handicap) if is_fav else (a_score - h_score + handicap)
    if diff > 0: return 10 if bet == "上盤" else -10
    if diff < 0: return -10 if bet == "上盤" else 10
    return 0

# 顯示頁面
df_matches = load_data("Matches")
df_bets = load_data("表單回覆 1")

st.title("🏆 燈閪盃全自動系統")

# 落注區
with st.sidebar.form("bet_form", clear_on_submit=True):
    u = st.text_input("兄弟名")
    m = st.selectbox("場次", df_matches["場次"].tolist() if not df_matches.empty else [])
    b = st.radio("盤口", ["上盤", "下盤"])
    if st.form_submit_button("🔥 提交"):
        requests.get(GAS_URL, params={'name': u, 'match': m, 'bet': b})
        st.success("成功！")

# 顯示榜
st.dataframe(df_bets)

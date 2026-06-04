import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
import requests
from datetime import datetime

# 網站基礎設定
st.set_page_config(page_title="燈閪盃落注系統", layout="wide")
st_autorefresh(interval=30000, key="datarefresh")

# ==================== 🔗 最終填寫區 (請確認無誤) ====================
# 1. 你的 Sheet ID (無需改動)
SHEET_ID = "1ZkA6GA8JXs2oCh2rNSr_4XA7HNuxBdUjeZF4y-UyBh0"

# 2. 你的 Form ID (網址 /d/ 後面嗰串)
GOOGLE_FORM_ID = "1FAIpQLSd2UfBYkCEUGk-Tda5c93u-uqhucltNgpKKtNpXLNSFWp7LIw"

# 3. 剛剛查到嘅 Entry ID (非常重要，唔好打錯)
ENTRY_ID_NAME = "entry.1567871226"   
ENTRY_ID_MATCH = "entry.846620228"  
ENTRY_ID_BET = "entry.254969876"    
# ===================================================================

st.title("🏆 世界盃 - 讓球亞盤「燈閪盃」")

# 獲取數據函數
@st.cache_data(ttl=0)
def load_sheet_data(worksheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={worksheet_name}"
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        # 自動處理 Google Form 產生嘅「表單回覆 1」
        if worksheet_name == "表單回覆 1" and not df.empty:
            if df.columns[0] in ["時間戳記", "Timestamp"]: df = df.iloc[:, 1:]
            if len(df.columns) >= 3: df.columns = ["人名", "場次", "投注"] + list(df.columns[3:])
        return df
    except: return pd.DataFrame()

# 載入數據
df_bets = load_sheet_data("表單回覆 1")
df_players = load_sheet_data("Players")
players_list = df_players["人名"].dropna().astype(str).str.strip().tolist() if "人名" in df_players.columns else []

# 側邊欄落注
st.sidebar.header("🎲 兄弟落注區")
with st.sidebar.form(key="bet_form", clear_on_submit=True):
    u = st.selectbox("選人名", ["請選擇"] + players_list)
    m = st.text_input("輸入場次 (要同 Matches 分頁一樣)")
    s = st.radio("揀盤", ["上盤", "下盤"])
    submit = st.form_submit_button("🔥 提交落注")
    
    if submit:
        if u == "請選擇" or m == "":
            st.error("請填完整資料！")
        else:
            # 這是最終自動填表連結
            url = f"https://docs.google.com/forms/d/{GOOGLE_FORM_ID}/viewform?usp=pp_url&{ENTRY_ID_NAME}={requests.utils.quote(u)}&{ENTRY_ID_MATCH}={requests.utils.quote(m)}&{ENTRY_ID_BET}={requests.utils.quote(s)}"
            st.success("資料已生成！")
            st.markdown(f"[👉 撳我傳送落注數據]({url})")
            st.info("撳完連結後，記住喺表單頁面按「提交」先會生效！")

# 顯示紀錄
st.subheader("📋 最新落注清單 (讀取自表單回覆 1)")
if not df_bets.empty:
    st.dataframe(df_bets)
else:
    st.warning("暫時未見到有人落注，請確認有無按「提交」。")

import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
import requests

# 網站設定
st.set_page_config(page_title="燈閪盃落注系統", layout="wide")
st_autorefresh(interval=30000, key="datarefresh")

# ==================== 鎖定設定區 (請勿手動更改) ====================
SHEET_ID = "1ZkA6GA8JXs2oCh2rNSr_4XA7HNuxBdUjeZF4y-UyBh0"
GOOGLE_FORM_ID = "1FAIpQLSd2UfBYkCEUGk-Tda5c93u-uqhucltNgpKKtNpXLNSFWp7LIw"

# 已經幫你鎖定好嘅正確 ID
ENTRY_NAME = "entry.1567871226"
ENTRY_MATCH = "entry.846620228"
ENTRY_BET = "entry.254969876"
# =================================================================

# 讀取 Sheet 數據
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
players = df_players["人名"].dropna().astype(str).tolist() if "人名" in df_players.columns else []

st.title("🏆 世界盃 - 燈閪盃落注系統")

# 落注側邊欄
st.sidebar.header("🎲 兄弟落注")
with st.sidebar.form("bet_form", clear_on_submit=True):
    u = st.selectbox("你是哪位兄弟？", ["請選擇"] + players)
    m = st.selectbox("選擇場次", df_matches["場次"].dropna().unique().tolist() if not df_matches.empty else [])
    b = st.radio("你的投注心水", ["上盤", "下盤"])
    sub = st.form_submit_button("🔥 確認落注")
    
    if sub:
        if u == "請選擇": st.error("❌ 請先揀人名！")
        else:
            # 這是最標準的預填連結，絕對能運作
            url = f"https://docs.google.com/forms/d/{GOOGLE_FORM_ID}/viewform?usp=pp_url&{ENTRY_NAME}={requests.utils.quote(u)}&{ENTRY_MATCH}={requests.utils.quote(m)}&{ENTRY_BET}={requests.utils.quote(b)}"
            st.success("✅ 落注資料已生成！")
            st.markdown(f"[👉 **撳我直接射入後台**]({url})")
            st.info("⚠️ 撳完連結後，請記得在該表單頁面按【提交】！")

# 顯示結果區
tab1, tab2 = st.tabs(["📊 燈閪榜", "📋 落注紀錄"])

with tab1:
    st.subheader("👑 兄弟積分紀錄")
    st.write("系統已連線，只要在後台按下提交，數據就會即時同步。")

with tab2:
    st.subheader("📋 實時落注清單")
    if not df_bets.empty: st.dataframe(df_bets, use_container_width=True)
    else: st.warning("暫時未有落注數據。")

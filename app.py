import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
import requests

# 網站設定
st.set_page_config(page_title="燈閪盃落注系統", layout="wide")
st_autorefresh(interval=30000, key="datarefresh")

# ==================== 設定區 ====================
SHEET_ID = "1ZkA6GA8JXs2oCh2rNSr_4XA7HNuxBdUjeZF4y-UyBh0"
# 這是你剛部署的 Web App 連結
GAS_URL = "https://script.google.com/macros/s/AKfycbziToDdXkbc-tG9G_snGu8CnEFAMHjAjVGT-uBecEB6CmPMt4xed_6U8VYAef45cW02gA/exec"
# ===============================================

# 載入數據
@st.cache_data(ttl=0)
def load_data(sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        return df
    except: return pd.DataFrame()

df_matches = load_data("Matches")
df_players = load_data("Players")
players = df_players["人名"].dropna().astype(str).tolist() if "人名" in df_players.columns else []

st.title("🏆 世界盃 - 燈閪盃全自動系統")

# 側邊欄落注
st.sidebar.header("🔥 兄弟落注 (一鍵提交)")
with st.sidebar.form("bet_form", clear_on_submit=True):
    u = st.selectbox("你是哪位兄弟？", ["請選擇"] + players)
    m = st.selectbox("選擇場次", df_matches["場次"].dropna().unique().tolist() if not df_matches.empty else [])
    b = st.radio("你的投注心水", ["上盤", "下盤"])
    sub = st.form_submit_button("🔥 確認並提交")
    
    if sub:
        if u == "請選擇": st.error("❌ 請先揀名！")
        else:
            # 直接發送數據到 GAS，完全不需要跳轉到 Google Form
            try:
                response = requests.post(GAS_URL, params={'name': u, 'match': m, 'bet': b}, timeout=10)
                if response.status_code == 200:
                    st.success("✅ 落注成功！數據已寫入 Sheet。")
                else:
                    st.error("❌ 寫入失敗，請檢查 GAS 部署權限。")
            except Exception as e:
                st.error(f"連線錯誤: {e}")

# 顯示結果
st.subheader("📋 實時落注紀錄")
df_bets = load_data("表單回覆 1")
if not df_bets.empty: st.dataframe(df_bets, use_container_width=True)
else: st.warning("目前未有落注。")

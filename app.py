import streamlit as st
import pandas as pd
import requests
import urllib.parse

# 設定
SHEET_ID = "1ZkA6GA8JXs2oCh2rNSr_4XA7HNuxBdUjeZF4y-UyBh0"
GAS_URL = "https://script.google.com/macros/s/AKfycbxCluMNIcBIU55MRgtd4hldqTikmpMCu1NrrcFtO38eDDPwbtbCsXCGr_rdsVq-1FzWLA/exec"

st.set_page_config(layout="wide", page_title="燈閪盃系統")
st.title("🏆 世界盃 - 燈閪盃總覽")

@st.cache_data(ttl=0)
def load_data(sheet):
    encoded_sheet = urllib.parse.quote(sheet)
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_sheet}"
    return pd.read_csv(url)

# 載入全部資料
df_matches = load_data("Matches")
df_bets = load_data("表單回覆 1")
df_players = load_data("Players")
all_players = df_players["人名"].dropna().astype(str).tolist()

# 計分邏輯 (處理同分同排名)
def get_points(res):
    mapping = {"贏全": 10, "贏半": 5, "走盤": 0, "輸半": -5, "輸全": -10}
    return mapping.get(str(res).strip(), 0)

# 計算並建立排名
if not df_bets.empty and "結果分類" in df_matches.columns:
    merged = df_bets.merge(df_matches[['場次', '結果分類']], on='場次', how='left')
    merged['得分'] = merged['結果分類'].apply(get_points)
    scores = merged.groupby('人名')['得分'].sum().to_dict()
else:
    scores = {}

# 建立 DataFrame 並設置 1-7 排名
leaderboard_data = [{"人名": p, "得分": scores.get(p, 0)} for p in all_players]
leaderboard = pd.DataFrame(leaderboard_data).sort_values(by="得分", ascending=False).reset_index(drop=True)
leaderboard['排名'] = leaderboard['得分'].rank(method='min', ascending=False).astype(int)
leaderboard = leaderboard[['排名', '人名', '得分']]

# 處理賽事表格：令 index 從 1 開始
df_matches_display = df_matches.copy()
df_matches_display.index = df_matches_display.index + 1

# --- 介面呈現 ---
with st.sidebar.form("bet_form", clear_on_submit=True):
    st.header("🎲 兄弟落注")
    u = st.selectbox("選擇名字", all_players)
    m = st.selectbox("選場次", df_matches["場次"].unique().tolist())
    b = st.radio("盤口", ["上盤", "下盤"])
    if st.form_submit_button("🔥 提交"):
        requests.get(GAS_URL, params={'name': u, 'match': m, 'bet': b})
        st.success("提交成功！")

# 修改 Tab 名稱
tab1, tab2, tab3 = st.tabs(["📊 總積分排名", "⚽ 賽程與賽果", "📋 投注紀錄"])

with tab1:
    st.subheader("🏆 燈閪盃兄弟排名")
    st.dataframe(leaderboard, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("⚽ 比賽詳情")
    st.dataframe(df_matches_display, use_container_width=True) # 顯示從1開始的 index

with tab3:
    st.subheader("📋 投注紀錄")
    st.dataframe(df_bets, use_container_width=True)

import streamlit as st
import pandas as pd
import requests
import urllib.parse

# 設定
SHEET_ID = "1ZkA6GA8JXs2oCh2rNSr_4XA7HNuxBdUjeZF4y-UyBh0"
GAS_URL = "https://script.google.com/macros/s/AKfycbziToDdXkbc-tG9G_snGu8CnEFAMHjAjVGT-uBecEB6CmPMt4xed_6U8VYAef45cW02gA/exec"

st.set_page_config(layout="wide", page_title="燈閪盃系統")
st.title("🏆 世界盃 - 燈閪盃總覽")

@st.cache_data(ttl=0)
def load_data(sheet):
    encoded_sheet = urllib.parse.quote(sheet)
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_sheet}"
    return pd.read_csv(url)

# 載入所有 Sheet，加入錯誤處理，如果 Sheet 空會顯示空白 DataFrame
try:
    df_matches = load_data("Matches")
    df_bets = load_data("Bets") # 確保這裡名稱和你 Sheet 裡的 Tab 名稱一模一樣
    df_players = load_data("Players")
    all_players = df_players["人名"].dropna().astype(str).tolist()
except Exception as e:
    st.error(f"讀取 Sheet 失敗，請檢查 Tab 名稱是否正確: {e}")
    st.stop()

# 計分邏輯
# 運算排名 (加入強制類型轉換)
if not df_bets.empty and "結果分類" in df_matches.columns and "場次" in df_bets.columns:
    # --- 關鍵修正：將兩邊的「場次」強制轉為字串，並去除前後空白 ---
    df_bets['場次'] = df_bets['場次'].astype(str).str.strip()
    df_matches['場次'] = df_matches['場次'].astype(str).str.strip()
    
    merged = df_bets.merge(df_matches[['場次', '結果分類']], on='場次', how='left')
    merged['得分'] = merged['結果分類'].apply(get_points)
    scores = merged.groupby('人名')['得分'].sum().to_dict()
else:
    scores = {}def get_points(res):
    mapping = {"贏全": 10, "贏半": 5, "走盤": 0, "輸半": -5, "輸全": -10}
    return mapping.get(str(res).strip(), 0)

# 運算排名
if not df_bets.empty and "結果分類" in df_matches.columns and "場次" in df_bets.columns:
    merged = df_bets.merge(df_matches[['場次', '結果分類']], on='場次', how='left')
    merged['得分'] = merged['結果分類'].apply(get_points)
    scores = merged.groupby('人名')['得分'].sum().to_dict()
else:
    scores = {}

# 建立完整排名
leaderboard_data = [{"人名": p, "得分": scores.get(p, 0)} for p in all_players]
leaderboard = pd.DataFrame(leaderboard_data).sort_values(by="得分", ascending=False).reset_index(drop=True)
leaderboard['排名'] = leaderboard['得分'].rank(method='min', ascending=False).astype(int)
leaderboard = leaderboard[['排名', '人名', '得分']]

# 介面
with st.sidebar.form("bet_form", clear_on_submit=True):
    st.header("🎲 兄弟落注")
    u = st.selectbox("選擇名字", all_players)
    m = st.selectbox("選場次", df_matches["場次"].unique().tolist())
    b = st.radio("盤口", ["上盤", "下盤"])
    if st.form_submit_button("🔥 提交"):
        requests.get(GAS_URL, params={'name': u, 'match': m, 'bet': b})
        st.success("提交成功！請稍候刷新")

tab1, tab2, tab3 = st.tabs(["📊 總積分排名", "⚽ 賽程與賽果", "📋 投注紀錄"])

with tab1:
    st.table(leaderboard.set_index('排名'))

with tab2:
    st.dataframe(df_matches, use_container_width=True)

with tab3:
    st.dataframe(df_bets, use_container_width=True)

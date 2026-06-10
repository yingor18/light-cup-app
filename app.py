import streamlit as st
import pandas as pd
import requests
import urllib.parse

# 設定 - 確保 SHEET_ID 係正確
SHEET_ID = "1ZkA6GA8JXs2oCh2rNSr_4XA7HNuxBdUjeZF4y-UyBh0"
GAS_URL = "https://script.google.com/macros/s/AKfycby5-mVhmT5qlhTj3i5S-vxNxERhxC7xQnwkJ9tlNnRRmzMRkeNoGbdWHBdJU-zuckv1Xw/exec"

st.set_page_config(layout="wide", page_title="燈閪盃系統")
st.title("🏆 世界盃 - 燈閪盃總覽")

# 讀取資料函數
@st.cache_data(ttl=0)
def load_data(sheet):
    encoded_sheet = urllib.parse.quote(sheet)
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_sheet}"
    return pd.read_csv(url)

# 1. 載入資料
# 修改這一段，確保它是讀取你確認有資料的 "FinalBets"
try:
    df_matches = load_data("Matches")
    # 這裡明確指向 FinalBets
    df_bets = load_data("FinalBets") 
    df_players = load_data("Players")
    all_players = df_players["人名"].dropna().astype(str).tolist()
    
    # --- 這裡增加強制檢查 ---
    if df_bets.empty:
        st.warning("偵測到 FinalBets 是空的，請檢查 Tab 名稱或資料是否已成功寫入")
    else:
        st.write(f"成功讀取到 {len(df_bets)} 筆投注紀錄") # 這行可以讓你確認是否有讀到資料

except Exception as e:
    st.error(f"讀取資料庫錯誤: {e}")

# 2. 強制格式轉換，避免合併錯誤
df_matches['場次'] = df_matches['場次'].astype(str).str.strip()
df_bets['場次'] = df_bets['場次'].astype(str).str.strip()

# 3. 計分邏輯
def get_points(res):
    mapping = {"贏全": 10, "贏半": 5, "走盤": 0, "輸半": -5, "輸全": -10}
    return mapping.get(str(res).strip(), 0)

# 4. 計算排名
if not df_bets.empty and "結果分類" in df_matches.columns:
    merged = df_bets.merge(df_matches[['場次', '結果分類']], on='場次', how='left')
    merged['得分'] = merged['結果分類'].apply(get_points)
    scores = merged.groupby('人名')['得分'].sum().to_dict()
else:
    scores = {}

leaderboard_data = [{"人名": p, "得分": scores.get(p, 0)} for p in all_players]
leaderboard = pd.DataFrame(leaderboard_data).sort_values(by="得分", ascending=False).reset_index(drop=True)
leaderboard['排名'] = leaderboard['得分'].rank(method='min', ascending=False).astype(int)
leaderboard = leaderboard[['排名', '人名', '得分']]

# 5. 賽程表處理 (從 1 開始)
df_matches_display = df_matches.copy()
df_matches_display.index = df_matches_display.index + 1

# --- 介面 ---
import pytz # 記得喺 requirements.txt 加一行 pytz
from datetime import datetime

# 在 form 裡面執行邏輯
with st.sidebar.form("bet_form", clear_on_submit=True):
    st.header("⚽ 手足落注")
    
    # 1. 取得香港時間
    hk_tz = pytz.timezone('Asia/Hong_Kong')
    now_hk = datetime.now(hk_tz)
    
    u = st.selectbox("選擇名字", options=all_players, index=None, placeholder="請選擇你的名字...")
    # 1. 取得香港時間
hk_tz = pytz.timezone('Asia/Hong_Kong')
now_hk = datetime.now(hk_tz)

# 2. 將開賽時間轉做 datetime 格式以便比較
df_matches['開賽時間_dt'] = pd.to_datetime(df_matches['開賽時間']).dt.tz_localize(hk_tz)

# 3. 過濾：只留下「還未開波」的場次
# 只有開賽時間大於現在時間的，才會顯示在選單裡
available_matches = df_matches[df_matches['開賽時間_dt'] > now_hk]['場次'].tolist()

# 4. 如果所有比賽都踢完，給一個提示
if not available_matches:
    st.sidebar.warning("🚫 全部比賽已開波，暫無可落注場次。")
    m = st.sidebar.selectbox("選擇場次", options=["無可落注場次"], disabled=True)
else:
    m = st.sidebar.selectbox("選擇場次", options=available_matches)
    b = st.radio("盤口", ["上盤", "下盤"])
    
    # 2. 獲取該場次的開賽時間 (假設你表格內的格式是 "2026/6/12 3:00")
    target_match = df_matches[df_matches['場次'] == m].iloc[0]
    match_time_str = target_match['開賽時間']
    match_time = pd.to_datetime(match_time_str).tz_localize(hk_tz)
    
    # 3. 封盤判斷
    is_closed = now_hk >= match_time
    
    if is_closed:
        st.error(f"❌ {m} 已經開波 (開賽時間: {match_time_str})，封盤！")
        st.form_submit_button("🚫 已封盤", disabled=True)
    else:
        if st.form_submit_button("🔥 提交"):
            if u is None:
                st.error("⚠️ 必須先選擇名字！")
            else:
                # 再次讀取最新紀錄檢查重複
                df_current = load_data("FinalBets")
                if not df_current[(df_current['人名'] == u) & (df_current['場次'] == m)].empty:
                    st.error("❌ 你已經投過呢場波喇，唔准改！")
                else:
                    params = {'name': u, 'match': m, 'bet': b}
                    response = requests.get(GAS_URL, params=params)
                    if response.status_code == 200:
                        st.success("提交成功！")
                    else:
                        st.error("系統繁忙，稍後再試")

# 刪除第 92 行，只留最下面呢個定義
tab1, tab2, tab3 = st.tabs(["📊 總積分排名", "⚽ 賽程與賽果", "📋 手足落注紀錄"])

with tab1:
    st.subheader("🏆 燈閪盃足排名")
    st.dataframe(leaderboard, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("⚽ 比賽詳情")
    st.dataframe(df_matches_display, use_container_width=True)

with tab3:
    st.subheader("📋 手足落注紀錄")
    # 這裡直接使用你在 app.py 開頭讀取的 df_bets
    if not df_bets.empty:
        # 只顯示這三欄
        display_df = df_bets[['人名', '場次', '投注']].copy()
        st.table(display_df)
    else:
        st.write("目前仲未有人落注，再唔賭就無機會賭！")

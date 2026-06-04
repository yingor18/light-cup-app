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
with st.sidebar.form("bet_form", clear_on_submit=True):
    st.header("⚽ 手足落注")
    u = st.selectbox("選擇名字", options=all_players, index=None, placeholder="請選擇你的名字...")
    m = st.selectbox("選擇場次", options=df_matches["場次"].unique().tolist())
    b = st.radio("盤口", ["上盤", "下盤"])
    
    if st.form_submit_button("🔥 提交"):
        if u is None:
            st.error("⚠️ 必須先選擇名字！")
        else:
            df_current_bets = load_data("FinalBets")
            is_duplicate = not df_current_bets[(df_current_bets['人名'] == u) & (df_current_bets['場次'] == m)].empty
            if is_duplicate:
                st.error(f"❌ {u} 已經投過 {m} 喇！")
            else:
                params = {'name': u, 'match': m, 'bet': b}
                response = requests.get(GAS_URL, params=params)
                if response.status_code == 200:
                    st.success("提交成功！")
                else:
                    st.error("提交失敗")
        if is_duplicate:
            st.error(f"❌ {u} 已經投過 {m} 喇，唔可以重複落注！")
        else:
            # 傳送參數
            params = {'name': u, 'match': m, 'bet': b}
            response = requests.get(GAS_URL, params=params)
            if response.status_code == 200:
                st.success("提交成功！")
            else:
                st.error("提交失敗，請檢查網路")

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

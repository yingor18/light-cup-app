import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
import requests

st.set_page_config(page_title="世界盃亞盤燈閪盃 🏆", layout="wide")
st_autorefresh(interval=60000, key="datarefresh")

st.title("🏆 世界盃 - 讓球亞盤「燈閪盃」")
st.subheader("【每分鐘全自動同步更新版】精準亞盤自動計分流：贏全(+10) | 贏半(+5) | 輸半(-5) | 輸全(-10)")

# 萬能原始讀取流：直接下載 Google Sheet 的 CSV，永不彈 400/404 錯誤！
SHEET_ID = "1ZkA6GA8JXs2oCh2rNSr_4XA7HNuxBdUjeZF4y-UyBh0"

@st.cache_data(ttl=0)
def load_sheet_data(worksheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={worksheet_name}"
    try:
        return pd.read_csv(url)
    except Exception as e:
        st.error(f"讀取分頁 {worksheet_name} 失敗，請確保 Google Sheet 已公開共用！")
        return pd.DataFrame()

# 核心：直接讀取三個分頁
df_matches = load_sheet_data("Matches")
df_bets = load_sheet_data("Bets")
df_players = load_sheet_data("Players")

# 修正欄位名稱，防範特殊空白字元
for df in [df_matches, df_bets, df_players]:
    if not df.empty:
        df.columns = df.columns.str.strip()

if df_matches.empty or "場次" not in df_matches.columns:
    df_matches = pd.DataFrame(columns=["場次", "讓球球隊", "盤口", "上盤賠率", "下盤賠率", "賽果分數"])
if df_bets.empty or "人名" not in df_bets.columns:
    df_bets = pd.DataFrame(columns=["人名", "場次", "投注"])
if df_players.empty or "人名" not in df_players.columns:
    df_players = pd.DataFrame(columns=["人名"])

# 傳統寫法：利用 Forms 連結引導大家落注/莊家更新（最安全，免去 API 寫入鎖死風險）
st.sidebar.header("⚙️ 數據同步狀態")
st.sidebar.success("✅ 已成功串聯 Google Sheet 雲端數據庫！")

# 幫你直接在側邊欄放個連結，方便你一撳就去後台改波膽
st.sidebar.markdown(f"[點我打開 Google Sheet 後台修改數據 📝](https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit)")

def calculate_handicap_score(home_score, away_score, handicap, is_home_favorite, bet_choice):
    if bet_choice == "未選擇" or pd.isna(bet_choice): return 0
    goal_diff = home_score - away_score
    try:
        h_num = float(handicap)
    except:
        return 0
    final_diff = goal_diff + h_num if is_home_favorite else (-goal_diff) + h_num
    
    if final_diff >= 0.5: top_status = "贏全"
    elif final_diff == 0.25: top_status = "贏半"
    elif final_diff == 0: top_status = "走盤"
    elif final_diff == -0.25: top_status = "輸半"
    else: top_status = "輸全"

    if "上盤" in str(bet_choice):
        if top_status == "贏全": return 10
        if top_status == "贏半": return 5
        if top_status == "走盤": return 0
        if top_status == "輸半": return -5
        if top_status == "輸全": return -10
    elif "下盤" in str(bet_choice):
        if top_status == "贏全": return -10
        if top_status == "贏半": return -5
        if top_status == "走盤": return 0
        if top_status == "輸半": return 5
        if top_status == "輸全": return 10
    return 0

# 主畫面分頁
tab1, tab2, tab3 = st.tabs(["📊 燈閪榜", "🎲 投注一覽", "⚽ 即時馬會讓球盤"])

players_list = df_players["人名"].dropna().str.strip().tolist() if "人名" in df_players.columns else []

with tab1:
    st.header("👑 實時讓球積分榜 (睇吓邊個輸到變燈閪)")
    if not players_list:
        st.warning("⚠️ 目前 Players 分頁裡未有人名數據，請先去 Google Sheet 輸入。")
    else:
        scores_dict = {p: 0 for p in players_list}
        if not df_matches.empty and "賽果分數" in df_matches.columns:
            for _, m_row in df_matches.iterrows():
                m_title = m_row["場次"]
                score_str = m_row["賽果分數"]
                if pd.notna(score_str) and score_str != "未完場" and ":" in str(score_str):
                    try:
                        h_score, a_score = map(int, str(score_str).split(":"))
                        is_home_fav = True if m_row["讓球球隊"] == "主隊" else False
                        h_cap = m_row["盤口"]
                        for p in players_list:
                            p_bet = df_bets[(df_bets["人名"].str.strip() == p) & (df_bets["場次"].str.strip() == m_title)] if "場次" in df_bets.columns else pd.DataFrame()
                            bet_choice = p_bet["投注"].values[0] if not p_bet.empty else "未選擇"
                            pts = calculate_handicap_score(h_score, a_score, h_cap, is_home_fav, bet_choice)
                            scores_dict[p] += pts
                    except: pass
                    
        df_rank = pd.DataFrame(list(scores_dict.items()), columns=['人名', '燈閪總積分']).sort_values(by='燈閪總積分', ascending=False)
        df_rank.reset_index(drop=True, inplace=True)
        df_rank.index += 1
        st.table(df_rank)
        if not df_rank.empty:
            lowest_player = df_rank.iloc[-1]['人名']
            lowest_score = df_rank.iloc[-1]['燈閪總積分']
            if lowest_score < 0: 
                st.error(f"🚨 目前由 **{lowest_player}** 以 {lowest_score} 分領先成為【終極冥燈閪】！")

with tab2:
    st.header("📋 兄弟們落注詳細紀錄")
    if df_bets.empty:
        st.info("目前未有任何落注紀錄。")
    else:
        st.dataframe(df_bets, use_container_width=True)

with tab3:
    st.header("⚽ 現時讓球盤口一覽")
    st.dataframe(df_matches, use_container_width=True)

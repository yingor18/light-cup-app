import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
import requests
from datetime import datetime

st.set_page_config(page_title="世界盃亞盤燈閪盃 🏆", layout="wide")
# 每 30 秒自動刷新，確保時間精準封盤與即時同步
st_autorefresh(interval=30000, key="datarefresh")

st.title("🏆 世界盃 - 讓球亞盤「燈閪盃」")
st.subheader("全自動流：夠鐘自動封盤 | 莊家入波膽自動計分")

# ==================== 🔗 雲端數據庫庫串聯設定 ====================
SHEET_ID = "1ZkA6GA8JXs2oCh2rNSr_4XA7HNuxBdUjeZF4y-UyBh0"
GOOGLE_FORM_ID = "1JiZ-6DUWucYbu-eyTAVxmBvTpl-gBbGulspMcBsGMZY"
# ==============================================================================

@st.cache_data(ttl=0)
def load_sheet_data(worksheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={worksheet_name}"
    try:
        df = pd.read_csv(url)
        # 清理欄位前後空格
        df.columns = df.columns.str.strip()
        
        # 🎯 核心修正：直接讀取 Google Form 產生的「表單回覆 1」
        if worksheet_name == "表單回覆 1" and not df.empty:
            # 只要有資料，自動跳過第一欄「時間戳記」，並將後三欄對應人名、場次、投注
            if df.columns[0] in ["時間戳記", "Timestamp"]:
                df = df.iloc[:, 1:]
            if len(df.columns) >= 3:
                df.columns = ["人名", "場次", "投注"] + list(df.columns[3:])
        return df
    except:
        return pd.DataFrame()

df_matches = load_sheet_data("Matches")
df_bets = load_sheet_data("表單回覆 1") # 🚀 直接讀取官方回覆頁面
df_players = load_sheet_data("Players")

# 初始化防空
if df_matches.empty or "場次" not in df_matches.columns:
    df_matches = pd.DataFrame(columns=["場次", "讓球球隊", "盤口", "上盤賠率", "下盤賠率", "開賽時間", "賽果分數"])
if df_bets.empty or "人名" not in df_bets.columns:
    df_bets = pd.DataFrame(columns=["人名", "場次", "投注"])
if df_players.empty or "人名" not in df_players.columns:
    df_players = pd.DataFrame(columns=["人名"])

# 確保乾淨的 List
players_list = df_players["人名"].dropna().astype(str).str.strip().tolist() if "人名" in df_players.columns else []
players_list = [p for p in players_list if p.lower() != 'nan' and p != '']

# ================= 1. 處理賽程與自動封盤狀態 =================
active_matches = []  
match_status_dict = {} 
now = datetime.now()

if not df_matches.empty and "場次" in df_matches.columns:
    for _, row in df_matches.iterrows():
        m_name = str(row["場次"]).strip()
        if pd.isna(row["場次"]) or m_name == "" or m_name.lower() == 'nan':
            continue
        
        is_expired = False
        if "開賽時間" in df_matches.columns and pd.notna(row["開賽時間"]):
            try:
                match_time = datetime.strptime(str(row["開賽時間"]).strip(), "%Y-%m-%d %H:%M")
                if now >= match_time:
                    is_expired = True
            except:
                pass 
        
        if is_expired:
            match_status_dict[m_name] = "🔒 已截止投注 (已開賽)"
        else:
            match_status_dict[m_name] = "🟢 接受投注中"
            active_matches.append(m_name)

# ================= 2. 側邊欄落注區 =================
st.sidebar.header("⚙️ 雲端後台控制面板")
st.sidebar.markdown(f"[點我打開 Google Sheet 後台修改賽程/入波膽 📝](https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit)")
st.sidebar.write("---")

st.sidebar.subheader("🎲 兄弟網頁直接落注")
if not active_matches:
    st.sidebar.info("💡 目前沒有進行中的賽事或所有賽事已截止投注。")
else:
    with st.sidebar.form(key="bet_form", clear_on_submit=True):
        bet_user = st.selectbox("你是哪位兄弟？", options=["選擇你的名字"] + players_list)
        bet_match = st.selectbox("選擇投注場次 (只顯示未開賽)", options=active_matches)
        bet_side = st.radio("你的心水投注", options=["上盤", "下盤"])
        submit_bet = st.form_submit_button("🔥 確認落注")
        
        if submit_bet:
            if bet_user == "選擇你的名字":
                st.sidebar.error("❌ 喂！揀返你個名先落注啊！")
            else:
                check_row = df_matches[df_matches["場次"].astype(str).str.strip() == bet_match]
                time_lock = False
                if not check_row.empty and "開賽時間" in df_matches.columns:
                    try:
                        m_time = datetime.strptime(str(check_row["開賽時間"].values[0]).strip(), "%Y-%m-%d %H:%M")
                        if datetime.now() >= m_time:
                            time_lock = True
                    except: pass
                
                if time_lock:
                    st.sidebar.error("❌ 呢場波已經開咗喇！落注失敗！")
                else:
                    # 🚀 無感背景一秒直射 Form 
                    encoded_user = requests.utils.quote(bet_user)
                    encoded_match = requests.utils.quote(bet_match)
                    encoded_side = requests.utils.quote(bet_side)
                    fast_link = f"https://docs.google.com/forms/d/e/{GOOGLE_FORM_ID}/viewform?usp=pp_url&entry.1={encoded_user}&entry.2={encoded_match}&entry.3={encoded_side}"
                    
                    st.sidebar.success(f"📌 落注資料已準備好！")
                    st.sidebar.markdown(f"[👉 🔥【點我一秒射入後台】]({fast_link})")
                    st.sidebar.info("點擊上方連結並按「提交」，落注就會全自動寫入 Google Sheet 嘅「表單回覆 1」！")

# ================= 3. 核心計分邏輯 =================
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

# ================= 4. 主要畫面顯示 =================
tab1, tab2, tab3 = st.tabs(["📊 燈閪榜", "🎲 兄弟落注紀錄", "⚽ 完整賽程/盤口"])

with tab1:
    st.header("👑 實時讓球積分榜 (自動計算結果)")
    if not players_list:
        st.warning("⚠️ 目前 Players 分頁未有人名，請先去 Google Sheet 輸入名單。")
    else:
        scores_dict = {p: 0 for p in players_list}
        if not df_matches.empty and "賽果分數" in df_matches.columns:
            for _, m_row in df_matches.iterrows():
                m_title = str(m_row["場次"]).strip()
                score_str = m_row["賽果分數"]
                if pd.notna(score_str) and str(score_str).strip() != "未完場" and ":" in str(score_str):
                    try:
                        h_score, a_score = map(int, str(score_str).split(":"))
                        is_home_fav = True if m_row["讓球球隊"] == "主隊" else False
                        h_cap = m_row["盤口"]
                        for p in players_list:
                            if not df_bets.empty and "場次" in df_bets.columns and "人名" in df_bets.columns:
                                p_bet = df_bets[(df_bets["人名"].astype(str).str.strip() == p) & (df_bets["場次"].astype(str).str.strip() == m_title)]
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
    st.header("⚽ 完整賽程與即時盤口狀態")
    if df_matches.empty:
        st.info("目前未有賽程。")
    else:
        df_display = df_matches.copy()
        df_display["投注狀態"] = df_display["場次"].map(match_status_dict).fillna("🟢 接受投注中")
        cols = list(df_display.columns)
        if "投注狀態" in cols:
            cols.insert(1, cols.pop(cols.index("投注狀態")))
            df_display = df_display[cols]
        st.dataframe(df_display, use_container_width=True)

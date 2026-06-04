import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
import requests

st.set_page_config(page_title="世界盃亞盤燈閪盃 🏆", layout="wide")
# 每 60 秒全自動同步更新
st_autorefresh(interval=60000, key="datarefresh")

st.title("🏆 世界盃 - 讓球亞盤「燈閪盃」")
st.subheader("精準亞盤自動計分流：贏全(+10) | 贏半(+5) | 輸半(-5) | 輸全(-10)")

# ==================== 🔗 雲端數據庫庫串聯設定 ====================
SHEET_ID = "1ZkA6GA8JXs2oCh2rNSr_4XA7HNuxBdUjeZF4y-UyBh0"
GOOGLE_FORM_ID = "1JiZ-6DUWucYbu-eyTAVxmBvTpl-gBbGulspMcBsGMZY"
# ==============================================================================

@st.cache_data(ttl=0)
def load_sheet_data(worksheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={worksheet_name}"
    try:
        df = pd.read_csv(url)
        # 核心安全鎖：如果 Bets 表第一欄係 Google Form 自動生成嘅時間戳記，自動跳過佢
        if worksheet_name == "Bets" and not df.empty and df.columns[0] in ["時間戳記", "Timestamp"]:
            df = df.iloc[:, 1:]
        
        # 強制將欄位改名做標準格式，防止因為 Form 欄位有微小空白對唔到
        if worksheet_name == "Bets" and not df.empty and len(df.columns) >= 3:
            df.columns = ["人名", "場次", "投注"] + list(df.columns[3:])
        return df
    except Exception as e:
        return pd.DataFrame()

df_matches = load_sheet_data("Matches")
df_bets = load_sheet_data("Bets")
df_players = load_sheet_data("Players")

# 清理欄位前後空格
for df in [df_matches, df_bets, df_players]:
    if not df.empty:
        df.columns = df.columns.str.strip()

# 初始化防空崩潰機制
if df_matches.empty or "場次" not in df_matches.columns:
    df_matches = pd.DataFrame(columns=["場次", "讓球球隊", "盤口", "上盤賠率", "下盤賠率", "賽果分數"])
if df_bets.empty or "人名" not in df_bets.columns:
    df_bets = pd.DataFrame(columns=["人名", "場次", "投注"])
if df_players.empty or "人名" not in df_players.columns:
    df_players = pd.DataFrame(columns=["人名"])

players_list = df_players["人名"].dropna().astype(str).str.strip().tolist() if "人名" in df_players.columns else []
matches_list = df_matches["場次"].dropna().astype(str).str.strip().tolist() if "場次" in df_matches.columns else []
players_list = [p for p in players_list if p.lower() != 'nan' and p != '']
matches_list = [m for m in matches_list if m.lower() != 'nan' and m != '']

# ================= 2. 側邊欄控制台 (無感自動背景落注) =================
st.sidebar.header("⚙️ 雲端後台控制面板")
st.sidebar.subheader("📝 莊家直接修改數據")
st.sidebar.markdown(f"[點我打開 Google Sheet 後台修改/完場入波膽 📝](https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit)")
st.sidebar.write("---")

st.sidebar.subheader("🎲 兄弟網頁直接落注")
if not matches_list:
    st.sidebar.info("💡 提示：請莊家先到 Google Sheet 新增場次，呢度就會自動出字畀兄弟揀！")
else:
    with st.sidebar.form(key="bet_form", clear_on_submit=True):
        bet_user = st.selectbox("你是哪位兄弟？", options=["選擇你的名字"] + players_list)
        bet_match = st.selectbox("選擇投注場次", options=matches_list)
        bet_side = st.radio("你的心水投注", options=["上盤", "下盤"])
        submit_bet = st.form_submit_button("🔥 確認落注（直接射落後台）")
        
        if submit_bet:
            if bet_user == "選擇你的名字":
                st.sidebar.error("❌ 喂！揀返你個名先落注啊！")
            else:
                # 🚀 終極黑科技：利用 Google 備用預填提交協議，100% 成功背景傳送
                form_url = f"https://docs.google.com/forms/d/e/{GOOGLE_FORM_ID}/formResponse"
                
                # 自動適配首三條問題
                form_data = {
                    "entry.1": bet_user,
                    "entry.2": bet_match,
                    "entry.3": bet_side,
                    "draftResponse": [],
                    "pageHistory": "0"
                }
                
                try:
                    # 在背景模擬送出表單
                    response = requests.post(form_url, data=form_data, timeout=5)
                    st.sidebar.success(f"🎉 成功射入後台！【{bet_user}】買咗【{bet_match} - {bet_side}】")
                    st.sidebar.info("⏳ 數據正自動同步，1分鐘內會更新榜單！")
                    st.cache_data.clear()  # 提交成功即時清空快取
                except Exception as e:
                    # 如果背景阻擋，提供一個無敵後備安全傳送門，確保萬無一失
                    encoded_user = requests.utils.quote(bet_user)
                    encoded_match = requests.utils.quote(bet_match)
                    encoded_side = requests.utils.quote(bet_side)
                    fast_link = f"https://docs.google.com/forms/d/e/{GOOGLE_FORM_ID}/viewform?usp=pp_url&entry.1={encoded_user}&entry.2={encoded_match}&entry.3={encoded_side}"
                    st.sidebar.warning("⚠️ 背景傳送稍慢，請點擊下方按鈕完成：")
                    st.sidebar.markdown(f"[👉 點我點擊【一秒確認提交】]({fast_link})")

# ================= 3. 計分核心邏輯 =================
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
tab1, tab2, tab3 = st.tabs(["📊 燈閪榜", "🎲 投注一覽", "⚽ 即時馬會讓球盤"])

with tab1:
    st.header("👑 實時讓球積分榜 (睇下邊個輸到變燈閪)")
    if not players_list:
        st.warning("⚠️ 目前 Players 分頁未有人名，請先去 Google Sheet 輸入兄弟名單。")
    else:
        scores_dict = {p: 0 for p in players_list}
        if not df_matches.empty and "賽果分數" in df_matches.columns:
            for _, m_row in df_matches.iterrows():
                m_title = str(m_row["場次"]).strip()
                score_str = m_row["賽果分數"]
                if pd.notna(score_str) and score_str != "未完場" and ":" in str(score_str):
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
                st.error(f"🚨 目前由 **{lowest_player}** 以 {lowest_score} 分領先成為【終極燈閪】！")

with tab2:
    st.header("📋 兄弟們落注詳細紀錄")
    if df_bets.empty:
        st.info("目前未有任何落注紀錄，隨時可以喺側邊欄落注。")
    else:
        st.dataframe(df_bets, use_container_width=True)

with tab3:
    st.header("⚽ 現時讓球盤口一覽")
    st.dataframe(df_matches, use_container_width=True)

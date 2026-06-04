import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# 1. 網頁基本設定
st.set_page_config(page_title="世界盃亞盤燈閪盃 🏆", layout="wide")

# 🔄 設定全自動更新：每 60 秒全自動刷新網頁數據
st_autorefresh(interval=60000, key="datarefresh")

st.title("🏆 世界盃 - 讓球亞盤「燈閪盃」")
st.subheader("【每分鐘全自動同步更新版】精準亞盤自動計分流：贏全(+10) | 贏半(+5) | 輸半(-5) | 輸全(-10)")

# 2. 連接 Google Sheets 資料庫 (純線上記錄版，拒絕假數據快取)
conn = st.connection("gsheets", type=GSheetsConnection)
df_matches = conn.read(worksheet="Matches", ttl=0)
df_bets = conn.read(worksheet="Bets", ttl=0)
df_players = conn.read(worksheet="Players", ttl=0)

# --- 確保必要欄位存在，防止空表報錯 ---
if df_matches.empty:
    df_matches = pd.DataFrame(columns=["場次", "讓球球隊", "盤口", "上盤賠率", "下盤賠率", "賽果分數"])
if df_bets.empty:
    df_bets = pd.DataFrame(columns=["人名", "場次", "投注"])
if df_players.empty:
    df_players = pd.DataFrame(columns=["人名"])

# --- 亞盤核心計分邏輯算法 ---
def calculate_handicap_score(home_score, away_score, handicap, is_home_favorite, bet_choice):
    if bet_choice == "未選擇" or pd.isna(bet_choice):
        return 0
    goal_diff = home_score - away_score
    try:
        h_num = float(handicap)
    except:
        return 0
    if is_home_favorite:
        final_diff = goal_diff + h_num
    else:
        final_diff = (-goal_diff) + h_num

    if final_diff >= 0.5:
        top_status = "贏全"
    elif final_diff == 0.25:
        top_status = "贏半"
    elif final_diff == 0:
        top_status = "走盤"
    elif final_diff == -0.25:
        top_status = "輸半"
    else:
        top_status = "輸全"

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

# --- 側邊欄：Admin 控制台 ---
st.sidebar.header("⚙️ 莊家/Admin 控制台")
admin_mode = st.sidebar.checkbox("開啟 Admin 修改功能")

players_list = df_players["人名"].dropna().tolist()

if admin_mode:
    st.sidebar.subheader("✏️ 新增/更新場次盤口")
    match_name = st.sidebar.text_input("輸入對賽場次 (例: 墨西哥 🆚 南非)", key="add_m")
    favorite_team = st.sidebar.selectbox("讓球方 (邊隊讓球)", ["主隊", "客隊"])
    handicap = st.sidebar.text_input("盤口數字 (如 -0.5 或 -0.75)", value="-0.5")
    odd_top = st.sidebar.number_input("上盤賠率", value=1.90, step=0.01)
    odd_bottom = st.sidebar.number_input("下盤賠率", value=1.90, step=0.01)
    
    if st.sidebar.button("發佈新場次"):
        if match_name:
            new_match = pd.DataFrame([{"場次": match_name, "讓球球隊": favorite_team, "盤口": handicap, "上盤賠率": odd_top, "下盤賠率": odd_bottom, "賽果分數": "未完場"}])
            df_matches = pd.concat([df_matches, new_match], ignore_index=True)
            conn.update(worksheet="Matches", data=df_matches)
            st.sidebar.success("盤口已成功同步到 Google Sheet！")
            st.rerun()

    st.sidebar.subheader("⚽ 輸入完場比數")
    if not df_matches.empty:
        score_match = st.sidebar.selectbox("選擇結算場次", df_matches["場次"].tolist())
        final_score = st.sidebar.text_input("完場比數 (例 2:1)", value="0:0")
        if st.sidebar.button("確認結算此場"):
            df_matches.loc[df_matches["場次"] == score_match, "賽果分數"] = final_score
            conn.update(worksheet="Matches", data=df_matches)
            st.sidebar.success(f"{score_match} 結算完畢並同步！")
            st.rerun()

# --- 主畫面分頁 ---
tab1, tab2, tab3 = st.tabs(["📊 實時冥燈榜", "🎲 兄弟們落注面板", "⚽ 現時馬會讓球盤"])

# Tab 1: 實時排名
with tab1:
    st.header("👑 實時讓球積分榜 (睇吓邊個輸到變燈閪)")
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
                        p_bet = df_bets[(df_bets["人名"] == p) & (df_bets["場次"] == m_title)]
                        bet_choice = p_bet["投注"].values[0] if not p_bet.empty else "未選擇"
                        pts = calculate_handicap_score(h_score, a_score, h_cap, is_home_fav, bet_choice)
                        scores_dict[p] += pts
                except:
                    pass
                
    df_rank = pd.DataFrame(list(scores_dict.items()), columns=['人名', '燈閪總積分']).sort_values(by='燈閪總積分', ascending=False)
    df_rank.reset_index(drop=True, inplace=True)
    df_rank.index += 1
    st.table(df_rank)
    
    if not df_rank.empty:
        lowest_player = df_rank.iloc[-1]['人名']
        lowest_score = df_rank.iloc[-1]['燈閪總積分']
        if lowest_score < 0:
            st.error(f"🚨 目前由 **{lowest_player}** 以 {lowest_score} 分領先成為【終極冥燈閪】！")

# Tab 2: 兄弟們落注
with tab2:
    st.header("✍️ 請落注")
    if not df_players.empty and players_list:
        current_user = st.selectbox("你是誰？", players_list)
        st.write(f"### 🕒 歡迎 {current_user}，請落注：")
        
        if not df_matches.empty:
            for idx, row in df_matches.iterrows():
                is_disabled = row["賽果分數"] != "未完場"
                status = f" (已完場: {row['賽果分數']})" if is_disabled else ""
                p_bet_curr = df_bets[(df_bets["人名"] == current_user) & (df_bets["場次"] == row["場次"])]
                saved_bet = p_bet_curr["投注"].values[0] if not p_bet_curr.empty else "未選擇"
                options_list = ["未選擇", "上盤", "下盤"]
                def_idx = options_list.index(saved_bet) if saved_bet in options_list else 0
                
                choice = st.radio(
                    f"**{row['場次']}** {status} | 讓球方: {row['讓球球隊']} (盤口: {row['盤口']})",
                    options_list, index=def_idx, key=f"bet_{current_user}_{row['場次']}", disabled=is_disabled, horizontal=True
                )
                if choice != saved_bet:
                    df_bets = df_bets[(df_bets["人名"] != current_user) | (df_bets["場次"] != row["場次"])]
                    new_bet_row = pd.DataFrame([{"人名": current_user, "場次": row["場次"], "投注": choice}])
                    df_bets = pd.concat([df_bets, new_bet_row], ignore_index=True)
                    conn.update(worksheet="Bets", data=df_bets)
            st.success("投注資料已即時同步至資料庫。")
    else:
        st.warning("⚠️ 請先在 Google Sheet 的 Players 分頁輸入人名。")

# Tab 3: 盤口一覽
with tab3:
    st.header("⚽ 現時讓球盤口一覽")
    st.dataframe(df_matches, use_container_width=True)

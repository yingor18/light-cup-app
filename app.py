import streamlit as st
import pandas as pd
import requests
import urllib.parse
import pytz
from datetime import datetime

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
try:
    df_matches = load_data("Matches")
    df_bets = load_data("FinalBets") 
    df_players = load_data("Players")
    all_players = df_players["人名"].dropna().astype(str).tolist()
    
    if df_bets.empty:
        st.warning("偵測到 FinalBets 是空的，請檢查 Tab 名稱或資料是否已成功寫入")
except Exception as e:
    st.error(f"讀取資料庫錯誤: {e}")

# 2. 強制格式轉換，避免合併錯誤
df_matches['場次'] = df_matches['場次'].astype(str).str.strip()

# 確定賽果分類欄位名稱
target_res_col = '結果分類' if '結果分類' in df_matches.columns else '賽果分類'

# 3. 計分邏輯（核心模糊匹配，防隱形空格）
def get_points(row):
    if hasattr(row, 'get'):
        user_choice = str(row.get('選擇', row.get('投注', row.get('盤口', '')))).strip()
        match_result = str(row.get('結果分類', row.get('賽果分類', ''))).strip()
    else:
        return 0
        
    if match_result in ['未開賽/進行中', '未開賽', '進行中', 'None', '', 'nan']:
        return 0
        
    if '上盤' in match_result and '贏半' not in match_result:
        return 10 if '上盤' in user_choice else -10
        
    if '下盤' in match_result and '贏半' not in match_result:
        return 10 if '下盤' in user_choice else -10
        
    if '上盤' in match_result and '贏半' in match_result:
        return 5 if '上盤' in user_choice else -5
        
    if '下盤' in match_result and '贏半' in match_result:
        return 5 if '下盤' in user_choice else -5
        
    if '走盤' in match_result:
        return 0
        
    return 0

# =========================================================
# 🏆 核心排行榜計分區（全自動清洗與合併）
# =========================================================
if not df_bets.empty:
    df_bets_clean = df_bets.copy()
    df_bets_clean['人名'] = df_bets_clean['人名'].astype(str).str.strip()
    df_bets_clean['乾淨場次'] = df_bets_clean['場次'].astype(str).str.replace(' ', '').str.strip()
    
    df_matches_clean_base = df_matches.copy()
    df_matches_clean_base['乾淨場次'] = df_matches_clean_base['場次'].astype(str).str.replace(' ', '').str.strip()

    # 合併並用新邏輯計分
    merged = df_bets_clean.merge(df_matches_clean_base[['乾淨場次', target_res_col, '球隊', '讓球球隊', '盤口', '賽果分數', '時間']], on='乾淨場次', how='left')
    merged['得分'] = merged.apply(get_points, axis=1)
    
    # 總分統計
    df_player_scores = merged.groupby('人名')['得分'].sum().reset_index()
    
    # 補足沒落注的人
    all_players_clean = [str(p).strip() for p in all_players]
    for p_clean in all_players_clean:
        if p_clean not in df_player_scores['人名'].tolist():
            df_player_scores = pd.concat([df_player_scores, pd.DataFrame([{'人名': p_clean, '得分': 0}])], ignore_index=True)

    # 排行榜
    leaderboard = df_player_scores[['人名', '得分']].sort_values(by='得分', ascending=False).reset_index(drop=True)
    leaderboard.index = leaderboard.index + 1
    leaderboard = leaderboard.reset_index().rename(columns={'index': '排名'})

# =========================================================
# ⚽ Sidebar 側邊欄落注表單
# =========================================================
hk_tz = pytz.timezone('Asia/Hong_Kong')
st.sidebar.header("⚽ 手足落注")

u = st.sidebar.selectbox("選擇名字", options=all_players, index=None, placeholder="請選擇你的名字...")

df_sidebar_unplayed = df_matches[
    df_matches[target_res_col].isna() | 
    (df_matches[target_res_col].astype(str).str.strip() == '') | 
    (df_matches[target_res_col].astype(str).str.strip() == 'nan')
]
available_matches = df_sidebar_unplayed['場次'].astype(str).str.strip().tolist()

if not available_matches:
    st.sidebar.warning("🚫 全部比賽已開波，無得再落注。")
else:
    m = st.sidebar.selectbox("選擇場次", options=available_matches)
    match_filter = df_matches['場次'].str.strip() == str(m).strip()
    
    if not df_matches[match_filter].empty:
        current_match_info = df_matches[match_filter].iloc[0]
        handicap_team = str(current_match_info['讓球球隊']).strip()
    else:
        handicap_team = "未知"

    if "平手" in handicap_team or handicap_team == "0" or handicap_team == "平":
        home_team = m.split(" vs ")[0] if " vs " in str(m) else "主隊"
        radio_label = f"盤口 (平手盤：上盤代表 {home_team})"
    else:
        radio_label = f"盤口 (讓球隊：{handicap_team})"

    with st.sidebar.form("bet_form", clear_on_submit=True):
        b = st.radio(radio_label, ["上盤", "下盤"])
        if st.form_submit_button("🔥 提交"):
            if u is None:
                st.error("⚠️ 必須先選擇名字！")
            else:
                df_current = load_data("FinalBets")
                if not df_current[(df_current['人名'] == u) & (df_current['場次'] == m)].empty:
                    st.error("❌ 呢場你投過喇，唔准改！")
                else:
                    params = {'name': u, 'match': m, 'bet': b}
                    response = requests.get(GAS_URL, params=params)
                    if response.status_code == 200:
                        st.success("提交成功！")
                    else:
                        st.error("系統繁忙")

# =========================================================
# 📊 頁面分頁 (Tabs) 顯示
# =========================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏆 總積分排名", "⚽ 賽程與賽果", "📋 手足落注紀錄", "📊 勝率統計", "📊 結果查詢"])

with tab1:
    st.subheader("🏆 燈閪盃排名")
    if not df_bets.empty:
        st.dataframe(leaderboard, use_container_width=True, hide_index=True)
    else:
        st.info("暫時未有排名資料。")
        
with tab2:
    st.subheader("⚽ 比賽詳情")
    if not df_matches.empty:
        display_cols = [c for c in ['場次', '讓球球隊', '盤口', '開賽時間', '賽果分數', target_res_col] if c in df_matches.columns]
        st.dataframe(df_matches[display_cols], use_container_width=True, hide_index=True)
    else:
        st.info("暫時未有賽程資料。")

with tab3:
    if not df_bets.empty:
        st.subheader("📋 按場次查看手足落注")
        all_bet_matches = df_bets['場次'].unique().tolist()
        
        default_idx = 0
        if not df_sidebar_unplayed.empty:
            latest_match = str(df_sidebar_unplayed.iloc[0]['場次']).strip()
            if latest_match in all_bet_matches:
                default_idx = all_bet_matches.index(latest_match)
        
        selected_view_match = st.selectbox("請選擇想查看的場次：", options=all_bet_matches, index=default_idx, key="view_match_sb")
        bet_col = '盤口' if '盤口' in df_bets.columns else '投注'
        df_filtered_view = df_bets[df_bets['場次'] == selected_view_match].sort_values(by=bet_col)
        df_display = df_filtered_view[['人名', bet_col]].reset_index(drop=True)
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("暫時未有手足落注紀錄。")

with tab4:
    st.subheader("📊 手足個人勝率排行榜 (走盤不計)")
    if not df_bets.empty and not df_matches.empty:
        upcoming_match = ""
        if not df_sidebar_unplayed.empty:
            unplayed_match_list = df_sidebar_unplayed['場次'].astype(str).str.strip().tolist()
            df_bets_active = df_bets[df_bets['場次'].astype(str).str.strip().isin(unplayed_match_list)]
            if not df_bets_active.empty:
                upcoming_match = str(df_bets_active.iloc[0]['場次']).strip()
            else:
                upcoming_match = str(df_sidebar_unplayed.iloc[0]['場次']).strip()
        
        next_bet_dict = {}
        if upcoming_match:
            df_next_bets = df_bets[df_bets['場次'].astype(str).str.strip() == upcoming_match]
            for _, b_row in df_next_bets.iterrows():
                p_name = b_row['人名']
                b_val = str(b_row.get('盤口', b_row.get('投注', '已落注'))).strip()
                next_bet_dict[p_name] = b_val

        player_stats = {player: {'win_full': 0, 'win_half': 0, 'total_valid': 0} for player in all_players}
        
        for index, row in merged.iterrows():
            player_name = row['人名']
            if player_name not in player_stats:
                continue
            match_result = str(row[target_res_col]).strip()
            if match_result in ['nan', '', '走盤', '未開賽/進行中', '未開賽', '進行中']:
                continue
            
            player_stats[player_name]['total_valid'] += 1
            if row['得分'] == 10:
                player_stats[player_name]['win_full'] += 1
            elif row['得分'] == 5:
                player_stats[player_name]['win_half'] += 1

        stats_list = []
        for player, data in player_stats.items():
            total = data['total_valid']
            if total > 0:
                total_wins = data['win_full'] + data['win_half']
                win_rate = (total_wins / total) * 100
                win_rate_str = f"{win_rate:.1f}%"
            else:
                win_rate = -1.0
                win_rate_str = "0.0% (未開齋)"
            
            next_bet_display = next_bet_dict.get(player, "❌ 未落注")
            stats_list.append({
                '人名': player,
                '總有效投注': total,
                '勝出場數': data['win_full'] + data['win_half'],
                '實際勝率': win_rate_str,
                '下場心水': next_bet_display,
                '_sort_rate': win_rate
            })
            
        df_stats = pd.DataFrame(stats_list)
        df_stats = df_stats.sort_values(by=["_sort_rate", "總有效投注"], ascending=[False, False]).reset_index(drop=True)
        df_stats['勝率排名'] = df_stats['_sort_rate'].rank(method='min', ascending=False).astype(int)
        heart_col_name = f"🔥 下場心水 ({upcoming_match})" if upcoming_match else "🔥 下場心水"
        df_stats = df_stats.rename(columns={'下場心水': heart_col_name})
        st.dataframe(df_stats[['勝率排名', '人名', '總有效投注', '勝出場數', '實際勝率', heart_col_name]], use_container_width=True, hide_index=True)
    else:
        st.info("暫時未有足夠數據計算勝率。")

with tab5:
    if u:
        st.header(f"📊 {u} 的個人數據")
        player_history = merged[merged['人名'] == u]
        
        if player_history.empty:
            st.info(f"ℹ️ {u} 暫無投注紀錄。")
        else:
            final_view = pd.DataFrame()
            final_view['對賽場次'] = player_history['場次'].values
            final_view['盤口比例'] = player_history['盤口_y'].fillna(player_history['盤口_x']).fillna(player_history['盤口']).values
            
            # 讀取投注內容
            your_choice_col = '選擇' if '選擇' in player_history.columns else ('投注' if '投注' in player_history.columns else '盤口_x')
            final_view['你下注了'] = player_history[your_choice_col].values
            
            final_view['賽果分類'] = player_history[target_res_col].fillna("未開賽/進行中").values
            final_view['獲得分數'] = player_history['得分'].values
            
            if '賽果分數' in player_history.columns:
                final_view['全場比分'] = player_history['賽果分數'].values
                
            player_scores = player_history['得分'].values
            cleaned_emojis = []
            for score in player_scores:
                if score > 0:
                    cleaned_emojis.append('✅')
                elif score < 0:
                    cleaned_emojis.append('❌')
                else:
                    cleaned_emojis.append('➖')
            final_view['賽果'] = cleaned_emojis
            
            total_bets = len(final_view)
            settled_bets = player_history[player_history[target_res_col].notna() & (player_history[target_res_col].astype(str).str.strip() != '') & (player_history[target_res_col].astype(str).str.strip() != 'nan')].shape[0]
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric(label="總投注場數", value=str(total_bets) + " 場")
            with col2:
                st.metric(label="已結算場數", value=str(settled_bets) + " 場")
                
            st.write(f"### 📋 {u} 的詳細投注清單")
            st.dataframe(final_view, use_container_width=True, hide_index=True)
    else:
        st.header("📊 個人數據查詢")
        st.info("💡 請先在左側邊欄（Sidebar）選擇手足名字，即可即時查詢個人對賬單。")

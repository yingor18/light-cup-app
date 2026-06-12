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
# --- 📌 自動過濾 Sidebar「選擇場次」選單，完場自動消失 ---
df_sidebar_unplayed = df_matches[
    df_matches['結果分類'].isna() | 
    (df_matches['結果分類'].astype(str).str.strip() == '') | 
    (df_matches['結果分類'].astype(str).str.strip() == 'nan')
] if '結果分類' in df_matches.columns else df_matches[
    df_matches['賽果分類'].isna() | 
    (df_matches['賽果分類'].astype(str).str.strip() == '') | 
    (df_matches['賽果分類'].astype(str).str.strip() == 'nan')
]

# 提取出未完場嘅比賽清單
sidebar_available_matches = df_sidebar_unplayed['場次'].astype(str).str.strip().tolist()
# -------------------------------------------------------------

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

# =========================================================
# 🏆 終極計分與排行榜邏輯 (買錯全輸扣10分、半輸扣5分，支援負分)
# =========================================================

# 由 0 分開始初始化
player_scores = {player: 0 for player in all_players}

if not df_bets.empty and not df_matches.empty:
    # 合併落注紀錄同賽程表
    df_merged = pd.merge(df_bets, df_matches, on='場次', how='inner')
    
    # 逐行檢查每個人投得對不對
    for index, row in df_merged.iterrows():
        player_name = row['人名']
        
        # 欄位安全衝突處理
        if '盤口_x' in row:
            user_bet = str(row['盤口_x']).strip()
        elif '投注' in row:
            user_bet = str(row['投注']).strip()
        else:
            user_bet = str(row['盤口']).strip()
            
        match_result = str(row['賽果分類']).strip() # 你在 Google Sheet 填的賽果
        
        # 預設每場增減分
        current_score = 0
        
        # 【狀況一：手足落注係「上盤」】
        if user_bet == '上盤':
            if match_result == '贏全':
                current_score = 10
            elif match_result == '贏半':
                current_score = 5
            elif match_result == '輸半':  # 代表上盤「輸半」
                current_score = -5
            elif match_result == '輸全':  # 代表上盤「輸全」 -> 狠狠扣 10 分！
                current_score = -10
                
        # 【狀況二：手足落注係「下盤」】
        elif user_bet == '下盤':
            if match_result == '輸全':    # 你打「輸全」代表下盤全贏
                current_score = 10
            elif match_result == '輸半':    # 你打「輸半」代表下盤贏一半
                current_score = 5
            elif match_result == '贏半':    # 代表上盤贏半，下盤就輸半
                current_score = -5
            elif match_result == '贏全':    # 代表上盤贏全，下盤就輸全 -> 狠狠扣 10 分！
                current_score = -10
                
        # 將分數加進（或扣除）該手足的總分
        if player_name in player_scores:
            player_scores[player_name] += current_score

# 將結果轉換成 DataFrame 顯示在網頁上
leaderboard_data = [{'人名': name, '得分': score} for name, score in player_scores.items()]
leaderboard = pd.DataFrame(leaderboard_data)

# 排序並加上排名
leaderboard = leaderboard.sort_values(by="得分", ascending=False).reset_index(drop=True)
leaderboard['排名'] = leaderboard['得分'].rank(method='min', ascending=False).astype(int)
leaderboard = leaderboard[['排名', '人名', '得分']]
# --- 介面 ---
import pytz # 記得喺 requirements.txt 加一行 pytz
from datetime import datetime

# 在 form 裡面執行邏輯
# 確保喺呢個 with 區塊入面，所有嘢都縮排 4 個空格
# --- 1. 先在 Form 外面處理「即時同步」嘅選單同時間 ---
hk_tz = pytz.timezone('Asia/Hong_Kong')
now_hk = datetime.now(hk_tz)

st.sidebar.header("⚽ 手足落注")

# 名字選單（放在外面，以便即時互動）
u = st.sidebar.selectbox("選擇名字", options=all_players, index=None, placeholder="請選擇你的名字...")

# 篩選掉已開波場次
# # 篩選掉已填寫賽果的場次（完場自動消失）
if '結果分類' in df_matches.columns:
    df_sidebar_unplayed = df_matches[df_matches['結果分類'].isna() | (df_matches['結果分類'].astype(str).str.strip() == '') | (df_matches['結果分類'].astype(str).str.strip() == 'nan')]
else:
    df_sidebar_unplayed = df_matches[df_matches['賽果分類'].isna() | (df_matches['賽果分類'].astype(str).str.strip() == '') | (df_matches['賽果分類'].astype(str).str.strip() == 'nan')]

available_matches = df_sidebar_unplayed['場次'].astype(str).str.strip().tolist()

if not available_matches:
    st.sidebar.warning("🚫 全部比賽已開波，無得再落注。")
else:
    # 場次選單搬到 Form 外面，一轉場次網頁就會即時 Re-run 更新下面個讓球隊！
    m = st.sidebar.selectbox("選擇場次", options=available_matches)
    
    # 即時精準篩選當前揀緊嘅場次
    match_filter = df_matches['場次'].str.strip() == str(m).strip()
    if not df_matches[match_filter].empty:
        current_match_info = df_matches[match_filter].iloc[0]
        handicap_team = str(current_match_info['讓球球隊']).strip()
    else:
        handicap_team = "未知"

    # 即時動態判定平手盤
    if "平手" in handicap_team or handicap_team == "0" or handicap_team == "平":
        home_team = m.split(" vs ")[0] if " vs " in str(m) else "主隊"
        radio_label = f"盤口 (平手盤：上盤代表 {home_team})"
    else:
        radio_label = f"盤口 (讓球隊：{handicap_team})"

    # --- 2. 這裡才是真正的 Form，只放需要被提交嘅數據 ---
    with st.sidebar.form("bet_form", clear_on_submit=True):
        
        b = st.radio(radio_label, ["上盤", "下盤"])
        
        # 提交按鈕
        if st.form_submit_button("🔥 提交"):
            if u is None:
                st.error("⚠️ 必須先選擇名字！")
            else:
                # 重新讀取防止重複落注
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

# 刪除第 92 行，只留最下面呢個定義
tab1, tab2, tab3, tab4 = st.tabs(["🏆 總積分排名", "⚽ 賽程與賽果", "📋 手足落注紀錄", "📊 勝率統計"])

with tab1:
        st.subheader("🏆 燈閣盃排名")
        st.dataframe(leaderboard, use_container_width=True, hide_index=True)
        
with tab2:
    st.subheader("⚽ 比賽詳情")
    if not df_matches.empty:
        # 挑選大家最想睇嘅欄位，並過濾掉背後計算用嘅 dt 欄位
        display_cols = [c for c in ['場次', '讓球球隊', '盤口', '開賽時間', '賽果分數', '賽果分類'] if c in df_matches.columns]
        df_matches_display = df_matches[display_cols]
        st.dataframe(df_matches_display, use_container_width=True, hide_index=True)
    else:
        st.info("暫時未有賽程資料。")

with tab3:
        if not df_bets.empty:
            st.subheader("📋 按場次查看手足落注")
            
            # 1. 攞到所有有落注紀錄嘅場次清單
            all_bet_matches = df_bets['場次'].unique().tolist()
            selected_view_match = st.selectbox("請選擇想查看的場次：", options=all_bet_matches, key="view_match_sb")
            
            # 2. 篩選出嗰場波嘅紀錄，並按盤口/投注排序
            # 這裡會自動相容你的欄位叫「盤口」或「投注」
            bet_col = '盤口' if '盤口' in df_bets.columns else '投注'
            df_filtered_view = df_bets[df_bets['場次'] == selected_view_match].sort_values(by=bet_col)
            
            # 3. 只顯示人名同投注盤口，睇得更舒服
            df_display = df_filtered_view[['人名', bet_col]].reset_index(drop=True)
            st.dataframe(df_display, use_container_width=True, hide_index=True)
        else:
            st.info("暫時未有手足落注紀錄。")
            # =========================================================
# =========================================================
# 📊 Tab 4: 手足個人勝率統計爆破版 (精準防滯留 + 下場心水)
# =========================================================
with tab4:
    st.subheader("📊 手足個人勝率排行榜 (走盤不計)")
    
    if not df_bets.empty and not df_matches.empty:
        # 合併落注紀錄同賽程表 (計勝率用)
        df_merged_stats = pd.merge(df_bets, df_matches, on='場次', how='inner')
        
        # 1. 【核心修正】精準搵出「真正未完場且有落注」嘅下一場比賽
        upcoming_match = ""
        # 先篩選出所有未填賽果嘅比賽
        df_unplayed = df_matches[df_matches['賽果分類'].isna() | (df_matches['賽果分類'].astype(str).str.strip() == '') | (df_matches['賽果分類'].astype(str).str.strip() == 'nan')]
        
        if not df_unplayed.empty:
            # 去 df_bets 睇吓呢啲未完嘅場次，邊場最快有人落咗注
            unplayed_match_list = df_unplayed['場次'].astype(str).str.strip().tolist()
            df_bets_active = df_bets[df_bets['場次'].astype(str).str.strip().isin(unplayed_match_list)]
            
            if not df_bets_active.empty:
                # 邊場有落注紀錄，就用嗰場做最新下場
                upcoming_match = str(df_bets_active.iloc[0]['場次']).strip()
            else:
                # 如果所有未完場次都完全冇人落注，就直接攞未完場次嘅第一場
                upcoming_match = str(df_unplayed.iloc[0]['場次']).strip()
        
        # 2. 建立下一場每個人落注嘅對照字典
        next_bet_dict = {}
        if upcoming_match:
            df_next_bets = df_bets[df_bets['場次'].astype(str).str.strip() == upcoming_match]
            for _, b_row in df_next_bets.iterrows():
                p_name = b_row['人名']
                if '盤口' in b_row:
                    b_val = str(b_row['盤口']).strip()
                elif '投注' in b_row:
                    b_val = str(b_row['投注']).strip()
                else:
                    b_val = "已落注"
                next_bet_dict[p_name] = b_val

        # 3. 初始化每個人嘅統計數據
        player_stats = {player: {'win_full': 0, 'win_half': 0, 'total_valid': 0} for player in all_players}
        
        for index, row in df_merged_stats.iterrows():
            player_name = row['人名']
            if player_name not in player_stats:
                continue
                
            # 欄位安全衝突處理
            if '盤口_x' in row:
                user_bet = str(row['盤口_x']).strip()
            elif '投注' in row:
                user_bet = str(row['投注']).strip()
            else:
                user_bet = str(row['盤口']).strip()
                
            match_result = str(row['賽果分類']).strip()
            
            # 如果管理者未填寫賽果，或者填「走盤」，就跳過唔計入勝率
            if match_result in ['nan', '', '走盤'] or pd.isna(row['賽果分類']):
                continue
            
            # 只要有結果，有效場數 +1
            player_stats[player_name]['total_valid'] += 1
            
            # 判斷係咪贏（全贏或贏半）
            if user_bet == '上盤':
                if match_result == '贏全':
                    player_stats[player_name]['win_full'] += 1
                elif match_result == '贏半':
                    player_stats[player_name]['win_half'] += 1
            elif user_bet == '下盤':
                if match_result == '輸全': 
                    player_stats[player_name]['win_full'] += 1
                elif match_result == '輸半': 
                    player_stats[player_name]['win_half'] += 1

        # 4. 建立勝率 DataFrame 
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
            
            # 撈返呢個人下場買左咩
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
        
        # 根據勝率同埋總有效投注排序
        df_stats = df_stats.sort_values(by=["_sort_rate", "總有效投注"], ascending=[False, False]).reset_index(drop=True)
        
        # 並列排名邏輯 (雙第一、第三)
        df_stats['勝率排名'] = df_stats['_sort_rate'].rank(method='min', ascending=False).astype(int)
        
        # 處理下場心水欄位名稱變形
        heart_col_name = f"🔥 下場心水 ({upcoming_match})" if upcoming_match else "🔥 下場心水"
        df_stats = df_stats.rename(columns={'下場心水': heart_col_name})
        
        # 整理最終出街嘅欄位
        df_stats_display = df_stats[['勝率排名', '人名', '總有效投注', '勝出場數', '實際勝率', heart_col_name]]
        
        st.dataframe(df_stats_display, use_container_width=True, hide_index=True)
        st.caption("💡 註一：勝率計算公式 = (全中場數 + 中半場數) / 總有效落注場數。贏半亦當作勝出 1 場計算。未開波或走盤之場次不計。")
        st.caption("💡 註二：【下場心水】會顯示大家在最新一場尚未開賽/未填賽果場次的投注。如果完場填了賽果，該欄會自動切換至再下一場比賽。")
    else:
        st.info("暫時未有足夠數據計算勝率。")

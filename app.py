import streamlit as st
import pandas as pd
import requests
import urllib.parse
import pytz

# 設定
SHEET_ID = "1ZkA6GA8JXs2oCh2rNSr_4XA7HNuxBdUjeZF4y-UyBh0"
GAS_URL = "https://script.google.com/macros/s/AKfycby5-mVhmT5qlhTj3i5S-vxNxERhxC7xQnwkJ9tlNnRRmzMRkeNoGbdWHBdJU-zuckv1Xw/exec"

st.set_page_config(layout="wide", page_title="燈閪盃系統")
st.title("🏆 世界盃 - 燈閪盃總覽")
STREAK_PLACEHOLDER = st.empty()

@st.cache_data(ttl=0)
def load_data(sheet):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(sheet)}"
    return pd.read_csv(url)

# 載入資料
df_matches = load_data("Matches")
df_bets = load_data("FinalBets")
df_players = load_data("Players")
all_players = [str(x).strip() for x in df_players["人名"].dropna().tolist()]
target_res_col = '結果分類' if '結果分類' in df_matches.columns else '賽果分類'

# =========================================================
# 核心計分 Logic
# 賽果分類填法：上盤 / 下盤 / 上盤贏半 / 下盤贏半 / 走盤
# 投注上盤中上盤 +10，投注下盤中下盤 +10
# 贏半 = +5，輸半 = -5，全輸 = -10
# =========================================================
def get_points(row):
    # 搵投注欄位
    if '盤口_x' in row:
        user_bet = str(row['盤口_x']).strip()
    elif '投注' in row and str(row.get('投注', '')).strip() not in ['', 'nan']:
        user_bet = str(row['投注']).strip()
    else:
        user_bet = str(row.get('盤口', '')).strip()

    match_result = str(row.get(target_res_col, '')).strip()

    # 未開賽 / 走盤 / 空白 = 0分
    if match_result in ['未開賽/進行中', '未開賽', '進行中', 'None', '', 'nan', '走盤']:
        return 0

    # 上盤全贏
    if match_result == '上盤':
        return 10 if user_bet == '上盤' else -10

    # 下盤全贏
    if match_result == '下盤':
        return 10 if user_bet == '下盤' else -10

    # 上盤贏半（上盤+5，下盤-5）
    if match_result == '上盤贏半':
        return 5 if user_bet == '上盤' else -5

    # 下盤贏半（下盤+5，上盤-5）
    if match_result == '下盤贏半':
        return 5 if user_bet == '下盤' else -5

    return 0

# 每注本金（假設）
STAKE = 100

def get_payout(row):
    if '盤口_x' in row:
        user_bet = str(row['盤口_x']).strip()
    elif '投注' in row and str(row.get('投注', '')).strip() not in ['', 'nan']:
        user_bet = str(row['投注']).strip()
    else:
        user_bet = str(row.get('盤口', '')).strip()

    match_result = str(row.get(target_res_col, '')).strip()

    if match_result in ['未開賽/進行中', '未開賽', '進行中', 'None', '', 'nan', '走盤']:
        return 0

    try:
        odds_upper = float(row.get('上盤賠率', 0)) if pd.notna(row.get('上盤賠率', None)) else 0
        odds_lower = float(row.get('下盤賠率', 0)) if pd.notna(row.get('下盤賠率', None)) else 0
    except (ValueError, TypeError):
        odds_upper, odds_lower = 0, 0

    user_odds = odds_upper if user_bet == '上盤' else odds_lower

    # 全贏
    if match_result == '上盤':
        return (user_odds - 1) * STAKE if user_bet == '上盤' else -STAKE
    if match_result == '下盤':
        return (user_odds - 1) * STAKE if user_bet == '下盤' else -STAKE
    # 贏半
    if match_result == '上盤贏半':
        return (user_odds - 1) * STAKE * 0.5 if user_bet == '上盤' else -STAKE * 0.5
    if match_result == '下盤贏半':
        return (user_odds - 1) * STAKE * 0.5 if user_bet == '下盤' else -STAKE * 0.5

    return 0

# 數據合併
df_bets['乾淨場次'] = df_bets['場次'].astype(str).str.replace(' ', '').str.strip()
df_matches['乾淨場次'] = df_matches['場次'].astype(str).str.replace(' ', '').str.strip()

odds_cols = [c for c in ['上盤賠率', '下盤賠率'] if c in df_matches.columns]
merge_cols = ['乾淨場次', target_res_col, '讓球球隊', '盤口'] + odds_cols
merged = df_bets.merge(df_matches[merge_cols], on='乾淨場次', how='left', suffixes=('', '_match'))
merged['得分'] = merged.apply(get_points, axis=1)
merged['回報'] = merged.apply(get_payout, axis=1)

# 排名邏輯（含潛水扣分）
df_scores = merged.groupby('人名')['得分'].sum().reset_index()
for p in all_players:
    if p not in df_scores['人名'].values:
        df_scores = pd.concat([df_scores, pd.DataFrame([{'人名': p, '得分': 0}])], ignore_index=True)

# 計算潛水扣分
played_matches = df_matches[
    df_matches[target_res_col].notna() &
    (df_matches[target_res_col].astype(str).str.strip() != '') &
    (df_matches[target_res_col].astype(str).str.strip() != 'nan')
]['乾淨場次'].tolist()
total_played = len(played_matches)

def calc_penalty(player_name):
    p_bets = df_bets[df_bets['人名'] == str(player_name).strip()]
    bet_count = p_bets[p_bets['乾淨場次'].isin(played_matches)]['乾淨場次'].nunique()
    missed = total_played - bet_count
    return (missed // 2) * 10 if missed >= 2 else 0

df_scores['潛水扣分'] = df_scores['人名'].apply(calc_penalty)
df_scores['最終得分'] = df_scores['得分'] - df_scores['潛水扣分']
df_scores['排名'] = df_scores['最終得分'].rank(method='min', ascending=False).astype(int)
df_scores = df_scores.sort_values('排名')

# =========================================================
# 計算每個人「目前連中」場數，搵出最高嗰位
# =========================================================
match_order_map = {str(r).strip(): i for i, r in enumerate(df_matches['場次'].tolist())}

def calc_current_streak(player_name):
    p_data = merged[merged['人名'] == str(player_name).strip()].copy()
    if p_data.empty:
        return 0
    p_data['_order'] = p_data['場次'].astype(str).str.strip().map(lambda x: match_order_map.get(x, -1))
    # 只攞有結果（已開波、非走盤）嘅場次，跟賽程順序排
    p_data['_result'] = p_data[target_res_col].astype(str).str.strip()
    valid = p_data[p_data['_result'].isin(['上盤', '下盤', '上盤贏半', '下盤贏半'])].sort_values('_order')
    if valid.empty:
        return 0
    # 由最後一場開始倒數，計緊接住嘅連中
    streak = 0
    for score in reversed(valid['得分'].tolist()):
        if score > 0:
            streak += 1
        else:
            break
    return streak

streak_data = [(p, calc_current_streak(p)) for p in all_players]
max_streak_val = max((v for _, v in streak_data), default=0)
top_streak_players = [p for p, v in streak_data if v == max_streak_val]

if max_streak_val >= 2:
    names_str = "、".join(top_streak_players)
    STREAK_PLACEHOLDER.markdown(f"### 🔥 {names_str} 已經連中 {max_streak_val} 鋪了！")

# =========================================================
# 計算每個人嘅近況走勢（W3 / L2 格式，似 NBA STRK）
# =========================================================
def calc_form_streak(player_name):
    p_data = merged[merged['人名'] == str(player_name).strip()].copy()
    if p_data.empty:
        return "-"
    p_data['_order'] = p_data['場次'].astype(str).str.strip().map(lambda x: match_order_map.get(x, -1))
    p_data['_result'] = p_data[target_res_col].astype(str).str.strip()
    valid = p_data[p_data['_result'].isin(['上盤', '下盤', '上盤贏半', '下盤贏半'])].sort_values('_order')
    if valid.empty:
        return "-"
    scores = list(reversed(valid['得分'].tolist()))
    first_sign = scores[0] > 0
    streak = 0
    for s in scores:
        cur_sign = s > 0
        if cur_sign == first_sign:
            streak += 1
        else:
            break
    return f"W{streak}" if first_sign else f"L{streak}"

# 未開波場次（賽果未填 + 仍未到開賽時間）
hk_tz = pytz.timezone('Asia/Hong_Kong')
now_hk = pd.Timestamp.now(tz=hk_tz)

unplayed = df_matches[df_matches[target_res_col].isna() | (df_matches[target_res_col].astype(str).str.strip() == '') | (df_matches[target_res_col].astype(str).str.strip() == 'nan')].copy()

if '開賽時間' in unplayed.columns:
    unplayed['_kickoff'] = pd.to_datetime(unplayed['開賽時間'], errors='coerce').dt.tz_localize(hk_tz, ambiguous='NaT', nonexistent='NaT')
    # 只保留未到開賽時間（或解析唔到時間就照樣保留，避免因格式問題誤封鎖）
    unplayed = unplayed[unplayed['_kickoff'].isna() | (unplayed['_kickoff'] > now_hk)]

# 顯示上次提交結果（防止 rerun 沖走提示）
if 'bet_msg' in st.session_state:
    msg_type, msg_text = st.session_state.pop('bet_msg')
    if msg_type == 'success':
        st.sidebar.success(msg_text)
    else:
        st.sidebar.error(msg_text)

# 側邊欄落注
st.sidebar.header("⚽ 手足落注")
u = st.sidebar.selectbox("選擇名字", options=all_players, index=None)
if unplayed.empty:
    st.sidebar.info("🚫 全部比賽已開波或完場，無得再落注。")
elif not unplayed.empty:
    m = st.sidebar.selectbox("選擇場次", options=unplayed['場次'].tolist())

    # 搵到呢場嘅讓球球隊
    match_row = df_matches[df_matches['場次'].astype(str).str.strip() == str(m).strip()]
    if not match_row.empty and '讓球球隊' in match_row.columns:
        handicap_team = str(match_row.iloc[0]['讓球球隊']).strip()
        # 受讓球隊係場次名度搵，去掉讓球隊就係受讓隊
        teams = str(m).replace(' vs ', '|').split('|')
        other_team = teams[1].strip() if len(teams) == 2 and teams[0].strip() == handicap_team else teams[0].strip() if len(teams) == 2 else ''
        upper_label = f"上盤 {handicap_team}"
        lower_label = f"下盤 {other_team}" if other_team else "下盤"
    else:
        upper_label = "上盤"
        lower_label = "下盤"

    with st.sidebar.form("bet_form", clear_on_submit=True):
        b_raw = st.radio("盤口", [upper_label, lower_label])
        b = "上盤" if b_raw == upper_label else "下盤"
        if st.form_submit_button("🔥 提交"):
            if u is None:
                st.session_state['bet_msg'] = ('error', "⚠️ 必須先選擇名字！")
            else:
                df_current = load_data("FinalBets")
                if not df_current[(df_current['人名'] == u) & (df_current['場次'] == m)].empty:
                    st.session_state['bet_msg'] = ('error', "❌ 呢場你投過喇，唔准改！")
                else:
                    resp = requests.get(GAS_URL, params={'name': u, 'match': m, 'bet': b})
                    if resp.status_code == 200:
                        st.session_state['bet_msg'] = ('success', f"✅ 已成功下注！{u} 投 {b}")
                    else:
                        st.session_state['bet_msg'] = ('error', "系統繁忙，請重試")
            st.rerun()

# 分頁顯示
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["🏆 總積分排名", "⚽ 賽程", "📋 下注紀錄", "📊 勝率與心水", "📈 詳細統計", "✅ 賽果核對", "📉 走勢圖"])

with tab1:
    st.subheader("🏆 燈閪盃排名")
    df_scores_display = df_scores[['排名', '人名', '最終得分']].rename(columns={'最終得分': '得分'})
    df_scores_display['走勢'] = df_scores_display['人名'].apply(calc_form_streak)

    # 計算回報率：每注平均回報 ÷ 本金
    def calc_roi(player_name):
        p_data = merged[merged['人名'] == str(player_name).strip()]
        valid = p_data[p_data[target_res_col].astype(str).str.strip().isin(['上盤', '下盤', '上盤贏半', '下盤贏半'])]
        if valid.empty:
            return "-", 0
        total_payout = valid['回報'].sum()
        total_staked = len(valid) * STAKE
        roi_pct = (total_payout / total_staked) * 100 if total_staked > 0 else 0
        sign = "+" if total_payout >= 0 else ""
        return f"{sign}{roi_pct:.1f}%", total_payout

    roi_results = df_scores_display['人名'].apply(calc_roi)
    df_scores_display['回報率'] = roi_results.apply(lambda x: x[0])
    df_scores_display['_roi_val'] = roi_results.apply(lambda x: x[1])

    def style_streak(val):
        if str(val).startswith('W'):
            return 'color: #16a34a; font-weight: bold;'
        elif str(val).startswith('L'):
            return 'color: #dc2626; font-weight: bold;'
        return ''

    def style_roi(val):
        if str(val).startswith('+'):
            return 'color: #16a34a; font-weight: bold;'
        elif str(val).startswith('-'):
            return 'color: #dc2626; font-weight: bold;'
        return ''

    display_final = df_scores_display[['排名', '人名', '得分', '走勢', '回報率']]
    styled = display_final.style.map(style_streak, subset=['走勢']).map(style_roi, subset=['回報率'])
    st.dataframe(styled, hide_index=True, use_container_width=True)
    st.caption(f"💡 走勢：W = 連勝，L = 連敗。回報率：假設每注本金 {STAKE} 蚊，按 Google Sheet 賠率計算嘅平均盈虧百分比（只計已開波、非走盤場次）")

with tab2:
    st.subheader("⚽ 比賽賽程與賽果")
    display_cols = [c for c in ['場次', '讓球球隊', '盤口', '開賽時間', '賽果分數', '賽果分類', '結果分類'] if c in df_matches.columns]
    st.dataframe(df_matches[display_cols], hide_index=True, use_container_width=True)

with tab3:
    st.subheader("📋 手足落注紀錄")
    all_bet_matches = df_bets['場次'].unique().tolist()
    # 預設最新未完場
    default_idx = 0
    if not unplayed.empty:
        latest = str(unplayed.iloc[0]['場次']).strip()
        if latest in all_bet_matches:
            default_idx = all_bet_matches.index(latest)
        else:
            default_idx = len(all_bet_matches) - 1
    sel_match = st.selectbox("查看場次", options=all_bet_matches, index=default_idx)
    bet_col = '盤口' if '盤口' in df_bets.columns else '投注'
    st.dataframe(df_bets[df_bets['場次'] == sel_match][['人名', bet_col]], hide_index=True, use_container_width=True)

with tab4:
    st.subheader("📊 勝率與下場心水")
    upcoming = unplayed['場次'].iloc[0] if not unplayed.empty else None
    stats = []
    for p in all_players:
        p_data = merged[merged['人名'] == p]
        valid = p_data[p_data[target_res_col].notna() & (p_data[target_res_col].astype(str).str.strip() != '走盤') & (p_data[target_res_col].astype(str).str.strip() != 'nan') & (p_data[target_res_col].astype(str).str.strip() != '')]
        wins = len(valid[valid['得分'] > 0])
        total = len(valid)
        bet_col = '盤口' if '盤口' in df_bets.columns else '投注'
        next_bet = df_bets[(df_bets['人名'] == p) & (df_bets['場次'] == upcoming)][bet_col].values
        stats.append({
            '人名': p,
            '投注場次': total,
            '贏嘅場次': wins,
            '勝率': f"{(wins/total*100):.1f}%" if total > 0 else "0%",
            '_sort': (wins/total*100) if total > 0 else 0,
            '下一場心水': next_bet[0] if len(next_bet) > 0 else "未落注"
        })
    df_stats = pd.DataFrame(stats)
    df_stats['勝率排名'] = df_stats['_sort'].rank(method='min', ascending=False).astype(int)
    df_stats = df_stats.sort_values('勝率排名').reset_index(drop=True)
    df_stats = df_stats[['勝率排名', '人名', '投注場次', '贏嘅場次', '勝率', '下一場心水']]
    st.dataframe(df_stats, hide_index=True, use_container_width=True)

# =========================================================
# 📈 Tab 5: 詳細個人統計（潛水扣分 + 完整數據）
# =========================================================
with tab5:
    st.subheader("📈 手足詳細統計（含潛水扣分）")

    if not df_bets.empty and not df_matches.empty:
        df_bets_clean = df_bets.copy()
        df_bets_clean['人名'] = df_bets_clean['人名'].astype(str).str.strip()
        df_bets_clean['乾淨場次'] = df_bets_clean['場次'].astype(str).str.replace(' ', '').str.strip()

        df_matches_clean = df_matches.copy()
        df_matches_clean['乾淨場次'] = df_matches_clean['場次'].astype(str).str.replace(' ', '').str.strip()

        # 已完場次
        played_matches_df = df_matches_clean[
            df_matches_clean[target_res_col].notna() &
            (df_matches_clean[target_res_col].astype(str).str.strip() != '') &
            (df_matches_clean[target_res_col].astype(str).str.strip() != 'nan')
        ]
        played_matches_clean = played_matches_df['乾淨場次'].tolist()
        total_played_count = len(played_matches_clean)

        # 合併計分
        merged2 = df_bets_clean.merge(df_matches_clean[['乾淨場次', target_res_col]], on='乾淨場次', how='left')
        merged2['得分'] = merged2.apply(get_points, axis=1)

        df_player_scores = merged2.groupby('人名')['得分'].sum().reset_index()
        for p in all_players:
            p_clean = str(p).strip()
            if p_clean not in df_player_scores['人名'].tolist():
                df_player_scores = pd.concat([df_player_scores, pd.DataFrame([{'人名': p_clean, '得分': 0}])], ignore_index=True)

        # 潛水扣分計算
        def get_detailed_info(player_name):
            p_str = str(player_name).strip()
            df_p = df_bets_clean[df_bets_clean['人名'] == p_str]
            player_bets_in_played = df_p[df_p['乾淨場次'].isin(played_matches_clean)]['乾淨場次'].nunique() if not df_p.empty else 0
            total_missed = total_played_count - player_bets_in_played
            penalty = (total_missed // 2) * 10 if total_missed >= 2 else 0
            return pd.Series([total_played_count, player_bets_in_played, total_missed, penalty])

        df_player_scores[['總場數', '已投場數', '漏投場數', '潛水扣分']] = df_player_scores['人名'].apply(get_detailed_info)
        df_player_scores['最終得分'] = df_player_scores['得分'] - df_player_scores['潛水扣分']
        df_player_scores = df_player_scores.sort_values('最終得分', ascending=False).reset_index(drop=True)
        df_player_scores.index += 1
        df_player_scores = df_player_scores.reset_index().rename(columns={'index': '排名', '得分': '基礎得分', '最終得分': '得分'})

        st.dataframe(df_player_scores[['排名', '人名', '基礎得分', '總場數', '已投場數', '漏投場數', '潛水扣分', '得分']], hide_index=True, use_container_width=True)
        st.caption("💡 潛水扣分：每漏投2場扣10分（向下取整）")
    else:
        st.info("暫時未有足夠數據。")

# =========================================================
# ✅ Tab 6: 賽果核對
# =========================================================
with tab6:
    st.subheader("✅ 賽果核對")
    check_player = st.selectbox("選擇手足", options=all_players, key="check_player_sb")

    p_data = merged[merged['人名'] == check_player].copy()

    if not p_data.empty:
        bet_col = '盤口' if '盤口' in df_bets.columns else ('投注' if '投注' in df_bets.columns else None)

        def get_bet_choice(row):
            if '盤口_x' in row:
                return str(row['盤口_x']).strip()
            elif '投注' in row and str(row.get('投注', '')).strip() not in ['', 'nan']:
                return str(row['投注']).strip()
            else:
                return str(row.get('盤口', '')).strip()

        p_data['我嘅投注'] = p_data.apply(get_bet_choice, axis=1)
        p_data['賽果'] = p_data[target_res_col].astype(str).str.strip()

        def get_check_mark(row):
            result = row['賽果']
            if result in ['未開賽/進行中', '未開賽', '進行中', 'None', '', 'nan']:
                return "⏳ 未開波"
            if result == '走盤':
                return "➖ 走盤"
            if row['得分'] > 0:
                return "✅ 中"
            elif row['得分'] < 0:
                return "❌ 唔中"
            else:
                return "➖"

        p_data['核對'] = p_data.apply(get_check_mark, axis=1)

        # 跟賽程順序排
        order_map = {str(r): i for i, r in enumerate(df_matches['場次'].tolist())}
        p_data['_order'] = p_data['場次'].map(lambda x: order_map.get(str(x), 999))
        p_data = p_data.sort_values('_order')

        display_df = p_data[['場次', '我嘅投注', '賽果', '得分', '核對']].reset_index(drop=True)
        st.dataframe(display_df, hide_index=True, use_container_width=True)

        total_correct = len(p_data[p_data['得分'] > 0])
        total_wrong = len(p_data[p_data['得分'] < 0])
        total_valid = len(p_data[p_data['賽果'].isin(['上盤', '下盤', '上盤贏半', '下盤贏半'])])
        st.caption(f"📌 {check_player} 共投注 {len(p_data)} 場，已開波 {total_valid} 場，中 {total_correct} 場，唔中 {total_wrong} 場")
    else:
        st.info(f"{check_player} 暫時未有投注紀錄。")

# =========================================================
# 📉 Tab 7: 累積得分走勢圖
# =========================================================
with tab7:
    st.subheader("📉 燈閪盃積分走勢")

    # 跟賽程順序，搵出已完場嘅場次
    played_order = df_matches[
        df_matches[target_res_col].notna() &
        (df_matches[target_res_col].astype(str).str.strip() != '') &
        (df_matches[target_res_col].astype(str).str.strip() != 'nan')
    ]['場次'].astype(str).str.strip().tolist()

    if not played_order:
        st.info("暫時未有完場數據，未能繪製走勢圖。")
    else:
        # 為每個人計每場（按時序）嘅累積得分
        trend_data = {'場次': played_order}
        for p in all_players:
            p_clean = str(p).strip()
            cum_scores = []
            running_total = 0
            p_bets_dict = {}
            p_data = merged[merged['人名'] == p_clean]
            for _, r in p_data.iterrows():
                p_bets_dict[str(r['場次']).strip()] = r['得分']
            for match_name in played_order:
                running_total += p_bets_dict.get(match_name, 0)
                cum_scores.append(running_total)
            trend_data[p] = cum_scores

        df_trend = pd.DataFrame(trend_data)
        # 用「第1場、第2場...」做X軸標籤，避免場次名太長
        df_trend.index = [f"第{i+1}場" for i in range(len(played_order))]
        df_trend_plot = df_trend.drop(columns=['場次'])

        st.line_chart(df_trend_plot, use_container_width=True, height=450)

        with st.expander("📋 查看場次對照表"):
            ref_df = pd.DataFrame({
                '場次編號': [f"第{i+1}場" for i in range(len(played_order))],
                '場次名稱': played_order
            })
            st.dataframe(ref_df, hide_index=True, use_container_width=True)

        st.caption("💡 線圖顯示每位手足喺每場開波後嘅累積得分（未計潛水扣分），方便睇返大家嘅起跌走勢。")

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
KO_STREAK_PLACEHOLDER = st.empty()

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

# 載入淘汰賽資料（如果 sheet 唔存在或讀取失敗，用空 DataFrame 頂住）
def safe_load(sheet_name, cols):
    try:
        df = load_data(sheet_name)
        if df.empty:
            return pd.DataFrame(columns=cols)
        return df
    except Exception:
        return pd.DataFrame(columns=cols)

ko_matches_cols = ['場次', '輪次', '讓球球隊', '盤口', '上盤賠率', '下盤賠率', '開賽時間',
                    '全場賽果分數', '半場賽果分數', '賽果分類', '半全場結果', '上半頭15分入球', '下半頭15分入球']
ko_bets_cols = ['人名', '場次', '盤口投注', '半場波膽投注', '全場波膽投注', '半全場投注', '上半頭15分投注', '下半頭15分投注', '時間戳記']
ko_champion_cols = ['人名', '投注球隊', '時間戳記']

df_ko_matches = safe_load("KO_Matches", ko_matches_cols)
df_ko_bets = safe_load("KO_Bets", ko_bets_cols)
df_ko_champion = safe_load("KO_Champion", ko_champion_cols)

# 32強球隊名單（用嚐奪冠球隊揀選單）
KO_TEAMS = sorted(set(
    [str(t).strip() for t in df_ko_matches['場次'].dropna().apply(
        lambda x: str(x).split(' vs ')
    ).explode().tolist() if str(t).strip()
])) if not df_ko_matches.empty else []

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

# =========================================================
# 淘汰賽計分 Logic
# 1. 盤口：贏10/輸10（贏半5/輸半5），必投，唔投扣20
# 2. 半場波膽：中50/唔中-10
# 3. 全場波膽：中30/唔中-10
# 4. 半全場：中20/唔中-10
# 5. 上半頭15分入球：中30/唔中-10
# 6. 下半頭15分入球：中30/唔中-10
# 7. 奪冠球隊：中100/唔中0（一次性）
# =========================================================
KO_PLAYED_STATUSES = ['上盤', '下盤', '上盤贏半', '下盤贏半']

def ko_get_handicap_points(row):
    """盤口計分（同小組賽一樣邏輯）"""
    user_bet = str(row.get('盤口投注', '')).strip()
    match_result = str(row.get('賽果分類', '')).strip()
    if match_result not in KO_PLAYED_STATUSES:
        return 0
    if match_result == '上盤':
        return 10 if user_bet == '上盤' else -10
    if match_result == '下盤':
        return 10 if user_bet == '下盤' else -10
    if match_result == '上盤贏半':
        return 5 if user_bet == '上盤' else -5
    if match_result == '下盤贏半':
        return 5 if user_bet == '下盤' else -5
    return 0

def ko_get_score_points(row, bet_col, result_col, win_pts):
    """波膽類計分（半場/全場波膽共用）：完全中先有分，中咗就 +win_pts，落咗注但唔中 -10"""
    user_bet = str(row.get(bet_col, '')).strip()
    result = str(row.get(result_col, '')).strip()
    if user_bet in ['', 'nan']:
        return 0  # 冇落呢項就唔計（選擇性項目）
    if result in ['', 'nan', 'None']:
        return 0  # 未開波/未填結果
    return win_pts if user_bet == result else -10

def ko_get_htft_points(row):
    """半全場計分：主主/主客/和和/客客/客主"""
    user_bet = str(row.get('半全場投注', '')).strip()
    result = str(row.get('半全場結果', '')).strip()
    if user_bet in ['', 'nan']:
        return 0
    if result in ['', 'nan', 'None']:
        return 0
    return 20 if user_bet == result else -10

def ko_get_first15_points(row, bet_col, result_col):
    """上/下半頭15分入球計分：是/否"""
    user_bet = str(row.get(bet_col, '')).strip()
    result = str(row.get(result_col, '')).strip()
    if user_bet in ['', 'nan']:
        return 0
    if result in ['', 'nan', 'None']:
        return 0
    return 30 if user_bet == result else -10

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
# 淘汰賽：數據合併同計分
# =========================================================
if not df_ko_bets.empty and not df_ko_matches.empty:
    ko_merge_cols = [c for c in ['場次', '賽果分類', '半全場結果', '上半頭15分入球', '下半頭15分入球', '讓球球隊', '盤口'] if c in df_ko_matches.columns]
    ko_merged = df_ko_bets.merge(df_ko_matches[ko_merge_cols], on='場次', how='left', suffixes=('', '_match'))

    ko_merged['盤口得分'] = ko_merged.apply(ko_get_handicap_points, axis=1)
    ko_merged['半場波膽得分'] = ko_merged.apply(lambda r: ko_get_score_points(r, '半場波膽投注', '半場賽果分數', 50), axis=1) if '半場賽果分數' in df_ko_matches.columns else 0
    ko_merged['全場波膽得分'] = ko_merged.apply(lambda r: ko_get_score_points(r, '全場波膽投注', '全場賽果分數', 30), axis=1) if '全場賽果分數' in df_ko_matches.columns else 0
    ko_merged['半全場得分'] = ko_merged.apply(ko_get_htft_points, axis=1)
    ko_merged['上半15分得分'] = ko_merged.apply(lambda r: ko_get_first15_points(r, '上半頭15分投注', '上半頭15分入球'), axis=1)
    ko_merged['下半15分得分'] = ko_merged.apply(lambda r: ko_get_first15_points(r, '下半頭15分投注', '下半頭15分入球'), axis=1)

    ko_merged['淘汰賽總分'] = (
        ko_merged['盤口得分'] + ko_merged['半場波膽得分'] + ko_merged['全場波膽得分'] +
        ko_merged['半全場得分'] + ko_merged['上半15分得分'] + ko_merged['下半15分得分']
    )
else:
    ko_merged = pd.DataFrame()

# 淘汰賽已完場場次（盤口已有結果）
if not df_ko_matches.empty and '賽果分類' in df_ko_matches.columns:
    ko_played_matches = df_ko_matches[
        df_ko_matches['賽果分類'].notna() &
        (df_ko_matches['賽果分類'].astype(str).str.strip().isin(KO_PLAYED_STATUSES))
    ]['場次'].astype(str).str.strip().tolist()
else:
    ko_played_matches = []
ko_total_played = len(ko_played_matches)

def ko_calc_penalty(player_name):
    """淘汰賽漏賭扣分：盤口冇落注 -20"""
    if df_ko_bets.empty:
        return 0
    p_bets = df_ko_bets[df_ko_bets['人名'] == str(player_name).strip()]
    bet_matches = p_bets['場次'].astype(str).str.strip().tolist() if not p_bets.empty else []
    missed = ko_total_played - len([m for m in ko_played_matches if m in bet_matches])
    return missed * 20

def ko_get_champion_points(player_name):
    """奪冠球隊：中100/唔中0，未開出冠軍前都係0"""
    if df_ko_champion.empty:
        return 0
    p_pick = df_ko_champion[df_ko_champion['人名'] == str(player_name).strip()]
    if p_pick.empty:
        return 0
    # 冠軍球隊要靠管理員自行喺 KO_Matches 標記，暫時用一個簡單方法：
    # 留個 hook，未有「冠軍結果」資料嘅話一律當未開出（0分）
    return 0  # 待冠軍出咗之後手動處理或之後加冠軍結果欄

# 計每個人嘅淘汰賽總得分
def ko_calc_total(player_name):
    if ko_merged.empty:
        base = 0
    else:
        p_data = ko_merged[ko_merged['人名'] == str(player_name).strip()]
        base = p_data['淘汰賽總分'].sum() if not p_data.empty else 0
    penalty = ko_calc_penalty(player_name)
    champion_pts = ko_get_champion_points(player_name)
    return base - penalty + champion_pts

df_ko_scores = pd.DataFrame({'人名': all_players})
df_ko_scores['淘汰賽得分'] = df_ko_scores['人名'].apply(ko_calc_total)
df_ko_scores['排名'] = df_ko_scores['淘汰賽得分'].rank(method='min', ascending=False).astype(int)
df_ko_scores = df_ko_scores.sort_values('排名')

# =========================================================
# 淘汰賽連中提示（用「盤口」項目嚐連中計算，跟賽程順序）
# =========================================================
ko_match_order_map = {str(r).strip(): i for i, r in enumerate(df_ko_matches['場次'].tolist())} if not df_ko_matches.empty else {}

def ko_calc_current_streak(player_name):
    if ko_merged.empty:
        return 0
    p_data = ko_merged[ko_merged['人名'] == str(player_name).strip()].copy()
    if p_data.empty:
        return 0
    p_data['_order'] = p_data['場次'].astype(str).str.strip().map(lambda x: ko_match_order_map.get(x, -1))
    p_data['_result'] = p_data['賽果分類'].astype(str).str.strip() if '賽果分類' in p_data.columns else ''
    valid = p_data[p_data['_result'].isin(KO_PLAYED_STATUSES)].sort_values('_order')
    if valid.empty:
        return 0
    streak = 0
    for score in reversed(valid['盤口得分'].tolist()):
        if score > 0:
            streak += 1
        else:
            break
    return streak

ko_streak_data = [(p, ko_calc_current_streak(p)) for p in all_players]
ko_max_streak_val = max((v for _, v in ko_streak_data), default=0)
ko_top_streak_players = [p for p, v in ko_streak_data if v == ko_max_streak_val]

if ko_max_streak_val >= 2:
    ko_names_str = "、".join(ko_top_streak_players)
    KO_STREAK_PLACEHOLDER.markdown(f"### 🔥 {ko_names_str} 喺淘汰賽已經連中 {ko_max_streak_val} 鋪了！")

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

# 小組賽冠軍訊息（用小組賽最終得分嗰位）
group_champion_name = df_scores.iloc[0]['人名'] if not df_scores.empty else ""
STREAK_PLACEHOLDER.markdown(f"### 🏆 恭喜 {group_champion_name} 成為小組賽冠軍！！！")

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

# 側邊欄落注（小組賽已完，呢個區塊隱藏；要重開就將下面 GROUP_STAGE_BETTING_OPEN 改做 True）
GROUP_STAGE_BETTING_OPEN = False

if GROUP_STAGE_BETTING_OPEN:
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

# =========================================================
# 側邊欄：淘汰賽落注
# =========================================================
ko_unplayed = pd.DataFrame()
if not df_ko_matches.empty:
    ko_unplayed = df_ko_matches[
        df_ko_matches['賽果分類'].isna() |
        (df_ko_matches['賽果分類'].astype(str).str.strip().isin(['', 'nan', 'None']))
    ].copy() if '賽果分類' in df_ko_matches.columns else df_ko_matches.copy()

    if '開賽時間' in ko_unplayed.columns:
        ko_unplayed['_kickoff'] = pd.to_datetime(ko_unplayed['開賽時間'], errors='coerce').dt.tz_localize(hk_tz, ambiguous='NaT', nonexistent='NaT')
        ko_unplayed = ko_unplayed[ko_unplayed['_kickoff'].isna() | (ko_unplayed['_kickoff'] > now_hk)]

if 'ko_bet_msg' in st.session_state:
    msg_type, msg_text = st.session_state.pop('ko_bet_msg')
    if msg_type == 'success':
        st.sidebar.success(msg_text)
    else:
        st.sidebar.error(msg_text)

with st.sidebar.expander("🏆 淘汰賽落注", expanded=False):
    if df_ko_matches.empty:
        st.info("淘汰賽賽程未準備好。")
    else:
        ku = st.selectbox("選擇名字", options=all_players, index=None, key="ko_name_sb")
        if ko_unplayed.empty:
            st.info("🚫 全部淘汰賽場次已開波或完場，無得再落注。")
        else:
            km = st.selectbox("選擇場次", options=ko_unplayed['場次'].tolist(), key="ko_match_sb")

            km_row = df_ko_matches[df_ko_matches['場次'].astype(str).str.strip() == str(km).strip()]
            handicap_team = str(km_row.iloc[0].get('讓球球隊', '')).strip() if not km_row.empty else ''
            teams = str(km).replace(' vs ', '|').split('|')
            home_team = teams[0].strip() if len(teams) == 2 else ''
            away_team = teams[1].strip() if len(teams) == 2 else ''
            other_team = away_team if handicap_team == home_team else home_team

            with st.form("ko_bet_form", clear_on_submit=True):
                st.markdown(f"**1. 盤口（必投，唔投扣20分）**")
                ko_handicap = st.radio("盤口", [f"上盤 {handicap_team}", f"下盤 {other_team}"], key="ko_handicap_radio", label_visibility="collapsed")
                ko_handicap_val = "上盤" if ko_handicap.startswith("上盤") else "下盤"

                st.markdown("**2. 半場波膽（選擇性，中+50/錯-10）**")
                half_score_options = ["未揀", "1:0", "2:0", "2:1", "3:1", "3:2", "4:1", "4:2",
                                       "0:0", "1:1", "2:2", "3:3",
                                       "0:1", "0:2", "1:2", "0:3", "1:3", "2:3", "1:4", "2:4",
                                       "主其他", "客其他"]
                ko_half_score = st.selectbox("半場波膽", half_score_options, key="ko_half_score_sb", label_visibility="collapsed")

                st.markdown("**3. 全場波膽（選擇性，中+30/錯-10）**")
                full_score_options = ["未揀", "1:0", "2:0", "2:1", "3:1", "3:2", "4:1", "4:2", "4:3", "5:1", "5:2", "5:3", "5:4",
                                       "0:0", "1:1", "2:2", "3:3",
                                       "0:1", "0:2", "1:2", "0:3", "1:3", "2:3", "1:4", "2:4", "3:4", "1:5", "2:5", "3:5", "4:5",
                                       "主其他", "客其他"]
                ko_full_score = st.selectbox("全場波膽", full_score_options, key="ko_full_score_sb", label_visibility="collapsed")

                st.markdown("**4. 半全場（選擇性，中+20/錯-10）**")
                htft_options = ["未揀", "主主", "主客", "和和", "客客", "客主"]
                ko_htft = st.selectbox("半全場", htft_options, key="ko_htft_sb", label_visibility="collapsed")

                st.markdown("**5. 上半場頭15分鐘入球（選擇性，中+30/錯-10）**")
                ko_first15_1h = st.selectbox("上半頭15分", ["未揀", "是", "否"], key="ko_first15_1h_sb", label_visibility="collapsed")

                st.markdown("**6. 下半場頭15分鐘入球（選擇性，中+30/錯-10）**")
                ko_first15_2h = st.selectbox("下半頭15分", ["未揀", "是", "否"], key="ko_first15_2h_sb", label_visibility="collapsed")

                if st.form_submit_button("🔥 提交淘汰賽投注"):
                    if ku is None:
                        st.session_state['ko_bet_msg'] = ('error', "⚠️ 必須先選擇名字！")
                    else:
                        df_ko_current = safe_load("KO_Bets", ko_bets_cols)
                        if not df_ko_current.empty and not df_ko_current[(df_ko_current['人名'] == ku) & (df_ko_current['場次'] == km)].empty:
                            st.session_state['ko_bet_msg'] = ('error', "❌ 呢場你投過喇，唔准改！")
                        else:
                            params = {
                                'sheet': 'KO_Bets',
                                'name': ku,
                                'match': km,
                                '盤口投注': ko_handicap_val,
                                '半場波膽投注': '' if ko_half_score == '未揀' else ko_half_score,
                                '全場波膽投注': '' if ko_full_score == '未揀' else ko_full_score,
                                '半全場投注': '' if ko_htft == '未揀' else ko_htft,
                                '上半頭15分投注': '' if ko_first15_1h == '未揀' else ko_first15_1h,
                                '下半頭15分投注': '' if ko_first15_2h == '未揀' else ko_first15_2h,
                            }
                            resp = requests.get(GAS_URL, params=params)
                            if resp.status_code == 200:
                                st.session_state['ko_bet_msg'] = ('success', f"✅ 已成功下注！{ku} - {km}")
                            else:
                                st.session_state['ko_bet_msg'] = ('error', "系統繁忙，請重試")
                        st.rerun()

# =========================================================
# 側邊欄：奪冠球隊（一次性投注）
# =========================================================
if 'champ_msg' in st.session_state:
    msg_type, msg_text = st.session_state.pop('champ_msg')
    if msg_type == 'success':
        st.sidebar.success(msg_text)
    else:
        st.sidebar.error(msg_text)

with st.sidebar.expander("👑 奪冠球隊（一次性，鎖死）", expanded=False):
    if not KO_TEAMS:
        st.info("32強隊伍名單未準備好。")
    else:
        cu = st.selectbox("選擇名字", options=all_players, index=None, key="champ_name_sb")
        with st.form("champion_form", clear_on_submit=True):
            cc = st.selectbox("選擇奪冠球隊", options=KO_TEAMS, key="champ_team_sb")
            if st.form_submit_button("👑 確認下注（不可更改）"):
                if cu is None:
                    st.session_state['champ_msg'] = ('error', "⚠️ 必須先選擇名字！")
                else:
                    df_champ_current = safe_load("KO_Champion", ko_champion_cols)
                    if not df_champ_current.empty and not df_champ_current[df_champ_current['人名'] == cu].empty:
                        st.session_state['champ_msg'] = ('error', f"❌ {cu} 已經揀過奪冠球隊喇，唔准改！")
                    else:
                        resp = requests.get(GAS_URL, params={'sheet': 'KO_Champion', 'name': cu, '投注球隊': cc})
                        if resp.status_code == 200:
                            st.session_state['champ_msg'] = ('success', f"✅ {cu} 已下注奪冠球隊：{cc}（已鎖死）")
                        else:
                            st.session_state['champ_msg'] = ('error', "系統繁忙，請重試")
                    st.rerun()

# 分頁顯示
tab_ko, tab1, tab2, tab_ko_mix, tab_mix, tab6, tab7 = st.tabs(["🏆 淘汰賽", "🏆 總積分排名", "⚽ 賽程", "🏆 淘汰賽詳情", "📊 小組賽詳情", "✅ 賽果核對", "📉 走勢圖"])

with tab_ko:
    st.subheader("🏆 淘汰賽積分排名")

    if df_ko_matches.empty:
        st.info("淘汰賽賽程未準備好。")
    else:
        st.dataframe(df_ko_scores[['排名', '人名', '淘汰賽得分']], hide_index=True, use_container_width=True)
        st.caption("💡 淘汰賽計分：盤口±10（贏半±5，必投，唔投扣20）、半場波膽中+50、全場波膽中+30、半全場中+20、上/下半頭15分入球中各+30，以上選擇性項目錯咗一律-10。奪冠球隊中+100（一次性，鎖死）。")

        if not df_ko_champion.empty:
            st.divider()
            st.subheader("👑 奪冠球隊投注紀錄")
            champ_display_cols = [c for c in ['人名', '投注球隊'] if c in df_ko_champion.columns]
            st.dataframe(df_ko_champion[champ_display_cols], hide_index=True, use_container_width=True)

with tab1:
    st.subheader("🏆 燈閪盃排名（小組賽 + 淘汰賽）")
    df_scores_display = df_scores[['排名', '人名', '最終得分']].rename(columns={'最終得分': '小組賽得分', '排名': '小組賽排名'})

    # 合併淘汰賽得分
    ko_score_map = dict(zip(df_ko_scores['人名'], df_ko_scores['淘汰賽得分'])) if 'df_ko_scores' in dir() and not df_ko_scores.empty else {}
    df_scores_display['淘汰賽得分'] = df_scores_display['人名'].map(lambda p: ko_score_map.get(p, 0))
    df_scores_display['總分'] = df_scores_display['小組賽得分'] + df_scores_display['淘汰賽得分']
    df_scores_display['排名'] = df_scores_display['總分'].rank(method='min', ascending=False).astype(int)
    df_scores_display = df_scores_display.sort_values('排名')

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

    display_final = df_scores_display[['排名', '人名', '小組賽得分', '淘汰賽得分', '總分', '走勢', '回報率']]
    styled = display_final.style.map(style_streak, subset=['走勢']).map(style_roi, subset=['回報率'])
    st.dataframe(styled, hide_index=True, use_container_width=True)
    st.caption(f"💡 總分 = 小組賽得分 + 淘汰賽得分。走勢：W = 連勝，L = 連敗（小組賽）。回報率：假設每注本金 {STAKE} 蚊，按 Google Sheet 賠率計算嘅平均盈虧百分比（只計小組賽已開波、非走盤場次）")

with tab2:
    sched_inner1, sched_inner2 = st.tabs(["⚽ 小組賽賽程", "🏆 淘汰賽賽程"])

    with sched_inner1:
        st.subheader("⚽ 比賽賽程與賽果")
        display_cols = [c for c in ['場次', '讓球球隊', '盤口', '開賽時間', '賽果分數', '賽果分類', '結果分類'] if c in df_matches.columns]
        st.dataframe(df_matches[display_cols], hide_index=True, use_container_width=True)

    with sched_inner2:
        st.subheader("🏆 淘汰賽賽程")
        if df_ko_matches.empty:
            st.info("淘汰賽賽程未準備好。")
        else:
            ko_display_cols = [c for c in ['場次', '輪次', '讓球球隊', '盤口', '開賽時間', '全場賽果分數', '半場賽果分數', '賽果分類', '半全場結果', '上半頭15分入球', '下半頭15分入球'] if c in df_ko_matches.columns]
            st.dataframe(df_ko_matches[ko_display_cols], hide_index=True, use_container_width=True)

with tab_ko_mix:
    st.subheader("🏆 淘汰賽詳情")

    if df_ko_matches.empty or df_ko_bets.empty:
        st.info("淘汰賽暫時未有足夠數據。")
    else:
        ko_inner1, ko_inner2, ko_inner3 = st.tabs(["📋 下注紀錄", "📊 勝率與心水", "📈 詳細統計"])

        with ko_inner1:
            ko_all_bet_matches = df_ko_bets['場次'].unique().tolist()
            ko_default_idx = 0
            if not ko_unplayed.empty:
                ko_latest = str(ko_unplayed.iloc[0]['場次']).strip()
                if ko_latest in ko_all_bet_matches:
                    ko_default_idx = ko_all_bet_matches.index(ko_latest)
                else:
                    ko_default_idx = len(ko_all_bet_matches) - 1
            ko_sel_match = st.selectbox("查看場次", options=ko_all_bet_matches, index=ko_default_idx, key="ko_mix_match_sb")
            ko_bet_display_cols = [c for c in ['人名', '盤口投注', '半場波膽投注', '全場波膽投注', '半全場投注', '上半頭15分投注', '下半頭15分投注'] if c in df_ko_bets.columns]
            st.dataframe(df_ko_bets[df_ko_bets['場次'] == ko_sel_match][ko_bet_display_cols], hide_index=True, use_container_width=True)

        with ko_inner2:
            ko_upcoming = ko_unplayed['場次'].iloc[0] if not ko_unplayed.empty else None
            ko_stats = []
            for p in all_players:
                p_data = ko_merged[ko_merged['人名'] == p] if not ko_merged.empty else pd.DataFrame()
                valid = p_data[p_data['賽果分類'].astype(str).str.strip().isin(KO_PLAYED_STATUSES)] if not p_data.empty else pd.DataFrame()
                wins = len(valid[valid['盤口得分'] > 0]) if not valid.empty else 0
                total = len(valid)
                next_bet = df_ko_bets[(df_ko_bets['人名'] == p) & (df_ko_bets['場次'] == ko_upcoming)]['盤口投注'].values if not df_ko_bets.empty else []
                ko_stats.append({
                    '人名': p,
                    '投注場次': total,
                    '贏嘅場次': wins,
                    '勝率': f"{(wins/total*100):.1f}%" if total > 0 else "0%",
                    '_sort': (wins/total*100) if total > 0 else 0,
                    '下一場心水': next_bet[0] if len(next_bet) > 0 else "未落注"
                })
            ko_df_stats = pd.DataFrame(ko_stats)
            ko_df_stats['勝率排名'] = ko_df_stats['_sort'].rank(method='min', ascending=False).astype(int)
            ko_df_stats = ko_df_stats.sort_values('勝率排名').reset_index(drop=True)
            ko_df_stats = ko_df_stats[['勝率排名', '人名', '投注場次', '贏嘅場次', '勝率', '下一場心水']]
            st.dataframe(ko_df_stats, hide_index=True, use_container_width=True)
            st.caption("💡 呢個勝率只計「盤口」項目（必投項目），唔包括半場波膽/全場波膽/半全場/頭15分入球。")

        with ko_inner3:
            ko_detail_display = df_ko_scores.copy()
            ko_detail_display['漏賭扣分'] = ko_detail_display['人名'].apply(ko_calc_penalty)
            ko_detail_display = ko_detail_display[['排名', '人名', '淘汰賽得分', '漏賭扣分']]
            st.dataframe(ko_detail_display, hide_index=True, use_container_width=True)
            st.caption("💡 淘汰賽得分已扣除漏賭扣分（每場盤口冇落注 -20）同計入奪冠球隊分數。")

with tab_mix:
    st.subheader("📊 小組賽詳情")
    inner1, inner2, inner3 = st.tabs(["📋 下注紀錄", "📊 勝率與心水", "📈 詳細統計"])

    with inner1:
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

    with inner2:
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

    with inner3:
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
    check_inner1, check_inner2 = st.tabs(["⚽ 小組賽", "🏆 淘汰賽"])

    with check_inner1:
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

    with check_inner2:
        if df_ko_matches.empty or ko_merged.empty:
            st.info("淘汰賽暫時未有數據。")
        else:
            ko_check_player = st.selectbox("選擇手足", options=all_players, key="ko_check_player_sb")

            ko_p_data = ko_merged[ko_merged['人名'] == ko_check_player].copy()

            if not ko_p_data.empty:
                def ko_get_check_mark(score, has_bet, has_result):
                    if not has_bet:
                        return "➖ 未落注"
                    if not has_result:
                        return "⏳ 未開波"
                    if score > 0:
                        return "✅ 中"
                    elif score < 0:
                        return "❌ 唔中"
                    else:
                        return "➖"

                rows = []
                for _, r in ko_p_data.iterrows():
                    handicap_result = str(r.get('賽果分類', '')).strip()
                    has_handicap_result = handicap_result in KO_PLAYED_STATUSES
                    rows.append({
                        '場次': r['場次'],
                        '盤口投注': r.get('盤口投注', ''),
                        '盤口結果': handicap_result if has_handicap_result else '未開波',
                        '盤口': ko_get_check_mark(r.get('盤口得分', 0), str(r.get('盤口投注', '')).strip() not in ['', 'nan'], has_handicap_result),
                        '半場波膽': ko_get_check_mark(r.get('半場波膽得分', 0), str(r.get('半場波膽投注', '')).strip() not in ['', 'nan'], str(r.get('半場賽果分數', '')).strip() not in ['', 'nan', 'None']),
                        '全場波膽': ko_get_check_mark(r.get('全場波膽得分', 0), str(r.get('全場波膽投注', '')).strip() not in ['', 'nan'], str(r.get('全場賽果分數', '')).strip() not in ['', 'nan', 'None']),
                        '半全場': ko_get_check_mark(r.get('半全場得分', 0), str(r.get('半全場投注', '')).strip() not in ['', 'nan'], str(r.get('半全場結果', '')).strip() not in ['', 'nan', 'None']),
                        '上半15分': ko_get_check_mark(r.get('上半15分得分', 0), str(r.get('上半頭15分投注', '')).strip() not in ['', 'nan'], str(r.get('上半頭15分入球', '')).strip() not in ['', 'nan', 'None']),
                        '下半15分': ko_get_check_mark(r.get('下半15分得分', 0), str(r.get('下半頭15分投注', '')).strip() not in ['', 'nan'], str(r.get('下半頭15分入球', '')).strip() not in ['', 'nan', 'None']),
                        '本場總分': r.get('淘汰賽總分', 0),
                    })

                ko_display_df = pd.DataFrame(rows)
                # 跟淘汰賽賽程順序排
                ko_display_df['_order'] = ko_display_df['場次'].map(lambda x: ko_match_order_map.get(str(x).strip(), 999))
                ko_display_df = ko_display_df.sort_values('_order').drop(columns=['_order']).reset_index(drop=True)

                st.dataframe(ko_display_df, hide_index=True, use_container_width=True)

                # 奪冠球隊投注顯示
                champ_pick = df_ko_champion[df_ko_champion['人名'] == ko_check_player] if not df_ko_champion.empty else pd.DataFrame()
                champ_text = champ_pick.iloc[0]['投注球隊'] if not champ_pick.empty else "未落注"
                st.caption(f"👑 奪冠球隊投注：{champ_text}")

                ko_penalty = ko_calc_penalty(ko_check_player)
                ko_total = ko_calc_total(ko_check_player)
                st.caption(f"📌 {ko_check_player} 淘汰賽漏賭扣分：{ko_penalty}，淘汰賽總得分：{ko_total}")
            else:
                st.info(f"{ko_check_player} 暫時未有淘汰賽投注紀錄。")

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
        # 用數字做 index（1, 2, 3...），避免 line_chart 將「第10場」當文字排序而搬亂順序
        df_trend.index = range(1, len(played_order) + 1)
        df_trend.index.name = "場次編號"
        df_trend_plot = df_trend.drop(columns=['場次'])

        selected_players = st.multiselect(
            "選擇想睇嘅手足（可多選，留空 = 全部顯示）",
            options=all_players,
            default=[]
        )

        if selected_players:
            df_trend_plot = df_trend_plot[selected_players]

        st.line_chart(df_trend_plot, use_container_width=True, height=450)

        with st.expander("📋 查看場次對照表"):
            ref_df = pd.DataFrame({
                '場次編號': range(1, len(played_order) + 1),
                '場次名稱': played_order
            })
            st.dataframe(ref_df, hide_index=True, use_container_width=True)

        st.caption("💡 線圖顯示每位手足喺每場開波後嘅累積得分（未計潛水扣分），方便睇返大家嘅起跌走勢。")

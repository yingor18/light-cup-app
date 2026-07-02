import streamlit as st
import streamlit.components.v1 as components
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
DAN_PLACEHOLDER = st.empty()
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
        # 確保所有預期欄位都存在，避免 KeyError
        for col in cols:
            if col not in df.columns:
                df[col] = ''
        return df
    except Exception:
        return pd.DataFrame(columns=cols)
ko_matches_cols = ['場次', '輪次', '讓球球隊', '盤口', '上盤賠率', '下盤賠率', '開賽時間',
                    '全場賽果分數', '半場賽果分數', '賽果分類', '半全場結果', '上半頭15分入球', '下半頭15分入球', '啟動晉級計分', '晉級球隊',
                    '半場角球結果', '全場角球結果', '罰牌大細結果', '大細波結果', '半大結果',
                    '半場角球盤口', '全場角球盤口', '罰牌盤口', '大細波盤口', '半大盤口']
ko_bets_cols = ['人名', '場次', '盤口投注', '晉級球隊投注', '半場波膽投注', '全場波膽投注', '半全場投注', '上半頭15分投注', '下半頭15分投注',
                 '半場角球投注', '全場角球投注', '罰牌大細投注', '大細波投注', '半大投注', '時間戳記']
ko_champion_cols = ['人名', '投注球隊', '是否冠軍', '時間戳記']
df_ko_matches = safe_load("KO_Matches", ko_matches_cols)
df_ko_bets = safe_load("KO_Bets", ko_bets_cols)
df_ko_champion = safe_load("KO_Champion", ko_champion_cols)
# 32強球隊名單（用嚐奪冠球隊揀選單）
KO_TEAMS = sorted(set(
    [str(t).strip() for t in df_ko_matches['場次'].dropna().apply(
        lambda x: str(x).split(' vs ')
    ).explode().tolist() if str(t).strip()
])) if not df_ko_matches.empty else []
# 搵出實際嘅冠軍隊（KO_Champion 嗰欄「是否冠軍」打「是」嗰行）
def get_champion_team():
    if df_ko_champion.empty or '是否冠軍' not in df_ko_champion.columns:
        return None
    champ_row = df_ko_champion[df_ko_champion['是否冠軍'].astype(str).str.strip() == '是']
    if champ_row.empty:
        return None
    return str(champ_row.iloc[0]['投注球隊']).strip()
ACTUAL_CHAMPION_TEAM = get_champion_team()
# =========================================================
# 核心計分 Logic（小組賽）
# =========================================================
def get_points(row):
    if '盤口_x' in row:
        user_bet = str(row['盤口_x']).strip()
    elif '投注' in row and str(row.get('投注', '')).strip() not in ['', 'nan']:
        user_bet = str(row['投注']).strip()
    else:
        user_bet = str(row.get('盤口', '')).strip()
    match_result = str(row.get(target_res_col, '')).strip()
    if match_result in ['未開賽/進行中', '未開賽', '進行中', 'None', '', 'nan', '走盤']:
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
    if match_result == '上盤':
        return (user_odds - 1) * STAKE if user_bet == '上盤' else -STAKE
    if match_result == '下盤':
        return (user_odds - 1) * STAKE if user_bet == '下盤' else -STAKE
    if match_result == '上盤贏半':
        return (user_odds - 1) * STAKE * 0.5 if user_bet == '上盤' else -STAKE * 0.5
    if match_result == '下盤贏半':
        return (user_odds - 1) * STAKE * 0.5 if user_bet == '下盤' else -STAKE * 0.5
    return 0
# =========================================================
# 淘汰賽計分 Logic
# =========================================================
KO_PLAYED_STATUSES = ['上盤', '下盤', '上盤贏半', '下盤贏半']
def ko_get_handicap_points(row):
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
def ko_get_advance_points(row):
    """晉級球隊：必揀，讀取 KO_Matches 嘅「晉級球隊」欄（管理員手動填）判斷係咪中
       中+10/唔中-10，未揀-10
       只有 KO_Matches 嗰場「啟動晉級計分」打「是」先會計分"""
    enabled = str(row.get('啟動晉級計分', '')).strip()
    if enabled != '是':
        return 0
    user_bet = str(row.get('晉級球隊投注', '')).strip()
    actual_winner = str(row.get('晉級球隊', '')).strip()  # 管理員填嘅晉級球隊
    if actual_winner in ['', 'nan', 'None']:
        return 0  # 管理員未填，唔計分
    if user_bet in ['', 'nan']:
        return -10  # 必揀，未揀扣10
    return 10 if user_bet == actual_winner else -10
def ko_get_score_points(row, bet_col, result_col, win_pts):
    user_bet = str(row.get(bet_col, '')).strip()
    result = str(row.get(result_col, '')).strip()
    if user_bet in ['', 'nan']:
        return 0
    if result in ['', 'nan', 'None']:
        return 0
    return win_pts if user_bet == result else -10
def ko_get_htft_points(row):
    user_bet = str(row.get('半全場投注', '')).strip()
    result = str(row.get('半全場結果', '')).strip()
    if user_bet in ['', 'nan']:
        return 0
    if result in ['', 'nan', 'None']:
        return 0
    return 20 if user_bet == result else -10
def ko_get_first15_points(row, bet_col, result_col):
    """上/下半頭15分入球：得「是」一個選項。揀咗「是」中咗就+30，唔中-10；冇揀（空白）唔計分。"""
    user_bet = str(row.get(bet_col, '')).strip()
    result = str(row.get(result_col, '')).strip()
    if user_bet in ['', 'nan']:
        return 0
    if result in ['', 'nan', 'None']:
        return 0
    return 30 if user_bet == result else -10
def ko_get_ou_points(row, bet_col, result_col):
    """大細類新項目（半場角球/全場角球/罰牌大細/大細波/半大）：
       選擇性、落唔落都唔扣分、中+20、錯-10、走盤=0（可以有走盤）"""
    user_bet = str(row.get(bet_col, '')).strip()
    result = str(row.get(result_col, '')).strip()
    if user_bet in ['', 'nan']:
        return 0
    if result in ['', 'nan', 'None']:
        return 0
    if result == '走盤':
        return 0
    return 20 if user_bet == result else -10
# 數據合併（小組賽）
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
# 淘汰賽數據合併 - 統一用「乾淨場次」去除空格差異
# =========================================================
if not df_ko_bets.empty and not df_ko_matches.empty:
    df_ko_bets['乾淨場次'] = df_ko_bets['場次'].astype(str).str.replace(' ', '').str.strip()
    df_ko_matches['乾淨場次'] = df_ko_matches['場次'].astype(str).str.replace(' ', '').str.strip()
    ko_merge_cols = [c for c in ['乾淨場次', '賽果分類', '半全場結果', '上半頭15分入球', '下半頭15分入球', '讓球球隊', '盤口',
                                  '半場賽果分數', '全場賽果分數', '啟動晉級計分', '晉級球隊',
                                  '半場角球結果', '全場角球結果', '罰牌大細結果', '大細波結果', '半大結果',
                                  '半場角球盤口', '全場角球盤口', '罰牌盤口', '大細波盤口', '半大盤口'] if c in df_ko_matches.columns]
    ko_merged = df_ko_bets.merge(df_ko_matches[ko_merge_cols], on='乾淨場次', how='left', suffixes=('', '_match'))
    ko_merged['盤口得分'] = ko_merged.apply(ko_get_handicap_points, axis=1)
    ko_merged['晉級球隊得分'] = ko_merged.apply(ko_get_advance_points, axis=1)
    ko_merged['半場波膽得分'] = ko_merged.apply(lambda r: ko_get_score_points(r, '半場波膽投注', '半場賽果分數', 30), axis=1) if '半場賽果分數' in df_ko_matches.columns else 0
    ko_merged['全場波膽得分'] = ko_merged.apply(lambda r: ko_get_score_points(r, '全場波膽投注', '全場賽果分數', 50), axis=1) if '全場賽果分數' in df_ko_matches.columns else 0
    ko_merged['半全場得分'] = ko_merged.apply(ko_get_htft_points, axis=1)
    ko_merged['上半15分得分'] = ko_merged.apply(lambda r: ko_get_first15_points(r, '上半頭15分投注', '上半頭15分入球'), axis=1)
    ko_merged['下半15分得分'] = ko_merged.apply(lambda r: ko_get_first15_points(r, '下半頭15分投注', '下半頭15分入球'), axis=1)
    ko_merged['半場角球得分'] = ko_merged.apply(lambda r: ko_get_ou_points(r, '半場角球投注', '半場角球結果'), axis=1) if '半場角球結果' in df_ko_matches.columns else 0
    ko_merged['全場角球得分'] = ko_merged.apply(lambda r: ko_get_ou_points(r, '全場角球投注', '全場角球結果'), axis=1) if '全場角球結果' in df_ko_matches.columns else 0
    ko_merged['罰牌大細得分'] = ko_merged.apply(lambda r: ko_get_ou_points(r, '罰牌大細投注', '罰牌大細結果'), axis=1) if '罰牌大細結果' in df_ko_matches.columns else 0
    ko_merged['大細波得分'] = ko_merged.apply(lambda r: ko_get_ou_points(r, '大細波投注', '大細波結果'), axis=1) if '大細波結果' in df_ko_matches.columns else 0
    ko_merged['半大得分'] = ko_merged.apply(lambda r: ko_get_ou_points(r, '半大投注', '半大結果'), axis=1) if '半大結果' in df_ko_matches.columns else 0
    ko_merged['淘汰賽總分'] = (
        ko_merged['盤口得分'] + ko_merged['晉級球隊得分'] + ko_merged['半場波膽得分'] + ko_merged['全場波膽得分'] +
        ko_merged['半全場得分'] + ko_merged['上半15分得分'] + ko_merged['下半15分得分'] +
        ko_merged['半場角球得分'] + ko_merged['全場角球得分'] + ko_merged['罰牌大細得分'] + ko_merged['大細波得分'] + ko_merged['半大得分']
    )
else:
    ko_merged = pd.DataFrame()
# 淘汰賽已完場場次
if not df_ko_matches.empty and '賽果分類' in df_ko_matches.columns:
    ko_played_matches = df_ko_matches[
        df_ko_matches['賽果分類'].notna() &
        (df_ko_matches['賽果分類'].astype(str).str.strip().isin(KO_PLAYED_STATUSES))
    ]['場次'].astype(str).str.strip().tolist()
else:
    ko_played_matches = []
ko_total_played = len(ko_played_matches)
def ko_calc_penalty(player_name):
    """淘汰賽漏賭扣分：完全冇落呢場注 -20（盤口-10 + 晉級球隊-10）"""
    if df_ko_bets.empty:
        return 0
    p_bets = df_ko_bets[df_ko_bets['人名'] == str(player_name).strip()]
    bet_matches = [m.replace(' ', '').strip() for m in p_bets['場次'].astype(str).tolist()] if not p_bets.empty else []
    ko_played_clean = [m.replace(' ', '').strip() for m in ko_played_matches]
    missed = ko_total_played - len([m for m in ko_played_clean if m in bet_matches])
    return missed * 20
def ko_get_champion_points(player_name):
    """奪冠球隊：中+100，錯0，未出冠軍前都係0"""
    if df_ko_champion.empty or ACTUAL_CHAMPION_TEAM is None:
        return 0
    p_pick = df_ko_champion[df_ko_champion['人名'] == str(player_name).strip()]
    if p_pick.empty:
        return 0
    picked_team = str(p_pick.iloc[0]['投注球隊']).strip()
    return 100 if picked_team == ACTUAL_CHAMPION_TEAM else 0
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
# 淘汰賽連中提示 + 中波膽標題提示
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
def get_latest_dan_hit():
    """搵返最新一次有人中波膽（半場波膽或全場波膽），直至有下一個人中波膽為止先會更新"""
    if ko_merged.empty:
        return None
    hits = []
    for _, r in ko_merged.iterrows():
        match_name = str(r['場次']).strip()
        order = ko_match_order_map.get(match_name, -1)
        half_bet = str(r.get('半場波膽投注', '')).strip()
        half_result = str(r.get('半場賽果分數', '')).strip()
        if half_bet not in ['', 'nan'] and half_result not in ['', 'nan', 'None'] and half_bet == half_result:
            hits.append((order, match_name, '半場', half_result, str(r['人名']).strip()))
        full_bet = str(r.get('全場波膽投注', '')).strip()
        full_result = str(r.get('全場賽果分數', '')).strip()
        if full_bet not in ['', 'nan'] and full_result not in ['', 'nan', 'None'] and full_bet == full_result:
            hits.append((order, match_name, '全場', full_result, str(r['人名']).strip()))
    if not hits:
        return None
    max_order = max(h[0] for h in hits)
    return [h for h in hits if h[0] == max_order]
latest_dan_hits = get_latest_dan_hit()
if latest_dan_hits:
    dan_lines = [f"恭喜 {player} 中咗 {match_name} 嘅 {half_or_full} {score} 波膽"
                 for (order, match_name, half_or_full, score, player) in latest_dan_hits]
    DAN_PLACEHOLDER.markdown("### 🎯 " + "　｜　".join(dan_lines))
# =========================================================
# 小組賽連中 / 走勢計算
# =========================================================
match_order_map = {str(r).strip(): i for i, r in enumerate(df_matches['場次'].tolist())}
def calc_current_streak(player_name):
    p_data = merged[merged['人名'] == str(player_name).strip()].copy()
    if p_data.empty:
        return 0
    p_data['_order'] = p_data['場次'].astype(str).str.strip().map(lambda x: match_order_map.get(x, -1))
    p_data['_result'] = p_data[target_res_col].astype(str).str.strip()
    valid = p_data[p_data['_result'].isin(['上盤', '下盤', '上盤贏半', '下盤贏半'])].sort_values('_order')
    if valid.empty:
        return 0
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
group_champion_name = df_scores.iloc[0]['人名'] if not df_scores.empty else ""
STREAK_PLACEHOLDER.markdown(f"### 🔥🔥🔥 恭喜 {group_champion_name} 成為小組賽冠軍 1️⃣！！！")
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
# 未開波場次
hk_tz = pytz.timezone('Asia/Hong_Kong')
now_hk = pd.Timestamp.now(tz=hk_tz)
unplayed = df_matches[df_matches[target_res_col].isna() | (df_matches[target_res_col].astype(str).str.strip() == '') | (df_matches[target_res_col].astype(str).str.strip() == 'nan')].copy()
if '開賽時間' in unplayed.columns:
    unplayed['_kickoff'] = pd.to_datetime(unplayed['開賽時間'], errors='coerce').dt.tz_localize(hk_tz, ambiguous='NaT', nonexistent='NaT')
    unplayed = unplayed[unplayed['_kickoff'].isna() | (unplayed['_kickoff'] > now_hk)]
# 顯示上次提交結果
if 'bet_msg' in st.session_state:
    msg_type, msg_text = st.session_state.pop('bet_msg')
    if msg_type == 'success':
        st.sidebar.success(msg_text)
    else:
        st.sidebar.error(msg_text)
# 小組賽落注（已關閉）
GROUP_STAGE_BETTING_OPEN = False
if GROUP_STAGE_BETTING_OPEN:
    st.sidebar.header("⚽ 手足落注")
    u = st.sidebar.selectbox("選擇名字", options=all_players, index=None)
    if unplayed.empty:
        st.sidebar.info("🚫 全部比賽已開波或完場，無得再落注。")
    elif not unplayed.empty:
        m = st.sidebar.selectbox("選擇場次", options=unplayed['場次'].tolist())
        match_row = df_matches[df_matches['場次'].astype(str).str.strip() == str(m).strip()]
        if not match_row.empty and '讓球球隊' in match_row.columns:
            handicap_team = str(match_row.iloc[0]['讓球球隊']).strip()
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
            # 搵返呢個人呢場波已經填咗嘅項目（用嚎決定表單顯示乜）
            existing_bet = None
            if ku is not None:
                df_ko_current_check = safe_load("KO_Bets", ko_bets_cols)
                if not df_ko_current_check.empty:
                    match_rows = df_ko_current_check[
                        (df_ko_current_check['人名'] == ku) & (df_ko_current_check['場次'] == km)
                    ]
                    if not match_rows.empty:
                        existing_bet = match_rows.iloc[0]
            def is_filled(col_name):
                """檢查呢個項目係咪已經填咗（有值）"""
                if existing_bet is None:
                    return False
                val = str(existing_bet.get(col_name, '')).strip()
                return val not in ['', 'nan', 'None']
            if existing_bet is not None:
                st.info("💡 你已經落咗部分注，已填項目唔會再顯示，可以補揀未填嘅項目。")
            with st.form("ko_bet_form", clear_on_submit=True):
                field_count = 0
                # 1. 盤口
                if not is_filled('盤口投注'):
                    field_count += 1
                    st.markdown(f"**{field_count}. 盤口（必投，唔投扣10分）**")
                    ko_handicap = st.radio("盤口", [f"上盤 {handicap_team}", f"下盤 {other_team}"], key="ko_handicap_radio", label_visibility="collapsed")
                    ko_handicap_val = "上盤" if ko_handicap.startswith("上盤") else "下盤"
                else:
                    ko_handicap_val = None
                # 2. 晉級球隊
                if not is_filled('晉級球隊投注'):
                    field_count += 1
                    st.markdown(f"**{field_count}. 晉級球隊（必揀，唔揀扣10分，中+10/錯-10）**")
                    ko_advance = st.radio("晉級球隊", [home_team, away_team], key="ko_advance_radio", label_visibility="collapsed")
                else:
                    ko_advance = None
                # 3. 半場波膽
                if not is_filled('半場波膽投注'):
                    field_count += 1
                    st.markdown(f"**{field_count}. 半場波膽（選擇性，中+30/錯-10）**")
                    half_score_options = ["未揀",
                                           "1:0", "2:0", "2:1", "3:0", "3:1", "3:2", "4:0", "4:1", "4:2", "4:3",
                                           "0:0", "1:1", "2:2", "3:3", "4:4",
                                           "0:1", "0:2", "1:2", "0:3", "1:3", "2:3", "0:4", "1:4", "2:4", "3:4"]
                    ko_half_score = st.selectbox("半場波膽", half_score_options, key="ko_half_score_sb", label_visibility="collapsed")
                else:
                    ko_half_score = None
                # 4. 全場波膽
                if not is_filled('全場波膽投注'):
                    field_count += 1
                    st.markdown(f"**{field_count}. 全場波膽（選擇性，中+50/錯-10）**")
                    full_score_options = ["未揀",
                                           "1:0", "2:0", "2:1", "3:0", "3:1", "3:2", "4:0", "4:1", "4:2", "4:3", "5:0", "5:1", "5:2", "5:3",
                                           "0:0", "1:1", "2:2", "3:3", "4:4",
                                           "0:1", "0:2", "1:2", "0:3", "1:3", "2:3", "0:4", "1:4", "2:4", "3:4", "0:5", "1:5", "2:5", "3:5", "4:5",
                                           "主其他", "和其他", "客其他"]
                    ko_full_score = st.selectbox("全場波膽", full_score_options, key="ko_full_score_sb", label_visibility="collapsed")
                else:
                    ko_full_score = None
                # 5. 半全場
                if not is_filled('半全場投注'):
                    field_count += 1
                    st.markdown(f"**{field_count}. 半全場（選擇性，中+20/錯-10）**")
                    htft_options = ["未揀", "主主", "主和", "主客", "和主", "和和", "和客", "客主", "客和", "客客"]
                    ko_htft = st.selectbox("半全場", htft_options, key="ko_htft_sb", label_visibility="collapsed")
                else:
                    ko_htft = None
                # 6. 上半頭15分
                if not is_filled('上半頭15分投注'):
                    field_count += 1
                    st.markdown(f"**{field_count}. 上半場頭15分鐘入球（選擇性，揀「是」中+30/錯-10，唔揀就唔計分）**")
                    ko_first15_1h = st.selectbox("上半頭15分", ["未揀", "是"], key="ko_first15_1h_sb", label_visibility="collapsed")
                else:
                    ko_first15_1h = None
                # 7. 下半頭15分
                if not is_filled('下半頭15分投注'):
                    field_count += 1
                    st.markdown(f"**{field_count}. 下半場頭15分鐘入球（選擇性，揀「是」中+30/錯-10，唔揀就唔計分）**")
                    ko_first15_2h = st.selectbox("下半頭15分", ["未揀", "是"], key="ko_first15_2h_sb", label_visibility="collapsed")
                else:
                    ko_first15_2h = None
                # 8. 半場角球
                if not is_filled('半場角球投注'):
                    field_count += 1
                    hc_corner_line = str(km_row.iloc[0].get('半場角球盤口', '')).strip() if not km_row.empty else ''
                    has_hc_line = hc_corner_line not in ['', 'nan', 'None']
                    st.markdown(f"**{field_count}. 半場角球 大細（選擇性，中+20/錯-10，可以走盤）**")
                    hc_corner_opts = ["未揀", f"大（大於 {hc_corner_line}）", f"細（細於 {hc_corner_line}）"] if has_hc_line else ["未揀", "大", "細"]
                    ko_hc_corner_raw = st.radio("半場角球", hc_corner_opts, key="ko_hc_corner_radio", label_visibility="collapsed")
                    ko_hc_corner = "未揀" if ko_hc_corner_raw == "未揀" else ("大" if ko_hc_corner_raw.startswith("大") else "細")
                else:
                    ko_hc_corner = None
                # 9. 全場角球
                if not is_filled('全場角球投注'):
                    field_count += 1
                    fc_corner_line = str(km_row.iloc[0].get('全場角球盤口', '')).strip() if not km_row.empty else ''
                    has_fc_line = fc_corner_line not in ['', 'nan', 'None']
                    st.markdown(f"**{field_count}. 全場角球 大細（選擇性，中+20/錯-10，可以走盤）**")
                    fc_corner_opts = ["未揀", f"大（大於 {fc_corner_line}）", f"細（細於 {fc_corner_line}）"] if has_fc_line else ["未揀", "大", "細"]
                    ko_fc_corner_raw = st.radio("全場角球", fc_corner_opts, key="ko_fc_corner_radio", label_visibility="collapsed")
                    ko_fc_corner = "未揀" if ko_fc_corner_raw == "未揀" else ("大" if ko_fc_corner_raw.startswith("大") else "細")
                else:
                    ko_fc_corner = None
                # 10. 罰牌大細
                if not is_filled('罰牌大細投注'):
                    field_count += 1
                    card_line = str(km_row.iloc[0].get('罰牌盤口', '')).strip() if not km_row.empty else ''
                    has_card_line = card_line not in ['', 'nan', 'None']
                    st.markdown(f"**{field_count}. 罰牌大細（選擇性，中+20/錯-10，可以走盤）**")
                    card_opts = ["未揀", f"大（大於 {card_line}）", f"細（細於 {card_line}）"] if has_card_line else ["未揀", "大", "細"]
                    ko_card_ou_raw = st.radio("罰牌大細", card_opts, key="ko_card_ou_radio", label_visibility="collapsed")
                    ko_card_ou = "未揀" if ko_card_ou_raw == "未揀" else ("大" if ko_card_ou_raw.startswith("大") else "細")
                else:
                    ko_card_ou = None
                # 11. 大細波
                if not is_filled('大細波投注'):
                    field_count += 1
                    ou_line_val = str(km_row.iloc[0].get('大細波盤口', '')).strip() if not km_row.empty else ''
                    has_ou_line = ou_line_val not in ['', 'nan', 'None']
                    st.markdown(f"**{field_count}. 大細波（選擇性，中+20/錯-10，可以走盤）**")
                    goal_ou_opts = ["未揀", f"大（大於 {ou_line_val}）", f"細（細於 {ou_line_val}）"] if has_ou_line else ["未揀", "大", "細"]
                    ko_goal_ou_raw = st.radio("大細波", goal_ou_opts, key="ko_goal_ou_radio", label_visibility="collapsed")
                    ko_goal_ou = "未揀" if ko_goal_ou_raw == "未揀" else ("大" if ko_goal_ou_raw.startswith("大") else "細")
                else:
                    ko_goal_ou = None
                # 12. 半大
                if not is_filled('半大投注'):
                    field_count += 1
                    half_ou_line_val = str(km_row.iloc[0].get('半大盤口', '')).strip() if not km_row.empty else ''
                    has_half_ou_line = half_ou_line_val not in ['', 'nan', 'None']
                    st.markdown(f"**{field_count}. 半大（選擇性，中+20/錯-10，可以走盤）**")
                    half_ou_opts = ["未揀", f"大（大於 {half_ou_line_val}）", f"細（細於 {half_ou_line_val}）"] if has_half_ou_line else ["未揀", "大", "細"]
                    ko_half_ou_raw = st.radio("半大", half_ou_opts, key="ko_half_ou_radio", label_visibility="collapsed")
                    ko_half_ou = "未揀" if ko_half_ou_raw == "未揀" else ("大" if ko_half_ou_raw.startswith("大") else "細")
                else:
                    ko_half_ou = None
                if field_count == 0:
                    st.success("✅ 你已經填咗全部項目喇！")
                if st.form_submit_button("🔥 提交淘汰賽投注"):
                    if ku is None:
                        st.session_state['ko_bet_msg'] = ('error', "⚠️ 必須先選擇名字！")
                    elif field_count == 0:
                        st.session_state['ko_bet_msg'] = ('error', "❌ 你已經填咗全部項目，冇得再改！")
                    else:
                        params = {'sheet': 'KO_Bets', 'name': ku, 'match': km}
                        if ko_handicap_val is not None:
                            params['盤口投注'] = ko_handicap_val
                        if ko_advance is not None:
                            params['晉級球隊投注'] = ko_advance
                        if ko_half_score is not None:
                            params['半場波膽投注'] = '' if ko_half_score == '未揀' else ko_half_score
                        if ko_full_score is not None:
                            params['全場波膽投注'] = '' if ko_full_score == '未揀' else ko_full_score
                        if ko_htft is not None:
                            params['半全場投注'] = '' if ko_htft == '未揀' else ko_htft
                        if ko_first15_1h is not None:
                            params['上半頭15分投注'] = '' if ko_first15_1h == '未揀' else ko_first15_1h
                        if ko_first15_2h is not None:
                            params['下半頭15分投注'] = '' if ko_first15_2h == '未揀' else ko_first15_2h
                        if ko_hc_corner is not None:
                            params['半場角球投注'] = '' if ko_hc_corner == '未揀' else ko_hc_corner
                        if ko_fc_corner is not None:
                            params['全場角球投注'] = '' if ko_fc_corner == '未揀' else ko_fc_corner
                        if ko_card_ou is not None:
                            params['罰牌大細投注'] = '' if ko_card_ou == '未揀' else ko_card_ou
                        if ko_goal_ou is not None:
                            params['大細波投注'] = '' if ko_goal_ou == '未揀' else ko_goal_ou
                        if ko_half_ou is not None:
                            params['半大投注'] = '' if ko_half_ou == '未揀' else ko_half_ou
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
with st.sidebar.expander("👑 奪冠球隊", expanded=False):
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
        if ACTUAL_CHAMPION_TEAM:
            st.caption(f"👑 冠軍隊：{ACTUAL_CHAMPION_TEAM}（已計入奪冠球隊得分）")
        st.caption("💡 淘汰賽計分：盤口±10（贏半±5，必投，完全唔落注扣-20=盤口10+晉級10）、晉級球隊中+10/錯-10（必揀，唔揀扣10，只有KO_Matches打咗「啟動晉級計分=是」嘅場次先會計分）、半場波膽中+30、全場波膽中+50、半全場中+20、上/下半頭15分入球中各+30，半場角球/全場角球/罰牌大細/大細波/半大呢5個新項目：選擇性、中+20、錯-10、可以走盤（走盤=0），以上選擇性項目錯咗一律-10。奪冠球隊中+100（一次性，鎖死）。")
        if not df_ko_champion.empty:
            st.divider()
            st.subheader("👑 奪冠球隊投注紀錄")
            champ_display_cols = [c for c in ['人名', '投注球隊'] if c in df_ko_champion.columns]
            st.dataframe(df_ko_champion[champ_display_cols], hide_index=True, use_container_width=True)
with tab1:
    st.subheader("🏆 燈閪盃排名（小組賽 + 淘汰賽）")
    df_scores_display = df_scores[['排名', '人名', '最終得分']].rename(columns={'最終得分': '小組賽得分', '排名': '小組賽排名'})
    ko_score_map = dict(zip(df_ko_scores['人名'], df_ko_scores['淘汰賽得分'])) if not df_ko_scores.empty else {}
    df_scores_display['淘汰賽得分'] = df_scores_display['人名'].map(lambda p: ko_score_map.get(p, 0))
    df_scores_display['總分'] = df_scores_display['小組賽得分'] + df_scores_display['淘汰賽得分']
    df_scores_display['排名'] = df_scores_display['總分'].rank(method='min', ascending=False).astype(int)
    df_scores_display = df_scores_display.sort_values('排名')
    df_scores_display['走勢'] = df_scores_display['人名'].apply(calc_form_streak)
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
    sched_inner1, sched_inner2 = st.tabs(["🏆 淘汰賽賽程", "⚽ 小組賽賽程"])
    with sched_inner1:
        st.subheader("🏆 淘汰賽對賽表")
        def get_match_by_teams(team_a, team_b, round_name=None):
            """根據隊名（同可選輪次）搵返 KO_Matches 嘅資料"""
            if df_ko_matches.empty:
                return None
            for _, row in df_ko_matches.iterrows():
                m_str = str(row['場次']).strip()
                if team_a in m_str and team_b in m_str:
                    if round_name is None or str(row.get('輪次', '')).strip() == round_name:
                        return row
            return None
        def get_match_winner(match_row):
            """直接讀取 KO_Matches 嘅「晉級球隊」欄（管理員手動填），冇填就未有結果"""
            if match_row is None:
                return None
            winner = str(match_row.get('晉級球隊', '')).strip()
            if winner in ['', 'nan', 'None']:
                return None
            return winner
        def get_match_kickoff(match_row):
            if match_row is None:
                return None
            k = str(match_row.get('開賽時間', '')).strip()
            return None if k in ['', 'nan', 'None'] else k
        # 32強左右對位（跟世界盃官方對賽表結構）
        r32_left = [
            ("德國", "巴拉圭"), ("法國", "瑞典"),
            ("南非", "加拿大"), ("荷蘭", "摩洛哥"),
            ("葡萄牙", "克羅地亞"), ("西班牙", "奧地利"),
            ("美國", "波斯尼亞"), ("比利時", "塞內加爾"),
        ]
        r32_right = [
            ("巴西", "日本"), ("科特迪瓦", "挪威"),
            ("墨西哥", "厄瓜多爾"), ("英格蘭", "剛果民主共和國"),
            ("阿根廷", "佛得角"), ("澳洲", "埃及"),
            ("瑞士", "阿爾及利亞"), ("哥倫比亞", "加納"),
        ]
        def winner_or_placeholder(team_a, team_b, round_name):
            m = get_match_by_teams(team_a, team_b, round_name)
            w = get_match_winner(m)
            return w if w else "待定"
        # 計算16強配對（由32強勝方推算，如果未有結果就顯示「待定」）
        def next_round_pairs(prev_pairs, round_name):
            winners = [winner_or_placeholder(a, b, round_name) for a, b in prev_pairs]
            return [(winners[i], winners[i+1]) for i in range(0, len(winners), 2)]
        r16_left = next_round_pairs(r32_left, "32強")
        r16_right = next_round_pairs(r32_right, "32強")
        r8_left = next_round_pairs(r16_left, "16強")
        r8_right = next_round_pairs(r16_right, "16強")
        r4_left = next_round_pairs(r8_left, "8強")
        r4_right = next_round_pairs(r8_right, "8強")
        final_pair = next_round_pairs(r4_left + r4_right, "4強")[0] if (r4_left + r4_right) else ("待定", "待定")
        # ===== 畫 SVG bracket =====
        def esc(s):
            return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        def box_svg(x, y, w, h, team_a, team_b, round_name, is_final=False):
            m = get_match_by_teams(team_a, team_b, round_name) if team_a != "待定" and team_b != "待定" else None
            winner = get_match_winner(m)
            kickoff = get_match_kickoff(m)
            fill = "#1a2332" if not is_final else "#2a1f0a"
            stroke = "#3a4456"
            mid_y = y + h / 2
            label_a = esc(team_a) + (" 🏆" if winner == team_a else "")
            label_b = esc(team_b) + (" 🏆" if winner == team_b else "")
            color_a = "#f4d35e" if winner == team_a else "#e8e8e8"
            color_b = "#f4d35e" if winner == team_b else "#e8e8e8"
            time_label = f'<text x="{x+w/2}" y="{y-4}" text-anchor="middle" font-size="9" fill="#888">{esc(kickoff) if kickoff else ""}</text>' if kickoff else ""
            return f'''
            <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1"/>
            <line x1="{x}" y1="{mid_y}" x2="{x+w}" y2="{mid_y}" stroke="{stroke}" stroke-width="0.5"/>
            <text x="{x+8}" y="{y+h*0.32}" font-size="11" fill="{color_a}">{label_a}</text>
            <text x="{x+8}" y="{y+h*0.78}" font-size="11" fill="{color_b}">{label_b}</text>
            {time_label}
            '''
        # 佈局參數
        BOX_W, BOX_H = 150, 34
        UNIT = 50  # 32強每場之間嘅垂直間距
        def y_center(round_level, index):
            """round_level: 0=32強(8場), 1=16強(4場), 2=8強(2場), 3=4強(1場)
               index: 嗰一輪第幾場（由0開始）
               回傳該場波 box 嘅中心 Y 座標"""
            spacing = UNIT * (2 ** round_level)
            offset = spacing / 2 - UNIT / 2 if round_level > 0 else 0
            return 20 + BOX_H/2 + index * spacing + offset
        svg_h = int(y_center(0, 7) + BOX_H/2 + 30)
        svg_parts = []
        # X座標：32強(左) -> 16強(左) -> 8強(左) -> 4強(左) -> 決賽 <- 4強(右) <- 8強(右) <- 16強(右) <- 32強(右)
        x32_l, x16_l, x8_l, x4_l = 10, 190, 370, 550
        x_final = 730
        x4_r, x8_r, x16_r, x32_r = 910, 1090, 1270, 1450
        total_w = x32_r + BOX_W + 20
        def put_box(x, round_level, index, team_a, team_b, round_name, is_final=False):
            yc = y_center(round_level, index)
            y = yc - BOX_H/2
            svg_parts.append(box_svg(x, y, BOX_W, BOX_H, team_a, team_b, round_name, is_final))
            return yc
        # 32強左/右 (8場 each)
        for i, (a, b) in enumerate(r32_left):
            put_box(x32_l, 0, i, a, b, "32強")
        for i, (a, b) in enumerate(r32_right):
            put_box(x32_r, 0, i, a, b, "32強")
        # 16強左/右 (4場 each)
        for i, (a, b) in enumerate(r16_left):
            put_box(x16_l, 1, i, a, b, "16強")
        for i, (a, b) in enumerate(r16_right):
            put_box(x16_r, 1, i, a, b, "16強")
        # 8強左/右 (2場 each)
        for i, (a, b) in enumerate(r8_left):
            put_box(x8_l, 2, i, a, b, "8強")
        for i, (a, b) in enumerate(r8_right):
            put_box(x8_r, 2, i, a, b, "8強")
        # 4強左/右 (1場 each)
        if r4_left:
            put_box(x4_l, 3, 0, r4_left[0][0], r4_left[0][1], "4強")
        if r4_right:
            put_box(x4_r, 3, 0, r4_right[0][0], r4_right[0][1], "4強")
        # 決賽
        y_final_mid = y_center(3, 0)
        svg_parts.append(box_svg(x_final, y_final_mid - BOX_H/2, BOX_W, BOX_H, final_pair[0], final_pair[1], "決賽", is_final=True))
        svg_parts.append(f'<text x="{x_final+BOX_W/2}" y="{y_final_mid-BOX_H/2-10}" text-anchor="middle" font-size="11" fill="#f4d35e">🏆 決賽 7/20(一) 03:00</text>')
        # 連線
        def connector(x1, y1, x2, y2):
            mid_x = (x1 + x2) / 2
            return f'<path d="M{x1},{y1} L{mid_x},{y1} L{mid_x},{y2} L{x2},{y2}" fill="none" stroke="#3a4456" stroke-width="1"/>'
        # 32強 -> 16強
        for i in range(8):
            y_src = y_center(0, i)
            y_dst = y_center(1, i // 2)
            svg_parts.append(connector(x32_l + BOX_W, y_src, x16_l, y_dst))
            svg_parts.append(connector(x32_r, y_src, x16_r + BOX_W, y_dst))
        # 16強 -> 8強
        for i in range(4):
            y_src = y_center(1, i)
            y_dst = y_center(2, i // 2)
            svg_parts.append(connector(x16_l + BOX_W, y_src, x8_l, y_dst))
            svg_parts.append(connector(x16_r, y_src, x8_r + BOX_W, y_dst))
        # 8強 -> 4強
        for i in range(2):
            y_src = y_center(2, i)
            y_dst = y_center(3, 0)
            svg_parts.append(connector(x8_l + BOX_W, y_src, x4_l, y_dst))
            svg_parts.append(connector(x8_r, y_src, x4_r + BOX_W, y_dst))
        # 4強 -> 決賽
        svg_parts.append(connector(x4_l + BOX_W, y_final_mid, x_final, y_final_mid))
        svg_parts.append(connector(x4_r, y_final_mid, x_final + BOX_W, y_final_mid))
        svg_content = "".join(svg_parts)
        full_html = f'''<!DOCTYPE html>
<html>
<head>
<style>
  body {{ margin:0; padding:16px; background:#0d1117; font-family: -apple-system, sans-serif; overflow-x:auto; }}
  svg {{ display:block; }}
</style>
</head>
<body>
<svg viewBox="0 0 {total_w} {svg_h}" width="{total_w}" height="{svg_h}">{svg_content}</svg>
</body>
</html>'''
        components.html(full_html, height=svg_h + 60, scrolling=True)
        st.caption("💡 32強對賽表，🏆代表已晉級（直接根據 KO_Matches 嘅「晉級球隊」欄顯示，管理員手動填晉級球隊即會反映）。輪次配對需要 KO_Matches 填入對應隊名先會自動連接（例：16強要填「德國 vs 法國」呢類由32強勝方組成嘅場次）。決賽：7月20日(一) 03:00　季軍戰：7月19日(日) 05:00")
        st.divider()
        st.subheader("📋 淘汰賽詳細賽程")
        if df_ko_matches.empty:
            st.info("淘汰賽賽程未準備好。")
        else:
            ko_display_cols = [c for c in ['場次', '輪次', '讓球球隊', '盤口', '開賽時間', '全場賽果分數', '半場賽果分數', '賽果分類',
                                            '半全場結果', '上半頭15分入球', '下半頭15分入球',
                                            '半場角球結果', '全場角球結果', '罰牌大細結果', '大細波結果', '半大結果'] if c in df_ko_matches.columns]
            st.dataframe(df_ko_matches[ko_display_cols], hide_index=True, use_container_width=True)
    with sched_inner2:
        st.subheader("⚽ 比賽賽程與賽果")
        display_cols = [c for c in ['場次', '讓球球隊', '盤口', '開賽時間', '賽果分數', '賽果分類', '結果分類'] if c in df_matches.columns]
        st.dataframe(df_matches[display_cols], hide_index=True, use_container_width=True)
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
            ko_bet_display_cols = [c for c in ['人名', '盤口投注', '晉級球隊投注', '半場波膽投注', '全場波膽投注', '半全場投注',
                                                '上半頭15分投注', '下半頭15分投注',
                                                '半場角球投注', '全場角球投注', '罰牌大細投注', '大細波投注', '半大投注'] if c in df_ko_bets.columns]
            ko_bet_view_df = df_ko_bets[df_ko_bets['場次'] == ko_sel_match][ko_bet_display_cols].copy()
            # 確保空白顯示為「-」而唔係 NaN/空白睇唔到
            for c in ['半場波膽投注', '全場波膽投注', '半全場投注', '上半頭15分投注', '下半頭15分投注',
                      '半場角球投注', '全場角球投注', '罰牌大細投注', '大細波投注', '半大投注']:
                if c in ko_bet_view_df.columns:
                    ko_bet_view_df[c] = ko_bet_view_df[c].apply(lambda x: '-' if str(x).strip() in ['', 'nan', 'None'] else x)
            st.dataframe(ko_bet_view_df, hide_index=True, use_container_width=True)
        with ko_inner2:
            ko_upcoming = ko_unplayed['場次'].iloc[0] if not ko_unplayed.empty else None
            ko_stats = []
            for p in all_players:
                p_data = ko_merged[ko_merged['人名'] == p] if not ko_merged.empty else pd.DataFrame()
                valid = p_data[p_data['賽果分類'].astype(str).str.strip().isin(KO_PLAYED_STATUSES)] if not p_data.empty and '賽果分類' in p_data.columns else pd.DataFrame()
                wins = len(valid[valid['盤口得分'] > 0]) if not valid.empty else 0
                total = len(valid)
                if not df_ko_bets.empty and '盤口投注' in df_ko_bets.columns and ko_upcoming is not None:
                    ko_upcoming_clean = str(ko_upcoming).replace(' ', '').strip()
                    next_bet = df_ko_bets[
                        (df_ko_bets['人名'] == p) &
                        (df_ko_bets['場次'].astype(str).str.replace(' ', '').str.strip() == ko_upcoming_clean)
                    ]['盤口投注'].values
                else:
                    next_bet = []
                ko_stats.append({
                    '人名': p,
                    '投注場次': total,
                    '勝場': wins,
                    '勝率': f"{(wins/total*100):.1f}%" if total > 0 else "0%",
                    '_sort': (wins/total*100) if total > 0 else 0,
                    '下一場心水': next_bet[0] if len(next_bet) > 0 else "未落注"
                })
            ko_df_stats = pd.DataFrame(ko_stats)
            ko_df_stats['勝率排名'] = ko_df_stats['_sort'].rank(method='min', ascending=False).astype(int)
            ko_df_stats = ko_df_stats.sort_values('勝率排名').reset_index(drop=True)
            ko_df_stats = ko_df_stats[['勝率排名', '人名', '投注場次', '勝場', '勝率', '下一場心水']]
            st.dataframe(ko_df_stats, hide_index=True, use_container_width=True)
            st.caption("💡 呢個勝率只計「盤口」項目（必投項目），唔包括半場波膽/全場波膽/半全場/頭15分入球/半場角球/全場角球/罰牌大細/大細波/半大。")
        with ko_inner3:
            ko_detail_display = df_ko_scores.copy()
            ko_detail_display['漏賭扣分'] = ko_detail_display['人名'].apply(ko_calc_penalty)
            ko_detail_display['奪冠加分'] = ko_detail_display['人名'].apply(ko_get_champion_points)
            ko_detail_display = ko_detail_display[['排名', '人名', '淘汰賽得分', '漏賭扣分', '奪冠加分']]
            st.dataframe(ko_detail_display, hide_index=True, use_container_width=True)
            st.caption("💡 淘汰賽得分已扣除漏賭扣分（每場盤口冇落注 -20）同計入奪冠球隊分數（中+100）。")
with tab_mix:
    st.subheader("📊 小組賽詳情")
    inner1, inner2, inner3 = st.tabs(["📋 下注紀錄", "📊 勝率與心水", "📈 詳細統計"])
    with inner1:
        all_bet_matches = df_bets['場次'].unique().tolist()
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
                '勝場': wins,
                '勝率': f"{(wins/total*100):.1f}%" if total > 0 else "0%",
                '_sort': (wins/total*100) if total > 0 else 0,
                '下一場心水': next_bet[0] if len(next_bet) > 0 else "未落注"
            })
        df_stats = pd.DataFrame(stats)
        df_stats['勝率排名'] = df_stats['_sort'].rank(method='min', ascending=False).astype(int)
        df_stats = df_stats.sort_values('勝率排名').reset_index(drop=True)
        df_stats = df_stats[['勝率排名', '人名', '投注場次', '勝場', '勝率', '下一場心水']]
        st.dataframe(df_stats, hide_index=True, use_container_width=True)
    with inner3:
        if not df_bets.empty and not df_matches.empty:
            df_bets_clean = df_bets.copy()
            df_bets_clean['人名'] = df_bets_clean['人名'].astype(str).str.strip()
            df_bets_clean['乾淨場次'] = df_bets_clean['場次'].astype(str).str.replace(' ', '').str.strip()
            df_matches_clean = df_matches.copy()
            df_matches_clean['乾淨場次'] = df_matches_clean['場次'].astype(str).str.replace(' ', '').str.strip()
            played_matches_df = df_matches_clean[
                df_matches_clean[target_res_col].notna() &
                (df_matches_clean[target_res_col].astype(str).str.strip() != '') &
                (df_matches_clean[target_res_col].astype(str).str.strip() != 'nan')
            ]
            played_matches_clean = played_matches_df['乾淨場次'].tolist()
            total_played_count = len(played_matches_clean)
            merged2 = df_bets_clean.merge(df_matches_clean[['乾淨場次', target_res_col]], on='乾淨場次', how='left')
            merged2['得分'] = merged2.apply(get_points, axis=1)
            df_player_scores = merged2.groupby('人名')['得分'].sum().reset_index()
            for p in all_players:
                p_clean = str(p).strip()
                if p_clean not in df_player_scores['人名'].tolist():
                    df_player_scores = pd.concat([df_player_scores, pd.DataFrame([{'人名': p_clean, '得分': 0}])], ignore_index=True)
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
                def ko_get_ou_check_mark(score, bet_val, result_val):
                    """大細類新項目專用核對（會顯示走盤）"""
                    bet_str = str(bet_val).strip()
                    result_str = str(result_val).strip()
                    if bet_str in ['', 'nan']:
                        return "➖ 未落注"
                    if result_str in ['', 'nan', 'None']:
                        return "⏳ 未開波"
                    if result_str == '走盤':
                        return "➖ 走盤"
                    if score > 0:
                        return "✅ 中"
                    elif score < 0:
                        return "❌ 唔中"
                    return "➖"
                rows = []
                for _, r in ko_p_data.iterrows():
                    handicap_result = str(r.get('賽果分類', '')).strip()
                    has_handicap_result = handicap_result in KO_PLAYED_STATUSES
                    has_full_score = str(r.get('全場賽果分數', '')).strip() not in ['', 'nan', 'None']
                    rows.append({
                        '場次': r['場次'],
                        '盤口投注': r.get('盤口投注', ''),
                        '盤口結果': handicap_result if has_handicap_result else '未開波',
                        '盤口': ko_get_check_mark(r.get('盤口得分', 0), str(r.get('盤口投注', '')).strip() not in ['', 'nan'], has_handicap_result),
                        '晉級球隊投注': r.get('晉級球隊投注', ''),
                        '晉級球隊': ko_get_check_mark(r.get('晉級球隊得分', 0), str(r.get('晉級球隊投注', '')).strip() not in ['', 'nan'], has_full_score),
                        '半場波膽': ko_get_check_mark(r.get('半場波膽得分', 0), str(r.get('半場波膽投注', '')).strip() not in ['', 'nan'], str(r.get('半場賽果分數', '')).strip() not in ['', 'nan', 'None']),
                        '全場波膽': ko_get_check_mark(r.get('全場波膽得分', 0), str(r.get('全場波膽投注', '')).strip() not in ['', 'nan'], has_full_score),
                        '半全場': ko_get_check_mark(r.get('半全場得分', 0), str(r.get('半全場投注', '')).strip() not in ['', 'nan'], str(r.get('半全場結果', '')).strip() not in ['', 'nan', 'None']),
                        '上半15分': ko_get_check_mark(r.get('上半15分得分', 0), str(r.get('上半頭15分投注', '')).strip() not in ['', 'nan'], str(r.get('上半頭15分入球', '')).strip() not in ['', 'nan', 'None']),
                        '下半15分': ko_get_check_mark(r.get('下半15分得分', 0), str(r.get('下半頭15分投注', '')).strip() not in ['', 'nan'], str(r.get('下半頭15分入球', '')).strip() not in ['', 'nan', 'None']),
                        '半場角球': ko_get_ou_check_mark(r.get('半場角球得分', 0), r.get('半場角球投注', ''), r.get('半場角球結果', '')),
                        '全場角球': ko_get_ou_check_mark(r.get('全場角球得分', 0), r.get('全場角球投注', ''), r.get('全場角球結果', '')),
                        '罰牌大細': ko_get_ou_check_mark(r.get('罰牌大細得分', 0), r.get('罰牌大細投注', ''), r.get('罰牌大細結果', '')),
                        '大細波': ko_get_ou_check_mark(r.get('大細波得分', 0), r.get('大細波投注', ''), r.get('大細波結果', '')),
                        '半大': ko_get_ou_check_mark(r.get('半大得分', 0), r.get('半大投注', ''), r.get('半大結果', '')),
                        '本場總分': r.get('淘汰賽總分', 0),
                    })
                ko_display_df = pd.DataFrame(rows)
                ko_display_df['_order'] = ko_display_df['場次'].map(lambda x: ko_match_order_map.get(str(x).strip(), 999))
                ko_display_df = ko_display_df.sort_values('_order').drop(columns=['_order']).reset_index(drop=True)
                st.dataframe(ko_display_df, hide_index=True, use_container_width=True)
                champ_pick = df_ko_champion[df_ko_champion['人名'] == ko_check_player] if not df_ko_champion.empty else pd.DataFrame()
                champ_text = champ_pick.iloc[0]['投注球隊'] if not champ_pick.empty else "未落注"
                champ_pts = ko_get_champion_points(ko_check_player)
                st.caption(f"👑 奪冠球隊投注：{champ_text}（{'✅ 中 +100' if champ_pts > 0 else '未中或未開出'}）")
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
    played_order = df_matches[
        df_matches[target_res_col].notna() &
        (df_matches[target_res_col].astype(str).str.strip() != '') &
        (df_matches[target_res_col].astype(str).str.strip() != 'nan')
    ]['場次'].astype(str).str.strip().tolist()
    if not played_order:
        st.info("暫時未有完場數據，未能繪製走勢圖。")
    else:
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

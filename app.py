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

# 數據合併
df_bets['乾淨場次'] = df_bets['場次'].astype(str).str.replace(' ', '').str.strip()
df_matches['乾淨場次'] = df_matches['場次'].astype(str).str.replace(' ', '').str.strip()
merged = df_bets.merge(df_matches[['乾淨場次', target_res_col, '讓球球隊', '盤口']], on='乾淨場次', how='left', suffixes=('', '_match'))
merged['得分'] = merged.apply(get_points, axis=1)

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

# 未開波場次
unplayed = df_matches[df_matches[target_res_col].isna() | (df_matches[target_res_col].astype(str).str.strip() == '') | (df_matches[target_res_col].astype(str).str.strip() == 'nan')]

# 側邊欄落注
st.sidebar.header("⚽ 手足落注")
u = st.sidebar.selectbox("選擇名字", options=all_players, index=None)
if not unplayed.empty:
    m = st.sidebar.selectbox("選擇場次", options=unplayed['場次'].tolist())

    # 搵到呢場嘅盤口數字
    match_row = df_matches[df_matches['場次'].astype(str).str.strip() == str(m).strip()]
    if not match_row.empty and '盤口' in match_row.columns:
        handicap_val = str(match_row.iloc[0]['盤口']).strip()
        upper_label = f"上盤 ({handicap_val})"
        lower_label = "下盤"
    else:
        upper_label = "上盤"
        lower_label = "下盤"

    with st.sidebar.form("bet_form", clear_on_submit=True):
        b_raw = st.radio("盤口", [upper_label, lower_label])
        b = "上盤" if b_raw == upper_label else "下盤"
        if st.form_submit_button("🔥 提交"):
            if u is None:
                st.sidebar.error("⚠️ 必須先選擇名字！")
            else:
                df_current = load_data("FinalBets")
                if not df_current[(df_current['人名'] == u) & (df_current['場次'] == m)].empty:
                    st.sidebar.error("❌ 呢場你投過喇，唔准改！")
                else:
                    resp = requests.get(GAS_URL, params={'name': u, 'match': m, 'bet': b})
                    if resp.status_code == 200:
                        st.sidebar.success(f"✅ 已成功下注！{u} 投 {b}")
                    else:
                        st.sidebar.error("系統繁忙，請重試")
                    st.rerun()

# 分頁顯示
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏆 總積分排名", "⚽ 賽程", "📋 下注紀錄", "📊 勝率與心水", "📈 詳細統計"])

with tab1:
    st.subheader("🏆 燈閪盃排名")
    df_scores_display = df_scores[['排名', '人名', '最終得分']].rename(columns={'最終得分': '得分'})
    st.dataframe(df_scores_display, hide_index=True, use_container_width=True)

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

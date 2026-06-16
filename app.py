import streamlit as st
import pandas as pd
import requests
import urllib.parse
import pytz

# 設定
SHEET_ID = "1ZkA6GA8JXs2oCh2rNSr_4XA7HNuxBdUjeZF4y-UyBh0"
GAS_URL = "https://script.google.com/macros/s/AKfycby5-mVhmT5qlhTj3i5S-vxNxERhxC7xQnwkJ9tlNnRRmzMRkeNoGbdWHBdJU-zuckv1Xw/exec"

st.set_page_config(layout="wide", page_title="燈閪盃系統")

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

# 核心計分
def get_points(row):
    user_choice = str(row.get('盤口', row.get('選擇', row.get('投注', '')))).strip()
    match_result = str(row.get(target_res_col, '')).strip()
    if match_result in ['未開賽/進行中', '未開賽', '進行中', 'None', '', 'nan']: return 0
    
    val = 0
    if '上盤' in match_result: val = 10 if '上盤' in user_choice else -10
    if '下盤' in match_result: val = 10 if '下盤' in user_choice else -10
    if '贏半' in match_result: val = val / 2
    return val if '走盤' not in match_result else 0

# 數據合併
df_bets['乾淨場次'] = df_bets['場次'].astype(str).str.replace(' ', '').str.strip()
df_matches['乾淨場次'] = df_matches['場次'].astype(str).str.replace(' ', '').str.strip()
merged = df_bets.merge(df_matches[['乾淨場次', target_res_col, '讓球球隊', '盤口']], on='乾淨場次', how='left', suffixes=('', '_match'))
merged['得分'] = merged.apply(get_points, axis=1)

# 1. 排名邏輯（並列處理）
df_scores = merged.groupby('人名')['得分'].sum().reset_index()
for p in all_players:
    if p not in df_scores['人名'].values:
        df_scores = pd.concat([df_scores, pd.DataFrame([{'人名': p, '得分': 0}])])
df_scores['排名'] = df_scores['得分'].rank(method='min', ascending=False).astype(int)
df_scores = df_scores.sort_values('排名')

# 側邊欄落注
st.sidebar.header("⚽ 手足落注")
u = st.sidebar.selectbox("選擇名字", options=all_players, index=None)
unplayed = df_matches[df_matches[target_res_col].isna() | (df_matches[target_res_col].astype(str).str.strip() == '')]
if not unplayed.empty:
    m = st.sidebar.selectbox("選擇場次", options=unplayed['場次'].tolist())
    with st.sidebar.form("bet_form", clear_on_submit=True):
        b = st.radio("盤口", ["上盤", "下盤"])
        if st.form_submit_button("提交"):
            requests.get(GAS_URL, params={'name': u, 'match': m, 'bet': b})
            st.rerun()

# 分頁顯示
tab1, tab2, tab3, tab4 = st.tabs(["🏆 總積分排名", "⚽ 賽程", "📋 下注紀錄", "📊 勝率與心水"])

with tab1:
    st.dataframe(df_scores[['排名', '人名', '得分']], hide_index=True, use_container_width=True)

with tab2:
    st.dataframe(df_matches, hide_index=True)

with tab3:
    sel_match = st.selectbox("查看場次", options=df_bets['場次'].unique())
    st.dataframe(df_bets[df_bets['場次'] == sel_match][['人名', '盤口']], hide_index=True)

with tab4:
    # 2. 勝率與心水統計
    upcoming = unplayed['場次'].iloc[0] if not unplayed.empty else None
    stats = []
    for p in all_players:
        p_data = merged[merged['人名'] == p]
        valid = p_data[p_data[target_res_col].notna() & (p_data[target_res_col] != '走盤')]
        wins = len(valid[valid['得分'] > 0])
        total = len(valid)
        next_bet = df_bets[(df_bets['人名'] == p) & (df_bets['場次'] == upcoming)]['盤口'].values
        stats.append({
            '人名': p, '勝率': f"{(wins/total*100):.1f}%" if total > 0 else "0%",
            '下一場心水': next_bet[0] if len(next_bet) > 0 else "未落注"
        })
    df_stats = pd.DataFrame(stats)
    df_stats['勝率排名'] = df_stats['勝率'].rank(method='min', ascending=False).astype(int)
    st.dataframe(df_stats.sort_values('勝率排名'), hide_index=True, use_container_width=True)

import streamlit as st
import pandas as pd
import requests
import urllib.parse

st.set_page_config(layout="wide", page_title="燈閪盃系統")

# --- 讀取資料並自動處理欄位空格 ---
@st.cache_data(ttl=0)
def load_data(sheet):
    url = f"https://docs.google.com/spreadsheets/d/1ZkA6GA8JXs2oCh2rNSr_4XA7HNuxBdUjeZF4y-UyBh0/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(sheet)}"
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip() # 處理欄位頭尾空格
    return df

df_matches = load_data("Matches")
df_bets = load_data("FinalBets")
df_players = load_data("Players")
all_players = [str(x).strip() for x in df_players["人名"].dropna().tolist()]

# 自動尋找目標欄位
def get_col(df, options):
    for o in options:
        if o in df.columns: return o
    return None

res_col = get_col(df_matches, ['結果分類', '賽果分類'])
bet_col = get_col(df_bets, ['盤口', '投注', '選擇'])

# --- 計分邏輯 ---
def get_points(row):
    choice = str(row.get(bet_col, '')).strip()
    res = str(row.get(res_col, '')).strip()
    if res in ['未開賽/進行中', '未開賽', '進行中', 'nan', '']: return 0
    val = 0
    if '上盤' in res: val = 10 if '上盤' in choice else -10
    if '下盤' in res: val = 10 if '下盤' in choice else -10
    if '贏半' in res: val = val / 2
    return val if '走盤' not in res else 0

# --- 數據準備 ---
df_bets['乾淨場次'] = df_bets['場次'].astype(str).str.replace(' ', '').str.strip()
df_matches['乾淨場次'] = df_matches['場次'].astype(str).str.replace(' ', '').str.strip()
merged = df_bets.merge(df_matches[['乾淨場次', res_col]], on='乾淨場次', how='left')
merged['得分'] = merged.apply(get_points, axis=1)

# --- 排名與統計 ---
df_scores = merged.groupby('人名')['得分'].sum().reset_index()
for p in all_players:
    if p not in df_scores['人名'].values:
        df_scores = pd.concat([df_scores, pd.DataFrame([{'人名': p, '得分': 0}])])
# 並列排名邏輯
df_scores['排名'] = df_scores['得分'].rank(method='min', ascending=False).astype(int)
df_scores = df_scores.sort_values('排名')

# --- 頁面 ---
tab1, tab2, tab3, tab4 = st.tabs(["🏆 總積分排名", "⚽ 賽程", "📋 下注紀錄", "📊 勝率與心水"])

with tab1:
    st.dataframe(df_scores[['排名', '人名', '得分']], hide_index=True, use_container_width=True)

with tab2:
    st.dataframe(df_matches, hide_index=True)

with tab3:
    sel_match = st.selectbox("查看場次", options=df_bets['場次'].unique())
    st.dataframe(df_bets[df_bets['場次'] == sel_match][['人名', bet_col]], hide_index=True)

with tab4:
    upcoming = df_matches[df_matches[res_col].isna() | (df_matches[res_col] == '')]['場次'].values
    next_m = upcoming[0] if len(upcoming) > 0 else None
    
    stats = []
    for p in all_players:
        p_data = merged[merged['人名'] == p]
        valid = p_data[p_data[res_col].notna() & (p_data[res_col] != '走盤') & (p_data[res_col] != '')]
        wins = len(valid[valid['得分'] > 0])
        total = len(valid)
        next_bet = df_bets[(df_bets['人名'] == p) & (df_bets['場次'] == next_m)][bet_col].values
        stats.append({
            '人名': p, 
            '勝率': (wins/total*100) if total > 0 else 0,
            '下一場心水': next_bet[0] if len(next_bet) > 0 else "未落注"
        })
    df_stats = pd.DataFrame(stats)
    df_stats['勝率排名'] = df_stats['勝率'].rank(method='min', ascending=False).astype(int)
    df_stats['勝率'] = df_stats['勝率'].apply(lambda x: f"{x:.1f}%")
    st.dataframe(df_stats.sort_values('勝率排名')[['勝率排名', '人名', '勝率', '下一場心水']], hide_index=True, use_container_width=True)

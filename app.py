import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="燈閪盃落注系統", layout="wide")

# 1. 填入你剛剛更新過的 GAS 部署網址
GAS_URL = "https://script.google.com/macros/s/AKfycbziToDdXkbc-tG9G_snGu8CnEFAMHjAjVGT-uBecEB6CmPMt4xed_6U8VYAef45cW02gA/exec"

@st.cache_data(ttl=0)
def load_data():
    url = f"https://docs.google.com/spreadsheets/d/1ZkA6GA8JXs2oCh2rNSr_4XA7HNuxBdUjeZF4y-UyBh0/gviz/tq?tqx=out:csv&sheet=表單回覆 1"
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        return df
    except: return pd.DataFrame()

# 獲取球員名單
def get_players():
    url = f"https://docs.google.com/spreadsheets/d/1ZkA6GA8JXs2oCh2rNSr_4XA7HNuxBdUjeZF4y-UyBh0/gviz/tq?tqx=out:csv&sheet=Players"
    try:
        df = pd.read_csv(url)
        return df["人名"].dropna().tolist()
    except: return []

st.title("🏆 燈閪盃全自動系統")

with st.sidebar.form("bet_form", clear_on_submit=True):
    u = st.selectbox("你是誰？", ["請選擇"] + get_players())
    m = st.text_input("輸入場次")
    b = st.radio("投注方向", ["上盤", "下盤"])
    sub = st.form_submit_button("🔥 確認提交")
    
    if sub:
        if u == "請選擇" or m == "":
            st.error("請填完整資料！")
        else:
            try:
                # 發送請求
                response = requests.get(GAS_URL, params={'name': u, 'match': m, 'bet': b}, timeout=15)
                if "Success" in response.text:
                    st.success("✅ 落注成功！")
                else:
                    st.error(f"❌ 寫入失敗: {response.text}")
            except Exception as e:
                st.error(f"連線錯誤: {e}")

st.subheader("📋 實時落注紀錄")
st.dataframe(load_data(), use_container_width=True)

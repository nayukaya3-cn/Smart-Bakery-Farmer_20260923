"""
セキュリティログ（管理者専用）─ 記録する → 見せる → 判断する

Streamlit Community Cloud の「Settings → Secrets」に ADMIN_TOKEN（16文字以上のランダムな文字列）を
登録したときだけ使えます。未登録なら誰も開けません。
"""
import pandas as pd
import plotly.express as px
import streamlit as st

import security_guard as sg

st.set_page_config(page_title="セキュリティログ", page_icon="🔒", layout="wide")
st.title("🔒 セキュリティログ（管理者専用）")

fails = st.session_state.get("_admin_fails", 0)
if fails >= 5:
    st.error("認証の失敗が続いたため、このセッションではロックしました。ページを開き直してください。")
    st.stop()

if not st.session_state.get("_admin_ok"):
    token = st.text_input("管理者トークン", type="password")
    if not token:
        st.caption("ADMIN_TOKEN が Secrets に未登録の場合、このページは使えません。")
        st.stop()
    if sg.admin_ok(token):
        st.session_state._admin_ok = True
        sg.log_event("admin_login", "INFO", page="security_log")
        st.rerun()
    st.session_state._admin_fails = fails + 1
    st.error("トークンが違います。")
    st.stop()

df = sg.recent_events()
st.caption("サーバーのメモリにある直近500件です（アプリの再起動で消えます）。"
           "残したい記録は下のボタンでCSV保存してください。全件は Manage app → Logs でも見られます。")
if df.empty:
    st.info("まだ記録はありません。")
    st.stop()

# ① 計算する
k = st.columns(4)
k[0].metric("記録件数", f"{len(df)} 件")
k[1].metric("警告（WARNING）", f"{(df['severity'] == 'WARNING').sum()} 件")
k[2].metric("重大（CRITICAL）", f"{(df['severity'] == 'CRITICAL').sum()} 件")
k[3].metric("AI呼び出し", f"{(df['event'] == 'ai_call').sum()} 回")

# ② 可視化する
df["時刻"] = pd.to_datetime(df["ts"])
fig = px.histogram(df, x="時刻", color="severity", nbins=48,
                   color_discrete_map={"INFO": "#8aa6c1", "WARNING": "#e6a23c", "CRITICAL": "#d9534f"})
fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig, width="stretch")

# ③ 判断する
crit = df[df["severity"] == "CRITICAL"]
if len(crit):
    st.error("重大なイベントがあります。SECURITY.md の「インシデント対応手順」に沿って確認してください。")
    st.dataframe(crit.drop(columns=["時刻"]), width="stretch", hide_index=True)

sev = st.multiselect("表示する重大度", ["INFO", "WARNING", "CRITICAL"], ["WARNING", "CRITICAL"])
st.dataframe(df[df["severity"].isin(sev)].drop(columns=["時刻"]).iloc[::-1], width="stretch", hide_index=True)
st.download_button("ログをCSVで保存", sg.safe_csv(df.drop(columns=["時刻"])), "security_log.csv", "text/csv")

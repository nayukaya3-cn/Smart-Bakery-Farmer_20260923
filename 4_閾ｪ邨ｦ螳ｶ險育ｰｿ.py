"""
自給家計簿 ─ 自給した食べ物を市場価格に換算し、「見えない収入」を可視化する
配置先: pages/4_自給家計簿.py （Streamlit のマルチページ構成）

保存について:
  Streamlit Community Cloud ではサーバー上のファイルが再起動で消えるため、
  記録は「CSVをダウンロード」で手元に保存し、次回「CSVを読み込む」で復元します。
"""
import datetime as dt

import pandas as pd
import streamlit as st

import security_guard as sg

st.set_page_config(page_title="自給家計簿", page_icon="🌾", layout="wide")

# ------------------------------------------------------------
# 初期データ（価格はすべて仮置き。地域の直売所価格などに置き換える）
# ------------------------------------------------------------
HARVEST_COLS = ["日付", "品目", "数量", "単位", "単価(円)"]
COST_COLS = ["日付", "項目", "金額(円)"]
WORK_COLS = ["日付", "作業", "メモ"]

DEFAULT_HARVEST = pd.DataFrame(columns=HARVEST_COLS)
DEFAULT_COST = pd.DataFrame(
    [[dt.date(2026, 10, 20), "小麦の種子", 0]], columns=COST_COLS
)
DEFAULT_WORK = pd.DataFrame(
    [[dt.date(2026, 10, 20), "パン用小麦の播種", "記録の1行目。発芽率も後で記入"]],
    columns=WORK_COLS,
)

for key, df in [("harvest", DEFAULT_HARVEST), ("cost", DEFAULT_COST), ("work", DEFAULT_WORK)]:
    if key not in st.session_state:
        st.session_state[key] = df.copy()


def to_date(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["日付"] = pd.to_datetime(df["日付"], errors="coerce").dt.date
    return df


# ------------------------------------------------------------
# サイドバー：保存と復元
# ------------------------------------------------------------
with st.sidebar:
    st.header("記録の保存・復元")
    st.caption("終わったら必ずダウンロードしてください。")

    for key, label in [("harvest", "収穫"), ("cost", "支出"), ("work", "作業")]:
        csv = sg.safe_csv(st.session_state[key])
        st.download_button(f"{label}記録をCSVで保存", csv, f"自給家計簿_{label}.csv", "text/csv")

    st.divider()
    for key, label in [("harvest", "収穫"), ("cost", "支出"), ("work", "作業")]:
        up = st.file_uploader(f"{label}記録のCSVを読み込む", type="csv", key=f"up_{key}")
        if up is not None:
            _df = sg.read_csv_safely(up, page="kakeibo", kind=key)
            if _df is not None:
                st.session_state[key] = to_date(_df)

    st.divider()
    year = st.number_input("集計する年", 2026, 2040, dt.date.today().year)
    pension_note = st.text_input("ひとこと目標", "年金＋細い現金収入＋自給で暮らす")

# ------------------------------------------------------------
# 本体：入力（記録する）
# ------------------------------------------------------------
st.title("🌾 自給家計簿")
st.caption("記録する → 見せる → 自分の条件で判断する")

tab_h, tab_c, tab_w = st.tabs(["収穫を記録", "支出を記録", "作業日誌"])

with tab_h:
    st.write("収穫した量と、**同じものを買った場合の単価**を入れます。")
    st.session_state["harvest"] = st.data_editor(
        st.session_state["harvest"],
        num_rows="dynamic",
        width="stretch",
        column_config={
            "日付": st.column_config.DateColumn(required=True),
            "品目": st.column_config.SelectboxColumn(
                options=["米", "小麦", "野菜", "果物", "卵", "その他"], required=True
            ),
            "数量": st.column_config.NumberColumn(min_value=0.0, step=0.1),
            "単位": st.column_config.SelectboxColumn(options=["kg", "個", "束", "本"]),
            "単価(円)": st.column_config.NumberColumn(min_value=0, step=10),
        },
        key="ed_harvest",
    )

with tab_c:
    st.write("自給のために**現金で払ったもの**（種・肥料・燃料・修理など）を入れます。")
    st.session_state["cost"] = st.data_editor(
        st.session_state["cost"],
        num_rows="dynamic",
        width="stretch",
        column_config={
            "日付": st.column_config.DateColumn(required=True),
            "項目": st.column_config.TextColumn(required=True),
            "金額(円)": st.column_config.NumberColumn(min_value=0, step=100),
        },
        key="ed_cost",
    )

with tab_w:
    st.write("播種・発芽・収穫などの作業と気づきを残します。")
    st.session_state["work"] = st.data_editor(
        st.session_state["work"],
        num_rows="dynamic",
        width="stretch",
        column_config={"日付": st.column_config.DateColumn(required=True)},
        key="ed_work",
    )

# ------------------------------------------------------------
# 集計（計算する）
# ------------------------------------------------------------
h = to_date(st.session_state["harvest"]).dropna(subset=["日付"])
c = to_date(st.session_state["cost"]).dropna(subset=["日付"])
h = h[pd.to_datetime(h["日付"]).dt.year == year]
c = c[pd.to_datetime(c["日付"]).dt.year == year]

h["金額換算(円)"] = h["数量"].fillna(0).astype(float) * h["単価(円)"].fillna(0).astype(float)
value = int(h["金額換算(円)"].sum())
cash = int(c["金額(円)"].fillna(0).astype(float).sum())
net = value - cash

# ------------------------------------------------------------
# 可視化（見せる）
# ------------------------------------------------------------
st.divider()
st.subheader(f"{year}年の集計")
st.caption(pension_note)

m1, m2, m3 = st.columns(3)
m1.metric("自給の金額換算", f"{value:,} 円")
m2.metric("自給のための現金支出", f"{cash:,} 円")
m3.metric("見えない収入（差し引き）", f"{net:,} 円", f"月あたり {net / 12:,.0f} 円")

if not h.empty or not c.empty:
    hm = h.assign(月=pd.to_datetime(h["日付"]).dt.month).groupby("月")["金額換算(円)"].sum()
    cm = c.assign(月=pd.to_datetime(c["日付"]).dt.month).groupby("月")["金額(円)"].sum()
    monthly = pd.DataFrame({"自給の金額換算": hm, "現金支出": cm}).reindex(range(1, 13)).fillna(0)
    monthly.index = [f"{m}月" for m in monthly.index]

    col1, col2 = st.columns(2)
    with col1:
        st.write("**月ごとの推移**")
        st.bar_chart(monthly)
    with col2:
        st.write("**品目ごとの金額換算**")
        if not h.empty:
            st.bar_chart(h.groupby("品目")["金額換算(円)"].sum())
        else:
            st.info("収穫を記録すると、ここに品目別のグラフが出ます。")
else:
    st.info("収穫や支出を記録すると、ここにグラフが出ます。")

# ------------------------------------------------------------
# 判断の材料
# ------------------------------------------------------------
st.divider()
st.subheader("自分の条件で判断する")
target = st.slider("食費のうち、自給で置き換えたい額（月）", 0, 60000, 20000, 1000)
rate = (net / 12) / target * 100 if target else 0
st.progress(min(max(rate, 0), 100) / 100, text=f"目標に対する達成度：{rate:.0f}%")
st.caption(
    "数字は市場価格への換算で、実際の家計の黒字を示すものではありません。"
    "医療・燃料・通信などの現金支出は別に確保してください。"
)

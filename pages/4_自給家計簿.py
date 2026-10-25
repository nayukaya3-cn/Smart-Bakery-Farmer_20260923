"""
自給家計簿 ─ 自給した食べ物を市場価格に換算し、「見えない収入」を可視化する
配置先: pages/4_自給家計簿.py （Streamlit のマルチページ構成）

保存について:
  Streamlit Community Cloud ではサーバー上のファイルが再起動で消えるため、
  記録は「CSVをダウンロード」で手元に保存し、次回「CSVを読み込む」で復元します。

カオスヘッジ（悪性インフレ・供給ショックへの備え）:
  ① 作る（自給）→ ② 余りを売る（流動性）→ ③ 現金は持ち続けず、早めに実物に換える
  （種・資材・道具・土地・技能・信頼）。計算の本体は chaos_hedge.py。

閲覧ロック:
  家計（収穫の金額換算・現金支出・暮らし方の目標）は本人の家計情報なので、所有者専用にする。
  ロックの本体は owner_gate.py（収入構造ページと共通。Googleログイン × OWNER_EMAILS）。
"""
import datetime as dt

import pandas as pd
import streamlit as st

import chaos_hedge as ch
import owner_gate as og
import security_guard as sg

st.set_page_config(page_title="自給家計簿（本人のみ）", page_icon="🌾", layout="wide")
og.require_owner("kakeibo")  # 所有者でなければここで止まる

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

DEFAULT_SALES = pd.DataFrame(columns=ch.SALES_COLS)
DEFAULT_CONVERT = pd.DataFrame(columns=ch.CONVERT_COLS)

LEDGERS = [("harvest", "収穫"), ("cost", "支出"), ("work", "作業"), ("sales", "余剰販売"), ("convert", "実物化")]

for key, df in [("harvest", DEFAULT_HARVEST), ("cost", DEFAULT_COST), ("work", DEFAULT_WORK),
                ("sales", DEFAULT_SALES), ("convert", DEFAULT_CONVERT)]:
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

    for key, label in LEDGERS:
        csv = sg.safe_csv(st.session_state[key])
        st.download_button(f"{label}記録をCSVで保存", csv, f"自給家計簿_{label}.csv", "text/csv")

    st.divider()
    for key, label in LEDGERS:
        up = st.file_uploader(f"{label}記録のCSVを読み込む", type="csv", key=f"up_{key}")
        if up is not None:
            _df = sg.read_csv_safely(up, page="kakeibo", kind=key)
            if _df is not None:
                st.session_state[key] = to_date(_df)

    st.divider()
    year = st.number_input("集計する年", 2026, 2040, dt.date.today().year)
    # 目標の文言は公開リポジトリに残さない（Secrets の KAKEIBO_GOAL で初期値を入れられる）
    try:
        _goal = str(st.secrets.get("KAKEIBO_GOAL", ""))
    except Exception:  # noqa: BLE001
        _goal = ""
    pension_note = st.text_input("ひとこと目標", _goal, placeholder="例：自給で暮らしを支える")

# ------------------------------------------------------------
# 本体：入力（記録する）
# ------------------------------------------------------------
st.title("🌾 自給家計簿")
st.caption("記録する → 見せる → 自分の条件で判断する")

tab_h, tab_c, tab_w, tab_s, tab_x, tab_p = st.tabs(
    ["収穫を記録", "支出を記録", "作業日誌", "② 余りを売る", "③ 実物に換える", "計画と比べる"])

with tab_h:
    st.write("収穫した量と、**同じものを買った場合の単価**を入れます。")
    st.session_state["harvest"] = st.data_editor(
        st.session_state["harvest"],
        num_rows="dynamic",
        width="stretch",
        column_config={
            "日付": st.column_config.DateColumn(required=True),
            "品目": st.column_config.SelectboxColumn(
                options=["米", "小麦", "大豆", "芋", "野菜", "果物", "卵", "その他"], required=True
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

with tab_s:
    st.write("自分で食べきれない**余り**を売った記録です。売上は②の流動性（現金）になります。")
    st.caption("生の野菜の直売は原則許可不要。パンなどの加工品は営業許可、路上販売は道路使用許可が要ります。")
    st.session_state["sales"] = st.data_editor(
        st.session_state["sales"],
        num_rows="dynamic",
        width="stretch",
        column_config={
            "日付": st.column_config.DateColumn(required=True),
            "品目": st.column_config.SelectboxColumn(
                options=["米", "小麦", "大豆", "芋", "野菜", "果物", "卵", "パン", "その他"], required=True
            ),
            "数量": st.column_config.NumberColumn(min_value=0.0, step=0.1),
            "単位": st.column_config.SelectboxColumn(options=["kg", "個", "束", "本"]),
            "売上(円)": st.column_config.NumberColumn(min_value=0, step=100),
            "販路": st.column_config.SelectboxColumn(options=ch.CHANNELS),
        },
        key="ed_sales",
    )

with tab_x:
    st.write("売上を**現金のまま持たず**、何に換えたかの記録です。")
    st.dataframe(
        pd.DataFrame({"年あたり減耗率（仮置き）": ch.ASSET_KINDS}).style.format("{:.0%}"),
        width="content",
    )
    st.session_state["convert"] = st.data_editor(
        st.session_state["convert"],
        num_rows="dynamic",
        width="stretch",
        column_config={
            "日付": st.column_config.DateColumn(required=True),
            "種類": st.column_config.SelectboxColumn(options=list(ch.ASSET_KINDS), required=True),
            "内容": st.column_config.TextColumn(help="例：小麦の種／鍬の更新／ボイラー講習／直売所の会費"),
            "金額(円)": st.column_config.NumberColumn(min_value=0, step=100),
        },
        key="ed_convert",
    )

with tab_p:
    st.write("自給シミュレーターの**計画値**と、ここに記録した**実績**を品目ごとに比べます。"
             "同じブラウザでシミュレーターを開いていれば自動で入ります。別の日は計画CSVを読み込みます。")
    up_plan = st.file_uploader("自給計画のCSVを読み込む", type="csv", key="up_plan")
    if up_plan is not None:
        _plan = sg.read_csv_safely(up_plan, page="kakeibo", kind="plan")
        if _plan is not None:
            st.session_state["jikyu_plan"] = to_date(_plan)
    plan = st.session_state.get("jikyu_plan")
    if plan is None or len(plan) == 0:
        st.info("まだ計画がありません。左メニュー「自給と防災の畑」の⑤タブで計画を作ってください。")
    else:
        _p = to_date(plan).dropna(subset=["日付"])
        _a = to_date(st.session_state["harvest"]).dropna(subset=["日付"])
        _p_year = int(pd.to_datetime(_p["日付"]).dt.year.mode().iloc[0])
        _a = _a[pd.to_datetime(_a["日付"]).dt.year == _p_year]
        _a = _a[_a["単位"].fillna("kg") == "kg"]
        cmp = pd.DataFrame({
            "計画(kg)": _p.groupby("品目")["数量"].sum(),
            "実績(kg)": _a.groupby("品目")["数量"].sum() if not _a.empty else pd.Series(dtype=float),
        }).fillna(0)
        cmp["達成率"] = (cmp["実績(kg)"] / cmp["計画(kg)"].where(cmp["計画(kg)"] > 0)).fillna(0)
        st.caption(f"{_p_year}年の計画と、同じ年の実績（単位が kg の記録）を比べています。")
        st.dataframe(cmp.style.format({"計画(kg)": "{:,.1f}", "実績(kg)": "{:,.1f}", "達成率": "{:.0%}"}),
                     width="stretch")
        st.bar_chart(cmp[["計画(kg)", "実績(kg)"]])
        st.caption("実績が計画を大きく下回る品目は、シミュレーターの収量の係数を実測値に置き換えると、"
                   "翌年の計画が現実に近づきます（「④ 探究フィールドワーク」の記録CSVを使います）。")

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

# ------------------------------------------------------------
# カオスヘッジ（悪性インフレ・供給ショックへの備え）
# ------------------------------------------------------------
st.divider()
st.subheader("🛡️ カオスヘッジ：作る → 余りを売る → すぐ換える")
st.caption("1990年代ロシアの家庭菜園（ダーチャ）も戦後日本も、残ったのは「現金」ではなく"
           "「買わずに済んだこと」と「実物・土地・技能」でした。教育用の単純化モデルです。")

scen = st.radio("インフレの想定（年率）", list(ch.SCENARIOS), index=2, horizontal=True)
pi = ch.SCENARIOS[scen]

s_df = to_date(st.session_state["sales"]).dropna(subset=["日付"])
x_df = to_date(st.session_state["convert"]).dropna(subset=["日付"])
s_df = s_df[pd.to_datetime(s_df["日付"]).dt.year == year]
x_df = x_df[pd.to_datetime(x_df["日付"]).dt.year == year]
sales_total = float(pd.to_numeric(s_df["売上(円)"], errors="coerce").fillna(0).sum())
conv_total = float(pd.to_numeric(x_df["金額(円)"], errors="coerce").fillna(0).sum())
idle = ch.idle_cash_loss(s_df, x_df, pi)

# ① 計算する
stages = ch.three_stage(value, cash, sales_total, conv_total, idle["lag_days"], target)
k1, k2, k3, k4 = st.columns(4)
k1.metric("② 余剰の売上", f"{sales_total:,.0f} 円")
k2.metric("③ 実物化した額", f"{conv_total:,.0f} 円", f"売上の {idle['ratio']:.0%}")
k3.metric("換えるまでの平均日数",
          "—" if idle["lag_days"] is None else f"{idle['lag_days']:.0f} 日")
k4.metric("現金で寝かせて失った実質額", f"{idle['loss']:,.0f} 円",
          f"平均滞留 {idle['avg_idle']:,.0f} 円", delta_color="inverse")

# ② 可視化する
col_a, col_b = st.columns(2)
with col_a:
    st.write("**3段の到達度**")
    st.bar_chart(stages.set_index("段")["到達度"], horizontal=True)
    st.caption(" / ".join(f"{r.段}：{r.見ている数字}" for r in stages.itertuples()))
with col_b:
    kind = st.selectbox("換える先", list(ch.ASSET_KINDS), index=2)
    amount = sales_total if sales_total > 0 else 10_000
    st.write(f"**{amount:,.0f} 円を「現金で持つ」か「{kind}に換える」か（実質価値）**")
    st.line_chart(ch.hold_vs_convert(amount, pi, kind, 24))
    st.caption("平時は種や資材を買い込むほうが損（減耗が物価上昇より大きい）。"
               "インフレ率が減耗率を上回ると、早く換えたほうが得になります。")

if not x_df.empty:
    led = ch.asset_ledger(x_df, pi, pd.Timestamp(dt.date.today()))
    st.write("**実物資産の台帳（今日時点の実質価値）**")
    st.dataframe(led.style.format("{:,.0f}"), width="stretch")
    div = ch.diversity(x_df)
    st.caption(f"実物資産の分散度（1−HHI）：{div:.2f}　"
               f"（0＝1種類に集中。{len(ch.ASSET_KINDS)}種類に均等なら {1 - 1 / len(ch.ASSET_KINDS):.2f}）")
    if div < 0.3:
        st.warning("換える先が1つに偏っています。道具・技能・信頼のように減りにくいものにも分けましょう。")

# ③ 自分の条件で判断する
st.write("**自分の条件で判断する**")
chk = [
    st.checkbox("A. 主食（米・小麦・芋のどれか）が、1か月分は手元か畑にある"),
    st.checkbox("B. 余りを売れる販路が2つ以上ある（直売所・契約先・物々交換など）"),
    st.checkbox("C. 売上を30日以内に、種・資材・道具・技能のどれかへ換えている"),
    st.checkbox("D. 換えた先が1種類に偏っていない（分散度 0.3 以上）"),
    st.checkbox("E. 医療・燃料・通信など、自給できない現金支出の3か月分は別に確保している"),
]
n = sum(chk)
if n == 5:
    st.success("カオスヘッジの土台が揃っています。年1回、想定インフレ率を変えて点検を。")
elif n >= 3:
    st.warning(f"{5 - n} 項目が未達です。未達の項目を来月の作業計画に1つ入れましょう。")
else:
    st.info("まず A（主食）と E（現金の床）から。ヘッジは『全部を実物に』ではなく、床を割らないことが先です。")
st.caption("投資・資産運用の助言ではありません。現金をゼロにする戦略ではなく、"
           "生活に必要な現金（E）を確保した上での『余剰の置き場所』の話です。硬貨の鋳つぶしは法律で禁止されています。")

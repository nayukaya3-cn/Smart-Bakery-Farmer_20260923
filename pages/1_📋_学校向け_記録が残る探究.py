"""
学校向け：記録が残る探究 ─ ルーブリック・活動ログ・記録ダッシュボード
配置先: pages/1_📋_学校向け_記録が残る探究.py （Streamlit のマルチページ構成）

ねらい:
  通信制高校・サポート校が外部フィールドと連携して探究学習を行うとき、
  学校が「適正な教育」を説明できる記録を、外部フィールド側で用意して渡す。

保存について:
  Streamlit Community Cloud ではサーバー上のファイルが再起動で消えるため、
  記録は「CSVで保存」で手元に保存し、次回「CSVを読み込む」で復元します。
  生徒の氏名は扱わず、学校が付けた匿名ID（例：S01）で記録します。
"""
import datetime as dt
import io

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="学校向け：記録が残る探究", page_icon="📋", layout="wide")

FACEBOOK_URL = "https://www.facebook.com/profile.php?id=100079624235158"
UPDATED = "2026-10-09"

st.markdown(
    """
    <style>
    .hero {padding: 1.6rem 1.8rem 1.4rem; border-radius: 16px;
           background: linear-gradient(120deg, #e4ecf5 0%, #e3efd6 100%);
           color: #22313f; margin-bottom: 1rem;}
    .hero .eyebrow {font-size: .85rem; letter-spacing: .08em; color: #4a6a8a; margin: 0 0 .4rem 0;}
    .hero h1 {margin: 0 0 .6rem 0; font-size: 2.0rem; line-height: 1.3; color: #22313f;}
    .hero .lead {margin: 0 0 .8rem 0; font-size: 1.05rem; line-height: 1.8;}
    .tags {display: flex; flex-wrap: wrap; gap: .45rem; margin: .2rem 0 0;}
    .tags span {padding: .35rem .8rem; border-radius: 999px; background: #ffffffcc;
                font-weight: 600; font-size: .95rem; color: #22313f;}
    .note {font-size: .85rem; color: #5a6a75;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────
# ルーブリックの定義（5観点 × 4段階）
#   ※ 観点名や記述を変えたいときは、ここを書きかえるだけで全体に反映されます
# ─────────────────────────────────────────────
RUBRIC = {
    "問いを立てる": [
        "問いが出せない／与えられた問いのまま",
        "畑で気づいたことを問いの形にできる",
        "確かめ方まで含めた問いにできる",
        "自分の生活や進路につながる問いに発展させられる",
    ],
    "① 計算する": [
        "測定・計算の手順を追えない",
        "手順どおりに測定し、数値を記録できる",
        "数式やモデルで見積もり、実測と比べられる",
        "誤差や仮定の限界を説明し、モデルを直せる",
    ],
    "② 可視化する": [
        "表やグラフにできない",
        "表・グラフに整理できる",
        "目的に合ったグラフを選び、傾向を読み取れる",
        "他者に伝わる形で示し、問いに答えられる",
    ],
    "③ 自分の条件で判断する": [
        "根拠なく結論を出す／判断を避ける",
        "データを根拠に結論を述べられる",
        "自分の条件（場所・資源・時間）に当てはめて判断できる",
        "別の条件なら判断がどう変わるかまで説明できる",
    ],
    "安全・協働・記録": [
        "安全上の指示を守れないことがある",
        "指示どおりに安全に作業し、記録を残せる",
        "危険を自分で予測し、仲間と分担して作業できる",
        "手順の改善を提案し、記録を後の人が使える形に整えられる",
    ],
}
AXES = list(RUBRIC)
LEVELS = [1, 2, 3, 4]

INSTRUCTORS = pd.DataFrame([
    ("楠香谷 隆規", "高等学校教諭一種免許状（理科）", "保有"),
    ("楠香谷 隆規", "職業訓練指導員（パン・菓子製造）", "保有"),
    ("楠香谷 隆規", "ものづくりマイスター（厚生労働省）／HACCP実務20年以上", "保有"),
    ("楠香谷 隆規", "産業用ロボット特別教育 修了（インストラクターコース 2026年12月修了予定）", "保有"),
    ("楠香谷 隆規", "危険物取扱者（乙種第4類）", "保有"),
    ("楠香谷 隆規", "高等学校教諭免許状（情報）", "取得予定（2027年9月）"),
    ("楠香谷 隆規", "特別支援学校 高等部 作業学習の実習助手", "経験 5年4か月"),
], columns=["指導者", "資格・経験", "区分"])

# ─────────────────────────────────────────────
# 記入例（架空）：実施実績ではありません
# ─────────────────────────────────────────────
LOG_COLS = ["日付", "学校", "生徒ID", "開始", "終了", "活動テーマ", "取得したデータ",
            "成果物", "安全説明", "体調確認", "指導者", "所見"]
SCORE_COLS = ["日付", "学校", "生徒ID", *AXES, "評価者", "コメント"]


def sample_log() -> pd.DataFrame:
    t = dt.time
    rows = [
        (dt.date(2027, 10, 20), "（例）A通信制高校", "S01", t(10, 0), t(11, 30), "播種日と発芽率",
         "播種量 g/㎡、地温", "観察シート", True, True, "楠香谷", "地温の測り方を自分で工夫できた"),
        (dt.date(2027, 10, 20), "（例）A通信制高校", "S02", t(10, 0), t(11, 30), "播種日と発芽率",
         "播種量 g/㎡、地温", "観察シート", True, True, "楠香谷", "記録は丁寧。問いはこれから"),
        (dt.date(2027, 11, 17), "（例）A通信制高校", "S01", t(10, 0), t(11, 30), "発芽率の実測",
         "発芽本数/㎡", "Pythonでのグラフ", True, True, "楠香谷", "予測と実測のずれに自分で気づいた"),
        (dt.date(2027, 11, 17), "（例）A通信制高校", "S02", t(10, 0), t(11, 0), "発芽率の実測",
         "発芽本数/㎡", "グラフ（手書き）", True, True, "楠香谷", "体調により30分早く終了"),
        (dt.date(2027, 12, 15), "（例）A通信制高校", "S01", t(10, 0), t(11, 30), "原価とショック時の判断",
         "1斤原価の試算", "発表スライド", True, True, "楠香谷", "自家産比率で判断が変わることを説明できた"),
        (dt.date(2027, 12, 15), "（例）A通信制高校", "S02", t(10, 0), t(11, 30), "原価とショック時の判断",
         "1斤原価の試算", "発表スライド", True, False, "楠香谷", "体調確認の記入漏れ（要改善）"),
    ]
    return pd.DataFrame(rows, columns=LOG_COLS)


def sample_scores() -> pd.DataFrame:
    rows = [
        (dt.date(2027, 10, 20), "（例）A通信制高校", "S01", 2, 2, 1, 1, 2, "楠香谷", "初回"),
        (dt.date(2027, 10, 20), "（例）A通信制高校", "S02", 1, 2, 2, 1, 2, "楠香谷", "初回"),
        (dt.date(2027, 12, 15), "（例）A通信制高校", "S01", 3, 3, 3, 3, 3, "楠香谷", "最終"),
        (dt.date(2027, 12, 15), "（例）A通信制高校", "S02", 2, 2, 3, 2, 3, "楠香谷", "最終"),
    ]
    return pd.DataFrame(rows, columns=SCORE_COLS)


def to_time(v):
    if isinstance(v, dt.time):
        return v
    try:
        return pd.to_datetime(str(v)).time()
    except (ValueError, TypeError):
        return None


def normalize_log(df: pd.DataFrame) -> pd.DataFrame:
    df = df.reindex(columns=LOG_COLS).copy()
    df["日付"] = pd.to_datetime(df["日付"], errors="coerce").dt.date
    for c in ("開始", "終了"):
        df[c] = df[c].map(to_time)
    for c in ("安全説明", "体調確認"):
        df[c] = df[c].map(lambda x: str(x).strip().lower() in ("true", "1", "はい", "済", "yes"))
    return df


def normalize_scores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.reindex(columns=SCORE_COLS).copy()
    df["日付"] = pd.to_datetime(df["日付"], errors="coerce").dt.date
    for a in AXES:
        df[a] = pd.to_numeric(df[a], errors="coerce")
    return df


if "edu_log" not in st.session_state:
    st.session_state.edu_log = sample_log()
    st.session_state.edu_scores = sample_scores()
    st.session_state.edu_is_sample = True

# ─────────────────────────────────────────────
# サイドバー：保存・復元・記入例の切り替え
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("📋 記録の保存・復元")
    st.caption("終わったら必ずCSVで保存してください（公開ページには残りません）。")
    up_log = st.file_uploader("活動ログのCSVを読み込む", type="csv", key="up_edu_log")
    if up_log is not None:
        st.session_state.edu_log = normalize_log(pd.read_csv(io.BytesIO(up_log.getvalue())))
        st.session_state.edu_is_sample = False
    up_sc = st.file_uploader("ルーブリック評価のCSVを読み込む", type="csv", key="up_edu_sc")
    if up_sc is not None:
        st.session_state.edu_scores = normalize_scores(pd.read_csv(io.BytesIO(up_sc.getvalue())))
        st.session_state.edu_is_sample = False
    st.divider()
    if st.button("記入例（架空）に戻す"):
        st.session_state.edu_log = sample_log()
        st.session_state.edu_scores = sample_scores()
        st.session_state.edu_is_sample = True
    if st.button("空の記録から始める"):
        st.session_state.edu_log = pd.DataFrame(columns=LOG_COLS)
        st.session_state.edu_scores = pd.DataFrame(columns=SCORE_COLS)
        st.session_state.edu_is_sample = False
    st.divider()
    st.link_button("📘 Facebookで相談する", FACEBOOK_URL, width="stretch")

# ═════════════════════════════════════════════
# ヒーロー：何を約束するのか
# ═════════════════════════════════════════════
st.markdown(
    """
    <div class="hero">
      <p class="eyebrow">通信制高校・サポート校の先生方へ ・ 探究学習の外部フィールド</p>
      <h1>記録が残る探究を、畑とパンのフィールドで。</h1>
      <p class="lead">生徒が<b>いつ・何時間・何をして・何を身につけたか</b>を、
      外部フィールドの側で記録し、学校にそのままお渡しします。<br>
      外部と連携した学習について、学校が保護者・所轄庁に<b>説明できる形</b>で残すことを最優先にしています。</p>
      <div class="tags">
        <span>📏 ルーブリック（5観点×4段階）</span>
        <span>📝 活動ログ（出席・時間・安全確認）</span>
        <span>📊 記録ダッシュボード＋報告書</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("記録の3点セット", "整備済み")
c1.caption("このページでそのまま使えます")
c2.metric("評価の観点", f"{len(AXES)} 観点 × {len(LEVELS)} 段階")
c2.caption("計算する→可視化する→判断する")
c3.metric("試行プログラムの実施", "0 回")
c3.caption("2027年度に 1〜2 回予定")
c4.metric("指導者の資格", f"{(INSTRUCTORS['区分'] == '保有').sum()} 種 保有")
c4.caption("理科免許・HACCP・ものづくりマイスターほか")

st.info(
    "**なぜ今、記録なのか**　2026年7月に改正された高校の定時制・通信教育の振興法が成立し、"
    "通信制高校の設置者には、連携する施設での**適正な教育の確保**が責務として明記されました。"
    "文部科学省は現在、そのための基本指針を検討しています。"
    "外部と連携した学習ほど、「実際に何が行われたか」を示す記録が学校の安心材料になります。"
)
st.markdown(
    '<p class="note">※ 本ページは、学校が説明責任を果たすための記録を外部フィールド側で用意するものです。'
    "法令上の手続きや施設の位置づけは、各学校・所轄庁の判断に従います。"
    f"　最終更新：{UPDATED}</p>",
    unsafe_allow_html=True,
)

tab_map, tab_rub, tab_log, tab_dash, tab_pkg = st.tabs([
    "🧭 学校が示すこと ↔ 残す記録", "📏 ルーブリック", "📝 活動ログ", "📊 記録ダッシュボード", "🤝 1回分のプログラム",
])

# ═════════════════════════════════════════════
# 1. 学校が示すこと ↔ この畑で残す記録
# ═════════════════════════════════════════════
with tab_map:
    st.header("🧭 学校が説明を求められること ↔ この畑で残す記録")
    st.write("外部フィールドでの学習について、学校が問われやすい点ごとに、こちらで残す記録を対応させました。")
    mapping = pd.DataFrame([
        ("生徒が実際に参加したか", "日付・開始／終了時刻・滞在時間（生徒IDごと）", "📝 活動ログ"),
        ("何を学んだか（学習の実質）", "活動テーマ・取得したデータ・成果物", "📝 活動ログ"),
        ("どう評価したか", "5観点×4段階のルーブリック。初回と最終の比較", "📏 ルーブリック"),
        ("安全に行ったか", "安全説明・体調確認の実施を毎回チェック", "📝 活動ログ"),
        ("誰が指導したか", "指導者名と保有資格", "🤝 1回分のプログラム"),
        ("どう改善していくか", "実施ごとの所見と集計、記入漏れの検出", "📊 記録ダッシュボード"),
        ("学校にどう渡すか", "CSV（学校の様式に転記可）と、報告書（テキスト）", "📊 記録ダッシュボード"),
    ], columns=["学校が説明を求められること", "この畑で残す記録", "どこで見られるか"])
    st.dataframe(mapping, width="stretch", hide_index=True)

    st.subheader("記録の流れ")
    flow = ["① 実施前：安全説明・体調確認", "② 実施中：活動ログを記入", "③ 実施後：ルーブリックで評価",
            "④ 月末：ダッシュボードで集計", "⑤ 学校へ：CSV＋報告書を提出"]
    st.markdown(" → ".join(f"**{s}**" for s in flow))

    with st.expander("個人情報の扱い"):
        st.markdown(
            "- 生徒の**氏名は扱いません**。学校が付けた匿名ID（例：S01）で記録します。\n"
            "- 記録はこのページのサーバーには残らず、CSVとして学校と指導者の手元でのみ保管します。\n"
            "- 写真を記録に使う場合は、顔が写らないよう撮影し、事前に学校・保護者の了承を得ます。"
        )
    st.caption("HACCP（食品衛生管理）で20年以上続けてきた「記録を残し、後から検証できる」管理の考え方を、"
               "探究学習の記録に応用しています。")

# ═════════════════════════════════════════════
# 2. ルーブリック
# ═════════════════════════════════════════════
with tab_rub:
    st.header("📏 探究ルーブリック（5観点 × 4段階）")
    st.write("このダッシュボード全体の「計算する → 可視化する → 自分の条件で判断する」に、"
             "「問いを立てる」と「安全・協働・記録」を加えた5観点です。")
    rub_df = pd.DataFrame(RUBRIC, index=[f"レベル{n}" for n in LEVELS]).T
    rub_df.index.name = "観点"
    st.dataframe(rub_df, width="stretch")
    st.download_button("ルーブリック表をCSVで保存", rub_df.to_csv().encode("utf-8-sig"),
                       "探究ルーブリック.csv", "text/csv")

    st.subheader("評価を入力する")
    if st.session_state.edu_is_sample:
        st.caption("※ いま表示しているのは**架空の記入例**です。実施実績ではありません。")
    scores = st.data_editor(
        st.session_state.edu_scores,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "日付": st.column_config.DateColumn(required=True),
            **{a: st.column_config.NumberColumn(min_value=1, max_value=4, step=1) for a in AXES},
        },
        key="ed_scores",
    )
    st.download_button("ルーブリック評価をCSVで保存", scores.to_csv(index=False).encode("utf-8-sig"),
                       "ルーブリック評価.csv", "text/csv")

# ═════════════════════════════════════════════
# 3. 活動ログ
# ═════════════════════════════════════════════
with tab_log:
    st.header("📝 活動ログ（出席・時間・安全確認）")
    st.write("1回の実施ごとに、生徒IDごとに1行ずつ記入します。滞在時間はダッシュボードで自動計算します。")
    if st.session_state.edu_is_sample:
        st.caption("※ いま表示しているのは**架空の記入例**です。実施実績ではありません。")
    log = st.data_editor(
        st.session_state.edu_log,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "日付": st.column_config.DateColumn(required=True),
            "開始": st.column_config.TimeColumn(format="HH:mm", step=300),
            "終了": st.column_config.TimeColumn(format="HH:mm", step=300),
            "安全説明": st.column_config.CheckboxColumn(help="実施前に安全説明をしたか"),
            "体調確認": st.column_config.CheckboxColumn(help="実施前に体調を確認したか"),
            "所見": st.column_config.TextColumn(width="large"),
        },
        key="ed_log",
    )
    st.download_button("活動ログをCSVで保存", log.to_csv(index=False).encode("utf-8-sig"),
                       "活動ログ.csv", "text/csv")

# ─────────────────────────────────────────────
# 集計（ダッシュボードと報告書で共用）
# ─────────────────────────────────────────────
L = normalize_log(log).dropna(subset=["日付"])
S = normalize_scores(scores).dropna(subset=["日付"])


def minutes(row) -> float:
    s, e = row["開始"], row["終了"]
    if s is None or e is None:
        return float("nan")
    m = (dt.datetime.combine(dt.date.min, e) - dt.datetime.combine(dt.date.min, s)).total_seconds() / 60
    return m if m >= 0 else float("nan")


if not L.empty:
    L["滞在(分)"] = L.apply(minutes, axis=1)
else:
    L["滞在(分)"] = pd.Series(dtype=float)

n_sessions = L["日付"].nunique()
n_students = L["生徒ID"].dropna().nunique()
total_h = L["滞在(分)"].sum(skipna=True) / 60
safety_rate = L["安全説明"].mean() * 100 if len(L) else 0.0
health_rate = L["体調確認"].mean() * 100 if len(L) else 0.0
missing = L[~(L["安全説明"] & L["体調確認"]) | L["滞在(分)"].isna()]


def first_last(df: pd.DataFrame) -> pd.DataFrame:
    """生徒ごとに、最初と最新のルーブリック評価を取り出す。"""
    if df.empty:
        return pd.DataFrame(columns=["生徒ID", "時点", *AXES])
    df = df.dropna(subset=AXES, how="all").sort_values("日付")
    first = df.groupby("生徒ID").head(1).assign(時点="初回")
    last = df.groupby("生徒ID").tail(1).assign(時点="最新")
    return pd.concat([first, last])[["生徒ID", "時点", *AXES]]


FL = first_last(S)
avg_first = FL[FL["時点"] == "初回"][AXES].mean(axis=1).mean() if not FL.empty else float("nan")
avg_last = FL[FL["時点"] == "最新"][AXES].mean(axis=1).mean() if not FL.empty else float("nan")

# ═════════════════════════════════════════════
# 4. 記録ダッシュボード
# ═════════════════════════════════════════════
with tab_dash:
    st.header("📊 記録ダッシュボード")
    if st.session_state.edu_is_sample:
        st.warning("いま表示しているのは**架空の記入例**の集計です。実施実績ではありません。")

    k = st.columns(5)
    k[0].metric("実施回数", f"{n_sessions} 回")
    k[1].metric("参加生徒数", f"{n_students} 人")
    k[2].metric("延べ学習時間", f"{total_h:.1f} 時間")
    k[3].metric("安全説明の実施率", f"{safety_rate:.0f} %")
    k[4].metric("体調確認の実施率", f"{health_rate:.0f} %",
                "要改善" if health_rate < 100 else "全回実施", delta_color="off")

    st.subheader("① 計算する：生徒ごとの参加時間")
    if L.empty:
        st.info("活動ログを記入すると、ここに集計が出ます。")
    else:
        per = (L.groupby("生徒ID").agg(参加回数=("日付", "nunique"), 学習時間_時間=("滞在(分)", "sum"))
               .assign(学習時間_時間=lambda d: (d["学習時間_時間"] / 60).round(1)).reset_index())
        st.dataframe(per, width="stretch", hide_index=True)

    st.subheader("② 可視化する：ルーブリックの伸び（初回 → 最新）")
    if FL.empty:
        st.info("ルーブリック評価を記入すると、ここに伸びが表示されます。")
    else:
        g1, g2 = st.columns([3, 2])
        with g1:
            sid = st.selectbox("生徒ID", sorted(FL["生徒ID"].dropna().unique()))
            fig = go.Figure()
            for label, color in [("初回", "#b5b5b5"), ("最新", "#2f6f9f")]:
                r = FL[(FL["生徒ID"] == sid) & (FL["時点"] == label)]
                if r.empty:
                    continue
                vals = r[AXES].iloc[0].tolist()
                fig.add_trace(go.Scatterpolar(r=vals + vals[:1], theta=AXES + AXES[:1], fill="toself",
                                              name=label, line=dict(color=color), opacity=0.7))
            fig.update_layout(polar=dict(radialaxis=dict(range=[0, 4], tickvals=LEVELS)),
                              height=380, margin=dict(l=40, r=40, t=30, b=20),
                              legend=dict(orientation="h", y=-0.05))
            st.plotly_chart(fig, width="stretch")
        with g2:
            st.metric("ルーブリック平均（全生徒・初回）", f"{avg_first:.2f}")
            st.metric("ルーブリック平均（全生徒・最新）", f"{avg_last:.2f}",
                      f"{avg_last - avg_first:+.2f}")
            axis_gain = (FL[FL["時点"] == "最新"].set_index("生徒ID")[AXES]
                         - FL[FL["時点"] == "初回"].set_index("生徒ID")[AXES]).mean()
            fig2 = px.bar(axis_gain.reset_index(), x=0, y="index", orientation="h",
                          labels={"0": "伸び（段階）", "index": ""}, color_discrete_sequence=["#6a9a4a"])
            fig2.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig2, width="stretch")
            st.caption("観点ごとの平均の伸び。伸びの小さい観点が、次回の重点になります。")

    st.subheader("③ 自分の条件で判断する：記録の抜け・改善点")
    if missing.empty:
        st.success("安全説明・体調確認・時刻の記入漏れはありません。")
    else:
        st.error(f"記入漏れ・要確認が {len(missing)} 件あります。次回までに確認してください。")
        st.dataframe(missing[["日付", "生徒ID", "安全説明", "体調確認", "開始", "終了", "所見"]],
                     width="stretch", hide_index=True)

    # ── 学校への報告書 ──
    st.subheader("📄 学校への報告書")
    period = (f"{L['日付'].min():%Y/%m/%d} 〜 {L['日付'].max():%Y/%m/%d}" if not L.empty else "—")
    schools = "、".join(sorted(L["学校"].dropna().astype(str).unique())) or "—"
    themes = "、".join(dict.fromkeys(L["活動テーマ"].dropna().astype(str))) or "—"
    quals = "／".join(INSTRUCTORS.loc[INSTRUCTORS["区分"] == "保有", "資格・経験"])
    report = f"""探究学習 外部フィールド 実施報告書
{'（架空の記入例による試作）' if st.session_state.edu_is_sample else ''}
作成日：{dt.date.today():%Y/%m/%d}
実施場所：広島県三原市西部（スマートパン屋農家 圃場・ハウス）

1. 実施概要
  対象校：{schools}
  期間：{period}
  実施回数：{n_sessions} 回／参加生徒数：{n_students} 人／延べ学習時間：{total_h:.1f} 時間
  活動テーマ：{themes}

2. 安全管理
  安全説明の実施率：{safety_rate:.0f} %
  体調確認の実施率：{health_rate:.0f} %
  記入漏れ・要確認：{len(missing)} 件

3. 学習評価（5観点×4段階ルーブリック）
  観点：{'、'.join(AXES)}
  全生徒平均：初回 {avg_first:.2f} → 最新 {avg_last:.2f}

4. 指導者
  {quals}

5. 添付
  活動ログ.csv（生徒IDごとの日付・時刻・活動・安全確認・所見）
  ルーブリック評価.csv（評価日・観点別の段階）

※ 生徒は学校が付けた匿名IDで記録しています。氏名は扱っていません。
"""
    st.text_area("報告書（プレビュー）", report, height=360)
    st.download_button("報告書をテキストで保存", report.encode("utf-8-sig"),
                       f"探究実施報告書_{dt.date.today():%Y%m%d}.txt", "text/plain")

# ═════════════════════════════════════════════
# 5. 1回分のプログラム（提供内容）
# ═════════════════════════════════════════════
with tab_pkg:
    st.header("🤝 1回分のプログラム（案：90分）")
    st.write("試行前の案です。学校の目的や生徒の状況に合わせて、時間と内容は調整します。")
    st.dataframe(pd.DataFrame([
        ("0–15分", "安全説明・体調確認・圃場観察", "活動ログ（安全説明・体調確認）"),
        ("15–60分", "小麦の生育測定とデータ入力（① 計算する）", "活動ログ（取得したデータ）"),
        ("60–80分", "グラフ化と読み取り（② 可視化する）", "成果物"),
        ("80–90分", "振り返り：自分ならどう判断するか（③ 判断する）", "ルーブリック評価・所見"),
    ], columns=["時間", "内容", "残る記録"]), width="stretch", hide_index=True)

    st.subheader("学校にお渡しするもの")
    st.markdown(
        "- **活動ログ**（CSV）：生徒IDごとの日付・時刻・滞在時間・活動・安全確認\n"
        "- **ルーブリック評価**（CSV）：5観点×4段階、初回と最終の比較\n"
        "- **実施報告書**（テキスト）：回数・時間・安全管理・評価の要約・指導者\n"
        "- 生徒が作った**成果物**（観察シート・グラフ・発表資料）"
    )

    st.subheader("指導者の資格・経験")
    st.dataframe(INSTRUCTORS[["資格・経験", "区分"]], width="stretch", hide_index=True)

    st.subheader("つながる教科・入試")
    st.dataframe(pd.DataFrame([
        ("理科（科学と人間生活・生物基礎・化学基礎）", "発芽・発酵・土壌の観察と測定"),
        ("情報Ⅰ", "データの活用・Pythonでの可視化"),
        ("総合的な探究の時間", "問い→計算→可視化→判断の一連の過程"),
        ("総合型選抜・学校推薦型選抜", "探究の過程を示す記録（活動ログ・ルーブリック・成果物）"),
    ], columns=["教科・場面", "この畑での内容"]), width="stretch", hide_index=True)

    st.info("受け入れ体制は準備中で、試行プログラムの実施はまだありません（2027年度に1〜2回予定）。"
            "記録の様式へのご意見や、試行へのご相談はFacebookからお寄せください。")
    st.link_button("📘 Facebookで相談する", FACEBOOK_URL)
    try:
        st.page_link("app.py", label="受け入れ準備の状況は、ホームの「🤝 受け入れ体制」タブで公開しています", icon="🏠")
    except Exception:  # noqa: BLE001  単独起動時などリンク先が無い場合
        st.caption("受け入れ準備の状況は、ホームの「🤝 受け入れ体制」タブで公開しています。")

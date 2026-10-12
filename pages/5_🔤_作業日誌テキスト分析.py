"""
作業日誌テキスト分析 ─ 「困りごと」を数え、原文で確かめ、AIエージェントを入れる作業を決める
配置先: pages/5_🔤_作業日誌テキスト分析.py （Streamlit のマルチページ構成）

研究メモ（テキスト分析 課題3）の手順を画面にしたもの。骨格はリポジトリ共通の3段構え：
  0 匿名化 → ① 計算する（回数・件数・分母、KWIC、否定の判定）→ ② 可視化する → ③ 自分の条件で判断する
同じ手順のノートブック: notebooks/text_analysis_work_diary.ipynb

方針
  - 日誌の原文は、このページから外部の生成AIに送らない（AI呼び出しは一切ない）。
  - アップロードした日誌はそのセッション内だけで使い、サーバーには残さない。
  - 初期表示は架空の日誌36件（data/sample_work_diary.csv）。
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

import diary_text as dtx
import security_guard as sg

st.set_page_config(page_title="作業日誌テキスト分析", page_icon="🔤", layout="wide")

DATA = Path(__file__).parent.parent / "data"
SAMPLE = DATA / "sample_work_diary.csv"
SAMPLE_LABELS = DATA / "sample_work_diary_labels.csv"
SAMPLE_NAMES = ["山田", "佐藤"]            # 架空データ用の匿名化辞書
SAMPLE_PARTNERS = ["みどり青果", "ひかり製パン"]
REQUIRED = ["ID", "日付", "作業", "本文"]
LABELS = ["未判定", "困りごと", "否定", "保留"]

# 仮置きの対応づけ（③で使う）。困りごとの種類 → AIエージェント候補・必要なデータ
CANDIDATES = {
    "遅れ": ("天気予報と作業予定を突き合わせ、段取りの組み直し案を出す", "作業予定表・気象予報"),
    "故障": ("機械ごとの故障履歴を検索し、点検・部品交換を知らせる", "機械台帳・故障の記録"),
    "人手": ("作業量と出勤予定から、人手が足りない日を前もって知らせる", "出勤予定・作業ごとの所要時間"),
}

st.title("🔤 作業日誌テキスト分析")
st.caption("文字を数える。意味は、確かめる。 ── 小規模農業法人へのAIエージェント導入に向けた予備分析")

with st.container(border=True):
    st.markdown(
        "**研究メモ**：関心分野は、小規模農業法人へのAIエージェントの導入である。"
        "テキストは、従業員が毎日記入する作業日誌の自由記述（1日1件）とする。"
        "問いは「作業上の困りごとが、どの作業や時期に、どのような言葉で書かれているか」である。"
        "まず「遅れ」「故障」「人手」を含む日誌を作業別・月別に数え、該当した原文を読む。"
        "注意点は四つある。第一に、語の出現回数と日誌の件数を区別し、分母を示す。"
        "第二に、「故障はなかった」のような否定も一致するため、原文で確かめる。"
        "第三に、「壊れた」などの言い換えは漏れる。"
        "第四に、氏名や取引先名を匿名化してから分析し、外部のAIには入力しない。"
    )

# ------------------------------------------------------------
# サイドバー：データの選択
# ------------------------------------------------------------
with st.sidebar:
    st.header("日誌のデータ")
    source = st.radio("使うデータ", ["架空の記入例（36件）", "自分の日誌CSVを読み込む"])
    up = None
    if source.startswith("自分"):
        st.caption("列：`ID,日付,作業,本文`（`記入者` は任意）。日付は 2026-10-12 の形。")
        up = st.file_uploader("日誌CSV", type="csv", key="diary_up")
        st.caption("読み込んだ日誌はこのセッションの中だけで使い、サーバーには残りません。"
                   "このページは外部の生成AIを呼び出しません。")
    st.divider()
    st.caption("同じ手順を Google Colab で：`notebooks/text_analysis_work_diary.ipynb`")

if source.startswith("自分"):
    if up is None:
        st.info("左のサイドバーから日誌のCSVを読み込んでください。")
        st.stop()
    raw = sg.read_csv_safely(up, page="diary", kind="diary")
    if raw is None:
        st.stop()
    missing = [c for c in REQUIRED if c not in raw.columns]
    if missing:
        st.error(f"列が足りません：{', '.join(missing)}")
        st.stop()
    default_names, default_partners, sample_labels = "", "", None
else:
    raw = pd.read_csv(SAMPLE, encoding="utf-8-sig")
    default_names, default_partners = "\n".join(SAMPLE_NAMES), "\n".join(SAMPLE_PARTNERS)
    sample_labels = pd.read_csv(SAMPLE_LABELS, encoding="utf-8-sig")
    st.warning("表示しているのは**教材用の架空データ**です（実在の法人・従業員・取引先ではありません）。")

raw["ID"] = raw["ID"].astype(str)
raw["本文"] = raw["本文"].astype(str)
raw["月"] = pd.to_datetime(raw["日付"], errors="coerce").dt.strftime("%Y-%m")

# ------------------------------------------------------------
# 0 匿名化
# ------------------------------------------------------------
st.header("0｜分析の前に匿名化する")
a1, a2 = st.columns(2)
names = a1.text_area("氏名（1行に1つ。敬称の前の部分）", default_names, height=90)
partners = a2.text_area("取引先名（1行に1つ）", default_partners, height=90)
name_list = [w.strip() for w in names.splitlines() if w.strip()]
partner_list = [w.strip() for w in partners.splitlines() if w.strip()]

df = raw.copy()
df["本文"] = [dtx.mask(t, name_list, partner_list) for t in df["本文"]]
left = dtx.residual(df["本文"], name_list + partner_list)
changed = int((raw["本文"] != df["本文"]).sum())
if left:
    st.error(f"匿名化のあとに残っている語があります：{', '.join(left)}。ここで止めます。")
    st.stop()
st.success(f"置き換えた日誌：{changed} 件 ／ 辞書の語の残り：0 件")
if "記入者" in df.columns:
    st.caption("記入者の列は、最初から「記入者A」のような仮名にしておきます（画面には表示しません）。")
    df = df.drop(columns=["記入者"])
st.caption("⚠️ 辞書に載っていない名前は残ります。最後は人の目で確かめてください。")

# ------------------------------------------------------------
# ① 計算する
# ------------------------------------------------------------
st.header("① 現象を計算する：回数と件数（分母つき）")
kw_text = st.text_input("検索語（読点・空白で区切る）", "遅れ、故障、人手")
keywords = [w for w in kw_text.replace("、", " ").replace(",", " ").split() if w]
if not keywords:
    st.stop()

results = [dtx.search(df, kw) for kw in keywords]
summary = pd.DataFrame([{k: r[k] for k in ["語", "回数", "件数", "分母"]} for r in results])
summary["件数の割合"] = (summary["件数"] / summary["分母"]).map("{:.0%}".format)
summary["検索規則"] = [r["規則"] for r in results]
st.dataframe(summary, hide_index=True, width="stretch")
st.caption("**回数**＝その語が現れた数（1件に2回あれば2）／**件数**＝その語を含む日誌の数。"
           "ここで言えるのは「その文字列を含む日誌が何件あるか」だけで、困りごとの件数ではありません。")

with st.expander("KWIC：語の前後を並べて読む"):
    for kw in keywords:
        st.markdown(f"**{kw}**")
        st.dataframe(dtx.kwic(df, kw), hide_index=True, width="stretch")

st.subheader("原文を読んで判定する")
st.markdown(
    "| 判定 | 基準 |\n|---|---|\n"
    "| 困りごと | 作業・出荷・機械・人員の**支障が起きた（起きている）**ことを述べている |\n"
    "| 否定 | 「遅れはない」「故障なし」「人手は足りた」のように**支障がなかった**ことを述べている |\n"
    "| 保留 | 対象が作業ではない・解消の報告・予測など、本文だけでは決められない |"
)
hits = dtx.hit_table(df, keywords)
hits["素朴な規則"] = [dtx.naive_label(t) for t in hits["本文"]]
hits["人の判定"] = "未判定"
if sample_labels is not None:
    lab = sample_labels.set_index(["ID", "語"])["人の判定"]
    hits["人の判定"] = [lab.get((i, k), "未判定") for i, k in zip(hits["ID"], hits["語"])]
    st.caption("記入例では、人の判定をあらかじめ入れてあります。書きかえて一致率の変化を確かめられます。")

edited = st.data_editor(
    hits[["ID", "作業", "月", "語", "本文", "規則の判定", "素朴な規則", "人の判定"]],
    hide_index=True, width="stretch", key=f"judge_{source}_{kw_text}",
    disabled=["ID", "作業", "月", "語", "本文", "規則の判定", "素朴な規則"],
    column_config={"人の判定": st.column_config.SelectboxColumn("人の判定", options=LABELS, required=True)},
)
judged = edited[edited["人の判定"] != "未判定"]
m1, m2, m3 = st.columns(3)
m1.metric("判定した組（日誌×語）", f"{len(judged)} / {len(edited)}")
if len(judged):
    for col, box, note in [("素朴な規則", m2, "「ない」があれば否定"), ("規則の判定", m3, "語の直後の形で判定")]:
        ok = int((judged[col] == judged["人の判定"]).sum())
        box.metric(f"{col}と人の一致", f"{ok / len(judged):.0%}", help=f"{note}。{ok}/{len(judged)} 組")
    miss = judged[judged["規則の判定"] != judged["人の判定"]]
    if len(miss):
        with st.expander(f"規則と人が食い違った {len(miss)} 組（規則では決められない種類）"):
            st.dataframe(miss[["ID", "語", "本文", "規則の判定", "人の判定"]], hide_index=True, width="stretch")
st.caption("「人手が足り**ない**」は「ない」を含むのに困りごと。否定の規則は**語ごとに逆向き**になります。"
           "規則は手元のデータを見て作った後付けなので、別の月・別の法人の日誌で一致率を確かめ直します。")

syn = dtx.synonym_hits(df)
with st.expander(f"検索の漏れ：3語では拾えない言い換え（{len(syn)} 件）"):
    st.dataframe(syn, hide_index=True, width="stretch")
    st.caption("拾えなかった困りごとは、全件を読むか言い換えの辞書で探します。書かれなかった困りごとは数えられません。")

# ------------------------------------------------------------
# ② 可視化する
# ------------------------------------------------------------
st.header("② 数値を可視化する：どの作業・どの月に")
use_syn = st.toggle("言い換えで見つけた困りごとも含める", value=True)
confirmed = judged[judged["人の判定"] == "困りごと"][["ID", "語", "作業", "月"]]
if use_syn and len(syn):
    extra = syn[syn["規則の判定"] == "困りごと"].rename(columns={"分類": "語"})
    extra = extra.merge(df[["ID", "作業", "月"]], on="ID")[["ID", "語", "作業", "月"]]
    confirmed = pd.concat([confirmed, extra])

if confirmed.empty:
    st.info("①で「困りごと」と判定した組がまだありません。")
else:
    heat = confirmed.pivot_table(index="作業", columns="月", values="ID", aggfunc="count", fill_value=0)
    fig = px.imshow(heat, text_auto=True, aspect="auto", color_continuous_scale="YlOrBr",
                    labels=dict(x="月", y="作業", color="困りごと"))
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10))
    g1, g2 = st.columns([3, 2])
    g1.plotly_chart(fig, width="stretch")
    days = df.groupby("作業").size().rename("日誌の日数")
    rate = pd.concat([days, confirmed.groupby("作業").size().rename("困りごと")], axis=1).fillna(0)
    rate["日誌1件あたり"] = (rate["困りごと"] / rate["日誌の日数"]).round(2)
    g2.dataframe(rate.sort_values("日誌1件あたり", ascending=False), width="stretch")
    g2.caption("単位は「日誌×語」。作業ごとに日誌の日数が違うので、日数で割った値でも比べます。")

# ------------------------------------------------------------
# ③ 自分の条件で判断する
# ------------------------------------------------------------
st.header("③ 自分の条件で判断する：AIエージェントを最初に入れる作業")
st.caption("答えは法人ごとに違います。候補は困りごとの種類からの**仮置き**です。損失時間は日誌に書かれていないので、現場で聞いて入れます。")
rows = []
cols = st.columns(max(1, len(keywords)))
counts = confirmed["語"].value_counts() if not confirmed.empty else pd.Series(dtype=int)
for kw, c in zip(keywords, cols):
    with c:
        st.markdown(f"**{kw}**")
        loss = st.slider("1件あたりの損失時間(h)", 0.0, 8.0, {"遅れ": 2.0, "故障": 4.0, "人手": 3.0}.get(kw, 2.0),
                         0.5, key=f"loss_{kw}")
        ready = st.slider("データの準備度", 0.0, 1.0, {"遅れ": 1.0}.get(kw, 0.5), 0.1, key=f"ready_{kw}")
    agent, need = CANDIDATES.get(kw, ("（自分で書く）", "（自分で書く）"))
    n = int(counts.get(kw, 0))
    rows.append({"語": kw, "確認済みの件数": n, "損失時間の見込み(h)": n * loss,
                 "優先度": round(n * loss * ready, 1), "エージェント候補": agent, "必要なデータ": need})
decide = pd.DataFrame(rows).sort_values("優先度", ascending=False)
st.dataframe(decide, hide_index=True, width="stretch")
if len(decide) and decide["優先度"].max() > 0:
    top = decide.iloc[0]
    st.success(f"今の条件では「{top['語']}」が最上位：{top['エージェント候補']}（前提：{top['必要なデータ']}）")
st.info("この判断に必要なのに日誌に無いもの：困りごとで**止まった時間**・**影響した量**。"
        "次の一手は、自由記述を残したまま「止まった時間（分）」「影響（出荷・作業・品質）」の2欄を日誌に足すこと。")

st.divider()
st.download_button("判定結果をCSVで保存（匿名化済み）", sg.safe_csv(edited), "日誌_判定結果.csv", "text/csv")
st.caption("© スマートパン屋農家プロジェクト ｜ 初期表示は教材用の架空データです。")

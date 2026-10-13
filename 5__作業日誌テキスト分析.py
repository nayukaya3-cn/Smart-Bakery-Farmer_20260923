"""
作業日誌テキスト分析 ─ 「困りごと」を数え、原文で確かめ、AIエージェントを入れる作業を決める
配置先: pages/5_🔤_作業日誌テキスト分析.py （Streamlit のマルチページ構成）

研究メモ（テキスト分析 課題3）の手順を画面にしたもの。骨格はリポジトリ共通の3段構え：
  0 匿名化 → ① 計算する（回数・件数・分母、KWIC、否定の判定）→ ✅ 検証する → ② 可視化する → ③ 自分の条件で判断する
同じ手順のノートブック: notebooks/text_analysis_work_diary.ipynb

授業との対応
  第1回「テキストを『データ』として読む」：6工程（問い→データ→表現→計算→検証→解釈）、回数・件数・意味の区別、3行の報告
  第2回「生成AIと始めるPython」：for・if・カウンタ、手で数えた小さな例でAIのコードを検証、トレース表（DNCL）

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
# 入力用の Google フォーム（回答は法人のスプレッドシートに入り、ここには来ない）
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSenOoiE1iYKvD_dQeR9VUhPt-8q955rsvA4G_Gl7nY0FuXIuQ/viewform"

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

with st.expander("このページの道のり：6つの工程と、人・AI・Pythonの役割", expanded=False):
    st.markdown(
        "**数えることはコンピュータにできる。「何を1つと数えるか」を決めることと、"
        "「その数字が何を意味するか」を読むことは、人の仕事。**\n\n"
        "| 工程 | このページのどこ | 担当 | ここで決めること |\n|---|---|---|---|\n"
        "| 1 問い | 研究メモ | 人 | 大きすぎる問い（AIは役に立つか？）を、日誌で確かめられる大きさにする |\n"
        "| 2 データ | 📝入力・0 匿名化 | 人 | 1日1件＝分母。困りごとがない日も書く |\n"
        "| 3 表現 | ① 検索語 | 人 | 何を1つと数えるか（回数／日誌の件数／日誌×語の組） |\n"
        "| 4 計算 | ① 表 | Python | 言われたとおりに数える（意味は考えない） |\n"
        "| 5 検証 | ✅ 検証 | 人 | 手で数えた答えを**先に**決め、コードの結果と比べる |\n"
        "| 6 解釈 | ①判定・②・③・3行 | 人 | 原文に戻って意味を読み、言える範囲を決める |\n\n"
        "AI（生成AI）はコードの候補を出す係です。このページの部品 `diary_text.py` も、"
        "動いたから正しいとは考えず、✅ 検証で手計算と照らし合わせています。"
    )

# ------------------------------------------------------------
# 入力：Google フォーム → スプレッドシート → 匿名化CSV → このページ
# ------------------------------------------------------------
st.header("📝 日誌を入力する（Googleフォーム）")
f1, f2 = st.columns([1, 2])
with f1:
    st.link_button("作業日誌フォームを開く", FORM_URL, type="primary", width="stretch")
    st.caption("スマホからも入力できます。1日1件、困りごとがない日も「特に問題なし」と書きます（分母になります）。")
with f2:
    st.markdown(
        "| 段 | どこで | すること |\n|---|---|---|\n"
        "| 1 入力 | Googleフォーム | 日付・記入者（仮名）・作業・本文・止まった時間・影響 |\n"
        "| 2 集計 | 法人のスプレッドシート | 「日誌」シートに D001… で自動追記、「集計」シートが自動更新 |\n"
        "| 3 匿名化 | 同じスプレッドシート | メニュー「作業日誌 → 解析用CSVを作る」で氏名・取引先名を伏せたCSVを保存 |\n"
        "| 4 分析 | このページ | 左のサイドバーで「自分の日誌CSVを読み込む」→ そのCSVを選ぶ |"
    )
with st.expander("フォームをこの画面の中で開く"):
    st.iframe(FORM_URL + "?embedded=true", height=900)
st.caption("フォームの回答はこのページには届かず、このページから回答を読みに行くこともしません。"
           "分析に使うのは、手順3で匿名化したCSVだけです。")

# ------------------------------------------------------------
# サイドバー：データの選択
# ------------------------------------------------------------
with st.sidebar:
    st.header("日誌のデータ")
    source = st.radio("使うデータ", ["架空の記入例（36件）", "自分の日誌CSVを読み込む"])
    up = None
    if source.startswith("自分"):
        st.caption("フォームのスプレッドシートで「作業日誌 → 解析用CSVを作る」を実行して保存したCSVを選びます。"
                   "列：`ID,日付,作業,本文`（`記入者`・`止まった時間(分)`・`影響`・`備考` は任意）。")
        up = st.file_uploader("日誌CSV", type="csv", key="diary_up")
        st.caption("読み込んだ日誌はこのセッションの中だけで使い、サーバーには残りません。"
                   "このページは外部の生成AIを呼び出しません。")
    st.divider()
    st.link_button("📝 作業日誌フォーム", FORM_URL, width="stretch")
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
use_nfkc = st.toggle("表記ゆれをそろえる（NFKC：全角英数・半角カナ・濁点の分かれた文字など）", value=True)
if use_nfkc:
    before = df["本文"].copy()
    df["本文"] = [dtx.normalize(t) for t in df["本文"]]
    n_norm = int((before != df["本文"]).sum())
    st.caption(f"そろえた日誌：{n_norm} 件。見た目が同じ「が」でも `len` が 2 になる文字があり、"
               "そろえないと検索から漏れます（第1回 発展A1）。")
    name_list = [dtx.normalize(w) for w in name_list]
    partner_list = [dtx.normalize(w) for w in partner_list]
pre_mask = df["本文"].copy()
df["本文"] = [dtx.mask(t, name_list, partner_list) for t in df["本文"]]
left = dtx.residual(df["本文"], name_list + partner_list)
changed = int((pre_mask != df["本文"]).sum())
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
if use_nfkc:
    keywords = list(dict.fromkeys(dtx.normalize(w) for w in keywords))
if not keywords:
    st.stop()

results = [dtx.search(df, kw) for kw in keywords]
summary = pd.DataFrame([{k: r[k] for k in ["語", "回数", "件数", "分母"]} for r in results])
summary["件数の割合"] = (summary["件数"] / summary["分母"]).map("{:.0%}".format)
summary["検索規則"] = [r["規則"] for r in results]
st.dataframe(summary, hide_index=True, width="stretch")
st.caption("**回数**＝その語が現れた数（1件に2回あれば2）／**件数**＝その語を含む日誌の数。"
           "ここで言えるのは「その文字列を含む日誌が何件あるか」だけで、困りごとの件数ではありません。")
pair_n = int(summary["件数"].sum())
any_hit = df["本文"].apply(lambda t: any(k in t for k in keywords))
c1, c2, c3 = st.columns(3)
c1.metric("出現回数の合計", f"{int(summary['回数'].sum())} 回")
c2.metric("日誌×語の組", f"{pair_n} 組", help="1件の日誌に「遅れ」と「人手」があれば2組")
c3.metric("どれか1語を含む日誌", f"{int(any_hit.sum())} 件 / {len(df)} 件",
          help="重複を除いた日誌の数。分母は日誌の日数")
st.caption("同じデータでも「何を1つと数えるか」で数字が3通りになります。報告には単位と分母を必ず添えます。"
           "**件数が多い語が重要とは限りません**（件数は重要度の順位ではない）。")

with st.expander("Pythonの3つの道具：`len`・`count`・`in` を1件の日誌で試す"):
    pick = st.selectbox("日誌を選ぶ", df["ID"].tolist(),
                        index=df["ID"].tolist().index("D10") if "D10" in df["ID"].tolist() else 0)
    text = df.loc[df["ID"] == pick, "本文"].iloc[0]
    st.code(f'text = "{text}"', language="python")
    tool_rows = [{"コード": "len(text)", "結果": str(len(text)), "意味": "文字数（句読点も1文字）。満足度や重要度ではない"}]
    for kw in keywords:
        tool_rows += [
            {"コード": f'text.count("{kw}")', "結果": str(text.count(kw)), "意味": "出現回数（1件に2回あれば2）"},
            {"コード": f'"{kw}" in text', "結果": str(kw in text), "意味": "含むかどうか → 件数を数える材料"},
        ]
    st.dataframe(pd.DataFrame(tool_rows), hide_index=True, width="stretch")
    st.caption("D10「草刈機がまた故障。先週の故障と同じ所。」は count が 2、in は True。"
               "故障した日誌は**1件**で、しかも2回目の「故障」は過去の話です。")

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
# ✅ 検証する（第2回：AIのコードが動いても、正しいとは限らない）
# ------------------------------------------------------------
st.header("✅ 検証する：手で数えた答えとコードを照らし合わせる")
st.caption("このページの数字は `diary_text.py` が出しています。動いてエラーが出なくても、"
           "**目的と違う数**を出していることがあります。手で数えられる小さな例で確かめます。")

v1, v2 = st.columns([3, 2])
with v1:
    test_text = st.text_area("小さな例（1行が日誌1件）", "雨で遅れた。\n遅れ、遅れと言われた。\n特に問題なし。", height=110)
    test_word = st.text_input("数える語", keywords[0], key="test_word")
with v2:
    st.markdown("**① 人が先に答えを決める**")
    exp_ans = st.number_input("期待する件数（語を含む行の数）", 0, 100, 2)
    exp_occ = st.number_input("期待する回数（語が現れた数）", 0, 100, 3)
tests = [t for t in test_text.splitlines() if t.strip()]
tdf = pd.DataFrame({"ID": [f"T{i + 1:02d}" for i in range(len(tests))], "本文": tests})
got = dtx.search(tdf, test_word) if tests and test_word else {"件数": 0, "回数": 0}
check = pd.DataFrame([
    {"何を": "件数", "期待値（人）": exp_ans, "pandas版 search()": got["件数"],
     "for文版 count_answers()": dtx.count_answers(tests, test_word)},
    {"何を": "回数", "期待値（人）": exp_occ, "pandas版 search()": got["回数"],
     "for文版 count_answers()": dtx.count_occurrences(tests, test_word)},
])
check["一致"] = [
    "✅" if r["期待値（人）"] == r["pandas版 search()"] == r["for文版 count_answers()"] else "❌"
    for _, r in check.iterrows()
]
check = check.rename(columns={"for文版 count_answers()": "for文版"})
st.markdown("**② コードを実行して比べる**")
st.dataframe(check, hide_index=True, width="stretch")
if (check["一致"] == "❌").any():
    st.warning("食い違いがあります。手で数え直すか、コードが「件数」と「回数」のどちらを数えているかを確かめます。")
else:
    st.success("人の答え・pandas版・for文版の3つが一致しました。")
st.caption("件数と回数が**違う値になる例**（同じ行に2回出る行）を必ず1つ入れます。"
           "両方が同じ値の例では、取り違えに気づけません。")

with st.expander("よくある2つの間違い（エラーは出ないのに、数がずれる）"):
    w0, texts_all = keywords[0], df["本文"].tolist()
    st.code(
        "answer_count = 0                 # ① 繰り返しの「前」で 0 にする\n"
        "for text in texts:               # ② 1件ずつ取り出す\n"
        f'    if "{w0}" in text:            # ③ 含むなら\n'
        "        answer_count = answer_count + 1  # ④ 1を足す\n"
        "print(answer_count)              # ⑤ 全部終わってから表示", language="python")
    st.dataframe(pd.DataFrame([
        {"書き方": "正しい：in で数える", "結果": dtx.count_answers(texts_all, w0), "何を数えたか": "件数（目的どおり）"},
        {"書き方": "誤り1：count を足す", "結果": dtx.count_occurrences(texts_all, w0), "何を数えたか": "出現回数（1件に2回あれば2）"},
        {"書き方": "誤り2：for の中で 0 に戻す", "結果": dtx.count_answers_buggy(texts_all, w0),
         "何を数えたか": "最後の1件の分だけ（0か1）"},
    ]), hide_index=True, width="stretch")
    st.caption(f"「{w0}」の日誌全{len(df)}件で実行した結果。誤り2は、正の字を1票ごとに捨てているのと同じです。")

with st.expander("トレース表：カウンタの値を1件ずつ追う（共通テスト『情報Ⅰ』のDNCLと対応）"):
    n_tr = st.slider("追う件数", 3, min(12, len(df)), min(6, len(df)))
    st.dataframe(dtx.trace(df["本文"].head(n_tr), keywords[0], df["ID"].head(n_tr)),
                 hide_index=True, width="stretch")
    st.code(
        "answer_count = 0\n"
        "i を 0 から 要素数(texts)-1 まで 1 ずつ増やしながら繰り返す:\n"
        f'│ もし texts[i] が "{keywords[0]}" を含む ならば:\n'
        "│ └ answer_count = answer_count + 1\n"
        "表示する(answer_count)", language="text")

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

st.subheader("文字列が一致した件数 ≠ 困りごとの件数")
gap = summary[["語", "件数"]].rename(columns={"件数": "検索で一致"}).copy()
jc = judged.groupby("語")["人の判定"].value_counts().unstack(fill_value=0) if len(judged) else pd.DataFrame()
for lab in ["困りごと", "否定", "保留"]:
    gap[f"読んで{lab}"] = [int(jc.loc[k, lab]) if k in jc.index and lab in jc.columns else 0 for k in gap["語"]]
gap["未判定"] = gap["検索で一致"] - gap[["読んで困りごと", "読んで否定", "読んで保留"]].sum(axis=1)
long = gap.melt(id_vars="語", value_vars=["読んで困りごと", "読んで否定", "読んで保留", "未判定"],
                var_name="原文を読んだ結果", value_name="件数")
fig2 = px.bar(long, x="件数", y="語", color="原文を読んだ結果", orientation="h",
              color_discrete_map={"読んで困りごと": "#c2410c", "読んで否定": "#64748b",
                                  "読んで保留": "#cbd5e1", "未判定": "#e5e7eb"})
fig2.update_layout(height=60 + 50 * len(gap), margin=dict(l=10, r=10, t=10, b=10), legend_title_text="")
st.plotly_chart(fig2, width="stretch")
st.caption("棒の全長が「検索で一致した日誌の件数」、濃い部分が「原文を読んで困りごとと確かめた件数」。"
           "割合を報告するときは、どちらの割合かを書き分けます（例：「遅れ」を含む日誌の割合 ≠ 遅れが起きた日の割合）。")

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
st.latex(r"\text{優先度} = \text{確認済みの件数} \times \text{1件あたりの損失時間} \times \text{データの準備度}")
decide = pd.DataFrame(rows).sort_values("優先度", ascending=False)
st.dataframe(decide, hide_index=True, width="stretch")
if len(decide) and decide["優先度"].max() > 0:
    top = decide.iloc[0]
    st.success(f"今の条件では「{top['語']}」が最上位：{top['エージェント候補']}（前提：{top['必要なデータ']}）")
st.info("この判断に必要なのに日誌に無いもの：困りごとで**止まった時間**・**影響した量**。"
        "次の一手は、自由記述を残したまま「止まった時間（分）」「影響（出荷・作業・品質）」の2欄を日誌に足すこと。")

# ------------------------------------------------------------
# 3行の報告（第1回 E09）：観測と解釈を分け、解釈にはIDと原文を根拠として付ける
# ------------------------------------------------------------
st.header("📝 3行で報告する：観測／解釈と根拠／限界")
rep_word = st.selectbox("報告する語", keywords, key="rep_word")
draft = dtx.three_lines(rep_word, results[keywords.index(rep_word)], judged)
report = st.text_area("下書き（自分の言葉に書きかえる）", draft, height=150, key=f"rep_{rep_word}_{len(judged)}")
st.caption("観測＝数えた事実（単位と分母つき）。解釈＝意味の読み取り（IDと原文を根拠に）。"
           "限界＝拾えないもの・一般化できない理由。生成した下書きをそのまま出さず、原文を読み直して直します。")
st.download_button("3行の報告を保存（.txt）", report.encode("utf-8"), f"3行報告_{rep_word}.txt", "text/plain")

st.divider()
st.download_button("判定結果をCSVで保存（匿名化済み）", sg.safe_csv(edited), "日誌_判定結果.csv", "text/csv")
st.caption("© スマートパン屋農家プロジェクト ｜ 初期表示は教材用の架空データです。")

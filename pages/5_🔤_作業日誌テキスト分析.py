"""
作業日誌テキスト分析＋画像分析 ─ 「困りごと」を数え、原文と写真で確かめ、AIエージェントを入れる作業を決める
配置先: pages/5_🔤_作業日誌テキスト分析.py （Streamlit のマルチページ構成）

研究メモ（テキスト分析 課題3）の手順を画面にしたもの。骨格はリポジトリ共通の3段構え：
  0 匿名化 → ① 計算する（回数・件数・分母、KWIC、否定の判定）→ 🖼️ 写真を読む（Claude）→ ✅ 検証する
  → ② 可視化する → ③ 自分の条件で判断する
同じ手順のノートブック: notebooks/text_analysis_work_diary.ipynb

授業との対応
  第1回「テキストを『データ』として読む」：6工程（問い→データ→表現→計算→検証→解釈）、回数・件数・意味の区別、3行の報告
  第2回「生成AIと始めるPython」：for・if・カウンタ、手で数えた小さな例でAIのコードを検証、トレース表（DNCL）

方針
  - 日誌の原文（テキスト）は、このページから外部の生成AIに送らない。
  - 画像分析（diary_vision.py）で Claude に渡すのは、位置情報（Exif）を消して縮小した写真1枚と固定の指示文だけ。
    渡すのは利用者が操作したときに限る（Claude.ai に自分で貼る／APIキーがあるときだけボタンで送る）。
    Claude の答えは語彙で検査し、人が確かめてから使う（Human-in-the-Loop）。
  - アップロードした日誌はそのセッション内だけで使い、サーバーには残さない。
  - 初期表示は架空の日誌36件（data/sample_work_diary.csv）。
  - 写真はリポジトリの assets/ に取り込み済みのものだけを参照する（diary_photos.py）。
    日誌IDの名前（assets/diary/YYYYMMDD/D012_1.jpg）か、日付フォルダ（assets/YYYYMMDD/）で結びつけ、
    画面には位置情報（Exif）を外して縮小した画像だけを出す。
"""
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

import diary_photos as dp
import diary_text as dtx
import diary_vision as dv
import security_guard as sg

st.set_page_config(page_title="作業日誌テキスト分析＋画像分析", page_icon="🔤", layout="wide")

DATA = Path(__file__).parent.parent / "data"
ASSETS = Path(__file__).parent.parent / "assets"
MAX_PHOTO_ZIP = 100 * 1024 * 1024
SAMPLE = DATA / "sample_work_diary.csv"
SAMPLE_LABELS = DATA / "sample_work_diary_labels.csv"
SAMPLE_PHOTO_AI = DATA / "sample_photo_ai.csv"   # 取り込み済みの写真に Claude が付けたタグ（記入例・人の確認前）
CLAUDE_AI_URL = "https://claude.ai/new"
SAMPLE_NAMES = ["山田", "佐藤"]            # 架空データ用の匿名化辞書
SAMPLE_PARTNERS = ["みどり青果", "ひかり製パン"]
REQUIRED = ["ID", "日付", "作業", "本文"]
LABELS = ["未判定", "困りごと", "否定", "保留"]
# 入力用の Google フォーム（回答は法人のスプレッドシートに入り、ここには来ない）
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSenOoiE1iYKvD_dQeR9VUhPt-8q955rsvA4G_Gl7nY0FuXIuQ/viewform"

# 写真の「圃場の観察」→ AIエージェント候補・必要なデータ（③で使う。仮置き）
OBS_AGENTS = {
    "病害の疑い": ("感染期（5〜6月）の前に防除の時期を知らせ、病斑の面積率を写真の時系列で追う", "同じ木の写真の時系列・降雨"),
    "伝染源": ("冬の落葉・腐れ果の処分を作業予定に入れる", "落葉の写真・作業予定表"),
    "着果過多": ("摘果の時期と量を知らせる（隔年結果を防ぐ）", "木ごとの着果数（ベイズ推定）・前年の収量"),
    "収穫適期": ("色づきの分布から収穫の順番を組む（強化学習の題材）", "果実の色の写真・天気・人手"),
    "獣害の誘因": ("取り残し・落果を減らす収穫と加工の段取りを組む", "未収穫の木の一覧・加工の受け入れ先"),
    "雑草の繁茂": ("草刈りの時期を作業予定に入れる", "通路・株元の写真・作業予定表"),
}
# 観察の語が日誌の本文に書かれているかを確かめる語（テキストで拾えるか）
OBS_WORDS = {
    "病害の疑い": r"病|斑点|黄変|カビ|白い粉", "伝染源": r"落葉|落ち葉|腐", "着果過多": r"摘果|実が多|枝が(?:折|垂)",
    "収穫適期": r"色づ|熟", "獣害の誘因": r"カラス|イノシシ|サル|獣|鳥", "雑草の繁茂": r"雑草|草が(?:伸|茂|生)",
}

# 仮置きの対応づけ（③で使う）。困りごとの種類 → AIエージェント候補・必要なデータ
CANDIDATES = {
    "遅れ": ("天気予報と作業予定を突き合わせ、段取りの組み直し案を出す", "作業予定表・気象予報"),
    "故障": ("機械ごとの故障履歴を検索し、点検・部品交換を知らせる", "機械台帳・故障の記録"),
    "人手": ("作業量と出勤予定から、人手が足りない日を前もって知らせる", "出勤予定・作業ごとの所要時間"),
}

st.title("🔤 作業日誌テキスト分析＋画像分析")
st.caption("文字を数える。写真を読む。意味は、確かめる。 ── 小規模農業法人へのAIエージェント導入に向けた予備分析")

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
        "さらに、日誌に添えた写真を Claude で読み、**テキストに書かれた困りごとが写真でも見えるか**、"
        "**書かれていない困りごとが写真にだけ写っていないか**を突き合わせる（写真は位置情報を消してから渡す）。"
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
        "| 6 解釈 | ①判定・②・③・3行 | 人 | 原文に戻って意味を読み、言える範囲を決める |\n"
        "| ＋ 写真 | 🖼️ 画像分析 | Claude → 人 | Claude は決まった語彙でタグを付ける係。合っているかは人が確かめる |\n\n"
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
    st.caption("スマホからも入力できます。1日1件、困りごとがない日も「特に問題なし」と書きます（分母になります）。"
               "**困りごとがあった日は、その様子を1枚撮ります**（写真が日誌IDで結びつき、🖼️ 画像分析の根拠になります）。")
with f2:
    st.markdown(
        "| 段 | どこで | すること |\n|---|---|---|\n"
        "| 1 入力 | Googleフォーム | 日付・記入者（仮名）・作業・本文・止まった時間・影響・**写真（困りごとの日は1枚・5枚まで）** |\n"
        "| 2 集計 | 法人のスプレッドシート | 「日誌」シートに D001… で自動追記、「集計」シートが自動更新 |\n"
        "| 3 匿名化 | 同じスプレッドシート | メニュー「作業日誌 → 解析用CSVを作る」で氏名・取引先名を伏せたCSVを保存 |\n"
        "| 4 分析 | このページ | 左のサイドバーで「自分の日誌CSVを読み込む」→ そのCSVを選ぶ |\n"
        "| 5 写真 | 同じスプレッドシート → このページ → GitHub | 「写真をZIPで保存（assets用）」→ 下の「写真をassetsに取り込む」で位置情報を消す → `assets/` に置く |"
    )
with st.expander("フォームをこの画面の中で開く"):
    st.iframe(FORM_URL + "?embedded=true", height=900)
st.caption("フォームの回答はこのページには届かず、このページから回答を読みに行くこともしません。"
           "分析に使うのは、手順3で匿名化したCSVだけです。")

with st.expander("📷 写真をassetsに取り込む（位置情報を消してから置く）"):
    st.markdown(
        "フォームに届いた写真は、スプレッドシートのメニュー「作業日誌 → **写真をZIPで保存（assets用）**」で、"
        "`diary/20261018/D012_1.jpg` の形のZIPになります。スマホの写真には**撮った場所（GPS）**が残ることがあるので、"
        "公開リポジトリに置く前にここで消します。\n\n"
        "1. ZIPを読み込む → 2. 位置情報を消して縮小したZIPを保存 → 3. 写真を目で確かめる（人の顔・車のナンバー・看板） → "
        "4. 展開して `diary` フォルダごと、リポジトリの `assets/` にアップロード"
    )
    zup = st.file_uploader("写真のZIP（diary_photos_YYYYMM.zip）", type="zip", key="photo_zip")
    if zup is not None and sg.check_upload(zup, MAX_PHOTO_ZIP, page="diary", kind="photo_zip"):
        try:
            cleaned, rep_df = dp.clean_zip(zup.getvalue())
        except Exception as e:  # noqa: BLE001  壊れたZIP・上限超え
            sg.log_event("photo_zip_rejected", "WARNING", page="diary", error=type(e).__name__)
            st.error(f"ZIPを処理できませんでした：{e}" if isinstance(e, ValueError) else "ZIPを開けませんでした。")
        else:
            ok = rep_df[rep_df["結果"] == "入れた"]
            st.success(f"{len(ok)} 枚を入れました（位置情報を消した写真：{int((ok['メモ'] == '位置情報を消した').sum())} 枚）。")
            st.dataframe(rep_df, hide_index=True, width="stretch")
            st.download_button("位置情報を消したZIPを保存", cleaned, "diary_photos_clean.zip", "application/zip")
    st.caption("読み込んだZIPはこのセッションの中だけで処理し、サーバーには残しません。"
               "iPhoneの HEIC 形式は読めないので、カメラの設定（フォーマット → 互換性優先）で JPEG にしてください。"
               "撮るときに位置情報をオフにしておくのが、いちばん確実です。")

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
    show_photos = st.toggle("取り込み済みの写真（assets）を参照する", value=True,
                            help="assets/diary/日付/日誌ID_番号.jpg と、日付フォルダ assets/YYYYMMDD/ の写真を日誌に結びつけます")
    photo_days = 0
    if show_photos:
        photo_days = st.slider("日付フォルダの写真を何日ずれまで結びつけるか", 0, 3,
                               2 if source.startswith("架空") else 0,
                               help="0 なら同じ日だけ。日誌IDの名前の写真は、日付に関係なく結びつきます")
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
if "写真の説明" in df.columns:
    df["写真の説明"] = [dtx.mask(t, name_list, partner_list) for t in df["写真の説明"].fillna("").astype(str)]
left = dtx.residual(list(df["本文"]) + (list(df["写真の説明"]) if "写真の説明" in df.columns else []),
                    name_list + partner_list)
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

# ------------------------------------------------------------
# 📷 原文と一緒に写真で確かめる（assets に取り込み済みの写真）
# ------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=600)
def _scan_assets(root: str) -> pd.DataFrame:
    return dp.scan(Path(root))


@st.cache_data(show_spinner=False, max_entries=64)
def _photo(path: str):
    return dp.clean_image(Path(path), max_side=900)


if show_photos:
    st.subheader("📷 写真で確かめる（取り込み済みの assets）")
    photos = _scan_assets(str(ASSETS))
    linked = dp.link(df, photos, days=photo_days)
    if linked.empty:
        st.info("この日誌に結びつく写真は、まだ assets にありません。"
                "フォームの写真は上の「📷 写真をassetsに取り込む」の手順で置くと、日誌IDで結びつきます。")
    else:
        per = linked.groupby("ID").size()
        hit_ids = [i for i in dict.fromkeys(edited["ID"]) if i in per.index]
        p1, p2, p3 = st.columns(3)
        p1.metric("写真のある日誌", f"{per.size} 件 / {len(df)} 件")
        p2.metric("結びついた写真", f"{len(linked)} 枚")
        p3.metric("そのうち困りごと候補の日誌", f"{len(hit_ids)} 件", help="①の検索語を含む日誌")
        only_hits = st.toggle("困りごと候補（検索語を含む日誌）だけを選ぶ", value=bool(hit_ids))
        ids = hit_ids if only_hits and hit_ids else list(per.index)
        pick_id = st.selectbox("日誌を選ぶ", ids,
                               format_func=lambda i: f"{i}（写真 {per[i]} 枚）", key="photo_pick")
        row = df[df["ID"] == pick_id].iloc[0]
        st.markdown(f"**{pick_id}｜{row['日付']}｜{row.get('作業', '')}**　{row['本文']}")
        if "写真の説明" in df.columns and str(row.get("写真の説明", "")).strip():
            st.caption(f"写真の説明：{row['写真の説明']}")
        sel = linked[linked["ID"] == pick_id]
        cols = st.columns(3)
        for k, (_, ph) in enumerate(sel.iterrows()):
            with cols[k % 3]:
                try:
                    st.image(_photo(str(ph["パス"])), width="stretch")
                except Exception:  # noqa: BLE001
                    st.warning(f"表示できませんでした：{Path(ph['パス']).name}")
                    continue
                st.caption(f"{ph['説明']}｜{ph['結びつけ方']}｜`{Path(ph['パス']).relative_to(ASSETS.parent)}`")
        if any(dp.has_gps(Path(p)) for p in sel["パス"]):
            st.warning("この中に位置情報（GPS）が残った写真があります。画面では消して表示していますが、"
                       "リポジトリのファイルには残っています。`python diary_photos.py --strip assets` で消してください。")
        st.caption("「同じ日」「近い日」は日付だけで結びつけたもので、その作業の写真とは限りません。"
                   "日誌IDで結びついた写真（フォームから取り込んだもの）を根拠に使います。")
        with st.expander("結びつけの一覧（CSVで保存できます）"):
            out = linked.assign(パス=[str(Path(p).relative_to(ASSETS.parent)) for p in linked["パス"]])
            st.dataframe(out, hide_index=True, width="stretch")
            st.download_button("日誌と写真の対応をCSVで保存", sg.safe_csv(out), "日誌_写真の対応.csv", "text/csv")

# ------------------------------------------------------------
# 🖼️ 画像分析：写真を Claude で読み、テキストと突き合わせる（diary_vision.py）
# ------------------------------------------------------------
ROOT = ASSETS.parent
img_tab = pd.DataFrame(columns=["ID", "語", "テキストの判定", "写真の手がかり", "写真の確信度", "突き合わせ"])
obs_hit = pd.DataFrame(columns=["パス", "観察", "確信度", "手がかり"])   # ③で使う（確信度がしきい値以上の観察）


@st.cache_data(show_spinner=False, max_entries=256)
def _metrics(path: str) -> dict:
    return dv.metrics(dv.load_small(Path(path), max_side=512))


@st.cache_data(show_spinner=False, max_entries=64)
def _send_bytes(path: str) -> bytes:
    return dv.to_jpeg_bytes(dv.load_small(Path(path)))


@st.cache_data(show_spinner=False, max_entries=16)
def _batch_zip(paths: tuple[str, ...]) -> bytes:
    return dv.batch_zip([Path(x) for x in paths])


if show_photos:
    st.header("🖼️ 画像分析：写真を Claude で読み、テキストと突き合わせる")
    with st.container(border=True):
        st.markdown(
            "| 段 | 担当 | すること |\n|---|---|---|\n"
            "| ① 手元で数える | Python | 明るさ・ピント・緑の割合・白い割合。**AIは使わない**。空白や資料らしい写真はここで外せる |\n"
            "| ① タグを付ける | Claude | 決まった語彙から「種類・場面・写っているもの・困りごとの手がかり・写り込み」を選ぶ |\n"
            "| ① 圃場を観察する | Claude | 病害の疑い・伝染源・着果過多・収穫適期など**作物の状態**と、判定を確かにする**次に撮る1枚**・見える果実数 |\n"
            "| ✅ 確かめる | 人 | Claude のタグが合っているかを見て、一致率を出す |\n"
            "| ② 突き合わせる | Python → 人 | テキストの判定と写真の手がかりを並べ、食い違った日誌の原文を読み直す |\n"
            "| ② ベイズで見積もる | Python → 人 | 区画ごとの見える果実数から、木1本の果実数を**不確実性つき**で見積もる |\n"
            "| ③ 判断に足す | 人 | 写真で裏づけられた困りごと・観察を、優先度とエージェント候補の材料に加える |"
        )
        st.caption(f"Claude に渡すのは「位置情報を消して長い辺を1024pxに縮めた写真（一度に{dv.MAX_BATCH}枚まで）」と「固定の指示文」だけです。"
                   "日誌の本文・ID・日付・ファイル名は渡しません。答えは語彙で検査し、語彙に無い答えや写真の中の文字による指示は捨てます。")

    photos_all = _scan_assets(str(ASSETS))
    linked_all = dp.link(df, photos_all, days=photo_days)
    scope = st.radio("解析する写真", ["日誌に結びついた写真", "assets の写真すべて"], horizontal=True, key="img_scope")
    paths = (list(dict.fromkeys(linked_all["パス"])) if scope.startswith("日誌") else
             list(photos_all.loc[photos_all["日付"].notna(), "パス"]))
    if not paths:
        st.info("解析できる写真がまだありません。上の「📷 写真をassetsに取り込む」の手順で写真を置いてください。")
    else:
        # ── ① 手元で数える（AIなし） ──
        mt = pd.DataFrame([{"キー": dv.key(p, ROOT), **_metrics(str(p))} for p in paths])
        mt["目安"] = [("・".join(dv.quality_flags(r)) or "送ってよい") for r in mt.to_dict("records")]
        n_skip = int((mt["目安"] != "送ってよい").sum())
        q1, q2, q3 = st.columns(3)
        q1.metric("対象の写真", f"{len(mt)} 枚")
        q2.metric("Claude に送らずに済む写真", f"{n_skip} 枚", help="空白・資料らしい（白い割合が50%以上）・暗い・ボケ")
        q3.metric("送る候補", f"{len(mt) - n_skip} 枚")
        with st.expander("① 手元で数えた値（写真ごと）"):
            st.dataframe(mt, hide_index=True, width="stretch")
            st.caption("ピント＝ラプラシアン（隣の画素との差）の分散。小さいほどボケている。"
                       "白い割合＝ほぼ白の画素の割合。紙や画面を撮った写真で大きくなる。境目の値は手元の写真で決めた仮置き。")

        # ── ① Claude にタグを付けてもらう ──
        st.session_state.setdefault("photo_ai", {})
        use_sample = st.toggle("記入例の解析結果（Claude が付けたタグ・人の確認前）を使う", value=True,
                               help=f"{SAMPLE_PHOTO_AI.relative_to(ROOT)}：assets の写真に、開発時に Claude が付けたタグ")
        base = dv.load_results(SAMPLE_PHOTO_AI) if use_sample else None
        session = pd.DataFrame(list(st.session_state.photo_ai.values()), columns=dv.RESULT_COLS)
        ai_res = dv.merge_results(base, session)

        st.subheader("Claude で読む（1枚ずつ／まとめて）")
        keys = list(mt["キー"])
        done = set(ai_res["パス"])
        flag = mt.set_index("キー")["目安"]
        pick_k = st.selectbox("写真を見る", keys, key="img_pick",
                              format_func=lambda k: f"{'✅' if k in done else '　'} {k}（{flag[k]}）")
        pick_p = paths[keys.index(pick_k)]
        sendable = [k for k in keys if flag[k] == "送ってよい"]
        def _fill_batch() -> None:
            todo = [k for k in sendable if k not in done][:dv.MAX_BATCH]
            st.session_state.img_batch = todo or [pick_k]
            if not todo:
                st.session_state["img_msg"] = "「送ってよい」写真は、すべて読み終わっています。"

        if "img_batch" not in st.session_state:
            st.session_state.img_batch = [pick_k]
        st.session_state.img_batch = [k for k in st.session_state.img_batch if k in keys] or [pick_k]
        batch = st.multiselect(
            f"Claude に読ませる写真（{dv.MAX_BATCH}枚まで。貼る順＝番号）", keys,
            max_selections=dv.MAX_BATCH, key="img_batch",
            help="最初は上で見ている1枚。「送ってよい」写真だけを選ぶと、資料や空白で回数を使わずに済みます")
        st.button(f"まだ読んでいない「送ってよい」写真を{dv.MAX_BATCH}枚まで選ぶ", key="img_fill", on_click=_fill_batch)
        batch_p = [paths[keys.index(k)] for k in batch]
        tag = f"{len(batch)}_{abs(hash(tuple(batch))) % 10**8}"

        def _take(res: dict[int, dict], how: str) -> None:
            for no, r in res.items():
                k = batch[no - 1]
                st.session_state.photo_ai[k] = {"パス": k, **r, "出どころ": how}

        v1, v2 = st.columns([2, 3])
        with v1:
            st.image(_photo(str(pick_p)), width="stretch")
            ids = linked_all.loc[linked_all["パス"] == pick_p, ["ID", "結びつけ方"]].drop_duplicates()
            if len(ids):
                st.caption("結びついた日誌：" + "、".join(f"{a}（{b}）" for a, b in ids.itertuples(index=False)))
            cur = ai_res[ai_res["パス"] == pick_k]
            if len(cur):
                r = cur.iloc[0]
                ob = dv.obs_table(cur)
                fr = r["見える果実数"]
                st.markdown(
                    f"**{r['種類']}｜{r['場面']}**　{r['説明']}  \n写っているもの：{r['写っているもの'] or '—'}  \n"
                    f"困りごとの手がかり：{r['手がかり'] or 'なし'}  \n"
                    f"圃場の観察：{'、'.join(f'{a} {b:.1f}（{c}）' for a, b, c in ob[['観察', '確信度', '手がかり']].itertuples(index=False)) or 'なし'}  \n"
                    f"次に撮る1枚：{r['次の1枚'] or '—'}　見える果実数：{'—' if pd.isna(fr) else int(fr)}  \n"
                    f"（{r['出どころ']}）")
        with v2:
            if not batch:
                st.info("読ませる写真を1枚以上選んでください。")
            tab_web, tab_api = st.tabs(["Claude.ai で読む（APIキー不要）", "API で読む（任意）"])
            with tab_web:
                if batch:
                    st.markdown(f"1. 写真{'' if len(batch) == 1 else f'{len(batch)}枚（ZIP）'}を保存する　"
                                "2. Claude.ai に写真と指示文を貼る（ZIPは展開して**番号順に**貼る）　3. 返事を下に貼る")
                    c1, c2 = st.columns(2)
                    if len(batch) == 1:
                        c1.download_button("① 写真を保存（位置情報なし）", _send_bytes(str(batch_p[0])),
                                           "01.jpg", "image/jpeg", width="stretch")
                    else:
                        c1.download_button(f"① 写真{len(batch)}枚をZIPで保存（位置情報なし）",
                                           _batch_zip(tuple(map(str, batch_p))), "claude_photos.zip",
                                           "application/zip", width="stretch")
                    c2.link_button("② Claude.ai を開く", CLAUDE_AI_URL, width="stretch")
                    st.code(dv.prompt(len(batch)), language="text")
                    st.caption("右上のボタンで指示文をコピーできます。写真の名前は番号（01.jpg…）だけで、日誌の情報もパスも含みません。")
                    with st.expander("番号と写真の対応（手元の確認用。Claude には渡さない）"):
                        st.dataframe(pd.DataFrame({"番号": range(1, len(batch) + 1), "写真": batch}),
                                     hide_index=True, width="stretch")
                    reply = st.text_area("③ Claude の返事を貼る", height=140, key=f"reply_{tag}")
                    if st.button("検査して取り込む", key=f"take_{tag}") and reply.strip():
                        try:
                            res = dv.parse_many(reply, len(batch))
                        except (ValueError, json.JSONDecodeError) as e:
                            st.error(f"取り込めませんでした：{e}")
                        else:
                            _take(res, "Claude.ai（貼り付け）")
                            sg.log_event("photo_ai_pasted", "INFO", page="diary", n=len(res))
                            miss = len(batch) - len(res)
                            st.session_state["img_msg"] = f"{len(res)} 枚を取り込みました" + (f"（{miss} 枚は番号が合わず捨てました）" if miss else "")
                            st.rerun()
                    if st.session_state.get("img_msg"):
                        st.success(st.session_state.pop("img_msg"))
            with tab_api:
                if not dv.ai_available():
                    st.info("APIキー（ANTHROPIC_API_KEY）が設定されていないので、この方法は使えません。"
                            "左の「Claude.ai で読む」を使ってください。")
                elif batch:
                    st.caption(f"モデル：`{dv.AI_MODEL}`。選んだ写真をまとめて1回で送ります（1回の訪問で "
                               f"{sg.AI_CALLS_PER_SESSION} 回まで）。空白・資料らしい写真は送らないでください。")
                    if st.button(f"🤖 選んだ {len(batch)} 枚を Claude に送る", key=f"api_{tag}") and sg.ai_quota_ok("diary_vision"):
                        with st.spinner("Claude が写真を読んでいます…"):
                            try:
                                res = dv.analyze_api([dv.load_small(Path(x)) for x in batch_p])
                            except Exception as e:  # noqa: BLE001  通信・JSONの失敗
                                sg.log_event("photo_ai_failed", "WARNING", page="diary", error=type(e).__name__)
                                st.error("Claude の結果を受け取れませんでした。Claude.ai で読む方法を使ってください。")
                            else:
                                _take(res, "Claude API")
                                st.rerun()

        # ── ✅ 人が確かめる ──
        res_t = ai_res[ai_res["パス"].isin(keys)].copy()
        if res_t.empty:
            st.info("この範囲の写真には、まだ Claude のタグがありません。上で1枚ずつ読んでください。")
        else:
            st.subheader("✅ Claude のタグを人が確かめる")
            res_t["困りごと（Claude）"] = [
                "・".join(f"{k}{r[k]:.1f}" for k in dv.TROUBLES if r[k] > 0) or "なし" for _, r in res_t.iterrows()]
            res_t["種類（人）"] = res_t["種類"]
            res_t["手がかりの確認"] = "未確認"
            chk = st.data_editor(
                res_t[["パス", "種類", "種類（人）", "困りごと（Claude）", "手がかり", "説明", "手がかりの確認"]],
                hide_index=True, width="stretch", key=f"img_check_{use_sample}_{len(res_t)}",
                disabled=["パス", "種類", "困りごと（Claude）", "手がかり", "説明"],
                column_config={
                    "種類（人）": st.column_config.SelectboxColumn("種類（人）", options=dv.KINDS, required=True),
                    "手がかりの確認": st.column_config.SelectboxColumn(
                        "手がかりの確認", options=["未確認", "正しい", "誤り（無いのに有る）", "見落とし（有るのに無い）"],
                        required=True),
                })
            seen = chk[chk["手がかりの確認"] != "未確認"]
            k1, k2, k3 = st.columns(3)
            k1.metric("種類の一致", f"{int((chk['種類'] == chk['種類（人）']).sum())} / {len(chk)}",
                      help="人が直さなかった行＝一致。直したら不一致として数える")
            k2.metric("手がかりを確かめた写真", f"{len(seen)} / {len(chk)}")
            k3.metric("手がかりの正答率", f"{(seen['手がかりの確認'] == '正しい').mean():.0%}" if len(seen) else "—",
                      help="確かめた写真のうち「正しい」の割合。見落としと誤りは別に数える")
            if len(seen):
                st.caption("　".join(f"{k}：{v} 枚" for k, v in seen["手がかりの確認"].value_counts().items()))
            st.caption("一致率が低い項目は、まだ Claude に任せられません。一致率は**この写真の束での値**で、"
                       "別の季節・別の圃場で確かめ直します（テキストの規則と同じ）。")

            pv = res_t[res_t[list(dv.PRIVACY.values())].any(axis=1)]
            pv = pv[pv[["人の顔", "車のナンバー", "看板・取引先名"]].any(axis=1)]
            if len(pv):
                st.warning(f"公開前に人の目で確かめる写真が {len(pv)} 枚あります（人の顔・車のナンバー・看板）："
                           + "、".join(pv["パス"].map(lambda x: Path(x).name).head(6)))

            # ── ② 可視化する ──
            st.subheader("② 可視化する：手元の数値と Claude のタグ")
            g1, g2 = st.columns(2)
            sc = mt.merge(res_t[["パス", "種類", "場面"]], left_on="キー", right_on="パス", how="inner")
            fig_s = px.scatter(sc, x="白い割合", y="緑の割合", color="種類", hover_data=["キー", "場面"],
                               color_discrete_map={"現場写真": "#15803d", "資料・画面": "#64748b", "判別できない": "#cbd5e1"})
            fig_s.add_vline(x=0.5, line_dash="dot", line_color="#94a3b8")
            fig_s.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="Claude の種類")
            g1.plotly_chart(fig_s, width="stretch")
            g1.caption("点線（白い割合50%）の右は「資料らしい」。Claude の判定と手元の数値がそろっていれば、"
                       "資料は送らずに外せる＝呼び出しを減らせる。")
            field = res_t[res_t["種類"] == "現場写真"]
            if len(field):
                lg = field.melt(id_vars="場面", value_vars=dv.TROUBLES, var_name="困りごと", value_name="確信度")
                fig_b = px.box(lg, x="困りごと", y="確信度", points="all", color="困りごと",
                               color_discrete_sequence=["#c2410c", "#b45309", "#7c3aed"])
                fig_b.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
                                    yaxis_range=[-0.05, 1.05])
                g2.plotly_chart(fig_b, width="stretch")
                g2.caption(f"現場写真 {len(field)} 枚の、困りごとの手がかりの確信度。0 が多いのは「写真では見えない」"
                           "困りごと（人手・遅れの多く）があるため。")

            # ── 突き合わせ：テキストの判定 × 写真の手がかり ──
            st.subheader("テキストと写真を突き合わせる")
            t1, t2, t3 = st.columns(3)
            thr = t1.slider("写真の手がかりとみなす確信度", 0.1, 0.9, 0.3 if use_sample else 0.5, 0.1, key="img_thr")
            by_date = t2.toggle("日付で結びついた写真も含める", value=source.startswith("架空"),
                                help="日付だけで結びついた写真は、その作業の写真とは限りません。根拠には日誌IDで結びついた写真を使います")
            field_only = t3.toggle("現場写真だけを使う", value=True)
            lk = linked_all if by_date else linked_all[linked_all["結びつけ方"] == "日誌ID"]
            lk = lk.assign(キー=[dv.key(p, ROOT) for p in lk["パス"]])
            sig = dv.image_signals(lk, ai_res, threshold=thr, field_only=field_only)
            img_tab = dv.text_image_table(judged, sig)
            if img_tab.empty:
                st.info("突き合わせられる日誌がありません（写真が日誌に結びついていないか、タグが付いていません）。")
            else:
                vc = img_tab["突き合わせ"].value_counts().rename_axis("突き合わせ").reset_index(name="組")
                order = ["両方で困りごと", "テキストだけ", "写真だけ（原文を読み直す）", "写真だけ（書かれていない？）", "どちらにも無い"]
                fig_v = px.bar(vc, x="組", y="突き合わせ", orientation="h", category_orders={"突き合わせ": order},
                               color="突き合わせ", color_discrete_map={
                                   "両方で困りごと": "#c2410c", "テキストだけ": "#f59e0b",
                                   "写真だけ（原文を読み直す）": "#7c3aed", "写真だけ（書かれていない？）": "#a78bfa",
                                   "どちらにも無い": "#e5e7eb"})
                fig_v.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
                st.plotly_chart(fig_v, width="stretch")
                look = img_tab[img_tab["突き合わせ"].str.startswith(("写真だけ", "テキストだけ"))]
                st.dataframe(look.merge(df[["ID", "本文"]], on="ID"), hide_index=True, width="stretch")
                st.caption("単位は「日誌×困りごとの種類」。**写真だけ**＝写真に手がかりがあるのに、テキストでは否定・保留・語なし → "
                           "原文を読み直すか、現場に聞く。**テキストだけ**＝書かれているが写真では見えない（人手・遅れは写りにくい）。"
                           "写真が無い日誌は対象外です。")

            # ── 🔎 圃場の観察（困りごと3語では拾えない、作物・圃場の状態） ──
            st.subheader("🔎 圃場の観察：困りごと3語では拾えない「作物の状態」")
            ot = dv.obs_table(res_t)
            if ot.empty:
                st.info("観察のタグが付いた写真がまだありません。Claude に読ませると「病害の疑い」などが付きます。")
            else:
                o1, o2 = st.columns([1, 2])
                obs_thr = o1.slider("観察とみなす確信度", 0.1, 0.9, 0.5, 0.1, key="obs_thr")
                obs_hit = ot[ot["確信度"] >= obs_thr]
                per_obs = obs_hit.groupby("観察")["パス"].nunique().reindex(list(dv.OBS), fill_value=0)
                o1.metric("観察のある写真", f"{obs_hit['パス'].nunique()} / {len(res_t)} 枚")
                o1.metric("病害の疑いがある写真", f"{int(per_obs['病害の疑い'])} 枚")
                fig_o = px.bar(per_obs.rename_axis("観察").reset_index(name="写真の枚数"), x="写真の枚数", y="観察",
                               orientation="h", color="観察", color_discrete_sequence=px.colors.qualitative.Safe)
                fig_o.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
                                    yaxis={"categoryorder": "array", "categoryarray": list(dv.OBS)[::-1]})
                o2.plotly_chart(fig_o, width="stretch")
                tbl = obs_hit.assign(写真=obs_hit["パス"].map(lambda x: Path(x).name),
                                     対策の時期=obs_hit["観察"].map(lambda k: dv.OBS[k][1]))
                st.dataframe(tbl[["写真", "観察", "確信度", "手がかり", "対策の時期"]].sort_values(["観察", "確信度"], ascending=[True, False]),
                             hide_index=True, width="stretch")
                with st.expander("「秋に見えるが、原因は初夏にある」：病害の因果の時間差（柿の円星落葉病の例）"):
                    st.markdown(
                        "```\n[前年の落葉を放置] → [5〜7月 胞子が飛び感染] → [潜伏] → [9〜10月 発病（斑点・黄変）]\n"
                        "                                                        ↓\n"
                        "                                  [早く落葉] → [実が軟らかく・糖度が下がる] → [翌年の花芽不足（隔年結果）]\n```\n"
                        "| いま写真で見えるもの | 原因が起きた時期 | 打てる手と時期 |\n|---|---|---|\n"
                        "| 葉の斑点・黄変（病害の疑い） | 5〜7月の感染 | 来年5〜6月の防除（症状が出てからでは遅い） |\n"
                        "| 斑点のある落葉（伝染源） | いま | 冬に集めて処分（いちばん安く効く） |\n"
                        "| 実が多く枝が垂れる（着果過多） | 7月ごろの摘果不足 | 今年は枝折れに注意・色づいた実から収穫 |\n\n"
                        "**因果AIの問い**：「冬の落葉処分 → 翌年の発病率 → 果実の品質」の効果を、木ごとの違い（日当たり・樹齢）を"
                        "調整して推定する。写真で毎年同じ木を撮っておくことが、そのままデータになります。")
                    st.caption("病名は写真からの推定です。確定は県の農業技術センターやJAの営農指導員に確かめてください。")

                nx = res_t[res_t["次の1枚"].astype(str).isin([x for x in dv.NEXT_SHOTS if x != "なし"])]
                if len(nx):
                    st.markdown("**📸 次に撮る1枚（判定を確かにするための撮影リスト）**")
                    shot = nx.assign(写真=nx["パス"].map(lambda x: Path(x).name))[["写真", "場面", "次の1枚", "説明"]]
                    st.dataframe(shot, hide_index=True, width="stretch")
                    st.download_button("撮影リストをCSVで保存", sg.safe_csv(shot), "次に撮る写真.csv", "text/csv")
                    st.caption("撮ったら作業日誌フォームに添付すると、日誌IDで結びつきます。例：葉の病斑のアップ＝病名の絞り込み、"
                               "果実の断面＝甘柿・渋柿の判定（種のまわりの黒い点＝ゴマの有無）。")

            # ── 🍊 ベイズで収量を見積もる ──
            st.subheader("🍊 ベイズで収量を見積もる：見える果実から、木1本の果実数を区間で")
            st.caption("写真では葉の陰の実が見えません。「見える割合」を1つの数に決めつけず、分布（Beta）で置くと、"
                       "知らないことの大きさが区間の幅として出てきます。")
            fr_src = res_t[res_t["見える果実数"].notna()]
            b1, b2 = st.columns([2, 3])
            with b1:
                default_counts = [18, 25, 12, 30, 22, 15]
                cnt = st.data_editor(pd.DataFrame({"区画": [f"区画{i + 1}" for i in range(len(default_counts))],
                                                   "見える果実数": default_counts}),
                                     num_rows="dynamic", hide_index=True, width="stretch", key="bayes_counts",
                                     column_config={"見える果実数": st.column_config.NumberColumn(min_value=0, max_value=1000, step=1)})
                if len(fr_src):
                    st.caption("Claude が数えた見える果実数（参考）：" + "、".join(
                        f"{Path(a).name} {int(b)}個" for a, b in fr_src[["パス", "見える果実数"]].itertuples(index=False)))
                n_sec = st.number_input("樹冠全体の区画の数", 1, 100, 10, key="bayes_nsec",
                                        help="木の写真を格子に分けたときの区画の総数。数えたのはその一部")
                vis_m = st.slider("見える割合の見込み（平均）", 0.3, 0.95, 0.7, 0.05, key="bayes_vis")
                vis_k = st.slider("その見込みの確からしさ（強さ）", 2, 200, 10, key="bayes_k",
                                  help="1つの区画で、葉をかき分けて全部数えた数と写真で見えた数を比べると、強さを上げられます")
            with b2:
                try:
                    by = dv.bayes_yield(cnt["見える果実数"].tolist(), int(n_sec), vis_m, float(vis_k))
                except ValueError as e:
                    st.info(str(e))
                else:
                    m1, m2 = st.columns(2)
                    m1.metric("木1本の果実数（中央値）", f"{by['中央値']:.0f} 個")
                    m2.metric("95%区間", f"{by['下限']:.0f}〜{by['上限']:.0f} 個")
                    fig_h = px.histogram(pd.DataFrame({"果実数": by["samples"]}), x="果実数", nbins=60,
                                         color_discrete_sequence=["#ea580c"])
                    for xv, lab in [(by["下限"], "2.5%"), (by["上限"], "97.5%")]:
                        fig_h.add_vline(x=xv, line_dash="dot", line_color="#7c2d12", annotation_text=lab)
                    fig_h.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="サンプル数")
                    st.plotly_chart(fig_h, width="stretch")
                    st.caption(f"見える割合を {vis_m:.2f} に決めつけた場合の95%区間：{by['固定の下限']:.0f}〜{by['固定の上限']:.0f} 個。"
                               "分布で置いた区間のほうが広いのは、見える割合を知らない分の不確実性を正直に足しているから。"
                               f"数えた区画 {by['数えた区画']} 個、1区画あたりの事後平均 {by['λの事後平均']:.1f} 個。")
                    st.code("λ ~ Gamma(2, 0.1) → 見える果実数 ~ Poisson(λ)  （事後も Gamma：共役）\n"
                            "v ~ Beta(平均×強さ, (1−平均)×強さ)                （見える割合）\n"
                            "木全体 = λ × 区画の総数 / v", language="text")

            st.download_button("画像分析の結果をCSVで保存", sg.safe_csv(ai_res), "日誌_写真のタグ.csv", "text/csv")
            st.caption("保存したCSVを `data/sample_photo_ai.csv` に置きかえると、次から記入例として読み込まれます。")

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
photo_both = img_tab[img_tab["突き合わせ"] == "両方で困りごと"]["語"].value_counts() if len(img_tab) else pd.Series(dtype=int)
photo_only = img_tab[img_tab["突き合わせ"].str.startswith("写真だけ")]["語"].value_counts() if len(img_tab) else pd.Series(dtype=int)
w_photo = st.slider("写真だけで見つかった困りごとの重み（0＝数えない、1＝テキストと同じに数える）", 0.0, 1.0, 0.5, 0.1,
                    help="写真の手がかりは Claude の候補なので、人が確かめるまでは割り引いて数えます")
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
    n_po, n_both = int(photo_only.get(kw, 0)), int(photo_both.get(kw, 0))
    n_eff = n + w_photo * n_po
    rows.append({"語": kw, "確認済みの件数": n, "写真で裏づけ": n_both, "写真だけ": n_po,
                 "損失時間の見込み(h)": round(n_eff * loss, 1),
                 "優先度": round(n_eff * loss * ready, 1), "エージェント候補": agent, "必要なデータ": need})
st.latex(r"\text{優先度} = (\text{確認済みの件数} + w \times \text{写真だけの件数}) \times "
         r"\text{1件あたりの損失時間} \times \text{データの準備度}")
decide = pd.DataFrame(rows).sort_values("優先度", ascending=False)
st.dataframe(decide, hide_index=True, width="stretch")
if len(decide) and decide["優先度"].max() > 0:
    top = decide.iloc[0]
    st.success(f"今の条件では「{top['語']}」が最上位：{top['エージェント候補']}（前提：{top['必要なデータ']}）")
if len(obs_hit):
    st.subheader("写真の観察から出てきた候補（困りごと3語の外側）")
    rows_o = []
    for k, (agent, need) in OBS_AGENTS.items():
        n_ph = int(obs_hit.loc[obs_hit["観察"] == k, "パス"].nunique())
        n_tx = int(df["本文"].str.contains(OBS_WORDS[k], regex=True).sum())
        if n_ph or n_tx:
            rows_o.append({"観察": k, "写真の枚数": n_ph, "日誌に書かれた件数": n_tx, "対策の時期": dv.OBS[k][1],
                           "エージェント候補": agent, "必要なデータ": need})
    if rows_o:
        st.dataframe(pd.DataFrame(rows_o).sort_values("写真の枚数", ascending=False), hide_index=True, width="stretch")
        st.caption("「日誌に書かれた件数」が0で写真にだけある観察は、**テキスト分析だけでは見えない困りごとの種**です。"
                   "日誌の検索語に足す（例：斑点・落葉）か、作業日誌フォームの『作業』に「果樹管理」を加えると、両方で数えられます。"
                   "病害は写真が撮れる秋と手を打つ初夏がずれるので、エージェントの価値は「時期を忘れずに知らせる」ことにあります。")
st.info("この判断に必要なのに日誌に無いもの：困りごとで**止まった時間**・**影響した量**。"
        "次の一手は、自由記述を残したまま「止まった時間（分）」「影響（出荷・作業・品質）」の2欄を日誌に足すこと。"
        "写真の側では、**困りごとがあった日に1枚撮る**（日誌IDで結びつく）ことが、写真で裏づけられる件数を増やす一番の近道です。")

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

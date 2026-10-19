"""
探究学習コーナー ─ AI・データサイエンス＝機械学習の目で、作業日誌・写真・糖度・集落のデータからインサイトを見つける
配置先: pages/16_🧠_機械学習で見つける.py （Streamlit のマルチページ構成）

「機械学習の基礎」（全15回）の一本道 ── データ準備 → 教師あり（判別／回帰）→ 教師なし → 相関と因果 → 自分の研究への適用
を、このリポジトリのデータに当てはめたもの。骨格は 🔤 作業日誌テキスト分析＋画像分析 と同じ：
  0 匿名化 → ① 前処理 → ② 判別 → ✅ 検証（トレース表・DNCL） → ③ 教師なし → ④ 回帰 → ⑤ 相関と因果 → ⑥ 適用シナリオと3行報告

計算は ml_insight.py（numpy だけで書いた決定木・PCA・k-means・重回帰・DID）。
scikit-learn が入っていれば、授業と同じライブラリで答えが一致するかを ✅ で確かめる。

方針
  - 外部の生成AIには何も送らない。日誌は匿名化してから特徴量にする。
  - 教師ありの「正解」は人が原文を読んで付けたもの。モデルは正解を真似るだけ。
  - 初期表示はすべて教材用の架空データ。アップロードしたCSVはセッション内だけで使い、サーバーには残さない。
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import diary_text as dtx
import ml_insight as ml
import security_guard as sg

st.set_page_config(page_title="機械学習で見つける（探究学習コーナー）", page_icon="🧠", layout="wide")

DATA = Path(__file__).parent.parent / "data"
SAMPLE = DATA / "sample_work_diary.csv"
SAMPLE_TRUTH = DATA / "sample_work_diary_truth.csv"
SAMPLE_PHOTO_AI = DATA / "sample_photo_ai.csv"
SAMPLE_BRIX = DATA / "sample_spinach_brix.csv"
SAMPLE_DID = DATA / "sample_shuraku_did.csv"
SAMPLE_NAMES = ["山田", "佐藤"]
SAMPLE_PARTNERS = ["みどり青果", "ひかり製パン"]
REQUIRED = ["ID", "日付", "作業", "本文"]
COLORS = ["#15803d", "#c2410c", "#7c3aed", "#0369a1", "#b45309", "#64748b"]

try:
    import sklearn  # noqa: F401
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

st.title("🧠 機械学習で見つける ── 探究学習コーナー")
st.caption("モデルは正解を真似る。正解を決めるのも、結果の意味を読むのも人。 ── 「機械学習の基礎」全15回を、畑のデータで歩き直す")

with st.container(border=True):
    st.markdown(
        "**探究メモ**：🔤 作業日誌テキスト分析では、人が原文を読んで「困りごと」かどうかを判定し、"
        "規則（否定の形・言い換え）を手で作った。ここでは同じ日誌と人の判定を**正解ラベル**にして、"
        "**機械学習は人の規則より上手に、あるいは別の手がかりで判定できるか**を確かめる。"
        "さらに、写真のタグ（Claude が付けたもの）を**教師なし学習**でまとめ、"
        "ホウレンソウの糖度を**回帰**で見積もり、集落の交付金の効果を**差の差（DID）**で読む。"
        "注意点は四つある。第一に、件数が36件と少ないので、**学習に使わなかったデータ**で評価する（train/test・交差検証）。"
        "第二に、困りごとは約半分だが、実際の日誌では少数派になる（**不均衡**）ので、正解率ではなく適合率・再現率・F値を見る。"
        "第三に、モデルが使った手がかりが**意味のある理由か**を、木のルールと重要度で人が確かめる。"
        "第四に、**相関は因果ではない**。効果を言うには比べ方を設計する。"
    )

with st.expander("このページの道のり：授業の15回と、人・AI・Pythonの役割", expanded=False):
    st.markdown(
        "| 授業 | 内容 | このページのどこ | 題材 | 担当 |\n|---|---|---|---|---|\n"
        "| 第1回 | ML/AI概論・CRISP-DM・ELSI | 探究メモ・0 匿名化 | 作業日誌 | 人 |\n"
        "| 第2〜4回 | Python基礎・生成AI援用コーディング・動作検査 | ✅ 検証（手計算・トレース表・scikit-learn） | 作業日誌 | 人・Python |\n"
        "| 第5〜6回 | データ品質・train-test split・エンコーディング | ① 前処理 | 作業日誌 → 特徴量 | 人が決め、Pythonが作る |\n"
        "| 第7〜8回 | 決定木・混同行列・Precision/Recall/F値・P-R曲線 | ② 判別 | 困りごとの判定 | Python → 人 |\n"
        "| 第9〜10回 | Feature Importance・交差検証・不均衡データ | ② 判別（重要度・交差検証） | 困りごとの判定 | Python → 人 |\n"
        "| 第11〜12回 | 重回帰・R²/RMSE/MAE・時系列の分け方 | ④ 回帰 | ホウレンソウの糖度 | Python → 人 |\n"
        "| 第13〜14回 | z標準化・PCA・k-means・エルボー法・主成分クラスター分析 | ③ 教師なし | 写真のタグ | Python → 人が意味づけ |\n"
        "| 第15回 | 手法選定・相関と因果（DID）・自分の研究への適用 | ⑤ 因果・⑥ 適用シナリオ | 集落の交付金 | 人 |\n\n"
        "**手法の選び方（第15回）**：目的変数があるか → ある：出力が離散なら**判別**、連続なら**回帰**／"
        "ない：変数を減らすなら**PCA**、似たものをまとめるなら**クラスター分析**／効果を言いたいなら**因果推論**。"
    )
    st.caption("計算は `ml_insight.py`（numpy だけで書いた決定木・PCA・k-means・重回帰・DID）。"
               "中身が追えるように小さく書き、✅ で scikit-learn の答えと照らし合わせています。")

# ------------------------------------------------------------
# サイドバー：データの選択
# ------------------------------------------------------------
with st.sidebar:
    st.header("日誌のデータ")
    source = st.radio("使うデータ", ["架空の記入例（36件）", "自分の日誌CSVを読み込む"])
    up = up_t = None
    if source.startswith("自分"):
        st.caption("日誌CSV：`ID,日付,作業,本文`。正解CSV：`ID,困りごと`（あり／なし／保留）。"
                   "🔤 作業日誌テキスト分析で保存した匿名化済みのCSVを使います。")
        up = st.file_uploader("日誌CSV", type="csv", key="ml_diary")
        up_t = st.file_uploader("正解CSV（人の判定）", type="csv", key="ml_truth")
    st.divider()
    hold = st.radio("「保留」の日誌の扱い", ["除く", "なし", "あり"], horizontal=True,
                    help="本文だけでは決められなかった日誌。正解をどう付けるかは人が決める（モデルは決めない）")
    seed = st.number_input("乱数の種（train/test・k-means）", 0, 999, 0)
    st.caption("このページは外部の生成AIを呼び出しません。読み込んだCSVはセッションの中だけで使います。")

if source.startswith("自分"):
    if up is None or up_t is None:
        st.info("左のサイドバーから、日誌CSVと正解CSVの2つを読み込んでください。")
        st.stop()
    raw = sg.read_csv_safely(up, page="ml", kind="diary")
    truth = sg.read_csv_safely(up_t, page="ml", kind="truth")
    if raw is None or truth is None:
        st.stop()
    missing = [c for c in REQUIRED if c not in raw.columns] + [c for c in ["ID", "困りごと"] if c not in truth.columns]
    if missing:
        st.error(f"列が足りません：{', '.join(missing)}")
        st.stop()
    default_names, default_partners = "", ""
else:
    raw = pd.read_csv(SAMPLE, encoding="utf-8-sig")
    truth = pd.read_csv(SAMPLE_TRUTH, encoding="utf-8-sig")
    default_names, default_partners = "\n".join(SAMPLE_NAMES), "\n".join(SAMPLE_PARTNERS)
    st.warning("表示しているのは**教材用の架空データ**です（実在の法人・従業員・取引先・集落ではありません）。")

raw["ID"] = raw["ID"].astype(str)
truth["ID"] = truth["ID"].astype(str)

# ------------------------------------------------------------
# 0 匿名化（第1回 ELSI）
# ------------------------------------------------------------
st.header("0｜学習の前に匿名化する（第1回 ELSI）")
a1, a2 = st.columns(2)
names = [dtx.normalize(w.strip()) for w in a1.text_area("氏名（1行に1つ）", default_names, height=80).splitlines() if w.strip()]
partners = [dtx.normalize(w.strip()) for w in a2.text_area("取引先名（1行に1つ）", default_partners, height=80).splitlines() if w.strip()]
df = raw.copy()
df["本文"] = [dtx.mask(dtx.normalize(str(t)), names, partners) for t in df["本文"]]
left = dtx.residual(df["本文"], names + partners)
if left:
    st.error(f"匿名化のあとに残っている語があります：{', '.join(left)}。ここで止めます。")
    st.stop()
df = df.drop(columns=[c for c in ["記入者"] if c in df.columns]).merge(truth[["ID", "困りごと"]], on="ID", how="left")
st.success(f"日誌 {len(df)} 件を匿名化しました（辞書の語の残り：0 件）。正解が付いた日誌：{int(df['困りごと'].notna().sum())} 件")
st.caption("モデルは本文の**特徴量**だけを見ます。氏名がモデルの手がかりになる（「山田さんの日は困りごと」）ことも防げます。")

# ------------------------------------------------------------
# ① 前処理（第5〜6回）
# ------------------------------------------------------------
st.header("① 前処理：本文 → 特徴量、正解 → 0/1、学習用とテスト用に分ける（第5〜6回）")
feat = ml.features(df)
y_all = ml.truth_vector(df["困りごと"], hold)
use = y_all.notna().to_numpy()
p1, p2, p3 = st.columns(3)
p1.metric("学習に使える日誌", f"{int(use.sum())} / {len(df)} 件", help=f"保留の扱い：{hold}")
p2.metric("困りごと(1)の割合", f"{y_all[use].mean():.0%}", help="1が少ないほど不均衡。正解率だけでは評価できない")
p3.metric("特徴量の数", f"{feat.shape[1]} 個")
with st.expander("特徴量の表（モデルが見るのはこの表だけ）", expanded=False):
    show = pd.concat([df[["ID", "作業", "本文", "困りごと"]], feat], axis=1)
    st.dataframe(show, hide_index=True, width="stretch")
    st.markdown("| 特徴量 | 作り方 |\n|---|---|\n" + "\n".join(f"| {k} | {v} |" for k, v in ml.FEATURE_NOTES.items()))
    st.caption("特徴量を決めるのは人です。ここに無い手がかり（写真・止まった時間）は、モデルには見えません。")

dfu, Fu = df[use].reset_index(drop=True), feat[use].reset_index(drop=True)
X, y = Fu.to_numpy(float), y_all[use].astype(int).to_numpy()
names_f = list(Fu.columns)

s1, s2 = st.columns([2, 3])
split = s1.radio("分け方", ["日付で分ける（前を学習・後をテスト）", "ランダムに分ける（層化）"],
                 help="日誌は時間順に増えていく。未来の日誌で使えるかを見るなら、日付で分けるのが本番に近い（第12回）")
test_ratio = s2.slider("テストに回す割合", 0.2, 0.5, 0.3, 0.05)
if split.startswith("日付"):
    order = np.argsort(pd.to_datetime(dfu["日付"], errors="coerce").fillna(pd.Timestamp.max).to_numpy(), kind="stable")
    n_test = max(2, int(round(len(order) * test_ratio)))
    te_idx, tr_idx = order[-n_test:], order[:-n_test]
else:
    rng = np.random.default_rng(int(seed))
    te_idx = np.concatenate([rng.permutation(np.where(y == c)[0])[: max(1, int(round((y == c).sum() * test_ratio)))]
                             for c in (0, 1)])
    tr_idx = np.setdiff1d(np.arange(len(y)), te_idx)
te_idx, tr_idx = np.sort(te_idx), np.sort(tr_idx)
st.caption(f"学習用 {len(tr_idx)} 件（困りごと {int(y[tr_idx].sum())}）／テスト用 {len(te_idx)} 件（困りごと {int(y[te_idx].sum())}）。"
           "テスト用はモデルを作るときに一度も見せません。")
if len(set(y[tr_idx])) < 2:
    st.error("学習用に困りごと(1)となし(0)の両方が入っていません。割合か分け方を変えてください。")
    st.stop()

# ------------------------------------------------------------
# ② 判別（第7〜10回）
# ------------------------------------------------------------
st.header("② 判別：人の規則と決定木、どちらが困りごとを当てるか（第7〜10回）")
d1, d2, d3 = st.columns(3)
depth = d1.slider("木の深さ（max_depth）", 1, 5, 2, help="深いほど学習用に合わせ込む（過学習）")
min_leaf = d2.slider("葉の最小件数（min_samples_leaf）", 1, 6, 1)
thr = d3.slider("困りごととみなす確率のしきい値", 0.1, 0.9, 0.5, 0.05,
                help="下げると見逃し(FN)が減り、誤報(FP)が増える。どちらを避けたいかは現場が決める")
drop_len = st.toggle("特徴量から「文字数」を外す", value=False,
                     help="「短い日誌＝特に問題なし」という近道（ショートカット）を使わせない")
cols_use = [j for j, n in enumerate(names_f) if not (drop_len and n == "文字数")]
names_use = [names_f[j] for j in cols_use]
Xu = X[:, cols_use]

tree = ml.fit_tree(Xu[tr_idx], y[tr_idx], max_depth=depth, min_leaf=min_leaf)
prob_te = ml.predict_proba(tree, Xu[te_idx])
prob_tr = ml.predict_proba(tree, Xu[tr_idx])
preds = {
    "素の検索（3語のどれか）": ml.rule_baseline(Fu.iloc[te_idx]),
    "人の規則（否定を除く＋言い換え）": ml.rule_handmade(Fu.iloc[te_idx]),
    f"決定木（深さ{depth}）": (prob_te >= thr).astype(int),
}
rows = []
for name, p in preds.items():
    cm = ml.confusion(y[te_idx], p)
    rows.append({"モデル": name, **cm, **{k: round(v, 2) for k, v in ml.scores(cm).items()}})
cmp = pd.DataFrame(rows)
st.dataframe(cmp, hide_index=True, width="stretch")
f_tr = ml.scores(ml.confusion(y[tr_idx], (prob_tr >= thr).astype(int)))["F値"]
f_te = cmp.iloc[2]["F値"]
st.caption(f"すべて**テスト用 {len(te_idx)} 件**での値。決定木のF値：学習用 {f_tr:.2f} ／ テスト用 {f_te:.2f}"
           + ("　→ 学習用だけ高い＝**過学習の兆し**" if f_tr - f_te > 0.15 else "") +
           "。件数が少ないので、1件の違いで値が大きく動きます（下の交差検証で確かめます）。")

g1, g2 = st.columns([2, 3])
with g1:
    st.markdown("**決定木を「もし〜ならば」で読む**")
    for line in ml.tree_rules(tree, names_use):
        st.markdown(f"- {line}")
    fi = pd.DataFrame({"特徴量": names_use, "重要度": ml.feature_importance(tree, len(names_use))})
    fi = fi[fi["重要度"] > 0].sort_values("重要度")
    if len(fi):
        fig_fi = px.bar(fi, x="重要度", y="特徴量", orientation="h", color_discrete_sequence=[COLORS[0]])
        fig_fi.update_layout(height=60 + 40 * len(fi), margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_fi, width="stretch")
        st.caption("Feature Importance（第9回）＝その特徴量で分けたときに不純度がどれだけ減ったか。"
                   "**効いた順であって、原因の順ではありません。**")
with g2:
    cm_t = ml.confusion(y[te_idx], preds[f"決定木（深さ{depth}）"])
    z = [[cm_t["TN"], cm_t["FP"]], [cm_t["FN"], cm_t["TP"]]]
    fig_cm = px.imshow(z, x=["予測：なし", "予測：困りごと"], y=["正解：なし", "正解：困りごと"], text_auto=True,
                       color_continuous_scale="Greens", aspect="auto")
    fig_cm.update_layout(height=260, margin=dict(l=10, r=10, t=30, b=10), coloraxis_showscale=False,
                         title_text="混同行列（決定木・テスト用）", title_font_size=14)
    st.plotly_chart(fig_cm, width="stretch")
    # P-R曲線（しきい値を動かしたときの軌跡）
    pr = []
    for t in np.unique(np.r_[prob_te, 0.0, 1.01]):
        s = ml.scores(ml.confusion(y[te_idx], (prob_te >= t).astype(int)))
        pr.append({"しきい値": round(float(t), 2), "再現率": s["再現率(Recall)"], "適合率": s["適合率(Precision)"]})
    pr = pd.DataFrame(pr)
    fig_pr = px.line(pr, x="再現率", y="適合率", markers=True, hover_data=["しきい値"], range_x=[-0.02, 1.02], range_y=[-0.02, 1.02])
    fig_pr.update_traces(line_color=COLORS[1])
    fig_pr.update_layout(height=260, margin=dict(l=10, r=10, t=30, b=10), title_text="P-R曲線（しきい値を動かす）", title_font_size=14)
    st.plotly_chart(fig_pr, width="stretch")

if "文字数" in names_use and fi["特徴量"].eq("文字数").any():
    st.warning("💡 **インサイト**：木が「文字数」を手がかりにしています。困りごとがない日は「特に問題なし。」と短く書かれるため、"
               "**長さで当てる近道（ショートカット学習）**ができてしまう。記入の仕方が変わる（困りごとの日も短く書く）と崩れます。"
               "上の「文字数を外す」と下の交差検証の線で、外しても当たり方が落ちないか（落ちないなら近道は要らない）を確かめてください。")

miss = dfu.iloc[te_idx].assign(正解=y[te_idx], 予測=preds[f"決定木（深さ{depth}）"], 確率=prob_te.round(2))
miss = miss[miss["正解"] != miss["予測"]]
with st.expander(f"テスト用で外れた日誌 {len(miss)} 件の原文（モデルが見ていない手がかりを探す）", expanded=bool(len(miss))):
    st.dataframe(miss[["ID", "日付", "作業", "本文", "正解", "予測", "確率"]], hide_index=True, width="stretch")
    st.caption("FN（見逃し）＝困りごとなのに「なし」。言い換え・推量・解消の報告など、特徴量に無い言い方が多い。"
               "FP（誤報）＝「なし」なのに「困りごと」。外れた原文から、次に足す特徴量を人が考えます。")

st.subheader("交差検証：分け方の運を減らす（第10回）")
k1, k2 = st.columns([1, 3])
k = k1.slider("分割数 k", 2, min(10, len(y)), min(5, len(y)))
cv_rows = []
for name, cidx in [("全特徴量", list(range(len(names_f)))),
                   ("文字数なし", [j for j, n in enumerate(names_f) if n != "文字数"])]:
    for dpt in range(1, 5):
        pcv = ml.cross_val_predict(X[:, cidx], y, k=k, seed=int(seed), max_depth=dpt, min_leaf=min_leaf)
        s = ml.scores(ml.confusion(y, (pcv >= thr).astype(int)))
        cv_rows.append({"特徴量": name, "深さ": dpt, "F値": round(s["F値"], 3), "再現率": round(s["再現率(Recall)"], 3)})
for name, fn in [("人の規則", ml.rule_handmade), ("素の検索", ml.rule_baseline)]:
    s = ml.scores(ml.confusion(y, fn(Fu)))
    cv_rows += [{"特徴量": name, "深さ": d, "F値": round(s["F値"], 3), "再現率": round(s["再現率(Recall)"], 3)} for d in range(1, 5)]
cvd = pd.DataFrame(cv_rows)
fig_cv = px.line(cvd, x="深さ", y="F値", color="特徴量", markers=True, color_discrete_sequence=COLORS)
fig_cv.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), yaxis_range=[0, 1.05])
k2.plotly_chart(fig_cv, width="stretch")
k1.caption(f"{k}分割：各日誌を「その日誌を学習に使わなかった木」で予測し、{len(y)} 件全部でF値を出す。"
           "人の規則は学習しないので横一直線（ただし規則はこのデータを見て作った後付け）。")

# ------------------------------------------------------------
# ✅ 検証（第2〜4回）：トレース表・DNCL・scikit-learn
# ------------------------------------------------------------
st.header("✅ 検証する：混同行列を手で数え、ライブラリの答えと照らし合わせる")
v1, v2 = st.columns([3, 2])
with v1:
    tr_tab = ml.trace_confusion(y[te_idx], preds[f"決定木（深さ{depth}）"], dfu["ID"].iloc[te_idx].tolist())
    st.dataframe(tr_tab, hide_index=True, width="stretch")
with v2:
    st.code(
        "TP = 0, FP = 0, FN = 0, TN = 0\n"
        "i を 0 から 要素数(正解)-1 まで 1 ずつ増やしながら繰り返す:\n"
        "│ もし 予測[i] = 1 かつ 正解[i] = 1 ならば:\n"
        "│ │ TP = TP + 1\n"
        "│ そうでなくもし 予測[i] = 1 ならば:\n"
        "│ │ FP = FP + 1\n"
        "│ そうでなくもし 正解[i] = 1 ならば:\n"
        "│ │ FN = FN + 1\n"
        "│ そうでなければ:\n"
        "│ └ TN = TN + 1\n"
        "適合率 = TP ÷ (TP + FP)\n"
        "再現率 = TP ÷ (TP + FN)\n"
        "表示する(適合率, 再現率)", language="text")
    last = tr_tab.iloc[-1] if len(tr_tab) else None
    if last is not None:
        ok = {kk: int(last[kk]) for kk in ["TP", "FP", "FN", "TN"]} == cm_t
        st.markdown(f"トレース表の最終行 = 上の混同行列：{'✅ 一致' if ok else '❌ 不一致'}")
    st.caption("共通テスト『情報Ⅰ』のDNCLと同じ形。分岐の順番を入れかえる（「正解[i]=1」を先に調べる）と、"
               "FPとFNの数がどう変わるかをトレース表で確かめてみましょう。")

if HAS_SKLEARN:
    from sklearn.tree import DecisionTreeClassifier
    sk = DecisionTreeClassifier(max_depth=depth, min_samples_leaf=min_leaf, random_state=0).fit(Xu[tr_idx], y[tr_idx])
    p_sk = (sk.predict_proba(Xu[te_idx])[:, 1] >= thr).astype(int) if len(sk.classes_) == 2 else np.zeros(len(te_idx), int)
    same = int((p_sk == preds[f"決定木（深さ{depth}）"]).sum())
    st.markdown(f"**scikit-learn（授業と同じ `DecisionTreeClassifier`）との一致**：テスト用 {same} / {len(te_idx)} 件"
                + ("　✅" if same == len(te_idx) else "　⚠️ 同点の分け方の選び方が違うと、ずれることがあります"))
else:
    st.caption("scikit-learn が入っていないので、ライブラリとの照合は省きました（Colab の `notebooks/` で確かめられます）。")

# ------------------------------------------------------------
# ③ 教師なし（第13〜14回）：写真のタグ → z標準化 → PCA → k-means
# ------------------------------------------------------------
st.header("③ 教師なし：写真のタグから「似た場面」をまとめる（第13〜14回）")
st.caption("正解ラベルは使いません。評価の軸は「当たったか」ではなく、**内は似て外は違うか・人が意味づけできるか**。")
photo = pd.read_csv(SAMPLE_PHOTO_AI, encoding="utf-8-sig")
photo = photo[photo["種類"] == "現場写真"].reset_index(drop=True) if st.toggle("現場写真だけを使う", value=True) else photo
M = ml.photo_matrix(photo)
num_cols = [c for c in ["遅れ", "故障", "人手"] if c in photo.columns]
if st.toggle("困りごとの確信度（遅れ・故障・人手）も特徴量に入れる", value=False):
    M = pd.concat([M, photo[num_cols].astype(float)], axis=1)
M = M.loc[:, M.sum() > 0]
if len(M) < 4 or M.shape[1] < 2:
    st.info("まとめられる写真のタグがまだ足りません。🔤 作業日誌テキスト分析の画像分析でタグを付けてください。")
else:
    zs = st.toggle("z標準化する（平均0・標準偏差1）", value=True,
                   help="単位や頻度の大きい列が距離を支配しないように（第14回）")
    Z = ml.zscore(M.to_numpy()) if zs else M.to_numpy(float)
    u1, u2 = st.columns([1, 3])
    kmax = min(6, len(M) - 1)
    el = ml.elbow(Z, range(1, kmax + 1), seed=int(seed))
    fig_el = px.line(el, x="k", y="WSS", markers=True)
    fig_el.update_traces(line_color=COLORS[2])
    fig_el.update_layout(height=220, margin=dict(l=10, r=10, t=10, b=10))
    u1.plotly_chart(fig_el, width="stretch")
    u1.caption("エルボー法：WSS（クラスター内のばらつき）の下がり方が鈍る k を探す。はっきり折れないことも多い。")
    kk = u1.slider("クラスター数 k", 2, max(2, kmax), min(3, kmax))
    km = ml.kmeans(Z, kk, seed=int(seed))
    pc = ml.pca(Z, 2)
    sc = pd.DataFrame(pc["scores"], columns=["第1主成分", "第2主成分"]).assign(
        クラスター=[f"C{c + 1}" for c in km["labels"]], 写真=photo["パス"].map(lambda p: Path(p).name),
        場面=photo["場面"], 写っているもの=photo["写っているもの"])
    fig_pc = px.scatter(sc, x="第1主成分", y="第2主成分", color="クラスター", hover_data=["写真", "場面", "写っているもの"],
                        color_discrete_sequence=COLORS, symbol="クラスター")
    fig_pc.update_traces(marker_size=11)
    fig_pc.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10))
    u2.plotly_chart(fig_pc, width="stretch")
    u2.caption(f"主成分クラスター分析：{M.shape[1]} 個のタグを2軸に要約（寄与率 第1 {pc['ratio'][0]:.0%}・第2 {pc['ratio'][1]:.0%}）。"
               "色は k-means の結果で、PCAの軸で分けたわけではありません。")

    load = pd.DataFrame(pc["loadings"], index=M.columns, columns=["第1主成分", "第2主成分"]).round(2)
    prof = M.assign(クラスター=sc["クラスター"]).groupby("クラスター").mean().round(2)
    w1, w2 = st.columns(2)
    with w1:
        st.markdown("**クラスターごとのタグの割合（意味づけの材料）**")
        top = {c: "・".join(prof.loc[c].sort_values(ascending=False).head(4).index) for c in prof.index}
        sizes = sc["クラスター"].value_counts()
        st.dataframe(pd.DataFrame({"クラスター": list(top), "写真の枚数": [int(sizes[c]) for c in top],
                                   "多いタグ": list(top.values()),
                                   "場面（多い順）": [" / ".join(sc.loc[sc["クラスター"] == c, "場面"].value_counts().head(3).index) for c in top]}),
                     hide_index=True, width="stretch")
        st.session_state.setdefault("cluster_names", {})
        for c in top:
            st.session_state.cluster_names[c] = st.text_input(f"{c} に名前を付ける（人の仕事）",
                                                              st.session_state.cluster_names.get(c, ""), key=f"cn_{c}_{kk}")
    with w2:
        st.markdown("**主成分の負荷量（どのタグが軸を作っているか）**")
        st.dataframe(load.reindex(load["第1主成分"].abs().sort_values(ascending=False).index).head(8), width="stretch")
    st.caption("名前を付けられないクラスターは、k が合っていないか、タグ（特徴量）が場面を表していないサイン。"
               "例：「通路の雑草」「果樹の株元」「パン用小麦の畝」のように付けられれば、エージェントの撮影リストや作業予定の単位になります。")

    with st.expander("トレース表：k-means の「割り当て」を1点ずつ追う（1次元の小さな例・DNCL）"):
        pts_txt = st.text_input("点（カンマ区切り）", "1, 2, 3, 8, 9, 15")
        cen_txt = st.text_input("中心（カンマ区切り）", "2, 9")
        try:
            pts = [float(v) for v in pts_txt.split(",") if v.strip()]
            cen = [float(v) for v in cen_txt.split(",") if v.strip()]
            st.dataframe(ml.trace_assign(pts, cen), hide_index=True, width="stretch")
        except ValueError:
            st.error("数字をカンマで区切って入れてください。")
        st.code(
            "i を 0 から 要素数(x)-1 まで 1 ずつ増やしながら繰り返す:\n"
            "│ 所属 = 0\n"
            "│ j を 1 から 要素数(c)-1 まで 1 ずつ増やしながら繰り返す:\n"
            "│ │ もし |x[i] − c[j]| < |x[i] − c[所属]| ならば:\n"
            "│ └ └ 所属 = j\n"
            "│ 表示する(i, 所属)\n"
            "（全員の所属が決まったら、各中心を所属した点の平均に動かし、変わらなくなるまでくり返す）", language="text")
        st.caption("15 は c1=9 に近いが、次の「重心の移動」で c1 が 15 側に引っぱられる。外れ値に弱いことが手で確かめられます。")

# ------------------------------------------------------------
# ④ 回帰（第11〜12回）：ホウレンソウの糖度
# ------------------------------------------------------------
st.header("④ 回帰：寒さに当てると、糖度は週にどれだけ上がるか（第11〜12回）")
brix = pd.read_csv(SAMPLE_BRIX, encoding="utf-8-sig")
day0 = pd.to_datetime(brix["測定日"]).min()
brix["週"] = (pd.to_datetime(brix["測定日"]) - day0).dt.days / 7
brix["寒さ"] = (brix["区"] == "寒さに当てる区").astype(int)
brix["週×寒さ"] = brix["週"] * brix["寒さ"]
cand = ["週", "寒さ", "週×寒さ", "列"]
r1, r2 = st.columns([1, 2])
xs = r1.multiselect("説明変数", cand, default=["週", "寒さ", "週×寒さ"],
                    help="「週×寒さ」＝寒さに当てた区だけの、週ごとの上乗せ（交互作用）")
r_split = r1.radio("分け方", ["最後の測定日をテストに（時系列）", "全部で学習（当てはまりだけ）"])
if not xs:
    st.info("説明変数を1つ以上選んでください。")
else:
    last_day = brix["測定日"].max()
    trn = brix[brix["測定日"] != last_day] if r_split.startswith("最後") else brix
    tst = brix[brix["測定日"] == last_day] if r_split.startswith("最後") else brix
    beta = ml.fit_ols(trn[xs].to_numpy(float), trn["糖度"])
    pred = ml.predict_ols(beta, tst[xs].to_numpy(float))
    rs = ml.reg_scores(tst["糖度"], pred)
    m1, m2, m3 = r1.columns(3)
    m1.metric("R²", f"{rs['R²']:.2f}")
    m2.metric("RMSE", f"{rs['RMSE']:.2f}")
    m3.metric("MAE", f"{rs['MAE']:.2f}")
    r1.dataframe(pd.DataFrame({"項": ["切片"] + xs, "係数": np.round(beta, 3)}), hide_index=True, width="stretch")
    if "週×寒さ" in xs:
        r1.success(f"💡 寒さに当てた区は、覆いをかけた区より**週に {beta[1 + xs.index('週×寒さ')]:+.2f} 度**多く上がる見込み"
                   "（この畑・この冬・3回の測定での値）。")
    avg = brix.groupby(["週", "区"], as_index=False)["糖度"].mean()
    fig_r = px.scatter(brix, x="週", y="糖度", color="区", opacity=0.45, color_discrete_sequence=[COLORS[3], COLORS[5]])
    grid = pd.DataFrame([{"週": w, "区": z} for w in np.linspace(0, brix["週"].max(), 20) for z in brix["区"].unique()])
    grid["寒さ"] = (grid["区"] == "寒さに当てる区").astype(int)
    grid["週×寒さ"] = grid["週"] * grid["寒さ"]
    grid["列"] = brix["列"].mean()
    grid["予測"] = ml.predict_ols(beta, grid[xs].to_numpy(float))
    for z, col in zip(brix["区"].unique(), [COLORS[3], COLORS[5]]):
        g = grid[grid["区"] == z]
        fig_r.add_trace(go.Scatter(x=g["週"], y=g["予測"], mode="lines", line=dict(color=col, width=3), name=f"{z}（モデル）"))
    fig_r.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="最初の測定からの週")
    r2.plotly_chart(fig_r, width="stretch")
    r2.caption("時系列のデータは、ランダムに分けると「未来の測定」で学習してしまう。最後の測定日をテストに回すと、"
               "**1週先を当てられるか**が見える（第12回）。外挿（測っていない週）は、気温が変われば当たりません。")

# ------------------------------------------------------------
# ⑤ 相関と因果（第15回）：差の差（DID）
# ------------------------------------------------------------
st.header("⑤ 相関と因果：交付金を受けた集落は、耕地の減りを抑えられたか（第15回）")
sh = pd.read_csv(SAMPLE_DID, encoding="utf-8-sig")
dd = ml.did(sh, "集落", "年", "交付金", "経営耕地_ha")
c1, c2, c3 = st.columns(3)
c1.metric(f"単純比較（{dd['後']}年の差）", f"{dd['単純比較（後の差）']:+.1f} ha", help="受けた集落 − 受けていない集落")
c2.metric("前後差（受けた集落）", f"{dd['処置群の変化']:+.1f} ha", help=f"{dd['後']}年 − {dd['前']}年")
c3.metric("差の差（DID）", f"{dd['DID']:+.2f} ha", help="（受けた集落の変化）−（受けていない集落の変化）")
tab = dd["表"].rename(index={0: "受けていない", 1: "受けた"})
fig_d = go.Figure()
for g_name, col in zip(tab.index, [COLORS[5], COLORS[1]]):
    fig_d.add_trace(go.Scatter(x=[str(c) for c in tab.columns], y=tab.loc[g_name], mode="lines+markers",
                               name=f"交付金を{g_name}集落", line=dict(color=col, width=3)))
ctrl = tab.loc["受けていない"]
fig_d.add_trace(go.Scatter(x=[str(c) for c in tab.columns],
                           y=[tab.loc["受けた"].iloc[0], tab.loc["受けた"].iloc[0] + (ctrl.iloc[1] - ctrl.iloc[0])],
                           mode="lines", name="受けなかったら（平行の仮定）", line=dict(color=COLORS[1], dash="dot")))
fig_d.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="経営耕地の平均（ha）")
st.plotly_chart(fig_d, width="stretch")
st.markdown(
    f"- **単純比較**では、受けた集落のほうが {dd['単純比較（後の差）']:.1f} ha 広い。しかし**もともと広い集落が交付金を受けていた**ので、これは効果ではない（選択バイアス）。\n"
    f"- **DID** では {dd['DID']:+.2f} ha。両方とも耕地は減っており、受けた集落の減りは**小さくなっていない**。\n"
    "- DIDが効果と言えるのは「交付金がなければ、両群は同じ傾きで変化した」（**平行トレンド**）ときだけ。2時点では確かめられないので、2020年より前の年も集めて確かめる。"
)
st.caption("機械学習（判別・回帰）は「当てる」ための道具で、「変えたらどうなるか」は教えてくれない。"
           "冬の落葉処分・寒さに当てる・交付金のような**手を打つ判断**には、比べ方の設計（RCT・DID・傾向スコア）が要る。")

# ------------------------------------------------------------
# ⑥ 適用シナリオ（第15回 終了課題）と3行の報告
# ------------------------------------------------------------
st.header("⑥ 自分の課題に当てはめる：ML適用シナリオと3行の報告（第15回 終了課題）")
sc_default = pd.DataFrame([
    {"課題": "日誌の困りごとを毎日拾う", "目的変数": "困りごと（あり/なし）", "説明変数": "語・否定・言い換え・推量",
     "手法": "決定木 → 人の確認", "評価指標": "再現率（見逃さない）を優先", "限界・ELSI": "書かれない困りごとは拾えない／氏名は匿名化"},
    {"課題": "写真の撮影リストを場面ごとに組む", "目的変数": "なし（教師なし）", "説明変数": "写真のタグ",
     "手法": "z標準化 → PCA → k-means", "評価指標": "人が名前を付けられるか", "限界・ELSI": "タグは Claude の候補／顔・ナンバーを除く"},
    {"課題": "ホウレンソウの出荷日を決める", "目的変数": "糖度（連続値）", "説明変数": "週・寒さ・交互作用",
     "手法": "重回帰", "評価指標": "RMSE（何度ずれるか）", "限界・ELSI": "この冬の気温でだけ成り立つ"},
    {"課題": "交付金の効果を確かめる", "目的変数": "経営耕地（ha）", "説明変数": "交付金×年",
     "手法": "差の差（DID）", "評価指標": "平行トレンドの確認", "限界・ELSI": "2時点では仮定を確かめられない"},
])
plan = st.data_editor(sc_default, num_rows="dynamic", hide_index=True, width="stretch", key="ml_plan")
st.caption("行を足して、自分の研究・探究の課題で埋めてください。「目的変数があるか」「出力は離散か連続か」で手法の列が決まります。")

best = cmp.sort_values("F値", ascending=False).iloc[0]
draft = (
    f"観測：匿名化した作業日誌{int(use.sum())}件（困りごと{int(y.sum())}件）をテスト用{len(te_idx)}件で評価すると、"
    f"F値は人の規則{cmp.iloc[1]['F値']:.2f}・決定木{cmp.iloc[2]['F値']:.2f}・素の検索{cmp.iloc[0]['F値']:.2f}だった（最上位：{best['モデル']}）。\n"
    f"解釈：決定木は{'「' + '」「'.join(fi.sort_values('重要度', ascending=False)['特徴量'].head(2)) + '」' if len(fi) else '（分岐なし）'}を手がかりにした。"
    "否定の形は意味のある手がかりだが、文字数は書き方の癖による近道の可能性がある（外れた日誌の原文で確認）。\n"
    f"限界：件数が少なく、1件でF値が大きく動く。正解は1人の判定で、保留は「{hold}」として扱った。別の月・別の法人の日誌で確かめ直す。"
)
report = st.text_area("3行の報告（観測／解釈と根拠／限界）。下書きを自分の言葉に書きかえる", draft, height=170,
                      key=f"ml_rep_{depth}_{drop_len}_{thr}_{split}")
e1, e2, e3 = st.columns(3)
e1.download_button("3行の報告を保存（.txt）", report.encode("utf-8"), "3行報告_機械学習.txt", "text/plain", width="stretch")
e2.download_button("適用シナリオをCSVで保存", sg.safe_csv(plan), "ML適用シナリオ.csv", "text/csv", width="stretch")
e3.download_button("特徴量と正解をCSVで保存（匿名化済み）", sg.safe_csv(pd.concat([df[["ID", "作業", "困りごと"]], feat], axis=1)),
                   "日誌_特徴量.csv", "text/csv", width="stretch")

st.divider()
st.caption("© スマートパン屋農家プロジェクト ｜ 初期表示は教材用の架空データです。"
           "同じ手順を Colab で：`notebooks/ml_insight_practice.ipynb`")

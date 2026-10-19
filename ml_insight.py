"""
ml_insight.py — 「機械学習の基礎」（全15回）の手法を、作業日誌・写真・糖度のデータに当てはめる小さな部品

画面は pages/16_🧠_機械学習で見つける.py。テキストの下ごしらえは diary_text.py を使う。

方針
  - 中身が追えるように numpy だけで書く（決定木・k-means・PCA・重回帰）。
    授業の scikit-learn と同じ答えになるかは notebooks/ml_insight_practice.ipynb で確かめる。
  - 外部の生成AIには何も送らない。日誌は diary_text.mask で匿名化したものを渡す前提。
  - 教師ありの「正解」は人が原文を読んで付けたもの（data/sample_work_diary_truth.csv）。
    モデルは正解を真似るだけで、正解の付け方を決めるのは人。

授業との対応
  第5〜6回 前処理（特徴量・train/test）   → features(), split_by()
  第7〜10回 判別（決定木・混同行列・FI・交差検証） → fit_tree(), confusion(), scores(), cross_val_predict()
  第11〜12回 回帰（重回帰・R²/RMSE/MAE・時系列の分け方） → fit_ols(), reg_scores()
  第13〜14回 教師なし（z標準化・PCA・k-means・エルボー） → zscore(), pca(), kmeans(), elbow()
  第15回 相関と因果（DID）               → did()
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

import numpy as np
import pandas as pd

import diary_text as dtx

# ------------------------------------------------------------
# 前処理：日誌の本文 → 特徴量（第5〜6回）
# ------------------------------------------------------------
# 推量・予測の言い方（確定した困りごとではない候補）
GUESS = r"かもしれない|かと思った|ようだ|らしい"

FEATURE_NOTES = {
    "語_遅れ": "本文に「遅れ」を含む（0/1）",
    "語_故障": "本文に「故障」を含む（0/1）",
    "語_人手": "本文に「人手」を含む（0/1）",
    "否定": "「遅れはない」「故障なし」「人手は足りた」などの打ち消し・充足の形（0/1）",
    "言い換え": "「遅延」「壊れ」「動かなくなっ」「手が足り」などの言い換え（0/1）",
    "推量": "「かもしれない」「かと思った」などの推量（0/1）",
    "文字数": "本文の長さ（字）",
}


def features(df: pd.DataFrame, col: str = "本文") -> pd.DataFrame:
    """日誌1件 → 1行の特徴量。文字列の一致だけで作る（意味は人が決める）。"""
    rows = []
    for text in df[col].astype(str).map(dtx.normalize):
        row = {f"語_{k}": int(k in text) for k in dtx.KEYWORDS}
        row["否定"] = int(any(re.search(p, text) for p in dtx.NEG_PATTERNS.values()))
        row["言い換え"] = int(any(re.search(p, text) for ps in dtx.SYNONYMS.values() for p in ps))
        row["推量"] = int(bool(re.search(GUESS, text)))
        row["文字数"] = len(text)
        rows.append(row)
    return pd.DataFrame(rows, index=df.index)


def truth_vector(truth: pd.Series, hold: str = "除く") -> pd.Series:
    """人の判定（あり／なし／保留）→ 1/0。保留の扱いは人が選ぶ：除く（NaN）・なし（0）・あり（1）。"""
    m = {"あり": 1.0, "なし": 0.0, "保留": {"除く": np.nan, "なし": 0.0, "あり": 1.0}[hold]}
    return truth.map(m)


def rule_baseline(feat: pd.DataFrame) -> np.ndarray:
    """第1段の規則：3語のどれかに一致したら困りごと（テキスト分析①の素の検索と同じ）"""
    return (feat[[f"語_{k}" for k in dtx.KEYWORDS]].sum(axis=1) > 0).astype(int).to_numpy()


def rule_handmade(feat: pd.DataFrame) -> np.ndarray:
    """人が書いた規則：（3語に一致 かつ 否定でない）または 言い換え"""
    hit = rule_baseline(feat).astype(bool)
    return ((hit & (feat["否定"] == 0).to_numpy()) | (feat["言い換え"] == 1).to_numpy()).astype(int)


# ------------------------------------------------------------
# 判別：決定木（CART・ジニ不純度）（第7・9回）
# ------------------------------------------------------------
def gini(counts: Sequence[int]) -> float:
    """ジニ不純度 = 1 − Σ p²。全部同じクラスなら0、半々なら0.5。"""
    n = sum(counts)
    return 0.0 if n == 0 else 1.0 - sum((c / n) ** 2 for c in counts)


def _best_split(X: np.ndarray, y: np.ndarray, min_leaf: int):
    n, best = len(y), None
    parent = gini([int((y == 0).sum()), int((y == 1).sum())])
    for j in range(X.shape[1]):
        vals = np.unique(X[:, j])
        for a, b in zip(vals[:-1], vals[1:]):
            thr = (a + b) / 2
            left = X[:, j] <= thr
            nl, nr = int(left.sum()), int((~left).sum())
            if nl < min_leaf or nr < min_leaf:
                continue
            gl = gini([int((y[left] == 0).sum()), int((y[left] == 1).sum())])
            gr = gini([int((y[~left] == 0).sum()), int((y[~left] == 1).sum())])
            gain = parent - (nl / n) * gl - (nr / n) * gr
            # 同点なら先の列を残す（結果が毎回同じになるように）
            if gain > 1e-12 and (best is None or gain > best[0] + 1e-12):
                best = (gain, j, thr)
    return best


def fit_tree(X: np.ndarray, y: np.ndarray, max_depth: int = 2, min_leaf: int = 1, depth: int = 0) -> dict:
    """決定木を作る。葉には「困りごと(1)」の割合を持たせる。"""
    X, y = np.asarray(X, float), np.asarray(y, int)
    node = {"n": len(y), "n1": int(y.sum()), "p": float(y.mean()) if len(y) else 0.0,
            "gini": gini([int((y == 0).sum()), int((y == 1).sum())])}
    if depth >= max_depth or node["gini"] == 0.0:
        return node
    best = _best_split(X, y, min_leaf)
    if best is None:
        return node
    gain, j, thr = best
    left = X[:, j] <= thr
    node.update(feature=j, thr=thr, gain=gain,
                left=fit_tree(X[left], y[left], max_depth, min_leaf, depth + 1),
                right=fit_tree(X[~left], y[~left], max_depth, min_leaf, depth + 1))
    return node


def predict_proba(tree: dict, X: np.ndarray) -> np.ndarray:
    out = []
    for x in np.asarray(X, float):
        node = tree
        while "feature" in node:
            node = node["left"] if x[node["feature"]] <= node["thr"] else node["right"]
        out.append(node["p"])
    return np.array(out)


def feature_importance(tree: dict, n_features: int) -> np.ndarray:
    """不純度の減少量（件数で重みづけ）の合計を、全体が1になるようにそろえる（第9回 FI）"""
    imp = np.zeros(n_features)

    def walk(node):
        if "feature" in node:
            l, r = node["left"], node["right"]
            imp[node["feature"]] += node["n"] * node["gini"] - l["n"] * l["gini"] - r["n"] * r["gini"]
            walk(l)
            walk(r)
    walk(tree)
    return imp / imp.sum() if imp.sum() > 0 else imp


def tree_rules(tree: dict, names: Sequence[str]) -> list[str]:
    """木を「もし〜ならば」の文に直す（人が読んで確かめられる形）"""
    lines = []

    def cond(j, thr, left):
        name = names[j]
        if name == "文字数":
            return f"{name} ≦ {thr:g}" if left else f"{name} > {thr:g}"
        return f"「{name}」なし" if left else f"「{name}」あり"

    def walk(node, path):
        if "feature" not in node:
            when = " かつ ".join(path) if path else "すべて"
            lines.append(f"もし {when} ならば → 困りごと {node['n1']}/{node['n']}件"
                         f"（{node['p']:.0%}）→ 判定：{'困りごと' if node['p'] >= 0.5 else '困りごとなし'}")
            return
        walk(node["left"], path + [cond(node["feature"], node["thr"], True)])
        walk(node["right"], path + [cond(node["feature"], node["thr"], False)])
    walk(tree, [])
    return lines


# ------------------------------------------------------------
# 評価：混同行列・Precision/Recall/F値（第8回）、交差検証（第10回）
# ------------------------------------------------------------
def confusion(y: Iterable[int], yhat: Iterable[int]) -> dict:
    """for文で1件ずつ数える（DNCLのトレース表と同じ手順）"""
    tp = fp = fn = tn = 0
    for t, p in zip(y, yhat):
        if p == 1 and t == 1:
            tp += 1
        elif p == 1 and t == 0:
            fp += 1
        elif p == 0 and t == 1:
            fn += 1
        else:
            tn += 1
    return {"TP": tp, "FP": fp, "FN": fn, "TN": tn}


def scores(cm: dict) -> dict:
    tp, fp, fn, tn = cm["TP"], cm["FP"], cm["FN"], cm["TN"]
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    acc = (tp + tn) / max(1, tp + fp + fn + tn)
    return {"正解率": acc, "適合率(Precision)": prec, "再現率(Recall)": rec, "F値": f1}


def trace_confusion(y: Sequence[int], yhat: Sequence[int], ids: Sequence[str]) -> pd.DataFrame:
    """混同行列を数える for文 の、1回ごとの変数の値（トレース表）"""
    tp = fp = fn = tn = 0
    rows = []
    for i, (t, p, d) in enumerate(zip(y, yhat, ids)):
        if p == 1 and t == 1:
            tp, branch = tp + 1, "TP"
        elif p == 1 and t == 0:
            fp, branch = fp + 1, "FP"
        elif p == 0 and t == 1:
            fn, branch = fn + 1, "FN"
        else:
            tn, branch = tn + 1, "TN"
        rows.append({"i": i, "ID": d, "正解[i]": int(t), "予測[i]": int(p), "通った分岐": branch,
                     "TP": tp, "FP": fp, "FN": fn, "TN": tn})
    return pd.DataFrame(rows)


def cross_val_predict(X: np.ndarray, y: np.ndarray, k: int, seed: int = 0, **tree_kw) -> np.ndarray:
    """k分割交差検証：各日誌を「学習に使わなかった木」で予測した確率を返す（k=件数なら1つ抜き）"""
    n = len(y)
    order = np.random.default_rng(seed).permutation(n)
    out = np.zeros(n)
    for fold in np.array_split(order, k):
        train = np.setdiff1d(order, fold)
        tree = fit_tree(X[train], y[train], **tree_kw)
        out[fold] = predict_proba(tree, X[fold])
    return out


# ------------------------------------------------------------
# 教師なし：z標準化・PCA・k-means（第13〜14回）
# ------------------------------------------------------------
def zscore(X: np.ndarray) -> np.ndarray:
    """列ごとに平均0・標準偏差1へ。ばらつきが0の列は0のまま（距離に効かない）。"""
    X = np.asarray(X, float)
    sd = X.std(axis=0)
    sd[sd == 0] = 1.0
    return (X - X.mean(axis=0)) / sd


def pca(Z: np.ndarray, n_comp: int = 2) -> dict:
    """特異値分解で主成分を求める。寄与率と負荷量（各変数が軸にどれだけ効くか）も返す。"""
    Z = np.asarray(Z, float) - np.asarray(Z, float).mean(axis=0)
    U, S, Vt = np.linalg.svd(Z, full_matrices=False)
    var = S ** 2 / max(1, len(Z) - 1)
    ratio = var / var.sum() if var.sum() > 0 else var
    # 向きをそろえる（各主成分で絶対値最大の負荷量を正に）→ 毎回同じ図になる
    signs = np.sign(Vt[np.arange(len(Vt)), np.abs(Vt).argmax(axis=1)])
    signs[signs == 0] = 1
    Vt = Vt * signs[:, None]
    return {"scores": Z @ Vt[:n_comp].T, "ratio": ratio[:n_comp], "loadings": Vt[:n_comp].T}


def _init_centers(X: np.ndarray, k: int, rng: np.random.Generator) -> np.ndarray:
    """k-means++：遠い点ほど次の中心に選ばれやすくする"""
    centers = [X[rng.integers(len(X))]]
    for _ in range(1, k):
        d2 = np.min([((X - c) ** 2).sum(axis=1) for c in centers], axis=0)
        p = d2 / d2.sum() if d2.sum() > 0 else np.full(len(X), 1 / len(X))
        centers.append(X[rng.choice(len(X), p=p)])
    return np.array(centers)


def kmeans(X: np.ndarray, k: int, seed: int = 0, n_init: int = 50, max_iter: int = 100) -> dict:
    """割り当て → 重心の移動 をくり返す。初期値を変えて n_init 回やり、クラスター内平方和(WSS)が最小のものを返す。"""
    X = np.asarray(X, float)
    rng, best = np.random.default_rng(seed), None
    for _ in range(n_init):
        c = _init_centers(X, k, rng)
        history = []
        for _ in range(max_iter):
            lab = ((X[:, None, :] - c[None]) ** 2).sum(axis=2).argmin(axis=1)
            new = np.array([X[lab == j].mean(axis=0) if (lab == j).any() else c[j] for j in range(k)])
            history.append(float(((X - new[lab]) ** 2).sum()))
            if np.allclose(new, c):
                break
            c = new
        wss = float(((X - c[lab]) ** 2).sum())
        if best is None or wss < best["wss"] - 1e-9:
            best = {"labels": lab, "centers": c, "wss": wss, "history": history}
    # 番号を「大きいクラスター順」にそろえる（毎回同じ色になる）
    order = np.argsort(-np.bincount(best["labels"], minlength=k), kind="stable")
    remap = np.empty(k, int)
    remap[order] = np.arange(k)
    best["labels"], best["centers"] = remap[best["labels"]], best["centers"][order]
    return best


def elbow(X: np.ndarray, ks: Iterable[int], seed: int = 0) -> pd.DataFrame:
    return pd.DataFrame([{"k": k, "WSS": kmeans(X, k, seed)["wss"]} for k in ks])


def trace_assign(points: Sequence[float], centers: Sequence[float]) -> pd.DataFrame:
    """k-means の「割り当て」1回分を1点ずつ追う（1次元の小さな例・DNCLのトレース表）"""
    rows = []
    for i, x in enumerate(points):
        d = [abs(x - c) for c in centers]
        best = 0
        for j in range(1, len(centers)):
            if d[j] < d[best]:
                best = j
        rows.append({"i": i, "x[i]": x, **{f"|x−c{j}|": round(v, 2) for j, v in enumerate(d)}, "所属": f"c{best}"})
    return pd.DataFrame(rows)


def photo_matrix(photo: pd.DataFrame, col: str = "写っているもの") -> pd.DataFrame:
    """写真の「写っているもの」（・区切り）→ 0/1 の表。Claude のタグを特徴量にする。"""
    tags = photo[col].fillna("").astype(str).str.split("・")
    vocab = sorted({t for ts in tags for t in ts if t})
    return pd.DataFrame([[int(v in ts) for v in vocab] for ts in tags], columns=vocab, index=photo.index)


# ------------------------------------------------------------
# 回帰：重回帰・R²/RMSE/MAE（第11〜12回）
# ------------------------------------------------------------
def fit_ols(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """最小二乗法。先頭に切片の列を足して係数を返す（[切片, 係数1, …]）"""
    A = np.column_stack([np.ones(len(X)), np.asarray(X, float)])
    return np.linalg.lstsq(A, np.asarray(y, float), rcond=None)[0]


def predict_ols(beta: np.ndarray, X: np.ndarray) -> np.ndarray:
    return beta[0] + np.asarray(X, float) @ beta[1:]


def reg_scores(y: np.ndarray, yhat: np.ndarray) -> dict:
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    err = y - yhat
    ss_tot = ((y - y.mean()) ** 2).sum()
    return {"R²": 1 - (err ** 2).sum() / ss_tot if ss_tot > 0 else 0.0,
            "RMSE": float(np.sqrt((err ** 2).mean())), "MAE": float(np.abs(err).mean())}


# ------------------------------------------------------------
# 相関と因果：差分の差分（第15回）
# ------------------------------------------------------------
def did(df: pd.DataFrame, unit: str, time: str, treat: str, y: str) -> dict:
    """（処置群の前後差）−（対照群の前後差）。2時点・2群の最小の形。"""
    t0, t1 = sorted(df[time].unique())[:2]
    m = df.pivot_table(index=treat, columns=time, values=y, aggfunc="mean")
    d_t, d_c = m.loc[1, t1] - m.loc[1, t0], m.loc[0, t1] - m.loc[0, t0]
    return {"前": t0, "後": t1, "処置群の変化": float(d_t), "対照群の変化": float(d_c), "DID": float(d_t - d_c),
            "単純比較（後の差）": float(m.loc[1, t1] - m.loc[0, t1]), "表": m}

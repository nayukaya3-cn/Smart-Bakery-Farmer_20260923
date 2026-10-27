"""
離れる顧客を先に見つける（顧客離反予測）─ 多分野データ解析実践演習 ケース3 の計算部品

pages/24_🛒_離れる顧客を先に見つける.py から呼び出します。画面を持たない純粋な関数だけを置き、
`python churn_lab.py` で自己チェック（assert）が走ります。

探究の3つの問い（ページのタブと対応）
  ❶「離れる」をどう定義し、データをどう見るか？ → snapshot()：基準日で時間を切り、顧客カルテ＋正解ラベル
  ❷ どの機械学習モデルを選ぶか？                → make_model() / cv_auc()：ベースラインと3モデルを比べる
  ❸ どう評価し、どう使うか？                    → split() → fit_predict() → confusion() / gain_table() / roi_table()

データ
  UCI Online Retail II（英国のオンライン雑貨卸・小売、2009/12/01〜2011/12/09）を、
  scripts/build_churn_data.py で「請求書（1回の注文）単位」に要約したもの。
  出典：Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository.
        https://doi.org/10.24432/C5CG6D（CC BY 4.0）

方針
  - 機械学習は scikit-learn（授業・Colabノートブックと同じコード）。
  - 「未来のデータを特徴量に混ぜない」を関数の形で守る：特徴量は基準日より前、正解は基準日より後だけを見る。
  - 正解ラベルは評価（答え合わせ）にだけ使う。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
DATA_PATH = ROOT / "data" / "online_retail_ii_invoices.csv.gz"
CID, INV, DATE, AMT, CANCEL, UK = "CustomerID", "Invoice", "InvoiceDate", "Amount", "IsCancel", "IsUK"
SOURCE = ("Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. "
          "https://doi.org/10.24432/C5CG6D （CC BY 4.0）")

# 特徴量：(日本語名, 意味, 離反との関係の直感)
FEATURES = {
    "recency_days":    ("R 最終購入からの日数", "基準日から見て、最後に買ったのは何日前か", "長いほど「もう来ない」かも"),
    "frequency":       ("F 注文回数", "観察期間の注文（請求書）の数", "多いほど常連"),
    "monetary":        ("M 購入金額合計（£）", "観察期間の購入額の合計", "多いほど上得意"),
    "tenure_days":     ("付き合いの長さ（日）", "観察期間の初回購入から基準日まで", "長いほど定着"),
    "active_months":   ("購入した月の数", "購入があった月が何か月あるか", "定期的に来ているか"),
    "avg_order_value": ("1注文あたり平均額（£）", "M ÷ F", "卸売的な大口か"),
    "monetary_last90": ("直近90日の購入額（£）", "基準日前90日の購入額", "最近の勢い"),
    "share_last90":    ("直近90日の割合", "購入額のうち直近90日の占める割合", "最近増えているか減っているか"),
    "n_cancel":        ("キャンセル回数", "観察期間のキャンセル請求書の数", "不満のサイン？"),
    "cancel_rate":     ("キャンセル率", "キャンセル ÷（注文＋キャンセル）", "不満のサイン？"),
    "is_uk":           ("英国の顧客", "主な購入国が英国なら1", "海外は離れやすい？"),
}
LEAK = "leak_last_purchase_all"   # リーケージ体験用（本番では絶対に使えない）
FEATURES_LEAK = {LEAK: ("⚠️ 最終購入日（データ全体から計算）",
                        "基準日で切らずに、データ全体の最後の購入日（初日から何日目か）を使ってしまった（よくある失敗）", "カンニング")}

MODELS = {
    "ロジスティック回帰": ("各特徴に「点数」をつけて足し合わせ、確率に変換", "説明しやすい・安定", "複雑な関係は苦手"),
    "ランダムフォレスト": ("たくさんの決定木（Yes/Noの質問の木）の多数決", "頑健・調整が少なくて済む", "中身が見えにくい"),
    "勾配ブースティング": ("前の木の間違いを、次の木が直していく", "高精度になりやすい", "過学習しやすい"),
}


# ─────────────────────────────────────────────
# 0. データ：明細 → 請求書単位
# ─────────────────────────────────────────────
def invoices_from_lines(lines: pd.DataFrame) -> pd.DataFrame:
    """Online Retail II の明細（Invoice, Quantity, InvoiceDate, Price, Customer ID, Country）→ 請求書1行の表。

    ノートブックの前処理③と同じ規則：完全重複を除く／顧客ID欠損を除く／
    購入は数量>0・単価>0の明細だけを足す／C始まりはキャンセル（金額はマイナス）。
    """
    df = lines.drop_duplicates().rename(columns={"Customer ID": CID})
    df = df.dropna(subset=[CID]).copy()
    df[CID] = df[CID].astype(int)
    df[INV] = df[INV].astype(str)
    df[CANCEL] = df[INV].str.startswith("C")
    ok = df[CANCEL] | ((df["Quantity"] > 0) & (df["Price"] > 0))
    df = df[ok].assign(**{AMT: lambda d: d["Quantity"] * d["Price"],
                          UK: lambda d: (d["Country"] == "United Kingdom").astype(int)})
    inv = (df.groupby([INV, CID], as_index=False)
             .agg(**{DATE: (DATE, "min"), AMT: (AMT, "sum"), CANCEL: (CANCEL, "first"), UK: (UK, "max")}))
    inv = inv[(inv[CANCEL]) | (inv[AMT] > 0)]
    inv[AMT] = inv[AMT].round(2)
    return inv.sort_values(DATE).reset_index(drop=True)


def load_invoices(path: Path | str = DATA_PATH) -> pd.DataFrame:
    inv = pd.read_csv(path, parse_dates=[DATE], dtype={INV: str})
    return prepare(inv)


def prepare(inv: pd.DataFrame) -> pd.DataFrame:
    """型をそろえ、月の列を足す（アップロードにも使う）。"""
    inv = inv.copy()
    inv[DATE] = pd.to_datetime(inv[DATE])
    inv[CID] = inv[CID].astype(int)
    inv[CANCEL] = inv[CANCEL].astype(bool)
    inv[AMT] = inv[AMT].astype(float)
    inv[UK] = inv[UK].astype(int) if UK in inv else 1
    inv["_month"] = inv[DATE].dt.to_period("M")
    return inv.sort_values(DATE).reset_index(drop=True)


def from_upload(raw: pd.DataFrame, cid: str, date: str, invoice: str, amount: str | None = None,
                qty: str | None = None, price: str | None = None) -> pd.DataFrame:
    """自分の取引CSV（1行＝1注文 or 1明細）→ 請求書単位。金額がなければ 数量×単価。マイナスはキャンセル扱い。"""
    d = pd.DataFrame({CID: pd.to_numeric(raw[cid], errors="coerce"),
                      INV: raw[invoice].astype(str),
                      DATE: pd.to_datetime(raw[date], errors="coerce")})
    d[AMT] = pd.to_numeric(raw[amount], errors="coerce") if amount else \
        pd.to_numeric(raw[qty], errors="coerce") * pd.to_numeric(raw[price], errors="coerce")
    d = d.dropna()
    d[CANCEL] = d[INV].str.upper().str.startswith("C") | (d[AMT] < 0)
    d = d.groupby([INV, CID], as_index=False).agg(**{DATE: (DATE, "min"), AMT: (AMT, "sum"), CANCEL: (CANCEL, "max")})
    d[UK] = 1
    return prepare(d)


def data_range(inv: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    """データの最初の日と、最後の日の翌日（0時）。"""
    return inv[DATE].min().normalize(), inv[DATE].max().normalize() + pd.Timedelta(days=1)


def month_starts(inv: pd.DataFrame) -> list[pd.Timestamp]:
    a, b = data_range(inv)
    return list(pd.date_range(a + pd.offsets.MonthBegin(0), b, freq="MS"))


# ─────────────────────────────────────────────
# ❶ 基準日で時間を切る：顧客カルテ（特徴量）と正解ラベル
# ─────────────────────────────────────────────
def window_ok(inv: pd.DataFrame, cutoff, obs_m: int, hor_m: int | None) -> str | None:
    """基準日・観察期間・予測期間がデータの中に収まるか。収まらなければ理由を返す。"""
    a, b = data_range(inv)
    cutoff = pd.Timestamp(cutoff)
    if cutoff - pd.DateOffset(months=obs_m) < a - pd.Timedelta(days=1):
        return f"観察期間（{obs_m}か月）がデータの始まり {a:%Y/%m/%d} より前にはみ出します。"
    if hor_m and cutoff + pd.DateOffset(months=hor_m) > b + pd.Timedelta(days=1):
        return f"予測期間（{hor_m}か月）がデータの終わり {b - pd.Timedelta(days=1):%Y/%m/%d} より後にはみ出します。"
    return None


def make_features(inv: pd.DataFrame, cutoff, obs_m: int = 12, net: bool = False) -> pd.DataFrame:
    """基準日 cutoff の直前 obs_m か月「だけ」から、顧客1人1行のカルテを作る（未来は見ない）。

    net=True：購入額からキャンセル額を差し引く（巨額注文→全量キャンセルの見かけの上得意を消す）。
    """
    cutoff = pd.Timestamp(cutoff)
    w = inv[(inv[DATE] >= cutoff - pd.DateOffset(months=obs_m)) & (inv[DATE] < cutoff)]
    buy, canc = w[~w[CANCEL]], w[w[CANCEL]]
    g = buy.groupby(CID)
    f = pd.DataFrame({
        "recency_days": (cutoff - g[DATE].max()).dt.days,
        "frequency": g[INV].nunique(),
        "monetary": g[AMT].sum(),
        "tenure_days": (cutoff - g[DATE].min()).dt.days,
        "active_months": g["_month"].nunique(),
    })
    if net:
        f["monetary"] = (f["monetary"] + canc.groupby(CID)[AMT].sum().reindex(f.index).fillna(0)).clip(lower=0)
    f["avg_order_value"] = f["monetary"] / f["frequency"]
    last = buy[buy[DATE] >= cutoff - pd.Timedelta(days=90)].groupby(CID)[AMT].sum()
    f["monetary_last90"] = last.reindex(f.index).fillna(0)
    f["share_last90"] = (f["monetary_last90"] / f["monetary"].replace(0, np.nan)).fillna(0).clip(0, 1)
    f["n_cancel"] = canc.groupby(CID)[INV].nunique().reindex(f.index).fillna(0)
    f["cancel_rate"] = f["n_cancel"] / (f["frequency"] + f["n_cancel"])
    f["is_uk"] = (buy.groupby(CID)[UK].mean() >= 0.5).astype(int).reindex(f.index).fillna(1).astype(int)
    return f


def make_label(inv: pd.DataFrame, customers: pd.Index, cutoff, hor_m: int = 12) -> pd.Series:
    """予測期間（基準日から hor_m か月）に1回も買わなければ 離反=1。"""
    cutoff = pd.Timestamp(cutoff)
    fut = inv[(inv[DATE] >= cutoff) & (inv[DATE] < cutoff + pd.DateOffset(months=hor_m)) & (~inv[CANCEL])]
    return pd.Series((~customers.isin(set(fut[CID]))).astype(int), index=customers, name="churn")


def snapshot(inv: pd.DataFrame, cutoff, obs_m: int = 12, hor_m: int = 12, net: bool = False,
             leak: bool = False) -> pd.DataFrame:
    """顧客カルテ＋正解ラベル。leak=True で「未来を覗く特徴量」を足す（リーケージ体験用）。"""
    f = make_features(inv, cutoff, obs_m, net)
    f["churn"] = make_label(inv, f.index, cutoff, hor_m)
    if leak:
        last_all = inv[~inv[CANCEL]].groupby(CID)[DATE].max()          # ← 基準日で切っていない
        f[LEAK] = (last_all.reindex(f.index) - inv[DATE].min().normalize()).dt.days   # データ初日から何日目か
    return f


def monthly(inv: pd.DataFrame) -> pd.DataFrame:
    """月ごとの売上・購入した顧客数（データ理解用）。"""
    b = inv[~inv[CANCEL]]
    m = b.groupby("_month").agg(売上=(AMT, "sum"), 購入した顧客数=(CID, "nunique"), 注文数=(INV, "nunique"))
    m.index = m.index.to_timestamp()
    return m


# ─────────────────────────────────────────────
# ❷ モデル
# ─────────────────────────────────────────────
def make_model(name: str, **p):
    from sklearn.dummy import DummyClassifier
    from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import FunctionTransformer, StandardScaler

    seed = p.get("seed", 42)
    if name == "ロジスティック回帰":   # 金額の偏りを対数でならしてから、尺度をそろえる
        return make_pipeline(FunctionTransformer(np.log1p), StandardScaler(),
                             LogisticRegression(C=p.get("C", 1.0), max_iter=2000))
    if name == "ランダムフォレスト":
        return RandomForestClassifier(n_estimators=p.get("n_estimators", 200),
                                      min_samples_leaf=p.get("min_samples_leaf", 20),
                                      max_features=0.5, random_state=seed, n_jobs=-1)
    if name == "勾配ブースティング":
        return HistGradientBoostingClassifier(max_iter=p.get("max_iter", 200),
                                              learning_rate=p.get("learning_rate", 0.03),
                                              max_depth=p.get("max_depth", 3),
                                              min_samples_leaf=p.get("min_samples_leaf_gb", 40),
                                              l2_regularization=1.0, random_state=seed)
    if name == "ベースライン（全員「継続」）":
        return DummyClassifier(strategy="most_frequent")
    raise ValueError(name)


def split(snap: pd.DataFrame, cols: list[str], test_size: float = 0.25, seed: int = 42):
    """顧客をランダムに 学習用／テスト用 に分ける（離反率をそろえる＝層化）。"""
    from sklearn.model_selection import train_test_split
    X, y = snap[cols], snap["churn"]
    return train_test_split(X, y, test_size=test_size, stratify=y, random_state=seed)


def cv_auc(model, X, y, seed: int = 42, k: int = 5) -> np.ndarray:
    """学習用データの中で k 分割交差検証した AUC（テストデータは見ない）。"""
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    return cross_val_score(model, X, y, cv=StratifiedKFold(k, shuffle=True, random_state=seed), scoring="roc_auc")


def auc(y, p) -> float:
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, p)) if len(set(np.asarray(y))) > 1 else float("nan")


def curves(y, p) -> tuple[pd.DataFrame, pd.DataFrame]:
    """ROC曲線と PR曲線の点。"""
    from sklearn.metrics import precision_recall_curve, roc_curve
    fpr, tpr, _ = roc_curve(y, p)
    pr, rc, _ = precision_recall_curve(y, p)
    return pd.DataFrame({"誤報率": fpr, "再現率": tpr}), pd.DataFrame({"再現率": rc, "適合率": pr})


def importance(model, X, y, seed: int = 42, repeats: int = 5) -> pd.Series:
    """順列重要度：その列だけシャッフルしたとき、AUC がどれだけ下がるか。"""
    from sklearn.inspection import permutation_importance
    r = permutation_importance(model, X, y, scoring="roc_auc", n_repeats=repeats, random_state=seed, n_jobs=-1)
    return pd.Series(r.importances_mean, index=X.columns).sort_values(ascending=False)


def coefficients(model, cols) -> pd.Series | None:
    """ロジスティック回帰の係数（標準化後）。プラス＝離反しやすくする方向。"""
    lr = getattr(model, "steps", [[None, None]])[-1][1]
    return pd.Series(lr.coef_[0], index=cols).sort_values() if hasattr(lr, "coef_") else None


# ─────────────────────────────────────────────
# ❸ 評価と使い方
# ─────────────────────────────────────────────
def confusion(y, p, thr: float = 0.5) -> dict:
    y, f = np.asarray(y).astype(bool), np.asarray(p) >= thr
    tp, fp, fn, tn = int((y & f).sum()), int((~y & f).sum()), int((y & ~f).sum()), int((~y & ~f).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {"TP": tp, "FP": fp, "FN": fn, "TN": tn, "正解率": (tp + tn) / max(len(y), 1),
            "適合率": prec, "再現率": rec, "F1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
            "離反と判定した人数": tp + fp}


def gain_table(y, p, ks=(0.1, 0.2, 0.3, 0.5)) -> pd.DataFrame:
    """離反確率の高い順に上位k%へ施策を打ったら、どれだけ当たるか（リフト）。"""
    r = pd.DataFrame({"y": np.asarray(y), "p": np.asarray(p)}).sort_values("p", ascending=False)
    base, tot, rows = r["y"].mean(), r["y"].sum(), []
    for k in ks:
        t = r.head(max(int(round(len(r) * k)), 1))
        rows.append((f"上位{k:.0%}", len(t), t["y"].mean(), t["y"].sum() / tot, t["y"].mean() / base))
    return pd.DataFrame(rows, columns=["対象", "人数", "当たり率（適合率）", "カバー率（再現率）", "リフト（倍）"])


def gain_curve(y, p) -> pd.DataFrame:
    r = np.asarray(y)[np.argsort(-np.asarray(p), kind="stable")]
    return pd.DataFrame({"施策を打つ割合": np.arange(1, len(r) + 1) / len(r), "カバーできた離反者の割合": r.cumsum() / r.sum()})


def roi_table(y, p, monetary, cost: float = 10, save_rate: float = 0.2, ks=None,
              by_expected_loss: bool = True) -> pd.DataFrame:
    """上位k%に施策を打ったときの 守れた売上・コスト・差引（前年の購入額で近似）。

    並べ順は 期待損失（離反確率×購入額）か、離反確率そのもの。
    """
    ks = ks if ks is not None else np.round(np.arange(0.05, 1.0001, 0.05), 2)
    y, p, m = np.asarray(y), np.asarray(p), np.asarray(monetary, float)
    order = np.argsort(-(p * m if by_expected_loss else p), kind="stable")
    y, m = y[order], m[order]
    rows = []
    for k in ks:
        n = max(int(round(len(y) * k)), 1)
        saved = float((y[:n] * m[:n]).sum() * save_rate)
        c = n * cost
        rows.append((k, n, saved, c, saved - c, saved / c if c else np.nan))
    return pd.DataFrame(rows, columns=["割合", "人数", "守れた売上£", "施策コスト£", "差引£", "費用対効果（倍）"])


SEGMENTS = {
    "A": ("A 最優先で引き留め", "担当者が個別に連絡・条件の見直し"),
    "B": ("B 低コスト施策", "メール・クーポン・カタログ"),
    "C": ("C 優良顧客として維持", "特典・新商品の先行案内"),
    "D": ("D 通常対応", "いつものニュースレター"),
}


def segment(proba, monetary, risk_thr: float = 0.5, value_line: float = 0.0) -> np.ndarray:
    """離反リスク × 顧客の価値 の4区分。"""
    hi_r, hi_v = np.asarray(proba) >= risk_thr, np.asarray(monetary) >= value_line
    return np.select([hi_r & hi_v, hi_r, hi_v], ["A", "B", "C"], "D")


# ─────────────────────────────────────────────
# 自己チェック：`python churn_lab.py`
# ─────────────────────────────────────────────
if __name__ == "__main__":
    inv = load_invoices()
    a, b = data_range(inv)
    assert a == pd.Timestamp("2009-12-01") and b == pd.Timestamp("2011-12-10"), (a, b)

    # ノートブックと同じ定義（観察12か月・予測12か月・基準日2010/12/01）なら、同じ人数・離反率になる
    s = snapshot(inv, "2010-12-01", 12, 12)
    assert abs(len(s) - 4266) <= 5 and abs(s["churn"].mean() - 0.364) < 0.01, (len(s), s["churn"].mean())
    assert window_ok(inv, "2010-12-01", 12, 12) is None and window_ok(inv, "2011-06-01", 12, 12)

    cols = list(FEATURES)
    Xtr, Xte, ytr, yte = split(s, cols)
    res = {}
    for name in MODELS:
        m = make_model(name).fit(Xtr, ytr)
        res[name] = auc(yte, m.predict_proba(Xte)[:, 1])
    # 実践知1：どのモデルも AUC≈0.78。モデルの差より特徴量の作り方が効く
    assert all(0.74 < v < 0.83 for v in res.values()) and max(res.values()) - min(res.values()) < 0.04, res
    # 実践知2：ベースラインは正解率64%でも、離反者を1人も見つけない
    d = make_model("ベースライン（全員「継続」）").fit(Xtr, ytr)
    c0 = confusion(yte, d.predict_proba(Xte)[:, 1])
    assert c0["正解率"] > 0.6 and c0["再現率"] == 0
    # 実践知3：未来を覗く特徴量を混ぜると、AUC が不自然に跳ね上がる（リーケージ）
    sl = snapshot(inv, "2010-12-01", 12, 12, leak=True)
    Xtr2, Xte2, ytr2, yte2 = split(sl, cols + [LEAK])
    m2 = make_model("ランダムフォレスト").fit(Xtr2, ytr2)
    assert auc(yte2, m2.predict_proba(Xte2)[:, 1]) > res["ランダムフォレスト"] + 0.05
    # 実践知4：時間をずらした検証（6か月→6か月）でも予測は効く
    tr = snapshot(inv, "2010-06-01", 6, 6)
    te = snapshot(inv, "2010-12-01", 6, 6)
    m3 = make_model("ロジスティック回帰").fit(tr[cols], tr["churn"])
    assert auc(te["churn"], m3.predict_proba(te[cols])[:, 1]) > 0.72
    # 実践知5：上位に絞るほど当たり率が上がる（リフト>1）
    p = make_model("ランダムフォレスト").fit(Xtr, ytr).predict_proba(Xte)[:, 1]
    g = gain_table(yte, p)
    assert g["リフト（倍）"].iloc[0] > 1.7 and g["当たり率（適合率）"].is_monotonic_decreasing
    roi = roi_table(yte, p, Xte["monetary"])
    assert roi["費用対効果（倍）"].iloc[0] > roi["費用対効果（倍）"].iloc[-1]
    # 実践知6：キャンセルを差し引くと、巨額注文→全量キャンセルの顧客の「見かけの価値」が消える
    deploy_gross = make_features(inv, b, 12, net=False)
    deploy_net = make_features(inv, b, 12, net=True)
    assert deploy_gross.loc[12346, "monetary"] > 50000 and deploy_net.loc[12346, "monetary"] < 1000
    assert set(segment([0.9, 0.9, 0.1, 0.1], [10, 1, 10, 1], 0.5, 5)) == {"A", "B", "C", "D"}
    print("ok", {k: round(v, 3) for k, v in res.items()})

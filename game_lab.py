"""
ゲーム運営の目で見る ─ 「ゲーム特化型」データ分析を農園の探究に移す計算部品

pages/12_🎮_探究コーナー.py から呼び出します。画面を持たない純粋な関数だけを置き、
`python game_lab.py` で自己チェック（assert）が走ります。

下敷き：ThinkingData『ゲームデータアナリティクス』（翔泳社）の分析の流れ
  収集（4章）→ 指標体系（5章）→ 探索的分析（7.1）→ 因果推論とテスト（7.2）
  → 検証と改善（8〜10章）→ きめ細やかな運営（11章）
を、「農園の体験会・直売所」に置き換えたもの。

対応表（ゲーム ↔ 農園 ↔ 研究での言い方）
  プレイヤー         ↔ 来訪者（匿名ID）                ↔ 観測単位
  チュートリアル突破 ↔ 種まき→収穫→パン焼き の各段     ↔ ファネル（段ごとの残存率）
  翌日継続率         ↔ 翌月の再来訪率                  ↔ コホート別リテンション
  課金率・ARPPU      ↔ 購入率・客単価                  ↔ 指標の掛け算分解（KPIツリー）
  プレイヤー分類     ↔ 来訪の仕方のタイプ               ↔ k-means＋主成分分析（PCA）
  A/Bテスト          ↔ 案内チラシ2種                    ↔ 並べ替え検定・ベータ分布の事後確率
  きめ細やかな運営   ↔ 次に勧める体験メニュー           ↔ 多腕バンディット（トンプソン抽出）

方針
  - 初期表示はすべて架空データ（実測ではありません）。氏名は扱わず、IDだけ。
  - 外部ライブラリは numpy・pandas だけ（scikit-learn なしで中身が読める実装）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ─────────────────────────────────────────────
# ① 集める：データプラン（何を・いつ・どの形で記録するか）
# ─────────────────────────────────────────────
EVENT_COLS = ["日付", "来訪者ID", "できごと", "経路", "チラシ", "金額"]
STEPS = ["来訪", "種まき体験", "収穫体験", "パン焼き体験", "購入"]  # ファネルの順
ROUTES = ["学校", "SNS", "口コミ", "通りがかり"]
FLYERS = ("A：写真中心", "B：数字中心")

DATA_PLAN = [
    # (項目, 例, 型, なぜ要るか, 守ること)
    ("日付", "2026-11-03", "日付", "月ごとの再来訪を数えるため", "時刻までは取らない"),
    ("来訪者ID", "V0012", "文字", "同じ人の2回目を数えるため", "氏名・連絡先は入れない（対応表は別に鍵付きで保管）"),
    ("できごと", "収穫体験", "選択肢", "ファネルの段を数えるため", f"選択肢は {'・'.join(STEPS)} に固定"),
    ("経路", "SNS", "選択肢", "どこから来た人が残るかを見るため", f"選択肢は {'・'.join(ROUTES)} に固定"),
    ("チラシ", "A：写真中心", "選択肢", "A/Bテストのため（くじで配る）", "受け取ったチラシを本人に選ばせない"),
    ("金額", "600", "整数（円）", "購入率・客単価を出すため", "購入以外の行は 0"),
]


def sample_events(n_visitors: int = 240, seed: int = 2026) -> pd.DataFrame:
    """架空の来訪ログ（実測ではありません）。

    来訪者ごとに「最初の月」「経路」「チラシ（くじ）」「関わりの強さ」を決め、
    ファネルを1段ずつ進むか、翌月以降また来るかを確率で決める。
    チラシBは収穫体験→パン焼き体験の段だけ少し強い（A/Bタブで見つける“正解”）。
    """
    rng = np.random.default_rng(seed)
    months = pd.period_range("2026-10", "2027-03", freq="M")
    route_p = np.array([0.30, 0.30, 0.25, 0.15])
    route_bonus = {"学校": 0.10, "SNS": -0.05, "口コミ": 0.15, "通りがかり": -0.15}
    route_spend = {"学校": 0.55, "SNS": 1.0, "口コミ": 1.25, "通りがかり": 0.9}
    rows = []
    for i in range(n_visitors):
        vid = f"V{i + 1:04d}"
        first = int(rng.integers(0, len(months) - 1))
        route = ROUTES[int(rng.choice(len(ROUTES), p=route_p))]
        flyer = FLYERS[int(rng.integers(0, 2))]  # くじ
        engage = float(np.clip(rng.normal(0.5 + route_bonus[route], 0.18), 0.05, 0.95))
        m = first
        while m < len(months):
            day = months[m].to_timestamp() + pd.Timedelta(days=int(rng.integers(0, 27)))
            d = day.strftime("%Y-%m-%d")
            p_next = [0.80, 0.70, 0.55, 0.60]  # 来訪→種まき→収穫→パン焼き→購入 の基本確率
            rows.append((d, vid, STEPS[0], route, flyer, 0))
            for k in range(1, len(STEPS)):
                p = p_next[k - 1] * (0.6 + 0.8 * engage)
                if k == 3 and flyer == FLYERS[1]:
                    p += 0.12
                if rng.random() > min(p, 0.97):
                    break
                amt = 0
                if STEPS[k] == "購入":
                    amt = int(round(rng.gamma(4.0, 220 * route_spend[route] * (0.7 + engage)) / 10) * 10)
                rows.append((d, vid, STEPS[k], route, flyer, amt))
            # 翌月また来るか（関わりが強いほど来る）
            if rng.random() > 0.15 + 0.55 * engage:
                break
            m += 1
    df = pd.DataFrame(rows, columns=EVENT_COLS)
    return df.sort_values(["日付", "来訪者ID"]).reset_index(drop=True)


def normalize_events(df: pd.DataFrame) -> pd.DataFrame:
    """列をそろえ、型を直す（読み込んだCSVにも使う）。"""
    out = df.copy()
    for c in EVENT_COLS:
        if c not in out.columns:
            out[c] = np.nan
    out = out[EVENT_COLS]
    out["日付"] = pd.to_datetime(out["日付"], errors="coerce")
    out["来訪者ID"] = out["来訪者ID"].astype("string").str.strip()
    out["金額"] = pd.to_numeric(out["金額"], errors="coerce").fillna(0).astype(int)
    return out


def quality_report(df: pd.DataFrame) -> pd.DataFrame:
    """データ品質チェック（書籍4.4.2の考え方）：記入漏れ・選択肢外・ありえない値・重複。"""
    issues = []
    for i, r in df.iterrows():
        row = i + 1
        if pd.isna(r["日付"]):
            issues.append((row, "日付", "日付が読めない"))
        if pd.isna(r["来訪者ID"]) or str(r["来訪者ID"]).strip() == "":
            issues.append((row, "来訪者ID", "IDが空"))
        if r["できごと"] not in STEPS:
            issues.append((row, "できごと", f"選択肢外：{r['できごと']}"))
        if r["経路"] not in ROUTES:
            issues.append((row, "経路", f"選択肢外：{r['経路']}"))
        if r["チラシ"] not in FLYERS:
            issues.append((row, "チラシ", f"選択肢外：{r['チラシ']}"))
        if r["金額"] < 0:
            issues.append((row, "金額", "マイナスの金額"))
        if r["できごと"] != "購入" and r["金額"] != 0:
            issues.append((row, "金額", "購入以外の行に金額がある"))
    dup = df.duplicated(subset=["日付", "来訪者ID", "できごと"], keep="first")
    for i in np.flatnonzero(dup.to_numpy()):
        issues.append((int(i) + 1, "行全体", "同じ日・同じ人・同じできごとが重複"))
    return pd.DataFrame(issues, columns=["行", "列", "内容"])


# ─────────────────────────────────────────────
# ② 指標をつくる：KPIツリー・ファネル・リテンション・アラート
# ─────────────────────────────────────────────
def visits(df: pd.DataFrame) -> pd.DataFrame:
    """1行＝1回の来訪（人×日）。その日にどの段まで進んだかと、使った金額。"""
    order = {s: k for k, s in enumerate(STEPS)}
    g = df.assign(段=df["できごと"].map(order)).groupby(["来訪者ID", "日付"], as_index=False)
    v = g.agg(到達段=("段", "max"), 金額=("金額", "sum"), 経路=("経路", "first"), チラシ=("チラシ", "first"))
    v["月"] = v["日付"].dt.to_period("M")
    return v


def kpi_tree(df: pd.DataFrame) -> pd.DataFrame:
    """月ごとに 売上 = 来訪数 × 購入率 × 客単価 に分解する（書籍5章の指標体系の考え方）。"""
    v = visits(df)
    buy = v["到達段"] == len(STEPS) - 1
    g = v.assign(購入=buy).groupby("月")
    out = pd.DataFrame({
        "来訪数": g.size(),
        "購入数": g["購入"].sum(),
        "売上": g["金額"].sum(),
    })
    out["購入率"] = out["購入数"] / out["来訪数"]
    out["客単価"] = (out["売上"] / out["購入数"].replace(0, np.nan)).fillna(0)
    out.index = out.index.astype(str)
    return out.reset_index()


def decompose_change(before: pd.Series, after: pd.Series) -> pd.DataFrame:
    """売上の変化を「来訪数・購入率・客単価」のどれが動かしたかに分ける（対数での寄与）。

    売上 = A×B×C なので log売上 = logA + logB + logC。各項の変化の割合で、売上の差を按分する。
    """
    keys = ["来訪数", "購入率", "客単価"]
    d = {k: np.log(after[k]) - np.log(before[k]) for k in keys}
    total = sum(d.values())
    diff = float(after["売上"] - before["売上"])
    share = {k: (d[k] / total if total != 0 else 1 / 3) for k in keys}
    return pd.DataFrame({
        "指標": keys,
        "前": [before[k] for k in keys],
        "後": [after[k] for k in keys],
        "変化率": [after[k] / before[k] - 1 for k in keys],
        "売上の差への寄与（円）": [diff * share[k] for k in keys],
    })


def funnel(df: pd.DataFrame, by: str | None = None) -> pd.DataFrame:
    """段ごとに「そこまで進んだ来訪の数」と、前の段からの残存率（チュートリアル突破率の考え方）。"""
    v = visits(df)
    groups = [("全体", v)] if by is None else list(v.groupby(by))
    rows = []
    for name, gv in groups:
        n0 = len(gv)
        prev = n0
        for k, s in enumerate(STEPS):
            n = int((gv["到達段"] >= k).sum())
            rows.append((name, k, s, n, n / n0 if n0 else np.nan, n / prev if prev else np.nan))
            prev = n
    return pd.DataFrame(rows, columns=["グループ", "順", "段", "人数", "最初からの割合", "前の段からの残存率"])


def retention(df: pd.DataFrame) -> pd.DataFrame:
    """コホート表：初来訪の月ごとに、k か月後にも来た人の割合（翌日継続率の“月”版）。"""
    v = visits(df)
    first = v.groupby("来訪者ID")["月"].min().rename("初回月")
    v = v.join(first, on="来訪者ID")
    v["経過月"] = (v["月"] - v["初回月"]).apply(lambda x: x.n)
    size = v.groupby("初回月")["来訪者ID"].nunique()
    act = v.groupby(["初回月", "経過月"])["来訪者ID"].nunique().unstack(fill_value=0)
    rate = act.div(size, axis=0)
    rate.index = rate.index.astype(str)
    rate.columns = [f"{c}か月後" for c in rate.columns]
    rate.insert(0, "人数", size.values)
    return rate


def alerts(series: pd.Series, window: int = 3, k: float = 2.0) -> pd.DataFrame:
    """直前 window 個の平均±k×標準偏差から外れた点に印をつける（書籍5.3.2のアラート）。"""
    s = series.astype(float)
    mu = s.shift(1).rolling(window, min_periods=window).mean()
    sd = s.shift(1).rolling(window, min_periods=window).std(ddof=1)
    lo, hi = mu - k * sd, mu + k * sd
    flag = (s < lo) | (s > hi)
    return pd.DataFrame({"値": s, "下限": lo, "上限": hi, "アラート": flag.fillna(False)})


# ─────────────────────────────────────────────
# ③ 探す：来訪者ごとの特徴・相関・k-means・PCA
# ─────────────────────────────────────────────
FEATURES = ["来訪回数", "最深到達段", "購入回数", "合計金額", "利用月数"]


def visitor_features(df: pd.DataFrame) -> pd.DataFrame:
    """1行＝1人。探索的分析に使う特徴量。"""
    v = visits(df)
    g = v.groupby("来訪者ID")
    f = pd.DataFrame({
        "来訪回数": g.size(),
        "最深到達段": g["到達段"].max(),
        "購入回数": g["到達段"].apply(lambda s: int((s == len(STEPS) - 1).sum())),
        "合計金額": g["金額"].sum(),
        "利用月数": g["月"].nunique(),
        "経路": g["経路"].first(),
        "チラシ": g["チラシ"].first(),
    })
    return f.reset_index()


def standardize(x: np.ndarray) -> np.ndarray:
    sd = x.std(axis=0, ddof=0)
    sd[sd == 0] = 1.0
    return (x - x.mean(axis=0)) / sd


def pca(x: np.ndarray, n: int = 2) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """主成分分析（特異値分解）。戻り値：得点（行×n）、寄与率、負荷量（n×特徴）。"""
    z = standardize(x)
    u, s, vt = np.linalg.svd(z, full_matrices=False)
    var = s ** 2 / (s ** 2).sum()
    return z @ vt[:n].T, var[:n], vt[:n]


def kmeans(x: np.ndarray, k: int, seed: int = 0, n_init: int = 10, iters: int = 100) -> tuple[np.ndarray, float]:
    """k-means（k-means++ で初期化、n_init 回やって一番まとまりの良いもの）。戻り値：所属、群内平方和。"""
    z = standardize(x)
    rng = np.random.default_rng(seed)
    best = (None, np.inf)
    for _ in range(n_init):
        c = [z[rng.integers(len(z))]]
        for _ in range(1, k):
            d2 = np.min([((z - ci) ** 2).sum(axis=1) for ci in c], axis=0)
            c.append(z[rng.choice(len(z), p=d2 / d2.sum())] if d2.sum() > 0 else z[rng.integers(len(z))])
        c = np.array(c)
        for _ in range(iters):
            lab = np.argmin(((z[:, None, :] - c[None]) ** 2).sum(axis=2), axis=1)
            newc = np.array([z[lab == j].mean(axis=0) if (lab == j).any() else c[j] for j in range(k)])
            if np.allclose(newc, c):
                break
            c = newc
        sse = float(((z - c[lab]) ** 2).sum())
        if sse < best[1]:
            best = (lab, sse)
    lab = best[0]
    # 合計金額の小さい順にクラスタ番号を振り直す（見るたびに番号が入れ替わらないように）
    spend_col = FEATURES.index("合計金額") if x.shape[1] == len(FEATURES) else 0
    order = np.argsort([x[lab == j, spend_col].mean() for j in range(k)])
    remap = {int(old): new for new, old in enumerate(order)}
    return np.array([remap[int(i)] for i in lab]), best[1]


def elbow(x: np.ndarray, k_max: int = 6, seed: int = 0) -> pd.DataFrame:
    return pd.DataFrame([(k, kmeans(x, k, seed)[1]) for k in range(1, k_max + 1)], columns=["k", "群内平方和"])


# ─────────────────────────────────────────────
# ④ 確かめる：A/Bテスト（並べ替え検定・ベイズ）
# ─────────────────────────────────────────────
def ab_table(df: pd.DataFrame, step: str = "パン焼き体験", base: str = "収穫体験") -> pd.DataFrame:
    """チラシごとに「base の段まで来た人のうち、step まで進んだ人」を数える（人単位）。"""
    f = visitor_features(df)
    kb, ks = STEPS.index(base), STEPS.index(step)
    f = f[f["最深到達段"] >= kb]
    g = f.assign(成功=(f["最深到達段"] >= ks).astype(int)).groupby("チラシ")["成功"]
    out = pd.DataFrame({"人数": g.size(), "成功": g.sum()})
    out["割合"] = out["成功"] / out["人数"]
    return out.reindex(list(FLYERS)).fillna(0)


def permutation_test(y: np.ndarray, group: np.ndarray, n_perm: int = 5000, seed: int = 0) -> tuple[float, float, np.ndarray]:
    """2群の平均の差（group==1 − group==0）と、くじを引き直したときに同じくらい大きな差が出る割合（両側p）。"""
    y = np.asarray(y, float)
    g = np.asarray(group, bool)
    obs = y[g].mean() - y[~g].mean()
    rng = np.random.default_rng(seed)
    null = np.empty(n_perm)
    for i in range(n_perm):
        p = rng.permutation(g)
        null[i] = y[p].mean() - y[~p].mean()
    pval = (np.sum(np.abs(null) >= abs(obs) - 1e-12) + 1) / (n_perm + 1)
    return float(obs), float(pval), null


def beta_posterior(success: int, n: int, a0: float = 1.0, b0: float = 1.0) -> tuple[float, float]:
    """一様な事前分布 Beta(1,1) から、観測後の事後分布 Beta(a, b) のパラメータ。"""
    return a0 + success, b0 + n - success


def prob_b_beats_a(sa: int, na: int, sb: int, nb: int, draws: int = 40000, seed: int = 0) -> tuple[float, np.ndarray, np.ndarray]:
    """P(B の割合 > A の割合 | データ) をサンプリングで求める。"""
    rng = np.random.default_rng(seed)
    pa = rng.beta(*beta_posterior(sa, na), size=draws)
    pb = rng.beta(*beta_posterior(sb, nb), size=draws)
    return float((pb > pa).mean()), pa, pb


def sample_size_per_group(p0: float, lift: float) -> int:
    """2つの割合の差を見つけるのに要る1群あたりの人数（有意水準5%両側・検出力80%の近似式）。"""
    p1 = min(max(p0 + lift, 1e-6), 1 - 1e-6)
    z_a, z_b = 1.959964, 0.841621
    pbar = (p0 + p1) / 2
    num = (z_a * np.sqrt(2 * pbar * (1 - pbar)) + z_b * np.sqrt(p0 * (1 - p0) + p1 * (1 - p1))) ** 2
    return int(np.ceil(num / (p1 - p0) ** 2)) if p1 != p0 else 10 ** 9


# ─────────────────────────────────────────────
# ⑤ 試し続ける：多腕バンディット（トンプソン抽出 vs 均等配分）
# ─────────────────────────────────────────────
def bandit_sim(true_p: list[float], n_rounds: int = 300, seed: int = 0) -> pd.DataFrame:
    """毎回「どの体験メニューを勧めるか」を選び、満足（1/0）を受け取る。

    トンプソン抽出：各メニューの満足率をベータ分布で持ち、引いた値が最大のメニューを選ぶ（ベイズ推論×強化学習）。
    均等配分：順番に回す（いわゆる“全部同じだけ試す”A/Bテスト型）。
    戻り値は回ごとの累積の取りこぼし（最善メニューを選んでいれば得られた満足との差の期待値）。
    """
    rng = np.random.default_rng(seed)
    p = np.asarray(true_p, float)
    best = p.max()
    a = np.ones(len(p))
    b = np.ones(len(p))
    reg_ts, reg_rr, picks = [], [], []
    cum_ts = cum_rr = 0.0
    for t in range(n_rounds):
        arm = int(np.argmax(rng.beta(a, b)))
        r = rng.random() < p[arm]
        a[arm] += r
        b[arm] += 1 - r
        cum_ts += best - p[arm]
        rr = t % len(p)
        cum_rr += best - p[rr]
        reg_ts.append(cum_ts)
        reg_rr.append(cum_rr)
        picks.append(arm)
    return pd.DataFrame({"回": np.arange(1, n_rounds + 1), "トンプソン抽出": reg_ts, "均等配分": reg_rr, "選んだメニュー": picks})


# ─────────────────────────────────────────────
# 自己チェック
# ─────────────────────────────────────────────
if __name__ == "__main__":
    ev = normalize_events(sample_events())
    assert set(ev["できごと"]) <= set(STEPS)
    assert quality_report(ev).empty, quality_report(ev).head()

    bad = ev.head(3).copy()
    bad.loc[0, "経路"] = "テレビ"
    bad.loc[1, "金額"] = 500
    bad = pd.concat([bad, bad.iloc[[2]]], ignore_index=True)
    q = quality_report(bad)
    assert {"経路", "金額", "行全体"} <= set(q["列"]), q

    kt = kpi_tree(ev)
    assert np.allclose(kt["来訪数"] * kt["購入率"] * kt["客単価"], kt["売上"])
    dc = decompose_change(kt.iloc[1], kt.iloc[2])
    assert abs(dc["売上の差への寄与（円）"].sum() - (kt.iloc[2]["売上"] - kt.iloc[1]["売上"])) < 1e-6

    fu = funnel(ev)
    assert fu["人数"].is_monotonic_decreasing and fu["人数"].iloc[0] == len(visits(ev))

    rt = retention(ev)
    assert (rt["0か月後"] == 1).all()

    al = alerts(pd.Series([10, 11, 10, 11, 30, 10]), window=3, k=2)
    assert al["アラート"].tolist() == [False, False, False, False, True, False]

    vf = visitor_features(ev)
    X = vf[FEATURES].to_numpy(float)
    sc, var, load = pca(X)
    assert sc.shape == (len(vf), 2) and 0 < var.sum() <= 1 + 1e-9
    lab, sse = kmeans(X, 3)
    assert set(lab) == {0, 1, 2}
    el = elbow(X, 4)
    assert el["群内平方和"].is_monotonic_decreasing

    # 並べ替え検定：差のないデータでは p が大きい、明らかな差では小さい
    rng = np.random.default_rng(1)
    g = np.r_[np.zeros(50), np.ones(50)]
    assert permutation_test(rng.normal(0, 1, 100), g, 2000)[1] > 0.01
    assert permutation_test(np.r_[np.zeros(50), np.ones(50)], g, 2000)[1] < 0.01

    pb, _, _ = prob_b_beats_a(30, 100, 45, 100)
    assert pb > 0.95
    assert 300 < sample_size_per_group(0.30, 0.10) < 400  # 教科書的な値（約356）

    bs = bandit_sim([0.3, 0.5, 0.7], 500, seed=3)
    assert bs["トンプソン抽出"].iloc[-1] < bs["均等配分"].iloc[-1]

    ab = ab_table(ev)
    print("ok", len(ev), "行 /", len(vf), "人 / A/B:", ab["割合"].round(2).to_dict())

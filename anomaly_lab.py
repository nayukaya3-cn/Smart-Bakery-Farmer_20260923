"""
異常検知の実践知 ─ 「いつもと違う」を、データの形から手法を選んで見つける計算部品

pages/13_🚨_異常検知の実践知.py から呼び出します。画面を持たない純粋な関数だけを置き、
`python anomaly_lab.py` で自己チェック（assert）が走ります。

探究の3つの問い（ページのタブと対応）
  ❶ 対象データをどう分析するか？     → diagnose()：型・変数の数・時間順・入出力・分布の形・ラベル
  ❷ 分析結果に基づきどの手法を選ぶか？ → recommend()：診断カードから、理由つきで手法を選ぶ
  ❸ 手法をどう実践し、どう評価するか？ → split() → score() → threshold() → evaluate()

下敷きにした考え方（文章・データ・コードはこのアプリ独自のもので、書籍の転載ではありません）
  - 中村謙太『まるごと学べる 異常検知の実践知』：手法の使い分け（1変数／計数／多変数／入出力／ベイズ）、
    前処理と性能評価、実システムで陥りやすい落とし穴
  - 笛田薫 監修・江崎剛史・李鍾賛『Pythonではじめる異常検知入門』：異常度と閾値、
    データの特性（入出力の構造・時系列性）でアプローチを決める
  - 馬場嘉朗『マイコンによる異常検知入門』：センサ → 収集 → 異常検知を自分の手で通す

5つの架空データ（どれも実測ではありません。正解ラベルは「評価のためだけ」に使う）
  🍞 パンの重さ          1変数        → 1変数ホテリング／ロバストz
  🔐 ログイン失敗回数    計数・時刻つき → ポアソン（時間帯別）
  🥖 製パン工程          多変数        → ホテリングT²／MT法／k近傍（＋教師ありとの比較）
  🌡️ 日射とハウス内温度  入出力        → 回帰の残差
  📈 ハウス気温の時系列  時系列        → 季節の基準線との差＋AR(1)の残差

方針
  - 外部ライブラリは numpy・pandas だけ（scikit-learn なしで中身が読める実装）。
  - 閾値は「テストデータを見ずに」決める（学習＝正常だけ／検証＝閾値決め／テスト＝評価だけ）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import NormalDist

import numpy as np
import pandas as pd

LABEL = "ラベル"          # 1＝異常（評価用の正解。学習には使わない）
TYPE = "異常の種類"        # 正常なら「正常」

# ─────────────────────────────────────────────
# 0. 道具：χ²分布の上側点・ポアソン分布の上側確率（scipy なし）
# ─────────────────────────────────────────────


def chi2_ppf(p: float, k: int) -> float:
    """自由度 k のχ²分布の p 分位点。k=1,2 は厳密、3以上は Wilson–Hilferty 近似（誤差1%未満）。"""
    if k == 1:
        return NormalDist().inv_cdf((1 + p) / 2) ** 2
    if k == 2:
        return -2.0 * math.log(1 - p)
    z = NormalDist().inv_cdf(p)
    return k * (1 - 2 / (9 * k) + z * math.sqrt(2 / (9 * k))) ** 3


def poisson_sf(x: np.ndarray, lam: np.ndarray) -> np.ndarray:
    """P(X ≥ x | λ)：x回以上起きる確率（上側確率）。"""
    x = np.asarray(x, int)
    lam = np.broadcast_to(np.asarray(lam, float), x.shape)
    out = np.ones(x.shape, float)
    for i in np.ndindex(x.shape):
        k, lm = int(x[i]), max(float(lam[i]), 1e-9)
        if k <= 0:
            continue
        logp = [j * math.log(lm) - lm - math.lgamma(j + 1) for j in range(k)]
        out[i] = max(1.0 - float(np.exp(logp).sum()), 1e-300)
    return out


# ─────────────────────────────────────────────
# 1. 架空データ（5種）
# ─────────────────────────────────────────────
@dataclass
class Dataset:
    key: str
    name: str
    df: pd.DataFrame
    cols: list[str]                       # 異常度の計算に使う数値の列
    kind: str                             # 1変数／計数／多変数／入出力／時系列
    story: str                            # どんな現場の、どんな「いつもと違う」か
    time_col: str | None = None
    group_col: str | None = None          # 計数データの「いつもの回数」を分ける列（時間帯など）
    inputs: list[str] | None = None       # 入出力データ：原因側
    output: str | None = None             # 入出力データ：結果側
    known_types: list[str] = field(default_factory=list)  # 過去に記録が残っている異常（教師ありで使える）
    period: int | None = None             # 時系列の周期（1日＝24時間）


def _finish(df: pd.DataFrame) -> pd.DataFrame:
    df[TYPE] = df[TYPE].fillna("正常")
    df[LABEL] = (df[TYPE] != "正常").astype(int)
    return df.reset_index(drop=True)


def bread_weight(n: int = 400, seed: int = 0) -> Dataset:
    rng = np.random.default_rng(seed)
    w = rng.normal(1000, 10, n)
    t = np.array([None] * n, dtype=object)
    for name, k, lo, hi in [("分割ミス（軽い）", 0.025, -45, -25), ("生焼け（重い）", 0.025, 25, 40)]:
        idx = rng.choice(np.where(t == None)[0], max(1, int(n * k)), replace=False)  # noqa: E711
        w[idx] += rng.uniform(lo, hi, len(idx))
        t[idx] = name
    df = _finish(pd.DataFrame({"製造順": np.arange(1, n + 1), "重さ_g": w.round(1), TYPE: t}))
    return Dataset("bread", "🍞 パンの重さ（1変数）", df, ["重さ_g"], "1変数",
                   "1000gの食パンを毎日量る。分割機のミスで軽いもの、焼成不足で水分が残って重いものが混ざる。")


def login_fail(days: int = 28, seed: int = 0) -> Dataset:
    rng = np.random.default_rng(seed)
    t = pd.date_range("2026-11-01", periods=days * 24, freq="h")
    hour = t.hour.to_numpy()
    lam = np.where(hour < 6, 0.3, np.where((hour >= 8) & (hour <= 19), 2.5, 1.0))
    y = rng.poisson(lam)
    typ = np.array([None] * len(t), dtype=object)
    for d in range(1, days, 2):  # 2日に1回くらい、どこかで攻撃
        if rng.random() < 0.5:   # 昼の総当たり：回数が一気に増える
            h = d * 24 + int(rng.integers(9, 18))
            y[h] += int(rng.integers(9, 16))
            typ[h] = "総当たり攻撃（昼）"
        else:                    # 深夜の少数試行：昼なら普通の回数だが、深夜にしては多い
            h = d * 24 + int(rng.integers(1, 5))
            y[h] += int(rng.integers(4, 6))
            typ[h] = "深夜の少数試行"
    df = _finish(pd.DataFrame({"時刻": t, "時間帯": hour, "失敗回数": y, TYPE: typ}))
    return Dataset("login", "🔐 ログイン失敗回数（計数）", df, ["失敗回数"], "計数",
                   "農園アプリの1時間ごとのログイン失敗回数。昼の総当たり攻撃と、深夜にこっそり数回だけ試す攻撃が混ざる。",
                   time_col="時刻", group_col="時間帯", period=24)


DOUGH_COLS = ["捏ね上げ温度_℃", "一次発酵_分", "焼成温度_℃", "焼き上がり重量_g", "焼き色_L"]


def dough(n: int = 480, seed: int = 0) -> Dataset:
    rng = np.random.default_rng(seed)
    T = rng.normal(26, 0.8, n)
    F = 60 - 6 * (T - 26) + rng.normal(0, 3, n)
    O_true = rng.normal(210, 3, n)
    W = 1000 - 1.2 * (F - 60) + rng.normal(0, 6, n)
    L = 62 - 0.8 * (O_true - 210) + rng.normal(0, 0.8, n)
    O = O_true.copy()
    typ = np.array([None] * n, dtype=object)
    free = lambda: np.where(typ == None)[0]  # noqa: E711,E731
    i1 = rng.choice(free(), int(n * 0.05), replace=False)       # 既知：過発酵（記録が残っている）
    F[i1] += rng.uniform(18, 28, len(i1))
    W[i1] -= rng.uniform(20, 35, len(i1))
    typ[i1] = "過発酵"
    i2 = rng.choice(free(), int(n * 0.04), replace=False)       # 未知：オーブンの温度計が低く表示する
    O[i2] -= rng.uniform(6, 8, len(i2))                         # 表示は低いのに、実際は普段どおり焼けている
    typ[i2] = "温度計のずれ"
    df = _finish(pd.DataFrame(dict(zip(DOUGH_COLS, [T.round(1), F.round(1), O.round(1), W.round(1), L.round(1)]))
                              | {TYPE: typ}))
    df.insert(0, "バッチ", np.arange(1, n + 1))
    return Dataset("dough", "🥖 製パン工程（多変数）", df, DOUGH_COLS, "多変数",
                   "1バッチごとに5項目を記録。1つずつ見ると普通の範囲なのに、組み合わせが崩れている異常（温度計のずれ）がある。",
                   known_types=["過発酵"])


def house_io(n: int = 500, seed: int = 0) -> Dataset:
    rng = np.random.default_rng(seed)
    sun = rng.uniform(0, 900, n)
    out = rng.normal(15, 4, n)
    inside = out + 0.012 * sun + rng.normal(0, 1.0, n)
    typ = np.array([None] * n, dtype=object)
    i1 = rng.choice(np.where(sun > 150)[0], int(n * 0.04), replace=False)
    inside[i1] += rng.uniform(4, 7, len(i1))
    typ[i1] = "換気窓が開かない"
    i2 = rng.choice(np.where(typ == None)[0], int(n * 0.02), replace=False)  # noqa: E711
    inside[i2] -= rng.uniform(5, 8, len(i2))
    typ[i2] = "温度センサーの汚れ（低く出る）"
    df = _finish(pd.DataFrame({"日射_W": sun.round(0), "外気温_℃": out.round(1),
                               "ハウス内温度_℃": inside.round(1), TYPE: typ}))
    return Dataset("house_io", "🌡️ 日射とハウス内温度（入出力）", df, ["日射_W", "外気温_℃", "ハウス内温度_℃"], "入出力",
                   "晴れて外が暖かければハウスは暑くなる（＝原因と結果がある）。換気窓が開かない日だけを見つけたい。",
                   inputs=["日射_W", "外気温_℃"], output="ハウス内温度_℃")


def house_ts(days: int = 28, seed: int = 0) -> Dataset:
    rng = np.random.default_rng(seed)
    t = pd.date_range("2026-11-01", periods=days * 24, freq="h")
    h = t.hour.to_numpy()
    e = np.zeros(len(t))
    for i in range(1, len(t)):
        e[i] = 0.6 * e[i - 1] + rng.normal(0, 0.5)
    y = 18 - 0.1 * np.arange(len(t)) / 24 + 6 * np.sin((h - 9) / 24 * 2 * np.pi) + e
    typ = np.array([None] * len(t), dtype=object)
    for j, d in enumerate(range(3, days, 2)):
        if j % 2 == 0:  # 深夜に暖房機が止まらず暑くなる：値そのものは昼間なら普通
            s = d * 24 + int(rng.integers(1, 4))
            y[s:s + 3] += np.array([3.5, 5.0, 4.0])
            typ[s:s + 3] = "深夜の過昇温"
        else:           # センサーが固まって同じ値を出し続ける
            s = d * 24 + int(rng.integers(8, 14))
            y[s:s + 6] = y[s]
            typ[s + 1:s + 6] = "センサー固着"
    df = _finish(pd.DataFrame({"時刻": t, "気温_℃": y.round(2), TYPE: typ}))
    return Dataset("house_ts", "📈 ハウス気温の時系列", df, ["気温_℃"], "時系列",
                   "1時間ごとのハウス気温。昼は暑く夜は寒いのが「いつも」。深夜の過昇温とセンサー固着を見つけたい。",
                   time_col="時刻", period=24)


SAMPLES = {"bread": bread_weight, "login": login_fail, "dough": dough, "house_io": house_io, "house_ts": house_ts}


def sample(key: str, seed: int = 0) -> Dataset:
    return SAMPLES[key](seed=seed)


def from_upload(df: pd.DataFrame, cols: list[str], label_col: str | None = None, time_col: str | None = None,
                output: str | None = None, period: int | None = None) -> Dataset:
    """読み込んだCSVを Dataset にする。ラベル列があれば評価に使う（0/1、または「正常」以外の文字）。"""
    d = df.copy()
    if time_col:
        d[time_col] = pd.to_datetime(d[time_col], errors="coerce")
        d = d.dropna(subset=[time_col]).sort_values(time_col)
    d = d.dropna(subset=cols)
    if label_col and label_col in d:
        lab = d[label_col]
        if pd.api.types.is_numeric_dtype(lab):
            d[TYPE] = np.where(lab.fillna(0).astype(float) > 0, "異常（ラベル）", "正常")
        else:
            d[TYPE] = lab.fillna("正常").astype(str).replace({"": "正常", "0": "正常"})
    else:
        d[TYPE] = "正常"
    d = _finish(d)
    inputs = [c for c in cols if c != output] if output else None
    is_count = all(pd.api.types.is_integer_dtype(d[c]) and (d[c] >= 0).all() for c in cols)
    kind = ("入出力" if output else "時系列" if time_col and len(cols) == 1 and not is_count
            else "計数" if is_count and len(cols) == 1 else "多変数" if len(cols) > 1 else "1変数")
    return Dataset("upload", "📂 読み込んだデータ", d, cols, kind, "アップロードした記録。",
                   time_col=time_col, inputs=inputs, output=output, period=period)


# ─────────────────────────────────────────────
# ❶ 対象データをどう分析するか：診断カード
# ─────────────────────────────────────────────
def _skew_kurt(x: np.ndarray) -> tuple[float, float]:
    x = x[np.isfinite(x)]
    if len(x) < 4 or x.std() == 0:
        return 0.0, 0.0
    z = (x - x.mean()) / x.std()
    return float((z ** 3).mean()), float((z ** 4).mean() - 3)


def acf(x: np.ndarray, lag: int) -> float:
    x = np.asarray(x, float)
    if len(x) <= lag + 2 or x.std() == 0:
        return 0.0
    return float(np.corrcoef(x[:-lag], x[lag:])[0, 1])


def diagnose(ds: Dataset) -> dict:
    """❶ のチェックリストを数字で埋める。ラベルは「何割が異常か」を知るためだけに数える。"""
    X = ds.df[ds.cols].to_numpy(float)
    is_count = bool(all(np.allclose(ds.df[c], np.round(ds.df[c])) and (ds.df[c] >= 0).all() for c in ds.cols))
    sk = [_skew_kurt(X[:, j]) for j in range(X.shape[1])]
    med = np.median(X, 0)
    mad = 1.4826 * np.median(np.abs(X - med), 0)
    core = (np.abs((X - med) / np.where(mad > 0, mad, 1)) < 3.5).all(1)  # 外れ値候補を除いた「本体」
    skc = [_skew_kurt(X[core, j]) for j in range(X.shape[1])]
    corr = ds.df[ds.cols].corr().abs().to_numpy().copy() if len(ds.cols) > 1 else np.zeros((1, 1))
    np.fill_diagonal(corr, 0)
    y0 = X[:, 0] if ds.output is None else ds.df[ds.output].to_numpy(float)
    r1 = acf(y0, 1) if ds.time_col else None
    rP = acf(y0, ds.period) if ds.time_col and ds.period else None
    mean0, var0 = float(X[:, 0].mean()), float(X[:, 0].var())
    n_lab = int(ds.df[LABEL].sum())
    types = ds.df.loc[ds.df[LABEL] == 1, TYPE].value_counts().to_dict()
    return {
        "行数": len(ds.df),
        "変数の数": len(ds.cols),
        "値の型": "計数（0,1,2,…の回数）" if is_count else "連続値（重さ・温度など）",
        "計数": is_count,
        "時間の順番": bool(ds.time_col),
        "1時点前との相関 r(1)": r1,
        "1周期前との相関 r(周期)": rP,
        "入出力（原因→結果）": bool(ds.output),
        "変数どうしの最大相関": float(corr.max()) if len(ds.cols) > 1 else None,
        "歪度（最大の絶対値）": max(abs(s) for s, _ in sk),
        "尖度（最大の絶対値）": max(abs(k) for _, k in sk),
        "歪度（外れ値候補を除く）": max(abs(v) for v, _ in skc),
        "尖度（外れ値候補を除く）": max(abs(v) for _, v in skc),
        "外れ値候補の割合": float(1 - core.mean()),
        "分散/平均（計数のばらつき）": var0 / mean0 if is_count and mean0 > 0 else None,
        "正解ラベルのある異常": n_lab,
        "異常の割合": n_lab / max(len(ds.df), 1),
        "異常の種類": types,
        "記録が残っている異常の種類": list(ds.known_types),
    }


def _is_normal(skew: float, kurt: float) -> bool:
    return skew < 0.5 and kurt < 1.0


def findings(dg: dict) -> list[str]:
    """診断カードを、人が読む所見に直す（❷ の手法選びの根拠になる文）。"""
    out = []
    out.append(f"変数は {dg['変数の数']} 個、値は {dg['値の型']}。")
    if dg["時間の順番"]:
        r1, rP = dg["1時点前との相関 r(1)"], dg["1周期前との相関 r(周期)"]
        out.append(f"時間の順番がある。r(1)={r1:.2f}" + (f"、r(周期)={rP:.2f}" if rP is not None else "")
                   + " → 1行ずつを独立と見なせない" if abs(r1) > 0.5 else
                   f"時間の順番はあるが r(1)={r1:.2f} と弱い → 時間帯で「いつもの値」が違うかを見る")
    if dg["入出力（原因→結果）"]:
        out.append("原因（入力）と結果（出力）がある → 「入力から予想される値」とのずれを見る")
    if dg["変数どうしの最大相関"] is not None:
        c = dg["変数どうしの最大相関"]
        out.append(f"変数どうしの最大相関 {c:.2f} → " + ("組み合わせの崩れを見る必要がある" if c > 0.3
                                                     else "変数ごとにほぼ独立"))
    sk, ku = dg["歪度（最大の絶対値）"], dg["尖度（最大の絶対値）"]
    skc, kuc, po = dg["歪度（外れ値候補を除く）"], dg["尖度（外れ値候補を除く）"], dg["外れ値候補の割合"]
    if not dg["計数"]:
        out.append(f"全体の歪度 {sk:.2f}・尖度 {ku:.2f}／外れ値候補（中央値から3.5MAD超）{po:.1%} を除くと 歪度 {skc:.2f}・尖度 {kuc:.2f} → "
                   + ("本体は正規分布に近い" if _is_normal(skc, kuc) else "本体も正規分布から遠い（もともと偏った・山が複数ある分布）")
                   + ("。裾の重さは外れ値の混入による" if po > 0.01 and not _is_normal(sk, ku) and _is_normal(skc, kuc) else ""))
    if dg["分散/平均（計数のばらつき）"] is not None:
        r = dg["分散/平均（計数のばらつき）"]
        out.append(f"分散/平均 = {r:.2f} → " + ("ポアソン分布の前提（≒1）に近い" if r < 1.5
                                             else "1より大きい（過分散）：時間帯などで平均が違うものが混ざっている"))
    pct = dg["異常の割合"]
    out.append(f"正解ラベルのある異常は {dg['正解ラベルのある異常']} 件（{pct:.1%}）→ "
               + ("異常はとても少ない：「正常のいつも」を学ぶ教師なしが基本" if pct < 0.1 else "異常が多い：まず記録の定義を疑う"))
    if dg["記録が残っている異常の種類"]:
        out.append("過去に記録がある異常は「" + "・".join(dg["記録が残っている異常の種類"])
                   + "」だけ。記録のない種類の異常が来たら、教師ありでは見つけられない")
    return out


# ─────────────────────────────────────────────
# ❷ どの手法を選ぶか：手法カタログと選び方
# ─────────────────────────────────────────────
METHODS = {
    # 名前: (向いているデータ, 異常度, 閾値, 苦手なこと, 参照)
    "変数ごとの管理図": ("1変数・正規分布", "a = ((x−平均)/標準偏差)²（変数が複数なら最大値）",
                    "χ²(1) の上側点（複数ならボンフェローニ補正）", "組み合わせの崩れ・時間の流れ・偏った分布",
                    "1変数のホテリング理論"),
    "ロバストz（中央値・MAD）": ("1変数・学習データに異常が混ざっていそう", "平均・標準偏差の代わりに中央値・MADで z を出す",
                          "χ²(1) の上側点", "組み合わせの崩れ・時間の流れ", "前処理（外れ値に強い統計量）"),
    "ポアソン（時間帯別）": ("計数データ（回数）", "a = −log10 P(X ≥ x | その時間帯のいつもの回数 λ)",
                    "上側確率 α（例 1%）", "λ が時間帯以外の理由でも変わるとき（過分散）", "計数データ：ポアソン分布の最尤推定"),
    "ホテリングT²": ("多変数・正規分布に近い・変数どうしに相関", "a = (x−μ)ᵀ Σ⁻¹ (x−μ)（マハラノビス距離の2乗）",
                  "χ²(変数の数) の上側点", "多峰・非線形の形、学習データが少ないとき（Σが不安定）", "多変数のホテリング理論"),
    "MT法": ("多変数・品質工学の現場", "D² = T² ÷ 変数の数（正常なら平均がほぼ1）",
            "慣例は D² > 4、理屈では χ²(M)/M", "ホテリングT²と同じ", "マハラノビス・タグチ法"),
    "k近傍距離": ("多変数・分布の形が分からない／多峰", "学習データの k 番目に近い点までの距離（標準化後）",
               "理論の閾値はない → 検証データで決める", "変数が多すぎると距離が効かない（次元の呪い）",
               "ノンパラメトリック手法・距離に基づく異常検知"),
    "回帰の残差": ("入出力（原因→結果）がある", "a = (実測 − 入力から予想した値)² / 残差の分散",
               "χ²(1) の上側点", "入力そのものの異常、原因と結果の関係が非線形", "入出力があるデータの統計モデリング"),
    "時系列の残差": ("時間の順番・周期がある", "季節の基準線（過去3日の同時刻の中央値）との差を AR(1) で予測し、外れ具合を見る",
                "χ²(1) の上側点", "周期が変わる・ゆっくり壊れる（ドリフト）", "時系列情報に基づくアプローチ（差分で定常化）"),
    "固着ルール（同じ値が続く）": ("時系列・センサーの値", "同じ値が何時間続いたか（変化量が0の連続の長さ）",
                       "2時間以上（センサーの雑音があれば、同じ値はふつう続かない）", "固着以外の異常は見えない",
                       "特徴量を自分で作る（マイコンのセンサ監視の定番）"),
    "教師あり（ロジスティック回帰）": ("過去の異常に正解ラベルが十分ある", "異常である確率 P(異常 | x)",
                         "確率 0.5（または検証データで）", "記録のない種類の異常（未知の異常）", "教師あり学習による異常検知の問題点"),
}
METHOD_KINDS = {  # どのデータに使えるか
    "変数ごとの管理図": {"1変数", "多変数", "入出力", "計数", "時系列"},
    "ロバストz（中央値・MAD）": {"1変数", "多変数", "入出力", "時系列"},
    "ポアソン（時間帯別）": {"計数"},
    "ホテリングT²": {"多変数", "入出力"},
    "MT法": {"多変数", "入出力"},
    "k近傍距離": {"多変数", "入出力", "1変数"},
    "回帰の残差": {"入出力"},
    "時系列の残差": {"時系列"},
    "固着ルール（同じ値が続く）": {"時系列"},
    "教師あり（ロジスティック回帰）": {"多変数"},
}


def available(ds: Dataset) -> list[str]:
    ok = [m for m, k in METHOD_KINDS.items() if ds.kind in k]
    if not ds.known_types:
        ok = [m for m in ok if not m.startswith("教師あり")]
    if ds.kind == "時系列" and not ds.period:
        ok = [m for m in ok if m != "時系列の残差"]
    return ok


def recommend(dg: dict, ds: Dataset) -> list[tuple[str, str]]:
    """診断カードから手法を選ぶ。（手法, 理由）を おすすめ順に返す。1つ目が本命、2つ目以降は比べる相手。"""
    rec: list[tuple[str, str]] = []
    if dg["入出力（原因→結果）"]:
        rec.append(("回帰の残差", "原因→結果の関係がある。結果の値そのものではなく「原因から予想される値とのずれ」を見る"))
        rec.append(("変数ごとの管理図", "結果の値だけを見た場合の比較対象（晴れて暑いだけの時間を異常と呼ぶかを確かめる）"))
        rec.append(("ホテリングT²", "入力と出力をまとめて多変数として扱う比較対象"))
    elif dg["計数"]:
        why = "回数のデータ。正規分布ではなくポアソン分布で「この時間帯にこの回数は起こりにくいか」を見る"
        if (dg["分散/平均（計数のばらつき）"] or 0) > 1.5:
            why += "。過分散なので、いつもの回数 λ を時間帯ごとに分ける"
        rec.append(("ポアソン（時間帯別）", why))
        rec.append(("変数ごとの管理図", "正規分布を仮定した場合の比較対象（回数が少ないと当てはまりが悪い）"))
    elif dg["時間の順番"] and abs(dg["1時点前との相関 r(1)"] or 0) > 0.5:
        rec.append(("時系列の残差", "前後の時刻が強く結びつき、周期もある。「この時刻ならいつもはこのくらい」との差を見る"))
        rec.append(("固着ルール（同じ値が続く）", "センサーの値なので「同じ値が続く」故障を、作った特徴量で別に見張る（残差では見えにくい）"))
        rec.append(("変数ごとの管理図", "時間を無視した場合の比較対象（昼の普通の値と夜の異常が区別できない）"))
    elif dg["変数の数"] > 1:
        normal = _is_normal(dg["歪度（外れ値候補を除く）"], dg["尖度（外れ値候補を除く）"])
        if normal and (dg["変数どうしの最大相関"] or 0) > 0.3:
            rec.append(("ホテリングT²", "多変数・ほぼ正規分布・変数どうしに相関がある。組み合わせの崩れを1つの数で測れる"))
        else:
            rec.append(("k近傍距離", "分布の形が正規から遠い。形を仮定せず「近くに仲間がいるか」で見る"))
        rec.append(("変数ごとの管理図", "1つずつ見た場合の比較対象（組み合わせの崩れを見逃すかを確かめる）"))
        if dg["記録が残っている異常の種類"]:
            rec.append(("教師あり（ロジスティック回帰）", "記録が残っている異常から学ぶ比較対象（未知の異常に弱いかを確かめる）"))
        rec.append(("MT法", "ホテリングT²と同じ考え方を品質工学の流儀（D²の平均≒1）で読む"))
        rec.append(("ホテリングT²", "正規分布を仮定した場合の比較対象"))
        rec.append(("k近傍距離", "分布の形を仮定しない比較対象"))
    else:
        if not _is_normal(dg["歪度（外れ値候補を除く）"], dg["尖度（外れ値候補を除く）"]):
            rec.append(("k近傍距離", "1変数だが、外れ値候補を除いても正規分布から遠い。形を仮定しない"))
            rec.append(("ロバストz（中央値・MAD）", "中央値からの離れ具合で見る比較対象"))
        elif dg["外れ値候補の割合"] > 0.01:
            rec.append(("ロバストz（中央値・MAD）", "本体は正規分布に近いが、外れ値候補が混ざっている。"
                        "平均・標準偏差は外れ値に引っ張られるので、中央値・MADで「いつも」を測る"))
            rec.append(("変数ごとの管理図", "平均・標準偏差を使った場合の比較対象（学習データを掃除できれば同等）"))
        else:
            rec.append(("変数ごとの管理図", "1変数・正規分布に近い。平均から標準偏差の何倍離れたかで十分"))
            rec.append(("ロバストz（中央値・MAD）", "学習データに異常が混ざっていた場合の保険"))
    seen, out = set(), []
    for m, w in rec:
        if m not in seen and m in available(ds):
            seen.add(m)
            out.append((m, w))
    return out


# ─────────────────────────────────────────────
# ❸ 実践：分ける → 学ぶ → 異常度 → 閾値 → 評価
# ─────────────────────────────────────────────
def split(ds: Dataset, seed: int = 0, frac=(0.5, 0.25)) -> dict[str, np.ndarray]:
    """学習・検証・テストに分ける。時系列は時間順（未来で過去を学ばない）、それ以外はくじ。"""
    n = len(ds.df)
    idx = np.arange(n) if ds.time_col else np.random.default_rng(seed).permutation(n)
    a, b = int(n * frac[0]), int(n * (frac[0] + frac[1]))
    return {"学習": np.sort(idx[:a]), "検証": np.sort(idx[a:b]), "テスト": np.sort(idx[b:])}


def train_rows(ds: Dataset, sp: dict, clean: bool, method: str) -> np.ndarray:
    """学習に使う行。教師なしは「正常」を学ぶので、clean=True なら記録のある異常を除く。"""
    tr = sp["学習"]
    if method.startswith("教師あり"):
        return tr
    if clean:
        if ds.known_types:   # 消せるのは「記録が残っている」異常だけ（未知の異常は正常のふりをして残る）
            return tr[~ds.df[TYPE].iloc[tr].isin(ds.known_types).to_numpy()]
        return tr[ds.df[LABEL].iloc[tr].to_numpy() == 0]
    return tr


def _z2(X, mu, sd):
    return ((X - mu) / np.where(sd > 0, sd, 1)) ** 2


def logistic_fit(X: np.ndarray, y: np.ndarray, lam: float = 1.0, iters: int = 30) -> np.ndarray:
    """L2つきロジスティック回帰（ニュートン法）。X には切片の列を含める。"""
    w = np.zeros(X.shape[1])
    reg = lam * np.eye(X.shape[1])
    reg[0, 0] = 0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(X @ w, -30, 30)))
        g = X.T @ (y - p) - reg @ w
        H = (X * (p * (1 - p))[:, None]).T @ X + reg
        step = np.linalg.solve(H, g)
        w += step
        if np.abs(step).max() < 1e-8:
            break
    return w


def score(method: str, ds: Dataset, tr: np.ndarray, alpha: float = 0.01, k: int = 5) -> tuple[np.ndarray, float | None]:
    """全行の異常度（大きいほど怪しい）と、理論から決まる閾値（なければ None）を返す。
    学習（平均・分散・係数など）は tr の行だけで行う。"""
    df = ds.df
    X = df[ds.cols].to_numpy(float)
    Xt = X[tr]
    M = X.shape[1]
    if method == "変数ごとの管理図":
        a = _z2(X, Xt.mean(0), Xt.std(0, ddof=1)).max(1)
        return a, chi2_ppf(1 - alpha / M, 1)
    if method == "ロバストz（中央値・MAD）":
        med = np.median(Xt, 0)
        mad = 1.4826 * np.median(np.abs(Xt - med), 0)
        return _z2(X, med, mad).max(1), chi2_ppf(1 - alpha / M, 1)
    if method == "ポアソン（時間帯別）":
        x = X[:, 0].astype(int)
        if ds.group_col:
            g = df[ds.group_col].to_numpy()
            lam_g = pd.Series(x[tr]).groupby(g[tr]).mean()
            lam = pd.Series(g).map(lam_g).fillna(x[tr].mean()).to_numpy(float)
        else:
            lam = np.full(len(x), x[tr].mean())
        lam = np.maximum(lam, 0.05)  # 学習期間に一度も起きなかった時間帯でも 0 にしない
        return -np.log10(poisson_sf(x, lam)), -math.log10(alpha)
    if method in ("ホテリングT²", "MT法"):
        mu = Xt.mean(0)
        S = np.cov(Xt, rowvar=False).reshape(M, M)
        Sinv = np.linalg.pinv(S)
        d = X - mu
        t2 = np.einsum("ij,jk,ik->i", d, Sinv, d)
        thr = chi2_ppf(1 - alpha, M)
        return (t2 / M, thr / M) if method == "MT法" else (t2, thr)
    if method == "k近傍距離":
        mu, sd = Xt.mean(0), Xt.std(0, ddof=1)
        sd = np.where(sd > 0, sd, 1)
        Z, Zt = (X - mu) / sd, (Xt - mu) / sd
        D = np.sqrt(((Z[:, None, :] - Zt[None, :, :]) ** 2).sum(-1))
        D[tr, np.arange(len(tr))] = np.inf  # 学習データ自身との距離0は数えない
        return np.sort(D, 1)[:, k - 1], None
    if method == "回帰の残差":
        A = np.c_[np.ones(len(df)), df[ds.inputs].to_numpy(float)]
        y = df[ds.output].to_numpy(float)
        beta, *_ = np.linalg.lstsq(A[tr], y[tr], rcond=None)
        r = y - A @ beta
        return (r / r[tr].std(ddof=A.shape[1])) ** 2, chi2_ppf(1 - alpha, 1)
    if method == "時系列の残差":
        y = X[:, 0]
        P = ds.period or 24
        base = np.full(len(y), np.nan)
        for i in range(3 * P, len(y)):
            base[i] = np.median(y[[i - P, i - 2 * P, i - 3 * P]])
        d = y - base
        ok = np.where(np.isfinite(d) & np.r_[False, np.isfinite(d[:-1])])[0]
        fit = ok[np.isin(ok, tr)]
        phi = float(np.dot(d[fit - 1], d[fit]) / max(np.dot(d[fit - 1], d[fit - 1]), 1e-9))
        e = np.full(len(y), np.nan)
        e[ok] = d[ok] - phi * d[ok - 1]
        sd = np.nanstd(e[fit], ddof=1)
        a = np.nan_to_num((e / sd) ** 2, nan=0.0)  # 最初の3日分は「判定できない」＝0
        return a, chi2_ppf(1 - alpha, 1)
    if method == "固着ルール（同じ値が続く）":
        y = X[:, 0]
        same = np.r_[False, np.abs(np.diff(y)) < 1e-9]
        run = np.zeros(len(y))
        for i in range(1, len(y)):
            run[i] = run[i - 1] + 1 if same[i] else 0
        return run, 1.0  # 2時間以上同じ値（連続の長さ2以上）で鳴らす
    if method == "教師あり（ロジスティック回帰）":
        mu, sd = Xt.mean(0), Xt.std(0, ddof=1)
        Z = np.c_[np.ones(len(X)), (X - mu) / np.where(sd > 0, sd, 1)]
        y = df[TYPE].isin(ds.known_types).to_numpy(int)  # 記録が残っている種類だけが「異常」として教えられる
        w = logistic_fit(Z[tr], y[tr])
        return 1 / (1 + np.exp(-np.clip(Z @ w, -30, 30))), 0.5
    raise ValueError(method)


def threshold(strategy: str, s_val: np.ndarray, y_val: np.ndarray, alpha: float, theory: float | None,
              c_fn: float = 10.0, c_fp: float = 1.0) -> float:
    """閾値の決め方（どれもテストデータは見ない）。異常度が閾値を「超えたら」アラート。
    理論：分布の仮定から。分位点：検証データの正常の (1−α) 分位点。コスト最小：検証データで 見逃し×c_fn＋誤報×c_fp が最小。"""
    if strategy == "理論" and theory is not None:
        return float(theory)
    if strategy == "コスト最小" and y_val.sum() > 0:
        cand = np.r_[np.unique(s_val)[0] - 1e-9, np.unique(s_val)]
        cost = [(c_fn * ((s_val <= t) & (y_val == 1)).sum() + c_fp * ((s_val > t) & (y_val == 0)).sum(), t)
                for t in cand]
        return float(min(cost)[1])
    normal = s_val[y_val == 0] if (y_val == 0).any() else s_val
    return float(np.quantile(normal, 1 - alpha))


def evaluate(y: np.ndarray, s: np.ndarray, thr: float, flag: np.ndarray | None = None) -> dict:
    """flag を渡すと、その判定（複数手法の組み合わせなど）で数える。AUC・AP は異常度 s で計算する。"""
    flag = s > thr if flag is None else np.asarray(flag, bool)
    tp = int((flag & (y == 1)).sum())
    fp = int((flag & (y == 0)).sum())
    fn = int((~flag & (y == 1)).sum())
    tn = int((~flag & (y == 0)).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {"TP": tp, "FP": fp, "FN": fn, "TN": tn, "適合率": prec, "再現率": rec,
            "F1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
            "誤報率": fp / (fp + tn) if fp + tn else 0.0,
            "ROC-AUC": roc_auc(y, s), "平均適合率(AP)": average_precision(y, s)}


def roc_auc(y: np.ndarray, s: np.ndarray) -> float:
    """「異常をランダムに1つ、正常をランダムに1つ選んだとき、異常のほうが異常度が高い確率」。"""
    y = np.asarray(y)
    n1, n0 = int((y == 1).sum()), int((y == 0).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = pd.Series(s).rank().to_numpy()
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def average_precision(y: np.ndarray, s: np.ndarray) -> float:
    y = np.asarray(y)
    if y.sum() == 0:
        return float("nan")
    o = np.argsort(-np.asarray(s), kind="stable")
    hit = y[o] == 1
    prec = np.cumsum(hit) / np.arange(1, len(y) + 1)
    return float(prec[hit].mean())


def curves(y: np.ndarray, s: np.ndarray) -> pd.DataFrame:
    """閾値を動かしたときの 再現率・誤報率・適合率（ROC曲線とPR曲線の元）。"""
    th = np.r_[np.inf, np.unique(s)[::-1]]
    rows = []
    for t in th:
        f = s >= t
        tp, fp = (f & (y == 1)).sum(), (f & (y == 0)).sum()
        rows.append((t, tp / max(y.sum(), 1), fp / max((y == 0).sum(), 1), tp / (tp + fp) if tp + fp else 1.0))
    return pd.DataFrame(rows, columns=["閾値", "再現率", "誤報率", "適合率"])


def by_type(types: pd.Series, flag: np.ndarray) -> pd.DataFrame:
    """異常の種類ごとに、何件中何件を見つけたか（どの種類に弱いかが分かる）。"""
    t = pd.DataFrame({"種類": types.to_numpy(), "検知": flag})
    g = t.groupby("種類")["検知"].agg(["size", "sum"]).rename(columns={"size": "件数", "sum": "検知"})
    g["割合"] = g["検知"] / g["件数"]
    return g.reset_index()


def alarm_truth(prevalence: float, recall: float, fpr: float) -> float:
    """ベイズの定理：アラートが鳴ったとき、それが本物の異常である確率（＝適合率の理論値）。"""
    num = recall * prevalence
    den = num + fpr * (1 - prevalence)
    return num / den if den else 0.0


# ─────────────────────────────────────────────
# 導入：ポアンカレとパン屋（点ではなく「分布」の異常）
# ─────────────────────────────────────────────
def poincare(n: int = 365, seed: int = 0) -> pd.DataFrame:
    """1年目：1000gのはずが平均950g。2年目：軽いものを渡さなくなる → 分布の左側が欠けて右に歪む（架空の再現）。"""
    rng = np.random.default_rng(seed)
    y1 = rng.normal(950, 25, n)
    pool = rng.normal(950, 25, n * 4)
    y2 = pool[pool >= 950][:n]  # 950g未満のものは渡さない（重いものだけ選ぶ）→ 左側の裾が切れる
    return pd.DataFrame({"年": ["1年目"] * n + ["2年目"] * n, "重さ_g": np.r_[y1, y2].round(1)})


# ─────────────────────────────────────────────
# 実践知チェックリスト（落とし穴）
# ─────────────────────────────────────────────
PITFALLS = [
    # (落とし穴, どう起きるか, 対策, このページで確かめる場所)
    ("テストデータで閾値を決める", "評価が甘くなり、本番で誤報・見逃しが増える",
     "学習／検証／テストに分け、閾値は検証データで決める", "❸ 閾値の決め方"),
    ("標準化や平均をテストデータ込みで計算する", "未来の情報が学習に漏れる（データリーク）",
     "平均・標準偏差は学習データだけで計算し、他に当てはめる", "❸ の学習データ"),
    ("学習データに異常が混ざったまま", "「いつも」の幅が広がり、異常が普通に見える",
     "記録のある異常を除く・ロバストな統計量を使う", "❸「学習データを掃除する」"),
    ("正解率（Accuracy）で評価する", "異常が1%なら「全部正常」と言うだけで99%",
     "再現率・適合率・PR曲線で見る", "❸ の評価指標"),
    ("異常の少なさを忘れる（基準率の無視）", "誤報率1%でも、異常が0.1%ならアラートの9割は空振り",
     "ベイズの定理でアラートの信頼度を見積もる", "❸ ベイズ"),
    ("過去の異常だけで学ぶ（教師ありに頼る）", "記録のない新しい種類の異常を見逃す",
     "教師なしを主に、教師ありは補助に", "❷・❸ 製パン工程"),
    ("時間の順番を無視してくじで分ける", "未来のデータで過去を学ぶことになる",
     "時系列は時間順に分ける", "❸ 時系列データ"),
    ("1変数ずつしか見ない", "組み合わせの崩れ（相関の崩れ）を見逃す",
     "多変数の距離（ホテリングT²・MT法）で見る", "❸ 製パン工程"),
    ("アラートを結論として扱う", "誤報のたびに現場が止まり、やがて誰も見なくなる",
     "アラートは「人が調べに行く合図」（Human-in-the-Loop）", "マイ判断シート"),
]

# 持ち込みノートブック（Anomaly_detection_01.ipynb）の点検結果
NOTEBOOK_REVIEW = [
    ("StandardScaler で標準化した値を、出力が0〜1のオートエンコーダ（sigmoid＋binary_crossentropy）に入れている",
     "標準化した値は負や1超えになるので、復元誤差が意味を持たない", "画素値を 0〜1 に割り算（÷255）するだけにする"),
    ("閾値を「異常画像の誤差の平均＋1.5σ」で決めている", "異常データで閾値を決めると、本番では異常が来る前に閾値がない",
     "正常画像を学習／検証に分け、検証の正常画像の誤差の99%点を閾値にする"),
    ("評価がない（画像を並べて見るだけ）", "どのくらい見つけ、どのくらい空振りするかが分からない",
     "テスト用の正常＋異常で ROC-AUC・再現率・適合率を出す"),
    ("One-Class SVM に 64×64=4096次元をそのまま入れ、gamma='auto'", "次元が多すぎて距離が効かず、gamma も合わない",
     "主成分分析で数十次元に落としてから、gamma='scale' で学習"),
    ("正常画像全部で学習し、同じ画像で異常度を見ている", "学習に使った画像は当然よく当てはまる（過学習が見えない）",
     "学習に使っていない正常画像で異常度を確かめる"),
]


# ─────────────────────────────────────────────
# 自己チェック
# ─────────────────────────────────────────────
def _pipeline(ds: Dataset, method: str, clean: bool = True, strategy: str = "分位点", alpha: float = 0.01):
    sp = split(ds, seed=1)
    tr = train_rows(ds, sp, clean, method)
    s, th = score(method, ds, tr, alpha)
    y = ds.df[LABEL].to_numpy()
    thr = threshold(strategy, s[sp["検証"]], y[sp["検証"]], alpha, th)
    return evaluate(y[sp["テスト"]], s[sp["テスト"]], thr), s, sp, thr


if __name__ == "__main__":
    # 道具
    assert abs(chi2_ppf(0.99, 1) - 6.635) < 0.01 and abs(chi2_ppf(0.99, 2) - 9.210) < 0.01
    assert abs(chi2_ppf(0.99, 5) - 15.086) < 0.15 and abs(chi2_ppf(0.95, 10) - 18.307) < 0.15
    assert abs(poisson_sf(np.array([3]), np.array([2.0]))[0] - 0.3233) < 1e-3
    assert poisson_sf(np.array([0]), np.array([1.0]))[0] == 1.0
    assert abs(roc_auc(np.array([0, 0, 1, 1]), np.array([0.1, 0.2, 0.3, 0.4])) - 1) < 1e-9
    assert abs(roc_auc(np.array([0, 1, 0, 1]), np.array([1, 1, 1, 1])) - 0.5) < 1e-9
    assert abs(average_precision(np.array([1, 0, 1]), np.array([3, 2, 1])) - (1 + 2 / 3) / 2) < 1e-9
    assert abs(alarm_truth(0.001, 1.0, 0.01) - 0.0909) < 1e-3   # 誤報率1%・異常0.1%なら9割は空振り

    for key in SAMPLES:
        ds = sample(key)
        dg = diagnose(ds)
        rec = recommend(dg, ds)
        assert rec and all(m in available(ds) for m, _ in rec), (key, rec)
        assert findings(dg)
        sp = split(ds)
        assert sum(len(v) for v in sp.values()) == len(ds.df)
        assert len(set(np.concatenate(list(sp.values())))) == len(ds.df)
        if ds.time_col:  # 時系列は時間順に分ける
            assert sp["学習"].max() < sp["検証"].min() < sp["テスト"].min()
        assert ds.df[LABEL].iloc[sp["テスト"]].sum() > 0, key  # テストに異常が入っている

    # ❷ の選び方
    pick = {k: recommend(diagnose(sample(k)), sample(k))[0][0] for k in SAMPLES}
    assert pick == {"bread": "ロバストz（中央値・MAD）", "login": "ポアソン（時間帯別）", "dough": "ホテリングT²",
                    "house_io": "回帰の残差", "house_ts": "時系列の残差"}, pick

    res = {}
    for key, m in pick.items():
        r, *_ = _pipeline(sample(key), m)
        res[key] = r
        assert r["ROC-AUC"] > 0.85, (key, m, r)

    # 実践知1：組み合わせの崩れは、1変数ずつでは見逃す（製パン工程・温度計のずれ）
    ds = sample("dough")
    r_t2, s_t2, sp, thr_t2 = _pipeline(ds, "ホテリングT²")
    r_uv, s_uv, _, thr_uv = _pipeline(ds, "変数ごとの管理図")
    te = sp["テスト"]
    bt_t2 = by_type(ds.df[TYPE].iloc[te], s_t2[te] > thr_t2).set_index("種類")
    bt_uv = by_type(ds.df[TYPE].iloc[te], s_uv[te] > thr_uv).set_index("種類")
    assert bt_t2.loc["温度計のずれ", "割合"] > bt_uv.loc["温度計のずれ", "割合"] + 0.3, (bt_t2, bt_uv)
    # MT法は T² ÷ 変数の数：順位は同じなので AUC も同じ
    r_mt, *_ = _pipeline(ds, "MT法")
    assert abs(r_mt["ROC-AUC"] - r_t2["ROC-AUC"]) < 1e-9

    # 実践知2：教師ありは記録のない種類（温度計のずれ）を見逃す
    r_sv, s_sv, _, thr_sv = _pipeline(ds, "教師あり（ロジスティック回帰）", strategy="理論")
    bt_sv = by_type(ds.df[TYPE].iloc[te], s_sv[te] > thr_sv).set_index("種類")
    assert bt_sv.loc["過発酵", "割合"] > 0.8 and bt_sv.loc["温度計のずれ", "割合"] < 0.3, bt_sv

    # 実践知3：入出力を無視すると、晴れて暑いだけの時間を異常と呼ぶ
    ds = sample("house_io")
    r_rg, *_ = _pipeline(ds, "回帰の残差")
    r_u1, *_ = _pipeline(ds, "変数ごとの管理図")
    assert r_rg["ROC-AUC"] > r_u1["ROC-AUC"] + 0.15, (r_rg, r_u1)

    # 実践知4：時間帯を分けないと、深夜の少数試行を見逃す
    ds = sample("login")
    _, s_p, sp, thr_p = _pipeline(ds, "ポアソン（時間帯別）")
    ds_flat = Dataset(**{**ds.__dict__, "group_col": None})
    _, s_f, _, thr_f = _pipeline(ds_flat, "ポアソン（時間帯別）")
    te = sp["テスト"]
    night = (ds.df[TYPE].iloc[te] == "深夜の少数試行").to_numpy()
    assert (s_p[te][night] > thr_p).mean() > (s_f[te][night] > thr_f).mean()

    # 実践知5：時系列を無視すると、深夜の過昇温（値そのものは昼なら普通）を見逃す
    ds = sample("house_ts")
    r_ts, s_ts, sp, thr_ts = _pipeline(ds, "時系列の残差")
    r_raw, *_ = _pipeline(ds, "変数ごとの管理図")
    assert r_ts["再現率"] > r_raw["再現率"] + 0.3, (r_ts, r_raw)
    # 実践知5b：固着は残差では見えにくい → 作った特徴量（同じ値が続く時間）と OR で組み合わせる
    _, s_st, _, thr_st = _pipeline(ds, "固着ルール（同じ値が続く）")
    te = sp["テスト"]
    y_te, typ_te = ds.df[LABEL].to_numpy()[te], ds.df[TYPE].iloc[te]
    f_ts, f_st = s_ts[te] > thr_ts, s_st[te] > thr_st
    st_ts = by_type(typ_te, f_ts).set_index("種類").loc["センサー固着", "割合"]
    st_or = by_type(typ_te, f_ts | f_st).set_index("種類").loc["センサー固着", "割合"]
    assert st_or >= 0.9 > st_ts, (st_ts, st_or)
    assert evaluate(y_te, s_ts[te], 0, f_ts | f_st)["適合率"] > 0.6

    # 実践知6：学習データの異常を掃除しないと、いつもの幅が広がって見逃しが増える（全行で数える）
    ds = sample("bread")
    sp = split(ds, seed=1)
    y = ds.df[LABEL].to_numpy()
    rc = {}
    for name, m, clean in [("掃除", "変数ごとの管理図", True), ("そのまま", "変数ごとの管理図", False),
                           ("ロバスト", "ロバストz（中央値・MAD）", False)]:
        s_, th_ = score(m, ds, train_rows(ds, sp, clean, m))
        rc[name] = evaluate(y, s_, th_)["再現率"]
    assert rc["そのまま"] < rc["掃除"] and rc["ロバスト"] > rc["そのまま"], rc

    # ポアンカレ：2年目は右に歪む
    pc = poincare()
    s1 = _skew_kurt(pc.loc[pc["年"] == "1年目", "重さ_g"].to_numpy())[0]
    s2 = _skew_kurt(pc.loc[pc["年"] == "2年目", "重さ_g"].to_numpy())[0]
    assert abs(s1) < 0.3 and s2 > 0.6, (s1, s2)

    # アップロード
    up = from_upload(sample("dough").df.drop(columns=[TYPE]), DOUGH_COLS[:3], label_col=LABEL)
    assert up.kind == "多変数" and up.df[LABEL].sum() > 0

    print("ok", {k: f"{v['ROC-AUC']:.2f}/{v['F1']:.2f}" for k, v in res.items()})

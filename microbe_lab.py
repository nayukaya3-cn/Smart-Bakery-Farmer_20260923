"""
microbe_lab.py — 「微生物（酵母・乳酸菌等）からの挑戦」の計算部品

画面は pages/17_🦠_微生物からの挑戦.py。`python microbe_lab.py` で自己チェック（手計算と照らし合わせ）。

4つの題材と、下敷きにした本
  🍞 酵母（パン種）の増殖       … 田村学造 編『酵母からのチャレンジ ─応用酵母学─』（野生酵母・製パン）
  🥛 乳酸菌と酵母の共棲         … 同上「酵母と共棲する乳酸菌」、ぬか床・サワー種・ぼかしの「よい香り」
  🌾 米ぬか発酵肥料（土壌微生物） … 南澤究・妹尾啓史 編『エッセンシャル土壌微生物学』（有機物の無機化・C/N）
  🔬 微生物検査（食品・化粧品）   … 三瀬勝利・井上富士男 編『食品中の微生物検査法解説書』、
                                    浅賀良雄『Q&A181 化粧品の微生物試験ガイドブック』（保存効力試験）

方針
  - numpy だけで書く。式が追えることを優先する。
  - 初期表示のデータはすべて架空（教材用）。材料の C/N・水分などの値は文献により幅がある「目安」。
  - 判定の基準（保存効力試験・堆肥温度）は、画面で人が変えられる初期値。正式な判定は原典・公定法・社内基準で行う。
"""
from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import pandas as pd

# ============================================================
# 🍞 酵母の増殖：ロジスティック曲線・倍加時間・温度
# ============================================================
def logistic(t, n0: float, k: float, r: float):
    """N(t) = K / (1 + (K/N0 − 1)·e^(−rt))。最初は倍々（指数）、資源が尽きると K で頭打ち。"""
    t = np.asarray(t, float)
    return k / (1 + (k / n0 - 1) * np.exp(-r * t))


def fit_logistic(t: Sequence[float], y: Sequence[float]) -> dict:
    """K を格子で動かし、ln(K/y − 1) = ln(K/N0 − 1) − r·t を直線で当てはめる。元の尺度の誤差が最小の K を選ぶ。"""
    t, y = np.asarray(t, float), np.asarray(y, float)
    if len(t) < 3 or np.any(y <= 0):
        raise ValueError("時間と値（正の数）が3組以上必要です")
    best = None
    for k in np.linspace(y.max() * 1.005, y.max() * 2.0, 400):
        z = np.log(k / y - 1)
        slope, icpt = np.polyfit(t, z, 1)
        r = -slope
        if r <= 0:
            continue
        n0 = k / (1 + math.exp(icpt))
        sse = float(((logistic(t, n0, k, r) - y) ** 2).sum())
        if best is None or sse < best["SSE"]:
            best = {"N0": n0, "K": float(k), "r": float(r), "SSE": sse}
    if best is None:
        raise ValueError("増えていくデータではないため当てはめられません")
    # 直線化の答えを出発点に、元の尺度の誤差でガウス・ニュートン法（log をとった3つのパラメータ）で詰める
    p = np.log([best["N0"], best["K"], best["r"]])

    def resid(q):
        return logistic(t, *np.exp(q)) - y
    for _ in range(60):
        res = resid(p)
        J = np.column_stack([(resid(p + h) - res) / 1e-6 for h in np.eye(3) * 1e-6])
        step = np.linalg.lstsq(J, -res, rcond=None)[0]
        lam = 1.0
        while lam > 1e-4 and (resid(p + lam * step) ** 2).sum() > (res ** 2).sum():
            lam /= 2
        p = p + lam * step
        if np.abs(lam * step).max() < 1e-9:
            break
    n0, k, r = map(float, np.exp(p))
    sse = float((resid(p) ** 2).sum())
    if sse < best["SSE"] and k >= y.max() * 0.9:
        best = {"N0": n0, "K": k, "r": r, "SSE": sse}
    best["倍加時間"] = math.log(2) / best["r"]
    best["R²"] = 1 - best["SSE"] / max(1e-12, float(((y - y.mean()) ** 2).sum()))
    return best


def cardinal_rate(temp, t_min: float = 2.0, t_opt: float = 30.0, t_max: float = 40.0, mu_opt: float = 1.0):
    """温度と増える速さ（Rosso の CTMI）。t_min 以下・t_max 以上は 0、t_opt で最大 mu_opt。"""
    T = np.asarray(temp, float)
    num = (T - t_max) * (T - t_min) ** 2
    den = (t_opt - t_min) * ((t_opt - t_min) * (T - t_opt) - (t_opt - t_max) * (t_opt + t_min - 2 * T))
    with np.errstate(divide="ignore", invalid="ignore"):
        mu = mu_opt * num / den
    return np.where((T <= t_min) | (T >= t_max), 0.0, np.clip(mu, 0, None))


def doubling_trace(n0: float, target: float, dt_h: float) -> pd.DataFrame:
    """「倍になる」を target を超えるまでくり返す（DNCLのトレース表）"""
    if n0 <= 0 or target <= n0:
        raise ValueError("はじめの数は正で、目標より小さくしてください")
    rows, n, i = [], n0, 0
    while n < target:
        n, i = n * 2, i + 1
        rows.append({"回": i, "経過時間(h)": round(i * dt_h, 2), "N": n, "N ≥ 目標か": n >= target})
        if i > 200:
            break
    return pd.DataFrame(rows)


def sample_dough(seed: int = 7) -> pd.DataFrame:
    """架空：自家製レーズン酵母で仕込んだ生地の体積倍率（3つの温度・2時間おき）"""
    rng = np.random.default_rng(seed)
    rows = []
    for temp in (20, 25, 30):
        r = 0.55 * float(cardinal_rate(temp)) + 0.02
        for h in range(0, 17, 2):
            v = float(logistic(h, 1.0, 2.6, r)) * (1 + rng.normal(0, 0.015))
            rows.append({"時間_h": h, "温度_C": temp, "体積倍率": round(max(v, 0.95), 2)})
    return pd.DataFrame(rows)


# ============================================================
# 🥛 乳酸菌と酵母の共棲：pH が下がると雑菌が増えない（オイラー法のシミュレーション）
# ============================================================
def coculture(hours: float = 72, dt: float = 0.5, y0=(1.0, 1.0, 1.0), r=(0.25, 0.35, 0.45),
              k=(100.0, 100.0, 100.0), acid_per_lab: float = 0.004, ph0: float = 6.5, ph_floor: float = 3.6,
              ph_stop_c: float = 4.6, ph_stop_lab: float = 3.6, ph_stop_y: float = 2.5, share: float = 1.0) -> pd.DataFrame:
    """酵母Y・乳酸菌L・雑菌C が同じ栄養（K）を分け合い、乳酸菌がつくる酸で pH が下がる。
    pH が各菌の「止まる pH」に近づくほど増える速さが落ちる。share=1 なら全員で同じ栄養を分け合う。
    1歩ごとに N ← N + dt × (増える速さ)（オイラー法）"""
    Y, L, C = map(float, y0)
    acid, rows = 0.0, []
    steps = int(round(hours / dt))
    for i in range(steps + 1):
        ph = max(ph_floor, ph0 - math.log10(1 + acid * 100))
        rows.append({"時間_h": round(i * dt, 2), "酵母": Y, "乳酸菌": L, "雑菌": C, "pH": ph})
        total = share * (Y + L + C)

        def f(ph_stop):  # pH による抑え（ph0 で 1、ph_stop で 0）
            return max(0.0, min(1.0, (ph - ph_stop) / (ph0 - ph_stop)))
        dY = r[0] * Y * (1 - (total if share else Y) / k[0]) * f(ph_stop_y)
        dL = r[1] * L * (1 - (total if share else L) / k[1]) * f(ph_stop_lab)
        dC = r[2] * C * (1 - (total if share else C) / k[2]) * f(ph_stop_c)
        Y, L, C = max(0.0, Y + dt * dY), max(0.0, L + dt * dL), max(0.0, C + dt * dC)
        acid += dt * acid_per_lab * L
    return pd.DataFrame(rows)


def euler_trace(n0: float, r: float, k: float, dt: float, steps: int) -> pd.DataFrame:
    """ロジスティックをオイラー法で1歩ずつ進める（DNCLのトレース表）。解析解と並べて誤差を見る。"""
    rows, n = [], n0
    for i in range(steps + 1):
        rows.append({"i": i, "t": round(i * dt, 3), "N（オイラー法）": round(n, 4),
                     "N（式）": round(float(logistic(i * dt, n0, k, r)), 4)})
        n = n + dt * r * n * (1 - n / k)
    out = pd.DataFrame(rows)
    out["誤差"] = (out["N（オイラー法）"] - out["N（式）"]).round(4)
    return out


# ============================================================
# 🌾 米ぬか発酵肥料（土壌微生物）：C/N と水分、堆肥温度の見張り
# ============================================================
# 目安（乾物あたり。文献・産地・季節で幅がある。手元の分析値があれば置きかえる）
MATERIALS = pd.DataFrame([
    {"材料": "米ぬか", "C/N": 20, "N_乾物%": 2.2, "水分%": 12},
    {"材料": "天日干しの雑草", "C/N": 25, "N_乾物%": 1.6, "水分%": 15},
    {"材料": "柿の小枝（剪定枝）", "C/N": 150, "N_乾物%": 0.35, "水分%": 35},
    {"材料": "落ち葉", "C/N": 45, "N_乾物%": 1.0, "水分%": 30},
    {"材料": "もみ殻", "C/N": 75, "N_乾物%": 0.5, "水分%": 10},
    {"材料": "生ごみ（野菜くず）", "C/N": 15, "N_乾物%": 2.5, "水分%": 80},
    {"材料": "鶏ふん（乾燥）", "C/N": 8, "N_乾物%": 3.5, "水分%": 20},
    {"材料": "水", "C/N": 0, "N_乾物%": 0.0, "水分%": 100},
])


def mix(materials: pd.DataFrame, kg: dict[str, float]) -> dict:
    """配合のC/Nと水分。C = N% × C/N（乾物あたり）として、乾物の C と N を足し合わせて割る。"""
    m = materials.set_index("材料")
    wet = dry = c = n = water = 0.0
    rows = []
    for name, w in kg.items():
        if w <= 0 or name not in m.index:
            continue
        mo = float(m.loc[name, "水分%"]) / 100
        d = w * (1 - mo)
        nn = d * float(m.loc[name, "N_乾物%"]) / 100
        cc = nn * float(m.loc[name, "C/N"])
        wet, dry, water, n, c = wet + w, dry + d, water + w * mo, n + nn, c + cc
        rows.append({"材料": name, "重さ_kg": w, "乾物_kg": round(d, 3), "N_kg": round(nn, 4), "C_kg": round(cc, 3)})
    return {"表": pd.DataFrame(rows), "重さ_kg": wet, "C/N": c / n if n else float("nan"),
            "水分%": 100 * water / wet if wet else float("nan"), "N_kg": n, "C_kg": c}


def water_to_add(materials: pd.DataFrame, kg: dict[str, float], target_moisture: float) -> float:
    """目標の水分%にするために足す水（kg）。水 x を足すと (水分 + x)/(全体 + x) = 目標"""
    base = {k: v for k, v in kg.items() if k != "水"}
    r = mix(materials, base)
    w0 = r["重さ_kg"] * r["水分%"] / 100
    t = target_moisture / 100
    return max(0.0, (t * r["重さ_kg"] - w0) / (1 - t)) if t < 1 else float("inf")


def compost_flags(df: pd.DataFrame, hot: float = 65.0, active: float = 10.0, window: int = 3) -> pd.DataFrame:
    """堆肥の温度の見張り。気温との差（発酵の熱）で段階を分ける（境目は人が決める初期値）。
    - hot 以上：熱すぎ（アンモニア臭・有用菌も弱る）→ 切り返し・水分を確かめる
    - 気温差 active 以上：発酵中
    - 切り返したのに温度が上がらない・気温差が小さいまま続く：熟成に近い（または水分・空気不足）"""
    d = df.copy().reset_index(drop=True)
    d["気温との差"] = d["堆肥温度_C"] - d["気温_C"]
    d["移動平均"] = d["堆肥温度_C"].rolling(window, min_periods=1).mean().round(1)
    status = []
    for i, row in d.iterrows():
        if row["堆肥温度_C"] >= hot:
            s = "🔥 熱すぎ"
        elif row["気温との差"] >= active:
            s = "🟠 発酵中"
        else:
            after = d.loc[:i][d.loc[:i, "切り返し"] == 1]
            if len(after) and (i - after.index[-1]) >= 2 and d.loc[after.index[-1]:i, "気温との差"].max() < active:
                s = "🟢 熟成に近い"
            else:
                s = "⚪ 静か（水分・空気を確かめる）"
        status.append(s)
    d["判定"] = status
    return d


def sample_compost(seed: int = 3) -> pd.DataFrame:
    """架空：2026-09-23 に仕込んだ米ぬか発酵肥料の、毎朝の温度。切り返しの翌日に再び上がり、回を重ねると上がらなくなる。"""
    rng = np.random.default_rng(seed)
    days = pd.date_range("2026-09-23", periods=36, freq="D")
    turns = {6, 13, 20, 27}
    rows, heat = [], 0.0
    for i, day in enumerate(days):
        air = 24 - 10 * i / 35 + rng.normal(0, 1.2)
        if i == 0:
            heat = 2.0
        elif i - 1 in turns:
            heat = max(heat, 38 * (0.55 ** (sorted(turns).index(i - 1) + 1)) + 3)
        else:
            heat = heat * 0.90 if i > 3 else heat + 15
        rows.append({"日付": day.strftime("%Y-%m-%d"), "気温_C": round(air, 1),
                     "堆肥温度_C": round(air + heat + rng.normal(0, 1.0), 1), "切り返し": int(i in turns)})
    return pd.DataFrame(rows)


# ============================================================
# 🔬 微生物検査：段階希釈の平板法（CFU）、ベイズ、保存効力試験
# ============================================================
def cfu_simple(plates: pd.DataFrame, lo: int = 30, hi: int = 300) -> dict:
    """30〜300個の平板だけを使い、各平板の CFU/g（集落数 × 希釈倍率 ÷ 塗抹量）を平均する（素朴な方法）"""
    ok = plates[(plates["集落数"] >= lo) & (plates["集落数"] <= hi)]
    if ok.empty:
        return {"CFU/g": float("nan"), "使った平板": 0}
    vals = ok["集落数"] * ok["希釈倍率"] / ok["塗抹量_mL"]
    return {"CFU/g": float(vals.mean()), "使った平板": int(len(ok))}


def cfu_weighted(plates: pd.DataFrame, lo: int = 30, hi: int = 300) -> dict:
    """連続した2段の希釈を重みつきで合わせる式 N = ΣC / (V × (n1 + 0.1·n2) × d)
    （d は残した平板のうち薄くない方の希釈。ISO 7218 の考え方。塗抹量 V は全平板で同じとする）"""
    ok = plates[(plates["集落数"] >= lo) & (plates["集落数"] <= hi)].copy()
    if ok.empty:
        return {"CFU/g": float("nan"), "n1": 0, "n2": 0}
    levels = sorted(ok["希釈倍率"].unique())[:2]
    ok = ok[ok["希釈倍率"].isin(levels)]
    v = float(ok["塗抹量_mL"].iloc[0])
    n1 = int((ok["希釈倍率"] == levels[0]).sum())
    n2 = int((ok["希釈倍率"] == levels[1]).sum()) if len(levels) > 1 else 0
    d = 1 / levels[0]
    return {"CFU/g": float(ok["集落数"].sum() / (v * (n1 + 0.1 * n2) * d)), "n1": n1, "n2": n2}


def cfu_bayes(plates: pd.DataFrame, a0: float = 0.5, b0: float = 0.0, upper: int = 300, seed: int = 0) -> dict:
    """ベイズ：各平板の集落数 C_i ~ Poisson(N × V_i / 希釈倍率_i)。事前 N ~ Gamma(a0, b0) なら事後も Gamma。
    数えきれない平板（upper 超え）は使わない。30未満の平板も「情報」として使える（捨てなくてよい）。"""
    ok = plates[plates["集落数"] <= upper]
    expo = (ok["塗抹量_mL"] / ok["希釈倍率"]).sum()
    a, b = a0 + ok["集落数"].sum(), b0 + expo
    if b <= 0:
        return {"中央値": float("nan"), "下限": float("nan"), "上限": float("nan"), "使った平板": 0}
    s = np.random.default_rng(seed).gamma(a, 1 / b, 40000)
    return {"事後平均": float(a / b), "中央値": float(np.median(s)), "下限": float(np.quantile(s, 0.025)),
            "上限": float(np.quantile(s, 0.975)), "使った平板": int(len(ok)), "samples": s}


def cfu_trace(plates: pd.DataFrame, lo: int = 30, hi: int = 300) -> pd.DataFrame:
    """30〜300の平板だけを足していく for文（DNCLのトレース表）"""
    total, cnt, rows = 0.0, 0, []
    for i, r in enumerate(plates.itertuples(index=False)):
        c = r.集落数
        use = lo <= c <= hi
        if use:
            total += c * r.希釈倍率 / r.塗抹量_mL
            cnt += 1
        rows.append({"i": i, "希釈倍率": r.希釈倍率, "集落数": c, f"{lo}≦C≦{hi}": use,
                     "合計(CFU/g)": total, "使った枚数": cnt})
    return pd.DataFrame(rows)


SAMPLE_PLATES = pd.DataFrame([
    {"希釈倍率": 10, "平板": "A", "塗抹量_mL": 1.0, "集落数": 999},   # 数えきれない（TNTC）
    {"希釈倍率": 10, "平板": "B", "塗抹量_mL": 1.0, "集落数": 999},
    {"希釈倍率": 100, "平板": "A", "塗抹量_mL": 1.0, "集落数": 232},
    {"希釈倍率": 100, "平板": "B", "塗抹量_mL": 1.0, "集落数": 244},
    {"希釈倍率": 1000, "平板": "A", "塗抹量_mL": 1.0, "集落数": 33},
    {"希釈倍率": 1000, "平板": "B", "塗抹量_mL": 1.0, "集落数": 28},
    {"希釈倍率": 10000, "平板": "A", "塗抹量_mL": 1.0, "集落数": 2},
    {"希釈倍率": 10000, "平板": "B", "塗抹量_mL": 1.0, "集落数": 4},
])

# 保存効力試験（チャレンジテスト）の判定：日数ごとに必要な log 減少の初期値（ISO 11930 判定基準Aの考え方）
# 正式な判定は原典・社内基準で確かめる。「増えない(NI)」は前の時点より log が増えていないこと。
CRITERIA_A = {"細菌": {7: 3.0, 14: 3.0, 28: 3.0}, "酵母": {7: 1.0, 14: 1.0, 28: 1.0}, "カビ": {7: 0.0, 14: 1.0, 28: 1.0}}

SAMPLE_CHALLENGE = pd.DataFrame([
    # 架空の化粧水（防腐剤あり／なし）。値は log10 CFU/g
    {"処方": "防腐剤あり", "菌": "細菌", "0日": 6.0, "7日": 2.4, "14日": 1.0, "28日": 1.0},
    {"処方": "防腐剤あり", "菌": "酵母", "0日": 5.5, "7日": 4.1, "14日": 3.0, "28日": 2.2},
    {"処方": "防腐剤あり", "菌": "カビ", "0日": 5.3, "7日": 5.1, "14日": 4.0, "28日": 3.5},
    {"処方": "防腐剤なし", "菌": "細菌", "0日": 6.0, "7日": 5.2, "14日": 5.8, "28日": 6.4},
    {"処方": "防腐剤なし", "菌": "酵母", "0日": 5.5, "7日": 5.6, "14日": 6.1, "28日": 6.3},
    {"処方": "防腐剤なし", "菌": "カビ", "0日": 5.3, "7日": 5.5, "14日": 5.9, "28日": 6.0},
])


def challenge_judge(df: pd.DataFrame, criteria: dict = CRITERIA_A) -> pd.DataFrame:
    """日ごとの log 減少（0日 − その日）と「前の時点から増えていないか」で判定する"""
    out = []
    for r in df.to_dict("records"):
        crit = criteria.get(r["菌"], {})
        prev, ok_all, notes = r["0日"], True, []
        row = {"処方": r["処方"], "菌": r["菌"]}
        for d in (7, 14, 28):
            v = r[f"{d}日"]
            red = r["0日"] - v
            need = crit.get(d, 0.0)
            ok = red >= need and (d == 7 or v <= prev + 0.5)   # 0.5 log 以内の揺れは「増えていない」とみなす
            row[f"{d}日の減少(log)"] = round(red, 2)
            if not ok:
                ok_all = False
                notes.append(f"{d}日：必要{need:g}に対し{red:.1f}" + ("・増えた" if v > prev + 0.5 else ""))
            prev = v
        row["判定"] = "✅ 適合" if ok_all else "❌ 不適合"
        row["理由"] = "／".join(notes)
        out.append(row)
    return pd.DataFrame(out)


# ============================================================
# 自己チェック（手計算と照らし合わせ）
# ============================================================
if __name__ == "__main__":
    # ロジスティック：r=ln2, K大 → 最初は1時間で2倍
    assert abs(logistic(1, 1, 1e9, math.log(2)) - 2) < 1e-6
    # 当てはめ：きれいなデータなら元の r に戻る
    tt = np.arange(0, 20, 2.0)
    f = fit_logistic(tt, logistic(tt, 1.0, 2.5, 0.4))
    assert abs(f["r"] - 0.4) < 0.02 and abs(f["K"] - 2.5) < 0.03, f
    # 温度モデル：最適温度で最大、範囲外で0
    assert abs(float(cardinal_rate(30)) - 1) < 1e-9 and cardinal_rate(1) == 0 and cardinal_rate(41) == 0
    # 倍々：1 → 1000 は 10 回（2^10=1024）
    assert len(doubling_trace(1, 1000, 1.5)) == 10
    # オイラー法：dt を小さくすると誤差が減る
    e1 = abs(euler_trace(1, 0.5, 100, 1.0, 10)["誤差"]).max()
    e2 = abs(euler_trace(1, 0.5, 100, 0.25, 40)["誤差"]).max()
    assert e2 < e1
    # 共棲：乳酸菌がいると雑菌が抑えられる
    with_lab = coculture()["雑菌"].iloc[-1]
    no_lab = coculture(y0=(1.0, 0.0, 1.0))["雑菌"].iloc[-1]
    assert with_lab < no_lab, (with_lab, no_lab)
    # 配合：米ぬか 10kg だけなら C/N=20、水分12%
    r = mix(MATERIALS, {"米ぬか": 10})
    assert abs(r["C/N"] - 20) < 1e-9 and abs(r["水分%"] - 12) < 1e-9
    # 水：10kg（水分12%）を50%に → (1.2 + x)/(10 + x)=0.5 → x=7.6
    assert abs(water_to_add(MATERIALS, {"米ぬか": 10}, 50) - 7.6) < 1e-9
    # CFU：30〜300 は 232,244,33（28 は30未満で使わない）→ 素朴な平均 (23200+24400+33000)/3 = 26866.67
    assert abs(cfu_simple(SAMPLE_PLATES)["CFU/g"] - 80600 / 3) < 1e-6
    # 重みつき：(232+244+33)/(1×(2+0.1×1)×0.01) = 509/0.021 = 24238.09…
    assert abs(cfu_weighted(SAMPLE_PLATES)["CFU/g"] - 509 / 0.021) < 1e-6
    # トレース表の最後 = 素朴な方法の合計
    tr = cfu_trace(SAMPLE_PLATES)
    assert abs(tr["合計(CFU/g)"].iloc[-1] / tr["使った枚数"].iloc[-1] - 80600 / 3) < 1e-6
    # 保存効力：防腐剤ありの細菌は適合、なしは不適合
    j = challenge_judge(SAMPLE_CHALLENGE)
    assert j.iloc[0]["判定"].startswith("✅") and j.iloc[3]["判定"].startswith("❌")
    # 堆肥：熱すぎの判定が出る
    assert compost_flags(sample_compost())["判定"].str.contains("発酵中").any()
    print("microbe_lab.py：自己チェック OK")

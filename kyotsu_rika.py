"""
kyotsu_rika.py — 「共通テスト『理科』を情報Ⅰで解く」の計算部品

画面は pages/18_📝_共通テスト理科×情報Ⅰ.py。`python kyotsu_rika.py` で自己チェック（手計算と照らし合わせ）。

ねらい
  共通テストの理科（基礎4科目）は、表やグラフを読んで計算する問題が多い。
  その「計算の手順」を DNCL（共通テスト『情報Ⅰ』の手順記述）に書き下し、トレース表で1行ずつ確かめると、
  理科の公式が「繰り返し・条件分岐・配列の探索」として見えてくる。題材はこの畑とパン屋。

  地学基礎：ハウスの結露と霜       … 飽和水蒸気量の表 → 配列の探索・線形補間（露点を求める）
  化学基礎：土の酸度と中和         … 物質量 mol → 繰り返しで滴定曲線を描く（中和点を探す）
  物理基礎：焼き上がったパンの冷め方 … 熱量の保存（熱平衡）・ニュートンの冷却をオイラー法で
  生物基礎：小麦の形質の遺伝       … 乱数で交配を再現（モンテカルロ法）→ 理論の比と χ² で比べる

数値の出どころ（教育用の目安。正式な値は教科書・理科年表で確かめる）
  - 飽和水蒸気量 [g/m³]：0℃ 4.8, 5℃ 6.8, 10℃ 9.4, 15℃ 12.8, 20℃ 17.3, 25℃ 23.1, 30℃ 30.4, 35℃ 39.6
  - 水の比熱 4.2 J/(g·K)。パン（食パン）の比熱は約 2.7 J/(g·K) とした（水分により幅がある）。
  - 問題文はすべてこのリポジトリのオリジナル（共通テストの形式にならったもの）で、過去問の転載ではない。
"""
from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import pandas as pd

# ============================================================
# 地学基礎：飽和水蒸気量・湿度・露点
# ============================================================
SAT_T = [0, 5, 10, 15, 20, 25, 30, 35]
SAT_V = [4.8, 6.8, 9.4, 12.8, 17.3, 23.1, 30.4, 39.6]


def sat_vapor(temp: float, ts: Sequence[float] = SAT_T, vs: Sequence[float] = SAT_V) -> float:
    """表のあいだを直線でつなぐ（線形補間）。表の外は端の2点の直線をのばす。"""
    i = 0
    while i < len(ts) - 2 and temp > ts[i + 1]:
        i += 1
    t0, t1, v0, v1 = ts[i], ts[i + 1], vs[i], vs[i + 1]
    return v0 + (v1 - v0) * (temp - t0) / (t1 - t0)


def humidity(temp: float, vapor: float) -> float:
    """湿度[%] = 空気1m³に含まれる水蒸気量 ÷ その温度の飽和水蒸気量 × 100"""
    return 100 * vapor / sat_vapor(temp)


def dew_point_trace(vapor: float, ts: Sequence[float] = SAT_T, vs: Sequence[float] = SAT_V) -> tuple[float, pd.DataFrame]:
    """露点：飽和水蒸気量がちょうど vapor になる温度。表を小さい方から探し、挟む2点で補間する（DNCLのトレース表つき）"""
    rows, i = [], 0
    while i < len(vs) - 1 and vs[i + 1] < vapor:
        rows.append({"i": i, "T[i+1]": ts[i + 1], "V[i+1]": vs[i + 1], "V[i+1] < 水蒸気量 か": True, "次へ": "i = i + 1"})
        i += 1
    rows.append({"i": i, "T[i+1]": ts[min(i + 1, len(ts) - 1)], "V[i+1]": vs[min(i + 1, len(vs) - 1)],
                 "V[i+1] < 水蒸気量 か": False, "次へ": "ここで止まる → 補間"})
    i = min(i, len(vs) - 2)
    t = ts[i] + (ts[i + 1] - ts[i]) * (vapor - vs[i]) / (vs[i + 1] - vs[i])
    return t, pd.DataFrame(rows)


def condensation(temp_day: float, hum_day: float, temp_night: float) -> dict:
    """昼の温度・湿度の空気が夜に冷えたとき、1m³あたり何gの水が結露するか"""
    v = sat_vapor(temp_day) * hum_day / 100
    s = sat_vapor(temp_night)
    return {"水蒸気量": v, "夜の飽和水蒸気量": s, "結露する水": max(0.0, v - s), "露点": dew_point_trace(v)[0]}


# ============================================================
# 化学基礎：中和と滴定曲線（強酸 × 強塩基、25℃）
# ============================================================
def ph_after(ca: float, va_ml: float, cb: float, vb_ml: float, valence_a: int = 1, valence_b: int = 1) -> float:
    """酸 ca[mol/L]×va[mL] に塩基 cb×vb を加えたあとの pH（完全に電離する強酸・強塩基とみなす）"""
    h = valence_a * ca * va_ml / 1000
    oh = valence_b * cb * vb_ml / 1000
    vol = (va_ml + vb_ml) / 1000
    if abs(h - oh) < 1e-15:
        return 7.0
    if h > oh:
        return -math.log10((h - oh) / vol)
    return 14 + math.log10((oh - h) / vol)


def titration(ca: float, va_ml: float, cb: float, step_ml: float, max_ml: float,
              valence_a: int = 1, valence_b: int = 1) -> pd.DataFrame:
    """塩基を step_ml ずつ加えるたびに pH を計算する（繰り返し＝滴定曲線）"""
    rows, vb = [], 0.0
    while vb <= max_ml + 1e-9:
        rows.append({"加えた量_mL": round(vb, 3), "pH": round(ph_after(ca, va_ml, cb, vb, valence_a, valence_b), 3)})
        vb += step_ml
    return pd.DataFrame(rows)


def equivalence_ml(ca: float, va_ml: float, cb: float, valence_a: int = 1, valence_b: int = 1) -> float:
    """中和点：酸が出す H⁺ の物質量 = 塩基が出す OH⁻ の物質量  →  a·c·V = b·c'·V'"""
    return valence_a * ca * va_ml / (valence_b * cb)


def lime_for_soil(acid_mmol_per_100g: float, soil_kg: float, purity: float = 0.95) -> dict:
    """土の中和に要る炭酸カルシウム（CaCO₃ = 100 g/mol、2価）。土の酸の量 [mmol H⁺ / 100 g 土] は測定値（目安）を入れる。
    CaCO₃ 1 mol で H⁺ 2 mol を中和 → 必要な CaCO₃[g] = H⁺[mol] ÷ 2 × 100"""
    h_mol = acid_mmol_per_100g / 1000 * soil_kg * 1000 / 100
    caco3 = h_mol / 2 * 100
    return {"H⁺_mol": h_mol, "CaCO3_g": caco3, "資材_g": caco3 / purity}


# ============================================================
# 物理基礎：熱平衡・ニュートンの冷却
# ============================================================
def equilibrium_temp(items: Sequence[tuple[float, float, float]]) -> float:
    """熱平衡：外に熱が逃げないとき、Σ m c (T − Te) = 0  →  Te = Σ m c T ÷ Σ m c。items = [(質量g, 比熱, 温度℃), …]"""
    num = sum(m * c * t for m, c, t in items)
    den = sum(m * c for m, c, _ in items)
    return num / den


def cooling_exact(t, t0: float, ta: float, k: float):
    """ニュートンの冷却：dT/dt = −k (T − Ta)  →  T = Ta + (T0 − Ta) e^(−kt)"""
    return ta + (t0 - ta) * np.exp(-k * np.asarray(t, float))


def cooling_euler(t0: float, ta: float, k: float, dt: float, minutes: float) -> pd.DataFrame:
    """オイラー法：T ← T − Δt × k × (T − Ta) を Δt ごとにくり返す"""
    rows, T, i = [], t0, 0
    while i * dt <= minutes + 1e-9:
        rows.append({"i": i, "t_分": round(i * dt, 3), "T（オイラー法）": round(T, 3),
                     "T（式）": round(float(cooling_exact(i * dt, t0, ta, k)), 3)})
        T = T - dt * k * (T - ta)
        i += 1
    d = pd.DataFrame(rows)
    d["誤差"] = (d["T（オイラー法）"] - d["T（式）"]).round(3)
    return d


def time_to_reach(target: float, t0: float, ta: float, k: float) -> float:
    """T = target になる時刻：t = ln((T0 − Ta)/(target − Ta)) ÷ k"""
    if not (min(t0, ta) < target < max(t0, ta)):
        return float("nan")
    return math.log((t0 - ta) / (target - ta)) / k


# ============================================================
# 生物基礎（生物）：遺伝の分離比をモンテカルロ法で
# ============================================================
def cross_sim(n: int, seed: int = 0, genes: int = 2) -> pd.DataFrame:
    """AaBb × AaBb（genes=1 なら Aa × Aa）。両親から1つずつ、乱数で配偶子を選ぶ。A・B は優性（顕性）。"""
    rng = np.random.default_rng(seed)
    a = rng.integers(0, 2, (n, 2)).sum(axis=1)       # 優性の数 0〜2
    out = {"A": np.where(a > 0, "A（顕性）", "a（潜性）")}
    if genes == 2:
        b = rng.integers(0, 2, (n, 2)).sum(axis=1)
        out["B"] = np.where(b > 0, "B（顕性）", "b（潜性）")
    df = pd.DataFrame(out)
    df["表現型"] = df.apply(lambda r: "・".join(r.values), axis=1)
    return df


def ratio_table(sim: pd.DataFrame, genes: int = 2) -> pd.DataFrame:
    if genes == 2:
        theory = {"A（顕性）・B（顕性）": 9, "A（顕性）・b（潜性）": 3, "a（潜性）・B（顕性）": 3, "a（潜性）・b（潜性）": 1}
    else:
        theory = {"A（顕性）": 3, "a（潜性）": 1}
    n = len(sim)
    tot = sum(theory.values())
    vc = sim["表現型"].value_counts()
    t = pd.DataFrame({"表現型": list(theory), "理論の比": list(theory.values())})
    t["期待値"] = t["理論の比"] / tot * n
    t["観測値"] = [int(vc.get(k, 0)) for k in theory]
    t["(観測−期待)²/期待"] = ((t["観測値"] - t["期待値"]) ** 2 / t["期待値"]).round(3)
    return t


CHI2_05 = {1: 3.841, 2: 5.991, 3: 7.815}   # 有意水準5%の境目（自由度ごと）


def trace_cross(n: int, seed: int = 0) -> pd.DataFrame:
    """Aa × Aa を n 回、乱数で配偶子を選んで数える（DNCLのトレース表）"""
    rng = np.random.default_rng(seed)
    big = small = 0
    rows = []
    for i in range(n):
        f, m = int(rng.integers(0, 2)), int(rng.integers(0, 2))   # 1=A, 0=a
        if f + m >= 1:
            big += 1
        else:
            small += 1
        rows.append({"i": i, "父の配偶子": "A" if f else "a", "母の配偶子": "A" if m else "a",
                     "子": ("A" if f else "a") + ("A" if m else "a"), "顕性の数": big, "潜性の数": small})
    return pd.DataFrame(rows)


# ============================================================
# 自己チェック
# ============================================================
if __name__ == "__main__":
    # 地学：表の点ではその値、20℃と25℃の中間 22.5℃ は (17.3+23.1)/2 = 20.2
    assert sat_vapor(20) == 17.3 and abs(sat_vapor(22.5) - 20.2) < 1e-9
    # 25℃・湿度60% → 23.1×0.6 = 13.86 g → 露点は 15℃(12.8) と 20℃(17.3) のあいだ：15 + 5×(1.06/4.5) = 16.18
    dp, tr = dew_point_trace(23.1 * 0.6)
    assert abs(dp - (15 + 5 * 1.06 / 4.5)) < 1e-9 and len(tr) == 4
    # 結露：25℃60% の空気が 10℃ に冷える → 13.86 − 9.4 = 4.46 g
    assert abs(condensation(25, 60, 10)["結露する水"] - 4.46) < 1e-9
    # 化学：0.10 mol/L 塩酸 10 mL を 0.10 mol/L NaOH で → 中和点 10 mL、はじめ pH 1、中和点 pH 7
    assert abs(equivalence_ml(0.1, 10, 0.1) - 10) < 1e-12
    assert abs(ph_after(0.1, 10, 0.1, 0) - 1) < 1e-9 and ph_after(0.1, 10, 0.1, 10) == 7.0
    # 硫酸（2価）0.05 mol/L 10 mL → H⁺ 1 mmol → NaOH 0.1 で 10 mL
    assert abs(equivalence_ml(0.05, 10, 0.1, valence_a=2) - 10) < 1e-12
    # 石灰：酸 2 mmol/100g の土 100 kg → H⁺ 2 mol → CaCO₃ 1 mol = 100 g
    assert abs(lime_for_soil(2, 100, 1.0)["CaCO3_g"] - 100) < 1e-9
    # 物理：60℃の水100g と 20℃の水100g → 40℃
    assert abs(equilibrium_temp([(100, 4.2, 60), (100, 4.2, 20)]) - 40) < 1e-12
    # 冷却：T0=90, Ta=20, k=0.05 → 55℃ は ln2/0.05 = 13.86分（半分の差になる時間）
    assert abs(time_to_reach(55, 90, 20, 0.05) - math.log(2) / 0.05) < 1e-9
    # オイラー法：Δt を小さくすると誤差が減る
    assert cooling_euler(90, 20, 0.05, 1, 60)["誤差"].abs().max() < cooling_euler(90, 20, 0.05, 5, 60)["誤差"].abs().max()
    # 遺伝：10万回で 9:3:3:1 に近い（χ² が境目より小さい）
    rt = ratio_table(cross_sim(100000, seed=1))
    assert rt["(観測−期待)²/期待"].sum() < CHI2_05[3], rt
    # トレース表の最後の行の数の合計 = 回数
    t = trace_cross(12, seed=3)
    assert t.iloc[-1]["顕性の数"] + t.iloc[-1]["潜性の数"] == 12
    print("kyotsu_rika.py：自己チェック OK")

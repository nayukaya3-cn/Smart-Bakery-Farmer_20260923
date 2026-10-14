"""
中学理科「量の計算」─ 現象を計算する → 可視化する → 自分の条件で判断する の計算部品

pages/6_🧪_中学理科_量の計算.py から呼び出します。画面を持たない純粋な関数だけを置き、
`python chugaku_rika.py` で自己チェック（assert）が走ります。

ねらい
  小学校の理科は「観察して言葉で説明する」問題が中心。中学では
    オームの法則（中2）・質量パーセント濃度（中1）・化学変化と質量（中2）
  のように、数式と割合で現象を扱う単元が一気に増える。三つは見た目が違っても、
  すべて「比べる量 = もとにする量 × 割合」（比例 y = a x）という同じ形をしている。
  つまずきの多くは理科ではなく「何を もと（100%・1）にするか」の取り違えなので、
  典型的な間違い方を判定して、その場で言葉にして返す（diagnose_* 関数）。

数値の出どころ（教育用の単純化を含む）
  - 家庭用コンセント 100 V、テーブルタップ・延長コードの定格は一般に 15 A（1500 W）。
  - 炭酸水素ナトリウム（重曹）の熱分解：2NaHCO3 → Na2CO3 + H2O + CO2
      168 g → 106 g（残る）+ 18 g（水）+ 44 g（二酸化炭素）。中学では実験の比で扱い、
      分子の重さによる説明は高校「化学基礎」の発展として示す。
  - 二酸化炭素の密度 約 1.8 g/L（20℃・1気圧付近）。
  - 米ぬかの水分 約 12%（乾物として扱う目安）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ─────────────────────────────────────────────
# 共通：三つの単元は同じ形
# ─────────────────────────────────────────────
SAME_FORM = pd.DataFrame([
    ("オームの法則（中2）", "電流 I [A]", "電圧 V [V]", "1/抵抗 = 1/R",
     "I = V ÷ R", "抵抗が同じなら、電圧を2倍にすると電流も2倍"),
    ("質量パーセント濃度（中1）", "溶質の質量 [g]", "溶液の質量 [g]（溶媒ではない）", "濃度 ÷ 100",
     "溶質 = 溶液 × 濃度/100", "濃度が同じなら、溶液を2倍にすると溶質も2倍"),
    ("化学変化と質量（中2）", "残る物質の質量 [g]", "加熱前の質量 [g]", "実験で求める比（重曹なら約0.63）",
     "残る質量 = 加熱前 × 0.63", "加熱前を2倍にすると残る質量も2倍"),
], columns=["単元", "比べる量 y", "もとにする量 x", "割合 a", "式", "確かめ方"])

# ─────────────────────────────────────────────
# A. オームの法則・電力（中2「電流とその利用」）
# ─────────────────────────────────────────────
VOLTAGE = 100.0      # 家庭用コンセント [V]
TAP_LIMIT_A = 15.0   # テーブルタップの定格電流 [A]（一般的な値。本体の表示を必ず確認）

APPLIANCE_COLS = ["機器", "消費電力_W", "使う"]


def sample_appliances() -> pd.DataFrame:
    """パン工房・ハウスで使いそうな機器（消費電力は一般的な目安。実物の表示で置き換える）。"""
    return pd.DataFrame([
        ("オーブンレンジ", 1300, True),
        ("電気ケトル", 1200, False),
        ("ホームベーカリー", 430, False),
        ("発酵器（ニーダー保温）", 100, True),
        ("育苗ヒーターマット", 60, False),
        ("ノートPC（記録用）", 40, True),
    ], columns=APPLIANCE_COLS)


def current_a(power_w: float, voltage_v: float = VOLTAGE) -> float:
    """電力 P = V × I より I = P ÷ V。"""
    if voltage_v <= 0:
        raise ValueError("電圧は正の値")
    return power_w / voltage_v


def resistance_ohm(power_w: float, voltage_v: float = VOLTAGE) -> float:
    """電熱線とみなしたときの抵抗 R = V ÷ I = V² ÷ P。"""
    if power_w <= 0:
        raise ValueError("消費電力は正の値")
    return voltage_v ** 2 / power_w


def tap_load(df: pd.DataFrame, voltage_v: float = VOLTAGE,
             limit_a: float = TAP_LIMIT_A) -> dict:
    """1つのタップに並列につないだときの合計電流（並列回路では電流が足し算）。"""
    use = df[df["使う"].astype(bool)].copy()
    use["電流_A"] = use["消費電力_W"].astype(float) / voltage_v
    total = float(use["電流_A"].sum())
    return {"table": use, "total_a": total, "total_w": total * voltage_v,
            "ratio": total / limit_a, "ok": total <= limit_a,
            "margin_a": limit_a - total}


def energy_cost_yen(power_w: float, hours: float, yen_per_kwh: float = 31.0) -> float:
    """電力量 [kWh] = 電力 [kW] × 時間 [h]、電気代 = 電力量 × 単価。"""
    return power_w / 1000 * hours * yen_per_kwh


def diagnose_ohm(answer_a: float, power_w: float, voltage_v: float = VOLTAGE) -> tuple[bool, str]:
    """「P[W] の機器に流れる電流は？」への答えを、典型的な間違い方で判定する。"""
    right = current_a(power_w, voltage_v)
    if np.isclose(answer_a, right, rtol=0.02):
        return True, "正解。電流 = 電力 ÷ 電圧。"
    if np.isclose(answer_a, power_w * voltage_v, rtol=0.02):
        return False, "電力と電圧をかけています。P = V × I なので、I は P を V で「割る」。"
    if np.isclose(answer_a, voltage_v / power_w, rtol=0.02):
        return False, "割る向きが逆です。単位で確かめると W ÷ V = A。"
    if np.isclose(answer_a, right * 1000, rtol=0.02):
        return False, "mA（ミリアンペア）で答えていませんか。1 A = 1000 mA。"
    return False, f"もう一度。式 I = P ÷ V に {power_w:g} と {voltage_v:g} を入れてみよう。"


# ─────────────────────────────────────────────
# B. 質量パーセント濃度（中1「水溶液」）
# ─────────────────────────────────────────────
def mass_percent(solute_g: float, solvent_g: float) -> float:
    """質量パーセント濃度 = 溶質 ÷ (溶質 + 溶媒) × 100。"""
    total = solute_g + solvent_g
    if total <= 0:
        raise ValueError("溶液の質量が0")
    return solute_g / total * 100


def bakers_percent(ingredient_g: float, flour_g: float) -> float:
    """ベーカーズ％（パン屋の％）= 材料 ÷ 粉 × 100。分母が「粉」で、溶液全体ではない。"""
    if flour_g <= 0:
        raise ValueError("粉の量が0")
    return ingredient_g / flour_g * 100


def dilute_percent(stock_percent: float, times: float) -> float:
    """原液を times 倍に薄めた濃度（液肥の「1000倍希釈」など）。"""
    if times < 1:
        raise ValueError("倍率は1以上")
    return stock_percent / times


def stock_ml_for(total_ml: float, times: float) -> float:
    """times 倍に薄めた液を total_ml 作るのに要る原液の量（原液 + 水 = 全体）。"""
    if times < 1:
        raise ValueError("倍率は1以上")
    return total_ml / times


def water_to_add(dry_g: float, now_water_pct: float, target_pct: float) -> float:
    """水分 now% の材料 dry_g に水を足して、水分（水の質量パーセント）を target% にする量。

    (dry×now + add) / (dry + add) = target  を add について解く。
    """
    now, tgt = now_water_pct / 100, target_pct / 100
    if not 0 <= now < 1 or not 0 <= tgt < 1:
        raise ValueError("水分は 0〜100% 未満")
    if tgt <= now:
        return 0.0
    return dry_g * (tgt - now) / (1 - tgt)


def concentration_curve(solute_g: float, solvent_start_g: float,
                        add_max_g: float, n: int = 60) -> pd.DataFrame:
    """水を足していったときの濃度の変化（直線ではなく、反比例に近い曲線になる）。"""
    add = np.linspace(0, add_max_g, n)
    pct = solute_g / (solute_g + solvent_start_g + add) * 100
    return pd.DataFrame({"足した水_g": add, "濃度_%": pct})


def diagnose_percent(answer_pct: float, solute_g: float, solvent_g: float) -> tuple[bool, str]:
    """「溶質 a g を水 b g に溶かした濃度は？」への答えを判定する。"""
    right = mass_percent(solute_g, solvent_g)
    if np.isclose(answer_pct, right, atol=0.05):
        return True, "正解。分母は「溶質 + 溶媒」＝溶液全体。"
    if np.isclose(answer_pct, solute_g / solvent_g * 100, atol=0.05):
        return False, ("分母を水（溶媒）だけにしています。溶けた食塩も溶液の一部なので、"
                       f"分母は {solute_g:g} + {solvent_g:g} = {solute_g + solvent_g:g} g。"
                       "（パン屋の％は分母が粉。何を100とするかで答えが変わる）")
    if np.isclose(answer_pct, right / 100, atol=0.0005):
        return False, "×100 を忘れています。割合（0.〜）とパーセント（〜%）は100倍ちがう。"
    return False, "もう一度。濃度 = 溶質 ÷ (溶質 + 溶媒) × 100。"


# ─────────────────────────────────────────────
# C. 化学変化と質量（中2「化学変化と原子・分子」）
# ─────────────────────────────────────────────
NAHCO3_RESIDUE = 106 / 168   # 重曹を加熱し切ったとき残る炭酸ナトリウムの割合（約0.631）
NAHCO3_CO2 = 44 / 168        # 出ていく二酸化炭素の割合（約0.262）
NAHCO3_H2O = 18 / 168        # 出ていく水（水蒸気）の割合（約0.107）
CO2_DENSITY_G_PER_L = 1.8    # 20℃付近


def sample_heating() -> pd.DataFrame:
    """架空の加熱実験データ（実測ではありません）。加熱前と、加熱し切った後の質量。"""
    rng = np.random.default_rng(2026)
    before = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    after = before * NAHCO3_RESIDUE + rng.normal(0, 0.03, size=before.size)
    return pd.DataFrame({"加熱前_g": before, "加熱後_g": after.round(2)})


def fit_through_origin(x: np.ndarray, y: np.ndarray) -> float:
    """原点を通る直線 y = a x の傾き a（最小二乗）。比例の関係を測定から求める。"""
    x, y = np.asarray(x, float), np.asarray(y, float)
    if np.sum(x * x) == 0:
        raise ValueError("x がすべて0")
    return float(np.sum(x * y) / np.sum(x * x))


def soda_products(soda_g: float) -> dict:
    """重曹 soda_g を加熱し切ったときに、残るもの・出ていくもの（質量保存を確かめる）。"""
    res = soda_g * NAHCO3_RESIDUE
    co2 = soda_g * NAHCO3_CO2
    h2o = soda_g * NAHCO3_H2O
    return {"残る炭酸ナトリウム_g": res, "二酸化炭素_g": co2, "水蒸気_g": h2o,
            "二酸化炭素_L": co2 / CO2_DENSITY_G_PER_L,
            "合計_g": res + co2 + h2o}


def open_vs_closed(soda_g: float) -> pd.DataFrame:
    """ふたを開けた容器と閉じた容器で、はかりの値はどう変わるか。"""
    p = soda_products(soda_g)
    return pd.DataFrame([
        ("ふたを開けた容器", soda_g, p["残る炭酸ナトリウム_g"],
         "気体（CO₂・水蒸気）が外へ出ていくので軽くなる"),
        ("ふたを閉じた容器", soda_g, p["合計_g"],
         "原子は出入りしないので、質量は変わらない（質量保存の法則）"),
    ], columns=["条件", "加熱前_g", "加熱後_g", "理由"])


def diagnose_residue(answer_g: float, soda_g: float, ratio: float = NAHCO3_RESIDUE) -> tuple[bool, str]:
    """「重曹 x g を加熱し切ると何 g 残る？」（比 = ratio）への答えを判定する。"""
    right = soda_g * ratio
    if np.isclose(answer_g, right, atol=0.05):
        return True, "正解。加熱前 × 割合。比例なので、量が2倍なら残りも2倍。"
    if np.isclose(answer_g, soda_g / ratio, atol=0.05):
        return False, "割合で割っています。残る量は加熱前より「少ない」はず。かけ算に直そう。"
    if np.isclose(answer_g, soda_g * (1 - ratio), atol=0.05):
        return False, "それは「出ていった気体」の質量です。問われているのは残った固体。"
    if np.isclose(answer_g, soda_g, atol=0.01):
        return False, "ふたを開けて加熱すると、気体が出ていくので軽くなります。"
    return False, f"もう一度。残る質量 = {soda_g:g} g × {ratio:.2f}。"


# ─────────────────────────────────────────────
# 横軸：自己効力感と将来像（TIMSS 2023 中学2年・理科、出典はページに明記）
# ─────────────────────────────────────────────
TIMSS2023_G8_SCIENCE = pd.DataFrame([
    ("理科の勉強は楽しい", 70, 79),
    ("理科は得意だ", 45, 51),
    ("理科を使う職業につきたい", 27, 58),
], columns=["質問", "日本_%", "国際平均_%"])

JOBS = pd.DataFrame([
    ("オームの法則・電力", "パン職人", "オーブンと発酵器を同じ回路で使えるか、ブレーカーが落ちない組み合わせを決める"),
    ("オームの法則・電力", "電気工事士・設備保全", "機器の定格と配線の太さから、安全に使える範囲を決める"),
    ("オームの法則・電力", "スマート農業・ロボット", "ハウスのヒーターやセンサー、ロボットの電源容量を見積もる"),
    ("質量パーセント濃度", "パン職人", "塩・砂糖・酵母をベーカーズ％で配合し、仕込み量を変えても同じ味にする"),
    ("質量パーセント濃度", "農家", "液肥を何倍に薄めるか、ぼかし肥料の水分を何％にするかを決める"),
    ("質量パーセント濃度", "看護師・薬剤師", "点滴や消毒液の濃度を計算する"),
    ("化学変化と質量", "パン・菓子職人", "重曹やベーキングパウダーの量から、ふくらみと苦みのバランスを決める"),
    ("化学変化と質量", "食品の品質管理（HACCP）", "加熱前後の重さの変化から、水分や工程の異常を見つける"),
    ("化学変化と質量", "環境・エネルギー", "燃料を燃やしたときに出る二酸化炭素の量を見積もる"),
], columns=["単元", "仕事", "使う場面"])

EFFICACY_LEVELS = {1: "まったくそう思わない", 2: "あまりそう思わない", 3: "ややそう思う", 4: "とてもそう思う"}


def efficacy_summary(rec: pd.DataFrame) -> pd.DataFrame:
    """自己評価（前・後）を単元ごとにまとめ、「得意だ（3以上）」の割合を出す。"""
    if rec.empty:
        return pd.DataFrame(columns=["単元", "前_平均", "後_平均", "前_得意%", "後_得意%"])
    g = rec.groupby("単元")
    return pd.DataFrame({
        "前_平均": g["前"].mean(), "後_平均": g["後"].mean(),
        "前_得意%": g["前"].apply(lambda s: (s >= 3).mean() * 100),
        "後_得意%": g["後"].apply(lambda s: (s >= 3).mean() * 100),
    }).reset_index()


# ─────────────────────────────────────────────
# 自己チェック
# ─────────────────────────────────────────────
if __name__ == "__main__":
    # A
    assert np.isclose(current_a(1200), 12.0)
    assert np.isclose(resistance_ohm(1000), 10.0)
    r = tap_load(sample_appliances())
    assert np.isclose(r["total_a"], (1300 + 100 + 40) / 100)
    assert r["ok"]
    df = sample_appliances()
    df.loc[df["機器"] == "電気ケトル", "使う"] = True
    assert not tap_load(df)["ok"]                       # 1300+1200 W で 15 A を超える
    assert diagnose_ohm(12, 1200)[0]
    assert "割る" in diagnose_ohm(120000, 1200)[1]
    assert "逆" in diagnose_ohm(100 / 1200, 1200)[1]
    assert np.isclose(energy_cost_yen(100, 10, 30), 30.0)
    # B
    assert np.isclose(mass_percent(10, 90), 10.0)
    assert np.isclose(bakers_percent(10, 500), 2.0)
    assert np.isclose(dilute_percent(6, 1000), 0.006)
    assert np.isclose(stock_ml_for(5000, 1000), 5.0)
    add = water_to_add(10_000, 12, 40)
    assert np.isclose((10_000 * 0.12 + add) / (10_000 + add), 0.40)
    assert water_to_add(1000, 50, 40) == 0.0
    c = concentration_curve(10, 90, 900)
    assert c["濃度_%"].is_monotonic_decreasing and np.isclose(c["濃度_%"].iloc[-1], 1.0)
    ok, msg = diagnose_percent(25 / 75 * 100, 25, 75)
    assert not ok and "分母" in msg
    assert diagnose_percent(25, 25, 75)[0]
    # C
    p = soda_products(8.4)
    assert np.isclose(p["合計_g"], 8.4)                  # 質量保存
    assert np.isclose(p["残る炭酸ナトリウム_g"], 5.3)
    h = sample_heating()
    assert abs(fit_through_origin(h["加熱前_g"], h["加熱後_g"]) - NAHCO3_RESIDUE) < 0.02
    assert diagnose_residue(8.4 * NAHCO3_RESIDUE, 8.4)[0]
    assert "気体" in diagnose_residue(8.4 * (1 - NAHCO3_RESIDUE), 8.4)[1]
    oc = open_vs_closed(2.0)
    assert np.isclose(oc.loc[1, "加熱後_g"], 2.0) and oc.loc[0, "加熱後_g"] < 2.0
    # 横軸
    rec = pd.DataFrame({"単元": ["A", "A"], "前": [2, 3], "後": [3, 4]})
    s = efficacy_summary(rec)
    assert np.isclose(s["前_得意%"].iloc[0], 50) and np.isclose(s["後_得意%"].iloc[0], 100)
    print("chugaku_rika: all checks passed")

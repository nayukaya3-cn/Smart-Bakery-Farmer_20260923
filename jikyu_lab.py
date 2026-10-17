"""
jikyu_lab.py ─ 自給と防災の畑シミュレーター（計算部）

ページ pages/15_自給シミュレーター.py から呼び出します。単体で `python jikyu_lab.py` を
実行すると、プリセット4案の比較表と自己チェックを表示します。

骨格はリポジトリ共通の3段構え：
  ① 計算する … 畑の配分（二毛作など）から、月ごとの自給量・不足分の調達経路・費用を出す
  ② 可視化する … ページ側で plotly に渡す縦長（long）形式の DataFrame を返す
  ③ 判断する … 二毛作の季節制約・停電断水時の持ちこたえ日数など、判断材料を返す

連動するデータ構造:
  - plan_to_kakeibo() … 自給家計簿の「収穫」と同じ列（日付・品目・数量・単位・単価(円)）で計画値を返す
  - income_link()     … 収入構造シミュレーターの「C 自給」に渡す削減額（saving_step / saving_cap）

数値はすべて目安の初期値です。実測CSV（coef_from_measurements）で自分の畑の値に置き換えていく前提です。
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date

import numpy as np
import pandas as pd

FIELD_M2 = 100  # 畑の面積（ハウスは別）

# ── 月ごとの分布（合計1）。露地は夏に多く、ハウスは冬の端境期を埋める ──
VEG_OPEN = np.array([4, 3, 4, 6, 9, 12, 14, 13, 10, 9, 9, 7]) / 100
VEG_HOUSE = np.array([10, 10, 11, 9, 7, 6, 5, 5, 7, 9, 10, 11]) / 100
KAKI = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 40, 60, 0]) / 100
FIG = np.array([0, 0, 0, 0, 0, 0, 0, 30, 45, 25, 0, 0]) / 100
KURI = np.array([0, 0, 0, 0, 0, 0, 0, 0, 60, 40, 0, 0]) / 100
# 三原周辺の月降水量の目安（mm）。気象庁の平年値（三原・福山など近い地点）で置き換える
RAIN_MM = np.array([40, 55, 90, 110, 140, 200, 180, 100, 170, 110, 65, 40])


@dataclass(frozen=True)
class Coef:
    yield_kg_m2: float   # 年間収量（kg/㎡）
    kcal_per_kg: float
    labor_h_m2: float    # 年間作業時間（時間/㎡）
    cost_yen_m2: float   # 種苗・肥料・資材（円/㎡・年）
    price_yen_kg: float  # 同じものを買った場合の単価（家計簿の換算に使う）


COEF: dict[str, Coef] = {
    "小麦": Coef(0.30, 3300, 0.3, 30, 400),      # 300kg/10a。小面積は鳥害を見込んで控えめ
    "大豆": Coef(0.20, 3700, 0.4, 20, 1000),     # 乾燥豆
    "サツマイモ": Coef(2.5, 1300, 0.5, 60, 400),
    "露地野菜": Coef(4.0, 300, 1.5, 150, 450),
    "ハウス野菜": Coef(6.0, 300, 2.0, 200, 450),
}

# 1人1か月の必要量（kg）と単価
DEMAND = {"主食": 5.0, "野菜": 9.0, "果物": 4.5, "たんぱく質": 3.0}
KCAL = {"主食": 3420, "野菜": 300, "果物": 600, "たんぱく質": 2000}  # 主食は米換算、たんぱく質は肉換算
PRICE = {"米": 750, "小麦粉": 450, "野菜": 450, "冷凍野菜・乾物": 550, "果物": 700,
         "下味冷凍": 1400, "缶詰": 1500}
KCAL_PER_DAY = 2000
SOY_MEAT_EQ = 1.7  # 乾燥大豆1kg ≒ 肉1.7kg分のたんぱく質（目安）
SEED_G_M2 = 10     # 小麦の播種量（条まき）

CHANNELS = ["自家産（とれたて）", "自家産（保存・貯蔵）", "下味冷凍", "常備品", "現地で買う"]
CATEGORIES = list(DEMAND)

STAGES = {"現在：隔週帰省で管理": 0.4, "移住1年目": 0.7, "移住3年目以降": 1.0}

PRESETS: dict[str, tuple[int, int]] = {  # (小麦→大豆の面積, 小麦→サツマイモの面積)
    "A 二毛作主体（小麦→大豆 70㎡）": (70, 0),
    "B 野菜中心（小麦なし）": (0, 0),
    "C 小麦→サツマイモ 70㎡": (0, 70),
    "D 折衷（小麦→大豆 50㎡・小麦→サツマイモ 20㎡）": (50, 20),
}


@dataclass
class Conditions:
    persons: int = 2
    stage: float = 0.7
    house_m2: float = 20
    bread_share: float = 0.25   # 主食のうちパンの割合
    keep_rate: float = 0.5      # 余剰を保存に回せる割合
    kuri_vigor: float = 0.4     # 栗の樹勢（盛りの木=1）
    rice_own: bool = False      # 米を委託中の水田から現物で受け取る（想定）
    a_soy: float = 70           # 小麦→大豆の面積
    a_imo: float = 0            # 小麦→サツマイモの面積
    coef: dict[str, Coef] = field(default_factory=lambda: dict(COEF))

    @property
    def a_wheat(self) -> float:
        return self.a_soy + self.a_imo

    @property
    def a_veg(self) -> float:
        return max(0.0, FIELD_M2 - self.a_wheat)


# ───────────────────────── ① 計算する ─────────────────────────
def _carry_over(dem: np.ndarray, prod: np.ndarray, keep: float, decay: float = 0.05):
    """月ごとに「とれたて → 保存分 → 不足」の順に充てる。2年回して2年目を返す（持ち越しを反映）。"""
    stock = 0.0
    for _ in range(2):
        fresh, stored, rem = np.zeros(12), np.zeros(12), np.zeros(12)
        for m in range(12):
            stock *= 1 - decay
            fresh[m] = min(prod[m], dem[m])
            r = dem[m] - fresh[m]
            stored[m] = min(stock, r)
            stock -= stored[m]
            rem[m] = r - stored[m]
            stock += (prod[m] - fresh[m]) * keep
    return fresh, stored, rem


def production(c: Conditions) -> dict[str, np.ndarray]:
    """月ごとの生産量（kg）。小麦は6月、大豆・サツマイモは10月に収穫。"""
    k, s = c.coef, c.stage
    z = np.zeros(12)
    wheat = z.copy()
    wheat[5] = max(0.0, c.a_wheat * k["小麦"].yield_kg_m2 * s - c.a_wheat * SEED_G_M2 / 1000)
    soy = z.copy()
    soy[9] = c.a_soy * k["大豆"].yield_kg_m2 * s
    imo = z.copy()
    imo[9] = c.a_imo * k["サツマイモ"].yield_kg_m2 * s
    veg = (c.a_veg * k["露地野菜"].yield_kg_m2 * s * VEG_OPEN
           + c.house_m2 * k["ハウス野菜"].yield_kg_m2 * s * VEG_HOUSE)
    fruit = (40 * max(s, 0.7) * KAKI + 2 * 8 * s * FIG
             + 5 * 5 * c.kuri_vigor * max(s, 0.6) * KURI)
    return {"小麦": wheat, "大豆": soy, "サツマイモ": imo, "野菜": veg, "果物": fruit}


def simulate(c: Conditions) -> tuple[pd.DataFrame, dict]:
    """月×品目×調達経路の量（kg）を縦長の表で返し、年間の要約を dict で返す。"""
    P = c.persons
    prod = production(c)
    flour = prod["小麦"].sum() * 0.9                 # 製粉歩留まり90%。通年で少しずつ使う
    imo_eq = np.zeros(12)                             # サツマイモは10〜2月に食べる（米換算）
    for m in (9, 10, 11, 0, 1):
        imo_eq[m] = prod["サツマイモ"].sum() * 0.9 / 5 * KCAL_PER_KG_IMO_TO_RICE
    rows = []

    def add(cat, arr_by_ch):
        for ch, arr in arr_by_ch.items():
            for m in range(12):
                rows.append((m + 1, cat, ch, float(arr[m])))

    # 主食（乾燥穀物・芋はすべて「保存・貯蔵」）
    dem = np.full(12, P * DEMAND["主食"])
    rice_part = dem * (1 - c.bread_share) if c.rice_own else 0
    own = np.minimum(dem, flour / 12 + imo_eq + rice_part)
    add("主食", {"自家産（保存・貯蔵）": own, "常備品": dem - own})

    # 野菜
    dem = np.full(12, P * DEMAND["野菜"])
    f, st, rem = _carry_over(dem, prod["野菜"], c.keep_rate)
    add("野菜", {"自家産（とれたて）": f, "自家産（保存・貯蔵）": st,
                 "常備品": rem * 0.2, "現地で買う": rem * 0.8})

    # 果物
    dem = np.full(12, P * DEMAND["果物"])
    f, st, rem = _carry_over(dem, prod["果物"], c.keep_rate)
    add("果物", {"自家産（とれたて）": f, "自家産（保存・貯蔵）": st, "現地で買う": rem})

    # たんぱく質（大豆は味噌・煮豆にして通年で使う）
    dem = np.full(12, P * DEMAND["たんぱく質"])
    own = np.minimum(dem, prod["大豆"].sum() * SOY_MEAT_EQ / 12)
    rem = dem - own
    add("たんぱく質", {"自家産（保存・貯蔵）": own, "下味冷凍": rem * 0.7, "常備品": rem * 0.3})

    df = pd.DataFrame(rows, columns=["月", "品目", "経路", "kg"])
    return df, summarize(c, df, prod)


KCAL_PER_KG_IMO_TO_RICE = COEF["サツマイモ"].kcal_per_kg / KCAL["主食"]


def summarize(c: Conditions, df: pd.DataFrame, prod: dict) -> dict:
    P = c.persons
    by = df.groupby(["品目", "経路"])["kg"].sum()
    dem = {k: P * v * 12 for k, v in DEMAND.items()}
    own = {k: by.get((k, "自家産（とれたて）"), 0) + by.get((k, "自家産（保存・貯蔵）"), 0) for k in CATEGORIES}
    rate = {k: own[k] / dem[k] for k in CATEGORIES}

    staple_price = PRICE["米"] * (1 - c.bread_share) + PRICE["小麦粉"] * c.bread_share
    buy = (by.get(("主食", "常備品"), 0) * staple_price
           + by.get(("野菜", "現地で買う"), 0) * PRICE["野菜"]
           + by.get(("野菜", "常備品"), 0) * PRICE["冷凍野菜・乾物"]
           + by.get(("果物", "現地で買う"), 0) * PRICE["果物"]
           + by.get(("たんぱく質", "下味冷凍"), 0) * PRICE["下味冷凍"]
           + by.get(("たんぱく質", "常備品"), 0) * PRICE["缶詰"])
    base = (dem["主食"] * staple_price + dem["野菜"] * PRICE["野菜"]
            + dem["果物"] * PRICE["果物"] + dem["たんぱく質"] * PRICE["下味冷凍"])
    k = c.coef
    material = (c.a_wheat * k["小麦"].cost_yen_m2 + c.a_soy * k["大豆"].cost_yen_m2
                + c.a_imo * k["サツマイモ"].cost_yen_m2 + c.a_veg * k["露地野菜"].cost_yen_m2
                + c.house_m2 * k["ハウス野菜"].cost_yen_m2)
    labor = (c.a_wheat * k["小麦"].labor_h_m2 + c.a_soy * k["大豆"].labor_h_m2
             + c.a_imo * k["サツマイモ"].labor_h_m2 + c.a_veg * k["露地野菜"].labor_h_m2
             + c.house_m2 * k["ハウス野菜"].labor_h_m2 + 20)  # 果樹の手入れ・収穫 20時間
    own_kcal = (own["主食"] * KCAL["主食"] + own["野菜"] * KCAL["野菜"] + own["果物"] * KCAL["果物"]
                + own["たんぱく質"] / SOY_MEAT_EQ * k["大豆"].kcal_per_kg)
    # 電気がなくても傷まない乾燥備蓄（小麦粉・大豆・芋）の年平均在庫で、何日分のカロリーになるか
    dry_kcal = (prod["小麦"].sum() * 0.9 * k["小麦"].kcal_per_kg
                + prod["大豆"].sum() * k["大豆"].kcal_per_kg
                + prod["サツマイモ"].sum() * 0.9 * k["サツマイモ"].kcal_per_kg * 5 / 12)
    return dict(
        demand=dem, own=own, rate=rate,
        weight_rate=sum(own.values()) / sum(dem.values()),
        kcal_rate=own_kcal / (P * KCAL_PER_DAY * 365),
        buy=buy, base=base, material=material, net=base - buy - material, labor_h=labor,
        dry_days=0.5 * dry_kcal / (P * KCAL_PER_DAY),
        veg_surplus=max(0.0, prod["野菜"].sum() - own["野菜"]),
        kcal_per_m2=kcal_per_m2(c),
        double_crop=sowing_tradeoff(c),
    )


def kcal_per_m2(c: Conditions) -> dict[str, float]:
    k = c.coef
    return {
        "小麦→大豆": k["小麦"].yield_kg_m2 * k["小麦"].kcal_per_kg + k["大豆"].yield_kg_m2 * k["大豆"].kcal_per_kg,
        "小麦→サツマイモ": k["小麦"].yield_kg_m2 * k["小麦"].kcal_per_kg
        + k["サツマイモ"].yield_kg_m2 * k["サツマイモ"].kcal_per_kg,
        "露地野菜": k["露地野菜"].yield_kg_m2 * k["露地野菜"].kcal_per_kg,
    }


def sowing_tradeoff(c: Conditions, peak: float = 0.90, decay_per_day: float = 0.005,
                    target_plants: int = 200, tkw_g: float = 40.0) -> dict | None:
    """二毛作の季節制約：夏作の収穫（10月中下旬）と小麦の最適播種日（10/20頃）がぶつかる。
    播種が11/5にずれた場合の、発芽率と必要な種子量（g/㎡）を、ホームの播種モデルと同じ式で出す。"""
    if c.a_wheat <= 0 or (c.a_soy + c.a_imo) <= 0:
        return None
    delay = 16  # 10/20 → 11/05
    g0, g1 = peak, max(0.3, peak - decay_per_day * delay)
    seed = lambda g: target_plants * tkw_g / 1000 / g  # noqa: E731
    return dict(delay_days=delay, germ_opt=g0, germ_late=g1,
                seed_opt_g_m2=seed(g0), seed_late_g_m2=seed(g1),
                seed_late_total_kg=seed(g1) * c.a_wheat / 1000)


def compare_presets(base: Conditions) -> pd.DataFrame:
    """プリセット4案を同じ条件で比べる。"""
    out = []
    for name, (soy, imo) in PRESETS.items():
        _, s = simulate(replace(base, a_soy=soy, a_imo=imo))
        out.append({
            "案": name,
            "重量の自給率": s["weight_rate"], "カロリー自給率": s["kcal_rate"],
            "主食": s["rate"]["主食"], "野菜": s["rate"]["野菜"], "たんぱく質": s["rate"]["たんぱく質"],
            "停電でも食べられる備蓄(日)": s["dry_days"], "野菜の余り(kg/年)": s["veg_surplus"],
            "全部買う場合との差(円/年)": s["net"], "作業時間(時間/年)": s["labor_h"],
        })
    return pd.DataFrame(out)


# ──────────────── 停電・断水（かまど・石窯） ────────────────
WATER_L_PER_PERSON = 3.0      # 飲料・調理（1人1日3Lの目安）
WOOD_COOK_KG = 3.0            # かまど炊飯・煮炊き（1日・世帯）
WOOD_PER_L_BOIL = 0.25        # 雨水を煮沸する薪（kg/L）
WOOD_OVEN_BAKE = 15.0         # 小型石窯1回の焼成（予熱込み）
OVEN_EVERY_DAYS = 4


def outage(c: Conditions, summary: dict, *, days: int, month: int, tank_l: float,
           freezer_full: bool, rice_kg: float, jobi_days: float, roof_m2: float | None = None
           ) -> tuple[pd.DataFrame, dict]:
    """停電・断水が days 日続いたときの、食べ物・水・薪を日ごとに追う。"""
    P = c.persons
    roof = c.house_m2 if roof_m2 is None else roof_m2
    rain_per_day = roof * RAIN_MM[month - 1] / 30 * 0.8          # 1mm × 1㎡ = 1L。集水効率80%
    need = WATER_L_PER_PERSON * P
    frozen_days = 2 if freezer_full else 1                       # 満杯で約48時間、半分で約24時間
    rice_days = rice_kg * KCAL["主食"] / (P * KCAL_PER_DAY)
    food_days = frozen_days + summary["dry_days"] + rice_days + jobi_days
    bake = c.bread_share > 0 and summary["own"]["主食"] > 0

    water, wood, rows, short_day = tank_l, 0.0, [], None
    for d in range(1, days + 1):
        water = min(tank_l, water + rain_per_day) - need
        if water < 0 and short_day is None:
            short_day = d
        boil = min(need, rain_per_day + max(water, 0))  # 雨水由来の飲み水は煮沸する前提
        today_wood = WOOD_COOK_KG + boil * WOOD_PER_L_BOIL
        if bake and d % OVEN_EVERY_DAYS == 1:
            today_wood += WOOD_OVEN_BAKE
        wood += today_wood
        if d <= frozen_days:
            food = "下味冷凍を焼き切る（かまど）"
        elif d <= frozen_days + summary["dry_days"]:
            food = "自家産の小麦（石窯パン）・大豆・芋"
        elif d <= frozen_days + summary["dry_days"] + rice_days:
            food = "備蓄米（かまど炊飯）"
        elif d <= food_days:
            food = "常備品（缶詰・乾物）"
        else:
            food = "不足"
        rows.append((d, food, max(water, 0.0), today_wood, wood))
        water = max(water, 0.0)
    df = pd.DataFrame(rows, columns=["日", "主な食べ物", "水の残り(L)", "その日の薪(kg)", "薪の累計(kg)"])
    return df, dict(rain_per_day=rain_per_day, need_per_day=need, food_days=food_days,
                    water_short_day=short_day, wood_total=wood, frozen_days=frozen_days)


# 薪の自給（栗の剪定枝・改植材）。乾燥に1年かかるので「今年切った分は来年の備え」
def firewood_supply(kuri_trees: int = 5, prune_kg_per_tree: float = 15, replant_trees: int = 0,
                    kg_per_old_tree: float = 300) -> float:
    return kuri_trees * prune_kg_per_tree + replant_trees * kg_per_old_tree


# ──────────────── 実測で係数を置き換える（探究フィールドワーク） ────────────────
MEASURE_COLS = ["日付", "作物", "区画面積_m2", "収量_kg", "測定者記号", "備考"]


def measurement_template() -> pd.DataFrame:
    """フィールドワーク用の記録テンプレート（架空の例。氏名は書かず、記号で記録する）。"""
    return pd.DataFrame([
        ["2027-06-05", "小麦", 10, 2.6, "A", "例：鳥よけネットあり"],
        ["2027-10-20", "大豆", 10, 1.7, "B", "例：乾燥後の重さ"],
        ["2027-10-20", "サツマイモ", 5, 11.0, "C", "例：つるを除いた重さ"],
    ], columns=MEASURE_COLS)


def coef_from_measurements(df: pd.DataFrame) -> dict[str, Coef]:
    """記録から作物ごとの収量（kg/㎡）を出し、初期値の係数を置き換える。"""
    coef = dict(COEF)
    d = df.copy()
    d["区画面積_m2"] = pd.to_numeric(d["区画面積_m2"], errors="coerce")
    d["収量_kg"] = pd.to_numeric(d["収量_kg"], errors="coerce")
    d = d.dropna(subset=["区画面積_m2", "収量_kg"])
    d = d[d["区画面積_m2"] > 0]
    for crop, g in d.groupby("作物"):
        if crop in coef:
            coef[crop] = replace(coef[crop], yield_kg_m2=float(g["収量_kg"].sum() / g["区画面積_m2"].sum()))
    return coef


# ──────────────── 家計簿・収入構造との連動 ────────────────
KAKEIBO_COLS = ["日付", "品目", "数量", "単位", "単価(円)"]
_TO_KAKEIBO = {"小麦": "小麦", "大豆": "大豆", "サツマイモ": "芋", "野菜": "野菜", "果物": "果物"}


def plan_to_kakeibo(c: Conditions, year: int) -> pd.DataFrame:
    """生産の計画値を、自給家計簿の「収穫」と同じ列で返す（毎月15日付）。"""
    prod = production(c)
    price = {"小麦": c.coef["小麦"].price_yen_kg, "大豆": c.coef["大豆"].price_yen_kg,
             "サツマイモ": c.coef["サツマイモ"].price_yen_kg, "野菜": PRICE["野菜"], "果物": PRICE["果物"]}
    rows = [(date(year, m + 1, 15), _TO_KAKEIBO[k], round(float(v[m]), 1), "kg", price[k])
            for k, v in prod.items() for m in range(12) if v[m] > 0.05]
    return pd.DataFrame(rows, columns=KAKEIBO_COLS)


def income_link(summary: dict, years_to_reach: int = 3) -> dict:
    """収入構造の「C 自給（削減額）」に渡す値。移住から years_to_reach 年で上限に達する想定。"""
    cap = int(max(0, round(summary["net"], -3)))
    return {"saving_cap": cap, "saving_step": int(round(cap / years_to_reach, -3))}


# ───────────────────────── 自己チェック ─────────────────────────
if __name__ == "__main__":
    base = Conditions(stage=1.0)
    table = compare_presets(base)
    pd.set_option("display.width", 200)
    print(table.round(2).to_string(index=False))

    _, sA = simulate(replace(base, a_soy=70, a_imo=0))
    _, sB = simulate(replace(base, a_soy=0, a_imo=0))
    _, sC = simulate(replace(base, a_soy=0, a_imo=70))
    assert 0 <= sA["weight_rate"] <= 1 and 0 <= sA["kcal_rate"] <= 1
    assert sA["rate"]["たんぱく質"] > sB["rate"]["たんぱく質"], "大豆があるとたんぱく質の自給率が上がる"
    assert sC["kcal_rate"] > sB["kcal_rate"], "芋はカロリーが稼げる"
    assert sB["rate"]["野菜"] >= sA["rate"]["野菜"], "野菜中心なら野菜の自給率は下がらない"
    assert sB["veg_surplus"] > sA["veg_surplus"], "野菜中心は余りが増える"
    df, s = simulate(base)
    for cat in CATEGORIES:  # 経路の合計は必要量に一致する
        assert abs(df[df["品目"] == cat]["kg"].sum() - s["demand"][cat]) < 1e-6, cat
    o, so = outage(base, sA, days=7, month=9, tank_l=200, freezer_full=True, rice_kg=10, jobi_days=3)
    assert len(o) == 7 and so["wood_total"] > 0
    k = plan_to_kakeibo(base, 2027)
    assert list(k.columns) == KAKEIBO_COLS and set(k["品目"]) <= {"小麦", "大豆", "芋", "野菜", "果物"}
    m = coef_from_measurements(measurement_template())
    assert abs(m["小麦"].yield_kg_m2 - 0.26) < 1e-9
    print("\nOK: 自己チェックを通過しました")

"""
jikyu_lab.py ─ 自給と防災の畑シミュレーター（計算部）

ページ pages/15_自給シミュレーター.py から呼び出します。単体で `python jikyu_lab.py` を
実行すると、プリセット5案の比較表・1年備蓄の計画・自己チェックを表示します。

骨格はリポジトリ共通の3段構え：
  ① 計算する … 畑の配分（二毛作・3区画輪作）から、月ごとの自給量・不足分の調達経路・費用を出す
  ② 可視化する … ページ側で plotly に渡す縦長（long）形式の DataFrame を返す
  ③ 判断する … 二毛作の季節制約・停電断水時の持ちこたえ日数・1年備蓄の成立条件など、判断材料を返す

ピボット資料「食糧保存プログラム」（同心円の備蓄計画）との対応:
  0  一年分の備蓄・回転率・今買う   → stock_plan()（保存期間で「回せる量」を判定）, purchase_pace()（揃え方とブルウィップ）
  1  有事最優先（栄養補給剤）       → 計算しない。PREP_CHECKLIST に注意書きだけ置く（量は医師・薬剤師に相談）
  2  必需食料品（玄小麦・大豆・芋…） → stock_plan() の「② 必需食料品」。畑の生産 production() とつなぐ
     輪作❶ 芋→豆→小麦               → Conditions.a_rot（3区画輪作）, rensaku（連作による減収）
     輪作❷ 野菜の四季リレー           → VEG_RELAY, veg_gap_months()（端境期）
  3  第三の円（乾燥品・調味料・塩）  → stock_plan() の「③ 第三の円」, AW_TABLE（水分活性で保存の原理を説明）
  A  エネルギー（薪ストーブ・木炭）  → outage(heating=, charcoal_kg=, wood_stock_kg=)
  B  水（最低2週間）                → water_target(), outage()
  C〜F 雑貨・足・猟と釣り・薬品     → PREP_CHECKLIST（法令・安全の注意つき）

不確かさ（天候・鳥害）の扱い:
  - staple_risk()     … 収量を対数正規でばらつかせ、主食・乾燥備蓄が目標に届く確率をモンテカルロで出す
  - yield_posterior() … 実測値で収量の事前分布をベイズ更新（対数正規・共役）。探究フィールドワークの記録が効く

連動するデータ構造:
  - plan_to_kakeibo() … 自給家計簿の「収穫」と同じ列（日付・品目・数量・単位・単価(円)）で計画値を返す
  - income_link()     … 収入構造シミュレーターの「C 自給」に渡す削減額（saving_step / saving_cap）

数値はすべて目安の初期値です。実測CSV（coef_from_measurements / yield_posterior）で自分の畑の値に置き換えていく前提です。
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
# 年ごとの収量のばらつき（変動係数）。天候・鳥害・獣害込みの目安。実測が増えたら yield_posterior で縮める
YIELD_CV = {"小麦": 0.35, "大豆": 0.30, "サツマイモ": 0.25, "露地野菜": 0.25, "ハウス野菜": 0.15}

# 1人1か月の必要量（kg）と単価
DEMAND = {"主食": 5.0, "野菜": 9.0, "果物": 4.5, "たんぱく質": 3.0}
KCAL = {"主食": 3420, "野菜": 300, "果物": 600, "たんぱく質": 2000}  # 主食は米換算、たんぱく質は肉換算
PRICE = {"米": 750, "小麦粉": 450, "野菜": 450, "冷凍野菜・乾物": 550, "果物": 700,
         "下味冷凍": 1400, "缶詰": 1500}
KCAL_PER_DAY = 2000
SOY_MEAT_EQ = 1.7  # 乾燥大豆1kg ≒ 肉1.7kg分のたんぱく質（目安）
SEED_G_M2 = 10     # 小麦の播種量（条まき）

# 輪作の効果（目安）。大豆の根粒の窒素が次の小麦に効き、肥料が減り収量が少し上がる
ROT_WHEAT_BONUS = 1.10
ROT_FERT_SAVING = 0.30

CHANNELS = ["自家産（とれたて）", "自家産（保存・貯蔵）", "下味冷凍", "常備品", "現地で買う"]
CATEGORIES = list(DEMAND)

STAGES = {"現在：隔週帰省で管理": 0.4, "移住1年目": 0.7, "移住3年目以降": 1.0}

PRESETS: dict[str, tuple[float, float, float]] = {  # (小麦→大豆, 小麦→サツマイモ, 3区画輪作) の面積
    "A 二毛作主体（小麦→大豆 70㎡）": (70, 0, 0),
    "B 野菜中心（小麦なし）": (0, 0, 0),
    "C 小麦→サツマイモ 70㎡": (0, 70, 0),
    "D 折衷（小麦→大豆 50㎡・小麦→サツマイモ 20㎡）": (50, 20, 0),
    "E 輪作❶（芋→大豆→小麦の3区画 各24㎡）": (0, 0, 72),
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
    a_soy: float = 70           # 小麦→大豆の面積（毎年同じ区画で二毛作）
    a_imo: float = 0            # 小麦→サツマイモの面積（毎年同じ区画で二毛作）
    a_rot: float = 0            # 3区画輪作（1年目 芋 → 2年目 大豆→小麦まき → 3年目 小麦収穫）の面積
    rensaku: float = 0.10       # 同じ区画で毎年同じ作物を作ることによる減収（目安）
    coef: dict[str, Coef] = field(default_factory=lambda: dict(COEF))

    @property
    def a_wheat(self) -> float:
        """その年に小麦を収穫する面積。輪作区は3区画のうち1区画。"""
        return self.a_soy + self.a_imo + self.a_rot / 3

    @property
    def a_crop(self) -> float:
        """穀物・豆・芋に使う畑の面積（輪作区は全体）。"""
        return self.a_soy + self.a_imo + self.a_rot

    @property
    def a_veg(self) -> float:
        return max(0.0, FIELD_M2 - self.a_crop)


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


def _field_crops(c: Conditions, yw, ys, yi):
    """小麦・大豆・サツマイモの年間収量（kg）。yw/ys/yi はスカラーでも配列（モンテカルロ）でもよい。"""
    s, pen = c.stage, 1 - c.rensaku
    third = c.a_rot / 3
    wheat = np.maximum(0.0, ((c.a_soy + c.a_imo) * pen + third * ROT_WHEAT_BONUS) * yw * s
                       - c.a_wheat * SEED_G_M2 / 1000)
    soy = (c.a_soy * pen + third) * ys * s
    imo = (c.a_imo * pen + third) * yi * s
    return wheat, soy, imo


def production(c: Conditions) -> dict[str, np.ndarray]:
    """月ごとの生産量（kg）。小麦は6月、大豆・サツマイモは10月に収穫。"""
    k, s = c.coef, c.stage
    w, so, im = _field_crops(c, k["小麦"].yield_kg_m2, k["大豆"].yield_kg_m2, k["サツマイモ"].yield_kg_m2)
    z = np.zeros(12)
    wheat, soy, imo = z.copy(), z.copy(), z.copy()
    wheat[5], soy[9], imo[9] = float(w), float(so), float(im)
    veg = (c.a_veg * k["露地野菜"].yield_kg_m2 * s * VEG_OPEN
           + c.house_m2 * k["ハウス野菜"].yield_kg_m2 * s * VEG_HOUSE)
    return {"小麦": wheat, "大豆": soy, "サツマイモ": imo, "野菜": veg, "果物": fruit_production(c)}


def fruit_production(c: Conditions) -> np.ndarray:
    s = c.stage
    return (40 * max(s, 0.7) * KAKI + 2 * 8 * s * FIG
            + 5 * 5 * c.kuri_vigor * max(s, 0.6) * KURI)


IMO_MONTHS = (9, 10, 11, 0, 1)  # サツマイモは10〜2月に食べる


def simulate(c: Conditions) -> tuple[pd.DataFrame, dict]:
    """月×品目×調達経路の量（kg）を縦長の表で返し、年間の要約を dict で返す。"""
    P = c.persons
    prod = production(c)
    flour = prod["小麦"].sum() * 0.9                 # 製粉歩留まり90%。通年で少しずつ使う
    imo_eq = np.zeros(12)                             # サツマイモ（米換算）
    for m in IMO_MONTHS:
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
    third = c.a_rot / 3
    material = ((c.a_soy + c.a_imo + third * (1 - ROT_FERT_SAVING)) * k["小麦"].cost_yen_m2
                + (c.a_soy + third) * k["大豆"].cost_yen_m2
                + (c.a_imo + third) * k["サツマイモ"].cost_yen_m2 + c.a_veg * k["露地野菜"].cost_yen_m2
                + c.house_m2 * k["ハウス野菜"].cost_yen_m2)
    labor = (c.a_wheat * k["小麦"].labor_h_m2 + (c.a_soy + third) * k["大豆"].labor_h_m2
             + (c.a_imo + third) * k["サツマイモ"].labor_h_m2 + c.a_veg * k["露地野菜"].labor_h_m2
             + c.house_m2 * k["ハウス野菜"].labor_h_m2 + 20)  # 果樹の手入れ・収穫 20時間
    own_kcal = (own["主食"] * KCAL["主食"] + own["野菜"] * KCAL["野菜"] + own["果物"] * KCAL["果物"]
                + own["たんぱく質"] / SOY_MEAT_EQ * k["大豆"].kcal_per_kg)
    dry_kcal = _dry_kcal(prod["小麦"].sum(), prod["大豆"].sum(), prod["サツマイモ"].sum(), k)
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


def _dry_kcal(wheat_kg, soy_kg, imo_kg, k: dict[str, Coef]):
    """電気がなくても傷まない乾燥備蓄（小麦粉・大豆・芋）の年平均在庫のカロリー。芋は5か月で食べ切る。"""
    return (wheat_kg * 0.9 * k["小麦"].kcal_per_kg + soy_kg * k["大豆"].kcal_per_kg
            + imo_kg * 0.9 * k["サツマイモ"].kcal_per_kg * 5 / 12)


def kcal_per_m2(c: Conditions) -> dict[str, float]:
    k = c.coef
    w, s, i = k["小麦"].yield_kg_m2, k["大豆"].yield_kg_m2, k["サツマイモ"].yield_kg_m2
    pen = 1 - c.rensaku
    return {
        "小麦→大豆": pen * (w * k["小麦"].kcal_per_kg + s * k["大豆"].kcal_per_kg),
        "小麦→サツマイモ": pen * (w * k["小麦"].kcal_per_kg + i * k["サツマイモ"].kcal_per_kg),
        "輪作❶（3区画の平均）": (w * ROT_WHEAT_BONUS * k["小麦"].kcal_per_kg + s * k["大豆"].kcal_per_kg
                          + i * k["サツマイモ"].kcal_per_kg) / 3,
        "露地野菜": k["露地野菜"].yield_kg_m2 * k["露地野菜"].kcal_per_kg,
    }


def sowing_tradeoff(c: Conditions, peak: float = 0.90, decay_per_day: float = 0.005,
                    target_plants: int = 200, tkw_g: float = 40.0) -> dict | None:
    """二毛作の季節制約：夏作の収穫（10月中下旬）と小麦の最適播種日（10/20頃）がぶつかる。
    播種が11/5にずれた場合の、発芽率と必要な種子量（g/㎡）を、ホームの播種モデルと同じ式で出す。
    輪作区も「大豆のあとに小麦」をまく1区画だけはぶつかる。"""
    late_area = c.a_soy + c.a_imo + c.a_rot / 3
    if late_area <= 0:
        return None
    delay = 16  # 10/20 → 11/05
    g0, g1 = peak, max(0.3, peak - decay_per_day * delay)
    seed = lambda g: target_plants * tkw_g / 1000 / g  # noqa: E731
    return dict(delay_days=delay, germ_opt=g0, germ_late=g1, late_area=late_area,
                seed_opt_g_m2=seed(g0), seed_late_g_m2=seed(g1),
                seed_late_total_kg=seed(g1) * late_area / 1000)


def compare_presets(base: Conditions) -> pd.DataFrame:
    """プリセット5案を同じ条件で比べる。"""
    out = []
    for name, (soy, imo, rot) in PRESETS.items():
        _, s = simulate(replace(base, a_soy=soy, a_imo=imo, a_rot=rot))
        out.append({
            "案": name,
            "重量の自給率": s["weight_rate"], "カロリー自給率": s["kcal_rate"],
            "主食": s["rate"]["主食"], "野菜": s["rate"]["野菜"], "たんぱく質": s["rate"]["たんぱく質"],
            "停電でも食べられる備蓄(日)": s["dry_days"], "野菜の余り(kg/年)": s["veg_surplus"],
            "全部買う場合との差(円/年)": s["net"], "作業時間(時間/年)": s["labor_h"],
        })
    return pd.DataFrame(out)


# ──────────────── 輪作❷ 野菜の四季リレーと端境期 ────────────────
VEG_RELAY = pd.DataFrame([
    ["春作", "アブラナ科（キャベツ・ブロッコリー・小松菜）", "2〜3月まき・植え → 5〜6月どり", "根こぶ病を避け、同じ科を続けない"],
    ["春夏作", "ウリ科・ナス科（きゅうり・トマト・なす）", "4〜5月植え → 6〜9月どり", "ナス科は3〜4年あける"],
    ["秋冬作", "ほうれん草・白菜・キャベツ・ねぎ", "8〜9月まき → 11〜2月どり", "寒締めで糖度が上がる（ハウスと組み合わせ）"],
    ["冬春作", "玉ねぎ・ねぎ（ヒガンバナ科）", "11月植え → 5〜6月どり", "玉ねぎは吊るして数か月もつ＝端境期の備え"],
], columns=["リレー", "主な作物（科）", "時期の目安", "連作・保存の要点"])


def veg_gap_months(df: pd.DataFrame) -> list[int]:
    """自家産（とれたて＋保存）で野菜の必要量に届かない月＝端境期。"""
    v = df[df["品目"] == "野菜"].pivot_table(index="月", columns="経路", values="kg", aggfunc="sum").fillna(0)
    own = v.get("自家産（とれたて）", 0) + v.get("自家産（保存・貯蔵）", 0)
    total = v.sum(axis=1)
    return [int(m) for m in v.index if own[m] < total[m] * 0.95]


# ──────────────── 0〜3 同心円の1年備蓄（食糧保存プログラム） ────────────────
@dataclass(frozen=True)
class StockItem:
    name: str
    circle: str
    kg_py: float        # 1人1年の目安量（kg）
    shelf_m: float      # 常温・密閉・冷暗所で品質を保てる目安（か月）。999 は事実上無期限
    form: str           # 保存の形と、長くもたせる工夫


def stock_items(c: Conditions) -> list[StockItem]:
    staple = DEMAND["主食"] * 12  # 1人1年 60kg（米換算）
    return [
        StockItem("玄小麦（パン用・粒のまま）", "② 必需食料品", staple * c.bread_share / 0.9, 24,
                  "粒で保存し、使う分だけ挽く（全粒粉にすると約3か月で油が酸化）→ 挽臼・製粉ミルが要る"),
        StockItem("玄米", "② 必需食料品", staple * (1 - c.bread_share) / 0.9, 12,
                  "玄米で保存し、精米器で必要量だけ。夏は虫が出やすいので低温・密閉"),
        StockItem("大豆（乾燥豆）", "② 必需食料品", 10, 24, "乾燥豆のまま。味噌に仕込めば発酵で保存性と味が上がる"),
        StockItem("サツマイモ・ジャガイモ", "② 必需食料品", 20, 4,
                  "サツマイモはキュアリング後13〜15℃。生のままでは1年もたない→干し芋で延ばす"),
        StockItem("粉ミルク・スキムミルク", "② 必需食料品", 3, 12, "未開封・冷暗所。開封後は早めに使う"),
        StockItem("乾燥卵（または鶏卵の回転）", "② 必需食料品", 1, 12, "国内では入手しにくい。採卵鶏を飼うなら「生き物で回す」"),
        StockItem("発芽用種子（緑豆・大豆・小麦）", "② 必需食料品", 2, 12,
                  "乾燥豆にほぼないビタミンCを、発芽で作れる。古いと発芽率が下がる"),
        StockItem("乾燥野菜（切り干し大根など）", "③ 第三の円", 3, 6, "天日乾燥で水分活性を下げる。湿気で戻るので密閉"),
        StockItem("干し柿・乾燥果物", "③ 第三の円", 2, 3, "常温は短い。冷凍すれば半年以上"),
        StockItem("味噌・醤油・香辛料", "③ 第三の円", 6, 12, "塩分と発酵で保存。自家産大豆で味噌を仕込める"),
        StockItem("ハチミツ", "③ 第三の円", 2, 24, "糖度が高く腐りにくい（1歳未満の乳児には与えない）"),
        StockItem("塩", "③ 第三の円", 3.6, 999, "腐らない。吸湿だけ注意。塩蔵・味噌づくりにも使う"),
    ]


def _own_supply(c: Conditions, prod: dict, summary: dict) -> dict[str, float]:
    """畑から1年に供給できる量（kg）。"""
    kaki_kg = 40 * max(c.stage, 0.7)
    return {
        "玄小麦（パン用・粒のまま）": prod["小麦"].sum(),
        "玄米": (DEMAND["主食"] * 12 * (1 - c.bread_share) / 0.9 * c.persons) if c.rice_own else 0.0,
        "大豆（乾燥豆）": prod["大豆"].sum(),
        "サツマイモ・ジャガイモ": prod["サツマイモ"].sum(),
        "乾燥野菜（切り干し大根など）": summary["veg_surplus"] * 0.10,   # 乾燥で重さは約1/10
        "干し柿・乾燥果物": kaki_kg * 0.5 * 0.30,                         # 半分を干し柿に、乾燥で約3割
    }


def stock_plan(c: Conditions, goal_months: float = 12) -> pd.DataFrame:
    """同心円の備蓄を「目標 → 回せる上限 → 畑から → 買い足す」に分ける。

    回転率の考え方：普段どおりの速さで古いものから食べると、備蓄の一番古い分は goal_months か月待つ。
    保存の目安 shelf_m がそれより短い品目は、そのまま1年分を持つと傷む。だから
      持てる上限 = 1人1年の量 × 人数 × min(goal, shelf) / 12
    を超える分は「保存の形を変える」か「量を抑える」しかない。
    """
    _, s = simulate(c)
    prod = production(c)
    own_all = _own_supply(c, prod, s)
    P = c.persons
    rows = []
    for it in stock_items(c):
        goal = it.kg_py * P * goal_months / 12
        hold_m = min(goal_months, it.shelf_m)
        hold = it.kg_py * P * hold_m / 12
        own = min(hold, own_all.get(it.name, 0.0))
        if it.shelf_m >= goal_months:
            verdict = "◎ そのまま回せる"
        else:
            verdict = f"△ {it.shelf_m:.0f}か月で入れ替え／形を変える"
        rows.append(dict(円=it.circle, 品目=it.name, 目標_kg=goal, 回せる上限_kg=hold, 畑から_kg=own,
                         買い足す_kg=max(0.0, hold - own), 保存の目安_月=it.shelf_m if it.shelf_m < 999 else np.inf,
                         判定=verdict, 保存の工夫=it.form))
    return pd.DataFrame(rows)


def purchase_pace(plan: pd.DataFrame, c: Conditions, paces_months=(0.25, 1, 3, 6, 12)) -> pd.DataFrame:
    """「今買う」をどの速さで実行するか。ふだんの月の購入量に対して何倍になるか（ブルウィップの入口）。

    1世帯の上乗せは小さくても、品薄報道のあと多くの世帯が同じ週に揃えると、店・卸・メーカーへと
    発注の振れが増幅する（Lee, Padmanabhan & Whang 1997）。平時に少しずつ揃えれば増幅は起きにくい。"""
    normal_month = sum(it.kg_py for it in stock_items(c)) * c.persons / 12
    gap = plan["買い足す_kg"].sum()
    return pd.DataFrame([dict(揃える期間=(f"{p*4:.0f}週間" if p < 1 else f"{p:.0f}か月"), 月数=p,
                              上乗せ_kg_月=gap / p, ふだんの何倍=(normal_month + gap / p) / normal_month)
                         for p in paces_months])


WATER_L_PER_PERSON = 3.0      # 飲料・調理（1人1日3Lの目安。農林水産省の家庭備蓄ガイドと同じ）


def water_target(persons: int, days: int = 14) -> float:
    """資料の「最低2週間分の調理水・飲料水」。"""
    return WATER_L_PER_PERSON * persons * days


# 水分活性（Aw）で「なぜ乾燥・塩・砂糖・発酵で保存できるか」を説明する（教科書的な目安）
AW_TABLE = pd.DataFrame([
    ["生野菜・肉・魚", 0.98, "ほぼすべての微生物が増える → 冷蔵・冷凍が要る（停電に弱い）"],
    ["味噌", 0.80, "塩分で細菌は止まるが、カビ・酵母は動ける（だから熟成が進む）"],
    ["干し柿・干し芋", 0.70, "多くのカビも止まり始める。湿気を吸うと戻る"],
    ["ハチミツ", 0.60, "微生物はほぼ増えない"],
    ["玄小麦・玄米・乾燥大豆（水分13〜15%）", 0.60, "乾燥させた穀物は年単位でもつ。敵は虫と湿気"],
], columns=["食品", "水分活性の目安", "意味"])
AW_LIMITS = {"多くの細菌": 0.90, "多くの酵母": 0.88, "多くのカビ": 0.80, "耐乾性のカビ": 0.65}

# C〜F と 1 は計算しない。量より「法令・安全」の確認が先
PREP_CHECKLIST = pd.DataFrame([
    ["1 有事最優先", "栄養補給剤（たんぱく質・ビタミン・ミネラル）",
     "食事の代わりにしない。持病・服薬がある人は量を医師・薬剤師に相談。発芽野菜・大豆・干し柿で食事から補う設計を先に"],
    ["A エネルギー", "薪ストーブ・薪の貯蔵、木炭調理器と木炭",
     "屋内の燃焼は一酸化炭素中毒の危険。換気とCO警報器。薪は乾燥に1年（今年切った分は来年の備え）"],
    ["B 水", "最低2週間分の飲料水・調理水、携帯浄水器",
     "飲み水の消毒は「滴数」で覚えず、保健所・自治体の案内と製品表示に従う。迷ったら煮沸"],
    ["C 雑貨", "普段1個なら3個（ファンベルト・ホース・プラグ・タイヤなど）",
     "平時に少しずつ。品薄になってからの買い増しは、それ自体が品薄を深める"],
    ["D 足", "自動車・自転車（燃料・空気入れ・修理キット）",
     "ガソリンは金属製携行缶で。40L（指定数量200Lの1/5）以上の保管は少量危険物として消防への届出が要る"],
    ["E 猟と釣り", "わな・釣り具",
     "わな猟も狩猟免許と狩猟者登録が必要（鳥獣保護管理法）。イノシシの有害捕獲は市町村の許可。川・池は漁業権と遊漁規則を確認"],
    ["F 薬品", "常備薬・救急箱",
     "処方薬の予備は主治医・薬剤師に相談。期限を回す（ローリングストック）"],
], columns=["区分", "資料の項目", "確認すること"])


# ──────────────── 不確かさ（天候・鳥害）とベイズ更新 ────────────────
def yield_posterior(prior_mean: float, prior_cv: float, obs_kg_m2, obs_cv: float = 0.30) -> dict:
    """収量の対数を正規分布とみなし、事前分布（目安の値）を実測で更新する（正規-正規の共役）。

    obs_cv は「同じ年でも区画ごとにこれくらいばらつく」の目安。実測が増えるほど事前の影響は小さくなる。"""
    s0 = np.sqrt(np.log(1 + prior_cv ** 2))
    mu0 = np.log(prior_mean) - s0 ** 2 / 2
    so = np.sqrt(np.log(1 + obs_cv ** 2))
    y = np.log(np.asarray([v for v in obs_kg_m2 if v and v > 0], dtype=float))
    n = len(y)
    prec = 1 / s0 ** 2 + n / so ** 2
    mu_n = (mu0 / s0 ** 2 + y.sum() / so ** 2) / prec
    sd_n = np.sqrt(1 / prec)
    # 来年の予測：平均の不確かさ ＋ 年ごとのばらつき（事前の cv を年変動とみなす）
    pred_s = np.sqrt(sd_n ** 2 + s0 ** 2) if n else s0
    mean = float(np.exp(mu_n + sd_n ** 2 / 2))
    return dict(n=n, mean=mean, lo90=float(np.exp(mu_n - 1.645 * sd_n)), hi90=float(np.exp(mu_n + 1.645 * sd_n)),
                pred_cv=float(np.sqrt(np.exp(pred_s ** 2) - 1)))


def posterior_from_measurements(df: pd.DataFrame) -> dict[str, dict]:
    """実測CSV（MEASURE_COLS）から作物ごとの事後分布を返す。"""
    d = df.copy()
    d["区画面積_m2"] = pd.to_numeric(d["区画面積_m2"], errors="coerce")
    d["収量_kg"] = pd.to_numeric(d["収量_kg"], errors="coerce")
    d = d.dropna(subset=["区画面積_m2", "収量_kg"])
    d = d[d["区画面積_m2"] > 0]
    out = {}
    for crop, g in d.groupby("作物"):
        if crop in COEF:
            out[crop] = yield_posterior(COEF[crop].yield_kg_m2, YIELD_CV[crop], g["収量_kg"] / g["区画面積_m2"])
    return out


def staple_risk(c: Conditions, n: int = 4000, seed: int = 0, post: dict[str, dict] | None = None) -> dict:
    """収量を対数正規でばらつかせ、主食の自給率・乾燥備蓄の日数・パン用小麦1年分の達成確率を出す。"""
    rng = np.random.default_rng(seed)
    post = post or {}

    def draw(crop):
        m = post.get(crop, {}).get("mean", c.coef[crop].yield_kg_m2)
        cv = post.get(crop, {}).get("pred_cv", YIELD_CV[crop])
        s = np.sqrt(np.log(1 + cv ** 2))
        return rng.lognormal(np.log(m) - s ** 2 / 2, s, n)

    w, so, im = _field_crops(c, draw("小麦"), draw("大豆"), draw("サツマイモ"))
    P = c.persons
    dem_m = P * DEMAND["主食"]
    imo_eq_m = im * 0.9 / 5 * KCAL_PER_KG_IMO_TO_RICE
    rice_m = dem_m * (1 - c.bread_share) if c.rice_own else 0.0
    base = w * 0.9 / 12 + rice_m
    own = (np.minimum(dem_m, base[:, None] + np.where(np.isin(np.arange(12), IMO_MONTHS), imo_eq_m[:, None], 0))
           .sum(axis=1))
    rate = own / (dem_m * 12)
    dry_days = 0.5 * _dry_kcal(w, so, im, c.coef) / (P * KCAL_PER_DAY)
    wheat_need = DEMAND["主食"] * 12 * c.bread_share / 0.9 * P
    q = lambda a: dict(p10=float(np.quantile(a, 0.1)), p50=float(np.median(a)), p90=float(np.quantile(a, 0.9)))  # noqa: E731
    return dict(
        n=n, rate=rate, dry_days=dry_days, wheat_kg=w,
        rate_q=q(rate), dry_q=q(dry_days), wheat_q=q(w),
        p_bread_year=float((w >= wheat_need).mean()) if wheat_need > 0 else 1.0,
        p_dry_week=float((dry_days >= 7).mean()),
        wheat_need=wheat_need,
        wheat_m2_for_bread=wheat_need / max(1e-9, c.coef["小麦"].yield_kg_m2 * c.stage),
    )


# ──────────────── 停電・断水（かまど・石窯・薪ストーブ） ────────────────
WOOD_COOK_KG = 3.0            # かまど炊飯・煮炊き（1日・世帯）
WOOD_PER_L_BOIL = 0.25        # 雨水を煮沸する薪（kg/L）
WOOD_OVEN_BAKE = 15.0         # 小型石窯1回の焼成（予熱込み）
OVEN_EVERY_DAYS = 4
# 薪ストーブ1台で居間1室を暖める薪（kg/日）の目安
HEAT_WOOD_KG = np.array([12, 12, 8, 3, 0, 0, 0, 0, 0, 2, 5, 10], dtype=float)
CHARCOAL_TO_WOOD = 2.0        # 木炭1kg ≒ 風乾薪2kg分の熱（発熱量の比の目安）


def outage(c: Conditions, summary: dict, *, days: int, month: int, tank_l: float,
           freezer_full: bool, rice_kg: float, jobi_days: float, roof_m2: float | None = None,
           heating: bool = False, charcoal_kg: float = 0.0, wood_stock_kg: float | None = None
           ) -> tuple[pd.DataFrame, dict]:
    """停電・断水が days 日続いたときの、食べ物・水・薪（暖房・木炭込み）を日ごとに追う。"""
    P = c.persons
    roof = c.house_m2 if roof_m2 is None else roof_m2
    rain_per_day = roof * RAIN_MM[month - 1] / 30 * 0.8          # 1mm × 1㎡ = 1L。集水効率80%
    need = WATER_L_PER_PERSON * P
    frozen_days = 2 if freezer_full else 1                       # 満杯で約48時間、半分で約24時間
    rice_days = rice_kg * KCAL["主食"] / (P * KCAL_PER_DAY)
    food_days = frozen_days + summary["dry_days"] + rice_days + jobi_days
    bake = c.bread_share > 0 and summary["own"]["主食"] > 0
    heat = HEAT_WOOD_KG[month - 1] if heating else 0.0

    water, wood, char, rows, short_day = tank_l, 0.0, charcoal_kg, [], None
    stock, wood_out_day = wood_stock_kg, None
    for d in range(1, days + 1):
        water = min(tank_l, water + rain_per_day) - need
        if water < 0 and short_day is None:
            short_day = d
        boil = min(need, rain_per_day + max(water, 0))  # 雨水由来の飲み水は煮沸する前提
        cook = WOOD_COOK_KG + boil * WOOD_PER_L_BOIL
        use_char = min(char, cook / CHARCOAL_TO_WOOD)    # 煮炊きは木炭から先に使う（煙が少ない）
        char -= use_char
        today_wood = cook - use_char * CHARCOAL_TO_WOOD + heat
        if bake and d % OVEN_EVERY_DAYS == 1:
            today_wood += WOOD_OVEN_BAKE
        wood += today_wood
        if stock is not None:
            stock -= today_wood
            if stock < 0 and wood_out_day is None:
                wood_out_day = d
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
        rows.append((d, food, max(water, 0.0), today_wood, wood, heat, char,
                     max(stock, 0.0) if stock is not None else np.nan))
        water = max(water, 0.0)
    df = pd.DataFrame(rows, columns=["日", "主な食べ物", "水の残り(L)", "その日の薪(kg)", "薪の累計(kg)",
                                     "うち暖房(kg)", "木炭の残り(kg)", "薪の残り(kg)"])
    return df, dict(rain_per_day=rain_per_day, need_per_day=need, food_days=food_days,
                    water_short_day=short_day, wood_total=wood, frozen_days=frozen_days,
                    heat_total=heat * days, charcoal_left=char, wood_out_day=wood_out_day)


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
    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 40)
    print(table.round(2).to_string(index=False))

    _, sA = simulate(replace(base, a_soy=70, a_imo=0))
    _, sB = simulate(replace(base, a_soy=0, a_imo=0))
    _, sC = simulate(replace(base, a_soy=0, a_imo=70))
    _, sE = simulate(replace(base, a_soy=0, a_imo=0, a_rot=72))
    assert 0 <= sA["weight_rate"] <= 1 and 0 <= sA["kcal_rate"] <= 1
    assert sA["rate"]["たんぱく質"] > sB["rate"]["たんぱく質"], "大豆があるとたんぱく質の自給率が上がる"
    assert sC["kcal_rate"] > sB["kcal_rate"], "芋はカロリーが稼げる"
    assert sB["rate"]["野菜"] >= sA["rate"]["野菜"], "野菜中心なら野菜の自給率は下がらない"
    assert sB["veg_surplus"] > sA["veg_surplus"], "野菜中心は余りが増える"
    assert sE["rate"]["たんぱく質"] > 0 and sE["rate"]["主食"] > 0, "輪作は主食とたんぱく質を両方まかなう"
    assert sE["double_crop"]["late_area"] < sA["double_crop"]["late_area"], "輪作は播種のぶつかりが小さい"
    _, s0 = simulate(replace(base, rensaku=0.0))
    _, s3 = simulate(replace(base, rensaku=0.3))
    assert s0["rate"]["たんぱく質"] > s3["rate"]["たんぱく質"], "連作の減収が効く"
    df, s = simulate(base)
    for cat in CATEGORIES:  # 経路の合計は必要量に一致する
        assert abs(df[df["品目"] == cat]["kg"].sum() - s["demand"][cat]) < 1e-6, cat

    o, so = outage(base, sA, days=7, month=9, tank_l=200, freezer_full=True, rice_kg=10, jobi_days=3)
    assert len(o) == 7 and so["wood_total"] > 0
    oh, soh = outage(base, sA, days=7, month=1, tank_l=200, freezer_full=True, rice_kg=10, jobi_days=3,
                     heating=True, charcoal_kg=5, wood_stock_kg=50)
    on, son = outage(base, sA, days=7, month=1, tank_l=200, freezer_full=True, rice_kg=10, jobi_days=3)
    assert soh["heat_total"] > 0 and soh["wood_out_day"] is not None, "冬の暖房で薪が尽きる日が出る"

    k = plan_to_kakeibo(base, 2027)
    assert list(k.columns) == KAKEIBO_COLS and set(k["品目"]) <= {"小麦", "大豆", "芋", "野菜", "果物"}
    m = coef_from_measurements(measurement_template())
    assert abs(m["小麦"].yield_kg_m2 - 0.26) < 1e-9

    plan = stock_plan(replace(base, a_soy=0, a_rot=72), goal_months=12)
    print("\n" + plan.drop(columns="保存の工夫").round(1).to_string(index=False))
    assert (plan["回せる上限_kg"] <= plan["目標_kg"] + 1e-9).all()
    assert (plan["買い足す_kg"] >= -1e-9).all()
    imo = plan.set_index("品目").loc["サツマイモ・ジャガイモ"]
    assert imo["回せる上限_kg"] < imo["目標_kg"], "生の芋は1年分を持てない"
    pace = purchase_pace(plan, base)
    print("\n" + pace.round(2).to_string(index=False))
    assert pace["ふだんの何倍"].is_monotonic_decreasing, "ゆっくり揃えるほど振れは小さい"

    post = yield_posterior(0.30, 0.35, [0.26, 0.24])
    assert post["n"] == 2 and 0.24 < post["mean"] < 0.30 and post["pred_cv"] > 0
    r = staple_risk(replace(base, a_soy=0, a_rot=72), n=2000)
    assert 0 <= r["p_bread_year"] <= 1 and r["dry_q"]["p10"] <= r["dry_q"]["p90"]
    print(f"\n輪作E：パン用小麦1年分の達成確率 {r['p_bread_year']:.0%}、乾燥備蓄 中央値 {r['dry_q']['p50']:.0f}日")
    print("端境期（野菜）:", veg_gap_months(df), "／ 2週間の水:", water_target(2), "L")
    print("\nOK: 自己チェックを通過しました")

"""
weeding_lab.py — 学校向けの探究「除草AIロボット・シミュレーター」の計算部品

画面は pages/10_🤖_AIロボット.py（除草のタブ）。`python weeding_lab.py` で自己チェック。
シミュレーター本体は docs/sim/weeding_robot.html（three.js、ブラウザだけで動く）。

問い
  パン用小麦の畑で、AIロボットに除草を任せるとき、「雑草を取り残す損」と「小麦を傷める損」の
  どちらをどれだけ許すかを、自分の畑の条件で決めるには、どう考えればよいか。

骨格（リポジトリ共通）：① 計算する → ② 可視化する → ③ 自分の条件で判断する
  ① 計算する   … AIの見分け（信号検出理論）・雑草による減収（Cousens 1985 の双曲線モデル）・作業時間
  ② 可視化する … ROC曲線・点数の分布・シミュレーターの記録CSVで「人・AI・AI＋人」を比べる（ベイズ）
  ③ 判断する   … 期待収量が最大になるしきい値 τ と、人が確かめる「グレーゾーン」の幅を決める

方針
  - このページも部品も、ロボットを動かさない。ROS2のコードは表示するだけ。
  - 数値（見分けやすさ d・減収の係数・作業の秒数）は教材用の仮置き。作物・雑草・機械で大きく変わる。
  - 実機のレーザーは扱わない（目と火災の危険が大きい）。レーザー除草はシミュレーターの中だけ。
"""
from __future__ import annotations

import io
import math
from collections.abc import Sequence

import numpy as np
import pandas as pd

import tokushi_lab as tl  # ベータ分布の更新はリポジトリ共通の関数を使う

# ============================================================
# シミュレーターと同じ定数（docs/sim/weeding_robot.html の MODEL と一致させる）
# ============================================================
# AIの点数モデル（信号検出理論）
#   z = μ(種類) + ε,  ε ~ N(0, 1)    点数 s = 1 / (1 + e^(−z))   → s ≥ τ なら「雑草」と判定して取る
#   μ(小麦) = −d/2,  μ(広葉の雑草) = +d/2,  μ(イネ科の雑草) = 0（小麦に似ているので中間）
D_DEFAULT = 2.5       # 見分けやすさ d（d′）。大きいほどAIが賢い（仮置き）
GRASS_DEFAULT = 0.4   # 雑草のうちイネ科（スズメノテッポウなど、小麦に似る）の割合

# 取り方（仮置き）
METHODS = {
    #           1本あたりの秒, 株元の雑草を取るとき隣の小麦を傷める確率, 説明
    "ハンド（抜き取り）": (2.6, 0.15, "つかんで根ごと抜く。株元では隣の小麦の根を傷めることがある"),
    "レーザー": (1.25, 0.0, "株元でも正確。目・やけど・乾いた草の火災の危険が大きい（実機は扱わない）"),
}
INROW_SHARE = 0.3     # 雑草のうち、小麦の株元（列の中）に生えている割合
ROBOT_SPEED = 0.2     # ロボットの走る速さ m/s
SWATH = 1.0           # 1回に見る幅 m（畝1本ぶん）
HAND_SEC = 5.0        # 人が手で1本抜く秒数
HUMAN_ACC = 0.92      # 人が見て正しく見分ける確率（イネ科も含めた平均。仮置き）
CHECK_SEC = 3.0       # AIが迷った1本を、人が画面で確かめる秒数

# 雑草による減収（Cousens 1985）：YL = I·N / (1 + I·N / A)
#   N：雑草の本数／㎡、I：雑草が少ないときの1本あたりの減収％、A：雑草が非常に多いときの減収の上限％
COUSENS_I = 1.0       # 仮置き。小麦×スズメノテッポウ等で値は大きく変わる
COUSENS_A = 50.0


def phi(x: float) -> float:
    """標準正規分布の累積分布関数 Φ(x)。scipy を使わず erf で書く（中身が見えるように）。"""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def d_from_difficulty(h: float) -> float:
    """シミュレーターの「見分けにくさ h（0〜1）」→ AIの見分けやすさ d。h=0.5 で d=2.5。"""
    return 4 - 3 * h


def means(d: float) -> dict:
    return {"小麦": -d / 2, "広葉の雑草": d / 2, "イネ科の雑草": 0.0}


def p_flag(kind: str, tau: float, d: float = D_DEFAULT) -> float:
    """その種類の1本が「雑草」と判定される確率 P(s ≥ τ) = 1 − Φ(logit τ − μ)。"""
    return 1 - phi(logit(tau) - means(d)[kind])


# ============================================================
# ① 計算する
# ============================================================
def classify_rates(tau: float, d: float = D_DEFAULT, grass: float = GRASS_DEFAULT) -> dict:
    """AIだけで決めたときの、雑草を取る割合（検出率）と小麦を雑草と読み違える割合。"""
    broad, gr = p_flag("広葉の雑草", tau, d), p_flag("イネ科の雑草", tau, d)
    return {"広葉を取る割合": broad, "イネ科を取る割合": gr,
            "雑草を取る割合": (1 - grass) * broad + grass * gr,
            "小麦を読み違える割合": p_flag("小麦", tau, d)}


def triage_rates(tau_low: float, tau_high: float, d: float = D_DEFAULT, grass: float = GRASS_DEFAULT,
                 acc: float = HUMAN_ACC) -> dict:
    """AI＋人：s ≥ τ_high は取る、s < τ_low は残す、その間（グレーゾーン）は人が確かめる。"""
    lo, hi = sorted((tau_low, tau_high))
    hi_r, lo_r = classify_rates(hi, d, grass), classify_rates(lo, d, grass)
    gray_weed = lo_r["雑草を取る割合"] - hi_r["雑草を取る割合"]
    gray_crop = lo_r["小麦を読み違える割合"] - hi_r["小麦を読み違える割合"]
    return {"雑草を取る割合": hi_r["雑草を取る割合"] + gray_weed * acc,
            "小麦を読み違える割合": hi_r["小麦を読み違える割合"] + gray_crop * (1 - acc),
            "人が見る雑草の割合": gray_weed, "人が見る小麦の割合": gray_crop}


def yield_loss(n_per_m2: float, i: float = COUSENS_I, a: float = COUSENS_A) -> float:
    """Cousens（1985）の双曲線モデル。雑草 N 本／㎡ のときの減収％。"""
    return i * n_per_m2 / (1 + i * n_per_m2 / a)


def field_outcome(removed: float, crop_misread: float, weeds_m2: float, crops_m2: float,
                  method: str = "ハンド（抜き取り）", inrow: float = INROW_SHARE) -> dict:
    """取る割合・読み違いの割合から、残る雑草・傷んだ小麦・期待収量（雑草なしを100）を出す。"""
    _, coll, _ = METHODS[method]
    left = weeds_m2 * (1 - removed)
    # 傷む小麦の本数／㎡ ＝ 読み違えて取った小麦 ＋ 株元の雑草を取るときに巻き込んだ小麦
    hurt_m2 = crops_m2 * crop_misread + weeds_m2 * removed * inrow * coll
    hurt = min(1.0, hurt_m2 / max(crops_m2, 1e-9))
    yl = yield_loss(left)
    return {"残る雑草_本m2": left, "傷んだ小麦の割合": hurt, "雑草による減収_%": yl,
            "期待収量": 100 * (1 - hurt) * (1 - yl / 100)}


def work_time(area_m2: float, weeds_m2: float, crops_m2: float, mode: str, method: str = "ハンド（抜き取り）",
              flagged_share: float = 0.0, checks_per_m2: float = 0.0) -> dict:
    """作業時間（分）。ロボット＝走る＋取る、人＝手で抜く・画面で確かめる。曲がる時間・充電は含まない。"""
    sec, _, _ = METHODS[method]
    if mode == "人の手":
        return {"ロボット_分": 0.0, "人_分": area_m2 * weeds_m2 * HAND_SEC / 60}
    run = area_m2 / SWATH / ROBOT_SPEED
    act = area_m2 * flagged_share * sec
    return {"ロボット_分": (run + act) / 60, "人_分": area_m2 * checks_per_m2 * CHECK_SEC / 60}


def compare_plans(area: float, weeds_m2: float, crops_m2: float, tau: float, band: float,
                  d: float = D_DEFAULT, grass: float = GRASS_DEFAULT, method: str = "ハンド（抜き取り）",
                  acc: float = HUMAN_ACC) -> pd.DataFrame:
    """人の手・AIだけ・AI＋人・何もしない、の4案を同じ条件で比べる。"""
    rows = []
    # 何もしない
    rows.append({"案": "何もしない", **field_outcome(0, 0, weeds_m2, crops_m2, method),
                 "ロボット_分": 0.0, "人_分": 0.0})
    # 人の手（イネ科も見分けられるが、読み違いはある）
    o = field_outcome(acc, 1 - acc, weeds_m2, crops_m2, "レーザー")  # 手は株元でも巻き込みにくいとみなす
    rows.append({"案": "人の手", **o, **work_time(area, weeds_m2, crops_m2, "人の手")})
    # AIだけ
    r = classify_rates(tau, d, grass)
    flag = weeds_m2 * r["雑草を取る割合"] + crops_m2 * r["小麦を読み違える割合"]
    rows.append({"案": "AIだけ", **field_outcome(r["雑草を取る割合"], r["小麦を読み違える割合"],
                                                weeds_m2, crops_m2, method),
                 **work_time(area, weeds_m2, crops_m2, "AI", method, flag)})
    # AI＋人（グレーゾーン τ±band）
    lo, hi = max(0.01, tau - band), min(0.99, tau + band)
    t = triage_rates(lo, hi, d, grass, acc)
    checks = weeds_m2 * t["人が見る雑草の割合"] + crops_m2 * t["人が見る小麦の割合"]
    flag2 = weeds_m2 * t["雑草を取る割合"] + crops_m2 * t["小麦を読み違える割合"]
    rows.append({"案": "AI＋人", **field_outcome(t["雑草を取る割合"], t["小麦を読み違える割合"],
                                                weeds_m2, crops_m2, method),
                 **work_time(area, weeds_m2, crops_m2, "AI", method, flag2, checks)})
    return pd.DataFrame(rows)


# ============================================================
# ② 可視化する
# ============================================================
def roc_curve(d: float = D_DEFAULT, grass: float = GRASS_DEFAULT,
              taus: Sequence[float] = tuple(np.round(np.arange(0.02, 0.99, 0.02), 2))) -> pd.DataFrame:
    rows = []
    for t in taus:
        r = classify_rates(t, d, grass)
        rows.append({"τ": t, "小麦を読み違える割合": r["小麦を読み違える割合"],
                     "雑草を取る割合": r["雑草を取る割合"], "イネ科を取る割合": r["イネ科を取る割合"]})
    return pd.DataFrame(rows)


def score_samples(d: float = D_DEFAULT, n: int = 600, seed: int = 0) -> pd.DataFrame:
    """種類ごとの点数 s の見本（ヒストグラム用）。"""
    rng = np.random.default_rng(seed)
    rows = []
    for kind, mu in means(d).items():
        z = mu + rng.standard_normal(n)
        rows += [{"種類": kind, "点数": float(1 / (1 + math.exp(-v)))} for v in z]
    return pd.DataFrame(rows)


def tau_curve(weeds_m2: float, crops_m2: float, d: float = D_DEFAULT, grass: float = GRASS_DEFAULT,
              method: str = "ハンド（抜き取り）",
              taus: Sequence[float] = tuple(np.round(np.arange(0.05, 0.951, 0.05), 2))) -> pd.DataFrame:
    rows = []
    for t in taus:
        r = classify_rates(t, d, grass)
        o = field_outcome(r["雑草を取る割合"], r["小麦を読み違える割合"], weeds_m2, crops_m2, method)
        rows.append({"τ": t, **o})
    return pd.DataFrame(rows)


def best_tau(weeds_m2: float, crops_m2: float, d: float = D_DEFAULT, grass: float = GRASS_DEFAULT,
             method: str = "ハンド（抜き取り）") -> tuple[float, float]:
    tc = tau_curve(weeds_m2, crops_m2, d, grass, method)
    i = int(tc["期待収量"].idxmax())
    return float(tc.loc[i, "τ"]), float(tc.loc[i, "期待収量"])


CSV_COLS = ["round", "mode", "difficulty", "method", "tau", "seed", "weeds_total", "weeds_removed",
            "crops_total", "crops_damaged", "human_checks", "human_sec", "robot_sec"]

# 架空の記録（畑の番号1で3方式を試した例）。実際は、シミュレーターの「CSVをコピー」を貼る。
# 秒はモデルの時間（人：手で抜く5秒／本・画面で確かめる3秒／本、ロボット：走る60秒＋取る秒×本数）
SAMPLE_CSV = """round,mode,difficulty,method,tau,seed,weeds_total,weeds_removed,crops_total,crops_damaged,human_checks,human_sec,robot_sec
1,人の目,0.5,手,,1,36,27,72,3,30,150,0
2,AIだけ,0.5,ハンド,0.50,1,36,28,72,7,0,0,130
3,AI＋人,0.5,ハンド,0.50,1,36,32,72,4,11,33,136
4,AIだけ,0.5,レーザー,0.50,1,36,29,72,4,0,0,80
5,AI＋人,0.5,レーザー,0.50,1,36,33,72,2,10,30,81
6,人の目,0.8,手,,2,36,22,72,5,27,135,0
7,AI＋人,0.8,レーザー,0.50,2,36,30,72,3,15,45,81
"""
MODES = ["人の目", "AIだけ", "AI＋人"]


def parse_records(text: str) -> pd.DataFrame:
    """CSVの文字列を読み、列と値を確かめる。おかしな行は落とす。"""
    df = pd.read_csv(io.StringIO(text.strip()))
    missing = [c for c in CSV_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"列が足りません：{', '.join(missing)}")
    df = df[CSV_COLS].copy()
    nums = ["difficulty", "tau", "seed", "weeds_total", "weeds_removed", "crops_total", "crops_damaged",
            "human_checks", "human_sec", "robot_sec"]
    for c in nums:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    cnt = ["weeds_total", "weeds_removed", "crops_total", "crops_damaged"]
    df = df.dropna(subset=cnt)
    df = df[(df[cnt] >= 0).all(axis=1)]
    df = df[(df["weeds_removed"] <= df["weeds_total"]) & (df["crops_damaged"] <= df["crops_total"])]
    df["方式"] = df["mode"].astype(str).map(lambda m: next((x for x in MODES[::-1] if x in m), "その他"))
    df = df[df["方式"] != "その他"]
    df["雑草を取った割合"] = df["weeds_removed"] / df["weeds_total"].clip(lower=1)
    df["小麦を傷めた割合"] = df["crops_damaged"] / df["crops_total"].clip(lower=1)
    return df.reset_index(drop=True)


def compare_modes(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("方式").agg(ラウンド=("round", "count"), 雑草=("weeds_total", "sum"),
                              取った=("weeds_removed", "sum"), 小麦=("crops_total", "sum"),
                              傷めた=("crops_damaged", "sum"), 人が見た=("human_checks", "sum"),
                              人の秒=("human_sec", "mean"), ロボの秒=("robot_sec", "mean"))
    g["雑草を取った割合"] = g["取った"] / g["雑草"].clip(lower=1)
    g["小麦を傷めた割合"] = g["傷めた"] / g["小麦"].clip(lower=1)
    order = [m for m in MODES if m in g.index]
    return g.loc[order].rename(columns={"人の秒": "人の秒（平均）", "ロボの秒": "ロボの秒（平均）"}).reset_index()


def prob_better(df: pd.DataFrame, a: str, b: str, metric: str = "取った",
                draws: int = 20000, seed: int = 0) -> float | None:
    """P(方式aが方式bより良い)。一様の事前分布 Beta(1,1) から更新し、乱数で比べる。
    metric="取った"：雑草を取った割合が大きいほど良い／"傷めた"：小麦を傷めた割合が小さいほど良い。"""
    cm = compare_modes(df).set_index("方式")
    if a == b or not {a, b} <= set(cm.index):
        return None
    total = "雑草" if metric == "取った" else "小麦"
    rng = np.random.default_rng(seed)
    p = {}
    for m in (a, b):
        al, be = tl.beta_posterior(int(cm.loc[m, metric]), int(cm.loc[m, total]))
        p[m] = rng.beta(al, be, draws)
    return float((p[a] > p[b]).mean() if metric == "取った" else (p[a] < p[b]).mean())


# ============================================================
# 安全の段階：体験を4段に分け、段ごとに残る危険を数える（ISO 12100 の3ステップの考え方）
# ============================================================
STAGES = ["0 シミュレーター（教室）", "1 小型ローバー（教室・刃なし）", "2 畑で見学（ロボット停止）",
          "3 畑で実機のそば"]
STAGE_COLS = ["0", "1", "2", "3"]
STEP3 = ["本質的安全設計", "安全防護", "使用上の情報"]

# 重さ（1〜4）× 起こりやすさ（0〜4）。値は教材用の仮置き。受け入れ先で見直す。
HAZARDS = pd.DataFrame([
    {"危険": "ロボットハンド・門型の可動部（はさまれ・ぶつかり）", "重さ": 4, "0": 0, "1": 1, "2": 1, "3": 3,
     "対策": "教室の段は小さく弱いハンドにする。可動範囲に入らない線・非常停止", "対策の種類": "本質的安全設計"},
    {"危険": "レーザー光（目・やけど）", "重さ": 4, "0": 0, "1": 0, "2": 0, "3": 0,
     "対策": "実機のレーザーは扱わない。シミュレーターの中だけ", "対策の種類": "本質的安全設計"},
    {"危険": "乾いた草への着火（レーザー・熱）", "重さ": 3, "0": 0, "1": 0, "2": 0, "3": 0,
     "対策": "同上。抜いた草を乾かす場所の近くで火を使わない", "対策の種類": "本質的安全設計"},
    {"危険": "走行（ひかれる・足を踏まれる）", "重さ": 3, "0": 0, "1": 1, "2": 1, "3": 2,
     "対策": "速さの上限・近づいたら止まる距離・非常停止", "対策の種類": "安全防護"},
    {"危険": "畝・斜面での転倒、石や土の飛び散り", "重さ": 2, "0": 0, "1": 0, "2": 1, "3": 2,
     "対策": "平らな畝だけで動かす・保護めがね・離れて見る", "対策の種類": "使用上の情報"},
    {"危険": "畑の暑さ（熱中症）", "重さ": 4, "0": 0, "1": 0, "2": 2, "3": 2,
     "対策": "暑さ指数（WBGT）で中止の基準を先に決める", "対策の種類": "使用上の情報"},
    {"危険": "通信の乗っ取り・途切れ（思わぬ動き）", "重さ": 3, "0": 0, "1": 2, "2": 0, "3": 2,
     "対策": "途切れたら止まる見張り役・操作する端末の認証（SROS2 など）", "対策の種類": "本質的安全設計"},
    {"危険": "カメラに人・近所の家が写る（個人情報）", "重さ": 2, "0": 0, "1": 1, "2": 2, "3": 2,
     "対策": "録画しない・畑の内側だけを写す・写真は許可を取る", "対策の種類": "使用上の情報"},
])


def risk_table(hz: pd.DataFrame = HAZARDS) -> pd.DataFrame:
    out = hz[["危険", "重さ"]].copy()
    for s, name in zip(STAGE_COLS, STAGES):
        out[name] = pd.to_numeric(hz["重さ"]) * pd.to_numeric(hz[s])
    return out


def stage_summary(hz: pd.DataFrame = HAZARDS) -> pd.DataFrame:
    rt = risk_table(hz)
    rows = []
    for name in STAGES:
        col = rt[name]
        rows.append({"段階": name, "リスク点の合計": int(col.sum()), "最大の点": int(col.max()),
                     "8点以上の危険": int((col >= 8).sum())})
    return pd.DataFrame(rows)


# ============================================================
# ③ 判断する：授業の流れと、実機に進む前の点検
# ============================================================
LESSON_PLANS = {
    "45分（1コマ）": [
        ("導入：除草はなぜ大変か・今日の問い", 5, "教員", "小麦と雑草、見分けにくいのはどれか"),
        ("人の目で1ラウンド（45秒）", 8, "生徒", "畑の番号（シード）をメモしておく"),
        ("同じ畑をAIだけで1ラウンド", 7, "生徒", "赤い枠（取る）に小麦が混ざっていないか"),
        ("同じ畑をAI＋人で1ラウンド", 10, "生徒", "黄色の「？」だけを人が決める"),
        ("記録を比べ、τ を自分で決めて一言", 15, "生徒→全体", "「自分の畑ならτ＝○○、なぜなら…」"),
    ],
    "90分（2コマ）": [
        ("導入：除草の手間と、畑の雑草（指標植物）の写真", 10, "教員", "スズメノテッポウは小麦に似ている"),
        ("人の目で2ラウンド（見分けにくさ 0.3 と 0.8）", 15, "生徒", "似ている雑草で人も迷うことを知る"),
        ("AIだけ・AI＋人で各1ラウンド（ハンドとレーザー）", 15, "生徒（2人1組）", "株元の雑草で何が起きるか"),
        ("記録CSVをこのページに貼って比べる", 15, "生徒", "ベイズで「どの方式が良さそうか」を確率で言う"),
        ("① の計算で τ とグレーゾーンの幅を決める", 20, "グループ", "取り残しと傷め、どちらが痛いか"),
        ("ふり返り：AIに任せる・人がやるの線引き", 15, "全体", "収量だけでなく、時間・危険・費用も"),
    ],
}


def lesson_table(name: str) -> pd.DataFrame:
    rows, t = [], 0
    for step, minutes, who, point in LESSON_PLANS[name]:
        rows.append({"開始_分": t, "すること": step, "分": minutes, "だれが": who, "ねらい": point})
        t += minutes
    return pd.DataFrame(rows)


NEXT_STAGE_CHECKS = [
    ("教室の小型ローバーのハンドは小さく弱いもので、刃を付けていない", True),
    ("非常停止の位置と使い方を、生徒全員が言える", True),
    ("通信が途切れたら止まることを、実機で確かめてある", True),
    ("畑で動かす範囲と、生徒が立つ位置を図にしてある（受け入れ先のリスクアセスメント）", True),
    ("暑さ指数（WBGT）の中止基準と、休む場所を決めてある", True),
    ("見守る大人の数が、生徒の数に足りている", True),
    ("カメラ映像を録画しない・写す範囲を、学校と取り決めてある", True),
    ("実機のレーザーを使わないことを、関係者で確かめてある", True),
    ("シミュレーターで、全員が3方式を1ラウンド以上終えている", False),
    ("事前学習で、小麦と畑の雑草の見分け方を学んでいる", False),
]


def next_stage_readiness(done: Sequence[bool]) -> dict:
    must_missing = [t for (t, must), ok in zip(NEXT_STAGE_CHECKS, done) if must and not ok]
    want_missing = [t for (t, must), ok in zip(NEXT_STAGE_CHECKS, done) if not must and not ok]
    verdict = ("まだ次の段には進まない（必須が欠けています）" if must_missing
               else "次の段を受け入れ先と相談できる" if not want_missing
               else "次の段に進める。ただし残りを当日までに")
    return {"準備度": sum(done) / len(NEXT_STAGE_CHECKS), "判定": verdict,
            "まだの必須": must_missing, "まだの推奨": want_missing}


ROS2_WEED_TRIAGE = '''# 除草の「仕分け役」（例：表示するだけ。実機では受け入れ先の安全担当が確かめてから）
# AIの点数 s で、取る／残す／人に聞く に分ける。人がそばにいるとき・非常停止中は、何も取らない。
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, Float32MultiArray

TAU_LOW, TAU_HIGH = 0.40, 0.60   # このページの③で決めた値

class WeedTriage(Node):
    def __init__(self):
        super().__init__("weed_triage")
        self.stop = True                       # わからないときは「止まる」側から始める
        self.take = self.create_publisher(Float32MultiArray, "/weeder/targets", 10)     # 取る（x, y の並び）
        self.ask = self.create_publisher(Float32MultiArray, "/weeder/human_review", 10)  # 人に聞く
        self.create_subscription(Bool, "/safety/stop", self.on_stop, 10)  # 非常停止・人の接近
        # 検出は [x, y, s, x, y, s, ...] の並びで届くとする（教材用の単純な形）
        self.create_subscription(Float32MultiArray, "/vision/weed_scores", self.on_scores, 10)

    def on_stop(self, msg):
        self.stop = msg.data

    def on_scores(self, msg):
        if self.stop:
            return                              # 止まっているあいだは、取る指令を出さない
        take, ask = Float32MultiArray(), Float32MultiArray()
        d = list(msg.data)
        for x, y, s in zip(d[0::3], d[1::3], d[2::3]):
            if s >= TAU_HIGH:
                take.data += [x, y]
            elif s >= TAU_LOW:
                ask.data += [x, y, s]           # 迷うものは人が画面で決める
        self.take.publish(take)
        self.ask.publish(ask)

def main():
    rclpy.init()
    rclpy.spin(WeedTriage())

if __name__ == "__main__":
    main()
'''

SOURCES = [
    "信号検出理論・ROC：Green, D. M., & Swets, J. A. (1966). Signal Detection Theory and Psychophysics. Wiley.",
    "雑草による減収の双曲線モデル：Cousens, R. (1985). A simple model relating yield loss to weed density. "
    "Annals of Applied Biology, 107(2), 239–252.",
    "リスクアセスメントの3ステップ：ISO 12100（機械類の安全性）",
    "レーザーの安全：JIS C 6802（レーザ製品の安全基準）。このページでは実機のレーザーを扱わない",
    "ROS 2 の通信の認証・暗号化：SROS2（ROS 2 公式ドキュメント）",
]


# ============================================================
# 自己チェック
# ============================================================
def main():
    # Φ と τ：τ が上がるほど取る割合も読み違いも減る
    assert abs(phi(0) - 0.5) < 1e-12 and abs(phi(1.96) - 0.975) < 1e-3
    r1, r2 = classify_rates(0.3), classify_rates(0.7)
    assert r1["雑草を取る割合"] > r2["雑草を取る割合"] and r1["小麦を読み違える割合"] > r2["小麦を読み違える割合"]
    assert r1["広葉を取る割合"] > r1["イネ科を取る割合"]          # イネ科は小麦に似ていて取りにくい
    assert abs(classify_rates(0.5, d=0)["雑草を取る割合"] - 0.5) < 1e-9  # d=0 はコイン投げ
    # τ=0.5 のとき、広葉の検出率 = 1 − 小麦の読み違い（対称）
    r = classify_rates(0.5)
    assert abs(r["広葉を取る割合"] - (1 - r["小麦を読み違える割合"])) < 1e-9
    # AI＋人：グレーゾーン幅0はAIだけと同じ。幅を広げると人の確認が増え、読み違いは減る
    a = classify_rates(0.5)
    t0 = triage_rates(0.5, 0.5)
    assert abs(t0["雑草を取る割合"] - a["雑草を取る割合"]) < 1e-9 and t0["人が見る雑草の割合"] == 0
    t1 = triage_rates(0.3, 0.7)
    assert t1["人が見る小麦の割合"] > 0 and t1["小麦を読み違える割合"] < classify_rates(0.3)["小麦を読み違える割合"]
    # Cousens：0本で0、増えると上限Aに近づく
    assert yield_loss(0) == 0 and yield_loss(10) < yield_loss(40) < COUSENS_A and yield_loss(1e6) > 49.9
    # ハンドは株元の雑草で隣の小麦の根を傷める。レーザーは傷めない
    m = field_outcome(0.9, 0.0, 40, 80, "ハンド（抜き取り）")
    lz = field_outcome(0.9, 0.0, 40, 80, "レーザー")
    assert m["傷んだ小麦の割合"] > lz["傷んだ小麦の割合"] == 0
    # 4案の比較：何もしないより、どの案も収量が上がる。人の手がいちばん人の時間を使う
    cp = compare_plans(96, 30, 80, 0.5, 0.15).set_index("案")
    assert (cp.loc[["人の手", "AIだけ", "AI＋人"], "期待収量"] > cp.loc["何もしない", "期待収量"]).all()
    assert cp["人_分"].idxmax() == "人の手" and cp.loc["AI＋人", "人_分"] > cp.loc["AIだけ", "人_分"] == 0
    # 人の手：96㎡×30本×5秒＝240分
    assert abs(cp.loc["人の手", "人_分"] - 240) < 1e-9
    # ROC：τ を下げるほど右上へ（単調）
    roc = roc_curve()
    assert roc["小麦を読み違える割合"].is_monotonic_decreasing and roc["雑草を取る割合"].is_monotonic_decreasing
    # 最適な τ：株元で傷めるハンドは、傷めないレーザーより τ を高め（取りすぎない）にする
    t_laser, y_laser = best_tau(40, 80, method="レーザー")
    t_mech, y_mech = best_tau(40, 80, method="ハンド（抜き取り）")
    assert t_mech >= t_laser and y_laser >= y_mech, (t_laser, t_mech)
    # 雑草が多いほど τ は低め（取りこぼしの損が大きい）
    t_lowweed, _ = best_tau(5, 80)
    t_highweed, _ = best_tau(80, 80)
    assert t_highweed <= t_lowweed, (t_lowweed, t_highweed)
    # 見本の点数：小麦 < イネ科 < 広葉 の順に平均が高い
    ss = score_samples().groupby("種類")["点数"].mean()
    assert ss["小麦"] < ss["イネ科の雑草"] < ss["広葉の雑草"]
    # ② 記録CSV
    df = parse_records(SAMPLE_CSV)
    assert len(df) == 7 and set(df["方式"]) == set(MODES)
    cm = compare_modes(df).set_index("方式")
    assert list(cm.index) == MODES
    assert cm.loc["AI＋人", "雑草を取った割合"] > cm.loc["人の目", "雑草を取った割合"]
    p = prob_better(df, "AI＋人", "人の目", "取った")
    assert p is not None and p > 0.9
    q = prob_better(df, "AI＋人", "AIだけ", "傷めた")
    assert q is not None and q > 0.5
    assert prob_better(df, "AI＋人", "AI＋人") is None
    assert prob_better(df[df["方式"] == "AIだけ"], "AIだけ", "人の目") is None
    try:
        parse_records("a,b\n1,2")
        raise AssertionError("列の足りないCSVを通してしまった")
    except ValueError:
        pass
    bad = parse_records(SAMPLE_CSV + "8,AIだけ,0.5,ハンド,0.5,1,10,12,72,0,0,0,80\n"   # 取った＞雑草
                        "9,AIだけ,0.5,ハンド,0.5,1,abc,1,72,0,0,0,80\n"                    # 数でない
                        "10,ロボ,0.5,ハンド,0.5,1,10,1,72,0,0,0,80\n")                      # 方式が不明
    assert d_from_difficulty(0.5) == D_DEFAULT
    assert len(bad) == 7
    # 安全の段階：シミュレーターの段は危険ゼロ、実機のそばがいちばん高い
    sm = stage_summary().set_index("段階")
    assert sm.loc[STAGES[0], "リスク点の合計"] == 0
    assert sm["リスク点の合計"].idxmax() == STAGES[3]
    assert risk_table()[STAGES].to_numpy().max() <= 16
    # 授業の流れ：45分と90分ちょうど
    assert lesson_table("45分（1コマ）")["分"].sum() == 45
    assert lesson_table("90分（2コマ）")["分"].sum() == 90
    ok = next_stage_readiness([True] * len(NEXT_STAGE_CHECKS))
    assert ok["判定"].startswith("次の段を") and ok["準備度"] == 1
    one = next_stage_readiness([i != 0 for i in range(len(NEXT_STAGE_CHECKS))])
    assert one["判定"].startswith("まだ") and len(one["まだの必須"]) == 1
    compile(ROS2_WEED_TRIAGE, "weed_triage.py", "exec")  # 表示するコードが文法として正しいか
    print("weeding_lab.py：自己チェック OK")


if __name__ == "__main__":
    main()

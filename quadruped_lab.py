"""
quadruped_lab.py — 学校向けの探究「四足ロボ・シミュレーター」（草刈り・除草剤散布・栗拾い）の計算部品

画面は pages/10_🤖_AIロボット.py（🐕 四足ロボのタブ）。`python quadruped_lab.py` で自己チェック。
シミュレーター本体は docs/sim/quadruped_robot.html（three.js、ブラウザだけで動く）。

問い
  車輪のロボットが入りにくい斜面・林の中で、四足歩行ロボットに草刈り・除草剤のスポット散布・栗拾いを
  任せるとき、「傾き」「見分けにくさ」「年間の作業量」から、ロボに任せるか人がやるかをどう決めるか。

骨格（リポジトリ共通）：① 計算する → ② 可視化する → ③ 自分の条件で判断する
  ① 計算する   … 見分ける点数（信号検出理論）・斜面のすべりやすさ・電池・作業の速さ
  ② 可視化する … 傾きとすべりやすさ（四足・人の足・車輪）、シミュレーターの記録CSVで「人・AI・AI＋人」を比べる
  ③ 判断する   … 1年あたりの費用（人がやる／四足ロボ＋見守り）と、元が取れる面積

方針
  - このページも部品も、ロボットを動かさない。数値はすべて教材用の仮置き。
  - 本体価格の初期値 900,000円 は、販売ページに載っていた Unitree Go2 のメーカー希望小売価格。
  - 実際の事例（CASES）は、資料に書かれていたことだけを載せる。性能の数値は載せない。
"""
from __future__ import annotations

import io
import math

import numpy as np
import pandas as pd

# ============================================================
# シミュレーターと同じ定数（docs/sim/quadruped_robot.html と一致させる）
# ============================================================
L, W = 8.0, 3.0            # 区画 m
LANE = 0.3                 # AIの往復の間隔 m
MIX = {"t": 0.6, "s": 0.25, "n": 0.15}   # 物の内訳：作業の相手・似ている物・ちがう物
SIGMA = 0.2                # すべりのばらつき
FALL = 0.15                # すべったときに転倒する割合
BODY = {"四足ロボ": 0.85, "人の足": 0.75, "車輪のロボ": 0.55}   # 摩擦係数（仮置き）
V0 = 0.4                   # 平らな所の歩く速さ m/秒
BAT0 = 0.25                # 平らな所 1 m あたりの電池 %
DRIFT = 0.08               # 風速 1 m/秒 あたり、近くの守る植物に薬がかかる割合（上限 0.6）
SPOT_ML, BLANKET_ML = 15, 100   # 1回のスポット散布 mL ／ 全面散布 mL/㎡
UNITREE_GO2_PRICE = 900_000     # 販売ページのメーカー希望小売価格（円）

TASKS = {
    "草刈り": {"相手": "草むら", "似ている物": "エヒメアヤメ（残す草花）", "ちがう物": "石・杭",
             "傾き": 25, "人の速さ": 400, "ロボの速さ係数": 1.0},
    "散布": {"相手": "雑草", "似ている物": "守る芝（グラウンドカバー）", "ちがう物": "架台の脚・ケーブル",
           "傾き": 5, "人の速さ": 800, "ロボの速さ係数": 1.5},
    "栗拾い": {"相手": "良い栗", "似ている物": "虫食い・傷んだ栗", "ちがう物": "石・空のイガ",
            "傾き": 15, "人の速さ": 150, "ロボの速さ係数": 0.4},
}


def phi(x: float) -> float:
    """標準正規分布の累積分布関数 Φ(x)。"""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def d_from_difficulty(h: float) -> float:
    """シミュレーターの見分けにくさ h（0〜1）→ 見分けやすさ d。"""
    return 4 - 3 * h


def p_act(kind: str, tau: float, d: float) -> float:
    """種類 kind（t 相手・s 似ている物・n ちがう物）に、AIが作業する確率 = 1 − Φ(logit τ − μ)。"""
    mu = {"t": d / 2, "s": 0.0, "n": -d / 2}[kind]
    return 1 - phi(logit(tau) - mu)


def p_slip(theta_deg: float, mu: float) -> float:
    """1 m あたりのすべりやすさ p = Φ((tan θ − μ) / σ)。"""
    return phi((math.tan(math.radians(theta_deg)) - mu) / SIGMA)


def speed(theta_deg: float) -> float:
    """歩く速さ m/秒（傾きが大きいほど遅い）。"""
    return V0 * max(0.15, 1 - theta_deg / 50)


def battery_per_m(theta_deg: float) -> float:
    """1 m あたりの電池 %。"""
    return BAT0 * (1 + 3 * math.sin(math.radians(theta_deg)))


def drift_prob(wind: float) -> float:
    """風速 wind（m/秒）で、近くの守る植物に薬がかかる割合。"""
    return min(0.6, DRIFT * wind)


def slip_table(thetas=range(0, 41, 5)) -> pd.DataFrame:
    """② 可視化：傾きごとの、1 m あたりのすべりやすさ（％）。"""
    rows = [{"傾き θ（度）": t, "必要な摩擦 tanθ": round(math.tan(math.radians(t)), 2),
             **{k: round(p_slip(t, mu) * 100, 2) for k, mu in BODY.items()}} for t in thetas]
    return pd.DataFrame(rows)


def rates(task: str, theta_deg: float) -> tuple[float, float]:
    """（人の作業速度, ロボの作業速度）㎡/時。どちらも傾きで遅くなる（仮置き）。"""
    t = TASKS[task]
    human = t["人の速さ"] * max(0.2, 1 - theta_deg / 60)
    robot = V0 * 3600 * LANE * 0.6 * t["ロボの速さ係数"] * max(0.15, 1 - theta_deg / 50)
    return human, robot


def annual_cost(area: float, task: str, theta_deg: float, wage: float = 1100, price: float = UNITREE_GO2_PRICE,
                years: float = 5, keep: float = 80_000, watch: float = 0.3, risk: float = 300) -> dict:
    """③ 1年あたりの費用（円）。シミュレーターの ③ と同じ式。
    人   = 面積 ÷ 人の速さ × 時給 ＋ 歩く距離（幅 1 m）× 人の足のすべりやすさ × すべり1回の重み
    ロボ = 本体 ÷ 年数 ＋ 保守 ＋ 面積 ÷ ロボの速さ × 時給 × 見守る割合 ＋ 歩く距離（幅 0.3 m）× すべり × 転倒 × 重み
    """
    hr, rr = rates(task, theta_deg)
    human = area / hr * wage + area / 1.0 * p_slip(theta_deg, BODY["人の足"]) * risk
    robot = (price / max(1, years) + keep + area / rr * wage * watch
             + area / LANE * p_slip(theta_deg, BODY["四足ロボ"]) * FALL * risk)
    return {"人がやる": human, "四足ロボ＋見守り": robot, "人の速さ ㎡/時": hr, "ロボの速さ ㎡/時": rr}


def break_even(task: str, theta_deg: float, **kw) -> float | None:
    """ロボのほうが安くなる年間面積（㎡）。面積あたりで人のほうが安いなら None。"""
    c0, c1 = annual_cost(0, task, theta_deg, **kw), annual_cost(1000, task, theta_deg, **kw)
    per = (c1["人がやる"] - c0["人がやる"] - (c1["四足ロボ＋見守り"] - c0["四足ロボ＋見守り"])) / 1000
    if per <= 0:
        return None
    return (c0["四足ロボ＋見守り"] - c0["人がやる"]) / per


def cost_curve(task: str, theta_deg: float, amax: float, n: int = 41, **kw) -> pd.DataFrame:
    rows = []
    for a in np.linspace(0, amax, n):
        c = annual_cost(float(a), task, theta_deg, **kw)
        rows += [{"年間の作業面積（㎡）": a, "やり方": k, "円／年": c[k]} for k in ("人がやる", "四足ロボ＋見守り")]
    return pd.DataFrame(rows)


# ============================================================
# シミュレーターの記録CSV
# ============================================================
CSV_COLS = ["round", "task", "mode", "slope_deg", "difficulty", "tau", "seed", "targets_total", "targets_done",
            "wrong_actions", "slips", "falls", "battery_used", "spray_ml", "human_checks", "human_sec", "robot_sec"]
SAMPLE_CSV = """round,task,mode,slope_deg,difficulty,tau,seed,targets_total,targets_done,wrong_actions,slips,falls,battery_used,spray_ml,human_checks,human_sec,robot_sec
1,草刈り,人の操作,25,0.5,,1,24,21,2,1,0,30,,23,410,410
2,草刈り,AIだけ,25,0.5,0.50,1,24,20,3,1,0,33,,0,0,236
3,草刈り,AI＋人,25,0.5,0.50,1,24,21,1,1,0,34,,6,14,245
4,草刈り,AIだけ,25,0.5,0.50,2,25,21,4,2,1,29,,0,120,205
5,草刈り,AI＋人,25,0.5,0.50,2,25,22,2,2,0,35,,7,16,250
"""
MODES = ["人の操作", "AIだけ", "AI＋人"]


def parse_records(text: str) -> pd.DataFrame:
    """シミュレーターの「CSVをコピー」を読む。知らない列は捨て、足りない列があればエラー。"""
    df = pd.read_csv(io.StringIO(text.strip()))
    miss = [c for c in CSV_COLS if c not in df.columns and c != "spray_ml"]
    if miss:
        raise ValueError("列が足りません：" + "、".join(miss))
    df = df[[c for c in CSV_COLS if c in df.columns]].copy()
    for c in ["targets_total", "targets_done", "wrong_actions", "slips", "falls", "battery_used", "human_sec", "robot_sec"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


def compare_modes(df: pd.DataFrame) -> pd.DataFrame:
    """作業・やり方ごとに、済んだ割合・まちがい・すべり・人の秒を合計して比べる。"""
    g = df.groupby(["task", "mode"], sort=False).agg(
        回数=("round", "count"), 相手=("targets_total", "sum"), 済んだ=("targets_done", "sum"),
        まちがい=("wrong_actions", "sum"), すべり=("slips", "sum"), 転倒=("falls", "sum"),
        人の秒=("human_sec", "sum"), ロボの秒=("robot_sec", "sum")).reset_index()
    g["済んだ割合"] = (g["済んだ"] / g["相手"].where(g["相手"] > 0)).round(3)
    return g.rename(columns={"task": "作業", "mode": "やり方"})


def prob_better(df: pd.DataFrame, a: str, b: str, task: str | None = None, n: int = 20_000, seed: int = 0) -> float | None:
    """「済んだ割合」について、やり方 a が b より高い確率（ベータ分布・一様な事前分布）。"""
    d = df if task is None else df[df["task"] == task]
    sa, sb = d[d["mode"] == a], d[d["mode"] == b]
    if sa.empty or sb.empty:
        return None
    rng = np.random.default_rng(seed)
    pa = rng.beta(1 + sa["targets_done"].sum(), 1 + (sa["targets_total"] - sa["targets_done"]).sum(), n)
    pb = rng.beta(1 + sb["targets_done"].sum(), 1 + (sb["targets_total"] - sb["targets_done"]).sum(), n)
    return float((pa > pb).mean())


# ============================================================
# 実際の事例・ロボットの体の比べ方・安全
# ============================================================
CASES = pd.DataFrame([
    ("草刈り", "ライフタイムサポート（長野県・信州型サンドボックス事業）",
     "Unitree Go2 の前に、3Dプリンターでつくったアームと草刈機の刈刃を取り付け、山間部の急斜面・法面で草刈りを実証（2026年11月1日）。"
     "人が斜面で刈払機を扱うときの転落・熱中症のリスクを減らすのが目的。12月中旬ごろから自動運転の検証に入る予定。",
     "https://prtimes.jp/main/html/rd/p/000000002.000169336.html"),
    ("除草剤散布", "Airion（東大発のフィジカルAI企業）・Stearmotor",
     "四足歩行ロボット（Unitree ベース）で「自律除草剤散布ロボット」を共同開発。太陽光パネルの周りの除草の省人化をねらう。",
     "https://robotstart.info/article/2026/08/26/382327.html"),
    ("栗拾い", "高知県四万十町の栗園での実証実験",
     "四足歩行ロボットにセンサーとアームを付け、落ちた栗を自動で拾う。人手不足の解決をねらい、教授は「想像以上にスムーズ」と話した。",
     "https://news.yahoo.co.jp/articles/0441bb127c66de9355ba6f520e2fbbb11b098974"),
], columns=["作業", "だれが・どこで", "資料に書かれていたこと", "出典"])

BODY_TABLE = pd.DataFrame([
    ("門型（車輪で畝をまたぐ）", "🌱 除草AIロボ", "平らな畑の畝。上から真下を見られ、ハンドが安定する", "斜面・段差・木の根。畝の幅が変わる畑"),
    ("レール走行（温湯管の上）", "🍅 ハウス収穫ロボ", "ハウスの通路。位置がぶれず、重い収穫箱も運べる", "レールのない場所。ハウスの外"),
    ("四足歩行", "🐕 四足ロボ", "法面・林の中・段差・パネルの下。横歩きで向きを変えずに動ける", "長い時間の作業（電池）・重い荷物・急な斜面での転倒"),
], columns=["体のつくり", "このダッシュボードのシミュレーター", "得意な場所", "苦手な場所"])

SAFETY = pd.DataFrame([
    ("刈刃", "飛び石・巻き込み", "人が刃の届く範囲（とその先の飛び石の範囲）にいるときは動かさない。止める手段（非常停止）を先に決める"),
    ("斜面", "転倒・滑落", "シミュレーターで傾きとすべりを先に試す。実機は人が近くで見守り、回収の道具と手順を決めておく"),
    ("除草剤", "薬害・周りの作物や水路への飛散", "登録された農薬を、ラベルの使用基準どおりに使う。風の強い日はまかない。生徒は実機の散布をしない"),
    ("アーム", "はさみ込み", "アームの動く範囲に手を入れない。動かす前に声をかける"),
    ("通信・カメラ", "乗っ取り・写り込み", "初期パスワードを変える。人や近くの家が写らない範囲で撮る"),
], columns=["道具・場所", "危険", "対策"])

SOURCES = [
    "信号検出理論・ROC：Green, D. M., & Swets, J. A. (1966). Signal Detection Theory and Psychophysics. Wiley.",
    "斜面ですべらずに立つ条件（μ ≥ tan θ）：高校物理基礎「摩擦力」",
    "リスクアセスメントの3ステップ：ISO 12100（機械類の安全性）",
    "Unitree Go2 の重量・大きさ・価格：販売ページ https://biz.fagcorp.com/product.php?id=29",
]


# ============================================================
# 自己チェック
# ============================================================
def main():
    assert abs(phi(0) - 0.5) < 1e-12
    # 見分け：τ を上げると、相手にも似ている物にも作業しにくくなる。相手 > 似ている物 > ちがう物
    d = d_from_difficulty(0.5)
    assert p_act("t", 0.3, d) > p_act("t", 0.7, d)
    assert p_act("t", 0.5, d) > p_act("s", 0.5, d) > p_act("n", 0.5, d)
    assert abs(p_act("s", 0.5, d) - 0.5) < 1e-9          # 似ている物は τ=0.5 でコイン投げ
    # 斜面：傾くほどすべりやすく、四足 < 人の足 < 車輪
    for t in (10, 25, 35):
        assert p_slip(t, BODY["四足ロボ"]) < p_slip(t, BODY["人の足"]) < p_slip(t, BODY["車輪のロボ"])
    assert p_slip(30, BODY["四足ロボ"]) > p_slip(20, BODY["四足ロボ"])
    assert p_slip(0, BODY["四足ロボ"]) < 1e-4
    assert speed(30) < speed(0) and battery_per_m(30) > battery_per_m(0)
    assert drift_prob(10) == 0.6 and drift_prob(0) == 0
    # 費用：面積が増えると人の費用が早く増える → 元が取れる面積がある（草刈り・25°）
    be = break_even("草刈り", 25)
    assert be is not None and be > 0
    c = annual_cost(be * 1.5, "草刈り", 25)
    assert c["四足ロボ＋見守り"] < c["人がやる"]
    c = annual_cost(be * 0.5, "草刈り", 25)
    assert c["四足ロボ＋見守り"] > c["人がやる"]
    # 本体が安いほど、元が取れる面積は小さい
    assert break_even("草刈り", 25, price=300_000) < be
    # CSV：サンプルが読めて、比べられる
    df = parse_records(SAMPLE_CSV)
    cm = compare_modes(df)
    assert set(cm["やり方"]) == set(MODES)
    p = prob_better(df, "AI＋人", "AIだけ", task="草刈り")
    assert p is not None and 0 <= p <= 1
    assert len(slip_table()) == 9 and len(CASES) == 3
    print("quadruped_lab: OK")
    print(slip_table().to_string(index=False))
    print(f"草刈り・25°で元が取れる年間面積：約 {be:,.0f} ㎡")


if __name__ == "__main__":
    main()

"""
harvest_lab.py — 探究コーナー「ハウス収穫ロボで安全安心な体験実習」の計算部品

画面は pages/21_🍅_ハウス収穫ロボ体験実習.py。`python harvest_lab.py` で自己チェック。
シミュレーター本体は docs/sim/harvest_robot_tomato.html（three.js、ブラウザだけで動く）。

問い
  ハウスの収穫ロボットを中高生の職場体験・実習で扱うとき、危険を段階的に減らしながら、
  「人の遠隔操作」と「AIの自動収穫」を比べ、自分の条件で AI の設定を決める体験を、どう組み立てるか。

骨格（リポジトリ共通）：① 計算する → ② 可視化する → ③ 自分の条件で判断する
  安全の段階   … 危険を「重さ×起こりやすさ」で点数化し、段階ごとに残るリスクを数える（ISO 12100 の3ステップの考え方）
  ① 計算する   … 遅延のあいだに進む距離／AIの検出と色の読み違いのモデル（シミュレーターと同じ式）
  ② 可視化する … シミュレーターの記録CSVを読み、人とAIを比べる（ベイズで「AIのほうが取り残しが少ない確率」）
  ③ 判断する   … 取り残しと誤収穫の損失から、しきい値 τ を決める。実機に進む前の点検
  大人の条件   … 収穫ロボが「産業用ロボット」にあたるか（80W）、どの作業に特別教育（安衛則36条31号・32号）が要るかを判定し、
                  段ごとに生徒・見守る大人・ロボットを扱う大人（修了者）の役割を分ける。生徒には教示・点検をさせない

方針
  - このページも部品も、ロボットを動かさない。ROS2のコードは表示するだけ。
  - モデルは教育用の単純化。実機の性能・判定方式を再現したものではない。
  - 実機に近づく段階の配置・人数は、受け入れ先のリスクアセスメントで決める。ここの点数は話し合いの材料。
"""
from __future__ import annotations

import io
from collections.abc import Sequence

import numpy as np
import pandas as pd

import tokushi_lab as tl  # ロボットとの距離の式は「AI×特別支援教育」と共通にする

# シミュレーターと同じ定数（docs/sim/harvest_robot_tomato.html の L・RIPE・REACH と速度）
RIPE = 0.70          # 収穫基準：着色度 ≥ 70%
REACH = 0.07         # ハンドが届く範囲（中心から ±m）
V_TRAVEL = 0.4       # 遠隔操作の走行速度 m/s
V_ARM = 0.3          # アームの上下速度 m/s

# ============================================================
# 安全の段階：体験を4段に分け、段ごとに残る危険を数える
# ============================================================
STAGES = ["0 シミュレーター（教室）", "1 遠隔操作（教室から実機）", "2 ハウス見学（ロボット停止）",
          "3 実機のそばで体験"]

# 重さ（1〜4）× 起こりやすさ（1〜4）。起こりやすさは「その段で人がその危険にさらされるか」で段ごとに置く。
# 0 は「その段にはその危険がない」。値は教材用の仮置き。受け入れ先で見直す。
HAZARDS = pd.DataFrame([
    {"危険": "ロボットの可動部（挟まれ・ぶつかり）", "重さ": 4, "0": 0, "1": 0, "2": 1, "3": 3,
     "対策": "可動範囲に入らない線・非常停止・速度と間隔の監視", "対策の種類": "安全防護"},
    {"危険": "収穫ハンドの刃（切り傷）", "重さ": 3, "0": 0, "1": 0, "2": 1, "3": 2,
     "対策": "刃の交換・清掃は大人だけ。生徒はハンドに触れない", "対策の種類": "使用上の情報"},
    {"危険": "温湯管レール（つまずき・熱いとき）", "重さ": 2, "0": 0, "1": 0, "2": 3, "3": 3,
     "対策": "通路だけを歩く・レールをまたがない・暖房期は触らない", "対策の種類": "使用上の情報"},
    {"危険": "ハウスの暑さ（熱中症）", "重さ": 4, "0": 0, "1": 0, "2": 2, "3": 3,
     "対策": "暑さ指数（WBGT）で中止の基準を先に決める・時間を区切る", "対策の種類": "使用上の情報"},
    {"危険": "農薬をまいた後の立ち入り", "重さ": 3, "0": 0, "1": 0, "2": 2, "3": 2,
     "対策": "散布の記録を確かめ、ラベルの立ち入り制限を守る", "対策の種類": "使用上の情報"},
    {"危険": "通信の遅れ・途切れ（思わぬ動き）", "重さ": 3, "0": 1, "1": 2, "2": 0, "3": 2,
     "対策": "途切れたら止まる見張り（ウォッチドッグ）・速度の上限", "対策の種類": "本質的安全設計"},
    {"危険": "カメラ映像に顔・名札が映る（個人情報）", "重さ": 2, "0": 0, "1": 2, "2": 2, "3": 2,
     "対策": "映像を録画しない・映す範囲を決める・写真は許可を取る", "対策の種類": "使用上の情報"},
    {"危険": "遠隔操作の乗っ取り（なりすまし）", "重さ": 3, "0": 0, "1": 2, "2": 0, "3": 1,
     "対策": "操作する端末を認証する（SROS2 など）・操作できる時間を決める", "対策の種類": "本質的安全設計"},
])
STAGE_COLS = ["0", "1", "2", "3"]
STEP3 = ["本質的安全設計", "安全防護", "使用上の情報"]  # ISO 12100 の順番：上ほど先に考える


def risk_table(hz: pd.DataFrame = HAZARDS) -> pd.DataFrame:
    """危険×段のリスク点（重さ×起こりやすさ、0〜16）。"""
    out = hz[["危険", "重さ"]].copy()
    for s, name in zip(STAGE_COLS, STAGES):
        out[name] = hz["重さ"] * hz[s]
    return out


def risk_level(score: float) -> str:
    """点数の区分（仮置き）。8以上は「その段では生徒を近づけない」相当。"""
    if score >= 8:
        return "高：対策が済むまで行わない"
    if score >= 4:
        return "中：対策と見守りの大人をつける"
    if score > 0:
        return "低：説明してから行う"
    return "なし"


def stage_summary(hz: pd.DataFrame = HAZARDS) -> pd.DataFrame:
    rt = risk_table(hz)
    rows = []
    for name in STAGES:
        col = rt[name]
        rows.append({"段階": name, "危険の数": int((col > 0).sum()), "リスク点の合計": int(col.sum()),
                     "いちばん高い点": int(col.max()), "区分": risk_level(col.max())})
    return pd.DataFrame(rows)


# ============================================================
# ① 計算する
# ============================================================
def latency_overshoot(latency_ms: float, v: float = V_TRAVEL) -> float:
    """手を離してから止まるまでに、遅延のぶん余分に進む距離（m）。"""
    return v * latency_ms / 1000


def max_safe_latency(reach: float = REACH, v: float = V_TRAVEL) -> float:
    """余分に進む距離が「届く範囲」を超えない遅延の上限（ms）。"""
    return reach / v * 1000


def latency_curve(latencies: Sequence[float] = tuple(range(0, 801, 50))) -> pd.DataFrame:
    return pd.DataFrame({"遅延_ms": list(latencies),
                         "走行で余分に進む_cm": [latency_overshoot(x) * 100 for x in latencies],
                         "上下で余分に動く_cm": [latency_overshoot(x, V_ARM) * 100 for x in latencies]})


def remote_distance(v_r: float, latency_ms: float, t_stop: float = 0.3, margin: float = 0.2) -> dict:
    """実機のそばにいる人とロボットの距離。遠隔操作では「気づくまでの時間」に通信の遅延が足される。"""
    return tl.protective_distance(v_r, t_react=0.1 + latency_ms / 1000, t_stop=t_stop, margin=margin)


# シミュレーターと同じ判定モデル
#   検出スコア s = 0.92 − 0.80·o + ε₁   ε₁~N(0, 0.08²)   → s ≥ τ で検出
#   着色度推定 ĉ = c + ε₂               ε₂~N(0, (0.04+0.12·o)²) → ĉ ≥ 0.70 で収穫
def simulate(occ_level: float, tau: float, n: int = 4000, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    col = rng.random(n)
    ripe = col >= RIPE
    occ = np.minimum(0.95, occ_level * (0.4 + rng.random(n) * 1.2))
    detected = 0.92 - 0.8 * occ + 0.08 * rng.standard_normal(n) >= tau
    est = col + (0.04 + 0.12 * occ) * rng.standard_normal(n)
    pick = detected & (est >= RIPE)
    tp, fn = int((ripe & pick).sum()), int((ripe & ~pick).sum())
    fp, tn = int((~ripe & pick).sum()), int((~ripe & ~pick).sum())
    return {"TP": tp, "FN": fn, "FP": fp, "TN": tn, "n": n,
            "適期果の収穫率": tp / max(1, tp + fn), "未熟果の誤収穫率": fp / max(1, fp + tn)}


def occlusion_curve(tau: float, occs: Sequence[float] = tuple(np.round(np.arange(0, 0.81, 0.1), 2)),
                    seed: int = 0) -> pd.DataFrame:
    rows = []
    for o in occs:
        r = simulate(o, tau, seed=seed)
        rows.append({"遮蔽率": o, "適期果の収穫率": r["適期果の収穫率"], "未熟果の誤収穫率": r["未熟果の誤収穫率"]})
    return pd.DataFrame(rows)


def loss_curve(occ_level: float, cost_miss: float, cost_false: float,
               taus: Sequence[float] = tuple(np.round(np.arange(0.30, 0.901, 0.05), 2)), seed: int = 0) -> pd.DataFrame:
    """100本あたりの損失（円）。同じ乱数で比べる（共通乱数法）ので、τ の差だけが出る。"""
    rows = []
    for t in taus:
        r = simulate(occ_level, t, seed=seed)
        rows.append({"τ": t, "取り残し": r["FN"] / r["n"] * 100, "誤収穫": r["FP"] / r["n"] * 100,
                     "損失_円": (r["FN"] * cost_miss + r["FP"] * cost_false) / r["n"] * 100})
    return pd.DataFrame(rows)


def best_tau(occ_level: float, cost_miss: float, cost_false: float, seed: int = 0) -> tuple[float, float]:
    lc = loss_curve(occ_level, cost_miss, cost_false, seed=seed)
    i = int(lc["損失_円"].idxmin())
    return float(lc.loc[i, "τ"]), float(lc.loc[i, "損失_円"])


# ============================================================
# ② 可視化する：シミュレーターの記録CSVを読む
# ============================================================
CSV_COLS = ["round", "mode", "occlusion", "condition", "good", "immature_picked", "missed", "sec_per_fruit"]

# 架空の記録（同じシードで人とAIを試した例）。実際は、シミュレーターの「CSVをコピー」を貼る。
SAMPLE_CSV = """round,mode,occlusion,condition,good,immature_picked,missed,sec_per_fruit
1,人（遠隔）,0.3,"遅延 150 ms",14,2,31,9.8
2,AI,0.3,"τ=0.55・×2",33,3,12,3.1
3,人（遠隔）,0.6,"遅延 150 ms",9,4,36,12.4
4,AI,0.6,"τ=0.55・×2",21,6,24,3.4
5,AI,0.6,"τ=0.40・×2",28,9,17,3.3
"""


def parse_records(text: str) -> pd.DataFrame:
    """CSVの文字列を読み、列と値を確かめる。おかしな行は落とす。"""
    df = pd.read_csv(io.StringIO(text.strip()))
    missing = [c for c in CSV_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"列が足りません：{', '.join(missing)}")
    df = df[CSV_COLS].copy()
    for c in ["occlusion", "good", "immature_picked", "missed", "sec_per_fruit"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["good", "immature_picked", "missed"])
    df = df[(df[["good", "immature_picked", "missed"]] >= 0).all(axis=1)]
    df["方式"] = np.where(df["mode"].astype(str).str.contains("AI"), "AI", "人（遠隔）")
    df["適期果の収穫率"] = df["good"] / (df["good"] + df["missed"]).clip(lower=1)
    df["誤収穫の割合"] = df["immature_picked"] / (df["good"] + df["immature_picked"]).clip(lower=1)
    return df.reset_index(drop=True)


def compare_modes(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("方式").agg(ラウンド=("round", "count"), 適期収穫=("good", "sum"),
                              誤収穫=("immature_picked", "sum"), 取り残し=("missed", "sum"),
                              秒本=("sec_per_fruit", "mean"))
    g["適期果の収穫率"] = g["適期収穫"] / (g["適期収穫"] + g["取り残し"]).clip(lower=1)
    g["誤収穫の割合"] = g["誤収穫"] / (g["適期収穫"] + g["誤収穫"]).clip(lower=1)
    return g.rename(columns={"秒本": "秒／本（平均）"}).reset_index()


def prob_ai_better(df: pd.DataFrame, draws: int = 20000, seed: int = 0) -> float | None:
    """P(AIの適期果の収穫率 > 人の収穫率)。一様の事前分布 Beta(1,1) から更新し、乱数で比べる。"""
    cm = compare_modes(df).set_index("方式")
    if not {"AI", "人（遠隔）"} <= set(cm.index):
        return None
    rng = np.random.default_rng(seed)
    p = {}
    for m in ["AI", "人（遠隔）"]:
        a, b = tl.beta_posterior(int(cm.loc[m, "適期収穫"]), int(cm.loc[m, "適期収穫"] + cm.loc[m, "取り残し"]))
        p[m] = rng.beta(a, b, draws)
    return float((p["AI"] > p["人（遠隔）"]).mean())


# ============================================================
# ③ 判断する：授業の流れと、実機に進む前の点検
# ============================================================
LESSON_PLANS = {
    "45分（1コマ）": [
        ("導入：安全の段階と今日の問い", 5, "教員", "なぜ最初はシミュレーターなのか"),
        ("人が遠隔で1ラウンド", 12, "生徒（2人1組）", "操作する人・カメラを見て声をかける人に分かれる"),
        ("AIで1ラウンド（同じシード）", 8, "生徒", "緑・黄・赤の枠の意味を読む"),
        ("記録表で比べる", 10, "生徒", "取り残しと誤収穫、どちらが痛いか"),
        ("τ を自分で決めて一言", 10, "生徒→全体", "「自分の農園ならτ＝○○、なぜなら…」"),
    ],
    "90分（2コマ）": [
        ("導入：安全の段階と今日の問い", 10, "教員", "なぜ最初はシミュレーターなのか"),
        ("人が遠隔で1ラウンド（遅延150ms）", 15, "生徒（2人1組）", "役割を交代して2回"),
        ("遅延を600msにしてもう1ラウンド", 10, "生徒", "遅れると何が起きるか、体で知る"),
        ("AIで2ラウンド（遮蔽30%と60%）", 15, "生徒", "葉が増えるとAIは何を見落とすか"),
        ("記録CSVをこのページに貼って比べる", 15, "生徒", "人とAI、ベイズで確かめる"),
        ("τ を自分で決める・実機に進む条件を話し合う", 20, "グループ", "損失の円を自分たちで決める"),
        ("ふり返り", 5, "全体", "AIに任せること・人がやること"),
    ],
}


def lesson_table(name: str) -> pd.DataFrame:
    rows, t = [], 0
    for step, minutes, who, point in LESSON_PLANS[name]:
        rows.append({"開始_分": t, "すること": step, "分": minutes, "だれが": who, "ねらい": point})
        t += minutes
    return pd.DataFrame(rows)


# 次の段階（実機）に進む前の点検。必須が1つでも欠けたら進まない。
NEXT_STAGE_CHECKS = [
    ("受け入れ先がリスクアセスメントを済ませ、生徒が入る範囲を図にしてある", True),
    ("非常停止の位置と使い方を、生徒全員が言える", True),
    ("通信が途切れたら止まることを、実機で確かめてある", True),
    ("暑さ指数（WBGT）の中止基準と、休む場所を決めてある", True),
    ("農薬散布の記録を確かめ、立ち入りできる日である", True),
    ("見守る大人の数が、生徒の数に足りている", True),
    ("ロボットの教示・点検をする大人と、組んで機器を操作する相棒が特別教育を修了し、記録がある（産業用ロボットにあたる場合）", True),
    ("カメラ映像を録画しない・映す範囲を、学校と取り決めてある", True),
    ("保険（傷害・賠償）の範囲を、学校と確かめてある", True),
    ("シミュレーターで、全員が1ラウンド以上を終えている", False),
    ("事前学習で、作物（トマト・キュウリ）の収穫基準を学んでいる", False),
]


def next_stage_readiness(done: Sequence[bool]) -> dict:
    must_missing = [t for (t, must), ok in zip(NEXT_STAGE_CHECKS, done) if must and not ok]
    want_missing = [t for (t, must), ok in zip(NEXT_STAGE_CHECKS, done) if not must and not ok]
    score = sum(done) / len(NEXT_STAGE_CHECKS)
    verdict = ("まだ実機には進まない（必須が欠けています）" if must_missing
               else "実機の段階を受け入れ先と相談できる" if not want_missing
               else "実機に進める。ただし残りを当日までに")
    return {"準備度": score, "判定": verdict, "まだの必須": must_missing, "まだの推奨": want_missing}


ROS2_TELEOP_GUARD = '''# 遠隔操作の見張り役（例：表示するだけ。実機では受け入れ先の安全担当が確かめてから）
# 教室からの指令が TIMEOUT 秒とだえたら、止まれ（速度0）を出し続ける。速さにも上限をかける。
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

TIMEOUT = 0.3      # 秒。遅延の上限（このページの①で計算）より短く
V_MAX = 0.2        # m/s。体験実習では、ふだんより遅くする

class TeleopGuard(Node):
    def __init__(self):
        super().__init__("teleop_guard")
        self.last = self.get_clock().now()
        self.cmd = Twist()
        self.pub = self.create_publisher(Twist, "/rail/cmd_vel", 10)           # ロボットへ
        self.create_subscription(Twist, "/classroom/cmd_vel", self.on_cmd, 10)  # 教室から
        self.create_timer(0.05, self.tick)                                      # 20回／秒で見張る

    def on_cmd(self, msg):
        msg.linear.x = max(-V_MAX, min(V_MAX, msg.linear.x))
        self.cmd, self.last = msg, self.get_clock().now()

    def tick(self):
        quiet = (self.get_clock().now() - self.last).nanoseconds / 1e9
        self.pub.publish(self.cmd if quiet < TIMEOUT else Twist())  # とだえたら止まる

def main():
    rclpy.init()
    rclpy.spin(TeleopGuard())

if __name__ == "__main__":
    main()
'''

# ============================================================
# 6 ロボットを扱う大人の条件（労働安全衛生法：産業用ロボットの特別教育）
# ============================================================
# 生徒は特別教育の対象ではない（教示・点検をさせない）。この節は「受け入れ側の大人」の条件を決めるためのもの。
# 2026年10月時点で確かめた範囲。条文・時間数の最新は e-Gov法令検索・労働基準監督署で確かめる。
ROBOT_LAW = pd.DataFrame([
    {"きまり": "労働安全衛生法 第59条第3項", "中身": "危険・有害な業務に労働者を就かせるとき、事業者は特別教育を行う",
     "ハウスでの読み方": "義務を負うのは受け入れ先（事業者）。相手は働く大人"},
    {"きまり": "安衛則 第36条第31号（教示等）",
     "中身": "可動範囲内で、動作の順序・位置・速度を設定・変更・確認する業務。その人と組んで、可動範囲外で教示に係る機器を操作する業務も含む",
     "ハウスでの読み方": "収穫位置を教える人だけでなく、通路で起動・停止を受け持つ相棒も対象"},
    {"きまり": "安衛則 第36条第32号（検査等）",
     "中身": "運転中に可動範囲内で行う検査・修理・調整とその結果の確認。組んで可動範囲外で機器を操作する業務も含む",
     "ハウスでの読み方": "止めてから行う刃の交換・清掃は、第150条の5（起動装置の施錠・表示）で守る"},
    {"きまり": "安全衛生特別教育規程 第18条・第19条", "中身": "教示等・検査等の特別教育の科目と時間（学科・実技）",
     "ハウスでの読み方": "下の表。時間は「以上」"},
    {"きまり": "安衛則 第37条・第38条", "中身": "十分な知識・技能がある人は科目を省略できる／受講者・科目の記録を3年間保存する",
     "ハウスでの読み方": "修了証の確認と記録の保存は受け入れ先の仕事"},
    {"きまり": "昭和58年労働省告示第51号", "中身": "駆動用原動機の定格出力が80W以下の機械、一つの動作を単調に繰り返す機械などは「産業用ロボット」から除く",
     "ハウスでの読み方": "収穫ロボがそもそも対象かを、まずカタログで確かめる。対象外でも危険は残る"},
    {"きまり": "安衛則 第150条の3", "中身": "教示等のときの措置（作業規程、異常時にすぐ止められる措置、作業中の表示）",
     "ハウスでの読み方": "教示モードの速さの上限（ISO 10218-1：250 mm/s）と合わせて考える"},
    {"きまり": "安衛則 第150条の4・平成25年 基発1224第2号", "中身": "運転中の接触防止（柵など）。リスクアセスメントで危険のおそれがないと評価できれば協働運転ができる",
     "ハウスでの読み方": "段3「実機のそば」は、この評価と記録が前提"},
])

TOKUBETSU_HOURS = pd.DataFrame([
    ("教示等（第31号）", "学科", "産業用ロボットに関する知識", 2),
    ("教示等（第31号）", "学科", "産業用ロボットの教示等の作業に関する知識", 4),
    ("教示等（第31号）", "学科", "関係法令", 1),
    ("教示等（第31号）", "実技", "産業用ロボットの操作の方法", 1),
    ("教示等（第31号）", "実技", "産業用ロボットの教示等の作業の方法", 2),
    ("検査等（第32号）", "学科", "産業用ロボットに関する知識", 4),
    ("検査等（第32号）", "学科", "産業用ロボットの検査等の作業に関する知識", 4),
    ("検査等（第32号）", "学科", "関係法令", 1),
    ("検査等（第32号）", "実技", "産業用ロボットの操作の方法", 1),
    ("検査等（第32号）", "実技", "産業用ロボットの検査等の作業の方法", 3),
], columns=["区分", "種別", "科目", "時間（以上）"])

TEACH_MODE_SPEED = 0.25  # m/s：教示モードの速さの上限（ISO 10218-1 の 250 mm/s）


def is_industrial_robot(power_w: float, manipulator: bool = True, memory: bool = True,
                        single_motion: bool = False, in_development: bool = False) -> dict:
    """その収穫ロボが、安衛則でいう「産業用ロボット」にあたるか（教育用の目安。最終確認はメーカー・労基署）。"""
    if not (manipulator and memory):
        return {"あたるか": False, "理由": "マニプレータと記憶装置の両方がない（定義にあてはまらない）"}
    if in_development:
        return {"あたるか": False, "理由": "研究開発中のものは定義から除かれる。ただし体験実習に使うなら同じ水準で守る"}
    if power_w <= 80:
        return {"あたるか": False, "理由": "定格出力80W以下（告示第51号）。特別教育の義務はないが、危険は残る"}
    if single_motion:
        return {"あたるか": False, "理由": "一つの動作を単調に繰り返すだけ（告示第51号）"}
    return {"あたるか": True, "理由": "定格出力80W超で、マニプレータと記憶装置をもつ。教示等・検査等には特別教育が要る"}


# 作業 → (区分, 説明, どの段で起こるか)
HARVEST_TASKS = {
    "収穫の位置・動作の順序を教える（ペンダントで、可動範囲内）":
        ("教示等（第31号）", "教示等の本体", "準備（生徒が来る前）"),
    "教える人と組み、通路（可動範囲外）で起動・非常停止を受け持つ":
        ("教示等（第31号）", "「組んで可動範囲外で機器を操作」にあたる", "準備（生徒が来る前）"),
    "運転中にレール上でハンドの位置を点検・調整する":
        ("検査等（第32号）", "検査等の本体", "準備（生徒が来る前）"),
    "点検する人と組み、可動範囲外で機器を操作する":
        ("検査等（第32号）", "「組んで可動範囲外で機器を操作」にあたる", "準備（生徒が来る前）"),
    "止めて鍵と表示をしてから、刃の交換・清掃をする":
        (None, "特別教育の対象外。第150条の5の措置（起動装置の施錠・表示）で守る", "準備（生徒が来る前）"),
    "教室から遠隔で走行・収穫ボタンを押す（ハウスに人がいない）":
        (None, "教示ではなく運転。ハウスに人がいるときは行わない（2 ① 計算するの距離）", "段1"),
    "ロボットを止めて電源を切ったハウスを見学する":
        (None, "特別教育の対象外。温湯管・暑さ・農薬の対策が中心", "段2"),
    "線の外から運転を見る（機器にさわらない）":
        (None, "特別教育の対象外。非常停止を受け持つなら「組んで機器を操作」にあたるか受け入れ先で判断する", "段3"),
}


def training_need(task: str, robot: bool = True, is_worker: bool = True) -> dict:
    """その人・その作業に、産業用ロボットの特別教育が要るか。"""
    kind, why, stage = HARVEST_TASKS[task]
    if not robot:
        return {"判定": "対象外（産業用ロボットにあたらない）", "区分": None, "時間": 0, "段": stage,
                "理由": "特別教育の義務はない。リスクアセスメントと作業手順は同じように行う"}
    if kind is None:
        return {"判定": "対象外（この作業）", "区分": None, "時間": 0, "段": stage, "理由": why}
    hours = int(TOKUBETSU_HOURS.loc[TOKUBETSU_HOURS["区分"] == kind, "時間（以上）"].sum())
    if not is_worker:
        return {"判定": "生徒にはさせない作業", "区分": kind, "時間": hours, "段": stage,
                "理由": f"{why}。特別教育は事業者が働く人に行うもの。修了した大人が、生徒が来る前に済ませる"}
    return {"判定": "特別教育が必要", "区分": kind, "時間": hours, "段": stage, "理由": why}


def staff_training_plan(teachers: int, partners: int, inspectors: int, backup: int = 1) -> pd.DataFrame:
    """受け入れ先の大人が受ける特別教育の延べ時間。休みに備えて予備（backup）を区分ごとに足す。"""
    hours = TOKUBETSU_HOURS.groupby("区分")["時間（以上）"].sum()
    rows = []
    for kind, n in [("教示等（第31号）", teachers + partners), ("検査等（第32号）", inspectors)]:
        people = n + (backup if n > 0 else 0)
        rows.append({"区分": kind, "受ける人数": people, "1人あたり_時間": int(hours[kind]),
                     "延べ_時間": people * int(hours[kind])})
    return pd.DataFrame(rows)


# 段ごとの役割：生徒・見守る大人・ロボットを扱う大人
STAGE_ROLES = pd.DataFrame([
    {"段階": STAGES[0], "生徒": "シミュレーターで遠隔操作とAIを比べる", "見守る大人": "教員",
     "ロボットを扱う大人": "いらない", "特別教育の修了者": "いらない"},
    {"段階": STAGES[1], "生徒": "教室から走行・収穫ボタンを押す", "見守る大人": "教員",
     "ロボットを扱う大人": "受け入れ先がハウスの外で監視（ハウス内は無人）", "特別教育の修了者": "事前の教示・点検をした人"},
    {"段階": STAGES[2], "生徒": "通路を歩いて見学・質問", "見守る大人": "教員＋受け入れ先",
     "ロボットを扱う大人": "電源を切り、起動装置に鍵と表示", "特別教育の修了者": "（止めているので運転はない）"},
    {"段階": STAGES[3], "生徒": "線の外から運転を見る・収穫した果実を確かめる", "見守る大人": "教員＋受け入れ先",
     "ロボットを扱う大人": "非常停止のそばで運転を受け持つ", "特別教育の修了者": "教示・点検とその相棒は修了者だけ"},
])


ROS2_TELEOP_PERMIT = '''# 遠隔操作の「許可」を出すノード（例：表示するだけ。安全機能ではない）
# ハウスに人がいるとき、または受け入れ先の修了者が許可していないときは、教室からの操作を通さない。
# 止める仕組みは、ロボット本体の非常停止とモード切替、5 の見張り役（ウォッチドッグ）で行う。
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String
from geometry_msgs.msg import Twist

TRAINED = {"staff_01", "staff_02"}   # 特別教育の修了者ID（記録は3年保存）。名前は持たない

class TeleopPermit(Node):
    def __init__(self):
        super().__init__("teleop_permit")
        self.person_in_house = True        # わからないときは「いる」とみなす
        self.approver = ""
        self.pub = self.create_publisher(Twist, "/classroom/cmd_vel_permitted", 10)
        self.log = self.create_publisher(String, "/audit/teleop", 10)
        self.create_subscription(Bool, "/house/person_detected", self.on_person, 10)  # 人感センサ・入口の記録
        self.create_subscription(String, "/house/approver_id", self.on_approver, 10)  # 修了者のICカード
        self.create_subscription(Twist, "/classroom/cmd_vel", self.on_cmd, 10)

    def on_person(self, msg):
        self.person_in_house = msg.data

    def on_approver(self, msg):
        self.approver = msg.data
        self.log.publish(String(data=f"approver={msg.data},trained={msg.data in TRAINED}"))

    def on_cmd(self, msg):
        ok = (not self.person_in_house) and (self.approver in TRAINED)
        self.pub.publish(msg if ok else Twist())   # 許可がなければ止まれ（速度0）

def main():
    rclpy.init()
    rclpy.spin(TeleopPermit())
'''


# 実例（調べた範囲。出典はページの「出典・参考」に）
CASES = pd.DataFrame([
    {"型": "遠隔収穫の出前授業", "実施": "AGRIST × 千葉県館山市の小学校", "内容": "茨城県の農場のキュウリ収穫ロボットを、教室から遠隔操作"},
    {"型": "遠隔収穫の出前授業", "実施": "AGRIST × 千葉県の小学校（3・4年生 約100名、90分）",
     "内容": "説明25分 → 収穫体験40分（モニター投影・タッチパネル操作）→ 質疑とまとめ"},
    {"型": "遠隔収穫の出前授業", "実施": "AGRIST × 鹿児島市の幼稚園", "内容": "埼玉県の農場のロボットを遠隔操作。各クラスのモニターで共有"},
    {"型": "ロボット競技会", "実施": "トマトロボット競技会（高校ロボコン部が出場）", "内容": "決勝は実際のビニルハウス。日光で画像処理が難しくなる"},
])


# ============================================================
# 自己チェック
# ============================================================
if __name__ == "__main__":
    # 安全の段階：シミュレーターは物理的な危険がなく、段が進むほどリスクが増える
    ss = stage_summary()
    assert ss.loc[0, "いちばん高い点"] < 4 and ss.loc[3, "いちばん高い点"] >= 8
    assert list(ss["リスク点の合計"]) == sorted(ss["リスク点の合計"]), ss
    assert set(HAZARDS["対策の種類"]) <= set(STEP3)
    assert risk_level(0) == "なし" and risk_level(12).startswith("高")
    # ① 遅延：0.4 m/s で 150 ms → 6 cm。届く範囲 7 cm を超えない上限は 175 ms
    assert abs(latency_overshoot(150) - 0.06) < 1e-9
    assert abs(max_safe_latency() - 175) < 1e-9
    assert latency_curve()["走行で余分に進む_cm"].is_monotonic_increasing
    # 遠隔では気づくまでの時間に遅延が足され、距離が長くなる
    assert remote_distance(0.5, 300)["合計（これより近づいたら止める）"] > remote_distance(0.5, 0)["合計（これより近づいたら止める）"]
    assert abs(remote_distance(0.0, 0)["合計（これより近づいたら止める）"] - 0.84) < 1e-9
    # 判定モデル：葉が増えると収穫率が下がる。τ を上げると誤収穫は減る
    oc = occlusion_curve(0.55)
    assert oc["適期果の収穫率"].iloc[0] > 0.8 > oc["適期果の収穫率"].iloc[-1]
    assert simulate(0.3, 0.8)["FP"] <= simulate(0.3, 0.4)["FP"]
    r = simulate(0.3, 0.55)
    assert r["TP"] + r["FN"] + r["FP"] + r["TN"] == r["n"]
    # 誤収穫が高くつくほど、最適な τ は上がる（または同じ）
    t_lo, _ = best_tau(0.4, 100, 10)
    t_hi, _ = best_tau(0.4, 10, 100)
    assert t_hi >= t_lo, (t_lo, t_hi)
    # ② 記録CSV
    df = parse_records(SAMPLE_CSV)
    assert len(df) == 5 and set(df["方式"]) == {"AI", "人（遠隔）"}
    cm = compare_modes(df).set_index("方式")
    assert cm.loc["AI", "適期果の収穫率"] > cm.loc["人（遠隔）", "適期果の収穫率"]
    assert prob_ai_better(df) > 0.95
    assert prob_ai_better(df[df["方式"] == "AI"]) is None
    try:
        parse_records("a,b\n1,2")
        raise AssertionError("列の足りないCSVを通してしまった")
    except ValueError:
        pass
    bad = parse_records(SAMPLE_CSV + '6,AI,0.3,"x",-1,0,3,1\n7,AI,0.3,"x",abc,0,3,1\n')
    assert len(bad) == 5
    # ③ 授業の流れ：45分と90分ちょうど
    assert lesson_table("45分（1コマ）")["分"].sum() == 45
    assert lesson_table("90分（2コマ）")["分"].sum() == 90
    ok = next_stage_readiness([True] * len(NEXT_STAGE_CHECKS))
    assert ok["判定"].startswith("実機の段階") and ok["準備度"] == 1
    one = next_stage_readiness([i != 2 for i in range(len(NEXT_STAGE_CHECKS))])
    assert one["判定"].startswith("まだ") and len(one["まだの必須"]) == 1
    # 大人の条件：時間は教示等10h・検査等13h。80W以下は産業用ロボットにあたらない
    h = TOKUBETSU_HOURS.groupby("区分")["時間（以上）"].sum()
    assert h["教示等（第31号）"] == 10 and h["検査等（第32号）"] == 13
    assert is_industrial_robot(400)["あたるか"] and not is_industrial_robot(60)["あたるか"]
    assert not is_industrial_robot(400, memory=False)["あたるか"]
    tasks = list(HARVEST_TASKS)
    assert training_need(tasks[0])["判定"] == "特別教育が必要"
    assert training_need(tasks[1])["区分"] == "教示等（第31号）"           # 通路で操作する相棒も対象
    assert training_need(tasks[0], is_worker=False)["判定"].startswith("生徒には")
    assert training_need(tasks[4])["区分"] is None                        # 止めてからの刃の交換は対象外
    assert training_need(tasks[0], robot=False)["判定"].startswith("対象外（産業用")
    assert all(HARVEST_TASKS[t][0] is None for t in tasks if HARVEST_TASKS[t][2] != "準備（生徒が来る前）")  # 生徒のいる段に教示・検査はない
    sp = staff_training_plan(1, 1, 0)
    assert sp.set_index("区分").loc["教示等（第31号）", "延べ_時間"] == 30 and sp["受ける人数"].iloc[1] == 0
    assert list(STAGE_ROLES["段階"]) == STAGES
    assert remote_distance(TEACH_MODE_SPEED, 0)["合計（これより近づいたら止める）"] > remote_distance(0.0, 0)["合計（これより近づいたら止める）"]
    print("harvest_lab.py：自己チェック OK")

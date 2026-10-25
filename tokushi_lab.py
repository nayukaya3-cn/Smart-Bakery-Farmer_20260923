"""
tokushi_lab.py — 探究コーナー「AI活用による特別支援教育・訓練への可能性」の計算部品

画面は pages/20_🧩_AI×特別支援教育.py。`python tokushi_lab.py` で自己チェック。

問い
  特別支援学校 高等部の「産業現場等における実習」の受け入れ先として、パン工房と畑を開くとき、
  生成AI・フィジカルAI（ROS2のロボット）・ベイズ推論・因果推論・強化学習は、どこで役に立ち、どこで使ってはいけないか。

骨格（リポジトリ共通）：① 計算する → ② 可視化する → ③ 自分の条件で判断する
  ① 制度の枠を数える   … 実習の回数は法令で決まっていない。年間の授業時数（標準）の中で、実習が占める割合を計算する
  ② 工程を切り出す     … パンの工程を危険と負担で表し、人・ロボット・生成AIの分担を決める。ロボットとの距離を計算する
  ③ 生成AIの使いどころ … 生成モデルの種類と、手順カードの下書き（読みやすさは fukushi_ai の物差しで測る）
  ④ 伸びを確かめる     … 工程ごとの「自分でできる確率」をベイズで更新し、支援を減らす候補を出す（トンプソン抽出）
  ⑤ 何が効いたか       … 手順カードの形（文字・写真・動画）の効果を、慣れ（練習回数）で調整して推定する
  ⑥ 受け入れの判断     … 受け入れ側の準備を点検し、足りないものを並べる

方針
  - このページも部品も、外部の生成AIを呼び出さない。ロボットも動かさない（ROS2のコードは表示するだけ）。
  - 初期表示のデータはすべて架空。生徒は「Aさん」などの仮名。障害の種類や診断名は扱わない。
  - 判定の境目は仮置き。決めるのは教員と本人。AIの出す数は「話し合いの材料」にとどめる。
  - 安全の計算は教育用の単純化。実際のロボットの配置はリスクアセスメントで決める。
"""
from __future__ import annotations

import re
from collections.abc import Sequence

import numpy as np
import pandas as pd

import fukushi_ai as fa  # 読みやすさ・個人情報の物差しは福祉×生成AIと共通にする

# ============================================================
# ① 制度の枠を数える
# ============================================================
# 法令の階層（2026年10月時点で確認した範囲。最新は文部科学省・県教委で確かめる）
LAW_LAYERS = pd.DataFrame([
    {"階層": "学校教育法 第72条", "決めていること": "特別支援学校の目的（準ずる教育＋自立に必要な知識技能）", "実習の回数": "規定なし"},
    {"階層": "学校教育法施行規則 第128〜131条", "決めていること": "高等部の教育課程の構成（各教科・自立活動など）", "実習の回数": "規定なし"},
    {"階層": "授業時数の標準（学習指導要領・各県の規則）", "決めていること": "年35週・週30単位時間。知的障害の特別支援学校は各学年1,050単位時間が標準",
     "実習の回数": "総枠だけ"},
    {"階層": "特別支援学校高等部学習指導要領（告示）", "決めていること": "地域・産業界と連携し、産業現場等における長期間の実習を取り入れるなど就業体験の機会を積極的に設ける",
     "実習の回数": "「積極的に」（数値なし）"},
    {"階層": "各学校の教育課程", "決めていること": "実習の回数・期間・時期・どの教科等に位置づけるか", "実習の回数": "ここで決まる"},
])

ANNUAL_HOURS = 1050   # 知的障害の特別支援学校 高等部：各学年の総授業時数の標準（単位時間）
UNIT_MIN = 50         # 1単位時間は50分が標準

# 公開資料で確認できた運用例（学校によって大きく違う）
PRACTICE_EXAMPLES = {
    "例1：3年間で6回（1回5〜14日）": {"1年": (2, 5), "2年": (2, 10), "3年": (2, 14)},
    "例2：各学年1回・10日": {"1年": (1, 10), "2年": (1, 10), "3年": (1, 10)},
}


def practicum_hours(times: int, days: int, hours_per_day: float = 6.0) -> float:
    """実習の時間（単位時間）。1日 hours_per_day 時間 → 単位時間に換算（50分＝1単位時間）。"""
    return times * days * hours_per_day * 60 / UNIT_MIN


def practicum_plan(plan: dict[str, tuple[int, int]], hours_per_day: float = 6.0,
                   annual: int = ANNUAL_HOURS) -> pd.DataFrame:
    """学年ごとの実習日数・単位時間・年間授業時数に占める割合。plan = {"1年": (回数, 1回の日数), ...}"""
    rows = []
    for grade, (times, days) in plan.items():
        h = practicum_hours(times, days, hours_per_day)
        rows.append({"学年": grade, "回数": times, "1回の日数": days, "実習日数": times * days,
                     "単位時間": round(h, 1), "年間授業時数に占める割合": h / annual})
    df = pd.DataFrame(rows)
    total = {"学年": "3年間の合計", "回数": int(df["回数"].sum()), "1回の日数": np.nan,
             "実習日数": int(df["実習日数"].sum()), "単位時間": round(float(df["単位時間"].sum()), 1),
             "年間授業時数に占める割合": float(df["単位時間"].sum()) / (annual * len(plan))}
    return pd.concat([df, pd.DataFrame([total])], ignore_index=True)


def host_capacity(students_per_term: int, terms_per_year: int, staff: int, ratio: int = 2) -> dict:
    """受け入れ側の上限：大人1人が見られる生徒の数（ratio）で決まる。"""
    per_term = min(students_per_term, staff * ratio)
    return {"1回に受け入れられる人数": per_term, "年間の延べ人数": per_term * terms_per_year,
            "人手が足りない": students_per_term > staff * ratio}


# ============================================================
# ② 工程を切り出す（パン工房・畑）
# ============================================================
# 0〜3 の目安（この工房の作業。現場で書きかえる）
STEPS = pd.DataFrame([
    {"工程": "小麦畑の草とり", "熱": 0, "刃物・挟まれ": 0, "重さ": 1, "衛生": 0, "判断": 1, "手順の数": 2, "時間_分": 30},
    {"工程": "材料の計量（粉・水・塩・酵母）", "熱": 0, "刃物・挟まれ": 0, "重さ": 1, "衛生": 2, "判断": 1, "手順の数": 4, "時間_分": 20},
    {"工程": "ミキサーでこねる", "熱": 0, "刃物・挟まれ": 3, "重さ": 2, "衛生": 2, "判断": 2, "手順の数": 3, "時間_分": 15},
    {"工程": "発酵の見張り（温度と時間を記録）", "熱": 0, "刃物・挟まれ": 0, "重さ": 0, "衛生": 1, "判断": 2, "手順の数": 2, "時間_分": 60},
    {"工程": "分割・計量（スケッパー）", "熱": 0, "刃物・挟まれ": 1, "重さ": 0, "衛生": 2, "判断": 1, "手順の数": 3, "時間_分": 20},
    {"工程": "丸め・成形", "熱": 0, "刃物・挟まれ": 0, "重さ": 0, "衛生": 2, "判断": 2, "手順の数": 4, "時間_分": 30},
    {"工程": "天板に並べる", "熱": 0, "刃物・挟まれ": 0, "重さ": 1, "衛生": 2, "判断": 1, "手順の数": 2, "時間_分": 10},
    {"工程": "窯で焼く（230℃）", "熱": 3, "刃物・挟まれ": 1, "重さ": 2, "衛生": 1, "判断": 3, "手順の数": 3, "時間_分": 25},
    {"工程": "窯から出す・天板を運ぶ", "熱": 3, "刃物・挟まれ": 0, "重さ": 3, "衛生": 1, "判断": 1, "手順の数": 2, "時間_分": 10},
    {"工程": "冷ます・数と焼き色を確かめる", "熱": 1, "刃物・挟まれ": 0, "重さ": 0, "衛生": 2, "判断": 2, "手順の数": 2, "時間_分": 20},
    {"工程": "袋詰め・ラベル貼り", "熱": 0, "刃物・挟まれ": 0, "重さ": 0, "衛生": 2, "判断": 1, "手順の数": 4, "時間_分": 30},
    {"工程": "器具を洗う・床の清掃", "熱": 1, "刃物・挟まれ": 2, "重さ": 1, "衛生": 2, "判断": 1, "手順の数": 3, "時間_分": 20},
])
HAZARD_COLS = ["熱", "刃物・挟まれ", "重さ"]

ROLES = {
    "ロボット・大人": "危険が大きい。ロボット（または大人）が担当し、生徒は見学や記録にまわる",
    "大人と一緒": "危険が中くらい。大人がそばにつき、ロボットとは作業エリアを分ける",
    "生徒": "危険が小さい。生徒が担当する（支援の量は ④ で決める）",
}


def allocate(steps: pd.DataFrame, robot_max: int = 3, together_min: int = 2, card_min_steps: int = 4,
             card_min_judge: int = 2) -> pd.DataFrame:
    """工程ごとの分担。危険（熱・刃物・重さの最大）で人とロボットを分け、手順や判断が多い工程には手順カードを付ける。"""
    out = steps.copy()
    out["危険"] = out[HAZARD_COLS].max(axis=1)

    def role(h: int) -> str:
        if h >= robot_max:
            return "ロボット・大人"
        if h >= together_min:
            return "大人と一緒"
        return "生徒"

    out["分担"] = out["危険"].map(role)
    out["手順カード"] = np.where((out["手順の数"] >= card_min_steps) | (out["判断"] >= card_min_judge), "あり（写真＋音声）", "なくてよい")
    out["生徒の時間_分"] = np.where(out["分担"] == "生徒", out["時間_分"], 0)
    return out


def allocation_summary(alloc: pd.DataFrame) -> pd.DataFrame:
    return (alloc.groupby("分担", as_index=False)
            .agg(工程の数=("工程", "count"), 時間_分=("時間_分", "sum"))
            .sort_values("時間_分", ascending=False, ignore_index=True))


# ロボットとの距離（速度と間隔の監視：ISO/TS 15066 の考え方を教育用に単純化）
#   S = 人の移動 v_h(T_r+T_s) ＋ ロボットの反応中の移動 v_r T_r ＋ 止まるまでの距離 S_s ＋ 余裕 C
#   S_s は一定の減速と考えて v_r T_s / 2。v_h=1.6 m/s は歩く人の速さの目安（ISO 13855）
def protective_distance(v_r: float, t_react: float = 0.1, t_stop: float = 0.3, v_h: float = 1.6,
                        margin: float = 0.2) -> dict:
    s_h = v_h * (t_react + t_stop)
    s_r = v_r * t_react
    s_s = v_r * t_stop / 2
    return {"人が近づく距離": s_h, "ロボットが反応中に進む距離": s_r, "ロボットが止まるまでの距離": s_s,
            "余裕": margin, "合計（これより近づいたら止める）": s_h + s_r + s_s + margin}


def distance_curve(t_react: float = 0.1, t_stop: float = 0.3, v_h: float = 1.6, margin: float = 0.2,
                   speeds: Sequence[float] = tuple(np.round(np.arange(0.0, 1.55, 0.1), 2))) -> pd.DataFrame:
    rows = []
    for v in speeds:
        d = protective_distance(v, t_react, t_stop, v_h, margin)
        rows.append({"ロボットの速さ_m/s": v, "必要な距離_m": d["合計（これより近づいたら止める）"]})
    return pd.DataFrame(rows)


ROS2_EXAMPLE = '''# 工程が終わったら、次の手順カードを出すノード（例：表示するだけ。実機では安全の確認が先）
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

CARDS = ["1. 手を洗う", "2. 粉を はかりに のせる", "3. 300g に なったら 止める"]

class StepGuide(Node):
    def __init__(self):
        super().__init__("step_guide")
        self.i = 0
        self.pub = self.create_publisher(String, "/guide/card", 10)          # プロジェクター・タブレットへ
        self.create_subscription(Bool, "/vision/step_done", self.on_done, 10)  # カメラの判定（AIは「案」）
        self.create_subscription(Bool, "/safety/human_near", self.on_near, 10) # 人が近い → 案内より安全が先

    def on_near(self, msg):
        if msg.data:
            self.pub.publish(String(data="とまって。せんせいを よんでね"))

    def on_done(self, msg):
        if msg.data and self.i < len(CARDS) - 1:
            self.i += 1
        self.pub.publish(String(data=CARDS[self.i]))

def main():
    rclpy.init()
    rclpy.spin(StepGuide())

if __name__ == "__main__":
    main()
'''

# ============================================================
# ③ 生成AIの使いどころ
# ============================================================
# 『生成 Deep Learning 第2版』（David Foster 著、O'Reilly Japan、2024）の章立てを手がかりに、
# 生成モデルの種類ごとに特別支援教育での使いどころと注意を並べる（使いどころ・注意はこのページの整理）
GEN_MODELS = pd.DataFrame([
    {"章": "3章 変分オートエンコーダ（VAE）", "得意なこと": "ふだんの形を覚え、そこから外れたものを見つける",
     "使いどころ": "パンの形・焼き色の「いつもと違う」を見つけ、生徒の検品を助ける", "注意": "外れた＝不良とは限らない。最後は人が見る"},
    {"章": "4章・10章 敵対的生成ネットワーク（GAN）", "得意なこと": "本物らしい画像をつくる",
     "使いどころ": "検品の練習用に、焼きむら・形くずれの画像を増やす", "注意": "実在の人の顔をつくらない・使わない"},
    {"章": "5章 自己回帰モデル／9章 トランスフォーマ", "得意なこと": "文章を一語ずつ続けて書く（大規模言語モデル）",
     "使いどころ": "手順書をやさしい日本語・ルビ付きに書きかえる。実習日誌の振り返りの言葉を一緒に探す",
     "注意": "数や温度を書きかえることがある → ③の照合が必要。個人情報を貼らない"},
    {"章": "6章 正規化フロー／7章 エネルギーベースモデル", "得意なこと": "データの起こりやすさ（確率）を計算する",
     "使いどころ": "発酵の温度・時間の記録で、起こりにくい値に気づく", "注意": "教材としては高度。考え方の紹介にとどめる"},
    {"章": "8章 拡散モデル", "得意なこと": "ことばから絵をつくる",
     "使いどころ": "手順カードの絵（ピクトグラム風）・販促POPの素材", "注意": "既存のキャラクター・作品に似せない。公開前に人が確認"},
    {"章": "11章 音楽生成", "得意なこと": "メロディやリズムをつくる",
     "使いどころ": "工程の切りかえを知らせる短い合図の音、作業時間の目安になるBGM", "注意": "音が苦手な生徒には使わない（本人に聞く）"},
    {"章": "12章 世界モデル", "得意なこと": "環境をまねた「夢の中」で行動を練習する",
     "使いどころ": "ロボットの動きをシミュレーション（Isaac Simなど）で確かめてから実機へ", "注意": "シミュレーションと実機の差（sim-to-real）は残る"},
    {"章": "13章 マルチモーダルモデル", "得意なこと": "画像・文章・音声をまとめて扱う",
     "使いどころ": "作業の写真から「次の手順」を音声で案内する。写真から日誌のタグ案をつくる",
     "注意": "顔・名札が写った写真はAIに送らない"},
])

CARD_NEEDS = ["1つの文に1つの動作", "漢字にふりがな（ルビ）をつける", "写真を撮る場所を（写真：…）で示す",
              "数はアラビア数字で大きく", "ほめる言葉を最後に1つ", "音声で読み上げやすい文"]


def build_card_prompt(step: str, facts: str, needs: Sequence[str], n_steps: int = 5) -> str:
    """生成AIに貼る、実習用の手順カードの指示文。名前・障害名・診断を入れる欄は作らない。"""
    need_txt = "\n".join(f"- {n}" for n in needs) or "- とくになし"
    return (
        "あなたは、パン工房ではじめて実習をする高校生のための「手順カード」を書く係です。\n"
        f"工程：{step}\n"
        f"現場で決まっていること（数・温度・時間を変えないこと）：{facts or '（なし）'}\n"
        "書き方のきまり：\n"
        f"- 手順は {n_steps} つまで。1. 2. 3. と番号をつける\n"
        "- 1文は20字くらいまで。むずかしい言葉は使わず、使うときは（）で言いかえる\n"
        "- いちばん最初に「安全のこと」（手洗い・手袋・やけど・休憩など）を書く\n"
        "- 「こまったら、だれに、なんと言うか」を最後に1行書く\n"
        "- 分からないことは作らずに「（先生に確かめる）」と書く\n"
        "読み手に合わせてほしいこと：\n"
        f"{need_txt}\n"
        "出力はカードの本文だけにしてください。"
    )


SAMPLE_FACTS = "強力粉300g、水195g、塩6g、ドライイースト3g。ボウルに入れる順番は 粉→塩→イースト→水。"
SAMPLE_CARD_BAD = ("材料の計量は、衛生管理に留意しつつ、適宜はかりの風袋引きを実施したうえで、強力粉300g、水195g、"
                   "塩6g、ドライイースト3gを速やかに計量し、所定の順序でボウルに投入すること。")
SAMPLE_CARD_GOOD = ("1. 手を洗う。手袋をつける。\n2. ボウルを はかりに のせる。\n3. ゼロの ボタンを おす。\n"
                    "4. 粉を 300g いれる。\n5. 塩 6g、イースト 3g、水 195g の じゅんに いれる。\n"
                    "こまったら：先生に「つぎは なに？」と言う。")


def card_check(card: str, facts: str = SAMPLE_FACTS) -> dict:
    """読みやすさ（fukushi_ai と同じ物差し）＋ 数の照合（生成AIが数を変えていないか）。"""
    r = fa.readability(card)
    body = re.sub(r"(?m)^\s*[0-9０-９]+[.．)）]\s*", "", card)  # 手順の番号は数として数えない
    fc = fa.fact_check(facts, body)
    return {"読みやすさ": r, "気になる点": fa.readability_flags(r, max_avg=20, max_len=35),
            "足された数": fc["足された数"], "落ちた数": fc["落ちた数"]}


# ============================================================
# ④ 伸びを確かめる（ベイズ推論＋トンプソン抽出）
# ============================================================
# 支援は多い順（最大から最小へ）。数字が大きいほど支援が少ない
SUPPORT = ["全面の手助け", "見本を見せる", "指さし・合図", "ことばで声かけ", "見守り（自分で）"]


def sample_trials(seed: int = 3, sessions: int = 12, per_day: int = 4) -> pd.DataFrame:
    """架空の記録：3工程 × 実習日。教員は「直近2日で4分の3以上できたら支援を1段減らす、
    その日ほとんどできなかったら1段戻す」という決まりで支援を変えた想定。"""
    rng = np.random.default_rng(seed)
    # 真の「自分でできる確率」＝ 工程の基礎 ＋ 支援の量 ＋ 慣れ（架空）
    base = {"材料の計量": 0.30, "丸め・成形": 0.05, "袋詰め・ラベル貼り": 0.45}
    rows = []
    for step, b in base.items():
        level, hist = 0, []
        for day in range(1, sessions + 1):
            p = float(np.clip(b + 0.12 * (len(SUPPORT) - 1 - level) + 0.025 * day, 0.02, 0.98))
            ok = [int(rng.random() < p) for _ in range(per_day)]
            rows += [{"実習日": day, "工程": step, "支援": SUPPORT[level], "成功": o} for o in ok]
            hist.append((level, sum(ok)))
            last2 = [k for lv, k in hist[-2:] if lv == level]
            if len(last2) == 2 and sum(last2) >= 0.75 * 2 * per_day and level < len(SUPPORT) - 1:
                level += 1
            elif sum(ok) <= per_day // 4 and level > 0:
                level -= 1
    return pd.DataFrame(rows)


def beta_posterior(successes: int, n: int, a0: float = 1.0, b0: float = 1.0) -> tuple[float, float]:
    return a0 + successes, b0 + (n - successes)


def prob_above(a: float, b: float, threshold: float, draws: int = 20000, seed: int = 0) -> float:
    """P(p > threshold)。scipy を使わず、乱数で近似する（教材として中が見えるように）。"""
    rng = np.random.default_rng(seed)
    return float((rng.beta(a, b, draws) > threshold).mean())


def posterior_table(trials: pd.DataFrame, threshold: float = 0.8, recent_days: int = 3) -> pd.DataFrame:
    """工程ごと、いまの支援レベルで「自分でできる確率」の事後分布。直近 recent_days 日の記録で見る。"""
    rows = []
    for step, g in trials.groupby("工程", sort=False):
        last = g["実習日"].max()
        cur = g[g["実習日"] > last - recent_days]
        level = cur["支援"].iloc[-1]
        cur = cur[cur["支援"] == level]
        a, b = beta_posterior(int(cur["成功"].sum()), len(cur))
        p_hi = prob_above(a, b, threshold)
        mean = a / (a + b)
        if p_hi > 0.7 and SUPPORT.index(level) < len(SUPPORT) - 1:
            hint = f"支援を1段減らす候補 →「{SUPPORT[SUPPORT.index(level) + 1]}」"
        elif mean < 0.5 and SUPPORT.index(level) > 0:
            hint = f"支援を1段戻す候補 →「{SUPPORT[SUPPORT.index(level) - 1]}」"
        else:
            hint = "いまの支援を続ける"
        rows.append({"工程": step, "いまの支援": level, "回数": len(cur), "成功": int(cur["成功"].sum()),
                     "a": a, "b": b, "平均": mean, f"P(できる確率>{threshold:.0%})": p_hi, "話し合いの材料": hint})
    return pd.DataFrame(rows)


def beta_pdf(a: float, b: float, x: np.ndarray) -> np.ndarray:
    from math import lgamma
    logc = lgamma(a + b) - lgamma(a) - lgamma(b)
    x = np.clip(x, 1e-9, 1 - 1e-9)
    return np.exp(logc + (a - 1) * np.log(x) + (b - 1) * np.log(1 - x))


def thompson_suggest(trials: pd.DataFrame, step: str, target: float = 0.8, seed: int = 0,
                     rounds: int = 2000) -> pd.DataFrame:
    """トンプソン抽出（多腕バンディット）：各支援レベルの成功率を事後分布から引き、
    「target を超える中で、いちばん支援が少ないレベル」が選ばれる割合を数える。記録のないレベルは Beta(1,1)。"""
    rng = np.random.default_rng(seed)
    g = trials[trials["工程"] == step]
    ab = []
    for lv in SUPPORT:
        s = g[g["支援"] == lv]
        ab.append(beta_posterior(int(s["成功"].sum()), len(s)))
    count = np.zeros(len(SUPPORT))
    for _ in range(rounds):
        p = np.array([rng.beta(a, b) for a, b in ab])
        ok = np.where(p >= target)[0]
        count[ok.max() if len(ok) else int(p.argmax())] += 1
    return pd.DataFrame({"支援": SUPPORT, "記録の数": [int(a + b - 2) for a, b in ab],
                         "次に選ばれる割合": count / rounds})


# ============================================================
# ⑤ 何が効いたか（因果推論：慣れによる見かけの差を取りのぞく）
# ============================================================
FORMATS = ["文字", "写真", "動画"]
TRUE_EFFECT = {"文字": 0.0, "写真": 0.12, "動画": 0.06}   # 架空の「本当の効果」（答え合わせ用）


def sample_formats(seed: int = 11, days: int = 12, per_day: int = 8) -> pd.DataFrame:
    """架空の記録。後半ほど動画を使いがち（教員が工夫した）＋ 後半ほど慣れて成功しやすい
    → そのまま比べると、動画の効果が大きく見える（交絡）。"""
    rng = np.random.default_rng(seed)
    rows = []
    for day in range(1, days + 1):
        late = (day - 1) / (days - 1)
        pf = np.array([0.6 - 0.45 * late, 0.25, 0.15 + 0.45 * late])
        pf = pf / pf.sum()
        for _ in range(per_day):
            f = FORMATS[rng.choice(3, p=pf)]
            p = np.clip(0.30 + 0.40 * late + TRUE_EFFECT[f], 0.02, 0.98)
            rows.append({"実習日": day, "慣れ": "前半" if day <= days // 3 else ("中盤" if day <= 2 * days // 3 else "後半"),
                         "手順カード": f, "成功": int(rng.random() < p)})
    return pd.DataFrame(rows)


def naive_effect(df: pd.DataFrame, base: str = "文字") -> pd.Series:
    m = df.groupby("手順カード")["成功"].mean()
    return (m - m[base]).reindex(FORMATS)


def adjusted_effect(df: pd.DataFrame, base: str = "文字", by: str = "慣れ") -> pd.Series:
    """バックドア調整（層別して重みづけ）：慣れの層ごとに差をとり、層の大きさで平均する。"""
    strata = df.groupby(by)
    w = strata.size() / len(df)
    eff = {}
    for f in FORMATS:
        tot = 0.0
        for k, g in strata:
            m = g.groupby("手順カード")["成功"].mean()
            if f in m and base in m:
                tot += w[k] * (m[f] - m[base])
        eff[f] = tot
    return pd.Series(eff).reindex(FORMATS)


DAG_DOT = """digraph {
  rankdir=LR; node [shape=box, style=rounded, fontname="sans-serif"];
  慣れ [label="慣れ（実習日）"]; カード [label="手順カードの形"]; 成功 [label="自分でできた"];
  慣れ -> カード [label="後半ほど動画を使う"]; 慣れ -> 成功 [label="慣れるとできる"]; カード -> 成功 [label="知りたい効果"];
}"""

# ============================================================
# ⑥ 受け入れの判断（受け入れ側の準備）
# ============================================================
# (項目, 重み, 必須か, 確かめる先)
HOST_CHECKS = [
    ("学校と、実習の目標・期間・評価の様式をすり合わせた", 3, True, "学校の進路指導主事"),
    ("実習中のけが・事故の補償（学校管理下の扱い・保険）を学校と確認した", 3, True, "学校・教育委員会"),
    ("危険の大きい工程（窯・ミキサー・重い天板）に生徒が入らない分担にした", 3, True, "このページ ②"),
    ("ロボットを使う工程は、生徒と作業エリアを分け、リスクアセスメントをした", 3, True, "ロボットの販売元・安全の専門家"),
    ("食品衛生（手洗い・服装・体調の確認）の手順を、生徒向けの言葉で用意した", 2, True, "保健所・HACCPの記録"),
    ("本人・保護者・学校と、合理的配慮の内容を話し合った", 2, True, "学校・本人"),
    ("生成AIを誰が使うか決めた（生徒が直接使う／大人の支援ツールにとどめる）", 2, False, "学校の生成AIの方針"),
    ("生成AIのサービスの年齢条件（18歳未満の利用）を確かめた", 2, False, "各サービスの利用規約"),
    ("名前・写真・障害や健康の情報を、外部の生成AIに送らない仕組みにした", 3, True, "このページ ③・福祉×生成AI ⑤"),
    ("実習の記録をどこに保存し、いつ消すかを決めた", 2, False, "学校の個人情報の取扱い"),
    ("休憩の場所と、困ったときに声をかける相手を決めた", 2, True, "現場の担当者"),
    ("暑さ（暑さ指数）・粉じんの対策を決めた", 1, False, "ホームの「農園で働く方へ」"),
]


def host_readiness(done: Sequence[bool]) -> dict:
    """準備度（重みつきの割合）と、まだの必須項目。必須が1つでも欠けたら「まだ受け入れない」。"""
    assert len(done) == len(HOST_CHECKS)
    w = np.array([c[1] for c in HOST_CHECKS], dtype=float)
    d = np.array(done, dtype=bool)
    missing_must = [c[0] for c, ok in zip(HOST_CHECKS, d) if c[2] and not ok]
    todo = pd.DataFrame([{"項目": c[0], "必須": "必須" if c[2] else "", "確かめる先": c[3]}
                         for c, ok in zip(HOST_CHECKS, d) if not ok], columns=["項目", "必須", "確かめる先"])
    score = float((w * d).sum() / w.sum())
    if missing_must:
        verdict = "まだ受け入れない（必須の準備が残っている）"
    elif score < 0.9:
        verdict = "1〜2名・短期間なら試せる"
    else:
        verdict = "受け入れの相談を始められる"
    return {"準備度": score, "判定": verdict, "まだの必須": missing_must, "やること": todo}


# ============================================================
# 自己チェック
# ============================================================
if __name__ == "__main__":
    # ① 1日6時間＝7.2単位時間。10日で72単位時間＝1,050の約6.9%
    assert abs(practicum_hours(1, 10, 6) - 72) < 1e-9
    pl = practicum_plan(PRACTICE_EXAMPLES["例2：各学年1回・10日"])
    assert pl.iloc[-1]["実習日数"] == 30 and abs(pl.iloc[0]["年間授業時数に占める割合"] - 72 / 1050) < 1e-9
    assert host_capacity(5, 2, staff=2)["1回に受け入れられる人数"] == 4 and host_capacity(5, 2, 2)["人手が足りない"]
    assert (LAW_LAYERS["実習の回数"] == "ここで決まる").sum() == 1
    # ② 窯・ミキサー・天板運びは生徒に割り当てない
    al = allocate(STEPS)
    kiken = al.set_index("工程")["分担"]
    assert kiken["窯で焼く（230℃）"] == "ロボット・大人" and kiken["ミキサーでこねる"] == "ロボット・大人"
    assert kiken["窯から出す・天板を運ぶ"] == "ロボット・大人" and kiken["袋詰め・ラベル貼り"] == "生徒"
    assert al.set_index("工程").loc["丸め・成形", "手順カード"].startswith("あり")
    assert allocation_summary(al)["工程の数"].sum() == len(STEPS)
    assert set(al["分担"]) == set(ROLES)
    # 距離：止まっているロボットでも人の分（1.6×0.4=0.64m）＋余裕0.2m
    assert abs(protective_distance(0.0)["合計（これより近づいたら止める）"] - 0.84) < 1e-9
    d1 = protective_distance(1.0)["合計（これより近づいたら止める）"]
    assert abs(d1 - (0.64 + 0.1 + 0.15 + 0.2)) < 1e-9
    assert distance_curve()["必要な距離_m"].is_monotonic_increasing
    # ③ 悪いカードは言いかえ語と長文で引っかかり、良いカードは数が一致する
    bad, good = card_check(SAMPLE_CARD_BAD), card_check(SAMPLE_CARD_GOOD)
    assert bad["読みやすさ"]["言いかえたい語"] and any("長い" in f for f in bad["気になる点"])
    assert good["足された数"] == [] and good["落ちた数"] == []
    assert card_check(SAMPLE_CARD_GOOD.replace("195g", "200g"))["足された数"] == ["200"]
    p = build_card_prompt("材料の計量", SAMPLE_FACTS, CARD_NEEDS[:2])
    assert "名前" not in p and "300g" in p
    assert len(GEN_MODELS) == 8
    # ④ ベイズ
    assert beta_posterior(9, 10) == (10, 2)
    assert prob_above(10, 2, 0.5) > 0.98 and prob_above(2, 10, 0.5) < 0.02
    tr = sample_trials()
    pt = posterior_table(tr)
    assert set(pt["工程"]) == {"材料の計量", "丸め・成形", "袋詰め・ラベル貼り"}
    x = np.linspace(0, 1, 2001)
    assert abs(np.trapezoid(beta_pdf(3, 5, x), x) - 1) < 1e-3
    ts = thompson_suggest(tr, "袋詰め・ラベル貼り")
    assert abs(ts["次に選ばれる割合"].sum() - 1) < 1e-9
    # ⑤ 因果：調整したほうが本当の効果（動画 +0.06）に近い
    fm = sample_formats(days=60, per_day=40)
    nv, ad = naive_effect(fm)["動画"], adjusted_effect(fm)["動画"]
    assert abs(ad - TRUE_EFFECT["動画"]) < abs(nv - TRUE_EFFECT["動画"]), (nv, ad)
    # ⑥ 必須が欠けたら受け入れない
    all_ok = host_readiness([True] * len(HOST_CHECKS))
    assert all_ok["準備度"] == 1 and all_ok["判定"].startswith("受け入れの相談")
    one_missing = host_readiness([i != 1 for i in range(len(HOST_CHECKS))])
    assert one_missing["判定"].startswith("まだ") and len(one_missing["まだの必須"]) == 1
    print("tokushi_lab.py：自己チェック OK")

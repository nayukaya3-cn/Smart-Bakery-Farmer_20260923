"""
career_lab.py — 探究コーナー「AI時代に残る仕事を、就活と起業で獲得する」の計算部品

画面は pages/22_🧭_AI時代に残る仕事.py。`python career_lab.py` で自己チェック。

問い
  生成AIやロボットが広がるとき、置き換わりにくく、AIと組むとむしろ強くなる仕事・事業はどれか。
  その仕事に就く・事業を始めるためのハードル（資格・インターン・特別教育・実務経験）は何で、
  どんな条件がそろえば突破できるか。

ピボット（出発点）
  東京都立蔵前工科高校では、ロボットインストラクターの資格をもつ教員が授業・実習の中で
  産業用ロボットの教示等の特別教育を行い、卒業時に修了証を出している。
  「学校の準備教育 → 特別教育 → 実務 → 教える側」という資格の鎖を、一つの学校の中でつないだ例である。

骨格（リポジトリ共通）：① 計算する → ② 可視化する → ③ 自分の条件で判断する
  ① 置き換わりにくさ … 仕事を5種類のタスクに分け、時間の割合から「置き換わりやすさ」と「AIと組める余地」を計算する
  ② 資格の地図       … 資格・経験の前提関係をグラフにし、いま持っているものから「次に挑戦できる一歩」を出す
  ③ 就活と起業       … 応募の通過率をベイズで更新して必要な応募数を出す／出張講習の損益分岐を出す

用語の規律
  「AIで無くならない仕事」と言い切れる研究はない。ここでは
  「AIへの曝露が低いか、曝露しても仕事が置き換えではなく変容する（AIと組める）仕事」と言いかえる。
  依拠する考え方：タスク・アプローチ（Autor, Levy & Murnane 2003）、自動化のボトルネック（Frey & Osborne 2017）、
  生成AIの職業曝露指標（ILO Working Paper 140, 2025）。

方針
  - 重み・料金・人数の初期値はすべて教育用の仮置き。自分の調べた値に置きかえて使う。
  - 個人の年齢・収入・健康などは入力させない。決めるのは本人。
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

import numpy as np
import pandas as pd

# ============================================================
# ① 置き換わりにくさ（タスク・アプローチ）
# ============================================================
# 置き換わりやすさ w_auto：そのタスクをAI・ロボットが代わりにできる度合い（0〜1、仮置き）
# 組める余地   w_aug ：AIを道具にすると速く・よくなる度合い（0〜1、仮置き）
TASK_TYPES = pd.DataFrame([
    {"タスク": "定型の事務（入力・転記・定型文）", "w_auto": 0.80, "w_aug": 0.20,
     "根拠": "ルールで書ける認知作業。生成AIの曝露がいちばん高い（ILO 2025：事務職）"},
    {"タスク": "定型の手作業（同じ動作のくり返し）", "w_auto": 0.55, "w_aug": 0.20,
     "根拠": "産業用ロボットが得意。ただし導入費と段取り替えが壁"},
    {"タスク": "分析・企画・文章（非定型の認知）", "w_auto": 0.40, "w_aug": 0.70,
     "根拠": "生成AIが下書きを出せる。判断と責任は人に残る（置き換えより変容）"},
    {"タスク": "対人（教える・相談・合意をつくる）", "w_auto": 0.15, "w_aug": 0.40,
     "根拠": "社会的知性はボトルネック（Frey & Osborne）。信頼と関係が価値"},
    {"タスク": "現場の手作業（その場で見て、手で直す）", "w_auto": 0.15, "w_aug": 0.35,
     "根拠": "知覚と操作はボトルネック。畑・工房・設備の不規則な現場"},
])
TASK_NAMES = list(TASK_TYPES["タスク"])

# 1週間の時間の割合（合計1）と「法令・資格で人が担うと決まっている割合」（仮置き）
JOBS: dict[str, dict] = {
    "一般事務": {"割合": [0.60, 0.05, 0.20, 0.15, 0.00], "制度": 0.00},
    "プログラマー（受託の実装）": {"割合": [0.15, 0.00, 0.70, 0.15, 0.00], "制度": 0.00},
    "工場のライン作業": {"割合": [0.05, 0.70, 0.05, 0.05, 0.15], "制度": 0.05},
    "ロボット安全教育インストラクター": {"割合": [0.10, 0.00, 0.20, 0.45, 0.25], "制度": 0.50},
    "高校の情報・理科の教員": {"割合": [0.20, 0.00, 0.25, 0.50, 0.05], "制度": 0.40},
    "パン職人（工房）": {"割合": [0.05, 0.30, 0.10, 0.15, 0.40], "制度": 0.10},
    "農場の運営スタッフ": {"割合": [0.10, 0.20, 0.10, 0.15, 0.45], "制度": 0.05},
}
LICENSE_SHIELD = 0.5  # 制度で人が担う部分は、置き換わりやすさを半分にする（仮置き）


def job_profile(shares: Iterable[float], licensed: float = 0.0) -> dict:
    """時間の割合から、置き換わりやすさ（0〜1）と組める余地（0〜1）を出す。"""
    s = np.asarray(list(shares), dtype=float)
    if s.shape != (len(TASK_TYPES),) or (s < 0).any() or s.sum() <= 0:
        raise ValueError("5種類のタスクの割合（0以上）を入れてください")
    s = s / s.sum()
    licensed = float(np.clip(licensed, 0, 1))
    auto_raw = float(s @ TASK_TYPES["w_auto"].to_numpy())
    auto = auto_raw * (1 - LICENSE_SHIELD * licensed)
    aug = float(s @ TASK_TYPES["w_aug"].to_numpy())
    if auto >= 0.45:
        kind = "置き換わりやすい：タスクの組み替えが要る"
    elif aug >= 0.40:
        kind = "変容型：AIと組むと強くなる"
    else:
        kind = "残りやすい：現場と対人が中心"
    return {"置き換わりやすさ": auto, "制度なしなら": auto_raw, "組める余地": aug, "型": kind}


def jobs_table(jobs: Mapping[str, dict] = JOBS) -> pd.DataFrame:
    rows = []
    for name, j in jobs.items():
        p = job_profile(j["割合"], j["制度"])
        rows.append({"仕事": name, "置き換わりやすさ": p["置き換わりやすさ"], "組める余地": p["組める余地"], "型": p["型"]})
    return pd.DataFrame(rows)


# ============================================================
# ② 資格の地図（前提のグラフ）
# ============================================================
# 名前 → (段, 種類, 前提（すべて必要）, 目安の月数, 確かめる先・メモ)
CREDENTIALS: dict[str, tuple] = {
    "準備教育（学校の授業・体験実習）": (0, "学ぶ", [], 1, "ハウス収穫ロボ体験実習・ロボット系の授業"),
    "教員免許（理科・情報など）": (0, "資格", [], 24, "大学の教職課程。情報は認定講習などの道もある"),
    "職業訓練指導員免許": (0, "資格", [], 12, "職種ごと。実務経験や講習で取得（都道府県）"),
    "産業用ロボットの特別教育（教示等・検査等）": (1, "特別教育", [], 1, "受講要件なし。教示等10時間以上・検査等13時間以上"),
    "インターン・職場体験（ロボットのある現場）": (1, "経験", ["準備教育（学校の授業・体験実習）"], 1, "受け入れ先のリスクアセスメントが前提"),
    "実務経験（ロボットを使う職場・訓練施設）": (2, "経験", ["産業用ロボットの特別教育（教示等・検査等）"], 12,
                                       "ポリテクセンターの訓練・メーカーのSIer研修なども"),
    "インストラクターコース修了": (2, "講習", ["産業用ロボットの特別教育（教示等・検査等）"], 1,
                          "法定の講師資格ではない。受講要件・日程は主催者で確かめる"),
    "学校の授業で特別教育を行う（蔵前工科高校型）": (3, "仕事", ["インストラクターコース修了", "教員免許（理科・情報など）",
                                               "実務経験（ロボットを使う職場・訓練施設）"], 6,
                                "教育課程への位置づけ・修了証の台帳は学校が管理"),
    "職業訓練で教える（ポリテク・訓練校）": (3, "仕事", ["職業訓練指導員免許", "実務経験（ロボットを使う職場・訓練施設）"], 6,
                                "求人は訓練機関ごと"),
    "事業所へ出張して特別教育を行う（起業）": (3, "事業", ["インストラクターコース修了", "実務経験（ロボットを使う職場・訓練施設）"], 6,
                                 "開業届・賠償保険・教材と実機（またはシミュレーター）の手配"),
    "体験実習の受け入れ先になる（起業）": (3, "事業", ["インストラクターコース修了", "インターン・職場体験（ロボットのある現場）"], 12,
                              "学校と目標・保険・評価の様式をすり合わせる"),
}


def credential_status(held: Iterable[str]) -> pd.DataFrame:
    """持っているものから、各項目の状態（済／いま挑戦できる／前提が足りない）と、足りない前提を出す。"""
    held = set(held)
    unknown = held - set(CREDENTIALS)
    if unknown:
        raise KeyError(f"地図にない項目：{sorted(unknown)}")
    rows = []
    for name, (lv, kind, pre, months, memo) in CREDENTIALS.items():
        missing = [p for p in pre if p not in held]
        state = "済" if name in held else ("いま挑戦できる" if not missing else "前提が足りない")
        rows.append({"項目": name, "段": lv, "種類": kind, "状態": state, "足りない前提": "／".join(missing),
                     "目安_月": months, "メモ": memo})
    return pd.DataFrame(rows)


def months_to_reach(goal: str, held: Iterable[str]) -> tuple[int, list[str]]:
    """目標までの最短の目安月数（前提を並行して進められるとして、いちばん長い道筋）と、その道筋。"""
    held = set(held)
    memo: dict[str, tuple[int, list[str]]] = {}

    def go(n: str) -> tuple[int, list[str]]:
        if n in held:
            return 0, []
        if n in memo:
            return memo[n]
        _, _, pre, months, _ = CREDENTIALS[n]
        best = (0, [])
        for p in pre:
            t = go(p)
            if t[0] > best[0]:
                best = t
        memo[n] = (best[0] + months, best[1] + [n])
        return memo[n]

    return go(goal)


# ハードルと、突破できる条件（道ごと）
HURDLES = pd.DataFrame([
    {"道": "正社員として就職", "ハードルの条件": "求人の条件（経験年数・資格・勤務地・年齢の運用）と、書類・面接の通過率",
     "突破できる条件": "求人の条件に合う証明（修了証・作品・記録）を先にそろえ、応募数を通過率から逆算する（③）",
     "AIとの関係": "書類の下書きにAIを使える。代わりに「現場で何ができるか」の証拠が差になる"},
    {"道": "非常勤・業務委託", "ハードルの条件": "空きが出る時期が限られる（年度替わり）。1件あたりの時間が短い",
     "突破できる条件": "複数の拠点・複数の科目で受けられるようにし、時期の前に名簿登録しておく",
     "AIとの関係": "授業準備はAIで速くなる。教室での対人の部分は残る"},
    {"道": "起業（個人事業）", "ハードルの条件": "最初の顧客・信用・固定費。事業所で教えるなら実機か代わりの教材",
     "突破できる条件": "損益分岐の回数（③）を1年目に満たせる顧客の当てがある。保険と開業届を先に",
     "AIとの関係": "集客・事務はAIで軽くなる。講習の中身と安全の責任は人"},
    {"道": "資格（免許・指導員）", "ハードルの条件": "受験・受講要件（学歴・実務年数）、時間と費用",
     "突破できる条件": "要件を前提のグラフ（②）で並べ、並行して進められるものを同時に始める",
     "AIとの関係": "法令で人が担うと決まっている業務は、置き換わりにくさの盾になる（①の「制度」）"},
    {"道": "特別教育・技能講習", "ハードルの条件": "受講そのものの壁は低い。ただし修了だけでは「できる」の証明にならない",
     "突破できる条件": "修了の後に実務経験とセットで記録を残す（作業日誌・ログ）",
     "AIとの関係": "シミュレーター（Isaac Sim・Gazebo）で実機前の練習ができる"},
    {"道": "インターン・職場体験", "ハードルの条件": "受け入れ先の数が少ない。安全・保険・評価の準備が要る",
     "突破できる条件": "受け入れ先の準備（リスクアセスメント・修了者の配置）を手伝える人がいる",
     "AIとの関係": "遠隔操作・シミュレーターで、危険ゼロの段から始められる"},
    {"道": "実務経験", "ハードルの条件": "経験がないと雇われず、雇われないと経験が積めない（鶏と卵）",
     "突破できる条件": "訓練施設・体験実習・自分の工房で「記録の残る経験」をつくる",
     "AIとの関係": "記録をAIで整理し、第三者が確かめられる形にする"},
])


# ============================================================
# ③ 就活と起業
# ============================================================
def pass_rate_posterior(passed: int, applied: int, a0: float = 1.0, b0: float = 1.0) -> tuple[float, float]:
    """書類の通過率の事後分布 Beta(a, b)。事前は一様。"""
    if not 0 <= passed <= applied:
        raise ValueError("通過数は 0〜応募数 の範囲で")
    return a0 + passed, b0 + applied - passed


def applications_needed(passed: int, applied: int, target: int, confidence: float = 0.8,
                        max_apps: int = 200, draws: int = 20000, seed: int = 0) -> int | None:
    """「面接が target 件以上になる確率」が confidence 以上になる、追加の応募数（ベータ二項・モンテカルロ）。"""
    if target <= 0:
        return 0
    a, b = pass_rate_posterior(passed, applied)
    rng = np.random.default_rng(seed)
    p = rng.beta(a, b, draws)
    for n in range(1, max_apps + 1):
        if (rng.binomial(n, p) >= target).mean() >= confidence:
            return n
    return None


def session_profit(price: float, participants: int, sessions: int, var_cost: float, fixed: float) -> dict:
    """出張講習の月の損益と、損益分岐の回数。price は1人あたり、var_cost は1回あたり（交通費・教材）。"""
    margin = price * participants - var_cost
    profit = margin * sessions - fixed
    be = None if margin <= 0 else int(np.ceil(fixed / margin))
    return {"1回の粗利": margin, "月の損益": profit, "損益分岐の回数": be}


# ============================================================
# 自己チェック
# ============================================================
if __name__ == "__main__":
    # ① 事務は置き換わりやすく、インストラクターは置き換わりにくい。制度の盾で下がる
    jt = jobs_table().set_index("仕事")
    assert jt.loc["一般事務", "置き換わりやすさ"] > 0.45 and jt.loc["一般事務", "型"].startswith("置き換わり")
    assert jt.loc["ロボット安全教育インストラクター", "置き換わりやすさ"] < jt.loc["工場のライン作業", "置き換わりやすさ"]
    assert jt.loc["プログラマー（受託の実装）", "型"].startswith("変容")
    p = job_profile(JOBS["ロボット安全教育インストラクター"]["割合"], 0.5)
    assert p["置き換わりやすさ"] < p["制度なしなら"]
    assert len(TASK_NAMES) == 5
    for j in JOBS.values():
        assert abs(sum(j["割合"]) - 1) < 1e-9
    try:
        job_profile([1, 2, 3])
        raise AssertionError("長さの違う割合を通してしまった")
    except ValueError:
        pass
    # ② 何もなければ、前提のない項目だけ挑戦できる。蔵前工科高校型には3つの前提がいる
    st0 = credential_status([]).set_index("項目")
    assert (st0["状態"] == "いま挑戦できる").sum() == sum(1 for v in CREDENTIALS.values() if not v[2])
    kura = "学校の授業で特別教育を行う（蔵前工科高校型）"
    assert len(st0.loc[kura, "足りない前提"].split("／")) == 3
    held = ["教員免許（理科・情報など）", "産業用ロボットの特別教育（教示等・検査等）", "インストラクターコース修了"]
    st1 = credential_status(held).set_index("項目")
    assert st1.loc[kura, "足りない前提"] == "実務経験（ロボットを使う職場・訓練施設）"
    m, path = months_to_reach(kura, held)
    assert m == 12 + 6 and path[-1] == kura
    m0, _ = months_to_reach(kura, [])
    assert m0 == max(24, 1 + 1, 1 + 12) + 6
    # 前提に循環がない（段は前提より大きい）
    for n, (lv, _, pre, _, _) in CREDENTIALS.items():
        assert all(CREDENTIALS[q][0] < lv for q in pre), n
    # ③ 通過率が高いほど、必要な応募数は少ない
    hi, lo = applications_needed(6, 10, 3), applications_needed(1, 10, 3)
    assert hi is not None and lo is not None and hi < lo, (hi, lo)
    assert applications_needed(0, 0, 0) == 0
    assert pass_rate_posterior(3, 10) == (4, 8)
    sp = session_profit(price=10000, participants=5, sessions=3, var_cost=10000, fixed=50000)
    assert sp["1回の粗利"] == 40000 and sp["月の損益"] == 70000 and sp["損益分岐の回数"] == 2
    assert session_profit(1000, 1, 5, 5000, 1000)["損益分岐の回数"] is None
    assert set(HURDLES["道"]) >= {"正社員として就職", "起業（個人事業）", "特別教育・技能講習", "実務経験"}
    print("career_lab.py：自己チェック OK")

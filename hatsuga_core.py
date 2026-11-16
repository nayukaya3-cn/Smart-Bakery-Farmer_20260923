"""
発芽を予測する：積算温度 ─ データと計算部品（姉妹3サイトに「同じ内容」で置くファイル）

  🌾 スマートパン屋農家 … 今まく作物（計画と実績・小麦の出芽予測）
  🧬 科学と人間生活 × 情報Ⅰ … 教室で計算する（予想 → ずれ δ）
  📡 IoTフィールドワーク … 地温を測って貯め、積算が届いたら知らせる

問い：「11月16日にまいた小麦は、いつ芽を出すか。2週間前にまいたほうれん草の芽は、いつ出たと言えるか」

畑の記録（FIELD_LOG）は実際の記録。それ以外の数値の扱い
  - 小麦の播種〜出芽の積算温度 108.6 ℃・日：茨城県農業総合センター農業研究所（平成28年度 主要成果）
    「適期に栽培管理を行うための小麦『さとのそら』の出芽期予測法」に書かれた推定値。
    品種（ここではミナミノカオリ）・土の水分・まく深さで変わる**参考値**。自分の畑の実測で置きかえる
  - 基準温度 0 ℃：日平均気温をそのまま足す、いちばん単純な数え方（仮定）
  - ミナミノカオリの播種の適期：佐賀県 11/10〜11/20（平成26年度 研究成果情報）、長崎県 11月下旬（平成20年度 成果情報。
    11月上旬の早まきは幼穂凍死が増える）。どちらも九州の試験で、三原西部にそのまま当てはまるとは限らない
  - 日ごとの気温・地温：**説明用の架空データ**（乱数の種を固定して毎回同じ形になる）

直し方：このファイルを直したら、ほかの2つのリポジトリにも同じ内容でコピーし、CORE_VERSION を上げる。
Streamlit にも numpy にも依存しない。`python hatsuga_core.py` で自己チェック。
"""
from __future__ import annotations

import math
import random
from datetime import date, timedelta

CORE_VERSION = "2026-11-16.1"
TITLE = "発芽を予測する：積算温度"
LEAD_QUESTION = "11月16日にまいた小麦は、いつ芽を出すか。2週間前にまいたほうれん草の芽は、『いつ出た』と言えるか？"
EASY_WORDS = ("積算温度（せきさんおんど）＝「毎日の平均気温を足していった合計」。単位は ℃・日。"
              "種は『日数』ではなく『あたたかさの合計』が決まった量に届くと芽を出す、と考える模型。")

# ─────────────────────────────────────────────
# 畑の記録（三原西部・実際の記録。日付と作業だけ。人の名前や場所の細かい情報は入れない）
# ─────────────────────────────────────────────
FIELD_LOG: list[dict] = [
    dict(date=date(2026, 11, 1), crop="寒締めほうれん草", event="播種"),
    dict(date=date(2026, 11, 15), crop="タマネギ（苗）", event="定植"),
    dict(date=date(2026, 11, 16), crop="パン用小麦（ミナミノカオリ）", event="播種"),
    dict(date=date(2026, 11, 16), crop="寒締めほうれん草", event="出芽を確認"),
]
WHEAT_SOWN = date(2026, 11, 16)
SPINACH_SOWN = date(2026, 11, 1)
SPINACH_SEEN = date(2026, 11, 16)

WHEAT_GDD = 108.6        # 小麦の播種〜出芽に必要な積算温度 [℃・日]（茨城県の「さとのそら」での推定値＝参考値）
BASE_TEMP = 0.0          # 基準温度 [℃]（これより寒い日は足さない）
GDD_SOURCE = "茨城県農業総合センター農業研究所 平成28年度 主要成果（小麦「さとのそら」の出芽期予測法）"

#   (どこの目安か, 開始(月,日), 終了(月,日), 根拠)
SOWING_WINDOWS: list[tuple[str, tuple[int, int], tuple[int, int], str]] = [
    ("佐賀県（ミナミノカオリ）", (11, 10), (11, 20),
     "穂発芽（収穫が梅雨にかかる）と、早まきの凍霜害・雑草害の両方を避ける時期。平成26年度 研究成果情報"),
    ("長崎県（ミナミノカオリ）", (11, 21), (11, 30),
     "11月上旬の早まきは幼穂凍死が増えて収量が下がるため、11月下旬にまく。平成20年度 成果情報"),
]


# ─────────────────────────────────────────────
# ① 計算する：積算温度
# ─────────────────────────────────────────────
def days_to_emerge(mean_temp: float, gdd: float = WHEAT_GDD, base: float = BASE_TEMP) -> float:
    """平均気温が一定のとき、出芽までの日数。基準温度以下なら、いつまでも届かない（inf）"""
    eff = mean_temp - base
    return math.inf if eff <= 0 else gdd / eff


def accumulate(temps, base: float = BASE_TEMP) -> list[float]:
    """日平均気温の列 → 積算温度の列。欠測（None）の日は足さない（＝0として扱ってしまう数え方）"""
    out, total = [], 0.0
    for t in temps:
        if t is not None:
            total += max(t - base, 0.0)
        out.append(round(total, 2))
    return out


def emerge_day(temps, gdd: float = WHEAT_GDD, base: float = BASE_TEMP) -> int | None:
    """積算温度がはじめて gdd に届く日（まいた翌日を1日目と数える）。届かなければ None"""
    for i, c in enumerate(accumulate(temps, base), 1):
        if c >= gdd:
            return i
    return None


def forecast(sown: date, temps, gdd: float = WHEAT_GDD, base: float = BASE_TEMP) -> date | None:
    """まいた日と、翌日からの日平均気温の列 → 出芽の予測日"""
    n = emerge_day(temps, gdd, base)
    return None if n is None else sown + timedelta(days=n)


def fill_missing(temps) -> list[float]:
    """欠測（None）を、前後の測れた日の平均でうめる。端の欠測は、いちばん近い測れた日の値でうめる"""
    known = [i for i, t in enumerate(temps) if t is not None]
    if not known:
        raise ValueError("測れた日が1日もありません")
    out = list(temps)
    for i, t in enumerate(temps):
        if t is None:
            before = max((k for k in known if k < i), default=None)
            after = min((k for k in known if k > i), default=None)
            near = [temps[k] for k in (before, after) if k is not None]
            out[i] = sum(near) / len(near)
    return out


# ─────────────────────────────────────────────
# ③ 判断する：「見た日」と「出た日」はちがう
# ─────────────────────────────────────────────
def emergence_interval(sown: date, seen: date, last_check: date | None = None) -> tuple[int, int]:
    """出芽を「確認した日」から言えること：出芽は、まいてから (lo, hi] 日のあいだ。

    last_check＝その前に畑を見て、まだ出ていなかった日。無ければ、まいた日（0日目）からとしか言えない。
    """
    if not sown <= (last_check or sown) < seen:
        raise ValueError("日付の順が、まいた日 ≦ 前に見た日 ＜ 確認した日 になっていません")
    return ((last_check or sown) - sown).days, (seen - sown).days


def window_state(day: date, start: tuple[int, int], end: tuple[int, int]) -> tuple[str, int]:
    """その日が、目安の期間（同じ年の 開始〜終了）の前・中・後のどこか。(状態, ずれた日数)"""
    s, e = date(day.year, *start), date(day.year, *end)
    if day < s:
        return "早い", (s - day).days
    if day > e:
        return "遅い", (day - e).days
    return "期間内", 0


# ─────────────────────────────────────────────
# 説明用の架空データ：晩秋の日平均気温（だんだん下がる＋日ごとのぶれ）
# ─────────────────────────────────────────────
def synth_temps(days: int = 45, start_temp: float = 11.0, drop_per_day: float = 0.12,
                noise: float = 1.5, seed: int = 1116) -> list[float]:
    """まいた翌日からの日平均気温 [℃]。**架空データ**（実測ではない）"""
    rng = random.Random(seed)
    return [round(start_temp - drop_per_day * i + rng.uniform(-noise, noise), 1) for i in range(days)]


def with_outage(temps, start: int, length: int) -> list:
    """start 日目（0始まり）から length 日ぶん、記録が止まった（None）ことにする"""
    return [None if start <= i < start + length else t for i, t in enumerate(temps)]


def _self_check() -> None:
    # 平均10℃なら約11日、5℃なら約22日。寒いほど長く、0℃以下では届かない
    assert round(days_to_emerge(10)) == 11 and round(days_to_emerge(5)) == 22
    assert days_to_emerge(0) == math.inf and days_to_emerge(-2) == math.inf
    assert accumulate([10, 10, None, -3, 5]) == [10, 20, 20, 20, 25]
    # 一定の気温なら、1日ずつ足した答えと割り算の答えが合う
    assert emerge_day([10.0] * 30) == math.ceil(WHEAT_GDD / 10) == 11
    assert emerge_day([1.0] * 30) is None
    assert forecast(WHEAT_SOWN, [10.0] * 30) == date(2026, 11, 27)
    # 欠測を0扱いすると予測は遅れ、うめると元にもどる
    full = synth_temps()
    cut = with_outage(full, 3, 4)
    assert emerge_day(cut) > emerge_day(full)
    assert abs(emerge_day(fill_missing(cut)) - emerge_day(full)) <= 1
    assert fill_missing([None, 4.0, None, 8.0, None]) == [4.0, 4.0, 6.0, 8.0, 8.0]
    # ほうれん草：確認した日（15日目）は「遅くとも」の日。前に見た日があれば幅がせばまる
    assert emergence_interval(SPINACH_SOWN, SPINACH_SEEN) == (0, 15)
    assert emergence_interval(SPINACH_SOWN, SPINACH_SEEN, date(2026, 11, 9)) == (8, 15)
    # 11/16 の播種は、佐賀の目安では期間内、長崎の目安では5日早い
    assert window_state(WHEAT_SOWN, *SOWING_WINDOWS[0][1:3]) == ("期間内", 0)
    assert window_state(WHEAT_SOWN, *SOWING_WINDOWS[1][1:3]) == ("早い", 5)
    assert synth_temps() == synth_temps() and len(synth_temps(10)) == 10
    assert [r["date"] for r in FIELD_LOG] == sorted(r["date"] for r in FIELD_LOG)


if __name__ == "__main__":
    _self_check()
    print("hatsuga_core: 自己チェックOK", CORE_VERSION)

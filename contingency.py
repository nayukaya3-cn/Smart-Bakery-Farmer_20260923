"""
contingency.py ─ コンテンジェンシープラン（現状把握 → 次の一手）の計算部品

  ① 現状把握（戦略情報）… 観測値を「平時・注意・警戒・非常」の4段階に読み替える
  ② 次の一手（戦術・戦場情報）… 段階ごとに、前もって決めた「もし〜なら、〜する」を引く
  ③ 振り返り … 判断と結果を記録し、しきい値と打ち手を直す

考え方（教材・研究に書くときの用語）:
  - 事業継続計画（BCP）の発動基準と行動計画
  - 実行意図（if-then プランニング: Gollwitzer, 1999）… 迷う前に決めておくと実行されやすい
  - 過剰反応の抑制（ブルウィップ効果: Lee, Padmanabhan & Whang, 1997）
    … 報道と実データの乖離 D が大きいときは「買い増さない」こと自体が打ち手
  - 総合レベル＝最も悪い指標の段階（最悪指標ルール。見落としを防ぐ保守的な読み方）

しきい値は仮置き。Streamlit に依存しない純粋関数だけを置く（pages/23_… から使う）。
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

LEVELS = ["平時", "注意", "警戒", "非常"]
LEVEL_ICON = ["🟢", "🟡", "🟠", "🔴"]


@dataclass(frozen=True)
class Signal:
    key: str
    name: str
    unit: str
    th: tuple[float, float, float]   # 注意・警戒・非常に上がる境目
    higher_is_worse: bool
    default: float
    source: str                      # どこで確かめるか（一次情報）
    actions: tuple[str, str, str]    # 注意・警戒・非常で引く打ち手


SIGNALS: list[Signal] = [
    Signal("food_cpi", "食料の物価上昇（前年比）", "%", (3, 6, 15), True, 2.0,
           "総務省 消費者物価指数（e-Stat）",
           ("買う量は変えず、旬の作物で自給を前倒しする",
            "食費の置き換え目標を上げ、主食（芋・小麦）の作付けを増やす",
            "主食・保存食を最優先。余剰は売らずに保存へ回す")),
    Signal("fuel", "燃料価格の変化（前月比）", "%", (5, 10, 20), True, 0.0,
           "資源エネルギー庁 石油製品価格調査",
           ("機械作業をまとめて行い、燃料の使用回数を減らす",
            "燃料を使う作業を手作業・太陽熱乾燥などに置き換える",
            "燃料は暖房・調理・移動の生活用に限る。圃場作業は人力へ")),
    Signal("shortage", "資材・原料の欠品（品目数）", "品目", (1, 3, 5), True, 0.0,
           "取引先・直売所・ホームセンターでの確認（自分の目で）",
           ("次の作の分だけ確保する（それ以上は買わない）",
            "代替資材（米ぬか・落葉堆肥など自家調達）に切り替える",
            "物々交換は信頼のある相手とだけ行う。加工品の販売は許可の範囲で")),
    Signal("cash_months", "現金で暮らせる月数（生活の床）", "か月", (6, 3, 1), False, 12.0,
           "自分の通帳・家計（このアプリには保存しない）",
           ("新しい支出（設備・講座）を先送りにする",
            "医療・燃料・通信の現金を最優先で確保し、余剰の実物化を止める",
            "収入を増やす前に支出を止める。公的な支援制度の窓口に相談する")),
    Signal("staple_days", "主食の手持ち日数", "日", (30, 14, 7), False, 60.0,
           "自宅の備蓄と畑の在庫（自給家計簿）",
           ("通常の買い物の範囲で、ローリングストックを1サイクル分増やす",
            "芋・豆など早く収穫できる主食を植え足す",
            "近隣・仲間と分け合う段取りを確認する（孤立しない）")),
    Signal("income_drop", "予定収入の減少", "%", (10, 30, 50), True, 0.0,
           "契約書・勤務予定（授業コマ・契約先）",
           ("次年度の契約・コマ数を早めに確認する",
            "販路・契約先を1つ増やす（1本足を避ける）",
            "固定費を見直し、自給（C）で必要額そのものを下げる")),
    Signal("security", "セキュリティ警告（直近の件数）", "件", (1, 5, 20), True, 0.0,
           "🔒 セキュリティログ（このアプリ）",
           ("警告の中身を確認する（誤検知か本物か）",
            "パスワード・Secrets を見直し、不要な公開ページを閉じる",
            "アプリを一時停止し、記録を保全してから原因を調べる")),
]
SIG = {s.key: s for s in SIGNALS}

# 段階ごとの共通の打ち手（指標に関係なく、その段階に入ったらすること）
COMMON = [
    ("記録を続ける（日誌・家計簿）", "余剰は売り、売上は30日以内に実物へ換える", "年1回、しきい値と打ち手を見直す"),
    ("在庫と販路を点検する", "買い増しは「通常量＋1サイクル」まで", "一次情報で確かめてから動く"),
    ("現金支出の優先順位を決める（医療・燃料・通信）", "販路を2つ以上動かしておく", "学校・契約先への連絡の文面を準備する"),
    ("生活の床（主食・水・燃料・暖）を守る", "約束している相手（学校・契約先）に早めに連絡する", "法令の範囲で動く（加工品の販売許可・物価統制）"),
]

# 過剰反応（β）のガード：動く前に確かめる3つの問い
BETA_CHECKS = [
    "一次情報（統計・取引先・自分の目）で確かめたか（報道・SNSだけで動いていないか）",
    "いまの在庫で何日もつか、数字で言えるか",
    "今日動かないと、何が失われるかを具体的に言えるか",
]
D_THRESHOLD = 0.5  # 報道と実データの乖離 D がこれ以上なら「買い増さない」


def level_of(sig: Signal, value: float) -> int:
    """観測値を段階（0=平時〜3=非常）に読み替える。"""
    lv = 0
    for i, t in enumerate(sig.th, start=1):
        if (value >= t) if sig.higher_is_worse else (value <= t):
            lv = i
    return lv


def assess(values: dict[str, float]) -> pd.DataFrame:
    """全指標の段階と、その段階で引く打ち手を一覧にする（悪い順）。"""
    rows = []
    for s in SIGNALS:
        v = float(values.get(s.key, s.default))
        lv = level_of(s, v)
        rows.append({
            "指標": s.name, "値": v, "単位": s.unit, "段階": lv,
            "表示": f"{LEVEL_ICON[lv]} {LEVELS[lv]}",
            "次の一手": s.actions[lv - 1] if lv else "—",
            "確かめる先": s.source, "key": s.key,
        })
    return pd.DataFrame(rows).sort_values("段階", ascending=False, kind="stable").reset_index(drop=True)


def overall(table: pd.DataFrame) -> int:
    """総合レベル＝最も悪い指標の段階。"""
    return int(table["段階"].max()) if len(table) else 0


def next_moves(table: pd.DataFrame, d_index: float, beta_ok: int, n: int = 3) -> list[str]:
    """
    今日の打ち手を最大 n 個。
      - 乖離 D が大きい／確かめが足りない → まず「確かめる」「買い増さない」を先頭に置く
      - その後、悪い指標の打ち手、足りなければ段階の共通の打ち手
    """
    moves: list[str] = []
    if d_index >= D_THRESHOLD:
        moves.append(f"報道と実データの乖離 D={d_index:.2f}：いまは買い増さない（過剰反応を起こさない）")
    if beta_ok < len(BETA_CHECKS) and (overall(table) > 0 or d_index >= D_THRESHOLD):
        moves.append("動く前に、未確認の問いを一次情報で確かめる")
    for a in table.loc[table["段階"] > 0, "次の一手"]:
        if a not in moves:
            moves.append(a)
    for a in COMMON[overall(table)]:
        if a not in moves:
            moves.append(a)
    return moves[:n]


DECISION_COLS = ["日付", "段階", "きっかけ", "決めた一手", "結果・気づき"]


# ───────────────────────── 自己チェック ─────────────────────────
if __name__ == "__main__":
    s = SIG["food_cpi"]
    assert [level_of(s, v) for v in (0, 3, 6, 15, 40)] == [0, 1, 2, 3, 3]
    c = SIG["cash_months"]
    assert [level_of(c, v) for v in (12, 6, 3, 1, 0)] == [0, 1, 2, 3, 3]

    calm = assess({k.key: (10 if not k.higher_is_worse else 0) for k in SIGNALS} | {"staple_days": 60})
    assert overall(calm) == 0
    assert next_moves(calm, 0.1, 3)[0] == COMMON[0][0]
    assert next_moves(calm, 0.1, 0)[0] == COMMON[0][0], "平時は確かめの催促を出さない"

    bad = assess({"food_cpi": 20, "cash_months": 4})
    assert overall(bad) == 3 and bad.iloc[0]["key"] == "food_cpi", "最悪指標が先頭に来る"
    mv = next_moves(bad, 0.8, 1)
    assert mv[0].startswith("報道と実データの乖離") and "確かめる" in mv[1] and len(mv) == 3
    assert all(len(x) == 3 for x in COMMON) and len(COMMON) == len(LEVELS)
    print("OK: contingency の自己チェックを通過しました")

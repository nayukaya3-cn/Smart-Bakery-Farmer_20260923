"""
高校の必履修科目「科学と人間生活」＝フィールドワーク事前学習 ─ 計算部品とデータ

画面は pages/27_🔭_科学と人間生活_FW事前学習.py（左メニュー「📝 教科×情報Ⅰ」）。
`python kagaku_ningen_fw.py` で自己チェック（assert）が走ります。

ねらい
  教科の先生が「どの単元を、どの調査地の前に置くか」「授業の最後にどんな問いを投げるか」を決め、
  事前学習の1コマを ① 計算する → ② 可視化する → ③ 自分の条件で判断する で組めるようにする。
  事前・本番・事後の伴走は pages/26（fieldwork_pdca.py）が受け持つ。単元の対応表もそこと共用。

出どころ
  - 学習指導要領（平成30年告示）高等学校 理科「科学と人間生活」の内容構成
  - 教科書：各社とも令和7年検定済の新版（例：東京書籍 科人002-901、第一学習社 科人183-901）
      （東京都教育委員会「教科書調査研究資料（令和8年度使用）」による）
  - 光の屈折：見かけの深さ ≒ 実際の深さ ÷ 水の屈折率（約1.33）。真上近くから見たときの近似
  - 浸水時の歩行の目安は自治体・国の防災資料で各自が確かめて入れる（初期値は説明用）
  - 姉妹サイト（教材ネットワーク）：sister_sites.py。教室側の「🧬 体をつくるタンパク質」と単元名（小項目）を共通語彙にしてつなぐ
  - PDCAの発展形：PDSA（Deming）、OODA（Boyd）、SDCA（TQMの標準化サイクル）。
    「PDCA 2.0（Purpose-Dialogue-Creative-Align）」は実務書・記事で使われる呼び方で、学術用語ではない
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import fieldwork_pdca as fp
import sister_sites as ss

TEXTBOOK_URL = "https://ten.tokyo-shoseki.co.jp/text/hs/rika/16737/"  # 東京書籍 令和9年度用 教科書・シラバス
NHK_URL = "https://edu.web.nhk/kokokoza/kagakuningen/"               # NHK高校講座 科学と人間生活

# ─────────────────────────────────────────────
# 科目の位置づけ
# ─────────────────────────────────────────────
PROFILE = pd.DataFrame([
    ("位置づけ", "高等学校 理科の基礎的な科目。理科の必履修は「科学と人間生活＋基礎を付した科目1つ」か"
                "「基礎を付した科目3つ」のどちらか（選択必履修）。多くの学校では1年次に履修する"),
    ("学ぶこと", "物理・化学・生物・地学の4分野を横断し、身近な現象や科学技術と結びつけて学ぶ"),
    ("ねらい", "暗記に偏らず、観察・実験やデータ・グラフの読み取りを通して、実生活に生かせる科学的な思考力・判断力を養う"),
    ("特徴", "複雑な数式は少ない。そのぶん「何を測り、どう比べ、どう判断するか」に時間を使える"),
    ("学び直し", "NHK高校講座（科学と人間生活）で映像講義を視聴できる"),
], columns=["項目", "内容"])

# 学習指導要領の内容構成（大項目 → 中項目 → 小項目）。小項目は fieldwork_pdca.UNIT_BRIDGE の「単元」と同じ名前
CURRICULUM = pd.DataFrame([
    ("(1) 科学技術の発展", "科学技術の発展", "科学技術の発展と人間生活"),
    ("(2) 人間生活の中の科学", "ア 光や熱の科学", "光の性質とその利用"),
    ("(2) 人間生活の中の科学", "ア 光や熱の科学", "熱の性質とその利用"),
    ("(2) 人間生活の中の科学", "イ 物質の科学", "材料とその再利用"),
    ("(2) 人間生活の中の科学", "イ 物質の科学", "衣料と食品"),
    ("(2) 人間生活の中の科学", "ウ 生命の科学", "ヒトの生命現象"),
    ("(2) 人間生活の中の科学", "ウ 生命の科学", "微生物とその利用"),
    ("(2) 人間生活の中の科学", "エ 宇宙や地球の科学", "太陽と地球"),
    ("(2) 人間生活の中の科学", "エ 宇宙や地球の科学", "自然景観と自然災害"),
    ("(3) これからの科学と人間生活", "これからの科学と人間生活", "探究・まとめ（フィールドワークの事後学習と重なる）"),
], columns=["大項目", "中項目", "小項目"])

# ─────────────────────────────────────────────
# 調査地の型 → 直前に置く単元・問いの例（「単元」と「調査地」の紐付け）
# ─────────────────────────────────────────────
SITES = pd.DataFrame([
    ("農場・パン工房（スマートパン屋農家）", "微生物とその利用／衣料と食品／熱の性質とその利用",
     "買ったイーストがなくてもパンは膨らむか。停電したら何を熱源にするか"),
    ("自然公園・里山", "自然景観と自然災害／微生物とその利用",
     "なぜここにこの植物が多いのか。落ち葉はどこへ消えるのか"),
    ("川・海岸・ため池", "光の性質とその利用／自然景観と自然災害",
     "上から見た水深は本当の深さか。どこまでなら歩いて渡れるのか"),
    ("工場・スマートシティ", "熱の性質とその利用／材料とその再利用",
     "なぜこの素材が使われているのか。捨てる熱はどこへ行くのか"),
    ("浄水場・ごみ処理施設", "微生物とその利用／材料とその再利用",
     "水をきれいにしているのは機械か、微生物か。リサイクルで何が失われるのか"),
    ("病院・福祉施設", "ヒトの生命現象／光の性質とその利用",
     "同じ暑さでも、人によって危ない度合いが違うのはなぜか"),
], columns=["調査地の型", "直前に置く単元", "問いの例"])


def bridge_question(unit: str, site: str, days_before: int = 7) -> str:
    """授業の終わりに投げかける「問いのブリッジ（架け橋）」の文面を作る。"""
    when = "明日" if days_before == 1 else f"{days_before}日後に"
    return (f"今日学んだ「{unit}」の知識を使って、{when}行く「{site}」について、どんな疑問が湧くか？"
            "疑問を1つ書き、その答えを確かめるには現地で何を1つ測ればよいかも書こう。")


def units_for_site(site: str) -> list[str]:
    """調査地の型に合う単元（UNIT_BRIDGE にある名前だけ）を返す。"""
    row = SITES[SITES["調査地の型"] == site]
    if row.empty:
        return []
    names = row.iloc[0]["直前に置く単元"].split("／")
    return [n for n in names if n in set(fp.UNIT_BRIDGE["単元"])]


# ─────────────────────────────────────────────
# 事前学習の演習：光の屈折と「水深の錯覚」（① 計算 → ② 可視化 → ③ 判断）
# ─────────────────────────────────────────────
N_WATER = 1.33


def apparent_depth(real_m: float, n: float = N_WATER) -> float:
    """真上近くから見たときの見かけの深さ（m）。見かけ ≒ 実際 ÷ 屈折率。"""
    if real_m < 0 or n <= 1:
        raise ValueError("深さは0以上、屈折率は1より大きくしてください")
    return real_m / n


def real_from_apparent(apparent_m: float, n: float = N_WATER) -> float:
    """見かけの深さから実際の深さを逆算する。現場で使う向き（見えた深さ×1.33）。"""
    if apparent_m < 0 or n <= 1:
        raise ValueError("深さは0以上、屈折率は1より大きくしてください")
    return apparent_m * n


def depth_table(max_m: float = 1.2, step: float = 0.1, n: float = N_WATER) -> pd.DataFrame:
    real = np.round(np.arange(0, max_m + 1e-9, step), 2)
    return pd.DataFrame({"実際の深さ(m)": real, "見かけの深さ(m)": np.round(real / n, 3)})


def wade_decision(apparent_m: float, my_limit_m: float, n: float = N_WATER, flowing: bool = False) -> tuple[str, float]:
    """見えた深さ・自分の歩行の目安・流れの有無から判断する。

    流れがあると、同じ深さでも足をとられやすいので、目安を半分にして判断する（教育用の安全側の仮定）。
    """
    real = real_from_apparent(apparent_m, n)
    limit = my_limit_m * (0.5 if flowing else 1.0)
    if real >= limit:
        return "渡らない（引き返す・高い所で待つ）", real
    if real >= 0.7 * limit:
        return "渡らない方がよい（目安の7割を超えている）", real
    return "目安の範囲内。ただし足元が見えない水には入らないのが原則", real


COLAB_SNIPPET = '''# 情報Ⅰ「モデル化とシミュレーション」：見かけの深さを計算してグラフにする
import numpy as np
import matplotlib.pyplot as plt

n = 1.33                          # 水の屈折率（真上近くから見たときの近似）
real = np.arange(0, 1.21, 0.1)     # 実際の深さ（m）
apparent = real / n               # 見かけの深さ（m）

plt.plot(real, apparent, marker="o", label="見かけの深さ")
plt.plot(real, real, linestyle="--", label="実際の深さ")
plt.xlabel("実際の深さ (m)"); plt.ylabel("深さ (m)"); plt.legend(); plt.show()

# 問い：膝の高さ（例 0.45 m）に「見えた」とき、実際は何 m か？
print(round(0.45 * n, 2), "m")
'''

# ─────────────────────────────────────────────
# PDCA の発展形と、伴走キット ❶〜❺ の対応
# ─────────────────────────────────────────────
PDCA_VARIANTS = pd.DataFrame([
    ("❶ 事前学習（HA）", "PDCA 2.0 の Purpose", "意味・意図を描く",
     "なぜこの調査地に行くのか、どの単元のレンズを掛けるのかを先に言葉にする", "実務書の呼び方（学術用語ではない）"),
    ("❷ 日々の伴走", "PDCA 2.0 の Dialogue", "対話が動きを生む",
     "答えを言わずに問い返す声かけ。準備度の低い生徒から対話する", "実務書の呼び方（学術用語ではない）"),
    ("❸ 本番（CCP）", "OODA ループ", "観察→情勢判断→決定→行動 を高速で",
     "現場では計画どおりにいかない。管理基準を見て、その場で判断して是正する", "J. Boyd が提唱した意思決定の枠組み"),
    ("❹ 事後（検証）", "PDSA サイクル の Study", "点検ではなく学ぶ",
     "「予想どおりだったか」の点検で終わらず、「なぜずれたか」を分析する", "W. E. Deming が Check を Study に改めた"),
    ("❺ 次の一手（是正処置）", "SDCA サイクル", "うまくいった手順を標準化して維持",
     "効いたワークシート・質問・管理基準を次回の標準にする。改善はPDCA、維持はSDCA", "TQM（総合的品質管理）の標準化サイクル"),
], columns=["伴走キットの段", "PDCAの発展形", "要点", "フィールドワークでの使い方", "出どころ"])


def _selftest() -> None:
    assert abs(apparent_depth(1.33) - 1.0) < 1e-9
    assert abs(real_from_apparent(apparent_depth(0.6)) - 0.6) < 1e-9
    try:
        apparent_depth(-1)
        raise AssertionError("負の深さを通してしまった")
    except ValueError:
        pass
    tb = depth_table()
    assert (tb["見かけの深さ(m)"] <= tb["実際の深さ(m)"]).all()
    msg, real = wade_decision(0.45, 0.5)            # 膝くらいに見えても実際は約0.60m
    assert real > 0.5 and msg.startswith("渡らない")
    msg2, _ = wade_decision(0.15, 0.5)
    assert msg2.startswith("目安の範囲内")
    assert wade_decision(0.15, 0.5, flowing=True)[0].startswith("渡らない")  # 流れがあれば厳しく
    for site in SITES["調査地の型"]:
        assert units_for_site(site), f"{site} に対応する単元がない"
    assert set(fp.UNIT_BRIDGE["単元"]) <= set(CURRICULUM["小項目"])
    assert "微生物とその利用" in bridge_question("微生物とその利用", "農場", 7)
    assert len(PDCA_VARIANTS) == 5
    # 姉妹サイト：単元名の語彙がそろっていること、リンク先のページが実在すること
    assert set(ss.UNITS) <= set(CURRICULUM["小項目"])
    for _a, _b, units, _w in ss.PAIRS:
        assert set(units) <= set(fp.UNIT_BRIDGE["単元"]), units
    from pathlib import Path
    assert ss.check_local_pages("bakery", Path(__file__).parent) == [], "姉妹サイトのリンク先ページが見つからない"
    print("kagaku_ningen_fw: すべてのチェックに合格しました")


if __name__ == "__main__":
    _selftest()

"""
diary_text.py — 作業日誌の自由記述を「データ」として読むための小さな部品

テキスト分析 第1回の手順（数える → 原文に戻る → 言える範囲を決める）を、
小規模農業法人の作業日誌に当てはめたもの。画面は pages/5_🔤_作業日誌テキスト分析.py、
同じ手順のノートブックは notebooks/text_analysis_work_diary.ipynb。
写真の側（画像分析）は diary_vision.py。

方針
  - 文字列の一致で「候補」を拾うだけ。困りごとかどうかの最終判断は人が原文を読んで決める。
  - 分析の前に匿名化する（mask）。外部の生成AIには、この部品は何も送らない。
  - 出現回数（回）と該当した日誌（件）を区別し、分母を必ず返す。
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

import pandas as pd

# 研究メモで決めた3語（ここを変えると画面とノートブックの両方に効く）
KEYWORDS = ["遅れ", "故障", "人手"]

# 打ち消し・充足の言い方（この形なら「困りごとではない」候補）。語ごとに意味が違う点に注意：
#   「遅れはない」は困りごとなし。しかし「人手がない」は困りごとあり。
NEG_PATTERNS = {
    "遅れ": r"(遅れ|遅延)(は|が|も)?(ない|なし|なかった|無し)",
    "故障": r"故障(は|が|も)?(ない|なし|なかった|無し)",
    "人手": r"人手(は|が|も)?(足りた|足りている|十分)",
}

# 言い換え（第1段の3語では漏れるもの）。(?<!人) で「人手が足りない」の二重計上を防ぐ
SYNONYMS = {
    "遅れ": [r"遅延"],
    "故障": [r"壊れ", r"動かなくなっ"],
    "人手": [r"(?<!人)手が足り"],
}

# 匿名化の置き換え先
MASK_LABELS = {"人名": "［人名］", "取引先": "［取引先］"}


def mask(text: str, names: Iterable[str] = (), partners: Iterable[str] = ()) -> str:
    """辞書に載った氏名・取引先名を置き換える。長い名前から先に置き換えて取りこぼしを防ぐ。"""
    out = str(text)
    for words, label in [(partners, MASK_LABELS["取引先"]), (names, MASK_LABELS["人名"])]:
        for w in sorted({w.strip() for w in words if str(w).strip()}, key=len, reverse=True):
            out = out.replace(w, label)
    return out


def normalize(text: str) -> str:
    """見た目が同じでも別の文字（全角英数・半角カナ・全角空白など）を NFKC でそろえる。
    第1回 発展A1：同じ「が」でも len が 2 になることがある。そろえないと検索が漏れる。"""
    return unicodedata.normalize("NFKC", str(text))


def residual(texts: Iterable[str], words: Iterable[str]) -> list[str]:
    """匿名化のあとに残ってしまった語（0件でなければ分析に進まない）"""
    joined = "\n".join(map(str, texts))
    return [w for w in words if str(w).strip() and str(w) in joined]


def search(df: pd.DataFrame, word: str, col: str = "本文", regex: bool = False) -> dict:
    """部分文字列（または正規表現）の一致を数え、4点セット（規則・単位と分母・ID・原文）を返す。"""
    pat = word if regex else re.escape(word)
    counts = df[col].astype(str).str.count(pat)
    hit = df[counts > 0].assign(回数=counts[counts > 0])
    return {
        "規則": f"{'正規表現' if regex else '部分文字列'}「{word}」の一致",
        "語": word,
        "回数": int(counts.sum()),
        "件数": len(hit),
        "分母": len(df),
        "ID": hit["ID"].tolist() if "ID" in hit else hit.index.tolist(),
        "該当": hit,
    }


def kwic(df: pd.DataFrame, word: str, width: int = 8, col: str = "本文") -> pd.DataFrame:
    """検索語の左右 width 文字を並べる（Key Word In Context）。1件に2回あれば2行になる。"""
    rows = []
    for _, r in df.iterrows():
        t = str(r[col])
        start = t.find(word)
        while start != -1:
            rows.append({
                "ID": r.get("ID", ""),
                "左": t[max(0, start - width):start],
                "語": word,
                "右": t[start + len(word):start + len(word) + width],
            })
            start = t.find(word, start + 1)
    return pd.DataFrame(rows, columns=["ID", "左", "語", "右"])


def rule_label(text: str, keyword: str) -> str:
    """規則による仮判定：打ち消し・充足の形なら『否定』、そうでなければ『困りごと』。"""
    pat = NEG_PATTERNS.get(keyword)
    return "否定" if pat and re.search(pat, str(text)) else "困りごと"


def naive_label(text: str) -> str:
    """素朴な規則：文のどこかに「ない・なし・なかった」があれば否定とみなす（失敗例として使う）"""
    return "否定" if re.search(r"ない|なし|なかった", str(text)) else "困りごと"


def hit_table(df: pd.DataFrame, keywords: Iterable[str] = KEYWORDS, col: str = "本文") -> pd.DataFrame:
    """日誌×語の組み合わせごとに1行。規則の仮判定を付けた『読む順番の表』。"""
    rows = []
    for kw in keywords:
        for _, r in df[df[col].astype(str).str.contains(re.escape(kw))].iterrows():
            rows.append({**r.to_dict(), "語": kw, "回数": str(r[col]).count(kw),
                         "規則の判定": rule_label(r[col], kw)})
    cols = list(df.columns) + ["語", "回数", "規則の判定"]
    return pd.DataFrame(rows, columns=cols)


def synonym_hits(df: pd.DataFrame, col: str = "本文") -> pd.DataFrame:
    """3語では拾えず、言い換えでだけ拾える日誌（検索の漏れの見本）"""
    base = df[col].astype(str).str.contains("|".join(map(re.escape, KEYWORDS)))
    rows = []
    for kw, pats in SYNONYMS.items():
        for p in pats:
            m = df[col].astype(str).str.contains(p, regex=True) & ~base
            for _, r in df[m].iterrows():
                rows.append({"ID": r.get("ID", ""), "分類": kw, "言い換え": p.replace("(?<!人)", ""),
                             "本文": r[col], "規則の判定": rule_label(r[col], kw)})
    return pd.DataFrame(rows, columns=["ID", "分類", "言い換え", "本文", "規則の判定"])


# ------------------------------------------------------------
# 検証用：第2回「生成AIと始めるPython」の for 文・if 文・カウンタをそのまま書いたもの
#   pandas 版（search）と同じ答えになるかを、手で数えられる小さな例で確かめるために使う。
# ------------------------------------------------------------
def count_answers(texts: Iterable[str], word: str) -> int:
    """回答件数：語を含む日誌が何件あるか（in + if）。カウンタは繰り返しの「前」で 0 にする。"""
    answer_count = 0
    for text in texts:
        if word in str(text):
            answer_count = answer_count + 1
    return answer_count


def count_occurrences(texts: Iterable[str], word: str) -> int:
    """出現回数：語が全部で何回現れたか（count）。1件に2回あれば2と数える。"""
    total = 0
    for text in texts:
        total = total + str(text).count(word)
    return total


def count_answers_buggy(texts: Iterable[str], word: str) -> int:
    """わざと間違えた例：カウンタを for の内側で 0 に戻している（最後の1件分しか残らない）。
    エラーは出ないので、手で数えた答えと比べないと気づけない。"""
    answer_count = 0
    for text in texts:
        answer_count = 0  # ← ここが誤り
        if word in str(text):
            answer_count = answer_count + 1
    return answer_count


def trace(texts: Iterable[str], word: str, ids: Iterable[str] | None = None) -> pd.DataFrame:
    """トレース表：カウンタの値が1件ごとにどう変わるかを1行ずつ記録する（DNCLの手で追う表と同じ形）。"""
    texts = list(texts)
    ids = list(ids) if ids is not None else [str(i) for i in range(len(texts))]
    rows, n = [{"i": "—", "ID": "—", "本文": "（繰り返しの前）", f"「{word}」を含む？": "—", "answer_count": 0}], 0
    for i, (id_, t) in enumerate(zip(ids, texts)):
        hit = word in str(t)
        n += int(hit)
        rows.append({"i": str(i), "ID": id_, "本文": str(t), f"「{word}」を含む？": "はい" if hit else "いいえ",
                     "answer_count": n})
    return pd.DataFrame(rows)


def three_lines(word: str, res: dict, judged: pd.DataFrame) -> str:
    """提出用の3行（観測／解釈と根拠／限界）。観測と解釈を分け、解釈にはIDと原文を根拠として付ける。"""
    obs = (f"観測：「{word}」を部分文字列一致で検索。出現{res['回数']}回／該当{res['件数']}件／"
           f"分母{res['分母']}件（{res['件数'] / max(res['分母'], 1):.1%}）。")
    j = judged[judged["語"] == word] if len(judged) else judged
    if len(j) == 0:
        mid = "解釈と根拠：まだ原文を読んでいない（人の判定が0組）。割合は困りごとの割合ではない。"
    else:
        parts = []
        for lab in ["困りごと", "否定", "保留"]:
            g = j[j["人の判定"] == lab]
            if len(g):
                ex = g.iloc[0]
                parts.append(f"{lab}{len(g)}件（{'・'.join(g['ID'].head(4))}{'ほか' if len(g) > 4 else ''}。"
                             f"例 {ex['ID']}「{str(ex['本文'])[:24]}」）")
        mid = f"解釈と根拠：判定した{len(j)}件のうち、" + "、".join(parts) + "。"
    syn = "・".join(f"「{p.replace('(?<!人)', '')}」" for p in SYNONYMS.get(word, []))
    lim = (f"限界・次に調べること：言い換え{'（' + syn + '等）' if syn else ''}は「{word}」では拾えない。"
           "判定者は1人で、規則は手元の日誌を見て作った後付け。件数は重要度ではなく、止まった時間は日誌に無い。")
    return "\n".join([obs, mid, lim])

"""
diary_text.py — 作業日誌の自由記述を「データ」として読むための小さな部品

テキスト分析 第1回の手順（数える → 原文に戻る → 言える範囲を決める）を、
小規模農業法人の作業日誌に当てはめたもの。画面は pages/5_🔤_作業日誌テキスト分析.py、
同じ手順のノートブックは notebooks/text_analysis_work_diary.ipynb。

方針
  - 文字列の一致で「候補」を拾うだけ。困りごとかどうかの最終判断は人が原文を読んで決める。
  - 分析の前に匿名化する（mask）。外部の生成AIには、この部品は何も送らない。
  - 出現回数（回）と該当した日誌（件）を区別し、分母を必ず返す。
"""
from __future__ import annotations

import re
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

"""
教材ネットワーク（姉妹サイト）の定義 ─ 2つのリポジトリに「同じ内容」で置くファイル

  🌾 スマートパン屋農家          … 現場：畑・ハウス・パン工房で確かめる（フィールドワーク）
  🧬 体をつくるタンパク質        … 教室：教科書の1単元を Python で動かす（事前学習）

  教室で「計算・可視化」したことを、現場で「判断」する。現場で湧いた問いを、教室で「計算」し直す。
  この往復を、ページどうしのリンク（PAIRS）として1か所で定義する。

直し方
  - このファイルを直したら、もう一方のリポジトリにも**同じ内容でコピー**し、NETWORK_VERSION を上げる。
  - ページのURLは「pages/ のファイル名から番号・絵文字を除いた部分」（Streamlit の既定の url_path）。
    存在しない URL は相手のホームに飛んでしまうため、各リポジトリのテストで check_local_pages() を必ず通す。
  - 単元名は学習指導要領「科学と人間生活」の小項目と同じ名前を使う（スマートパン屋農家の UNIT_BRIDGE と共通語彙）。

Streamlit に依存しない（render() の中だけで import する）。
"""
from __future__ import annotations

import unicodedata
from pathlib import Path

NETWORK_VERSION = "2026-11-06"

SITES: dict[str, dict] = {
    "bakery": {
        "name": "スマートパン屋農家",
        "icon": "🌾",
        "role": "現場（フィールドワーク）：畑・ハウス・パン工房で確かめる",
        "app": "https://smart-bakery-farm.streamlit.app",
        "repo": "https://github.com/nayukaya3-cn/Smart-Bakery-Farmer_20260923",
    },
    "tanpaku": {
        "name": "体をつくるタンパク質",
        "icon": "🧬",
        "role": "教室（事前学習）：教科書の1単元をPythonで動かす",
        "app": None,  # Streamlit Cloud で公開したら URL を入れる（None の間は GitHub に案内）
        "repo": "https://github.com/nayukaya3-cn/Science-and-Our-Daily-Life-dashboard",
    },
}

# 学習指導要領「科学と人間生活」の小項目（共通語彙）
UNITS = (
    "科学技術の発展と人間生活", "光の性質とその利用", "熱の性質とその利用", "材料とその再利用",
    "衣料と食品", "ヒトの生命現象", "微生物とその利用", "太陽と地球", "自然景観と自然災害",
)

# ページどうしの対応：((サイト, ページ), (サイト, ページ), 単元, なぜつながるか)
#   ページ "" はホーム。どちらの端から見ても、もう一方の端が「つながるページ」として表示される。
PAIRS: list[tuple[tuple[str, str], tuple[str, str], tuple[str, ...], str]] = [
    (("tanpaku", ""), ("bakery", ""), (),
     "教室（事前学習）と現場（フィールドワーク）の姉妹サイト。教室で計算し、現場で判断する"),
    (("tanpaku", "shoka"), ("bakery", "科学と人間生活_FW事前学習"), ("衣料と食品", "ヒトの生命現象"),
     "パン用小麦のタンパク質（グルテン）も、食べれば消化されてアミノ酸になる。"
     "教室で確かめた『食べ物は材料、設計図は自分の遺伝子』を、畑と工房で見る"),
    (("tanpaku", "field"), ("bakery", "フィールドワーク伴走"), ("衣料と食品", "ヒトの生命現象"),
     "事前学習（教室）→ 本番（畑・工房）→ 事後 を一続きに。"
     "小麦アレルギーは小麦のタンパク質に対する免疫の反応で、当日の重要管理点（アレルゲン）につながる"),
    (("tanpaku", "idenshi"), ("bakery", "微生物からの挑戦"), ("微生物とその利用",),
     "パンを膨らませる酵母も、ヒトとほぼ同じ遺伝暗号の表でタンパク質（酵素）をつくる"),
    (("tanpaku", "joho1"), ("bakery", "共通テスト理科×情報Ⅰ"), (),
     "同じ情報Ⅰの道具（文字列・辞書・場合の数）で、共通テスト理科の題材を解く"),
]


def url(site: str, page: str = "") -> str | None:
    """相手のページの URL。アプリが未公開なら None。"""
    app = SITES[site]["app"]
    if not app:
        return None
    return f"{app.rstrip('/')}/{page}" if page else app


def pairs_for(site: str, page: str) -> list[tuple[str, str, str]]:
    """（このサイト, このページ）から見た、つながる相手 [(相手サイト, 相手ページ, 理由)]"""
    out = []
    for a, b, _units, why in PAIRS:
        if a == (site, page):
            out.append((b[0], b[1], why))
        elif b == (site, page):
            out.append((a[0], a[1], why))
    return out


def pairs_for_unit(unit: str, here: str) -> list[tuple[str, str, str]]:
    """単元名から、もう一方のサイトのつながるページを探す（here は自分のサイト）"""
    out = []
    for a, b, units, why in PAIRS:
        if unit in units:
            other = b if a[0] == here else a
            out.append((other[0], other[1], why))
    return out


def local_pages(site: str) -> set[str]:
    """PAIRS に出てくる、このサイト側のページ名"""
    return {end[1] for a, b, _u, _w in PAIRS for end in (a, b) if end[0] == site}


def check_local_pages(site: str, root: Path) -> list[str]:
    """このサイト側のページが pages/ に実在するか。見つからないページ名のリストを返す（空なら合格）"""
    files = [unicodedata.normalize("NFC", p.stem) for p in (Path(root) / "pages").glob("*.py")]
    missing = []
    for page in local_pages(site):
        if page and not any(f.endswith(unicodedata.normalize("NFC", page)) for f in files):
            missing.append(page)
    return missing


def render(here_site: str, here_page: str = "", title: str = "🔗 姉妹サイトでつながるページ") -> None:
    """ページの下に「つながるページ」を表示する（Streamlit 専用）"""
    import streamlit as st

    links = pairs_for(here_site, here_page)
    if not links:
        return
    with st.container(border=True):
        st.markdown(f"**{title}**")
        for site, page, why in links:
            s = SITES[site]
            target = url(site, page)
            c1, c2 = st.columns([3, 1])
            c1.markdown(f"{s['icon']} **{s['name']}** ─ {why}")
            if target:
                c2.link_button("開く ↗", target, width="stretch")
            else:
                c2.link_button("GitHub ↗", s["repo"], width="stretch")
                c1.caption("アプリは公開準備中です（GitHub でコードと説明を見られます）")


def render_unit(unit: str, here_site: str) -> None:
    """単元名から、もう一方のサイトの教材を案内する（Streamlit 専用）"""
    import streamlit as st

    for site, page, why in pairs_for_unit(unit, here_site):
        s = SITES[site]
        target = url(site, page) or s["repo"]
        st.markdown(f"- {s['icon']} 姉妹サイト「{s['name']}」：{why} → [開く]({target})")


def _self_check() -> None:
    sites = set(SITES)
    for a, b, units, why in PAIRS:
        assert a[0] in sites and b[0] in sites and a[0] != b[0], (a, b)
        assert set(units) <= set(UNITS), units
        assert why
    assert pairs_for("tanpaku", "shoka") and pairs_for("bakery", "科学と人間生活_FW事前学習")
    assert pairs_for_unit("ヒトの生命現象", "bakery")[0][0] == "tanpaku"
    assert url("bakery", "フィールドワーク伴走").endswith("/フィールドワーク伴走")


if __name__ == "__main__":
    _self_check()
    print("sister_sites: 自己チェックOK", NETWORK_VERSION)

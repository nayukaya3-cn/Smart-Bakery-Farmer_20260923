"""
スマートパン屋農家を始める！ — 入口（左メニューの組み立て）

起動: streamlit run app.py
  ホームの中身は home.py、各ページは pages/ にあります。

左メニューは「だれが・何のために開くか」で5つに束ねています。
  人が一度に見分けられる塊は 4±1（Cowan, 2001）。1つのまとまりも、ページは最大6つまで。
  ページを足すときは NAV に1行足すだけです（ファイルが無い行は自動で飛ばします）。
"""
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent
MAX_CATEGORIES = 6

st.set_page_config(page_title="スマートパン屋農家を始める！", page_icon="🌾", layout="wide")

# まとまり → [(ファイル, 表示名, アイコン)]
# pages/ のファイルは先頭の番号（"1_" など）で探す。Macで作った日本語・絵文字のファイル名は
# 文字の内部表現（NFC/NFD）が違うことがあり、名前をそのまま書くと見つからないため。
NAV = {
    "🌾 スマートパン屋農家": [
        ("home.py", "ホーム", "🏠"),
    ],
    "🎓 学校向けの探究": [
        ("1", "記録が残る探究", "📋"),
        ("3", "比べて確かめる探究", "⚖️"),
        ("6", "中学理科 量の計算", "🧪"),
        ("7", "メタバース工房", "🌐"),
        ("8", "3Dプリンター", "🖨️"),
        ("10", "AIロボット", "🤖"),
    ],
    "📝 共通テスト×情報Ⅰ": [
        ("18", "共通テスト『理科』を情報Ⅰで解く", "🔬"),
    ],
    "🎮 探究コーナー": [
        ("12", "ゲーム運営の目で見る", "🎮"),
        ("13", "異常検知の実践知", "🚨"),
        ("14", "衛星データ解析", "🛰️"),
        ("15", "自給と防災の畑", "🍞"),
        ("20", "AI×特別支援教育・訓練", "🧩"),
        ("21", "ハウス収穫ロボ体験実習", "🍅"),
    ],
    "🔬 研究・実証": [
        ("5", "作業日誌テキスト＋画像分析", "🔤"),
        ("16", "機械学習で見つける（探究）", "🧠"),
        ("17", "微生物（酵母・乳酸菌等）からの挑戦", "🦠"),
        ("19", "福祉×生成AI", "🤝"),
        ("22", "AI時代に残る仕事（就活と起業）", "🧭"),
        ("2", "地元の農業法人での農作業", "🌾"),
    ],
    "🔒 管理": [
        ("9", "セキュリティログ", "🔒"),
        ("11", "収入構造（本人のみ）", "💴"),
        ("4", "自給家計簿（本人のみ）", "🌾"),
    ],
}


def find_page(key: str) -> str | None:
    """「home.py」はそのまま、「1」などの番号は pages/1_*.py を探して、相対パスで返す。"""
    if key.endswith(".py"):
        return key if (ROOT / key).exists() else None
    hits = sorted((ROOT / "pages").glob(f"{key}_*.py"))
    return str(hits[0].relative_to(ROOT)) if hits else None


def build_nav() -> dict[str, list]:
    assert len(NAV) <= MAX_CATEGORIES, "まとまりが多すぎます"
    nav = {}
    for section, items in NAV.items():
        assert len(items) <= MAX_CATEGORIES, f"「{section}」のページが多すぎます"
        pages = [
            st.Page(found, title=title, icon=icon, default=(key == "home.py"))
            for key, title, icon in items
            if (found := find_page(key))  # まだ置いていないページは出さない
        ]
        if pages:
            nav[section] = pages
    return nav


st.navigation(build_nav()).run()

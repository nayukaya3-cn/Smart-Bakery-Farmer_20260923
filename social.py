"""
SNSリンク（Facebook・LinkedIn）— 全ページ共通のボタン

URLを変えるときは、ここだけ書きかえれば全ページに反映されます。
  - LINKEDIN_URL は、閲覧者が開くと「あなたの」プロフィールが出る URL
    （例：https://www.linkedin.com/in/xxxx/）にしてください。
    https://www.linkedin.com/feed/ は「開いた人自身」のフィードになるため、活動内容は見えません。
"""
import streamlit as st

FACEBOOK_URL = "https://www.facebook.com/profile.php?id=100079624235158"
LINKEDIN_URL = "https://www.linkedin.com/in/%E9%9A%86%E8%A6%8F-%E6%A5%A0%E9%A6%99%E8%B0%B7-392aa12a0/"

# (アイコン, サービス名, URL)
SOCIALS = [
    ("📘", "Facebook", FACEBOOK_URL),
    ("💼", "LinkedIn", LINKEDIN_URL),
]
NAMES = "・".join(name for _, name, _ in SOCIALS)  # 文中で使う「Facebook・LinkedIn」


def buttons(action: str = "で活動内容を見る", stacked: bool = False) -> None:
    """Facebook と LinkedIn のボタンを並べて表示する。

    action  : ボタン文言のサービス名の後ろ（例："で活動内容を見る" → 「LinkedInで活動内容を見る」）
    stacked : True で縦に積む（サイドバーなど幅の狭い場所用）
    """
    if stacked:
        for icon, name, url in SOCIALS:
            st.link_button(f"{icon} {name}{action}", url, width="stretch")
        return
    for col, (icon, name, url) in zip(st.columns(len(SOCIALS)), SOCIALS):
        with col:
            st.link_button(f"{icon} {name}{action}", url, width="stretch")

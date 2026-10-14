"""
3Dプリンター ─ 自助具から、畑とパンの道具へ（学校向けの探究）
配置先: pages/8_🖨️_3Dプリンター.py
もとは home.py の「🔎 詳しく見る → 🖨️ 3Dプリンター」タブ。学校向けの探究として独立したページにした。
記録は assets/3d_printer/YYYYMMDD/ に置くと、下の「記録・資料」に表示される。
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import media_gallery as mg

ROOT = Path(__file__).parents[1]
ASSETS = ROOT / "assets"


def page_path(no: str) -> str:
    """pages/ の中から番号で始まるファイルを探す（Mac由来の文字の違いに強くする）。"""
    hits = sorted((ROOT / "pages").glob(f"{no}_*.py"))
    return f"pages/{hits[0].name}" if hits else f"pages/{no}_"


def safe_page_link(page: str, label: str, icon: str) -> None:
    try:
        st.page_link(page, label=label, icon=icon)
    except Exception:  # noqa: BLE001
        st.caption(f"{icon} {label}（左のメニューから開けます）")


def school_box(title: str, steps: list[tuple[str, str]], subjects: list[tuple[str, str]]) -> None:
    """学校向け：この題材を探究テーマにするときの3段構えと、つながる教科。"""
    with st.container(border=True):
        st.markdown(f"#### 🎓 探究テーマにするなら：{title}")
        for col, (head, body) in zip(st.columns(len(steps)), steps):
            col.markdown(f"**{head}**  \n{body}")
        st.dataframe(pd.DataFrame(subjects, columns=["教科", "つながるところ"]),
                     width="stretch", hide_index=True)
        l1, l2 = st.columns(2)
        with l1:
            safe_page_link(page_path("1"), "記録が残る探究（ルーブリック・活動ログ）", "📋")
        with l2:
            safe_page_link(page_path("3"), "比べて確かめる探究（くじで分けて測る）", "⚖️")

COCRE_HUB_URL = "https://cocrehub.com/"

st.set_page_config(page_title="3Dプリンター", page_icon="🖨️", layout="wide")

st.header("🖨️ 3Dプリンターで、道具を自分でつくる")
st.write(
    "3Dプリンターは、まったくの初心者からのスタートです。"
    "いきなり設計はせず、**本で基本を学び、公開されているデータを印刷する**ところから始めます。"
    "慣れてきたら、寸法を変えて自分の手や畑に合わせ、最後は畑とパンの道具を自分で設計します。"
)

school_box(
    "握りやすい持ち手は、何mm？",
    [
        ("① 計算する", "太さ20・30・40mmの持ち手を設計し、樹脂の量と1個あたりの費用を計算する"),
        ("② 可視化する", "家族や友だちに使ってもらい、作業時間と「握りやすさ（1〜5）」をグラフにする"),
        ("③ 自分の条件で判断する", "使う人の手の大きさ・握る力に合わせて、どの太さにするかを決める"),
    ],
    [
        ("数学", "体積・比例（太さを変えると樹脂の量と費用がどう変わるか）"),
        ("技術・家庭／情報", "3Dデータの寸法を変える・設計して試作する"),
        ("福祉・公民", "自助具：だれでも作業に参加できる道具とは"),
        ("美術", "形と使いやすさ（ユニバーサルデザイン）"),
    ],
)
st.divider()

st.subheader("手引きにするもの")
r1, r2 = st.columns(2)
with r1:
    st.markdown(
        "##### 📗 『はじめてでも簡単！3Dプリンタで自助具を作ろう』\n"
        "林 園子 著（三輪書店）。作業療法士の視点で、自助具（食事・書字・つまむ動作などを助ける道具）を"
        "3Dプリンターで作る手順が、はじめての人向けにまとめられています。"
    )
with r2:
    st.markdown(
        "##### 🌐 COCRE HUB（コクリハブ）\n"
        "自助具など、誰もが暮らしやすくなる道具の3Dデータを共有し、**ともにつくる**ためのプラットフォーム。"
        "公開データをダウンロードして、そのまま、または寸法を調整して印刷できます。"
    )
    st.link_button("🌐 COCRE HUB を見る", COCRE_HUB_URL)

st.subheader("ステップ：ハードルを低く、少しずつ")
steps3d = pd.DataFrame([
    ("① 学ぶ", "本で、プリンターの仕組み・材料・安全な使い方を知る", "書籍", "いまここ"),
    ("② 印刷する", "COCRE HUB の公開データを、そのまま印刷してみる", "COCRE HUB", "次"),
    ("③ 合わせる", "持ち手の太さ・長さなど、寸法だけ変えて自分や家族に合わせる", "書籍＋COCRE HUB", "予定"),
    ("④ つくる", "畑やパンで「あったら便利」な道具を自分で設計する", "自分の現場", "予定"),
], columns=["段階", "やること", "手がかり", "状況"])
st.dataframe(steps3d, width="stretch", hide_index=True)

st.subheader("つくってみたいもの（アイデア）")
ideas = pd.DataFrame([
    ("自助具", "スコップ・ハサミ・スプーンの太い持ち手", "握る力が弱くても、畑やパンづくりの作業がしやすくなる"),
    ("自助具", "ペットボトル・袋のオープナー", "作業の合間の「ちょっとした不便」を減らす"),
    ("畑", "苗ラベル・支柱どうしを留めるクリップ", "壊れたら同じものをすぐ印刷し直せる"),
    ("畑", "土壌センサーのケース・取り付け台", "圃場モニターのセンサーを雨や泥から守る"),
    ("畑", "モグラよけ風車の軸受け部品", "ペットボトル風車の回転をなめらかにする"),
    ("パン", "生地の厚みをそろえるガイド・カードの台", "形と焼きムラをそろえる"),
], columns=["分野", "つくるもの", "ねらい"])
st.dataframe(ideas, width="stretch", hide_index=True)
st.caption("車椅子でも通れる通路づくりと同じく、「誰でも作業に参加しやすい畑」にするための道具として考えています。")

st.subheader("① 計算する：1個つくるといくら？")
q = st.columns(5)
grams = q[0].number_input("使う樹脂の量 g", 1, 1000, 30)
fil_price = q[1].number_input("フィラメント 円/kg", 1000, 10000, 2500, 100)
hours = q[2].number_input("印刷時間 時間", 0.1, 48.0, 2.0, 0.5)
watt = q[3].number_input("消費電力 W", 50, 500, 120, 10)
kwh_price = q[4].number_input("電気代 円/kWh", 10, 80, 31)
mat_cost = grams / 1000 * fil_price
elec_cost = watt / 1000 * hours * kwh_price
m1, m2, m3 = st.columns(3)
m1.metric("材料費", f"{mat_cost:.0f} 円")
m2.metric("電気代", f"{elec_cost:.0f} 円")
m3.metric("1個あたり合計", f"{mat_cost + elec_cost:.0f} 円")
st.caption("※ 失敗印刷・プリンター本体の購入費・手間は含みません。目安を知るための簡易計算です。")

with st.expander("⚠️ 注意しておくこと"):
    st.markdown(
        "- **食品に直接ふれる道具は慎重に**：積層のすき間に汚れや菌が残りやすく、洗浄しにくいことがあります。"
        "パンの生地に直接ふれるものは、用途と材料を確かめてから使います。\n"
        "- **自助具は使う人に合わせる**：体の状態に合わせた調整が大切です。"
        "必要に応じて作業療法士などの専門職に相談します。\n"
        "- 公開データを使うときは、各データの**利用条件（ライセンス）**を確認します。\n"
        "- 印刷中は高温になります。換気をし、子どもの手が届かないようにします。"
    )

st.divider()
mg.media_section(ASSETS / "3d_printer", key="p3d", title="📂 3Dプリンターの記録・資料")

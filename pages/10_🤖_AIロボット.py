"""
AIロボット ─ 記録 → シミュレーション → 実機（学校向けの探究）
配置先: pages/10_🤖_AIロボット.py
もとは home.py の「🔎 詳しく見る → 🤖 AIロボット」タブ。学校向けの探究として独立したページにした。
記録は assets/robot/YYYYMMDD/ に置くと、下の「記録・資料」に表示される。
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

st.set_page_config(page_title="AIロボット", page_icon="🤖", layout="wide")

st.header("🤖 AIロボットで、畑を見回る")
st.write(
    "最終的には、小さなロボットが畑を巡回して写真やセンサー値を集め、"
    "「AI土壌診断」につなげることを目指しています。"
    "ただし、いまは**人の手とスマホで記録している段階**です。"
    "実機を動かす前に、まずはパソコンの中（シミュレーション）で試すところから進めます。"
)

school_box(
    "写真の重なりは、何％がちょうどいい？",
    [
        ("① 計算する", "重なり％を変えると、走る距離・時間・撮影枚数がどう変わるかを下の計算で求める"),
        ("② 可視化する", "重なり0〜60％の結果を表とグラフにし、「時間」と「撮りもれの少なさ」の関係を見る"),
        ("③ 自分の条件で判断する", "充電1回で走れる時間と、AIが見分けたい細かさから、自分の畑の設定を決める"),
    ],
    [
        ("物理基礎", "距離・速さ・時間（巡回の所要時間）"),
        ("数学", "割り算と切り上げ（往復の本数）、グラフで関係を読む"),
        ("情報Ⅰ", "シミュレーション、ループと条件分岐、ROS 2 へのつながり"),
        ("公民・情報倫理", "ロボットに任せる作業・人がやる作業の線引き、写り込みとプライバシー"),
    ],
)
st.divider()

st.subheader("ステップ")
steps_rb = pd.DataFrame([
    ("① 人が記録する", "スマホで同じ位置から定点撮影し、写真とメモを残す", "スマホ・活動ログ", "いまここ"),
    ("② シミュレーションで試す", "ROS 2 とシミュレーターで、約96㎡の畑を巡回する経路を作る", "ROS 2・Gazebo", "次"),
    ("③ 小型ロボットで巡回", "カメラ付きの小型ローバーで、決めた経路を走って撮影する", "小型ローバー", "予定"),
    ("④ AIとつなぐ", "集めた写真を「AI土壌診断」に流し、生育ムラや雑草の分布を自動で集計する", "AI土壌診断タブ", "予定"),
], columns=["段階", "やること", "使うもの", "状況"])
st.dataframe(steps_rb, width="stretch", hide_index=True)

st.subheader("① 計算する → ② 可視化する：巡回ルートを設計する")
st.write("畑を往復しながら撮影する「芝刈り型」のルートで、走る距離・時間・撮影枚数を見積もります。")
rc_in, rc_out = st.columns([1, 2])
with rc_in:
    fw = st.number_input("畑の幅 m", 2.0, 50.0, 8.0, 0.5)
    fd = st.number_input("畑の奥行き m", 2.0, 50.0, 12.0, 0.5)
    swath = st.slider("カメラが1回で写す幅 m", 0.5, 3.0, 1.5, 0.1)
    overlap = st.slider("写真の重なり %", 0, 60, 30, 5)
    speed = st.slider("走る速さ m/秒", 0.05, 1.0, 0.2, 0.05)

step = swath * (1 - overlap / 100)
n_lanes = int(np.ceil(fw / step))
xs, ys = [], []
for k in range(n_lanes):
    x = min(step / 2 + k * step, fw)
    y0, y1 = (0, fd) if k % 2 == 0 else (fd, 0)
    xs += [x, x]
    ys += [y0, y1]
path_len = float(np.sum(np.hypot(np.diff(xs), np.diff(ys))))
n_photos = int(np.ceil(path_len / step)) + 1

with rc_out:
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("往復の本数", f"{n_lanes} 本")
    k2.metric("走る距離", f"{path_len:.0f} m")
    k3.metric("所要時間", f"{path_len / speed / 60:.0f} 分")
    k4.metric("撮影枚数", f"{n_photos} 枚")
    fig = go.Figure()
    fig.add_shape(type="rect", x0=0, y0=0, x1=fw, y1=fd,
                  fillcolor="rgba(155,184,132,.25)", line=dict(color="#9a9a9a", dash="dot", width=1))
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name="巡回ルート",
                             line=dict(color="#8a4b12", width=2), marker=dict(size=4, color="#8a4b12")))
    fig.add_trace(go.Scatter(x=[xs[0]], y=[ys[0]], mode="markers+text", text=["スタート"],
                             textposition="bottom center", marker=dict(size=12, color="#3b2f1e"),
                             showlegend=False))
    fig.update_xaxes(title="幅 m", range=[-0.5, fw + 0.5])
    fig.update_yaxes(title="奥行き m", range=[-1, fd + 0.5], scaleanchor="x", scaleratio=1)
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
    st.plotly_chart(fig, width="stretch")
st.caption(f"畑の面積 {fw * fd:.0f} ㎡ のモデル。曲がる時間や充電は含まない簡易計算です。"
           "シミュレーションでは、この経路をROS 2のナビゲーションに渡して走らせることを想定しています。")

st.subheader("③ 自分の条件で判断する：ロボットに任せる？ 人がやる？")
cmp_ = pd.DataFrame([
    ("定点撮影（週1回）", "人", "数分で終わる。まずは人で十分"),
    ("畑全体の撮影（生育ムラ）", "ロボット候補", "毎回同じ経路・同じ高さで撮れるとAIの比較精度が上がる"),
    ("雑草の判定", "AI＋人", "AIが候補を出し、最終判断は人が行う"),
    ("草刈り・収穫", "人", "刃物や重い作業は、当面ロボットに任せない"),
], columns=["作業", "担い手", "理由"])
st.dataframe(cmp_, width="stretch", hide_index=True)

with st.expander("⚠️ 安全について"):
    st.markdown(
        "- ロボットを動かすのは、**人が近くで見守れるとき**だけにします。非常停止の手段を必ず用意します。\n"
        "- 実機の前に、必ずシミュレーションで経路と動きを確かめます。\n"
        "- 撮影した写真に人や近所の家が写り込まないよう、撮影範囲に気をつけます。\n"
        "- 通信でつながる機器なので、初期パスワードの変更など**基本的なセキュリティ対策**を行います。"
    )

st.divider()
mg.media_section(ASSETS / "robot", key="robot", title="📂 AIロボットの記録・資料")

"""
AIロボット ─ 記録 → シミュレーション → 実機（学校向けの探究）
配置先: pages/10_🤖_AIロボット.py
もとは home.py の「🔎 詳しく見る → 🤖 AIロボット」タブ。学校向けの探究として独立したページにした。
記録は assets/robot/YYYYMMDD/ に置くと、下の「記録・資料」に表示される。

タブ
  🗺️ 巡回ルートを設計する … 畑を見回るロボットの経路（写真の重なり・距離・時間）
  🌱 除草 0〜5            … 除草AIロボット・シミュレーター（docs/sim/weeding_robot.html）と、その探究
                             計算は weeding_lab.py（`python weeding_lab.py` で自己チェック）
このページはロボットを動かさない。除草のモデルは教育用の単純化で、実機の性能を再現したものではない。
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import media_gallery as mg
import weeding_lab as wl

ROOT = Path(__file__).parents[1]
ASSETS = ROOT / "assets"
WEED_SIM = ROOT / "docs" / "sim" / "weeding_robot.html"
# 全画面は「同じページ＋?view=weedsim」で開く（Streamlit の静的配信は HTML を text/plain で返すため）
WEED_SIM_URL = "?view=weedsim"
METHOD_KEYS = {"ハンド（抜き取り）": "ハンド（抜き取り）", "レーザー（シミュレーターの中だけ）": "レーザー"}


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

if st.query_params.get("view") == "weedsim":
    st.markdown("**🌱 除草AIロボ・シミュレーター（全画面）**　"
                "記録の「CSVをコピー」は、元のページの「除草 3 ② 可視化する」に貼ってください。")
    if WEED_SIM.exists():
        st.iframe(WEED_SIM, height=2100)  # リポジトリ内の自作ファイルだけを埋め込む
    else:
        st.error("シミュレーターのファイルが見つかりません。")
    st.stop()

st.header("🤖 AIロボットで、畑を見回る・雑草を取る")
st.write(
    "最終的には、小さなロボットが畑を巡回して写真やセンサー値を集め、"
    "「AI土壌診断」や除草につなげることを目指しています。"
    "ただし、いまは**人の手とスマホで記録している段階**です。"
    "実機を動かす前に、まずはパソコンの中（シミュレーション）で試すところから進めます。"
)

T = st.tabs(["🗺️ 巡回ルートを設計する", "🌱 除草 0 問いと安全", "除草 1 体験する", "除草 2 ① 計算する",
             "除草 3 ② 可視化する", "除草 4 ③ 自分の条件で判断する", "除草 5 授業と実機への点検"])

# ═════════════════════ 巡回ルート（もとのページ） ═════════════════════
with T[0]:
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

# ═════════════════════ 除草 0 問いと安全 ═════════════════════
with T[1]:
    st.subheader("🌱 除草AIロボット・シミュレーター")
    st.write("除草は、栽培管理の中でも時間を取られる作業で、農薬を減らす有機栽培ではとくに大きな手間になります。"
             "AIロボットに任せると楽になりそうですが、AIは**雑草を取り残す**ことも、**小麦を雑草と読み違えて傷める**こともあります。"
             "小麦の畑で困るのは、スズメノテッポウのような**イネ科の雑草が小麦とよく似ている**ことです。")
    school_box(
        "除草AIの「しきい値 τ」は、いくつがちょうどいい？",
        [
            ("① 計算する", "AIの点数の分布（正規分布）から、雑草を取る割合・小麦を傷める割合と、雑草による減収を求める"),
            ("② 可視化する", "ROC曲線と、シミュレーターで集めた記録で「人の目・AIだけ・AI＋人」を比べる（ベイズ）"),
            ("③ 自分の条件で判断する", "雑草の多さ・取り方・人が使える時間から、自分の畑の τ と「人が確かめる幅」を決める"),
        ],
        [
            ("生物基礎", "単子葉（イネ科：小麦・スズメノテッポウ）と双子葉（広葉の雑草）の葉の形の違い"),
            ("数学", "正規分布と確率、関数のグラフ（雑草の密度と減収の曲線）"),
            ("情報Ⅰ", "モデル化とシミュレーション、データの活用、ROS 2 へのつながり"),
            ("公民・情報倫理", "AIに任せる作業・人が決める作業の線引き、カメラの写り込み"),
        ],
    )
    st.markdown("#### 安全の段階：なぜ、最初はシミュレーターなのか")
    st.write("体験を4段に分け、段ごとに、その危険に人がさらされるか（起こりやすさ 0〜4）を置きます。"
             "リスク点＝重さ（1〜4）×起こりやすさ。値は仮置きなので、表を直して自分たちの現場に合わせてください。")
    hz = st.data_editor(
        wl.HAZARDS, hide_index=True, width="stretch", key="wd_hz",
        column_config={"重さ": st.column_config.NumberColumn(min_value=1, max_value=4),
                       **{s: st.column_config.NumberColumn(f"段{s}", min_value=0, max_value=4) for s in wl.STAGE_COLS},
                       "対策の種類": st.column_config.SelectboxColumn(options=wl.STEP3)})
    long = wl.risk_table(hz).melt(id_vars=["危険", "重さ"], var_name="段階", value_name="リスク点")
    fig = px.density_heatmap(long, x="段階", y="危険", z="リスク点", text_auto=True,
                             color_continuous_scale=["#f4f1ea", "#e9b44c", "#b5523b"], range_color=[0, 16])
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), coloraxis_showscale=False,
                      xaxis_title=None, yaxis_title=None)
    st.plotly_chart(fig, width="stretch")
    st.dataframe(wl.stage_summary(hz), hide_index=True, width="stretch")
    st.info("シミュレーターの段には危険がありません。**刃も光も熱もない場所で、取り残し・読み違いを先に体験しておく**のが、"
            "この探究のいちばんの安全対策です。実機のレーザーは、目とやけど・火災の危険が大きいため扱いません。")

# ═════════════════════ 除草 1 体験する ═════════════════════
with T[2]:
    st.subheader("体験する：画像認識で見分け、ロボットハンドで抜く")
    st.markdown(
        "1. **遠隔操作（人）**：門型ロボを走らせ（A・D）、ハンドを左右に動かし（W・S）、"
        "右下の搭載カメラの映像で雑草を見つけたら「ここを抜く」。終わったら「答え合わせ」。\n"
        "2. **AI自動**：同じ畑の番号で「自動除草を開始」。カメラの画像認識が植物に点数 s を付け、"
        "s ≥ τ の植物をハンドが根ごと抜く。赤い枠に小麦が混ざっていないか見る。\n"
        "3. **AI＋人**：AIが迷った植物（黄色の枠）で止まるので、人が「抜く（Y）／残す（N）」を決める。\n"
        "4. 取り方を「レーザー」に替えて試す。**CSVをコピー**して「除草 3」に貼る。"
    )
    st.link_button("シミュレーターを全画面で開く", WEED_SIM_URL)
    if WEED_SIM.exists():
        st.iframe(WEED_SIM, height=2050)  # リポジトリ内の自作ファイルだけを埋め込む（外部や利用者の入力は渡さない）
    else:
        st.error("シミュレーターのファイル（docs/sim/weeding_robot.html）が見つかりません。")
    st.caption("記録はブラウザの中だけにあり、どこにも送られません。数値は教材用の仮置きで、実機の性能ではありません。")

# ═════════════════════ 除草 2 ① 計算する ═════════════════════
with T[3]:
    st.subheader("① 計算する：AIの点数と、雑草による減収")
    st.markdown(
        "AIは1本ごとに「雑草らしさ」の点数 **s（0〜1）** を出し、**s ≥ τ なら雑草として取る**とします。"
        "点数のもとになる値 z は、種類ごとに平均がちがう正規分布に従うとみなします（信号検出理論）。\n\n"
        "- 小麦：平均 −d/2　／　広葉の雑草：平均 +d/2　／　イネ科の雑草：平均 0（小麦に似ているので中間）\n"
        "- s = 1 / (1 + e^(−z))、取る確率 = 1 − Φ(logit τ − 平均)\n"
        "- d（見分けやすさ）は、シミュレーターの見分けにくさ h から **d = 4 − 3h** で決めています。"
    )
    c1, c2 = st.columns([1, 2])
    with c1:
        h = st.slider("見分けにくさ h", 0.0, 1.0, 0.5, 0.1, key="wd_h")
        d = wl.d_from_difficulty(h)
        tau = st.slider("しきい値 τ", 0.05, 0.95, 0.5, 0.05, key="wd_tau")
        grass = st.slider("雑草のうちイネ科の割合", 0.0, 1.0, wl.GRASS_DEFAULT, 0.1, key="wd_grass")
        r = wl.classify_rates(tau, d, grass)
        st.metric("見分けやすさ d", f"{d:.1f}")
        st.metric("雑草を取る割合", f"{r['雑草を取る割合']:.0%}",
                  help=f"広葉 {r['広葉を取る割合']:.0%}／イネ科 {r['イネ科を取る割合']:.0%}")
        st.metric("小麦を読み違える割合", f"{r['小麦を読み違える割合']:.1%}")
    with c2:
        ss = wl.score_samples(d)
        fig = px.histogram(ss, x="点数", color="種類", nbins=40, barmode="overlay", opacity=0.6,
                           color_discrete_map={"小麦": "#5f9a3b", "広葉の雑草": "#2f6db0", "イネ科の雑草": "#c98a2b"})
        fig.add_vline(x=tau, line_dash="dash", line_color="#c92a2a", annotation_text=f"τ={tau:.2f}")
        fig.update_layout(height=340, margin=dict(l=10, r=10, t=30, b=10), yaxis_title="本数（見本）")
        st.plotly_chart(fig, width="stretch")
        st.caption("τ より右が「取る」。小麦の山の右すそが τ を越えたぶんだけ、小麦を傷めます。"
                   "イネ科の山は小麦と広葉のあいだにあり、どこに τ を置いても半分近くは迷います。")

    st.markdown("#### 雑草が残ると、どれだけ減るか（Cousens 1985 の双曲線モデル）")
    st.latex(r"\text{減収\%} = \frac{I\,N}{1 + I\,N / A}")
    st.caption(f"N：雑草の本数／㎡、I：雑草が少ないときの1本あたりの減収％（仮置き {wl.COUSENS_I}）、"
               f"A：雑草が非常に多いときの減収の上限％（仮置き {wl.COUSENS_A:.0f}）。I と A は作物・雑草の種類で大きく変わります。")
    nn = np.arange(0, 201, 5)
    fig = go.Figure(go.Scatter(x=nn, y=[wl.yield_loss(n) for n in nn], mode="lines", line=dict(color="#8a4b12", width=3)))
    fig.add_hline(y=wl.COUSENS_A, line_dash="dot", line_color="#9a9a9a", annotation_text="上限 A")
    fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="雑草 N 本／㎡", yaxis_title="減収 %")
    st.plotly_chart(fig, width="stretch")

    st.markdown("#### 4つのやり方を、同じ条件で計算する")
    k1, k2, k3, k4 = st.columns(4)
    area = k1.number_input("畑の面積 ㎡", 1.0, 2000.0, 96.0, 1.0, key="wd_area")
    weeds = k2.number_input("雑草 本／㎡", 0.0, 300.0, 30.0, 1.0, key="wd_weeds")
    crops = k3.number_input("小麦 株／㎡", 1.0, 400.0, 80.0, 1.0, key="wd_crops")
    band = k4.slider("AI＋人：人が確かめる幅 ±", 0.0, 0.3, 0.15, 0.05, key="wd_band")
    m1, m2 = st.columns(2)
    method = METHOD_KEYS[m1.radio("ロボットの取り方", list(METHOD_KEYS), horizontal=True, key="wd_method")]
    acc = m2.slider("人が正しく見分ける確率", 0.6, 1.0, wl.HUMAN_ACC, 0.01, key="wd_acc")
    cp = wl.compare_plans(area, weeds, crops, tau, band, d, grass, method, acc)
    st.dataframe(cp.round({"残る雑草_本m2": 1, "傷んだ小麦の割合": 3, "雑草による減収_%": 1, "期待収量": 1,
                           "ロボット_分": 0, "人_分": 0}), hide_index=True, width="stretch")
    st.caption(f"期待収量＝100×（1−傷んだ小麦の割合）×（1−減収%/100）。人の手は1本 {wl.HAND_SEC:.0f} 秒、"
               f"画面で確かめるのは1本 {wl.CHECK_SEC:.0f} 秒、ロボットは {wl.ROBOT_SPEED} m/s で幅 {wl.SWATH:.0f} m ずつ走る（曲がる時間・充電は含まない）。"
               f"ハンドは株元の雑草（{wl.INROW_SHARE:.0%}）を抜くとき {wl.METHODS['ハンド（抜き取り）'][1]:.0%} の確率で隣の小麦の根を傷めるとしています。")

# ═════════════════════ 除草 3 ② 可視化する ═════════════════════
with T[4]:
    st.subheader("② 可視化する：ROC曲線と、記録の比べ方")
    v1, v2 = st.columns(2)
    with v1:
        st.markdown("**ROC曲線：τ を動かすと、取る割合と読み違いが一緒に動く**")
        fig = go.Figure()
        for hh, col in [(0.2, "#2f6db0"), (0.5, "#8a4b12"), (0.8, "#c98a2b")]:
            rc = wl.roc_curve(wl.d_from_difficulty(hh), grass)
            fig.add_trace(go.Scatter(x=rc["小麦を読み違える割合"], y=rc["雑草を取る割合"], mode="lines",
                                     name=f"h={hh}", line=dict(color=col, width=2)))
        r_now = wl.classify_rates(tau, d, grass)
        fig.add_trace(go.Scatter(x=[r_now["小麦を読み違える割合"]], y=[r_now["雑草を取る割合"]], mode="markers+text",
                                 text=[f"いまの τ={tau:.2f}"], textposition="bottom right", name="いまの設定",
                                 marker=dict(size=12, color="#c92a2a")))
        fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color="#aaa", dash="dot"), name="当てずっぽう"))
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10),
                          xaxis_title="小麦を読み違える割合", yaxis_title="雑草を取る割合")
        st.plotly_chart(fig, width="stretch")
        st.caption("左上に近いほど良いAI。h が大きい（似ている）ほど曲線が対角線に近づきます。τ を下げると右上へ動きます。")
    with v2:
        st.markdown("**τ と期待収量（① の条件で）**")
        tc = wl.tau_curve(weeds, crops, d, grass, method)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=tc["τ"], y=tc["期待収量"], mode="lines+markers", name="期待収量",
                                 line=dict(color="#2b8a3e", width=3)))
        fig.add_trace(go.Scatter(x=tc["τ"], y=100 - tc["雑草による減収_%"], mode="lines", name="雑草だけの損",
                                 line=dict(color="#2f6db0", dash="dot")))
        fig.add_trace(go.Scatter(x=tc["τ"], y=100 * (1 - tc["傷んだ小麦の割合"]), mode="lines", name="傷めだけの損",
                                 line=dict(color="#c98a2b", dash="dot")))
        bt, by = wl.best_tau(weeds, crops, d, grass, method)
        fig.add_vline(x=bt, line_dash="dash", line_color="#c92a2a", annotation_text=f"いちばん良い τ≈{bt:.2f}")
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="τ", yaxis_title="雑草なし・傷みなし＝100")
        st.plotly_chart(fig, width="stretch")
        st.caption("τ が低いと小麦を傷め、高いと雑草が残る。二つの損の掛け算がいちばん小さくなる τ を探します。")

    st.markdown("#### シミュレーターの記録を貼って、やり方を比べる")
    txt = st.text_area("「CSVをコピー」した記録（はじめは架空の例）", wl.SAMPLE_CSV, height=190, key="wd_csv")
    try:
        df = wl.parse_records(txt)
    except Exception as e:  # noqa: BLE001
        st.error(f"読めませんでした：{e}")
        df = None
    if df is not None and len(df):
        cm = wl.compare_modes(df)
        st.dataframe(cm.round(3), hide_index=True, width="stretch")
        long2 = cm.melt(id_vars="方式", value_vars=["雑草を取った割合", "小麦を傷めた割合"], var_name="指標", value_name="割合")
        fig = px.bar(long2, x="指標", y="割合", color="方式", barmode="group", text_auto=".0%",
                     color_discrete_map={"人の目": "#c98a2b", "AIだけ": "#2f6db0", "AI＋人": "#2b8a3e"})
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), yaxis_tickformat=".0%")
        st.plotly_chart(fig, width="stretch")
        modes = list(cm["方式"])
        if len(modes) >= 2:
            b1, b2 = st.columns(2)
            ma = b1.selectbox("比べる方式 A", modes, index=len(modes) - 1, key="wd_ma")
            mb = b2.selectbox("比べる方式 B", modes, index=0, key="wd_mb")
            p_w = wl.prob_better(df, ma, mb, "取った")
            p_c = wl.prob_better(df, ma, mb, "傷めた")
            if p_w is None:
                st.info("ちがう方式を2つ選んでください。")
            else:
                e1, e2 = st.columns(2)
                e1.metric(f"P（{ma} のほうが雑草を多く取る）", f"{p_w:.0%}")
                e2.metric(f"P（{ma} のほうが小麦を傷めない）", f"{p_c:.0%}")
                st.caption("ベイズ推論：割合の事前分布を一様（Beta(1,1)）とし、取った本数・傷めた本数で更新して、乱数で比べた確率です。"
                           "本数が少ないうちは50%に近く、ラウンドを重ねるほどはっきりします。")
        st.caption("初期表示の記録は教材用の架空データです。")

# ═════════════════════ 除草 4 ③ 自分の条件で判断する ═════════════════════
with T[5]:
    st.subheader("③ 自分の条件で判断する：τ と「人が確かめる幅」を決める")
    st.write("「① 計算する」の条件（畑の面積・雑草と小麦の多さ・見分けにくさ）で、取り方ごとにいちばん良い τ を出し、"
             "次に、人が確かめる幅を広げると**人の時間がどれだけ増え、収量がどれだけ戻るか**を見ます。")
    rows = []
    for label, key in METHOD_KEYS.items():
        bt, by = wl.best_tau(weeds, crops, d, grass, key)
        rows.append({"取り方": label, "いちばん良い τ": bt, "そのときの期待収量": round(by, 1)})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("ハンドは株元の雑草を抜くときに隣の小麦の根を傷めるので、τ を高め（取りすぎない）にしたほうが良くなりやすい。")

    bands = np.round(np.arange(0, 0.31, 0.05), 2)
    rec = []
    for b in bands:
        row = wl.compare_plans(area, weeds, crops, tau, float(b), d, grass, method, acc).set_index("案").loc["AI＋人"]
        rec.append({"幅": b, "人_分": row["人_分"], "期待収量": row["期待収量"]})
    bd = pd.DataFrame(rec)
    fig = go.Figure(go.Scatter(x=bd["人_分"], y=bd["期待収量"], mode="lines+markers+text",
                               text=[f"±{b:.2f}" for b in bd["幅"]], textposition="top left",
                               line=dict(color="#2b8a3e", width=3)))
    hand = wl.compare_plans(area, weeds, crops, tau, 0, d, grass, method, acc).set_index("案").loc["人の手"]
    fig.add_trace(go.Scatter(x=[hand["人_分"]], y=[hand["期待収量"]], mode="markers+text", text=["人の手だけ"],
                             textposition="bottom left", marker=dict(size=12, color="#c98a2b")))
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
                      xaxis_title="人の時間（分）", yaxis_title="期待収量")
    st.plotly_chart(fig, width="stretch")
    st.caption(f"τ={tau:.2f}・{method} のとき。幅を広げるほど右上へ。曲がり方が寝てきたところが「人の時間を足しても割に合わなくなる」点です。")

    budget = st.number_input("この畑に、人が使える時間（分）", 0, 600, 60, 10, key="wd_budget")
    ok = bd[bd["人_分"] <= budget]
    if len(ok):
        best = ok.loc[ok["期待収量"].idxmax()]
        st.success(f"人の時間 {budget} 分以内なら、幅 ±{best['幅']:.2f}（人 {best['人_分']:.0f} 分）で期待収量 {best['期待収量']:.1f}。")
    else:
        st.warning("この時間では、AI＋人の最小の幅でも足りません。AIだけにするか、畑を分けて何回かにします。")
    with st.container(border=True):
        st.markdown("**わたしの判断（ノートに書く）**")
        st.markdown("「わたしの畑なら、取り方は ＿＿＿、τ＝＿＿、人が確かめる幅は ±＿＿ にする。"
                    "なぜなら、＿＿＿（取り残し／傷め／時間／危険／費用）を一番大事にしたいから。」")
        st.caption("答えは人によって違います。収量だけでなく、時間・危険・費用・農薬を減らしたいか、も理由になります。")
    with st.expander("発展：τ を畑で少しずつ学ぶ（強化学習・ベイズ）"):
        st.write("毎回の除草のあとに「取り残し」と「傷め」を数え、次の τ を少しずつ変えていくと、"
                 "畑ごとの最適な τ に近づけます。候補の τ をいくつか用意し、良さそうなものを多めに試すのが"
                 "多腕バンディット（トンプソン抽出）です。探究コーナーの「ゲーム運営の目で見る」に同じ考え方があります。")

# ═════════════════════ 除草 5 授業と実機への点検 ═════════════════════
with T[6]:
    st.subheader("授業の進め方")
    plan = st.radio("時間", list(wl.LESSON_PLANS), horizontal=True, key="wd_plan")
    st.dataframe(wl.lesson_table(plan), hide_index=True, width="stretch")

    st.subheader("次の段（小型ローバー・畑）に進む前の点検")
    done = [st.checkbox(("【必須】" if must else "【推奨】") + t, key=f"wd_chk{i}")
            for i, (t, must) in enumerate(wl.NEXT_STAGE_CHECKS)]
    rd = wl.next_stage_readiness(done)
    st.progress(rd["準備度"], text=f"準備度 {rd['準備度']:.0%}")
    (st.error if rd["まだの必須"] else st.success)(rd["判定"])
    st.caption("刃の付いた実機に近づく段の配置・人数は、受け入れ先のリスクアセスメントで決めます。"
               "ロボットを扱う大人の条件（産業用ロボットにあたるか・特別教育）は、「ハウス収穫ロボ体験実習」の 6 にまとめています。")
    hits21 = sorted((ROOT / "pages").glob("21_*.py"))
    if hits21:
        safe_page_link(f"pages/{hits21[0].name}", "ハウス収穫ロボ体験実習（大人の条件・遠隔操作の見張り役）", "🍅")
    with st.expander("フィジカルAI：除草の「仕分け役」（ROS2ノードの例・表示のみ）"):
        st.write("AIの点数で「取る／残す／人に聞く」に分けます。非常停止や人の接近の合図が出ているあいだは、取る指令を出しません。")
        st.code(wl.ROS2_WEED_TRIAGE, language="python")
        st.caption("記録と運用の確認のためのノードで、安全機能ではありません。止める仕組みはロボット本体の非常停止で行います。")

    with st.expander("⚠️ 安全について"):
        st.markdown(
            "- ロボットを動かすのは、**人が近くで見守れるとき**だけにします。非常停止の手段を必ず用意します。\n"
            "- 教室の段のローバーには、刃・つめを付けません。\n"
            "- 実機のレーザーは扱いません（目・やけど・乾いた草の火災）。\n"
            "- 撮影した写真に人や近所の家が写り込まないよう、畑の内側だけを写します。"
        )
    with st.expander("出典・参考"):
        st.markdown("\n".join(f"- {s}" for s in wl.SOURCES))
    st.caption("© スマートパン屋農家プロジェクト ｜ 記録の初期表示と数値の多くは教材用の仮置きです。")

st.divider()
mg.media_section(ASSETS / "robot", key="robot", title="📂 AIロボットの記録・資料")

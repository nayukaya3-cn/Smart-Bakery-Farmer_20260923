"""
探究コーナー ─ 「ハウス収穫ロボ・シミュレーター」で安全安心な体験実習
配置先: pages/21_🍅_ハウス収穫ロボ体験実習.py （Streamlit のマルチページ構成）

問い
  ハウスの収穫ロボットを、中高生の職場体験・実習で扱うとき、危険を段階的に減らしながら
  「人の遠隔操作」と「AIの自動収穫」を比べ、自分の条件で AI の設定を決める体験を、どう組み立てるか。

7つの段（タブ）。骨格はリポジトリ共通の3段構え（① 計算する → ② 可視化する → ③ 自分の条件で判断する）
  0 安全の段階  1 体験する  2 ① 計算する  3 ② 可視化する  4 ③ 自分の条件で判断する  5 授業の進め方と実機への点検
  6 ロボットを扱う大人の条件（労働安全衛生法：産業用ロボットの教示等・検査等の特別教育）

計算は harvest_lab.py（`python harvest_lab.py` で自己チェック）。シミュレーター本体は docs/sim/harvest_robot_tomato.html。
このページはロボットを動かさない。モデルは教育用の単純化で、実機の性能を再現したものではない。
"""
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import harvest_lab as hl
import security_guard as sg

st.set_page_config(page_title="ハウス収穫ロボ体験実習", page_icon="🍅", layout="wide")

SIM = Path(__file__).parent.parent / "docs" / "sim" / "harvest_robot_tomato.html"
# 全画面は「同じページ＋?view=sim」で開く（GitHub Pages を有効にしていなくても動く。
# Streamlit の静的配信は HTML を text/plain で返すため使えない）
SIM_URL = "?view=sim"
MODE_COLORS = {"人（遠隔）": "#c98a2b", "AI": "#2f6db0"}

if st.query_params.get("view") == "sim":
    st.markdown("**🍅 ハウス収穫ロボ・シミュレーター（全画面）**　"
                "記録の「CSVをコピー」は、元のタブの「3 ② 可視化する」に貼ってください。")
    if SIM.exists():
        st.iframe(SIM, height=2100)  # リポジトリ内の自作ファイルだけを埋め込む
    else:
        st.error("シミュレーターのファイルが見つかりません。")
    st.stop()

st.title("🍅 ハウス収穫ロボで、安全安心な体験実習")
st.caption("刃も熱も重さもない教室から始め、段階を踏んで実機に近づく。人とAIの収穫を比べ、AIの設定を自分の条件で決める。"
           " ── ① 計算する → ② 可視化する → ③ 自分の条件で判断する")

with st.container(border=True):
    st.markdown(
        "**研究メモ**：ハウス内をレールで走る収穫ロボットを、教室から遠隔操作する出前授業は、小学校・幼稚園ですでに行われている。"
        "いっぽう、中高生の**職場体験**でハウス内のロボット収穫を扱った公開事例は、調べた範囲では見つからなかった。"
        "そこで、**① シミュレーター → ② 教室から実機を遠隔操作 → ③ ロボットを止めてハウス見学 → ④ 実機のそば**"
        "という4段で、危険を一つずつ増やしながら進める設計にする。"
        "問いは「**危険がゼロの段階で、AIの見落とし・読み違いと、遠隔操作の遅れを体で知っておくと、"
        "実機の段階で安全に、しかも考えて動けるか**」である。"
        "注意点は四つ。第一に、モデルは**教育用の単純化**で、実機の性能ではない。"
        "第二に、実機の段階の人数・配置は**受け入れ先のリスクアセスメント**で決める。"
        "第三に、カメラ映像に**顔や名札を映さない・録画しない**。"
        "第四に、ロボットの**教示・点検は、特別教育（安衛則 第36条第31号・第32号）を修了した受け入れ先の大人**が、"
        "生徒が来る前に済ませる。生徒にはさせない（6）。"
    )
    st.caption("いまは構想・準備の段階です。実機を使った体験実習の実施実績ではありません。")

with st.expander("このページの道のり：7つの段と、人・AI・Pythonの役割", expanded=False):
    st.markdown(
        "| 段 | すること | 担当 | 使う考え方 |\n|---|---|---|---|\n"
        "| 0 安全の段階 | 体験を4段に分け、危険を「重さ×起こりやすさ」で数える | 人が点を付け、Pythonが数える | リスクアセスメント（ISO 12100 の3ステップ） |\n"
        "| 1 体験する | シミュレーターで、人の遠隔操作とAIの自動収穫を1ラウンドずつ | 生徒 | 遠隔操作・画像認識 |\n"
        "| 2 ① 計算する | 遅れのあいだに進む距離、AIの検出と色の読み違いの式 | Pythonが計算する | モデル化・速度と間隔の監視 |\n"
        "| 3 ② 可視化する | 記録CSVを貼り、人とAIを比べる | Pythonが集計し、人が読む | ベイズ推論（ベータ分布） |\n"
        "| 4 ③ 判断する | 取り残しと誤収穫の損失から、しきい値 τ を決める | 人が決める | 期待損失の最小化 |\n"
        "| 5 授業と点検 | 45分・90分の流れ、実機に進む前の点検、ROS2の見張り役 | 人が判断する | チェックリスト・フィジカルAI（ROS2） |\n"
        "| 6 大人の条件 | 収穫ロボが産業用ロボットにあたるか、どの作業に特別教育が要るかを判定し、段ごとの役割を分ける | 法令が決め、受け入れ先が実施する | 安衛則36条31号・32号・ROS2の許可ゲート |"
    )

T = st.tabs(["0 安全の段階", "1 体験する", "2 ① 計算する", "3 ② 可視化する",
             "4 ③ 自分の条件で判断する", "5 授業の進め方と実機への点検",
             "6 ロボットを扱う大人の条件"])

# ═════════════════════ 0 安全の段階 ═════════════════════
with T[0]:
    st.subheader("問い：なぜ、最初はシミュレーターなのか")
    st.write("ハウスの収穫ロボットには、動く部分・刃・熱い温湯管・暑さ・農薬・通信の遅れ、と危険がいくつも重なります。"
             "体験を4段に分け、**段ごとに、その危険に人がさらされるか（起こりやすさ 0〜4）**を置きます。"
             "リスク点＝重さ（1〜4）×起こりやすさ。点の付け方は仮置きなので、表を直して自分たちの現場に合わせてください。")
    hz = st.data_editor(
        hl.HAZARDS, hide_index=True, width="stretch", key="hv_hz",
        column_config={"重さ": st.column_config.NumberColumn(min_value=1, max_value=4),
                       **{s: st.column_config.NumberColumn(f"段{s}", min_value=0, max_value=4) for s in hl.STAGE_COLS},
                       "対策の種類": st.column_config.SelectboxColumn(options=hl.STEP3)})
    rt = hl.risk_table(hz)
    long = rt.melt(id_vars=["危険", "重さ"], var_name="段階", value_name="リスク点")
    fig = px.density_heatmap(long, x="段階", y="危険", z="リスク点", text_auto=True,
                             color_continuous_scale=["#f4f1ea", "#e9b44c", "#b5523b"], range_color=[0, 16])
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), coloraxis_showscale=False,
                      xaxis_title=None, yaxis_title=None)
    st.plotly_chart(fig, width="stretch")
    st.dataframe(hl.stage_summary(hz), hide_index=True, width="stretch")
    st.info("シミュレーターの段に残るのは「通信の遅れ」だけで、それも画面の中の話です。"
            "**危険がゼロの場所で、遅れ・見落とし・読み違いを先に体験しておく**のが、この実習のいちばんの安全対策です。")
    st.markdown("**対策の順番（ISO 12100 の3ステップ）**：① 危険そのものをなくす・小さくする（本質的安全設計）"
                "→ ② 柵・非常停止などで守る（安全防護）→ ③ 注意書き・説明・教育で補う（使用上の情報）。"
                "説明や注意だけで済ませるのは、いちばん最後の手段です。")

# ═════════════════════ 1 体験する ═════════════════════
with T[1]:
    st.subheader("体験：人が遠隔で1ラウンド → AIで1ラウンド → 記録を比べる")
    st.markdown(
        "1. 右の操作盤で **遠隔操作（人）** を選び、◀▶で走行・▲▼でアームを上下。小窓（ロボット搭載カメラ）の枠が"
        "**黄色の実線**になったら「収穫する」。\n"
        "2. 「答え合わせ」を押す。取り残した適期果が赤枠で出る。\n"
        "3. **同じ乱数シードのまま**「圃場をつくり直す」→ **AI自動** で「自動収穫を開始」。\n"
        "4. 下の記録表の「CSVをコピー」を押し、**3 ② 可視化する** のタブに貼る。"
    )
    st.caption("画面が小さいときは、別のタブで全画面で開けます（記録はそのブラウザの中だけに残り、サーバーには送られません）。")
    st.link_button("シミュレーターを全画面で開く", SIM_URL)
    if SIM.exists():
        st.iframe(SIM, height=2050)  # リポジトリ内の自作ファイルだけを埋め込む（外部や利用者の入力は渡さない）
    else:
        st.warning("docs/sim/harvest_robot_tomato.html が見つかりません。上のボタンから開いてください。")

# ═════════════════════ 2 ① 計算する ═════════════════════
with T[2]:
    st.subheader("① 計算する：遅れは、何cmのずれになるか")
    st.write("遠隔操作では、ボタンを離してもロボットはすぐには止まりません。その間に進む距離は「速さ×遅れ」です。")
    st.latex(r"\Delta x = v \times t_{\mathrm{遅れ}}")
    c1, c2 = st.columns([1, 2])
    with c1:
        lat = st.slider("通信の遅れ（ms）", 0, 800, 150, 50, key="hv_lat")
        dx = hl.latency_overshoot(lat)
        st.metric("走行で余分に進む", f"{dx * 100:.1f} cm")
        st.metric("ハンドが届く範囲（中心から）", f"±{hl.REACH * 100:.0f} cm")
        st.metric("ずれが届く範囲を超えない遅れの上限", f"{hl.max_safe_latency():.0f} ms")
        if dx > hl.REACH:
            st.warning("ずれが届く範囲を超えます。ボタンを早めに離す「先読み」が要ります。")
    with c2:
        lc = hl.latency_curve()
        fig = px.line(lc, x="遅延_ms", y=["走行で余分に進む_cm", "上下で余分に動く_cm"], markers=True)
        fig.add_hline(y=hl.REACH * 100, line_dash="dash", annotation_text="届く範囲 7cm")
        fig.add_vline(x=lat, line_dash="dot")
        fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), legend_title=None, yaxis_title="cm")
        st.plotly_chart(fig, width="stretch")

    st.divider()
    st.markdown("#### 実機のそばでは：遅れは「人との距離」をのばす")
    st.write("協働ロボットの「速度と間隔の監視」の考え方（ISO/TS 15066）を単純化した式に、通信の遅れを"
             "「気づくまでの時間」として足します（式は「🧩 AI×特別支援教育」と共通）。")
    st.latex(r"S = v_h\,(T_r+t_{\mathrm{遅れ}}+T_s) + v_r\,(T_r+t_{\mathrm{遅れ}}) + \tfrac{1}{2}v_r\,T_s + C")
    v_r = st.slider("ロボットの速さ v_r（m/s）", 0.0, 1.0, 0.4, 0.1, key="hv_vr")
    d0, d1 = hl.remote_distance(v_r, 0), hl.remote_distance(v_r, lat)
    k = "合計（これより近づいたら止める）"
    m1, m2 = st.columns(2)
    m1.metric("その場で操作したとき", f"{d0[k]:.2f} m")
    m2.metric(f"遅れ {lat} ms で遠隔操作したとき", f"{d1[k]:.2f} m", f"+{d1[k] - d0[k]:.2f} m", delta_color="inverse")
    st.caption("だから、実機の段階では「人がハウスにいる間は、遠隔操作をしない」か「速さを落とす」を先に決めます。")

    st.divider()
    st.markdown("#### AIの「見える／見えない」のモデル（シミュレーターと同じ式）")
    st.code("検出スコア  s = 0.92 − 0.80·o + ε₁   ε₁~N(0, 0.08²)   → s ≥ τ で検出\n"
            "着色度推定  ĉ = c + ε₂               ε₂~N(0, (0.04+0.12·o)²) → ĉ ≥ 0.70 で収穫", language="text")
    st.write("o は葉の遮蔽率、c は着色度（緑 0 → 赤 1）、τ は信頼度しきい値。葉の陰ほど「見つからない」うえに「色を読み違える」。")

# ═════════════════════ 3 ② 可視化する ═════════════════════
with T[3]:
    st.subheader("② 可視化する：人とAI、どちらが取り残しが少ないか")
    st.write("シミュレーターの「CSVをコピー」で写した記録を、下に貼ってください。最初は**架空の記録**が入っています。")
    text = st.text_area("記録CSV", hl.SAMPLE_CSV, height=170, key="hv_csv", max_chars=20000)
    try:
        df = hl.parse_records(text)
    except Exception as e:  # 読めない貼り付けは、理由だけ伝えて止める
        sg.log_event("csv_parse_error", "INFO", page="harvest", error=type(e).__name__)
        st.error(f"読めませんでした：{e}")
        df = None
    if df is not None and len(df):
        if text.strip() == hl.SAMPLE_CSV.strip():
            st.caption("いま表示しているのは架空の記録です。")
        cm = hl.compare_modes(df)
        st.dataframe(cm.style.format({"適期果の収穫率": "{:.0%}", "誤収穫の割合": "{:.0%}", "秒／本（平均）": "{:.1f}"}),
                     hide_index=True, width="stretch")
        fig = px.scatter(df, x="適期果の収穫率", y="誤収穫の割合", color="方式", size="good", text="round",
                         hover_data=["condition", "occlusion"], color_discrete_map=MODE_COLORS)
        fig.update_traces(textposition="top center")
        fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10),
                          xaxis_tickformat=".0%", yaxis_tickformat=".0%")
        st.plotly_chart(fig, width="stretch")
        st.caption("右下ほどよい（たくさん採って、未熟果をまちがえない）。点の数字はラウンド番号。")

        p = hl.prob_ai_better(df)
        if p is None:
            st.info("人とAIの両方の記録があると、どちらの収穫率が高いかをベイズで確かめられます。")
        else:
            st.metric("AIの適期果の収穫率が、人より高い確率（ベイズ）", f"{p:.0%}")
            st.caption("収穫率を「採った数／（採った数＋取り残し）」として、一様な事前分布 Beta(1,1) から更新し、"
                       "乱数で2万回比べた割合。ラウンドが少ないうちは、確率が50%に近くなります。")
        st.download_button("記録を保存（CSV）", sg.safe_csv(df), "収穫ロボ_記録.csv", "text/csv")

    st.divider()
    st.markdown("#### モデルで見る：葉が増えると、AIは何を落とすか")
    tau_v = st.slider("しきい値 τ", 0.30, 0.90, 0.55, 0.05, key="hv_tau_v")
    oc = hl.occlusion_curve(tau_v)
    fig = go.Figure()
    fig.add_scatter(x=oc["遮蔽率"], y=oc["適期果の収穫率"], name="適期果の収穫率", mode="lines+markers",
                    line_color="#2b8a3e")
    fig.add_scatter(x=oc["遮蔽率"], y=oc["未熟果の誤収穫率"], name="未熟果の誤収穫率", mode="lines+markers",
                    line_color="#c92a2a")
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="葉の遮蔽率",
                      xaxis_tickformat=".0%", yaxis_tickformat=".0%")
    st.plotly_chart(fig, width="stretch")

# ═════════════════════ 4 ③ 自分の条件で判断する ═════════════════════
with T[4]:
    st.subheader("③ 自分の条件で判断する：しきい値 τ をいくつにするか")
    st.write("τ を下げるとたくさん見つけるが、まちがいも増える。上げると慎重になるが、取り残しが増える。"
             "どちらが痛いかは、**売り方・品種・人手**で変わります。答えは人によって違います。")
    c1, c2, c3 = st.columns(3)
    occ = c1.slider("自分のハウスの葉の遮蔽率", 0.0, 0.8, 0.3, 0.05, key="hv_occ")
    cmiss = c2.number_input("取り残し1本の損失（円）", 0, 500, 40, 5, key="hv_cm",
                            help="次の見回りで採れれば小さい。熟れすぎて出荷できなければ大きい")
    cfalse = c3.number_input("誤収穫1本の損失（円）", 0, 500, 90, 5, key="hv_cf",
                             help="育っていれば得られた売上＋出荷できない分")
    lc = hl.loss_curve(occ, cmiss, cfalse)
    bt, bl = hl.best_tau(occ, cmiss, cfalse)
    fig = px.line(lc, x="τ", y="損失_円", markers=True)
    fig.add_scatter(x=[bt], y=[bl], mode="markers", marker=dict(size=14, color="#b5523b"), name="最小")
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="損失（円／100本）", showlegend=False)
    st.plotly_chart(fig, width="stretch")
    st.success(f"遮蔽率 {occ:.0%} のこのハウスでは、**τ = {bt:.2f}** で損失が最小（100本あたり約 {bl:.0f} 円）。"
               "シミュレーターの「AI自動」で、この τ を入れて確かめてみましょう。")
    with st.container(border=True):
        st.markdown("**ワークシート：自分の一言**")
        st.text_input("自分の農園なら τ ＝ ○○。なぜなら……", key="hv_why",
                      placeholder="例：直売所では見た目が大事なので、未熟果をまちがえるほうが痛い。だから τ を高めにする")
        st.text_input("AIに任せること・人がやること", key="hv_split",
                      placeholder="例：見えている果実はAI、葉の陰は人があとで見回る")
        st.caption("書いた内容はこのブラウザの中だけにあり、保存も送信もされません。")

# ═════════════════════ 5 授業の進め方と実機への点検 ═════════════════════
with T[5]:
    st.subheader("授業の進め方")
    plan = st.radio("時間", list(hl.LESSON_PLANS), horizontal=True, key="hv_plan")
    lt = hl.lesson_table(plan)
    st.dataframe(lt, hide_index=True, width="stretch")
    fig = px.bar(lt, x="分", y=["すること"] * len(lt), color="すること", orientation="h", text="すること")
    fig.update_layout(height=140, margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
                      yaxis_visible=False, barmode="stack")
    st.plotly_chart(fig, width="stretch")

    st.divider()
    st.markdown("#### 実例：ロボット収穫を授業で扱った例（調べた範囲）")
    st.dataframe(hl.CASES, hide_index=True, width="stretch")
    st.caption("中高生の職場体験としてハウス内でロボット収穫を行った公開事例は、調べた範囲では見つかりませんでした。")

    st.divider()
    st.markdown("#### 次の段（実機）に進む前の点検")
    done = [st.checkbox(("【必須】" if must else "【推奨】") + t, key=f"hv_ck{i}")
            for i, (t, must) in enumerate(hl.NEXT_STAGE_CHECKS)]
    res = hl.next_stage_readiness(done)
    st.progress(res["準備度"], text=f"準備度 {res['準備度']:.0%}")
    (st.error if res["まだの必須"] else st.success)(res["判定"])

    with st.expander("フィジカルAI：遠隔操作の見張り役（ROS2ノードの例・表示のみ）"):
        st.write("教室からの指令がとだえたら止まり、速さにも上限をかける「ウォッチドッグ」です。"
                 "①で計算した遅れの上限より短い時間で止めます。遠隔操作の通信は、操作する端末の認証（SROS2 など）とあわせて使います。")
        st.code(hl.ROS2_TELEOP_GUARD, language="python")

# ═════════════════════ 6 ロボットを扱う大人の条件 ═════════════════════
with T[6]:
    st.subheader("問い：生徒が安全に体験するために、ロボットを扱う大人は何を済ませておくか")
    st.write("労働安全衛生法では、産業用ロボットの**教示等**（安衛則 第36条第31号）と**検査等**（第32号）の業務に就く人に、"
             "事業者が**特別教育**を行います。教える本人だけでなく、**組んで可動範囲の外で機器を操作する相棒**も対象です。"
             "生徒にはこれらの作業をさせません。ここで決めるのは、**受け入れ先の大人の条件**です。")
    with st.expander("きまりの一覧（2026年10月時点で確かめた範囲）"):
        st.dataframe(hl.ROBOT_LAW, hide_index=True, width="stretch")

    st.markdown("#### ① 計算する：その収穫ロボは「産業用ロボット」か、その作業に特別教育は要るか")
    a1, a2 = st.columns([1, 2])
    with a1:
        pw = st.number_input("いちばん大きいモーターの定格出力（W）", 0, 5000, 400, 10, key="hv6_w",
                             help="カタログの値。80W以下は告示第51号で産業用ロボットから除かれる")
        mani = st.checkbox("腕（マニプレータ）がある", True, key="hv6_m")
        mem = st.checkbox("動きを覚える記憶装置がある", True, key="hv6_mem")
        single = st.checkbox("一つの動作を単調に繰り返すだけ", False, key="hv6_single")
        rnd = st.checkbox("研究開発中の試作機", False, key="hv6_rnd")
        ir = hl.is_industrial_robot(pw, mani, mem, single, rnd)
        (st.warning if ir["あたるか"] else st.info)(("産業用ロボットにあたる" if ir["あたるか"] else "産業用ロボットにあたらない")
                                                + "（目安）")
        st.caption(ir["理由"])
    with a2:
        task = st.selectbox("作業", list(hl.HARVEST_TASKS), key="hv6_task")
        who = st.radio("その人は", ["受け入れ先の大人（働く人）", "生徒"], horizontal=True, key="hv6_who")
        r = hl.training_need(task, ir["あたるか"], who.startswith("受け入れ"))
        (st.error if r["判定"].startswith("生徒") else st.warning if r["判定"] == "特別教育が必要" else st.success)(
            f"**{r['判定']}**" + (f"　（{r['区分']}・学科と実技で {r['時間']} 時間以上）" if r["区分"] else ""))
        st.caption(f"起こる段：{r['段']}　／　{r['理由']}")

    st.markdown("#### ② 可視化する：段ごとの役割と、大人が受ける教育")
    st.dataframe(hl.STAGE_ROLES, hide_index=True, width="stretch")
    st.caption("教示・点検は、すべて「生徒が来る前」に済ませます。生徒がいる段にあるのは、運転と見学だけです。")
    b1, b2 = st.columns([3, 2])
    with b1:
        fig = px.bar(hl.TOKUBETSU_HOURS, x="時間（以上）", y="区分", color="種別", orientation="h",
                     hover_data=["科目"], text="科目", color_discrete_map={"学科": "#2b8a3e", "実技": "#b5523b"})
        fig.update_traces(textposition="inside", insidetextanchor="middle", textfont_size=10)
        fig.update_layout(height=230, margin=dict(l=10, r=10, t=10, b=10), barmode="stack", yaxis_title=None)
        st.plotly_chart(fig, width="stretch")
        st.caption("安全衛生特別教育規程 第18条・第19条。時間は最低時間。十分な知識・技能がある人は科目を省略できる（安衛則 第37条）。")
    with b2:
        e1, e2, e3 = st.columns(3)
        n_t = e1.number_input("教える人", 0, 5, 1, key="hv6_t")
        n_p = e2.number_input("組む相棒", 0, 5, 1, key="hv6_p")
        n_i = e3.number_input("運転中に点検", 0, 5, 0, key="hv6_i")
        plan_ = hl.staff_training_plan(int(n_t), int(n_p), int(n_i))
        st.dataframe(plan_, hide_index=True, width="stretch")
        st.metric("延べ時間（予備1人ずつを含む）", f"{int(plan_['延べ_時間'].sum())} 時間")
        st.caption("修了の記録（受講者・科目）は3年間保存する（安衛則 第38条）。")
    dd = hl.remote_distance(hl.TEACH_MODE_SPEED, 0)["合計（これより近づいたら止める）"]
    st.write(f"教示モードの速さの上限 **{hl.TEACH_MODE_SPEED*1000:.0f} mm/s**（ISO 10218-1）でも、「2 ① 計算する」の式では"
             f"止める距離は **{dd:.2f} m**。ゆっくりでも、教示中の可動範囲に生徒を入れない理由になります。")

    st.markdown("#### ③ 自分の条件で判断する：受け入れ先の道筋")
    st.markdown(
        "| 順番 | すること | 決める人 |\n|---|---|---|\n"
        "| 1. 機械を確かめる | 定格出力（80W）・記憶装置・安全機能（非常停止・速度の上限）をカタログとメーカーで確かめる | 受け入れ先・メーカー |\n"
        "| 2. 大人の教育 | 教える人と組む相棒、運転中に点検する人が特別教育を修了し、記録を残す | 受け入れ先 |\n"
        "| 3. 作業規程と配置 | 教示の手順・合図・異常時の止め方を決め、生徒が入る範囲を図にする（リスクアセスメント） | 受け入れ先・安全の専門家 |\n"
        "| 4. 体験の段を進める | 段0 → 段3 を、「5 授業の進め方と実機への点検」の必須がそろってから | 教員・受け入れ先 |"
    )
    st.caption("参考：工業高校では、ロボットインストラクターの資格をもつ教員が授業・実習の中で教示等の特別教育を行い、"
               "卒業時に修了証を出している例がある（東京都立蔵前工科高校）。この体験実習は職場体験なので、生徒に特別教育は行いません。")
    with st.expander("フィジカルAI：遠隔操作の「許可」を出す役（ROS2ノードの例・表示のみ）"):
        st.write("ハウスに人がいるとき、または修了者が許可していないときは、教室からの操作を通さず「止まれ」を出します。"
                 "人がいるかわからないときは「いる」とみなします。")
        st.code(hl.ROS2_TELEOP_PERMIT, language="python")
        st.caption("記録と運用の確認のためのノードで、安全機能ではありません。止める仕組みはロボット本体の非常停止・モード切替と、"
                   "「5」の見張り役（ウォッチドッグ）で行います。修了者は名前ではなくIDで持ちます。")

with st.expander("出典・参考"):
    st.markdown(
        "- 遠隔収穫の出前授業：マイナビ農業「AGRIST、館山市から茨城県のキュウリを教室から収穫」、"
        "同「千葉県初開催！100名の小学生が収穫作業を体験」、リセマム「鹿児島市幼稚園でキュウリの遠隔収穫体験」\n"
        "- 長崎総合科学大学「トマト収穫ロボットの開発」プロジェクト報告（トマトロボット競技会）\n"
        "- 労働安全衛生法 第59条第3項、労働安全衛生規則 第36条第31号・第32号・第37条・第38条・第150条の3〜第150条の5、"
        "安全衛生特別教育規程 第18条・第19条、昭和58年労働省告示第51号（80W）、平成25年12月24日 基発1224第2号（協働運転）\n"
        "- 日本ロボット工業会「産業用ロボットに関する労働安全衛生法令」、東京都立蔵前工科高校「ロボット安全特別教育修了証の発行について」\n"
        "- ISO 10218-1（教示モードの速さ 250 mm/s）\n"
        "- ISO 12100（機械類の安全性：リスクアセスメントとリスク低減の3ステップ）\n"
        "- ISO/TS 15066（協働ロボット）・ISO 13855（人の接近速度）：このページの式は教育用に単純化したもの\n"
        "- 暑さ指数（WBGT）：環境省 熱中症予防情報サイト\n"
        "- SROS2：ROS 2 の通信を認証・暗号化する仕組み（ROS 2 公式ドキュメント）"
    )
st.caption("© スマートパン屋農家プロジェクト ｜ 記録の初期表示は教材用の架空データです。"
           "このページはロボットを動かさず、シミュレーターの記録もサーバーに送りません。")

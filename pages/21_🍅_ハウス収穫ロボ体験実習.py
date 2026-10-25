"""
探究コーナー ─ 「ハウス収穫ロボ・シミュレーター」で安全安心な体験実習
配置先: pages/21_🍅_ハウス収穫ロボ体験実習.py （Streamlit のマルチページ構成）

問い
  ハウスの収穫ロボットを、中高生の職場体験・実習で扱うとき、危険を段階的に減らしながら
  「人の遠隔操作」と「AIの自動収穫」を比べ、自分の条件で AI の設定を決める体験を、どう組み立てるか。

6つの段（タブ）。骨格はリポジトリ共通の3段構え（① 計算する → ② 可視化する → ③ 自分の条件で判断する）
  0 安全の段階  1 体験する  2 ① 計算する  3 ② 可視化する  4 ③ 自分の条件で判断する  5 授業の進め方と実機への点検

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
        "注意点は三つ。第一に、モデルは**教育用の単純化**で、実機の性能ではない。"
        "第二に、実機の段階の人数・配置は**受け入れ先のリスクアセスメント**で決める。"
        "第三に、カメラ映像に**顔や名札を映さない・録画しない**。"
    )
    st.caption("いまは構想・準備の段階です。実機を使った体験実習の実施実績ではありません。")

with st.expander("このページの道のり：6つの段と、人・AI・Pythonの役割", expanded=False):
    st.markdown(
        "| 段 | すること | 担当 | 使う考え方 |\n|---|---|---|---|\n"
        "| 0 安全の段階 | 体験を4段に分け、危険を「重さ×起こりやすさ」で数える | 人が点を付け、Pythonが数える | リスクアセスメント（ISO 12100 の3ステップ） |\n"
        "| 1 体験する | シミュレーターで、人の遠隔操作とAIの自動収穫を1ラウンドずつ | 生徒 | 遠隔操作・画像認識 |\n"
        "| 2 ① 計算する | 遅れのあいだに進む距離、AIの検出と色の読み違いの式 | Pythonが計算する | モデル化・速度と間隔の監視 |\n"
        "| 3 ② 可視化する | 記録CSVを貼り、人とAIを比べる | Pythonが集計し、人が読む | ベイズ推論（ベータ分布） |\n"
        "| 4 ③ 判断する | 取り残しと誤収穫の損失から、しきい値 τ を決める | 人が決める | 期待損失の最小化 |\n"
        "| 5 授業と点検 | 45分・90分の流れ、実機に進む前の点検、ROS2の見張り役 | 人が判断する | チェックリスト・フィジカルAI（ROS2） |"
    )

T = st.tabs(["0 安全の段階", "1 体験する", "2 ① 計算する", "3 ② 可視化する",
             "4 ③ 自分の条件で判断する", "5 授業の進め方と実機への点検"])

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

with st.expander("出典・参考"):
    st.markdown(
        "- 遠隔収穫の出前授業：マイナビ農業「AGRIST、館山市から茨城県のキュウリを教室から収穫」、"
        "同「千葉県初開催！100名の小学生が収穫作業を体験」、リセマム「鹿児島市幼稚園でキュウリの遠隔収穫体験」\n"
        "- 長崎総合科学大学「トマト収穫ロボットの開発」プロジェクト報告（トマトロボット競技会）\n"
        "- ISO 12100（機械類の安全性：リスクアセスメントとリスク低減の3ステップ）\n"
        "- ISO/TS 15066（協働ロボット）・ISO 13855（人の接近速度）：このページの式は教育用に単純化したもの\n"
        "- 暑さ指数（WBGT）：環境省 熱中症予防情報サイト\n"
        "- SROS2：ROS 2 の通信を認証・暗号化する仕組み（ROS 2 公式ドキュメント）"
    )
st.caption("© スマートパン屋農家プロジェクト ｜ 記録の初期表示は教材用の架空データです。"
           "このページはロボットを動かさず、シミュレーターの記録もサーバーに送りません。")

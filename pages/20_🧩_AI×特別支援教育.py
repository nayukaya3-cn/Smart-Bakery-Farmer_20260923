"""
探究コーナー ─ AI活用による特別支援教育・訓練への可能性
配置先: pages/20_🧩_AI×特別支援教育.py （Streamlit のマルチページ構成）

問い
  特別支援学校 高等部の「産業現場等における実習」の受け入れ先として、パン工房と畑を開くとき、
  生成AI・フィジカルAI（ROS2のロボット）・ベイズ推論・因果推論・強化学習は、どこで役に立ち、どこで使ってはいけないか。

6つの段（タブ）。骨格はリポジトリ共通の3段構え（① 計算する → ② 可視化する → ③ 自分の条件で判断する）
  ① 制度の枠を数える  ② 工程を切り出す（人・ロボット・AI）  ③ 生成AIの使いどころ
  ④ 伸びを確かめる（ベイズ）  ⑤ 何が効いたか（因果）  ⑥ 受け入れの判断

計算は tokushi_lab.py（`python tokushi_lab.py` で自己チェック）。このページは外部の生成AIを呼び出さず、ロボットも動かさない。
初期表示はすべて架空（生徒は仮名）。障害の種類や診断名は扱わない。
福祉の現場（就労継続支援など）で生成AIを使う話は「🤝 福祉×生成AI」、このページは学校の実習が中心。
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import fukushi_ai as fa
import security_guard as sg
import tokushi_lab as tl

st.set_page_config(page_title="AI×特別支援教育", page_icon="🧩", layout="wide")

COLORS = {"ロボット・大人": "#b5523b", "大人と一緒": "#c98a2b", "生徒": "#6a9a4a"}

st.title("🧩 AI活用による特別支援教育・訓練への可能性")
st.caption("パン工房と畑を、特別支援学校の「産業現場等における実習」の場として開くとしたら。"
           "AIは何を計算し、何を見えるようにし、何を人に任せるべきか。 ── ① 計算する → ② 可視化する → ③ 自分の条件で判断する")

with st.container(border=True):
    st.markdown(
        "**研究メモ**：特別支援学校 高等部では、地域や産業界と連携して**産業現場等における長期間の実習**を取り入れ、"
        "就業体験の機会を積極的に設けることが学習指導要領で求められている。ただし**実習の回数・日数を決めた法令はなく**、"
        "各学校が教育課程の中で決める。いっぽう現場では、民間の受け入れ先が少ないことが課題になっている。"
        "問いは「**危険な工程をロボットと大人が引き受け、生徒が担う工程に生成AIの手順カードを付け、伸びをベイズで記録すると、"
        "受け入れ先を増やせるか**」である。"
        "注意点は四つある。第一に、AIの出す数は**話し合いの材料**で、決めるのは教員と本人。"
        "第二に、生成AIの文は**人が読んで確かめてから**使う。第三に、名前・写真・障害や健康の情報は**外部のAIに送らない**。"
        "第四に、ロボットの計算は**教育用の単純化**で、実際の配置はリスクアセスメントで決める。"
    )
    st.caption("いまは構想・準備の段階です。実習の受け入れ実績ではありません。")

with st.expander("このページの道のり：6つの段と、人・AI・Pythonの役割", expanded=False):
    st.markdown(
        "| 段 | すること | 担当 | 使う考え方 |\n|---|---|---|---|\n"
        "| ① 制度の枠を数える | 実習の日数が、年間の授業時数のどれだけを占めるかを計算する | 学校が決め、Pythonが数える | 法令の階層・割合 |\n"
        "| ② 工程を切り出す | パンの工程を危険で分け、人・ロボット・手順カードの分担を決める。ロボットとの距離を計算する | 人が決め、Pythonが分ける | モデル化・フィジカルAI（ROS2） |\n"
        "| ③ 生成AIの使いどころ | 生成モデルの種類ごとの使いどころ。手順カードを生成AIで下書きし、読みやすさと数を確かめる | AIが下書き → 人が確かめる | 生成モデル・情報の妥当性確認 |\n"
        "| ④ 伸びを確かめる | 工程ごとの「自分でできる確率」をベイズで更新し、支援を減らす候補を出す | 人が記録し、Pythonが更新する | ベイズ推論・バンディット（強化学習） |\n"
        "| ⑤ 何が効いたか | 手順カードの形（文字・写真・動画）の効果を、慣れの影響を除いて推定する | Pythonが調整し、人が解釈する | 因果推論（交絡・バックドア調整） |\n"
        "| ⑥ 受け入れの判断 | 受け入れ側の準備を点検し、足りないものを並べる | 人が判断する | チェックリスト・重みづけ |"
    )

T = st.tabs(["① 制度の枠を数える", "② 工程を切り出す", "③ 生成AIの使いどころ",
             "④ 伸びを確かめる", "⑤ 何が効いたか", "⑥ 受け入れの判断"])

# ═════════════════════ ① 制度の枠を数える ═════════════════════
with T[0]:
    st.subheader("問い：実習は何回・何日？ ── 法令は「回数」を決めていない")
    st.dataframe(tl.LAW_LAYERS, hide_index=True, width="stretch")
    st.info("回数・日数は**各学校の教育課程**で決まります。受け入れ側は、学校の計画に合わせる立場です。")

    st.markdown("#### ① 計算する：実習が年間の授業時数に占める割合")
    c1, c2 = st.columns([1, 2])
    with c1:
        ex = st.selectbox("運用の例から始める", list(tl.PRACTICE_EXAMPLES), key="tk_ex")
        hpd = st.slider("実習1日の時間（時間）", 3.0, 8.0, 6.0, 0.5, key="tk_hpd")
        plan = {}
        for g, (times, days) in tl.PRACTICE_EXAMPLES[ex].items():
            cc1, cc2 = st.columns(2)
            t_ = cc1.number_input(f"{g}：回数", 0, 4, times, key=f"tk_t_{ex}_{g}")
            d_ = cc2.number_input(f"{g}：1回の日数", 0, 20, days, key=f"tk_d_{ex}_{g}")
            plan[g] = (int(t_), int(d_))
    pl = tl.practicum_plan(plan, hpd)
    with c2:
        show = pl.copy()
        show["年間授業時数に占める割合"] = (show["年間授業時数に占める割合"] * 100).round(1).astype(str) + "%"
        st.dataframe(show, hide_index=True, width="stretch")
        st.caption(f"1単位時間＝{tl.UNIT_MIN}分、年間の総授業時数の標準＝{tl.ANNUAL_HOURS:,}単位時間（知的障害の特別支援学校 高等部）で換算。"
                   "実習をどの教科等の時数に位置づけるかは学校が決めます。")
        body = pl[pl["学年"] != "3年間の合計"]
        fig = px.bar(body, x="学年", y="年間授業時数に占める割合", text_auto=".1%",
                     color_discrete_sequence=["#6a9a4a"])
        fig.update_yaxes(tickformat=".0%", title=None)
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width="stretch")

    st.markdown("#### ③ 自分の条件で判断する：受け入れ側の上限")
    k1, k2, k3, k4 = st.columns(4)
    want = k1.number_input("学校が1回に送りたい人数", 1, 10, 3, key="tk_want")
    terms = k2.number_input("年間の受け入れ回数", 1, 6, 2, key="tk_terms")
    staff = k3.number_input("現場で見られる大人の数", 1, 5, 1, key="tk_staff")
    ratio = k4.number_input("大人1人が見られる生徒の数", 1, 4, 2, key="tk_ratio")
    cap = tl.host_capacity(int(want), int(terms), int(staff), int(ratio))
    m1, m2 = st.columns(2)
    m1.metric("1回に受け入れられる人数", f"{cap['1回に受け入れられる人数']}人")
    m2.metric("年間の延べ人数", f"{cap['年間の延べ人数']}人")
    if cap["人手が足りない"]:
        st.warning("学校の希望に人手が追いつきません。最初は1〜2名・短期間から始めるのが安全です。")

# ═════════════════════ ② 工程を切り出す ═════════════════════
with T[1]:
    st.subheader("問い：どの工程を、だれが（生徒・大人・ロボット）担うか")
    st.write("工程を「熱・刃物や挟まれ・重さ」の危険（0〜3）で表し、いちばん大きい危険で分担を決めます。"
             "手順や判断が多い工程には、生成AIで下書きした手順カード（③）を付けます。")
    c1, c2, c3 = st.columns(3)
    robot_max = c1.slider("この危険以上はロボット・大人", 2, 3, 3, key="tk_rmax")
    together = c2.slider("この危険以上は大人と一緒", 1, robot_max, 2, key="tk_tog")
    card_steps = c3.slider("手順がこの数以上ならカードを付ける", 2, 5, 4, key="tk_card")
    steps = st.data_editor(tl.STEPS, hide_index=True, width="stretch", key="tk_steps",
                           column_config={c: st.column_config.NumberColumn(min_value=0, max_value=3)
                                          for c in tl.HAZARD_COLS + ["衛生", "判断"]})
    al = tl.allocate(steps, robot_max, together, card_steps)
    st.dataframe(al[["工程", "危険", "分担", "手順カード", "時間_分"]], hide_index=True, width="stretch")

    summ = tl.allocation_summary(al)
    fig = px.bar(summ, x="時間_分", y="分担", orientation="h", color="分担", text="工程の数",
                 color_discrete_map=COLORS)
    fig.update_layout(height=220, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
    fig.update_traces(texttemplate="%{text}工程")
    st.plotly_chart(fig, width="stretch")
    st.caption("　".join(f"**{k}**：{v}" for k, v in tl.ROLES.items()))

    st.divider()
    st.markdown("#### ① 計算する：ロボットに、どこまで近づいたら止めるか")
    st.write("協働ロボットの「速度と間隔の監視」の考え方（ISO/TS 15066）を、教育用に単純化した式です。")
    st.latex(r"S = v_h\,(T_r+T_s) + v_r\,T_r + \tfrac{1}{2}v_r\,T_s + C")
    d1, d2, d3, d4 = st.columns(4)
    v_r = d1.slider("ロボットの速さ v_r（m/s）", 0.0, 1.5, 0.5, 0.1, key="tk_vr")
    t_r = d2.slider("気づくまでの時間 T_r（秒）", 0.05, 0.5, 0.1, 0.05, key="tk_tr")
    t_s = d3.slider("止まるまでの時間 T_s（秒）", 0.1, 1.0, 0.3, 0.05, key="tk_ts")
    c_m = d4.slider("余裕 C（m）", 0.0, 0.5, 0.2, 0.05, key="tk_c")
    dist = tl.protective_distance(v_r, t_r, t_s, margin=c_m)
    total = dist["合計（これより近づいたら止める）"]
    g1, g2 = st.columns([1, 2])
    with g1:
        st.metric("これより近づいたら止める距離", f"{total:.2f} m")
        st.dataframe(pd.DataFrame({"内わけ": list(dist)[:-1], "m": [round(v, 3) for v in list(dist.values())[:-1]]}),
                     hide_index=True, width="stretch")
        st.caption("v_h＝1.6 m/s は歩く人の速さの目安（ISO 13855）。生徒が急に動くことも考え、余裕は大きめに。")
    with g2:
        cur = tl.distance_curve(t_r, t_s, margin=c_m)
        fig = px.line(cur, x="ロボットの速さ_m/s", y="必要な距離_m", markers=True, color_discrete_sequence=["#b5523b"])
        fig.add_vline(x=v_r, line_dash="dot")
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width="stretch")
    st.warning("ロボットが止まっていても、人が近づく分だけで 0.6 m 以上が必要になります。"
               "**最初の受け入れでは、生徒の作業エリアとロボットのエリアを分ける**のが無難です。"
               "この計算は教材です。実際の配置は、ロボットの販売元・安全の専門家とリスクアセスメントで決めます。")
    with st.expander("ROS2 の例：工程が終わったら、次の手順カードを出す（表示するだけ）"):
        st.code(tl.ROS2_EXAMPLE, language="python")
        st.caption("カメラの判定（/vision/step_done）は「案」。人が近いという合図（/safety/human_near）を、案内より先に扱います。"
                   "安全を守る止め方（非常停止など）は、このノードではなく、ロボット本体の安全機能で行います。")

# ═════════════════════ ③ 生成AIの使いどころ ═════════════════════
with T[2]:
    st.subheader("問い：生成AIは、どの種類を、どこで使うか")
    st.write("『生成 Deep Learning 第2版』（David Foster 著、O'Reilly Japan、2024）の章立てを手がかりに、"
             "生成モデルの種類ごとに使いどころと注意を整理しました（使いどころ・注意はこのページの整理です）。")
    st.dataframe(tl.GEN_MODELS, hide_index=True, width="stretch")

    st.divider()
    st.markdown("#### 手順カードを生成AIで下書きする")
    c1, c2 = st.columns(2)
    with c1:
        kids = al[al["手順カード"].str.startswith("あり") & (al["分担"] == "生徒")]["工程"].tolist() or tl.STEPS["工程"].tolist()
        step = st.selectbox("工程（②で「生徒・カードあり」になったもの）", kids, key="tk_step")
        facts = st.text_area("現場で決まっていること（数・温度・時間）", tl.SAMPLE_FACTS, height=90, key="tk_facts")
        needs = st.multiselect("読み手に合わせてほしいこと", tl.CARD_NEEDS, default=tl.CARD_NEEDS[:3], key="tk_needs")
        n_steps = st.slider("手順の数", 3, 7, 5, key="tk_n")
        scan = fa.pii_scan(facts)
        if len(scan):
            st.error("貼る前に伏せてください（名前・番号・障害や健康の情報・文の中の指示）。")
            st.dataframe(scan, hide_index=True, width="stretch")
    with c2:
        st.code(tl.build_card_prompt(step, facts, needs, n_steps), language="text")
        st.caption("学校・事業所で決めた生成AIに貼ります。このページはAIを呼び出しません。名前・障害名を入れる欄はありません。")

    st.markdown("#### ③ 自分の条件で判断する：AIの下書きを確かめる")
    ex = st.radio("例", ["わかりにくい例", "わかりやすい例", "自分で貼る"], horizontal=True, key="tk_cardex")
    default = {"わかりにくい例": tl.SAMPLE_CARD_BAD, "わかりやすい例": tl.SAMPLE_CARD_GOOD, "自分で貼る": ""}[ex]
    card = st.text_area("生成AIが書いた手順カード", default, height=160, key=f"tk_card_{ex}")
    if card.strip():
        chk = tl.card_check(card, facts)
        r = chk["読みやすさ"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("1文の平均", f"{r['1文の平均(字)']}字")
        m2.metric("漢字の割合", f"{r['漢字の割合']:.0%}")
        m3.metric("番号つきの手順", r["番号つきの手順"])
        m4.metric("足された数", len(chk["足された数"]))
        if chk["足された数"]:
            st.error("元にない数があります：" + "・".join(chk["足された数"]) + " → 生成AIが数を書きかえた可能性。必ず直す。")
        if chk["落ちた数"]:
            st.warning("元の数が消えています：" + "・".join(chk["落ちた数"]))
        for f in chk["気になる点"]:
            st.write("・" + f)
        if not chk["気になる点"] and not chk["足された数"] and not chk["落ちた数"]:
            st.success("物差しの上では問題なし。最後に、生徒本人に読んでもらって確かめます。")
        st.caption("読みやすさの物差しは「🤝 福祉×生成AI」と共通です。境目は仮置き（1文20字・漢字30%）で、生徒に合わせて変えます。")

# ═════════════════════ ④ 伸びを確かめる ═════════════════════
with T[3]:
    st.subheader("問い：この工程の支援を、1段減らしてよいか")
    st.write(f"支援は多い順に **{' → '.join(tl.SUPPORT)}**。"
             "工程ごとに「自分でできた／できなかった」を記録し、ベータ分布で「自分でできる確率」を更新します。")
    up = st.file_uploader("記録CSV（列：実習日, 工程, 支援, 成功）。なければ架空の記録を使います", type="csv", key="tk_up")
    trials = None
    if up is not None:
        rec = sg.read_csv_safely(up, page="tokushi", kind="trials")
        if rec is not None and {"実習日", "工程", "支援", "成功"} <= set(rec.columns) and rec["支援"].isin(tl.SUPPORT).all():
            trials = rec
        elif rec is not None:
            st.error(f"列名か支援の名前が合いません（支援は {', '.join(tl.SUPPORT)} のどれか）。")
    if trials is None:
        trials = tl.sample_trials()
        st.caption("架空の記録：教員が「直近2日で4分の3以上できたら1段減らす」という決まりで支援を変えた想定です。")

    th = st.slider("「自分でできる」とみなす成功率", 0.6, 0.95, 0.8, 0.05, key="tk_th")
    pt = tl.posterior_table(trials, th)
    show = pt.drop(columns=["a", "b"]).copy()
    show["平均"] = show["平均"].round(2)
    show[f"P(できる確率>{th:.0%})"] = show[f"P(できる確率>{th:.0%})"].round(2)
    st.dataframe(show, hide_index=True, width="stretch")

    # ② 可視化する：事後分布
    x = np.linspace(0, 1, 301)
    fig = go.Figure()
    for _, row in pt.iterrows():
        fig.add_scatter(x=x, y=tl.beta_pdf(row["a"], row["b"], x), name=f"{row['工程']}（{row['いまの支援']}）", mode="lines")
    fig.add_vline(x=th, line_dash="dot", annotation_text="目標")
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="自分でできる確率",
                      yaxis_title="確からしさ", legend=dict(orientation="h", y=-0.3))
    st.plotly_chart(fig, width="stretch")
    st.caption("山が右にあるほど「できる」、山が細いほど「記録が多く確か」。回数が少ないうちは山が太く、決めつけられません。")

    st.markdown("#### 次はどの支援から始めるか（トンプソン抽出）")
    step4 = st.selectbox("工程", pt["工程"].tolist(), key="tk_step4")
    ts = tl.thompson_suggest(trials, step4, th)
    fig = px.bar(ts, x="支援", y="次に選ばれる割合", text_auto=".0%", color_discrete_sequence=["#3f7cac"],
                 hover_data=["記録の数"])
    fig.update_yaxes(tickformat=".0%", title=None)
    fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch")
    st.info("強化学習（多腕バンディット）の考え方で、各支援レベルの成功率を分布から引き、「目標を超える中でいちばん支援が少ないもの」を選ぶ割合です。"
            "記録の少ないレベルにも割合が残るのは「まだ分からないから試す価値がある」という意味です。"
            "**これは提案です。** 生徒の様子・気持ち・その日の体調を知っているのは教員と本人で、個別の指導計画を書きかえるのは人です。")

# ═════════════════════ ⑤ 何が効いたか ═════════════════════
with T[4]:
    st.subheader("問い：動画の手順カードは、本当に効いたのか")
    st.write("後半の実習日ほど動画のカードを使い、しかも後半ほど慣れてできるようになっていた ── この記録をそのまま比べると、"
             "**慣れの効果まで動画の手柄に見えます**（交絡）。慣れの段階ごとに比べてから平均すると、取りのぞけます。")
    c1, c2 = st.columns([1, 1])
    with c1:
        st.graphviz_chart(tl.DAG_DOT)
    with c2:
        days = st.slider("記録の日数", 6, 60, 12, 3, key="tk_days")
        per = st.slider("1日の試行の数", 4, 40, 8, 4, key="tk_per")
        seed = st.number_input("乱数のたね", 0, 999, 11, key="tk_seed")
    fm = tl.sample_formats(int(seed), days, per)
    eff = pd.DataFrame({"そのまま比べる": tl.naive_effect(fm), "慣れで調整": tl.adjusted_effect(fm),
                        "本当の効果（架空の答え）": pd.Series(tl.TRUE_EFFECT)}).reset_index(names="手順カード")
    long = eff[eff["手順カード"] != "文字"].melt(id_vars="手順カード", var_name="比べ方", value_name="文字との差")
    fig = px.bar(long, x="手順カード", y="文字との差", color="比べ方", barmode="group", text_auto=".2f",
                 color_discrete_sequence=["#b77a86", "#3f7cac", "#999999"])
    fig.update_yaxes(tickformat="+.0%", title="できた割合の差（文字のカードと比べて）")
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="")
    st.plotly_chart(fig, width="stretch")
    st.caption("記録が少ないと、調整しても値は大きくぶれます（日数・試行を増やして確かめてください）。"
               "実際の授業では、日ごとに形を入れかえる（ABAB）と交絡を避けやすくなります → 「🤝 福祉×生成AI」⑥。")
    with st.expander("計算のしかた（バックドア調整）"):
        st.latex(r"\text{効果}(f)=\sum_{k\in\{\text{前半},\text{中盤},\text{後半}\}} P(k)\,\big(\bar y_{f,k}-\bar y_{\text{文字},k}\big)")
        st.write("Python なら DoWhy や PyMC でも同じ考え方を使えます。まずは手で計算し、何をしているかを確かめます。")

# ═════════════════════ ⑥ 受け入れの判断 ═════════════════════
with T[5]:
    st.subheader("問い：この工房は、実習生を受け入れてよいか")
    st.write("必須の項目が1つでも欠けたら「まだ受け入れない」。そろったら、1〜2名・短期間から試します。")
    done = []
    for i, (item, w, must, where) in enumerate(tl.HOST_CHECKS):
        done.append(st.checkbox(f"{'【必須】' if must else ''}{item}", key=f"tk_chk{i}", help=f"確かめる先：{where}"))
    res = tl.host_readiness(done)
    m1, m2 = st.columns([1, 2])
    m1.metric("準備度（重みつき）", f"{res['準備度']:.0%}")
    (m2.success if res["判定"].startswith("受け入れの相談") else m2.warning if res["判定"].startswith("1〜2名") else m2.error)(res["判定"])
    if len(res["やること"]):
        st.markdown("**まだのこと**")
        st.dataframe(res["やること"], hide_index=True, width="stretch")
        st.download_button("まだのことを保存（CSV）", sg.safe_csv(res["やること"]), "受け入れ準備_やること.csv", "text/csv")
    with st.expander("確かめておくこと（制度・ルール）"):
        st.markdown(
            "- **生成AI**：文部科学省「初等中等教育段階における生成AIの利活用に関するガイドライン（Ver.2.0）」（2024年12月26日）と、"
            "学校・教育委員会の方針。生徒が直接使うのか、大人の支援ツールにとどめるのかで、手続きの重さが変わる\n"
            "- **利用規約の年齢**：多くの生成AIサービスに18歳未満の利用条件がある\n"
            "- **個人情報**：障害や健康の情報は要配慮個人情報。外部のAIに送らない（このページと「🤝 福祉×生成AI」⑤の点検）\n"
            "- **合理的配慮**：改正障害者差別解消法により、2024年4月から民間事業者にも提供が義務になっている\n"
            "- **ロボット**：産業用ロボット特別教育（労働安全衛生法）は教示・点検をする労働者のためのもの。"
            "生徒向けには「ロボットのいる職場で安全に働く」準備教育として行い、「特別教育」とは名乗らない\n"
            "- 制度は変わります。最新の情報は学校・教育委員会・各窓口で確かめてください。"
        )

with st.expander("出典・参考"):
    st.markdown(
        "- 特別支援学校高等部学習指導要領（総則）・国立特別支援教育総合研究所の研究報告（職業教育の充実、産業現場等における長期間の実習）\n"
        "- 授業時数の標準：例として山梨県の規則（高等部は年35週・週30単位時間、知的障害の特別支援学校は各学年1,050単位時間）\n"
        "- 実習の運用例：静岡県立藤枝特別支援学校焼津分校の受け入れ案内（3年間で6回・1回5〜14日程度）、"
        "大分大学教育学部附属特別支援学校の進路だより（学年ごとのねらい・10日間）\n"
        "- 受け入れ先の課題：長野県「地域と連携したキャリア教育の充実」（実習先の開拓、就労コーディネーター）\n"
        "- 文部科学省「初等中等教育段階における生成AIの利活用に関するガイドライン（Ver.2.0）」（2024年12月26日）\n"
        "- David Foster『生成 Deep Learning 第2版 ― 絵を描き、物語や音楽を作り、ゲームをプレイする』O'Reilly Japan（2024）\n"
        "- ISO/TS 15066（協働ロボット）・ISO 13855（人の接近速度）：このページの式は教育用に単純化したもの\n"
        "- 支援を減らす考え方：最大から最小への援助（プロンプト・フェーディング）"
    )
st.caption("© スマートパン屋農家プロジェクト ｜ 初期表示は教材用の架空データ（生徒は仮名）です。"
           "このページは外部の生成AIを呼び出さず、ロボットも動かしません。")

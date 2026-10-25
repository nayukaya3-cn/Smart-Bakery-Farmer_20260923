"""
探究コーナー ─ AI時代に残る仕事を、就活と起業で獲得する
配置先: pages/22_🧭_AI時代に残る仕事.py （Streamlit のマルチページ構成）

問い
  置き換わりにくく、AIと組むとむしろ強くなる仕事・事業はどれか。そこに就く・始めるハードル
  （資格・インターン・特別教育・実務経験）は何で、どんな条件がそろえば突破できるか。

ピボット：東京都立蔵前工科高校（ロボットインストラクターの資格をもつ教員が、授業・実習の中で教示等の特別教育を行い、
卒業時に修了証を出す）。「学校の準備教育 → 特別教育 → 実務 → 教える側」という資格の鎖の実例。

5つの段（タブ）。骨格はリポジトリ共通の3段構え
  0 ピボット  1 ① 置き換わりにくさを計算する  2 ② 資格の地図を可視化する  3 ③ 就活と起業を判断する  4 研究・実証への組み込み

計算は career_lab.py（`python career_lab.py` で自己チェック）。重み・料金の初期値は教育用の仮置き。
"""
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import career_lab as cl
import security_guard as sg

st.set_page_config(page_title="AI時代に残る仕事", page_icon="🧭", layout="wide")
STATE_COLORS = {"済": "#2b8a3e", "いま挑戦できる": "#2f6db0", "前提が足りない": "#b0aaa0"}


def link_page(num: str, label: str, icon: str) -> None:
    """番号でページを探してリンクする。見つからない環境（単体起動など）では文字だけ出す。"""
    hits = sorted((Path(__file__).parent).glob(f"{num}_*.py"))
    try:
        st.page_link(f"pages/{hits[0].name}", label=label, icon=icon)
    except Exception:  # noqa: BLE001
        st.caption(f"{icon} {label}（左のメニューから開けます）")

st.title("🧭 AI時代に残る仕事を、就活と起業で獲得する")
st.caption("置き換わりにくさを数え、資格の鎖を地図にし、自分の条件で一歩を決める。"
           " ── ① 計算する → ② 可視化する → ③ 自分の条件で判断する")

with st.container(border=True):
    st.markdown(
        "**研究メモ**：「AIで無くならない仕事」と言い切れる研究はない。ILO（2025）は、世界の労働者の約4人に1人が"
        "生成AIに何らかの形でさらされるが、多くの仕事は**置き換えより変容**が起こりやすいとした。"
        "そこでこのページでは、問いを「**置き換わりにくく、AIと組むと強くなる仕事に、どう就き、どう始めるか**」に言いかえる。"
        "注意点は三つ。第一に、①の重みは**教育用の仮置き**で、職業の将来の予測ではない。"
        "第二に、資格の要件・日程は変わるので、**主催者・行政で確かめる**。"
        "第三に、年齢・収入・健康などは入力させない。決めるのは本人。"
    )

with st.expander("このページの道のり：5つの段と、人・AI・Pythonの役割", expanded=False):
    st.markdown(
        "| 段 | すること | 担当 | 使う考え方 |\n|---|---|---|---|\n"
        "| 0 ピボット | 蔵前工科高校の例から「資格の鎖」を読む | 人が読む | 事例研究 |\n"
        "| 1 ① 計算する | 仕事を5種類のタスクに分け、置き換わりやすさと組める余地を出す | Pythonが計算し、人が割合を決める | タスク・アプローチ（Autor ほか 2003） |\n"
        "| 2 ② 可視化する | 資格・経験の前提関係を地図にし、次の一歩と目標までの月数を出す | Pythonが並べ、人が選ぶ | 有向グラフ・最長経路 |\n"
        "| 3 ③ 判断する | 応募の通過率から必要な応募数を出す／出張講習の損益分岐を出す | 人が決める | ベイズ推論（ベータ二項）・損益分岐 |\n"
        "| 4 研究・実証 | ハードルと突破の条件を一覧にし、研究の指標に組み込む | 人が設計する | 縦断研究・因果推論 |"
    )

T = st.tabs(["0 ピボット", "1 ① 置き換わりにくさ", "2 ② 資格の地図", "3 ③ 就活と起業", "4 研究・実証への組み込み"])

# ═════════════════════ 0 ピボット ═════════════════════
with T[0]:
    st.subheader("出発点：学校の中で「資格の鎖」をつないだ例")
    st.markdown(
        "東京都立蔵前工科高校では、**ロボットインストラクターの資格をもつ教員**が、ロボティクスコースの授業と実習の中で"
        "産業用ロボットの**教示等の特別教育**（安衛則 第36条第31号）を行い、必要な単位と成績を満たした生徒に、"
        "卒業時に修了証を出しています。実技は「産業用ロボットの操作の方法 1時間以上」と「教示等の作業の方法 2時間以上」です。"
    )
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**この例から読めること**")
        st.markdown(
            "- 特別教育そのものの受講要件は低い。**価値が出るのは、それを教えられる人**のほう\n"
            "- 教える人には「インストラクターの修了」＋「教員としての立場」＋「現場の経験」が重なっている\n"
            "- 生徒は卒業時点で、就職先がもう一度行う手間を減らせる証明（修了証と台帳）を持って出られる"
        )
    with c2:
        st.markdown("**ここから、自分の道に引き直す**")
        st.markdown(
            "| 段 | 場所 | このリポジトリのページ |\n|---|---|---|\n"
            "| 準備教育 | 学校・体験実習 | 🍅 ハウス収穫ロボ体験実習（段0〜段3） |\n"
            "| 特別教育 | 就職先・資格をもつ人 | 🍅 の「6 ロボットを扱う大人の条件」 |\n"
            "| 実務 | 職場・訓練施設・自分の工房 | 作業日誌（記録の残る経験） |\n"
            "| 教える側 | 学校・訓練校・出張講習 | このページの ② と ③ |"
        )
    link_page("21", "ハウス収穫ロボ体験実習（準備教育と大人の条件）を開く", "🍅")
    st.caption("特別支援学校で同じような例は、調べた範囲では確認できていません。")

# ═════════════════════ 1 ① 置き換わりにくさ ═════════════════════
with T[1]:
    st.subheader("① 計算する：その仕事は、置き換わるのか、AIと組むのか")
    st.write("仕事を「1週間の時間をどのタスクに使うか」で表し、タスクごとの重みをかけて合計します。"
             "法令や資格で人が担うと決まっている部分は、置き換わりやすさを半分にします（仮置き）。")
    st.latex(r"\text{置き換わりやすさ}=\Bigl(\sum_k s_k\,w^{\mathrm{auto}}_k\Bigr)\,(1-0.5\,r)\qquad"
             r"\text{組める余地}=\sum_k s_k\,w^{\mathrm{aug}}_k")
    st.dataframe(cl.TASK_TYPES, hide_index=True, width="stretch")

    c1, c2 = st.columns([1, 2])
    with c1:
        job = st.selectbox("例から始める", list(cl.JOBS), index=3, key="cr_job")
        base = cl.JOBS[job]
        shares = [st.slider(t, 0.0, 1.0, float(v), 0.05, key=f"cr_s_{job}_{i}")
                  for i, (t, v) in enumerate(zip(cl.TASK_NAMES, base["割合"]))]
        lic = st.slider("法令・資格で人が担う割合 r", 0.0, 1.0, float(base["制度"]), 0.05, key=f"cr_r_{job}")
    with c2:
        try:
            prof = cl.job_profile(shares, lic)
        except ValueError as e:
            st.error(str(e))
            prof = None
        if prof:
            m1, m2, m3 = st.columns(3)
            m1.metric("置き換わりやすさ", f"{prof['置き換わりやすさ']:.2f}",
                      f"制度なしなら {prof['制度なしなら']:.2f}", delta_color="off")
            m2.metric("組める余地", f"{prof['組める余地']:.2f}")
            m3.markdown(f"**型**<br>{prof['型']}", unsafe_allow_html=True)
        jt = cl.jobs_table()
        fig = px.scatter(jt, x="置き換わりやすさ", y="組める余地", text="仕事", color="型",
                         color_discrete_sequence=["#b5523b", "#2f6db0", "#2b8a3e"])
        if prof:
            fig.add_scatter(x=[prof["置き換わりやすさ"]], y=[prof["組める余地"]], mode="markers",
                            marker=dict(size=16, symbol="star", color="#e9b44c"), name="いま調整中")
        fig.update_traces(textposition="top center", selector=dict(mode="markers+text"))
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), legend_title=None)
        st.plotly_chart(fig, width="stretch")
        st.caption("左上ほど「置き換わりにくく、AIと組むと強くなる」。重みは仮置きなので、点の位置より**動き方**を見てください。")
    st.info("同じ仕事でも、**定型の事務を減らし、対人と現場の手作業の割合を増やす**と左上へ動きます。"
            "「どの仕事に就くか」と同じくらい、「仕事の中で何に時間を使うか」が効きます。")

# ═════════════════════ 2 ② 資格の地図 ═════════════════════
with T[2]:
    st.subheader("② 可視化する：資格と経験の鎖 ── いま持っているものから、次の一歩")
    held = st.multiselect("いま持っているもの・済んだもの", list(cl.CREDENTIALS), key="cr_held",
                          default=["準備教育（学校の授業・体験実習）"])
    stt = cl.credential_status(held)

    # 段ごとに並べた前提のグラフ
    pos = {}
    for lv, grp in stt.groupby("段"):
        for i, name in enumerate(grp["項目"]):
            pos[name] = (lv, -(i - (len(grp) - 1) / 2))
    fig = go.Figure()
    for name, (_, _, pre, _, _) in cl.CREDENTIALS.items():
        for p in pre:
            fig.add_annotation(x=pos[name][0], y=pos[name][1], ax=pos[p][0], ay=pos[p][1],
                               xref="x", yref="y", axref="x", ayref="y", showarrow=True,
                               arrowhead=2, arrowwidth=1.2, arrowcolor="#8a8378", standoff=10, startstandoff=10)
    for state, grp in stt.groupby("状態"):
        fig.add_scatter(x=[pos[n][0] for n in grp["項目"]], y=[pos[n][1] for n in grp["項目"]],
                        mode="markers+text", text=grp["項目"], textposition="bottom center", name=state,
                        marker=dict(size=18, color=STATE_COLORS[state]), textfont=dict(size=10),
                        hovertext=grp["メモ"], hoverinfo="text")
    fig.update_xaxes(tickvals=[0, 1, 2, 3], ticktext=["学ぶ・免許", "特別教育・体験", "実務・講習", "仕事・事業"],
                     range=[-0.5, 3.6])
    fig.update_yaxes(visible=False)
    fig.update_layout(height=470, margin=dict(l=10, r=10, t=10, b=10), legend_title=None)
    st.plotly_chart(fig, width="stretch")

    nxt = stt[stt["状態"] == "いま挑戦できる"]
    st.markdown("**いま挑戦できる一歩**")
    st.dataframe(nxt[["項目", "種類", "目安_月", "メモ"]], hide_index=True, width="stretch")

    st.markdown("#### 目標までの目安")
    goals = [n for n, v in cl.CREDENTIALS.items() if v[1] in ("仕事", "事業")]
    goal = st.selectbox("目標", goals, key="cr_goal")
    months, path = cl.months_to_reach(goal, held)
    st.metric("いちばん長い道筋の目安", f"{months} か月")
    st.write(" → ".join(path) if path else "もう済んでいます。")
    st.caption("前提を並行して進められるとした目安です。月数は仮置きなので、表の「目安_月」を自分の調べた値で考えてください。"
               "特別教育の講師には免許のような法定資格はないため、インストラクターの修了と実務の記録が「信用の証明」になります。")

# ═════════════════════ 3 ③ 就活と起業 ═════════════════════
with T[3]:
    st.subheader("③ 自分の条件で判断する：就活と起業、それぞれの突破条件")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 就活：あと何件応募すれば、面接に届くか（ベイズ）")
        a1, a2, a3 = st.columns(3)
        applied = a1.number_input("これまでの応募", 0, 200, 10, key="cr_app")
        passed = a2.number_input("書類が通った数", 0, 200, 2, key="cr_pass")
        target = a3.number_input("ほしい面接の数", 1, 20, 3, key="cr_tgt")
        conf = st.slider("見込みの確かさ", 0.5, 0.95, 0.8, 0.05, key="cr_conf")
        if passed > applied:
            st.error("書類が通った数は、応募の数以下にしてください。")
        else:
            a, b = cl.pass_rate_posterior(int(passed), int(applied))
            need = cl.applications_needed(int(passed), int(applied), int(target), conf)
            st.metric("通過率の見込み（事後平均）", f"{a / (a + b):.0%}")
            st.metric(f"面接 {target} 件に {conf:.0%} の確かさで届く追加の応募数",
                      f"{need} 件" if need else "200件でも届かない")
            st.caption("通過率を一様な事前分布 Beta(1,1) から更新し、ベータ二項で数えています。"
                       "必要な応募数が多すぎるときは、応募先を増やすより**通過率を上げる証拠**（修了証・作品・記録）を先にそろえます。")
    with c2:
        st.markdown("#### 起業：出張講習は、月に何回で黒字になるか")
        b1, b2 = st.columns(2)
        price = b1.number_input("1人あたりの受講料（円・仮置き）", 0, 100000, 15000, 1000, key="cr_price")
        ppl = b2.number_input("1回の受講者数", 1, 30, 4, key="cr_ppl")
        var = b1.number_input("1回の費用（交通費・教材など）", 0, 200000, 15000, 1000, key="cr_var")
        fixed = b2.number_input("月の固定費（保険・機材・通信など）", 0, 500000, 40000, 5000, key="cr_fix")
        sess = st.slider("月の回数", 0, 12, 2, key="cr_sess")
        pr = cl.session_profit(price, int(ppl), sess, var, fixed)
        m1, m2 = st.columns(2)
        m1.metric("月の損益", f"{pr['月の損益']:,.0f} 円")
        m2.metric("損益分岐の回数", f"{pr['損益分岐の回数']} 回／月" if pr["損益分岐の回数"] else "1回の粗利が赤字")
        xs = list(range(0, 13))
        ys = [cl.session_profit(price, int(ppl), s, var, fixed)["月の損益"] for s in xs]
        fig = px.bar(x=xs, y=ys, labels={"x": "月の回数", "y": "月の損益（円）"},
                     color=[("黒字" if y >= 0 else "赤字") for y in ys],
                     color_discrete_map={"黒字": "#2b8a3e", "赤字": "#b5523b"})
        fig.update_layout(height=250, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
        st.plotly_chart(fig, width="stretch")
        st.caption("料金・費用はすべて仮置き。相場は自分で調べて入れてください。実機を持ち込めないときの教材（シミュレーター）も費用に入れます。")
    with st.container(border=True):
        st.markdown("**ワークシート：自分の一言**")
        st.text_input("私が最初に突破するハードルは……　なぜなら……", key="cr_w1",
                      placeholder="例：実務経験。修了証だけでは「できる」の証明にならないので、訓練施設で記録を残す")
        st.text_input("就活と起業、どちらを先にするか。その条件は……", key="cr_w2",
                      placeholder="例：損益分岐の回数を満たせる顧客の当てが2件できるまでは、非常勤で働きながら準備する")
        st.caption("書いた内容はこのブラウザの中だけにあり、保存も送信もされません。")

# ═════════════════════ 4 研究・実証への組み込み ═════════════════════
with T[4]:
    st.subheader("ハードルと、突破できる条件の一覧")
    st.dataframe(cl.HURDLES, hide_index=True, width="stretch")
    st.download_button("一覧を保存（CSV）", sg.safe_csv(cl.HURDLES), "ハードルと突破の条件.csv", "text/csv")

    st.divider()
    st.markdown("#### 研究・実証の中で確かめること")
    st.markdown(
        "| 確かめたいこと | 測るもの | 方法 |\n|---|---|---|\n"
        "| 準備教育は、特別教育の学びを速くするか | 体験実習の有無で、特別教育の実技の到達（観察チェック）を比べる | 準実験・共変量の調整（因果推論） |\n"
        "| 修了証に「記録」を添えると、通過率は上がるか | 応募ごとの書類通過（③と同じ形で記録） | ベイズ更新・2群の事後分布の比較 |\n"
        "| 学んだことは現場で使われるか | 修了後の実務での使用（作業日誌のログ） | 縦断の記録・学習転移率 |\n"
        "| 受け入れ先は増えるか | 体験実習の受け入れ先の数・準備度（🍅 の点検） | 年ごとの縦断 |"
    )
    st.caption("人を対象にする測定は、研究倫理の審査と、本人・保護者・学校の同意を先に済ませます。"
               "個人が特定できる記録は外部のAIに送りません。")

with st.expander("出典・参考"):
    st.markdown(
        "- 東京都立蔵前工科高校「ロボット安全特別教育修了証発行について」\n"
        "- 労働安全衛生規則 第36条第31号・第32号、安全衛生特別教育規程 第18条・第19条\n"
        "- ILO Working Paper 140「Generative AI and Jobs: A Refined Global Index of Occupational Exposure」（2025）\n"
        "- Autor, D. H., Levy, F., & Murnane, R. J. (2003). The skill content of recent technological change. "
        "Quarterly Journal of Economics, 118(4).\n"
        "- Frey, C. B., & Osborne, M. A. (2017). The future of employment. Technological Forecasting and Social Change, 114.\n"
        "- 重み・月数・料金の初期値は教育用の仮置き"
    )
st.caption("© スマートパン屋農家プロジェクト ｜ このページは入力を保存・送信しません。数は話し合いの材料で、決めるのは本人です。")

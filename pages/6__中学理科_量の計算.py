"""
中学理科「量の計算」─ パン工房と畑で、数式と割合を使う
配置先: pages/6_🧪_中学理科_量の計算.py （Streamlit のマルチページ構成）

小学校の理科は「観察して言葉で説明する」問題が中心。中学では
  オームの法則（中2）・質量パーセント濃度（中1）・化学変化と質量（中2）
のように、数式と割合で現象を扱う単元が一気に増える。ここでつまずくと
「自分は理科（数式）ができない」という自己像ができ、高1の文理選択で理系を選ばなくなる。

骨格はリポジトリ共通の3段構え：
  ① 現象を計算する → ② 数値を可視化する → ③ 自分の条件で判断する
に、横軸として「得意だと思えるか・使う仕事が想像できるか」（自己効力感と将来像）を足す。

方針
  - 計算は chugaku_rika.py（`python chugaku_rika.py` で自己チェック）。
  - 初期表示の数値は一般的な目安と架空データ（実測ではありません）。
  - 入力はセッション内だけで使い、サーバーには残さない。生徒の氏名は扱わない。
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import chugaku_rika as cr
import security_guard as sg

st.set_page_config(page_title="中学理科 量の計算", page_icon="🧪", layout="wide")

import social as sn  # noqa: E402  SNSのURLは social.py で一括管理

UPDATED = "2026-10-14"
TIMSS_URL = "https://www.nippon.com/ja/japan-data/h02233/"
MEXT_TIMSS_URL = "https://www.mext.go.jp/content/20241223-mxt_chousa02-000039290-9.pdf"
HULLEMAN_URL = "https://sparq.stanford.edu/sites/g/files/sbiybj19021/files/media/file/hulleman_harackiewicz_2009_-_promoting_interest_performance_in_high_school_science_classes.pdf"
PARENT_URL = "https://journals.sagepub.com/doi/10.1177/0956797611435530"
UNITS = ["⚡ オームの法則", "🧂 質量パーセント濃度", "🔥 化学変化と質量"]
OK, NG = "#2e7d5b", "#c0392b"


def check_box(key: str, question: str, diagnose, *args, unit: str = "", step: float = 0.1) -> None:
    """つまずきチェック：答えを入れると、間違い方に合わせて言葉で返す。"""
    with st.container(border=True):
        st.markdown(f"**✏️ つまずきチェック**　{question}")
        ans = st.number_input(f"答え（{unit}）", value=None, step=step, key=key, format="%.3f")
        if ans is not None:
            ok, msg = diagnose(ans, *args)
            (st.success if ok else st.warning)(msg)


def deciders(unit: str) -> None:
    """単元の冒頭：この計算で「何を決めている人」がいるか（原則①）。"""
    ms = [m for m in cr.MISSIONS if m["単元"] == unit]
    lines = "\n".join(f"- **{m['仕事']}**：{m['決めること']}" for m in ms)
    st.info(f"👷 **この計算で決めている人**\n{lines}\n\n"
            "→ 「🌱 横軸：使う仕事が想像できる」タブの仕事ミッションで、その人になって計算できます。")


with st.sidebar:
    st.header("🧪 中学理科 量の計算")
    st.caption("3つの単元は、どれも「比べる量 = もとにする量 × 割合」。")
    st.caption("入力はページを閉じると消えます。残したい記録はCSVで保存してください。")
    st.divider()
    sn.buttons("で相談する", stacked=True)

st.title("🧪 中学理科「量の計算」── パン工房と畑で使う")
st.caption("① 現象を計算する → ② 数値を可視化する → ③ 自分の条件で判断する　＋　横軸：使う仕事が想像できるか")

tab_flow, tab_a, tab_b, tab_c, tab_x = st.tabs([
    "🧭 なぜ中学でつまずくか", *UNITS, "🌱 横軸：使う仕事が想像できる",
])

# ═════════════════════════════════════════════
# 0. 流れ
# ═════════════════════════════════════════════
with tab_flow:
    st.header("🧭 小学校の「言葉で説明」から、中学の「数式と割合」へ")
    st.write("中学理科では、量を計算する単元が一気に増えます。とある中学校が課題に挙げているのも、"
             "この「量の計算」の単元です。ここでつまずくと「自分は理科（数式）ができない」という自己像ができ、"
             "高1の文理選択で理系を選ばなくなる、という流れが起こりえます。")

    st.subheader("3つの単元は、同じ形をしている")
    st.dataframe(cr.SAME_FORM, width="stretch", hide_index=True)
    st.info("**つまずきの多くは理科ではなく「何を もと（100%・1）にするか」の取り違え**です。"
            "濃度の分母を水だけにする、電力と電圧をかけてしまう、残った質量と出ていった気体を取り違える──"
            "各タブの「つまずきチェック」は、この間違い方を見分けて言葉で返します。")
    st.info("**もう一つの段差は「何に使うのか分からない」こと。** 国際調査では、日本の中2で"
            "「理科を使う職業につきたい」は27%（国際平均58%）。そこで各単元は「誰が・何を決めるために」"
            "計算するかから始め、横軸タブで仕事の人になって数値を決める体験をします。")

    st.subheader("1単元あたりの流れ（50分の例）")
    st.dataframe(pd.DataFrame([
        ("0–10分", "パン工房・畑の場面から問いを立てる", "例：オーブンと発酵器を同じタップにつないでいい？"),
        ("10–25分", "① 現象を計算する", "式に入れる前に「もとにする量」を指でさす"),
        ("25–35分", "② 数値を可視化する", "グラフの傾きが「割合 a」だと確かめる"),
        ("35–45分", "③ 自分の条件で判断する", "自分の家・畑の数値を入れて決める。答えは人によって違う"),
        ("45–50分", "横軸：使う仕事", "仕事ミッションを1つ解き、「自分の言葉でつなぐ」を書く。前後の自己評価を記録"),
    ], columns=["時間", "段", "ポイント"]), width="stretch", hide_index=True)
    st.caption("※ 計算は教育用に単純化しています。電気機器は本体の表示、肥料は製品の説明書、"
               "食品は衛生上の基準に必ず従ってください。")

# ═════════════════════════════════════════════
# A. オームの法則・電力
# ═════════════════════════════════════════════
with tab_a:
    st.header("⚡ オーブンと発酵器、同じタップにつないでいい？")
    deciders("オームの法則・電力")
    st.write(f"家のコンセントは **{cr.VOLTAGE:.0f} V**。1つのタップにつないだ機器は **並列** なので、"
             f"電流は **足し算** になります。テーブルタップの定格は一般に **{cr.TAP_LIMIT_A:.0f} A** です。")

    st.subheader("① 現象を計算する")
    c1, c2, c3 = st.columns(3)
    p_w = c1.number_input("機器の消費電力 P [W]", 10, 3000, 1200, 10)
    i_a = cr.current_a(p_w)
    c2.metric("電流 I = P ÷ V", f"{i_a:.1f} A")
    c3.metric("抵抗 R = V ÷ I（電熱線とみなす）", f"{cr.resistance_ohm(p_w):.1f} Ω")
    check_box("chk_ohm", "消費電力 1300 W のオーブンに流れる電流は何 A？", cr.diagnose_ohm, 1300.0, unit="A")

    st.subheader("② 数値を可視化する")
    st.caption("電圧を変えたときの電流（I–V グラフ）。直線の傾きが 1/R。消費電力の大きい機器ほど抵抗が小さく、傾きが急になる。")
    df_app = st.data_editor(cr.sample_appliances(), key="app_ed", num_rows="dynamic", width="stretch",
                            column_config={"使う": st.column_config.CheckboxColumn("同じタップで同時に使う")})
    df_app = df_app.dropna(subset=["機器", "消費電力_W"])
    df_app = df_app[df_app["消費電力_W"] > 0]
    fig = go.Figure()
    for _, row in df_app.iterrows():
        r_ohm = cr.resistance_ohm(float(row["消費電力_W"]))
        fig.add_trace(go.Scatter(x=[0, 100], y=[0, 100 / r_ohm], mode="lines",
                                 name=f"{row['機器']}（{r_ohm:.0f} Ω）"))
    fig.update_layout(height=340, margin=dict(t=10, b=10),
                      xaxis_title="電圧 V [V]", yaxis_title="電流 I [A]")
    st.plotly_chart(fig, width="stretch")

    st.subheader("③ 自分の条件で判断する")
    load = cr.tap_load(df_app)
    tbl = load["table"]
    fig2 = go.Figure()
    for _, row in tbl.iterrows():
        fig2.add_trace(go.Bar(y=["合計電流"], x=[row["電流_A"]], orientation="h",
                              name=f"{row['機器']} {row['電流_A']:.1f} A"))
    fig2.add_vline(x=cr.TAP_LIMIT_A, line_dash="dash", line_color=NG,
                   annotation_text=f"定格 {cr.TAP_LIMIT_A:.0f} A")
    fig2.add_vline(x=cr.TAP_LIMIT_A * 0.8, line_dash="dot", line_color="#888",
                   annotation_text="余裕を見た目安 80%", annotation_position="bottom")
    fig2.update_layout(barmode="stack", height=220, margin=dict(t=30, b=10),
                       xaxis=dict(title="電流 [A]", range=[0, max(cr.TAP_LIMIT_A * 1.3, load["total_a"] * 1.1)]))
    st.plotly_chart(fig2, width="stretch")
    m1, m2 = st.columns(2)
    m1.metric("合計電流", f"{load['total_a']:.1f} A", f"定格の {load['ratio'] * 100:.0f}%", delta_color="off")
    m2.metric("合計電力", f"{load['total_w']:.0f} W")
    if not load["ok"]:
        st.error("定格を超えます。タップやコードが熱くなり、火災の原因になります。"
                 "どれかを別のコンセント（別の回路）に分けるか、時間をずらしましょう。")
    elif load["ratio"] > 0.8:
        st.warning("定格以内ですが余裕が少なめです。長時間使う機器は別のコンセントに分けると安心です。")
    else:
        st.success("定格以内で、余裕もあります。")

    with st.expander("発展：電力量と電気代（中2「電力量」）"):
        e1, e2, e3 = st.columns(3)
        pw = e1.number_input("消費電力 [W]", 1, 3000, 100, key="e_w")
        hr = e2.number_input("1日に使う時間 [h]", 0.0, 24.0, 8.0, 0.5, key="e_h")
        yen = e3.number_input("電気代の単価 [円/kWh]（契約で確認）", 1.0, 100.0, 31.0, 1.0, key="e_y")
        st.write(f"1日 {pw / 1000 * hr:.2f} kWh → 約 **{cr.energy_cost_yen(pw, hr, yen):.0f} 円**、"
                 f"30日で約 **{cr.energy_cost_yen(pw, hr * 30, yen):,.0f} 円**")

    st.text_area("自分の判断：自分の家（工房）では、どの機器を同じタップで使う？　理由を数値で", key="judge_a")

# ═════════════════════════════════════════════
# B. 質量パーセント濃度
# ═════════════════════════════════════════════
with tab_b:
    st.header("🧂 パン屋の「塩2%」と、理科の「2%」は同じ？")
    deciders("質量パーセント濃度")
    st.write("理科の質量パーセント濃度は **溶液全体** が分母。パン屋のベーカーズ％は **粉** が分母。"
             "「何を100とするか」で、同じ材料でも％が変わります。")

    st.subheader("① 現象を計算する")
    b1, b2, b3, b4 = st.columns(4)
    flour = b1.number_input("強力粉 [g]", 1, 5000, 500, 10)
    salt = b2.number_input("塩 [g]", 0, 500, 10, 1)
    water = b3.number_input("水 [g]", 0, 5000, 340, 10)
    yeast = b4.number_input("酵母・その他 [g]", 0, 500, 10, 1)
    k1, k2, k3 = st.columns(3)
    k1.metric("ベーカーズ％（塩 ÷ 粉）", f"{cr.bakers_percent(salt, flour):.2f} %")
    k2.metric("生地全体に対する塩の質量％", f"{salt / (flour + salt + water + yeast) * 100:.2f} %")
    k3.metric("仕込み水に溶かした塩水の濃度", f"{cr.mass_percent(salt, water):.2f} %" if water + salt > 0 else "—")
    check_box("chk_pct", "食塩 25 g を水 75 g に溶かした食塩水の濃度は何％？",
              cr.diagnose_percent, 25.0, 75.0, unit="%")

    st.subheader("② 数値を可視化する")
    st.caption("水を足していくと濃度はどう下がる？　直線ではなく、だんだんゆるやかになる曲線。"
               "「水を2倍にしたら濃度が半分」にはならない（分母は溶液全体だから）。")
    v1, v2 = st.columns(2)
    sol = v1.number_input("溶質（食塩）[g]", 1, 200, 10, key="c_sol")
    sv0 = v2.number_input("はじめの水 [g]", 1, 2000, 90, key="c_sv")
    curve = cr.concentration_curve(sol, sv0, sv0 * 9)
    fig = px.line(curve, x="足した水_g", y="濃度_%")
    fig.update_layout(height=320, margin=dict(t=10, b=10),
                      xaxis_title="足した水 [g]", yaxis_title="質量パーセント濃度 [%]")
    st.plotly_chart(fig, width="stretch")

    st.subheader("③ 自分の条件で判断する")
    j1, j2 = st.columns(2)
    with j1, st.container(border=True):
        st.markdown("**🌾 米ぬか発酵肥料の水分を決める**")
        st.caption("米ぬかの水分を約12%として、水分（水の質量％）を目標まで上げる水の量。"
                   "仕上げは「手で握ると固まり、つつくと崩れる」で確かめる。")
        nuka = st.number_input("米ぬか [kg]", 0.5, 500.0, 10.0, 0.5)
        now = st.number_input("いまの水分 [%]", 0.0, 60.0, 12.0, 1.0)
        tgt = st.slider("目標の水分 [%]", 20, 60, 40)
        add = cr.water_to_add(nuka, now, tgt)
        st.metric("足す水", f"{add:.1f} kg（≒ {add:.1f} L）")
    with j2, st.container(border=True):
        st.markdown("**🌱 液肥を何倍に薄める？**")
        st.caption("製品の説明書の倍率に従います。ここでは原液の量と、薄めた後の濃度を計算します。")
        times = st.number_input("希釈倍率 [倍]", 1, 5000, 1000, 50)
        can = st.number_input("ジョウロの容量 [L]", 0.5, 50.0, 5.0, 0.5)
        stock = st.number_input("原液の濃度（成分の％）", 0.0, 50.0, 6.0, 0.5)
        st.metric("原液の量", f"{cr.stock_ml_for(can * 1000, times):.1f} mL")
        st.caption(f"薄めた後の濃度：約 {cr.dilute_percent(stock, times):.4f} %")
    st.text_area("自分の判断：自分の畑・台所では、どの％を何に使う？　分母は何？", key="judge_b")

# ═════════════════════════════════════════════
# C. 化学変化と質量
# ═════════════════════════════════════════════
with tab_c:
    st.header("🔥 蒸しパンの重曹は、どこへ行く？")
    deciders("化学変化と質量")
    st.write("重曹（炭酸水素ナトリウム）を加熱すると、**炭酸ナトリウム（固体）が残り**、"
             "**二酸化炭素と水蒸気が出ていきます**。出ていく二酸化炭素が生地をふくらませ、"
             "残る炭酸ナトリウムが多すぎると苦みや黄ばみの原因になります。")

    st.subheader("① 現象を計算する（実験から比を求める）")
    st.caption("加熱前と、加熱し切った後の質量を記録する。初期値は架空データ（実測ではありません）。")
    heat = st.data_editor(cr.sample_heating(), key="heat_ed", num_rows="dynamic", width="stretch")
    heat = heat.dropna()
    heat = heat[heat["加熱前_g"] > 0]
    if len(heat) >= 2:
        a = cr.fit_through_origin(heat["加熱前_g"], heat["加熱後_g"])
        st.metric("比（残る質量 ÷ 加熱前）", f"{a:.3f}", f"理論値 {cr.NAHCO3_RESIDUE:.3f} との差 {a - cr.NAHCO3_RESIDUE:+.3f}",
                  delta_color="off")
    else:
        a = cr.NAHCO3_RESIDUE
        st.info("2行以上入れると、比を計算します。")
    check_box("chk_res", "重曹 8.4 g を加熱し切ると、何 g 残る？（比 0.63）",
              cr.diagnose_residue, 8.4, unit="g")

    st.subheader("② 数値を可視化する")
    g1, g2 = st.columns(2)
    with g1:
        fig = px.scatter(heat, x="加熱前_g", y="加熱後_g")
        xmax = float(heat["加熱前_g"].max()) if len(heat) else 5.0
        fig.add_trace(go.Scatter(x=[0, xmax * 1.1], y=[0, xmax * 1.1 * a], mode="lines",
                                 name=f"y = {a:.2f} x", line=dict(dash="dash")))
        fig.update_layout(height=320, margin=dict(t=10, b=10), xaxis_title="加熱前 [g]",
                          yaxis_title="加熱後 [g]", xaxis_rangemode="tozero", yaxis_rangemode="tozero")
        st.plotly_chart(fig, width="stretch")
        st.caption("点が原点を通る直線に並ぶ ＝ 比例。傾きが「割合 a」。")
    with g2:
        soda_v = st.number_input("重曹 [g]", 0.1, 100.0, 2.0, 0.1, key="oc_soda")
        oc = cr.open_vs_closed(soda_v)
        fig3 = px.bar(oc, x="条件", y=["加熱前_g", "加熱後_g"], barmode="group")
        fig3.update_layout(height=280, margin=dict(t=10, b=10), yaxis_title="はかりの値 [g]", legend_title="")
        st.plotly_chart(fig3, width="stretch")
        st.dataframe(oc[["条件", "理由"]], hide_index=True, width="stretch")

    st.subheader("③ 自分の条件で判断する：重曹を何 g 入れる？")
    d1, d2 = st.columns(2)
    flour_c = d1.number_input("薄力粉 [g]", 50, 2000, 200, 10, key="mushi_flour")
    soda_g = d2.slider("重曹 [g]", 0.0, 10.0, 3.0, 0.5)
    pr = cr.soda_products(soda_g)
    r1, r2, r3 = st.columns(3)
    r1.metric("重曹のベーカーズ％", f"{cr.bakers_percent(soda_g, flour_c):.1f} %")
    r2.metric("出る二酸化炭素", f"{pr['二酸化炭素_g']:.2f} g ≒ {pr['二酸化炭素_L']:.2f} L")
    r3.metric("残る炭酸ナトリウム", f"{pr['残る炭酸ナトリウム_g']:.2f} g")
    st.caption("ふくらみ（二酸化炭素）と苦み（炭酸ナトリウム）は、同じ比で一緒に増える。"
               "どこで止めるかは、作る人の判断。酸（ヨーグルト・レモン汁など）を合わせると苦みが出にくくなる理由は、高校化学基礎で。")
    with st.expander("発展（高校 化学基礎）：0.63 はどこから来る？"):
        st.write("2NaHCO₃ → Na₂CO₃ + H₂O + CO₂。分子の重さで 168 g → 106 g + 18 g + 44 g。"
                 f"106 ÷ 168 = {cr.NAHCO3_RESIDUE:.3f}。左右の合計が等しいのが質量保存の法則。")
    st.text_area("自分の判断：自分の蒸しパンには重曹を何 g 入れる？　ふくらみと苦みのどちらを優先した？", key="judge_c")

# ═════════════════════════════════════════════
# 横軸：「使う仕事が想像できる」学び
# ═════════════════════════════════════════════
with tab_x:
    st.header("🌱 「使う仕事が想像できる」学びにする")
    st.subheader("国際調査（TIMSS 2023）中学2年・理科")
    t = cr.TIMSS2023_G8_SCIENCE.melt(id_vars="質問", var_name="", value_name="%")
    t[""] = t[""].str.replace("_%", "")
    fig = px.bar(t, x="%", y="質問", color="", barmode="group", orientation="h", text="%",
                 color_discrete_map={"日本": "#3f7cac", "国際平均": "#c98a2b"})
    fig.update_layout(height=280, margin=dict(t=10, b=10), xaxis=dict(range=[0, 100], title="肯定的に答えた割合 [%]"),
                      yaxis_title="", legend_title="")
    st.plotly_chart(fig, width="stretch")
    st.markdown(
        "- 日本の中2は「楽しい」が70%あっても、「得意だ」は45%、"
        "**「理科を使う職業につきたい」は27%で、国際平均（58%）の半分以下**。\n"
        "- 差がいちばん大きいのは「楽しさ」ではなく **「使う仕事が想像できるか」**。"
    )
    st.caption(f"出典：IEA 国際数学・理科教育動向調査（TIMSS 2023）。数値は nippon.com の記事より（{TIMSS_URL}）。"
               f"詳細は文部科学省・国立教育政策研究所の公表資料（{MEXT_TIMSS_URL}）を参照。")

    # ── なぜ「職業一覧」では足りないか ──
    st.subheader("「この計算を使う職業」の一覧を見せるだけでは足りない")
    st.write("「看護師も使います」「エンジニアも使います」と名前を並べても、"
             "生徒の頭には **その人が何をしている場面** が浮かびません。想像できるのは、"
             "**誰かが、ある数値を決めるために計算し、間違えると困ることが起きる** という場面まで見えたときです。"
             "このページでは、次の5つの原則で組み立てています。")
    st.dataframe(cr.DESIGN_PRINCIPLES, width="stretch", hide_index=True)
    with st.expander("原則④⑤の根拠（研究の例）"):
        st.markdown(
            f"- **④ 生徒が自分で書く**：米国の高校理科で、学んだ内容と自分の生活とのつながりを生徒自身に"
            f"書かせる課題を続けたところ、成績への見通しが低かった生徒ほど、興味と成績が伸びたと報告されています"
            f"（Hulleman & Harackiewicz, 2009, *Science*）。[論文PDF]({HULLEMAN_URL})\n"
            f"- **⑤ 身近な大人**：保護者に「理数がどう役に立つか」を伝える資料を渡したところ、"
            f"子どもの高校での理数科目の履修が増えたと報告されています"
            f"（Harackiewicz et al., 2012, *Psychological Science*）。[論文]({PARENT_URL})\n"
            "- どちらも米国での研究です。日本の中学生に同じ効果があるかは、確かめる対象です。"
        )

    # ── 💼 仕事ミッション ──
    st.subheader("💼 仕事ミッション：その仕事の人になって、数値を決める")
    st.caption("仕事を1つ選び、その人が実際に決めている数値を計算します。正解すると「何を決めているか」「間違えると何が起きるか」が開きます。")
    names = [m["仕事"] for m in cr.MISSIONS]
    pick = st.radio("仕事を選ぶ", names, horizontal=True, key="mission_pick")
    m = cr.MISSIONS[names.index(pick)]
    with st.container(border=True):
        st.markdown(f"**{m['仕事']}**（{m['単元']}）")
        st.write(m["場面"])
        st.markdown(f"**問い：{m['問い']}**")
        ans = st.number_input(f"答え（{m['単位']}）", value=None, step=1.0, format="%.2f",
                              key=f"mission_{names.index(pick)}")
        if ans is not None:
            if cr.check_mission(ans, m):
                st.success(f"正解。{m['式']} = {m['答え']:g} {m['単位']}")
                c1, c2 = st.columns(2)
                c1.info(f"**この数値で決めること**\n\n{m['決めること']}")
                c2.error(f"**間違えると**\n\n{m['間違えると']}")
                st.session_state.setdefault("mission_done", set()).add(pick)
            else:
                st.warning("もう一度。「何を もと（100%・1）にするか」を確かめよう。")
                with st.expander("ヒント：式"):
                    st.write(m["式"])
    done = st.session_state.get("mission_done", set())
    st.progress(len(done) / len(names), text=f"クリアした仕事：{len(done)} / {len(names)}")

    # ── ✍️ 自分の言葉でつなぐ ──
    st.subheader("✍️ 自分の言葉でつなぐ（原則④）")
    st.caption("先生や画面が「役に立つ」と言うより、自分で書いたつながりのほうが残ります。単元ごとに空欄を埋めてください。")
    st.markdown(f"> {cr.UTILITY_TEMPLATE}")
    for i, unit in enumerate(UNITS):
        st.text_area(unit, key=f"utility_{i}", height=80,
                     placeholder="例：この計算は、パン職人が明日の塩の量を決めるときに使う。"
                                 "間違えると味がぼやける。自分の生活では、カルピスを薄めるときに使えそう。")

    # ── 🗣️ 身近な大人に聞く ──
    st.subheader("🗣️ 身近な大人に聞く（原則⑤）")
    st.caption("家族や地域の大人に、次の4つを聞いてきます。名前は書かず、仕事の種類だけ書きます。")
    job_kind = st.text_input("聞いた人の仕事の種類（例：介護職、農家、事務、料理人）", key="iv_job")
    iv_answers = [st.text_area(f"Q{i + 1}. {q}", key=f"iv_{i}", height=70)
                  for i, q in enumerate(cr.INTERVIEW_QUESTIONS)]
    sheet = "身近な大人に聞く（中学理科 量の計算）\n" + f"仕事の種類：{job_kind}\n\n" + "\n\n".join(
        f"Q{i + 1}. {q}\nA. {a}" for i, (q, a) in enumerate(zip(cr.INTERVIEW_QUESTIONS, iv_answers)))
    utility = "\n\n".join(f"{u}\n{st.session_state.get(f'utility_{i}', '')}" for i, u in enumerate(UNITS))
    st.download_button("「自分の言葉でつなぐ」と聞き取りを保存（テキスト）",
                       (f"自分の言葉でつなぐ\n{cr.UTILITY_TEMPLATE}\n\n{utility}\n\n{'─' * 20}\n{sheet}").encode("utf-8-sig"),
                       "使う仕事_ワークシート.txt", "text/plain")

    # ── 📈 前後の記録 ──
    st.subheader("📈 前と後で、何が変わった？")
    st.caption("授業の前と後に、単元ごとに2つの質問を1〜4で記録します（氏名は書かない）。"
               "TIMSS の「得意だ」「理科を使う職業」に対応させています。")
    st.caption("、".join(f"{k}＝{v}" for k, v in cr.EFFICACY_LEVELS.items()))
    if "eff_rec2" not in st.session_state:
        st.session_state.eff_rec2 = pd.DataFrame({"単元": UNITS, "得意_前": [2] * 3, "得意_後": [2] * 3,
                                                  "仕事_前": [2] * 3, "仕事_後": [2] * 3})
    num = dict(min_value=1, max_value=4, step=1)
    rec = st.data_editor(
        st.session_state.eff_rec2, key="eff_ed2", width="stretch", hide_index=True,
        column_config={
            "単元": st.column_config.TextColumn(disabled=True),
            "得意_前": st.column_config.NumberColumn("得意だと思う（前）", **num),
            "得意_後": st.column_config.NumberColumn("得意だと思う（後）", **num),
            "仕事_前": st.column_config.NumberColumn("使う仕事が想像できる（前）", **num),
            "仕事_後": st.column_config.NumberColumn("使う仕事が想像できる（後）", **num),
        })
    summ = cr.efficacy_summary(rec)
    if not summ.empty:
        fig_e = px.line(summ, x="時点", y="平均", color="単元", facet_col="質問", markers=True,
                        category_orders={"時点": ["前", "後"]})
        fig_e.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        fig_e.update_layout(height=300, margin=dict(t=30, b=10), legend_title="")
        fig_e.update_yaxes(range=[0.8, 4.2], dtick=1, title="")
        st.plotly_chart(fig_e, width="stretch")
    st.download_button("自己評価をCSVで保存", sg.safe_csv(rec), "自己評価_量の計算.csv", "text/csv")
    st.caption("研究で使う場合は、前後比較だけでは「授業のおかげ」とは言えません（慣れ・時期の影響が混ざる）。"
               "「⚖️ 比べて確かめる探究」と同じく、比べる相手の置き方を先に決めます。")

st.markdown(
    f'<p style="font-size:.85rem;color:#5a6a75">※ 計算は教育用の単純化モデル、初期値は目安と架空データです。'
    f'最終更新：{UPDATED}</p>',
    unsafe_allow_html=True,
)

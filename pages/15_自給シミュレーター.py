"""
自給と防災の畑シミュレーター ─ 計算する → 可視化する → 自分の条件で判断する
配置先: pages/15_自給シミュレーター.py （Streamlit のマルチページ構成）

問い：「小麦と大豆の二毛作を主体に、ハウスで野菜」は、実家の畑100㎡で最適な自給態勢か？
       水・電気が止まったら、かまど・石窯で何日しのげるか？

方針
  - 計算は jikyu_lab.py（`python jikyu_lab.py` で自己チェック）。
  - 数値はすべて目安の初期値。探究フィールドワークの実測CSVで、自分の畑の値に置き換える。
  - アップロードした記録はセッション内だけで使い、サーバーには残さない。生徒の氏名は扱わない。
  - このページは公開。家計の実額は扱わず、連動先の自給家計簿・収入構造（本人のみ）へ
    計画値を同じセッション内で渡すだけにする。
"""
from dataclasses import replace
from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import jikyu_lab as jl
import security_guard as sg

st.set_page_config(page_title="自給と防災の畑", page_icon="🍞", layout="wide")

PAGE = "jikyu"
CH_COLORS = {
    "自家産（とれたて）": "#6a9a4a", "自家産（保存・貯蔵）": "#2f6f5e", "下味冷凍": "#3f7cac",
    "常備品": "#c98a2b", "現地で買う": "#b77a86",
}

# ─────────────────────── 条件（サイドバー） ───────────────────────
with st.sidebar:
    st.header("共通の条件")
    stage_name = st.selectbox("管理の段階", list(jl.STAGES), index=1,
                              help="隔週帰省だと、収穫遅れ・鳥害・草で収量が大きく落ちる想定です。")
    persons = st.slider("食べる人数", 1, 4, 2)
    house = st.slider("ハウスの面積（㎡）", 0, 60, 20, 5, help="実際の面積に合わせてください（初期値は仮）。")
    bread = st.slider("主食のうちパンの割合（%）", 0, 60, 25, 5) / 100
    keep = st.slider("余りを保存に回せる割合（%）", 0, 90, 50, 10) / 100
    kuri = st.slider("栗5本の樹勢（%）", 10, 100, 40, 10, help="盛りの木を100%として。植えて30年。") / 100
    rice_own = st.checkbox("米を委託中の水田から現物で受け取る（想定）")
    if "jikyu_coef" in st.session_state:
        st.success("収量の係数は、読み込んだ実測値を使っています。")
        if st.button("初期値に戻す"):
            del st.session_state["jikyu_coef"]
            st.rerun()

base = jl.Conditions(persons=persons, stage=jl.STAGES[stage_name], house_m2=house,
                     bread_share=bread, keep_rate=keep, kuri_vigor=kuri, rice_own=rice_own,
                     coef=st.session_state.get("jikyu_coef", dict(jl.COEF)))

st.title("🍞 自給と防災の畑シミュレーター")
st.caption("三原市西部の実家：畑100㎡・ハウス・柿1本・いちじく2本・栗5本 ／ ① 計算する → ② 可視化する → ③ 自分の条件で判断する")

T = st.tabs(["① 畑の配分を比べる", "② 月ごとの調達", "③ 停電・断水（かまど・石窯）",
             "④ 探究フィールドワーク", "⑤ 家計簿・収入構造とつなぐ"])

# ═════════════════════ ① 畑の配分を比べる ═════════════════════
with T[0]:
    st.subheader("問い：二毛作（小麦→大豆）主体＋ハウス野菜が最適か")
    st.write("同じ条件で4つの案を比べます。何を「最適」とするか（お金・カロリー・たんぱく質・停電への備え・手間）で答えが変わります。")
    cmp = jl.compare_presets(base)
    show = cmp.copy()
    for col in ["重量の自給率", "カロリー自給率", "主食", "野菜", "たんぱく質"]:
        show[col] = (show[col] * 100).round(0).astype(int).astype(str) + "%"
    for col in ["停電でも食べられる備蓄(日)", "野菜の余り(kg/年)", "作業時間(時間/年)"]:
        show[col] = show[col].round(0).astype(int)
    show["全部買う場合との差(円/年)"] = show["全部買う場合との差(円/年)"].map(lambda v: f"{v:,.0f}")
    st.dataframe(show, hide_index=True, width="stretch")
    st.caption("重量の自給率は主食・野菜・果物・たんぱく質の4区分の合計。カロリー自給率は1人1日2,000kcalに対する割合で、"
               "油・砂糖・調味料は含めていないため低めに出ます。差額は種苗・肥料などの資材費を差し引いた値です。")

    long = cmp.melt(id_vars="案", value_vars=["カロリー自給率", "主食", "野菜", "たんぱく質"],
                    var_name="指標", value_name="割合")
    fig = px.bar(long, x="指標", y="割合", color="案", barmode="group",
                 color_discrete_sequence=["#c98a2b", "#7fb3a8", "#6a9a4a", "#3f7cac"])
    fig.update_yaxes(tickformat=".0%", range=[0, 1.05], title=None)
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="")
    st.plotly_chart(fig, width="stretch")

    kpm = jl.kcal_per_m2(base)
    st.markdown("**1㎡あたりのカロリー（年間の目安）**　"
                + "　／　".join(f"{k} **{v:,.0f}** kcal" for k, v in kpm.items()))

    st.divider()
    st.subheader("自分の配分を試す")
    c1, c2 = st.columns(2)
    a_soy = c1.slider("小麦→大豆の面積（㎡）", 0, 100, 70, 5)
    a_imo = c2.slider("小麦→サツマイモの面積（㎡）", 0, 100 - a_soy, 0, 5)
    st.caption(f"残りの {100 - a_soy - a_imo}㎡ は通年の露地野菜。小麦は11〜5月に畑を使い、6月の収穫後に夏作へ回します。")
    st.session_state["jikyu_area"] = (a_soy, a_imo)

    cond = replace(base, a_soy=a_soy, a_imo=a_imo)
    _, s = jl.simulate(cond)
    m = st.columns(4)
    m[0].metric("重量の自給率", f"{s['weight_rate']:.0%}")
    m[1].metric("カロリー自給率", f"{s['kcal_rate']:.0%}")
    m[2].metric("停電でも食べられる乾燥備蓄", f"{s['dry_days']:.0f} 日分")
    m[3].metric("全部買う場合との差", f"{s['net']:,.0f} 円/年")

    st.subheader("判断の材料")
    tips = []
    best_kcal = cmp.loc[cmp["カロリー自給率"].idxmax(), "案"]
    best_money = cmp.loc[cmp["全部買う場合との差(円/年)"].idxmax(), "案"]
    tips.append(f"カロリー（停電時の生き延びやすさ）で選ぶなら **{best_kcal}**、お金で選ぶなら **{best_money}** が上位です。")
    tips.append("野菜は露地30㎡＋ハウスで必要量にほぼ届きます。畑を全部野菜にしても余りが増えるだけで、"
                "主食とたんぱく質は1割も自給できません。")
    tips.append("大豆はたんぱく質を、サツマイモはカロリーを稼ぎます。どちらか一方より、両方を組み合わせた折衷案が"
                "弱点（たんぱく質ゼロ・カロリー不足）を作りにくい配分です。")
    dc = s["double_crop"]
    if dc:
        tips.append(f"**二毛作の季節制約**：夏作の収穫（10月中下旬）が小麦の最適播種日（10/20頃）とぶつかります。"
                    f"播種が11/5まで{dc['delay_days']}日ずれると、発芽率は {dc['germ_opt']:.0%} → {dc['germ_late']:.0%}、"
                    f"種子は {dc['seed_opt_g_m2']:.1f} → {dc['seed_late_g_m2']:.1f} g/㎡ に増え、"
                    f"{cond.a_wheat:.0f}㎡で約 {dc['seed_late_total_kg']:.2f} kg 必要です。"
                    "早生の大豆を選ぶか、夏作の一部だけ早く片付けて小麦を先にまく区画を作ると緩和できます。")
    for t in tips:
        st.markdown(f"- {t}")

# ═════════════════════ ② 月ごとの調達 ═════════════════════
a_soy, a_imo = st.session_state.get("jikyu_area", (70, 0))
cond = replace(base, a_soy=a_soy, a_imo=a_imo)
df, s = jl.simulate(cond)

with T[1]:
    st.subheader("足りない分を、何でまかなうか")
    st.write(f"①で選んだ配分（大豆 {a_soy}㎡・サツマイモ {a_imo}㎡・野菜 {cond.a_veg:.0f}㎡）で、"
             "月ごとの必要量を5つの経路に分けます。")
    cat = st.radio("品目", jl.CATEGORIES, horizontal=True,
                   format_func=lambda k: f"{k}（自給 {s['rate'][k]:.0%}）")
    d = df[df["品目"] == cat].copy()
    d["割合"] = d["kg"] / d.groupby("月")["kg"].transform("sum")
    fig = px.bar(d, x="月", y="割合", color="経路", color_discrete_map=CH_COLORS,
                 category_orders={"経路": jl.CHANNELS}, hover_data={"kg": ":.1f", "割合": ":.0%"})
    fig.update_xaxes(tickmode="array", tickvals=list(range(1, 13)), ticktext=[f"{m}月" for m in range(1, 13)], title=None)
    fig.update_yaxes(tickformat=".0%", title=None)
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="")
    st.plotly_chart(fig, width="stretch")

    pv = df.pivot_table(index="品目", columns="経路", values="kg", aggfunc="sum").reindex(columns=jl.CHANNELS).fillna(0)
    pv["必要量"] = pv.sum(axis=1)
    st.dataframe(pv.round(0).astype(int), width="stretch")
    st.caption("単位は kg/年。主食は米換算、たんぱく質は肉換算。")

    st.subheader("今の「下味冷凍＋常備品＋現地で買う」は、移住後どう変わるか")
    st.dataframe(pd.DataFrame([
        ["下味冷凍", "月1回仕込んで車で運ぶ", "肉・魚の月1回まとめ買いとして続ける（たんぱく質の主力）"],
        ["常備品", "缶詰・乾物・冷凍野菜を実家に置く", "自家製の小麦粉・大豆・干し柿・切り干し大根に置き換わる"],
        ["現地で買う", "惣菜の代わりに卵・豆腐・野菜", "野菜は端境期（2〜4月）だけ。果物は旬以外"],
    ], columns=["経路", "今（隔週帰省）", "移住後"]), hide_index=True, width="stretch")

# ═════════════════════ ③ 停電・断水 ═════════════════════
with T[2]:
    st.subheader("水と電気が止まったら、何日しのげるか")
    st.write("冷凍庫は止まると傷み始め、雨水は煮沸が要り、煮炊きとパン焼きには薪が要ります。食べ物・水・薪を1日ずつ追います。")
    c1, c2, c3 = st.columns(3)
    days = c1.slider("停電・断水の日数", 1, 21, 7)
    month = c1.selectbox("起きる月", list(range(1, 13)), index=8, format_func=lambda m: f"{m}月")
    tank = c2.number_input("雨水タンクの容量（L）", 0, 5000, 200, 50)
    roof = c2.number_input("集水する屋根の面積（㎡）", 0, 200, int(house), 5, help="初期値はハウスの面積")
    freezer = c2.radio("冷凍庫の中身", ["満杯に近い", "半分以下"], horizontal=True)
    rice_kg = c3.number_input("備蓄米（kg）", 0, 120, 30, 5)
    jobi = c3.number_input("常備品（缶詰・乾物）の量（日分）", 0, 60, 7)

    od, os_ = jl.outage(cond, s, days=days, month=month, tank_l=tank, freezer_full=freezer == "満杯に近い",
                        rice_kg=rice_kg, jobi_days=jobi, roof_m2=roof)
    m = st.columns(4)
    m[0].metric("食べ物が続く日数", f"{os_['food_days']:.0f} 日")
    m[1].metric("水が足りなくなる日", f"{os_['water_short_day']} 日目" if os_["water_short_day"] else "期間内は足りる")
    m[2].metric("1日の雨水（平均）", f"{os_['rain_per_day']:.0f} L", f"必要 {os_['need_per_day']:.0f} L/日", delta_color="off")
    m[3].metric(f"{days}日間の薪", f"{os_['wood_total']:.0f} kg")

    fig = go.Figure()
    fig.add_bar(x=od["日"], y=od["その日の薪(kg)"], name="その日の薪（kg）", marker_color="#a08a68", yaxis="y2", opacity=0.6)
    fig.add_scatter(x=od["日"], y=od["水の残り(L)"], name="水の残り（L）", mode="lines+markers", line=dict(color="#3f7cac"))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h"),
                      xaxis_title="日目", yaxis=dict(title="L", rangemode="tozero"),
                      yaxis2=dict(title="kg", overlaying="y", side="right", rangemode="tozero"))
    st.plotly_chart(fig, width="stretch")
    with st.expander("1日ずつの表"):
        st.dataframe(od.round(1), hide_index=True, width="stretch")

    supply = jl.firewood_supply()
    st.subheader("判断の材料")
    st.markdown(
        f"- 冷凍庫は閉めたままで、満杯なら約2日、半分なら約1日もちます。**下味冷凍は最初の{os_['frozen_days']}日で、かまどで焼き切る**順番にします。\n"
        f"- 雨水は屋根1㎡に1mm降ると1Lです。{month}月は1日平均約{os_['rain_per_day']:.0f}L集まる計算です。飲み水は**煮沸かろ過**してから使います。\n"
        f"- 薪は{days}日で約{os_['wood_total']:.0f}kg。栗5本の剪定枝だけで年約{supply:.0f}kg（目安）です。"
        "栗を改植するときに出る材は乾燥に1年かかるので、**今年切った分が来年の備え**になります。\n"
        "- 石窯で一度にまとめて焼けば、パンは数日もつ主食になります。自家産の小麦はここで効きます。"
    )
    st.warning("かまど・石窯は必ず屋外か十分に換気できる場所で使います（一酸化炭素中毒・火災の危険）。"
               "本ページの数値は教育用の単純化モデルです。実際の備えは自治体のハザードマップと防災情報に従ってください。")

# ═════════════════════ ④ 探究フィールドワーク ═════════════════════
with T[3]:
    st.subheader("探究フィールドワークの叩き台")
    st.write("通信制高校・サポート校の探究、総合型選抜に向けた探究、特別支援学校の作業学習の場として使う想定です。"
             "このシミュレーターの**目安の数値を、生徒が畑で測った値に置き換えていく**ことが探究の中心です。")

    st.markdown("**「科学と人間生活」の単元との対応**")
    st.dataframe(pd.DataFrame([
        ["水のリスク", "雨水の集水量（1mm×1㎡＝1L）、1日に必要な水", "③ 停電・断水"],
        ["火と有毒ガス", "かまど・石窯の燃焼、薪の量、一酸化炭素", "③ 停電・断水"],
        ["食と衛生", "乾燥・発酵・冷凍による保存、冷凍庫が止まった後の時間", "② 月ごとの調達"],
        ["土地を読む", "畑の配分、二毛作の季節のぶつかり、1㎡あたりのカロリー", "① 畑の配分"],
        ["情報としての判断", "目安の値と実測の値を区別し、係数を置き換える", "④ この下の記録"],
    ], columns=["単元", "このシミュレーターで扱うこと", "使うタブ"]), hide_index=True, width="stretch")

    st.markdown("**半日プログラム（約3時間）の例**")
    st.dataframe(pd.DataFrame([
        ["30分", "畑の観察と面積の測量（巻尺）", "区画ごとの面積を記録する"],
        ["60分", "実測：収量の計量、雨水タンクの水位、薪1束の重さ", "テンプレートCSVに記録（氏名ではなく記号）"],
        ["30分", "記録を読み込み、係数を置き換えて再計算", "目安の値との差を確かめる"],
        ["30分", "自分の家に置き換えて判断（マイ・タイムライン）", "停電が何日続いたら困るかを決める"],
        ["30分", "発表と振り返り", "根拠の数値を添えて説明する"],
    ], columns=["時間", "活動", "成果物"]), hide_index=True, width="stretch")
    st.caption("刃物・火を使う活動は指導者が付き、かまど・石窯の火入れは見学から始めます。")

    st.divider()
    st.markdown("**実測の記録で係数を置き換える**")
    tmpl = jl.measurement_template()
    st.download_button("記録テンプレート（CSV）をダウンロード", sg.safe_csv(tmpl), "自給_実測記録テンプレート.csv", "text/csv")
    st.dataframe(tmpl, hide_index=True, width="stretch")
    st.caption("上の3行は架空の例です。作物名は「小麦・大豆・サツマイモ・露地野菜・ハウス野菜」のいずれかで書きます。")
    up = st.file_uploader("記録したCSVを読み込む", type="csv", key="up_measure")
    if up is not None:
        mdf = sg.read_csv_safely(up, page=PAGE, kind="measure")
        if mdf is not None:
            missing = [c for c in ["作物", "区画面積_m2", "収量_kg"] if c not in mdf.columns]
            if missing:
                st.error(f"列が足りません：{'・'.join(missing)}。テンプレートの列名のまま記録してください。")
            else:
                new = jl.coef_from_measurements(mdf)
                diff = pd.DataFrame([(k, jl.COEF[k].yield_kg_m2, new[k].yield_kg_m2) for k in jl.COEF],
                                    columns=["作物", "目安(kg/㎡)", "実測(kg/㎡)"])
                st.dataframe(diff.round(2), hide_index=True, width="stretch")
                if st.button("この実測値で再計算する"):
                    st.session_state["jikyu_coef"] = new
                    st.rerun()

# ═════════════════════ ⑤ 家計簿・収入構造とつなぐ ═════════════════════
with T[4]:
    st.subheader("計画値を、自給家計簿と収入構造へ渡す")
    st.write("このページは計画（見込み）、自給家計簿は実績、収入構造は10年の家計の見通しです。"
             "同じ品目名・同じ列でつなぐので、計画と実績の差がそのまま次の判断材料になります。")
    year = st.number_input("計画の年", 2026, 2040, date.today().year + 1)
    plan = jl.plan_to_kakeibo(cond, int(year))
    link = jl.income_link(s)
    st.session_state["jikyu_plan"] = plan
    st.session_state["jikyu_link"] = link

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**自給家計簿へ（収穫の計画値）**")
        st.dataframe(plan.groupby("品目")["数量"].sum().round(0).rename("計画(kg/年)"), width="stretch")
        st.download_button("計画値をCSVで保存（家計簿の収穫と同じ列）", sg.safe_csv(plan),
                           f"自給計画_{year}.csv", "text/csv")
    with c2:
        st.markdown("**収入構造へ（C 自給の削減額）**")
        st.metric("削減額の上限", f"{link['saving_cap']:,} 円/年")
        st.metric("年ごとの増分（3年で上限）", f"{link['saving_step']:,} 円")
    st.info("このブラウザで続けて「自給家計簿」「収入構造」（どちらも本人のみ）を開くと、ここで計算した値が初期値として入ります。"
            "別の日に使うときは、上のCSVを家計簿の「計画と比べる」で読み込んでください。")
    with st.expander("データのつながり（構造）"):
        st.code(
            "自給シミュレーター（公開・計画）\n"
            "  ├─ plan_to_kakeibo() ─→ 日付, 品目, 数量, 単位, 単価(円)  ─→ 自給家計簿「計画と比べる」\n"
            "  │                                                         ↑ 実績：収穫を記録（同じ列）\n"
            "  └─ income_link() ────→ saving_step, saving_cap          ─→ 収入構造「C 自給（削減額）」\n"
            "探究フィールドワーク（実測CSV）─→ coef_from_measurements() ─→ 収量の係数を置き換え",
            language="text",
        )

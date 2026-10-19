"""
研究・実証 ─ 微生物（酵母・乳酸菌等）からの挑戦：見えない働き手を、数えて・式にして・確かめる
配置先: pages/17_🦠_微生物からの挑戦.py （Streamlit のマルチページ構成）

小麦 → パン → 米ぬか・残渣 → 発酵肥料 → 土 の循環で、いちばん働いているのに見えないのが微生物。
4つのタブで、それぞれの本を畑の題材に当てはめる。骨格はリポジトリ共通の3段構え：
  ① 計算する → ② 可視化する → ③ 自分の条件で判断する（＋ ✅ トレース表・DNCL、📝 3行の報告）

  🍞 酵母（パン種）       … 『酵母からのチャレンジ ─応用酵母学─』        → ロジスティック曲線・倍加時間・温度モデル
  🥛 乳酸菌との共棲       … 同「酵母と共棲する乳酸菌」                    → オイラー法のシミュレーション（情報Ⅰ モデル化）
  🌾 米ぬか発酵肥料       … 『エッセンシャル土壌微生物学』               → C/N と水分の配合計算・堆肥温度の見張り
  🔬 微生物検査           … 『食品中の微生物検査法解説書』『化粧品の微生物試験ガイドブック』 → 段階希釈のCFU・ベイズ・保存効力試験

方針
  - 計算は microbe_lab.py（`python microbe_lab.py` で手計算との自己チェック）。
  - 初期表示はすべて教材用の架空データ。材料の C/N などは文献で幅のある「目安」、判定の境目は人が変えられる初期値。
  - 写真は assets/ の取り込み済みのものを、位置情報（Exif）を外して表示する。外部の生成AIは呼び出さない。
"""
import math
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import diary_photos as dp
import microbe_lab as mb
import security_guard as sg

st.set_page_config(page_title="微生物（酵母・乳酸菌等）からの挑戦", page_icon="🦠", layout="wide")

ROOT = Path(__file__).parent.parent
ASSETS = ROOT / "assets"
C_Y, C_L, C_C, C_PH = "#b45309", "#0369a1", "#9f1239", "#64748b"

st.title("🦠 微生物（酵母・乳酸菌等）からの挑戦")
st.caption("見えない働き手を、数えて・式にして・確かめる ── 小麦 → パン → 米ぬか → 発酵肥料 → 土 の循環を支える微生物")

with st.container(border=True):
    st.markdown(
        "**研究メモ**：この畑の循環（🌱 土づくり → 🌾 小麦 → 🍞 パン → ♻️ 米ぬか・残渣を発酵肥料に）は、"
        "どの段にも微生物がいる。パンを膨らませる**酵母**、ぬか床やサワー種・ぼかしで酸をつくり雑菌を抑える**乳酸菌**、"
        "米ぬかや雑草を分解して作物の養分に戻す**土壌微生物**。そして、食品や化粧品として人に渡す前には、"
        "**微生物を数えて安全を確かめる**。問いは「目に見えない微生物の働きを、どこまで数と式で捉え、"
        "作業の判断（仕込みの時間・切り返し・出荷の可否）につなげられるか」である。"
        "注意点は三つある。第一に、ここでの式は**現象を単純にしたモデル**で、係数は手元の記録で確かめ直す。"
        "第二に、微生物は**数え方で数が変わる**（希釈・平板の選び方）ので、数え方を書き添える。"
        "第三に、**培養は安全の範囲で**行う。"
    )

with st.expander("⚠️ 安全のために（最初に読む）", expanded=False):
    st.markdown(
        "- **家庭・学校で行うのは「見えている発酵」まで**（パン種・ぬか床・ぼかし・ヨーグルト）。病原菌を増やす目的の培養はしない。\n"
        "- 自家製酵母の瓶に**カビ（白・青・黒のふわふわ）や腐敗臭**が出たら、味見せずに捨てる。\n"
        "- 寒天培地で手や空気の菌を増やす実験は、**ふたを開けずに観察**し、先生の指導のもとで加熱・消毒してから捨てる。\n"
        "- 発酵肥料は、**未熟なまま畑に入れない**（熱やガスで根を傷める）。熟成は温度と匂い（甘酸っぱい・土の匂い）で確かめる。\n"
        "- 手づくりの化粧品・食品は、**保存効力試験や微生物検査をせずに人に配らない・売らない**（④のタブ）。"
    )

with st.expander("このページの道のり：4冊の本 → 4つのタブ → 情報Ⅰ・データサイエンスの道具", expanded=False):
    st.markdown(
        "| タブ | 下敷きにした本 | この畑の題材 | 道具（情報Ⅰ・DS） | 判断すること |\n|---|---|---|---|---|\n"
        "| 🍞 酵母 | 田村学造 編『酵母からのチャレンジ ─応用酵母学─』（野生酵母・新しい製パン法） | 自家製酵母の生地の膨らみ | ロジスティック曲線の当てはめ・倍加時間・温度モデル | 室温から仕込みの時間を決める |\n"
        "| 🥛 乳酸菌 | 同「酵母と共棲する乳酸菌」 | サワー種・ぬか床・ぼかしの「よい匂い」 | オイラー法のシミュレーション（モデル化） | 乳酸菌を先に増やすべきか |\n"
        "| 🌾 発酵肥料 | 南澤究・妹尾啓史 編『エッセンシャル土壌微生物学』（有機物の無機化・物質循環） | 9/22〜23 に仕込んだ米ぬか発酵肥料 | 加重平均（C/N）・水分の式・時系列の見張り | 配合・水・切り返しの時期 |\n"
        "| 🔬 検査 | 三瀬勝利・井上富士男 編『食品中の微生物検査法解説書』／浅賀良雄『Q&A181 化粧品の微生物試験ガイドブック』 | パン・加工品・化粧水の安全 | 段階希釈の計算・ベイズ推定・log の比較 | 出荷・配布してよいか |\n\n"
        "**共通**：計算は `microbe_lab.py`。`python microbe_lab.py` で、手で計算した答えとの一致を確かめています。"
    )

tab_y, tab_l, tab_s, tab_q = st.tabs(["🍞 酵母（パン種）", "🥛 乳酸菌との共棲", "🌾 米ぬか発酵肥料", "🔬 微生物検査（食品・化粧品）"])
report = {}

# ============================================================
# 🍞 酵母
# ============================================================
with tab_y:
    st.subheader("🍞 自家製酵母の生地は、何時間で何倍に膨らむか")
    st.caption("酵母は糖を食べて CO₂ を出し、生地を膨らませる。最初は倍々（指数関数）、粉の糖や場所が尽きると頭打ち（ロジスティック）。")
    src = st.radio("データ", ["架空の記入例（レーズン酵母・3つの温度）", "自分の記録CSVを読み込む"], horizontal=True, key="y_src")
    if src.startswith("自分"):
        st.caption("列：`時間_h,温度_C,体積倍率`（仕込み直後を1.0として、瓶や容器の目盛りで測る）")
        up = st.file_uploader("記録CSV", type="csv", key="y_up")
        dough = sg.read_csv_safely(up, page="microbe", kind="dough") if up is not None else None
        if dough is None or not {"時間_h", "温度_C", "体積倍率"} <= set(dough.columns):
            st.info("列 `時間_h,温度_C,体積倍率` のCSVを読み込んでください。")
            dough = None
    else:
        dough = mb.sample_dough()
        st.caption("表示しているのは**教材用の架空データ**です。")

    if dough is not None:
        # ── ① 計算する ──
        fits = []
        for temp, g in dough.groupby("温度_C"):
            try:
                f = mb.fit_logistic(g["時間_h"], g["体積倍率"])
            except ValueError as e:
                st.warning(f"{temp}℃：{e}")
                continue
            fits.append({"温度_C": temp, "はじめ N0": round(f["N0"], 2), "頭打ち K": round(f["K"], 2),
                         "増える速さ r(/h)": round(f["r"], 3), "倍加時間(h)": round(f["倍加時間"], 2), "R²": round(f["R²"], 3)})
        fit_df = pd.DataFrame(fits)
        st.markdown("**① 温度ごとに式を当てはめる**　$N(t)=\\dfrac{K}{1+(K/N_0-1)e^{-rt}}$")
        st.dataframe(fit_df, hide_index=True, width="stretch")
        st.caption("倍加時間 = ln2 ÷ r：最初の倍々の時期に、数が2倍になるのにかかる時間。"
                   "生地の体積は酵母の数そのものではなく、出した CO₂ の結果であることに注意（測っているのは「働き」）。")

        # ── ② 可視化する ──
        c1, c2 = st.columns([3, 2])
        fig = px.scatter(dough, x="時間_h", y="体積倍率", color=dough["温度_C"].astype(str) + "℃",
                         color_discrete_sequence=["#0369a1", "#15803d", "#c2410c", "#7c3aed"])
        tt = np.linspace(0, dough["時間_h"].max(), 80)
        for (_, f), col in zip(fit_df.iterrows(), ["#0369a1", "#15803d", "#c2410c", "#7c3aed"]):
            fig.add_trace(go.Scatter(x=tt, y=mb.logistic(tt, f["はじめ N0"], f["頭打ち K"], f["増える速さ r(/h)"]),
                                     mode="lines", line=dict(color=col), showlegend=False))
        fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="温度")
        c1.plotly_chart(fig, width="stretch")
        with c2:
            st.markdown("**温度と増える速さ（カーディナル温度モデル）**")
            t_min, t_max = st.slider("増えなくなる温度（下限・上限）", -5, 50, (2, 40), key="y_card")
            t_opt = st.slider("いちばんよく増える温度（最適）", -4, 49, 30, key="y_opt")
            if not t_min < t_opt < t_max:
                st.warning("最適の温度は、下限と上限のあいだにしてください（いまは間に入るよう直して計算しています）。")
                t_max = max(t_max, t_min + 2)
                t_opt = min(max(t_opt, t_min + 1), t_max - 1)
            mu_opt = float(fit_df["増える速さ r(/h)"].max()) if len(fit_df) else 0.5
            TT = np.linspace(-5, 50, 200)
            fig_t = go.Figure(go.Scatter(x=TT, y=mb.cardinal_rate(TT, t_min, t_opt, t_max, mu_opt), mode="lines",
                                         line=dict(color=C_Y), name="モデル"))
            if len(fit_df):
                fig_t.add_trace(go.Scatter(x=fit_df["温度_C"], y=fit_df["増える速さ r(/h)"], mode="markers",
                                           marker=dict(size=11, color="#111827"), name="記録から"))
            fig_t.update_layout(height=250, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="温度(℃)",
                                yaxis_title="r(/h)", showlegend=False)
            st.plotly_chart(fig_t, width="stretch")
            st.caption("酵母は 25〜30℃ ほどでよく増え、40℃を超えると弱り、低温ではゆっくりになる（境目は菌株で違う）。")

        # ── ③ 判断する ──
        st.markdown("**③ 自分の条件で判断する：今夜の室温で、朝に何倍になっているか**")
        j1, j2, j3 = st.columns(3)
        room = j1.slider("室温(℃)", 5, 35, 18, key="y_room")
        target = j2.slider("目標の体積倍率", 1.2, 2.5, 2.0, 0.1, key="y_target")
        hours = j3.slider("置いておく時間(h)", 1, 16, 8, key="y_hours")
        if len(fit_df):
            K, N0 = float(fit_df["頭打ち K"].mean()), float(fit_df["はじめ N0"].mean())
            r_room = float(mb.cardinal_rate(room, t_min, t_opt, t_max, mu_opt))
            if r_room <= 0:
                st.error(f"{room}℃ では、このモデルでは酵母が増えません。温かい場所を探します。")
            elif target >= K:
                st.warning(f"目標 {target:.1f} 倍は頭打ち（約 {K:.1f} 倍）を超えるので届きません。")
            else:
                need = math.log((K / N0 - 1) / (K / target - 1)) / r_room
                at = float(mb.logistic(hours, N0, K, r_room))
                m1, m2 = st.columns(2)
                m1.metric(f"{target:.1f}倍になるまで", f"{need:.1f} 時間", help=f"{room}℃での r = {r_room:.3f}/h")
                m2.metric(f"{hours} 時間後の体積", f"{at:.2f} 倍")
                st.caption("室温が記録の温度の外（20〜30℃の外）なら**外挿**で、当たりにくい。冬の夜は温度計を置いて記録を足します。")
                report["🍞 酵母"] = (
                    f"観測：架空の記録では、倍加時間は {', '.join(f'{a}℃ {b}h' for a, b in zip(fit_df['温度_C'], fit_df['倍加時間(h)']))} だった（R² は {fit_df['R²'].min():.2f} 以上）。\n"
                    f"解釈：温度モデルでは室温 {room}℃ で {target:.1f} 倍になるのに約 {need:.1f} 時間かかる見込みで、仕込みの時刻を逆算できる。\n"
                    "限界：体積は酵母の数ではなく CO₂ の結果。粉・水分・種の状態で係数が変わり、記録の温度範囲の外は外挿になる。")

        with st.expander("✅ トレース表：倍々は何回で目標を超えるか（共通テスト『情報Ⅰ』のDNCL）"):
            d1, d2, d3 = st.columns(3)
            n0 = d1.number_input("はじめの数（個/g）", 1.0, 1e6, 1000.0, key="y_n0")
            tgt = d2.number_input("目標の数（個/g）", 2.0, 1e10, 1e6, key="y_tgt")
            dtd = d3.number_input("倍加時間(h)", 0.1, 24.0, 1.5, key="y_dt")
            try:
                tr = mb.doubling_trace(n0, tgt, dtd)
                st.dataframe(tr, hide_index=True, width="stretch")
                st.success(f"{len(tr)} 回（{len(tr) * dtd:.1f} 時間）で目標を超えます。式で確かめる：log₂({tgt:g}/{n0:g}) = {math.log2(tgt / n0):.2f} → 切り上げて {math.ceil(math.log2(tgt / n0))} 回")
            except ValueError as e:
                st.error(str(e))
            st.code("N = はじめの数\nかいすう = 0\nN < 目標 の間、繰り返す:\n│ N = N × 2\n└ かいすう = かいすう + 1\n"
                    "表示する(かいすう, かいすう × 倍加時間)", language="text")
        st.caption("比べ方の設計：温度の効果を確かめるなら、**同じ種・同じ粉・同じ水**の瓶をつくり、どの瓶をどの温度に置くかをくじで決める"
                   "（⚖️ 比べて確かめる探究 のくじと同じ）。")

# ============================================================
# 🥛 乳酸菌との共棲
# ============================================================
with tab_l:
    st.subheader("🥛 乳酸菌が先に酸をつくると、雑菌は増えられない")
    st.caption("サワー種・ぬか床・ぼかしで「ヨーグルトのような甘酸っぱい匂い」がするのは、乳酸菌が pH を下げて雑菌を抑えているしるし。"
               "酵母は酸に強いので、乳酸菌と一緒に暮らせる（共棲）。")
    l1, l2 = st.columns([1, 2])
    with l1:
        lab0 = st.slider("はじめの乳酸菌（相対値）", 0.0, 10.0, 1.0, 0.5, key="l_lab")
        con0 = st.slider("はじめの雑菌（相対値）", 0.1, 10.0, 1.0, 0.1, key="l_con")
        r_con = st.slider("雑菌の増える速さ r", 0.1, 1.0, 0.45, 0.05, key="l_rc",
                          help="乳酸菌（0.35）より速い設定が初期値。速い雑菌にも勝てるか")
        stop_c = st.slider("雑菌が止まる pH", 3.8, 5.5, 4.6, 0.1, key="l_stop")
        acid = st.slider("乳酸菌1あたりの酸のつくりやすさ", 0.0, 0.01, 0.004, 0.001, format="%.3f", key="l_acid")
    sim = mb.coculture(y0=(1.0, lab0, con0), r=(0.25, 0.35, r_con), acid_per_lab=acid, ph_stop_c=stop_c)
    ref = mb.coculture(y0=(1.0, 0.0, con0), r=(0.25, 0.35, r_con), acid_per_lab=acid, ph_stop_c=stop_c)
    with l2:
        fig_l = go.Figure()
        for col, c in [("酵母", C_Y), ("乳酸菌", C_L), ("雑菌", C_C)]:
            fig_l.add_trace(go.Scatter(x=sim["時間_h"], y=sim[col], name=col, line=dict(color=c, width=3)))
        fig_l.add_trace(go.Scatter(x=ref["時間_h"], y=ref["雑菌"], name="雑菌（乳酸菌なし）", line=dict(color=C_C, dash="dot")))
        fig_l.add_trace(go.Scatter(x=sim["時間_h"], y=sim["pH"], name="pH", yaxis="y2", line=dict(color=C_PH, dash="dash")))
        fig_l.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="時間(h)", yaxis_title="数（相対値）",
                            yaxis2=dict(title="pH", overlaying="y", side="right", range=[3, 7]), legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_l, width="stretch")
    end, end_ref = sim.iloc[-1], ref.iloc[-1]
    m1, m2, m3 = st.columns(3)
    m1.metric("72時間後の雑菌", f"{end['雑菌']:.1f}", f"{end['雑菌'] - end_ref['雑菌']:+.1f}（乳酸菌なしと比べて）", delta_color="inverse")
    m2.metric("72時間後の pH", f"{end['pH']:.2f}")
    hit = sim[sim["pH"] <= stop_c]
    m3.metric(f"pH が {stop_c} まで下がった時刻", f"{hit['時間_h'].iloc[0]:.0f} 時間" if len(hit) else "下がらない")
    st.caption("このモデルでの「効果」は、同じ条件で**乳酸菌だけを0にした世界**（点線）と比べた差＝反実仮想。"
               "実際の瓶では片方しか観察できないので、比べるには瓶を2つ用意し、くじで割り当てる。")
    report["🥛 乳酸菌"] = (
        f"観測：シミュレーションでは、乳酸菌を {lab0:g} 入れると72時間後の雑菌は {end['雑菌']:.1f}（入れないと {end_ref['雑菌']:.1f}）、pH は {end['pH']:.2f} になった。\n"
        "解釈：雑菌のほうが速く増える設定でも、乳酸菌が先に pH を下げれば雑菌は途中で止まる。ぬか床やサワー種の「種継ぎ（前の種を足す）」は、はじめの乳酸菌を増やす操作と読める。\n"
        "限界：3種類だけの単純なモデルで、係数は仮置き。実際の瓶の pH を試験紙で毎日測り、曲線と比べて確かめる。")

    with st.expander("✅ オイラー法を1歩ずつ追う（情報Ⅰ「モデル化とシミュレーション」・DNCL）"):
        e1, e2 = st.columns([1, 3])
        dt = e1.select_slider("1歩の時間 Δt", [2.0, 1.0, 0.5, 0.25], value=1.0, key="l_dt")
        steps = int(12 / dt)
        et = mb.euler_trace(1.0, 0.5, 100.0, dt, steps)
        e2.dataframe(et, hide_index=True, width="stretch", height=260)
        e1.metric("いちばん大きい誤差", f"{et['誤差'].abs().max():.3f}")
        st.code("N = 1,  r = 0.5,  K = 100,  Δt = " + f"{dt:g}\n"
                "i を 0 から " + f"{steps - 1}" + " まで 1 ずつ増やしながら繰り返す:\n"
                "│ 増える量 = r × N × (1 − N ÷ K)\n"
                "└ N = N + Δt × 増える量\n表示する(N)", language="text")
        st.caption("Δt を半分にすると誤差もおよそ半分になる（オイラー法は1次の精度）。上のグラフの共棲モデルも Δt=0.5h で同じことをしています。")

# ============================================================
# 🌾 米ぬか発酵肥料
# ============================================================
@st.cache_data(show_spinner=False, max_entries=16)
def _photo(path: str):
    return dp.clean_image(Path(path), max_side=900)


with tab_s:
    st.subheader("🌾 米ぬか発酵肥料：土壌微生物に、ちょうどよい餌と水と空気を")
    st.caption("2026/9/22〜23：柿の小枝・天日干しの雑草をコンポストに入れ、その上から米ぬかを2袋。"
               "微生物は炭素（C）をエネルギーに、窒素（N）を体の材料に使う。C/N が低すぎるとアンモニア臭、高すぎると進まない。")
    pics = sorted(p for p in ASSETS.rglob("*.jpg") if "ぬか" in __import__("unicodedata").normalize("NFC", p.name))
    pics = list(dict.fromkeys(p.name for p in pics))
    pic_paths = [next(ASSETS.rglob(n)) for n in pics][:4]
    if pic_paths:
        cols = st.columns(len(pic_paths))
        for c, p in zip(cols, pic_paths):
            try:
                c.image(_photo(str(p)), caption=p.stem, width="stretch")
            except Exception:  # noqa: BLE001
                c.caption(f"表示できませんでした：{p.name}")

    st.markdown("**① 配合を計算する：C/N と水分**")
    s1, s2 = st.columns([3, 2])
    with s1:
        mats = st.data_editor(mb.MATERIALS, hide_index=True, width="stretch", key="s_mats", num_rows="dynamic",
                              column_config={"C/N": st.column_config.NumberColumn(min_value=0, max_value=500),
                                             "N_乾物%": st.column_config.NumberColumn(min_value=0.0, max_value=20.0, format="%.2f"),
                                             "水分%": st.column_config.NumberColumn(min_value=0, max_value=100)})
        st.caption("値は文献で幅のある**目安**です（乾物あたり）。手元の分析値や袋の表示があれば書きかえます。")
    with s2:
        default_kg = {"米ぬか": 30.0, "天日干しの雑草": 5.0, "柿の小枝（剪定枝）": 3.0}
        kg_df = st.data_editor(pd.DataFrame({"材料": mats["材料"], "重さ_kg": [default_kg.get(m, 0.0) for m in mats["材料"]]}),
                               hide_index=True, width="stretch", key="s_kg", disabled=["材料"],
                               column_config={"重さ_kg": st.column_config.NumberColumn(min_value=0.0, max_value=1000.0, step=0.5)})
        st.caption("米ぬか1袋＝15kg として2袋＝30kg（仮置き）。")
    kg = dict(zip(kg_df["材料"], kg_df["重さ_kg"].fillna(0).astype(float)))
    res = mb.mix(mats, kg)
    if res["重さ_kg"] <= 0:
        st.info("材料の重さを入れてください。")
    else:
        t1, t2, t3 = st.columns(3)
        cn = res["C/N"]
        t1.metric("配合の C/N", f"{cn:.1f}", help="C = N% × C/N として、乾物の C と N をそれぞれ足して割る（加重平均）")
        t2.metric("配合の水分", f"{res['水分%']:.0f} %")
        goal = t3.slider("目標の水分(%)", 30, 65, 50, key="s_goal",
                         help="手で握ると団子になり、指で押すとホロっと崩れる＝およそ40〜60%（目安）")
        add = mb.water_to_add(mats, kg, goal)
        st.success(f"水分を {goal}% にするには、水を約 **{add:.1f} kg（≒ {add:.1f} L）** 足します（少しずつ足し、握って確かめる）。")
        if cn < 15:
            st.warning("C/N が低め：窒素が余り、アンモニア臭や高温になりやすい。もみ殻・落ち葉・枝で炭素を足します。")
        elif cn > 35:
            st.warning("C/N が高め：微生物の窒素が足りず、分解が遅い。米ぬか・鶏ふんで窒素を足します。")
        else:
            st.caption("C/N 15〜35 はおおむね発酵が進みやすい範囲（目安。ぼかしは米ぬか主体で20前後）。")
        with st.expander("計算の中身（材料ごとの乾物・N・C）"):
            st.dataframe(res["表"], hide_index=True, width="stretch")
            st.latex(r"\text{C/N} = \frac{\sum_i m_i (1-w_i)\, n_i\, (\text{C/N})_i}{\sum_i m_i (1-w_i)\, n_i}"
                     r"\qquad \text{足す水} = \frac{t\,M - W}{1-t}")
            st.caption("m：重さ、w：水分の割合、n：乾物の窒素の割合、M：全体の重さ、W：いまの水の重さ、t：目標の水分の割合。"
                       "柿の小枝は C/N が高いが重さが小さいので、全体の C/N をあまり動かさない（加重平均）。")

    st.markdown("**② 堆肥の温度を見張る：微生物が働いているか**")
    src_c = st.radio("温度の記録", ["架空の記入例（9/23〜・36日）", "自分の記録CSVを読み込む"], horizontal=True, key="s_src")
    comp = None
    if src_c.startswith("自分"):
        st.caption("列：`日付,堆肥温度_C,気温_C,切り返し`（切り返した日は1）。棒温度計を中心に差して、毎朝同じ時刻に測る。")
        upc = st.file_uploader("温度の記録CSV", type="csv", key="s_up")
        if upc is not None:
            comp = sg.read_csv_safely(upc, page="microbe", kind="compost")
            if comp is not None and not {"日付", "堆肥温度_C", "気温_C", "切り返し"} <= set(comp.columns):
                st.error("列 `日付,堆肥温度_C,気温_C,切り返し` が必要です。")
                comp = None
    else:
        comp = mb.sample_compost()
        st.caption("表示しているのは**架空の温度**です。実際の記録が取れたらCSVで差しかえます。")
    if comp is not None:
        h1, h2 = st.columns(2)
        hot = h1.slider("「熱すぎ」の境目(℃)", 50, 75, 65, key="s_hot")
        active = h2.slider("「発酵中」とみなす気温との差(℃)", 3, 20, 10, key="s_act")
        fl = mb.compost_flags(comp, hot=hot, active=active)
        colors = {"🔥 熱すぎ": "#b91c1c", "🟠 発酵中": "#ea580c", "🟢 熟成に近い": "#15803d", "⚪ 静か（水分・空気を確かめる）": "#94a3b8"}
        fig_c = go.Figure()
        fig_c.add_trace(go.Scatter(x=fl["日付"], y=fl["気温_C"], name="気温", line=dict(color="#94a3b8", dash="dot")))
        fig_c.add_trace(go.Scatter(x=fl["日付"], y=fl["堆肥温度_C"], name="堆肥の温度", mode="lines+markers",
                                   line=dict(color="#78350f"), marker=dict(size=9, color=[colors.get(s, "#000") for s in fl["判定"]]),
                                   text=fl["判定"], hovertemplate="%{x}<br>%{y}℃<br>%{text}<extra></extra>"))
        for d in fl.loc[fl["切り返し"] == 1, "日付"]:
            fig_c.add_vline(x=d, line_dash="dash", line_color="#0369a1")
        fig_c.add_hline(y=hot, line_dash="dot", line_color="#b91c1c", annotation_text="熱すぎ")
        fig_c.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="℃", legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_c, width="stretch")
        st.caption("青い破線＝切り返し。切り返すと空気が入り、微生物が再び働いて温度が上がる。回を重ねると上がり方が小さくなる＝餌が減ってきた。")
        vc = fl["判定"].value_counts()
        st.markdown("　".join(f"{k}：{v} 日" for k, v in vc.items()))
        last = fl.iloc[-1]
        st.markdown("**③ 判断する：次にすること**")
        nxt = {"🔥 熱すぎ": "切り返して熱を逃がす。乾いていれば水を足す（アンモニア臭が強ければ炭素材を足す）。",
               "🟠 発酵中": "そのまま。温度が下がり始めたら切り返しの合図。",
               "🟢 熟成に近い": "匂い（甘酸っぱい・土の匂い）と見た目（白い菌糸・パラパラ）を確かめ、日陰で乾かして保存。",
               "⚪ 静か（水分・空気を確かめる）": "握って水分を確かめる。乾いていれば水、べたつけば乾いた材料。切り返して空気を入れる。"}
        st.info(f"最新（{last['日付']}・{last['堆肥温度_C']}℃・気温との差 {last['気温との差']:.1f}℃）は **{last['判定']}** → {nxt.get(last['判定'], '')}")
        st.caption("AIエージェントにするなら：温度センサー（毎時）→ この判定 → スマホに「切り返しの合図」を送る。"
                   "発展：切り返しの時期を、温度の推移と作業の手間から学ぶ（強化学習の題材。報酬＝早く熟成・臭いが出ない・手間が少ない）。")
        n_turn = int(fl["切り返し"].sum())
        report["🌾 発酵肥料"] = (
            f"観測：配合の C/N は {cn:.1f}・水分 {res['水分%']:.0f}%（目安の値で計算）。温度の記録 {len(fl)} 日のうち、熱すぎ {int(vc.get('🔥 熱すぎ', 0))} 日・発酵中 {int(vc.get('🟠 発酵中', 0))} 日、切り返し {n_turn} 回。\n"
            "解釈：切り返しのたびに温度が上がり、その山が小さくなっていく＝空気で微生物が働き直し、分解できる餌が減っている。最新の判定は「" + last["判定"] + "」。\n"
            "限界：材料の C/N・水分は目安、判定の境目は仮置き。温度は1点・1日1回の測定で、山の中心と外側では違う。")

# ============================================================
# 🔬 微生物検査
# ============================================================
with tab_q:
    st.subheader("🔬 微生物を数える：食品の一般生菌数と、化粧品の保存効力試験")
    st.caption("1gに何個の菌がいるかは、薄めて（段階希釈）寒天培地に広げ、育った集落（コロニー）を数えて逆算する。"
               "数え方（どの平板を使うか）で答えが変わるので、方法を必ず書き添える。")
    st.markdown("**① 段階希釈の平板法：CFU/g を3つの方法で出す**")
    q1, q2 = st.columns([3, 2])
    with q1:
        plates = st.data_editor(mb.SAMPLE_PLATES, num_rows="dynamic", hide_index=True, width="stretch", key="q_plates",
                                column_config={"集落数": st.column_config.NumberColumn(min_value=0, max_value=9999, step=1,
                                                                                    help="数えきれない平板は 999 と入れる")})
        lo, hi = st.slider("数える平板の範囲（集落数）", 1, 500, (30, 300), key="q_range")
    plates = plates.dropna()
    if len(plates):
        s_res = mb.cfu_simple(plates, lo, hi)
        w_res = mb.cfu_weighted(plates, lo, hi)
        b_res = mb.cfu_bayes(plates, upper=hi)
        with q2:
            st.metric("素朴な方法（範囲内の平板の平均）", f"{s_res['CFU/g']:,.0f} CFU/g" if not math.isnan(s_res["CFU/g"]) else "—",
                      help=f"使った平板 {s_res['使った平板']} 枚")
            st.metric("重みつきの式（連続2段）", f"{w_res['CFU/g']:,.0f} CFU/g" if not math.isnan(w_res["CFU/g"]) else "—",
                      help="N = ΣC ÷ (V × (n1 + 0.1·n2) × d)。ISO 7218 の考え方")
            if not math.isnan(b_res.get("中央値", float("nan"))):
                st.metric("ベイズ（ポアソン × ガンマ）", f"{b_res['中央値']:,.0f} CFU/g",
                          help=f"95%区間 {b_res['下限']:,.0f}〜{b_res['上限']:,.0f}。範囲の下限未満の平板も使う")
        if "samples" in b_res:
            fig_b = px.histogram(pd.DataFrame({"CFU/g": b_res["samples"]}), x="CFU/g", nbins=60, color_discrete_sequence=["#0369a1"])
            for v, lab in [(s_res["CFU/g"], "素朴"), (w_res["CFU/g"], "重みつき")]:
                if not math.isnan(v):
                    fig_b.add_vline(x=v, line_dash="dot", annotation_text=lab)
            fig_b.update_layout(height=240, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="サンプル数")
            st.plotly_chart(fig_b, width="stretch")
            st.caption("💡 **インサイト**：素朴な平均は、集落が少ない（ばらつきの大きい）薄い平板にも同じ重みを置くので高めに出る。"
                       "重みつきの式はベイズの事後平均（全平板の集落の合計 ÷ 全平板の「g換算の量」の合計）とほぼ同じで、"
                       "ベイズは**区間**も出してくれる。30未満の平板も、捨てずに情報として使えます。")
            st.latex(r"C_i \sim \text{Poisson}\!\left(N \cdot \frac{V_i}{\text{希釈倍率}_i}\right),\quad "
                     r"N \sim \text{Gamma}(a_0, b_0) \Rightarrow N \mid C \sim \text{Gamma}\!\left(a_0+\sum C_i,\; b_0+\sum \frac{V_i}{\text{希釈倍率}_i}\right)")
        with st.expander("✅ トレース表：範囲内の平板だけを足す for文（DNCL）"):
            st.dataframe(mb.cfu_trace(plates, lo, hi), hide_index=True, width="stretch")
            st.code(f"合計 = 0,  枚数 = 0\ni を 0 から 要素数(集落数)-1 まで 1 ずつ増やしながら繰り返す:\n"
                    f"│ もし {lo} ≦ 集落数[i] かつ 集落数[i] ≦ {hi} ならば:\n"
                    "│ │ 合計 = 合計 + 集落数[i] × 希釈倍率[i] ÷ 塗抹量[i]\n"
                    "│ └ 枚数 = 枚数 + 1\n表示する(合計 ÷ 枚数)", language="text")
            st.caption("最後の行の「合計 ÷ 使った枚数」が、上の「素朴な方法」と一致します。28 は 30 未満なので足されません。")
        report["🔬 検査"] = (
            f"観測：段階希釈 {len(plates)} 枚から、素朴な平均 {s_res['CFU/g']:,.0f}・重みつきの式 {w_res['CFU/g']:,.0f}・ベイズの中央値 "
            f"{b_res.get('中央値', float('nan')):,.0f} CFU/g（95%区間 {b_res.get('下限', float('nan')):,.0f}〜{b_res.get('上限', float('nan')):,.0f}）。\n"
            "解釈：同じ平板でも数え方で約1割違う。重みつきの式とベイズはほぼ一致し、薄い平板の偶然のばらつきに引っぱられにくい。\n"
            "限界：教材用の架空の数。実際の検査は公定法・指針の手順（培地・温度・時間）に従い、基準値との比較は検査機関の結果で行う。")

    st.markdown("**② 保存効力試験（チャレンジテスト）：防腐の力で、入った菌が減っていくか**")
    st.caption("化粧水などにわざと菌を入れ、7・14・28日後に数える。使っているあいだに指や空気から入る菌を、処方が抑えられるかを確かめる。")
    ch = st.data_editor(mb.SAMPLE_CHALLENGE, num_rows="dynamic", hide_index=True, width="stretch", key="q_ch")
    with st.expander("判定の基準（日ごとに必要な log の減少）を変える"):
        crit_df = pd.DataFrame([{"菌": k, **{f"{d}日": v for d, v in c.items()}} for k, c in mb.CRITERIA_A.items()])
        crit_ed = st.data_editor(crit_df, hide_index=True, width="stretch", key="q_crit", disabled=["菌"])
        st.caption("初期値は ISO 11930 の判定基準Aの考え方（細菌は7日で3 log＝1000分の1）。"
                   "**正式な判定は、原典・社内基準で必ず確かめてください。** 前の時点から 0.5 log を超えて増えたら「増えた」とします。")
    crit = {r["菌"]: {7: r["7日"], 14: r["14日"], 28: r["28日"]} for r in crit_ed.to_dict("records")}
    ch = ch.dropna()
    if len(ch):
        jd = mb.challenge_judge(ch, crit)
        st.dataframe(jd, hide_index=True, width="stretch")
        lg = ch.melt(id_vars=["処方", "菌"], value_vars=["0日", "7日", "14日", "28日"], var_name="日", value_name="log10 CFU/g")
        lg["日数"] = lg["日"].str.replace("日", "").astype(int)
        fig_ch = px.line(lg, x="日数", y="log10 CFU/g", color="菌", line_dash="処方", markers=True,
                         color_discrete_map={"細菌": C_C, "酵母": C_Y, "カビ": "#15803d"})
        fig_ch.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_ch, width="stretch")
        st.caption("縦軸は log（1目盛り＝10倍）。細菌が 6 → 2.4 は「3.6 log の減少」＝約4000分の1。"
                   "防腐剤なしの処方では菌が増えていく：**手づくり化粧品を人に配る前に、なぜ試験が要るのか**がわかる。")
        bad = jd[jd["判定"].str.startswith("❌")]
        if len(bad):
            st.warning("不適合：" + "、".join(f"{a}の{b}" for a, b in bad[["処方", "菌"]].itertuples(index=False)))

    st.markdown("**③ 判断する：出荷・配布の前に、何を確かめるか**")
    st.markdown(
        "| 段 | 食品（パン・加工品） | 化粧品（化粧水など） |\n|---|---|---|\n"
        "| つくる前 | 原料の受け入れ・保管温度 | 防腐の設計（処方）・保存効力試験 |\n"
        "| つくる間 | 手洗い・器具の洗浄消毒・加熱の温度と時間の記録 | 製造環境の衛生管理（拭き取り・落下菌） |\n"
        "| 出す前 | 一般生菌数・大腸菌群など（検査機関） | 製品試験（菌数・特定の菌がいないこと） |\n"
        "| 出した後 | 苦情の記録・保存サンプル | 汚染事故の対応手順（回収・原因の特定） |"
    )
    st.caption("記録が残っていれば、事故のときに「どこで入ったか」を遡れる（PL法・自主的衛生管理）。"
               "記録の数字は、このページの計算でそのまま確かめられる形（CSV）で残すのが近道です。")

# ============================================================
# 📝 3行の報告
# ============================================================
st.divider()
st.header("📝 3行で報告する：観測／解釈と根拠／限界")
if report:
    pick = st.selectbox("報告するタブ", list(report), key="rep_pick")
    txt = st.text_area("下書き（自分の言葉に書きかえる）", report[pick], height=150, key=f"rep_{pick}")
    st.download_button("3行の報告を保存（.txt）", txt.encode("utf-8"), f"3行報告_微生物_{pick[2:]}.txt", "text/plain")
    st.caption("観測＝数えた・計算した事実（単位つき）。解釈＝意味の読み取り。限界＝モデルの単純化・仮置きの値・測り方の偏り。")
else:
    st.info("各タブで計算すると、ここに下書きが出ます。")

st.caption("© スマートパン屋農家プロジェクト ｜ 初期表示は教材用の架空データです。値の目安・判定の基準は原典・公定法で確かめてください。")

"""
共通テスト×情報Ⅰ ─ 共通テスト『理科』（基礎4科目）を、情報Ⅰの道具で解いて確かめる
配置先: pages/18_📝_共通テスト理科×情報Ⅰ.py （Streamlit のマルチページ構成）

各大問の流れ（頭の中の説明で終わらせず、手を動かして確かめる）
  問題（共通テストの形式にならったオリジナル）→ 解答を選ぶ → 正答の根拠を情報Ⅰの思考ツールで解説
  → ② Python で条件を変えて確かめる → ③ DNCL のコードとトレース表 → 発展課題・発問例
  最後に 学習チェックリスト・頻出用語ミニ辞典

計算は kyotsu_rika.py（`python kyotsu_rika.py` で手計算との自己チェック）。
問題文はすべてオリジナルで、過去問の転載ではありません。数値は教育用の目安です。
"""
import math

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import kyotsu_rika as kr

st.set_page_config(page_title="共通テスト『理科』を情報Ⅰで解く", page_icon="📝", layout="wide")

st.title("📝 共通テスト『理科』を情報Ⅰで解く")
st.caption("理科の公式は、手順にすると「繰り返し・条件分岐・配列の探索」になる ── 畑とパン屋の題材で、基礎4科目を解いて確かめる")

TOOLS = {
    "🧩 モデル化とシミュレーション": "現象を式やルールに置きかえ、条件を変えて試す（オイラー法・乱数）",
    "🔁 アルゴリズム（DNCL・トレース表）": "手順を DNCL に書き、変数の値を1行ずつ追って確かめる",
    "📊 データの活用": "表から値を読む・補間する・期待値とずれを比べる（χ²）",
    "🎨 情報デザイン": "グラフの軸・目盛り（log・pH）を選び、伝わる形にする",
}
with st.container(border=True):
    st.markdown("**情報Ⅰの4つの思考ツール** ── 各大問の解説で、正答の根拠をどのツールで確かめたかを示します")
    cols = st.columns(4)
    for c, (k, v) in zip(cols, TOOLS.items()):
        c.markdown(f"**{k}**")
        c.caption(v)

with st.expander("このページの使い方（授業・自習）", expanded=False):
    st.markdown(
        "| 段 | すること | 目安 |\n|---|---|---|\n"
        "| 1 解く | 問題を読み、選択肢を選ぶ（まず手計算） | 5分 |\n"
        "| 2 根拠 | 解説で、正答の根拠と使った思考ツールを確かめる | 3分 |\n"
        "| 3 動かす | ② で条件を変え、答えがどう変わるかを見る（「もし〜なら？」） | 5分 |\n"
        "| 4 追う | ③ の DNCL を読み、トレース表の値を自分で1行書いてから表と比べる | 7分 |\n"
        "| 5 広げる | 発展課題・発問例を1つ選んで、ノートに答える | 5分 |\n\n"
        "問題文はこのリポジトリのオリジナル（共通テストの形式にならったもの）です。数値は教育用の目安で、"
        "正式な値は教科書・理科年表で確かめてください。"
    )


def choice(qid: str, prompt: str, options: list[str], answer: int, explain: str, tools: list[str]) -> bool:
    """選択式の問題。答えを選ぶまで解説は出さない。"""
    st.markdown(f"**{prompt}**")
    pick = st.radio("解答", options, index=None, key=f"q_{qid}", horizontal=True, label_visibility="collapsed",
                    format_func=lambda o: f"{'①②③④⑤⑥'[options.index(o)]} {o}")
    if pick is None:
        st.caption("選ぶと、正誤と解説が出ます。")
        return False
    ok = options.index(pick) == answer
    (st.success if ok else st.error)(f"{'正解' if ok else '不正解'}：正答は {'①②③④⑤⑥'[answer]} {options[answer]}")
    st.markdown(explain)
    st.caption("使った思考ツール：" + "／".join(tools))
    st.session_state.setdefault("scores", {})[qid] = ok
    return ok


tab_e, tab_c, tab_p, tab_b, tab_x = st.tabs(
    ["🌫️ 地学基礎：ハウスの結露", "🧪 化学基礎：土の酸度と中和", "🍞 物理基礎：仕込み水とパンの冷め方",
     "🌾 生物基礎：小麦の遺伝", "✅ チェックリスト・用語辞典"])

# ============================================================
# 地学基礎
# ============================================================
with tab_e:
    st.header("第1問（地学基礎）ハウスの中の水滴はどこから来るか")
    st.markdown(
        "秋の晴れた日、育苗ハウスの中の空気は昼に **25℃・湿度60%** だった。夜にハウスの中が **10℃** まで冷えると、"
        "天井のビニールに水滴がつき、苗に落ちていた。下の表は温度と飽和水蒸気量の関係である。"
    )
    st.dataframe(pd.DataFrame({"温度(℃)": kr.SAT_T, "飽和水蒸気量(g/m³)": kr.SAT_V}).set_index("温度(℃)").T, width="stretch")
    choice("e1", "問1　夜に空気1m³あたりで水滴になる水蒸気の量として、最も適当なものを選べ。",
           ["2.4 g", "4.5 g", "9.4 g", "13.9 g"], 1,
           "**根拠**：昼の空気1m³の水蒸気量 = 23.1 × 0.60 = **13.86 g**。10℃ で空気が持てるのは 9.4 g まで。"
           "持ちきれない 13.86 − 9.4 = **4.46 g ≒ 4.5 g** が水滴になる。③は10℃の飽和水蒸気量、④は昼の水蒸気量そのものを選んだ誤り。",
           ["📊 データの活用（表を読む）"])
    choice("e2", "問2　この空気の露点として、最も適当なものを選べ。",
           ["約 10℃", "約 13℃", "約 16℃", "約 20℃"], 2,
           "**根拠**：13.86 g は 15℃(12.8 g) と 20℃(17.3 g) のあいだ。あいだを直線とみなすと "
           "15 + 5 × (13.86 − 12.8) ÷ (17.3 − 12.8) = **16.2℃**。表を小さい方から順に調べ、"
           "「はじめて 13.86 を超える」ところで止まる手順は、**配列の探索**そのもの。",
           ["📊 データの活用（線形補間）", "🔁 アルゴリズム（配列の探索）"])

    st.subheader("② 条件を変えて確かめる")
    a1, a2, a3 = st.columns(3)
    td = a1.slider("昼の温度(℃)", 5, 35, 25, key="e_td")
    hd = a2.slider("昼の湿度(%)", 10, 100, 60, key="e_hd")
    tn = a3.slider("夜の温度(℃)", 0, 30, 10, key="e_tn")
    cd = kr.condensation(td, hd, tn)
    m1, m2, m3 = st.columns(3)
    m1.metric("昼の水蒸気量", f"{cd['水蒸気量']:.2f} g/m³")
    m2.metric("露点", f"{cd['露点']:.1f} ℃")
    m3.metric("夜に水滴になる量", f"{cd['結露する水']:.2f} g/m³", help="ハウスの体積を掛けると全体の量になる")
    TT = np.linspace(0, 35, 141)
    fig = go.Figure(go.Scatter(x=TT, y=[kr.sat_vapor(t) for t in TT], name="飽和水蒸気量", line=dict(color="#0369a1")))
    fig.add_trace(go.Scatter(x=kr.SAT_T, y=kr.SAT_V, mode="markers", name="表の値", marker=dict(color="#0369a1", size=8)))
    fig.add_trace(go.Scatter(x=[td, cd["露点"], tn], y=[cd["水蒸気量"], cd["水蒸気量"], kr.sat_vapor(tn)],
                             mode="lines+markers", name="空気の変化", line=dict(color="#c2410c", dash="dot")))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="温度(℃)", yaxis_title="g/m³")
    st.plotly_chart(fig, width="stretch")
    st.caption("空気が冷えると左へ動き、曲線にぶつかった温度が露点。そこからは曲線にそって下がり、差が水滴になる。")
    vol = st.number_input("ハウスの体積(m³)（間口6m×奥行20m×平均高さ2.5mなら300）", 10, 5000, 300, key="e_vol")
    st.info(f"このハウス全体では、一晩で約 **{cd['結露する水'] * vol / 1000:.2f} L** の水滴ができる見込み。"
            "→ 夕方に換気して水蒸気を外に出す・暖房で露点より下げない、が対策（苗の病気の予防）。")

    st.subheader("③ DNCL で露点を探す（トレース表）")
    dpt, trd = kr.dew_point_trace(cd["水蒸気量"])
    c1, c2 = st.columns([2, 3])
    c1.code("T = [0, 5, 10, 15, 20, 25, 30, 35]\nV = [4.8, 6.8, 9.4, 12.8, 17.3, 23.1, 30.4, 39.6]\n"
            f"x = {cd['水蒸気量']:.2f}\ni = 0\n"
            "i < 要素数(V) − 2 かつ V[i+1] < x の間、繰り返す:\n└ i = i + 1\n"
            "露点 = T[i] + (T[i+1] − T[i]) × (x − V[i]) ÷ (V[i+1] − V[i])\n表示する(露点)", language="text")
    c2.dataframe(trd, hide_index=True, width="stretch")
    c2.caption(f"止まったところの2点で補間して、露点 {dpt:.2f}℃。繰り返しの条件を「V[i] < x」と書くと、1つずれた2点で補間してしまう（よくある誤り）。")
    with st.expander("発展課題・発問例"):
        st.markdown(
            "- **発展**：表を1℃刻みにすると露点はどれだけ変わるか。刻みを細かくする利点と、表を作る手間を比べよう。\n"
            "- **発問**：同じ湿度60%でも、昼が30℃の日のほうが水滴が多いのはなぜか。曲線の形（上に反っている）で説明しよう。\n"
            "- **発問**：霜（地面付近の水蒸気が氷になる）が降りやすいのは、晴れて風の弱い夜である。理由を放射冷却と露点で説明しよう。"
        )

# ============================================================
# 化学基礎
# ============================================================
with tab_c:
    st.header("第2問（化学基礎）酸性になった畑の土を中和する")
    st.markdown(
        "雨が多いと、土は酸性に傾く。土の酸の量を調べるため、土の抽出液を想定した **0.050 mol/L の硫酸 10 mL** を、"
        "**0.10 mol/L の水酸化ナトリウム水溶液**で中和する実験を考える。"
    )
    choice("c1", "問1　中和に必要な水酸化ナトリウム水溶液の体積として、最も適当なものを選べ。",
           ["2.5 mL", "5.0 mL", "10 mL", "20 mL"], 2,
           "**根拠**：硫酸 H₂SO₄ は **2価**の酸。出す H⁺ = 2 × 0.050 × 10/1000 = 1.0×10⁻³ mol。"
           "NaOH は1価なので、0.10 × V/1000 = 1.0×10⁻³ → **V = 10 mL**。②は「2価」を見落とした誤り。"
           "（価数 × 濃度 × 体積）が等しい、という1つの式で、塩酸でも硫酸でも同じ手順で解ける。",
           ["🧩 モデル化（物質量の保存）"])
    choice("c2", "問2　水酸化ナトリウム水溶液を少しずつ加えたときの pH の変わり方として、最も適当なものを選べ。",
           ["加えた量に比例して、まっすぐ上がる", "はじめはほとんど変わらず、中和点の近くで急に上がる",
            "はじめに急に上がり、その後はほとんど変わらない", "中和点でいちばん高くなり、その後は下がる"], 1,
           "**根拠**：pH は H⁺ の濃度の **log（対数）**。H⁺ が 1/10 になって、やっと pH が1上がる。"
           "はじめは H⁺ がたくさん残っているので少し減っても pH は動かず、残りがわずかになる中和点の近くで急に跳ね上がる。"
           "②で滴定曲線を描いて確かめよう。",
           ["🎨 情報デザイン（log の目盛り）", "🧩 シミュレーション（繰り返しで曲線を描く）"])

    st.subheader("② 条件を変えて滴定曲線を描く")
    b1, b2, b3, b4 = st.columns(4)
    acid = b1.radio("酸", ["硫酸（2価）", "塩酸（1価）"], key="c_acid")
    ca = b2.number_input("酸の濃度(mol/L)", 0.001, 1.0, 0.050, 0.005, format="%.3f", key="c_ca")
    va = b3.number_input("酸の体積(mL)", 1.0, 100.0, 10.0, 1.0, key="c_va")
    cb = b4.number_input("NaOH の濃度(mol/L)", 0.001, 1.0, 0.10, 0.01, format="%.3f", key="c_cb")
    val = 2 if acid.startswith("硫酸") else 1
    eq = kr.equivalence_ml(ca, va, cb, valence_a=val)
    step = st.select_slider("1回に加える量(mL)", [2.0, 1.0, 0.5, 0.1], value=0.5, key="c_step")
    tt = kr.titration(ca, va, cb, step, eq * 2, valence_a=val)
    fig_t = px.line(tt, x="加えた量_mL", y="pH", markers=step >= 0.5)
    fig_t.add_vline(x=eq, line_dash="dot", annotation_text=f"中和点 {eq:.2f} mL")
    fig_t.add_hrect(y0=8.0, y1=9.8, fillcolor="#f472b6", opacity=0.12, line_width=0, annotation_text="フェノールフタレインの変色域")
    fig_t.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), yaxis_range=[0, 14])
    st.plotly_chart(fig_t, width="stretch")
    st.caption("1回に加える量を大きくすると、中和点の急な跳ね上がりを見のがす。データを取る間隔の選び方も、情報Ⅰの「データの収集」の問題。")

    st.markdown("**畑に当てはめる：苦土石灰（炭酸カルシウム）をどれだけまくか**")
    d1, d2, d3 = st.columns(3)
    acid_amt = d1.number_input("土の酸の量（mmol H⁺ / 土100 g）", 0.1, 20.0, 2.0, 0.1, key="c_soil",
                               help="測定値の目安を入れる。土壌診断の結果があれば、その値に置きかえる")
    soil = d2.number_input("中和したい土の量(kg)", 1.0, 100000.0, 150.0, 10.0, key="c_kg",
                           help="1m²・深さ10cm の土は約 100〜150 kg")
    purity = d3.slider("資材の CaCO₃ の割合", 0.5, 1.0, 0.95, 0.05, key="c_pur")
    lm = kr.lime_for_soil(acid_amt, soil, purity)
    st.success(f"中和する H⁺ は {lm['H⁺_mol']:.2f} mol → CaCO₃ は {lm['CaCO3_g']:.0f} g（CaCO₃ 1 mol = 100 g が H⁺ 2 mol を中和）"
               f" → 資材として約 **{lm['資材_g']:.0f} g**。")
    st.caption("実際の施用量は、土の緩衝能（酸を抱え込む力）や作物の好む pH で変わる。土壌診断と資材の袋の表示に従います。")

    st.subheader("③ DNCL で滴定曲線を描く（トレース表）")
    c1, c2 = st.columns([2, 3])
    c1.code(f"H = {val} × {ca} × {va} ÷ 1000      # 酸が出す H⁺ [mol]\nv = 0\n"
            f"v ≦ {eq * 2:g} の間、繰り返す:\n"
            f"│ OH = {cb} × v ÷ 1000\n│ 全体 = ({va} + v) ÷ 1000\n"
            "│ もし H > OH ならば:\n│ │ pH = −log10((H − OH) ÷ 全体)\n"
            "│ そうでなくもし H = OH ならば:\n│ │ pH = 7\n│ そうでなければ:\n│ └ pH = 14 + log10((OH − H) ÷ 全体)\n"
            f"│ 表示する(v, pH)\n└ v = v + {step}", language="text")
    show = tt[(tt["加えた量_mL"] >= eq - 3 * step) & (tt["加えた量_mL"] <= eq + 3 * step)]
    c2.dataframe(show, hide_index=True, width="stretch")
    c2.caption("中和点の前後だけを抜き出したトレース表。わずかな量で pH が大きく動くのがわかる。")
    with st.expander("発展課題・発問例"):
        st.markdown(
            "- **発展**：酢酸（弱酸）を中和すると、はじめの pH や中和点の pH はどう変わるか。電離度を考えてモデルを直してみよう。\n"
            "- **発問**：石灰をまきすぎると、作物にどんな困りごとが起きるか（アルカリ性・微量要素の吸収）。\n"
            "- **発問**：雨がなぜ土を酸性にするのか。雨水に溶ける二酸化炭素と、土から流れ出る陽イオンで説明しよう。"
        )

# ============================================================
# 物理基礎
# ============================================================
with tab_p:
    st.header("第3問（物理基礎）仕込み水の温度と、焼き上がったパンの冷め方")
    st.markdown(
        "パン生地をこねるとき、生地の温度をそろえるため、**60℃の湯 200 g** と **15℃の水**を混ぜて **30℃の仕込み水**をつくる。"
        "熱は外に逃げないものとし、水の比熱は 4.2 J/(g·K) とする。"
    )
    choice("p1", "問1　混ぜる 15℃ の水の質量として、最も適当なものを選べ。",
           ["100 g", "200 g", "400 g", "600 g"], 2,
           "**根拠**：湯が失う熱 = 水が得る熱。4.2 × 200 × (60 − 30) = 4.2 × m × (30 − 15) → **m = 400 g**。"
           "比熱は両辺で同じなので消える。「温度差の比 30:15 = 2:1 の逆の比で質量が決まる」と見てもよい（てこと同じ形）。",
           ["🧩 モデル化（熱量の保存）"])
    st.markdown(
        "焼き上がったパン（95℃）を室温22℃の部屋に置く。パンの温度 T は、室温との差に比例する速さで下がる"
        "（ニュートンの冷却：dT/dt = −k(T − 室温)、k = 0.040 /分 とする）。"
    )
    choice("p2", "問2　パンの温度が、室温との差が半分（58.5℃）になるまでの時間として、最も適当なものを選べ。",
           ["約 9 分", "約 17 分", "約 25 分", "約 35 分"], 1,
           "**根拠**：差は e^(−kt) 倍になる。半分になる時間は ln2 ÷ k = 0.693 ÷ 0.040 = **17.3 分**。"
           "差が半分になる時間は、はじめの温度に関係なく一定（放射性物質の半減期と同じ形）。"
           "式を知らなくても、③のオイラー法で1分ずつ計算すれば同じ答えに近づく。",
           ["🧩 シミュレーション（オイラー法）", "🔁 アルゴリズム（繰り返し）"])

    st.subheader("② 条件を変えて確かめる")
    p1, p2, p3, p4 = st.columns(4)
    t0 = p1.slider("焼き上がりの温度(℃)", 70, 100, 95, key="p_t0")
    ta = p2.slider("室温(℃)", 0, 35, 22, key="p_ta")
    k = p3.slider("冷めやすさ k(/分)", 0.01, 0.15, 0.04, 0.005, key="p_k",
                  help="小さいパン・網の上・風があると大きい。大きな食パン・型の中だと小さい")
    target = p4.slider("切ってよい温度(℃)", 25, 60, 40, key="p_target")
    dt = st.select_slider("オイラー法の1歩 Δt(分)", [10.0, 5.0, 2.0, 1.0, 0.5], value=5.0, key="p_dt")
    ce = kr.cooling_euler(t0, ta, k, dt, 90)
    fig_p = go.Figure()
    tt2 = np.linspace(0, 90, 181)
    fig_p.add_trace(go.Scatter(x=tt2, y=kr.cooling_exact(tt2, t0, ta, k), name="式", line=dict(color="#c2410c")))
    fig_p.add_trace(go.Scatter(x=ce["t_分"], y=ce["T（オイラー法）"], name=f"オイラー法（Δt={dt:g}分）",
                               mode="lines+markers", line=dict(color="#0369a1", dash="dot")))
    fig_p.add_hline(y=target, line_dash="dash", line_color="#15803d", annotation_text="切ってよい")
    fig_p.add_hline(y=ta, line_dash="dot", line_color="#94a3b8", annotation_text="室温")
    fig_p.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="分", yaxis_title="℃")
    st.plotly_chart(fig_p, width="stretch")
    need = kr.time_to_reach(target, t0, ta, k)
    q1, q2 = st.columns(2)
    q1.metric(f"{target}℃ まで", f"{need:.0f} 分" if not math.isnan(need) else "届かない",
              help="室温より低い温度には、置いておくだけでは届かない")
    q2.metric("オイラー法のいちばん大きい誤差", f"{ce['誤差'].abs().max():.2f} ℃")
    st.caption("Δt を小さくするほど、点線が式に近づく。冬（室温が低い）は早く冷めるので、出荷の段取りを季節で変える根拠になる。")

    st.subheader("③ DNCL で冷め方を計算する（トレース表）")
    c1, c2 = st.columns([2, 3])
    c1.code(f"T = {t0}\n室温 = {ta}\nk = {k}\nΔt = {dt:g}\n分 = 0\n"
            f"T > {target} の間、繰り返す:\n│ T = T − Δt × k × (T − 室温)\n└ 分 = 分 + Δt\n表示する(分)", language="text")
    c2.dataframe(ce.head(12), hide_index=True, width="stretch")
    reach = ce[ce["T（オイラー法）"] <= target]
    c2.caption(f"オイラー法で {target}℃ 以下になるのは "
               + (f"{reach['t_分'].iloc[0]:g} 分（式では {need:.1f} 分）。" if len(reach) else "90分より後。")
               + "Δt の刻みでしか止まれないので、少し遅めに出る。")
    with st.expander("発展課題・発問例"):
        st.markdown(
            "- **発展**：パンの質量を2倍にすると k はどう変わると考えられるか（表面積と体積の比）。仮説を立てて記録で確かめよう。\n"
            "- **発問**：問1で、実際には容器や空気に熱が逃げる。そのとき 15℃ の水は 400 g より多く要るか、少なくて済むか。\n"
            "- **発問**：石窯の石を厚くすると、温まるのに時間がかかるが冷めにくい。比熱と質量（熱容量）で説明しよう。"
        )

# ============================================================
# 生物基礎（生物）
# ============================================================
with tab_b:
    st.header("第4問（生物）パン用小麦の2つの形質の遺伝")
    st.markdown(
        "小麦の2つの形質を、それぞれ1対の遺伝子が決めるとする（説明のための単純化）。"
        "穂が長い **A** は短い **a** に、のぎ（穂の先の毛）がある **B** はない **b** に対して顕性で、"
        "2つの遺伝子は別々の染色体にある。AaBb どうしを交配して、子を **160個体** 得た。"
    )
    choice("b1", "問1　穂が短く、のぎがない（aabb）個体の数として、最も期待されるものを選べ。",
           ["10 個体", "30 個体", "40 個体", "90 個体"], 0,
           "**根拠**：aa になる確率 1/4、bb になる確率 1/4。別々の染色体なので**掛け算**して 1/16。"
           "160 × 1/16 = **10 個体**。表現型の比は 9:3:3:1 で、②は「穂が短く、のぎあり」（3/16）の数。",
           ["🧩 モデル化（確率の積）"])
    choice("b2", "問2　実際に数えると aabb が 5 個体だった。このずれについて、最も適当な考え方を選べ。",
           ["理論が間違っているので、比は 9:3:3:1 ではない", "数が少ないと偶然のずれが出るので、すぐに理論を否定できない",
            "数え間違いなので、数え直せば必ず 10 個体になる", "ずれは環境の影響なので、遺伝とは関係がない"], 1,
           "**根拠**：160 個体くらいでは、偶然のずれは珍しくない。②で乱数を使って何度も交配を再現すると、"
           "理論どおりでも 5 個体や 15 個体がしばしば出ることがわかる。ずれの大きさは **χ²（カイ二乗）** で測り、"
           "境目（自由度3・5%で 7.81）を超えたときに「理論と合わない」と考える。",
           ["🧩 シミュレーション（モンテカルロ法）", "📊 データの活用（期待値とずれ）"])

    st.subheader("② 乱数で交配を再現する（モンテカルロ法）")
    g1, g2, g3 = st.columns(3)
    genes = 2 if g1.radio("交配", ["AaBb × AaBb（2つの形質）", "Aa × Aa（1つの形質）"], key="b_g").startswith("AaBb") else 1
    n = g2.select_slider("子の数", [16, 40, 160, 1000, 10000], value=160, key="b_n")
    seed = g3.number_input("乱数の種", 0, 9999, 0, key="b_seed")
    sim = kr.cross_sim(int(n), int(seed), genes)
    rt = kr.ratio_table(sim, genes)
    chi = float(rt["(観測−期待)²/期待"].sum())
    dfree = len(rt) - 1
    r1, r2 = st.columns([3, 2])
    fig_b = go.Figure()
    fig_b.add_trace(go.Bar(x=rt["表現型"], y=rt["観測値"], name="観測（乱数）", marker_color="#15803d"))
    fig_b.add_trace(go.Bar(x=rt["表現型"], y=rt["期待値"], name="期待（理論）", marker_color="#cbd5e1"))
    fig_b.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), barmode="group")
    r1.plotly_chart(fig_b, width="stretch")
    r2.dataframe(rt, hide_index=True, width="stretch")
    r2.metric("χ²", f"{chi:.2f}", f"境目 {kr.CHI2_05[dfree]}（自由度{dfree}・5%）", delta_color="off")
    r2.caption("χ² が境目より小さければ「理論どおりでも起こりうるずれ」。")

    reps = st.slider("交配の実験を何回くり返すか", 50, 1000, 300, 50, key="b_reps")
    last = []
    for s in range(reps):
        t = kr.ratio_table(kr.cross_sim(160, 10000 + s, 2), 2)
        last.append(int(t.iloc[-1]["観測値"]))
    fig_h = px.histogram(pd.DataFrame({"aabb の数": last}), x="aabb の数", color_discrete_sequence=["#7c3aed"])
    fig_h.add_vline(x=10, line_dash="dot", annotation_text="期待値 10")
    fig_h.add_vline(x=5, line_dash="dash", line_color="#c2410c", annotation_text="観測 5")
    fig_h.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="実験の回数")
    st.plotly_chart(fig_h, width="stretch")
    share = np.mean(np.array(last) <= 5)
    st.info(f"理論どおり（1/16）でも、160個体の実験 {reps} 回のうち **{share:.0%}** で aabb が5個体以下になった。"
            "→ 問2で「すぐに理論を否定できない」根拠。")

    st.subheader("③ DNCL で交配を数える（トレース表）")
    c1, c2 = st.columns([2, 3])
    c1.code("顕性 = 0,  潜性 = 0\ni を 0 から 11 まで 1 ずつ増やしながら繰り返す:\n"
            "│ 父 = 乱数で 0 か 1   # 1 なら A\n│ 母 = 乱数で 0 か 1\n"
            "│ もし 父 + 母 ≧ 1 ならば:\n│ │ 顕性 = 顕性 + 1\n│ そうでなければ:\n│ └ 潜性 = 潜性 + 1\n"
            "表示する(顕性, 潜性)", language="text")
    c2.dataframe(kr.trace_cross(12, int(seed)), hide_index=True, width="stretch")
    c2.caption("Aa × Aa を12回。「父 + 母 ≧ 1」＝ A を1つでも持てば顕性。12回では 3:1 からずれることが多い。")
    with st.expander("発展課題・発問例"):
        st.markdown(
            "- **発展**：2つの遺伝子が同じ染色体の近くにある（連鎖している）と、比はどう変わるか。乱数の部分を直してモデル化しよう。\n"
            "- **発問**：実際の小麦は六倍体で、多くの形質は多数の遺伝子と環境で決まる。この問題の単純化は、どこまで現実に使えるか。\n"
            "- **発問**：品種改良で「穂が長く、のぎがない」小麦を固定するには、何世代かかりそうか。シミュレーションで確かめる方法を考えよう。"
        )

# ============================================================
# チェックリスト・用語辞典
# ============================================================
with tab_x:
    sc = st.session_state.get("scores", {})
    st.header("✅ 学習チェックリスト")
    st.metric("解いた問題", f"{len(sc)} / 8", f"正解 {sum(sc.values())} 問", delta_color="off")
    items = [
        ("地学", "表から飽和水蒸気量を読み、湿度・露点・結露する量を計算できる"),
        ("地学", "露点を「配列の探索＋線形補間」の手順として DNCL で書ける"),
        ("化学", "（価数 × 濃度 × 体積）の等式で、中和に要る量を求められる"),
        ("化学", "pH が log なので、中和点の近くで急に変わることを説明できる"),
        ("物理", "熱量の保存（熱平衡）の式を立て、混ぜる量を求められる"),
        ("物理", "冷却の式を、オイラー法の繰り返しで近似し、Δt と誤差の関係を説明できる"),
        ("生物", "独立な2つの遺伝子の分離比 9:3:3:1 を、確率の積から導ける"),
        ("生物", "乱数のシミュレーションと χ² で、観測のずれが偶然かを判断できる"),
    ]
    done = 0
    for i, (sub, txt) in enumerate(items):
        done += st.checkbox(f"【{sub}】{txt}", key=f"chk_{i}")
    st.progress(done / len(items), text=f"{done} / {len(items)} 項目")

    st.header("📖 頻出用語ミニ辞典")
    st.dataframe(pd.DataFrame([
        ("飽和水蒸気量", "地学", "空気1m³が含むことのできる水蒸気の最大量[g/m³]。温度が高いほど大きい", "配列（表）"),
        ("露点", "地学", "空気を冷やしたとき、水蒸気が水滴になり始める温度", "探索・補間"),
        ("物質量 mol", "化学", "粒子 6.02×10²³ 個を1 mol とする量。中和は H⁺ と OH⁻ の mol が等しいとき", "モデル化"),
        ("価数", "化学", "酸1分子が出せる H⁺ の数（硫酸は2）、塩基が出せる OH⁻ の数", "条件の見落とし"),
        ("pH", "化学", "−log10[H⁺]。1 上がると H⁺ は 1/10", "情報デザイン（log）"),
        ("比熱", "物理", "1 g を 1 K 上げるのに要る熱量[J/(g·K)]", "モデル化"),
        ("熱平衡", "物理", "接した物体の温度が等しくなった状態。失った熱 = 得た熱", "保存の式"),
        ("オイラー法", "情報Ⅰ", "変化の速さ × Δt を足していく近似計算。Δt が小さいほど正確", "シミュレーション"),
        ("顕性・潜性", "生物", "ヘテロ接合で現れる形質が顕性（以前の優性）、現れないほうが潜性（劣性）", "条件分岐"),
        ("モンテカルロ法", "情報Ⅰ", "乱数でくり返し試し、結果の分布から確率を見積もる方法", "シミュレーション"),
        ("χ²（カイ二乗）", "データ", "Σ(観測−期待)²/期待。ずれの大きさを1つの数にまとめる", "データの活用"),
        ("トレース表", "情報Ⅰ", "手順を1行ずつ実行したときの変数の値の表。誤りを見つける道具", "アルゴリズム"),
    ], columns=["用語", "分野", "意味", "情報Ⅰの道具"]), hide_index=True, width="stretch")
    st.caption("© スマートパン屋農家プロジェクト ｜ 問題文はオリジナル。数値は教育用の目安で、正式な値は教科書・理科年表で確かめてください。")

"""
高校の必履修科目「科学と人間生活」＝フィールドワーク事前学習
配置先: pages/27_🔭_科学と人間生活_FW事前学習.py （左メニュー「📝 教科×情報Ⅰ」）

ピボット：「科学と人間生活」は「総合的な探究の時間」におけるフィールドワークの事前学習として、
         極めて親和性が高く、非常に有益な科目である。

教科の先生向け。ホームの「⏱️ 学校の先生向け 3分コース」と同じ部品（teacher_course.py）を先頭に置いて連動させ、
その下で「科目の位置づけ → 単元と調査地の紐付け → 事前学習の1コマ（情報Ⅰ）→ PDCAの発展形」を扱う。
事前・本番・事後の伴走そのものは「🎓 学校向けの探究 › 🧭 フィールドワーク伴走」（pages/26）。

計算は kagaku_ningen_fw.py（`python kagaku_ningen_fw.py` で自己チェック）。入力はセッション内だけで使い、保存しない。
"""
import plotly.graph_objects as go
import streamlit as st

import fieldwork_pdca as fp
import kagaku_ningen_fw as kn
import sister_sites as ss
import teacher_course as tc

st.set_page_config(page_title="科学と人間生活＝フィールドワーク事前学習", page_icon="🔭", layout="wide")

UPDATED = "2026-11-06"

st.markdown(
    """
    <style>
    .hero {padding: 1.6rem 1.8rem 1.4rem; border-radius: 16px;
           background: linear-gradient(120deg, #e3efd6 0%, #e4ecf5 100%);
           color: #22313f; margin-bottom: 1rem;}
    .hero .eyebrow {font-size: .85rem; letter-spacing: .08em; color: #4a6a8a; margin: 0 0 .4rem 0;}
    .hero h1 {margin: 0 0 .6rem 0; font-size: 1.9rem; line-height: 1.35; color: #22313f;}
    .hero .lead {margin: 0; font-size: 1.05rem; line-height: 1.8;}
    .note {font-size: .85rem; color: #5a6a75;}
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    f"""
    <div class="hero">
      <p class="eyebrow">📝 教科×情報Ⅰ ・ 理科の先生向け</p>
      <h1>高校の必履修科目「科学と人間生活」＝フィールドワーク事前学習</h1>
      <p class="lead">{tc.PIVOT}<br>
      単元を「調査地の直前」に置き、授業の最後に<b>問いのブリッジ</b>を投げる。それだけで、現場で見える景色が変わります。</p>
    </div>
    """,
    unsafe_allow_html=True,
)

tabs = st.tabs(["⏱️ 3分コース", "📘 科目の位置づけ", "🔗 単元×調査地", "💻 事前学習の1コマ（情報Ⅰ）", "🔁 PDCAの発展形"])

# ═════════════════════════════════════════════
# ⏱️ 3分コース（ホームと共用）
# ═════════════════════════════════════════════
with tabs[0]:
    tc.render(where="subject")
    st.markdown("**このページの使い方**：① 科目の位置づけを確かめる → ② 調査地に合う単元を選ぶ → "
                "③ 事前学習の1コマ（計算・可視化・判断）を授業で行う → ④ 本番と事後は 🧭 フィールドワーク伴走 へ。")

# ═════════════════════════════════════════════
# 📘 科目の位置づけ
# ═════════════════════════════════════════════
with tabs[1]:
    st.header("📘 「科学と人間生活」とは")
    st.dataframe(kn.PROFILE, width="stretch", hide_index=True)

    st.subheader("学習指導要領（平成30年告示）の内容構成")
    st.caption("小項目の名前は、🧭 フィールドワーク伴走の「単元 ↔ 調査地」表と同じです。")
    st.dataframe(kn.CURRICULUM, width="stretch", hide_index=True)

    st.subheader("なぜフィールドワークの事前学習に向いているのか")
    for i, (title, body) in enumerate(fp.REASONS, 1):
        st.markdown(f"**{i}. {title}**　{body}")

    st.subheader("教科書・学び直しの資料")
    st.markdown(
        f"- 教科書は各社とも令和7年検定済の新版（例：東京書籍 科人002-901、第一学習社 科人183-901）。"
        f"[東京書籍「改訂 科学と人間生活」令和9年度用 教科書・シラバス]({kn.TEXTBOOK_URL})\n"
        f"- 映像で復習：[NHK高校講座「科学と人間生活」]({kn.NHK_URL})\n"
        f"- 教科書の1単元を Python で動かす教材：姉妹サイト"
        f"[{ss.SITES['tanpaku']['icon']} {ss.SITES['tanpaku']['name']}]({ss.url('tanpaku') or ss.SITES['tanpaku']['repo']})"
        "（生命の科学「ヒトの生命現象」 ─ 体をつくるタンパク質）"
    )
    st.markdown('<p class="note">教科書の記号・番号は、東京都教育委員会「教科書調査研究資料（令和8年度使用）」によります。'
                "採択している教科書の単元名に合わせて、表の名前を読み替えてください。</p>", unsafe_allow_html=True)

# ═════════════════════════════════════════════
# 🔗 単元×調査地
# ═════════════════════════════════════════════
with tabs[2]:
    st.header("🔗 「単元」と「調査地」の紐付け、そして問いのブリッジ")
    st.write("行き先に合わせて、**直前の授業に置く単元**を選びます。授業の終わりに**問いのブリッジ**を投げかけ、"
             "探究のワークシートにそのまま書かせます。")
    st.dataframe(kn.SITES, width="stretch", hide_index=True)

    c1, c2 = st.columns([1, 2])
    site = c1.selectbox("行き先（調査地の型）", kn.SITES["調査地の型"].tolist(), key="kn_site")
    cands = kn.units_for_site(site)
    unit = c1.selectbox("直前の授業の単元", cands, key="kn_unit")
    days = c1.slider("本番まで何日前の授業か", 1, 14, 7, key="kn_days")
    with c2.container(border=True):
        st.markdown("**授業の最後に投げる問い（問いのブリッジ）**")
        q = kn.bridge_question(unit, site, days)
        st.markdown(f"> {q}")
        row = fp.UNIT_BRIDGE[fp.UNIT_BRIDGE["単元"] == unit]
        if len(row):
            r = row.iloc[0]
            st.markdown(f"- スマートパン屋農家で見るもの：{r['現場で見るもの']}\n"
                        f"- 問いの例：{r['問いのブリッジ']}\n- 観察のレンズ：{fp.LENSES[r['レンズ']]}")
        st.download_button("問いのブリッジをテキストで保存", q.encode("utf-8"), "問いのブリッジ.txt", "text/plain")
        if ss.pairs_for_unit(unit, "bakery"):
            st.markdown("**教室で使う事前学習の教材（姉妹サイト）**")
            ss.render_unit(unit, "bakery")

# ═════════════════════════════════════════════
# 💻 事前学習の1コマ（情報Ⅰ）
# ═════════════════════════════════════════════
with tabs[3]:
    st.header("💻 事前学習の1コマ：光の屈折と「水深の錯覚」")
    st.write("単元「光の性質とその利用」×行き先「川・海岸・ため池」の例です。"
             "**① 計算する → ② 可視化する → ③ 自分の条件で判断する** の3段で、情報Ⅰ「モデル化とシミュレーション」と重ねます。")

    st.subheader("① 計算する")
    n = st.slider("水の屈折率 n", 1.30, 1.36, kn.N_WATER, 0.01, key="kn_n")
    real = st.slider("実際の深さ（m）", 0.0, 1.2, 0.6, 0.05, key="kn_real")
    m1, m2 = st.columns(2)
    m1.metric("見かけの深さ", f"{kn.apparent_depth(real, n):.2f} m",
              f"実際より {real - kn.apparent_depth(real, n):.2f} m 浅く見える", delta_color="off")
    m2.metric("見かけ ÷ 実際", f"{1 / n:.2f}", "約4分の3に見える", delta_color="off")
    st.caption("真上近くから見たときの近似：見かけの深さ ≒ 実際の深さ ÷ n。斜めから見るほど、さらに浅く見えます。")

    st.subheader("② 可視化する")
    tb = kn.depth_table(n=n)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tb["実際の深さ(m)"], y=tb["見かけの深さ(m)"], name="見かけの深さ",
                             mode="lines+markers", line=dict(color="#4a7ab0", width=3)))
    fig.add_trace(go.Scatter(x=tb["実際の深さ(m)"], y=tb["実際の深さ(m)"], name="実際の深さ",
                             line=dict(color="#999", dash="dash")))
    fig.add_vline(x=real, line_dash="dot", line_color="#c98a2b")
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10),
                      xaxis_title="実際の深さ (m)", yaxis_title="深さ (m)", legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, width="stretch")

    st.subheader("③ 自分の条件で判断する")
    d1, d2 = st.columns(2)
    seen = d1.slider("見えた深さ（m）", 0.0, 1.0, 0.45, 0.05, key="kn_seen")
    limit = d2.number_input("自分が歩ける深さの目安（m）", 0.1, 1.2, 0.5, 0.05, key="kn_limit",
                            help="自治体・国の防災資料で目安を調べて入れる。家族の脚力（子ども・高齢の家族）でも試す")
    flowing = d2.checkbox("水が流れている", key="kn_flow")
    msg, est = kn.wade_decision(seen, limit, n, flowing)
    box = st.error if msg.startswith("渡らない") else st.success
    box(f"見えた深さ {seen:.2f} m → 実際は約 **{est:.2f} m**。判断：{msg}")
    st.caption("流れがあると足をとられやすいため、この演習では目安を半分にして判断します（教育用の安全側の仮定）。"
               "実際の避難判断は、自治体のハザードマップ・気象庁の情報・避難指示に従ってください。")
    st.text_area("フィールドワークで確かめたい問い（例：この川の護岸は、何cmの増水を想定しているのか）", key="kn_q")

    with st.expander("情報Ⅰ：Google Colab で同じ計算をする（コピーして使えます）"):
        st.code(kn.COLAB_SNIPPET, language="python")

# ═════════════════════════════════════════════
# 🔁 PDCAの発展形
# ═════════════════════════════════════════════
with tabs[4]:
    st.header("🔁 PDCAの発展形を、伴走キット ❶〜❺ に当てはめる")
    st.write("PDCAは「計画を立ててから動く」型です。フィールドワークでは段ごとに求められる動きが違うため、"
             "発展形のよいところを段ごとに借ります。")
    st.dataframe(kn.PDCA_VARIANTS, width="stretch", hide_index=True)
    st.info("ひとことで：**準備は意味と対話（PDCA 2.0）、現場は速さ（OODA）、振り返りは学び（PDSA）、"
            "うまくいったら標準化（SDCA）**。改善はPDCA、維持はSDCAで交互に回します。")
    st.caption("「PDCA 2.0」は実務書・記事で使われる呼び方で、学術用語ではありません。"
               "研究や報告書で書くときは、PDSA（Deming）・OODA（Boyd）・SDCA（TQM）を使います。")
    try:
        st.page_link(tc.FIELDWORK_PAGE, label="伴走キット（❶〜❺）を開く", icon="🧭")
    except Exception:  # noqa: BLE001
        st.caption("🧭 伴走キットは左メニュー「🎓 学校向けの探究」から開けます")

ss.render("bakery", "科学と人間生活_FW事前学習")
st.markdown(f'<p class="note">最終更新：{UPDATED}　入力はこの画面の中だけで使い、保存しません。</p>',
            unsafe_allow_html=True)

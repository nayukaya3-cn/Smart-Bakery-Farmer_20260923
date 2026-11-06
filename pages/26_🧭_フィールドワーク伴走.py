"""
フィールドワーク伴走（HACCP型PDCA）─ 科学と人間生活を「事前学習のレンズ」にする
配置先: pages/26_🧭_フィールドワーク伴走.py （Streamlit のマルチページ構成）

ピボット：「科学と人間生活」は「総合的な探究の時間」におけるフィールドワークの事前学習として、
         極めて親和性が高く、非常に有益な科目である。

❶ 事前学習（HA：危害分析・戦略情報メモ）→ ❷ 日々の伴走（準備度のベイズ推定）
→ ❸ 本番（CCP の設定と日常管理）→ ❹ 事後（ずれ＝インサイト）→ ❺ 次の一手（是正処置と伴走）

計算は fieldwork_pdca.py（`python fieldwork_pdca.py` で自己チェック）。
初期表示はすべて架空の記入例です。入力はセッション内だけで使い、サーバーには残しません。
生徒の氏名は扱わず、学校が付けた匿名ID（例：S01）・班名で記録します。
"""
import datetime as dt

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import fieldwork_pdca as fp
import security_guard as sg
import sister_sites as ss
import social as sn
import teacher_course as tc

st.set_page_config(page_title="フィールドワーク伴走", page_icon="🧭", layout="wide")

PAGE = "fieldwork_pdca"
UPDATED = "2026-11-04"

st.markdown(
    """
    <style>
    .hero {padding: 1.6rem 1.8rem 1.4rem; border-radius: 16px;
           background: linear-gradient(120deg, #e4ecf5 0%, #f6e7c8 100%);
           color: #22313f; margin-bottom: 1rem;}
    .hero .eyebrow {font-size: .85rem; letter-spacing: .08em; color: #4a6a8a; margin: 0 0 .4rem 0;}
    .hero h1 {margin: 0 0 .6rem 0; font-size: 1.9rem; line-height: 1.35; color: #22313f;}
    .hero .lead {margin: 0; font-size: 1.05rem; line-height: 1.8;}
    .cycle {display: flex; flex-wrap: wrap; align-items: center; gap: .35rem; margin: .4rem 0 1rem;}
    .cycle span.step {padding: .4rem .8rem; border-radius: 10px; background: #eef2f6;
                      color: #22313f; font-size: .92rem; white-space: nowrap;}
    .cycle span.arrow {color: #8a9aa8;}
    .note {font-size: .85rem; color: #5a6a75;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="hero">
      <p class="eyebrow">学校の先生向け ・ 総合的な探究の時間 × 科学と人間生活</p>
      <h1>フィールドワークを「見学」で終わらせない<br>HACCP型PDCAの伴走キット</h1>
      <p class="lead">{fp.PIVOT}<br>
      教科の知識を<b>レンズ（眼鏡）</b>として掛けてから現場に行くと、見える景色が変わります。
      パン工場の衛生管理（HACCP）と同じ骨格で、事前・本番・事後を一続きに回します。</p>
    </div>
    """,
    unsafe_allow_html=True,
)
steps = ["❶ 事前学習＝HA（危害分析）", "❷ 日々の伴走", "❸ 本番＝CCP", "❹ 事後＝検証", "❺ 次の一手＝是正処置"]
st.markdown('<div class="cycle">' + '<span class="arrow">→</span>'.join(
    f'<span class="step">{s}</span>' for s in steps) + '<span class="arrow">→ ❶へ戻る</span></div>',
    unsafe_allow_html=True)

with st.sidebar:
    st.header("🧭 フィールドワークの設定")
    theme = st.text_input("テーマ", "サプライチェーンの崩壊に備える「スマートパン屋農家」から学ぶ食と技術",
                          key="fw_theme")
    fw_day = st.date_input("フィールドワークの日", dt.date.today() + dt.timedelta(days=14), key="fw_day")
    grade = st.selectbox("対象", ["高校1年", "高校2年", "高校3年", "通信制・サポート校", "中学3年"], key="fw_grade")
    n_students = st.number_input("人数", 1, 200, 30, key="fw_n")
    days_left = (fw_day - dt.date.today()).days
    st.metric("本番まで", f"{days_left} 日" if days_left >= 0 else "実施済み")
    st.caption("初期表示はすべて架空の記入例です。入力はこの画面の中だけで使い、保存しません。")

tabs = st.tabs(["🧭 全体像", "❶ 事前：HA", "❷ 日々の伴走", "❸ 本番：CCP", "❹ 事後：振り返り", "❺ 次の一手"])

# ═════════════════════════════════════════════
# 全体像
# ═════════════════════════════════════════════
with tabs[0]:
    st.header("🧭 なぜ「科学と人間生活」が事前学習に効くのか")
    cols = st.columns(3)
    for col, (i, (title, body)) in zip(cols, enumerate(fp.REASONS, 1)):
        with col.container(border=True):
            st.markdown(f"**理由{i}：{title}**\n\n{body}")

    try:
        st.page_link(tc.SUBJECT_PAGE, label="教科の側から：科目の位置づけ・単元×調査地・事前学習の1コマ（📝 教科×情報Ⅰ）", icon="🔭")
    except Exception:  # noqa: BLE001
        st.caption("🔭 科目の詳しい説明は左メニュー「📝 教科×情報Ⅰ」から開けます")

    st.subheader("PDCA を HACCP の言葉で回す")
    st.dataframe(fp.PDCA, width="stretch", hide_index=True)
    st.caption("HACCP（危害分析・重要管理点）は、食品工場で「事故を起こしてから検査する」のではなく、"
               "「どこで何が起こりうるかを先に分析し、要所だけを決まった基準で毎回測る」考え方です。"
               "探究学習でも、見学で終わる・事故になる原因を先に分析し、当日は要所だけを測ります。")

    st.subheader("現場で迷子にならない「3つのレンズ」")
    for k, v in fp.LENSES.items():
        st.markdown(f"- **レンズ{k}**：{v}")

    st.subheader("配布物（そのまま印刷・編集できます）")
    d1, d2 = st.columns(2)
    with d1:
        st.download_button("📄 事前学習ワークシート（Markdown）", fp.WORKSHEET_MD.encode("utf-8"),
                           "事前学習ワークシート.md", "text/markdown", width="stretch")
        with st.expander("中身を見る"):
            st.markdown(fp.WORKSHEET_MD)
    with d2:
        st.download_button("🎤 インタビュー質問集（Markdown）", fp.INTERVIEW_MD.encode("utf-8"),
                           "インタビュー質問集.md", "text/markdown", width="stretch")
        with st.expander("中身を見る"):
            st.markdown(fp.INTERVIEW_MD)

# ═════════════════════════════════════════════
# ❶ 事前学習：HA（危害分析）＝ 戦略情報メモ
# ═════════════════════════════════════════════
with tabs[1]:
    st.header("❶ 事前学習：HA（危害分析）── 戦略情報メモをつくる")
    st.write("**全体最適**の段です。① 単元と現場を紐付け、② 当日起こりうる危害を点数化し、"
             "③ 本番で管理する点（CCP）を決めます。学校内の打ち合わせと、受け入れ先との共有に使います。")

    st.subheader("① 計算する前に：単元 ↔ 調査地 の紐付け（問いのブリッジ）")
    units = st.multiselect("直前の授業で扱う単元（科学と人間生活）", fp.UNIT_BRIDGE["単元"].tolist(),
                           default=["微生物とその利用", "熱の性質とその利用", "自然景観と自然災害"], key="fw_units")
    st.dataframe(fp.UNIT_BRIDGE[fp.UNIT_BRIDGE["単元"].isin(units)], width="stretch", hide_index=True)
    st.caption("授業の最後に「問いのブリッジ」を投げかけ、ワークシートの Step3 にそのまま書かせます。")
    lens_cnt = fp.UNIT_BRIDGE[fp.UNIT_BRIDGE["単元"].isin(units)]["レンズ"].value_counts()
    missing_lens = [k for k in fp.LENSES if k not in lens_cnt.index]
    if missing_lens:
        st.warning(f"レンズ {'・'.join(missing_lens)} につながる単元が選ばれていません。"
                   "当日の観察が片寄らないよう、1つ足すかインタビュー質問で補ってください。")

    st.subheader("② 危害分析：起こりやすさ × 重大さ")
    st.caption("種類：" + "／".join(f"{k}＝{v}" for k, v in fp.HAZARD_KINDS.items()))
    if "fw_hazards" not in st.session_state:
        st.session_state.fw_hazards = fp.HAZARDS.copy()
    hz_in = st.data_editor(
        st.session_state.fw_hazards, num_rows="dynamic", width="stretch", hide_index=True, key="fw_hz_editor",
        column_config={
            "種類": st.column_config.SelectboxColumn(options=list(fp.HAZARD_KINDS), required=True),
            "起こりやすさ": st.column_config.NumberColumn(min_value=1, max_value=3, step=1, required=True),
            "重大さ": st.column_config.NumberColumn(min_value=1, max_value=3, step=1, required=True),
        })
    hz_in = hz_in.dropna(subset=["危害", "起こりやすさ", "重大さ"])
    hz = fp.analyze_hazards(hz_in) if len(hz_in) else hz_in

    if len(hz):
        st.subheader("③ 可視化する：リスクマップ")
        fig = px.scatter(hz, x="起こりやすさ", y="重大さ", color="区分", size="リスク点", text="種類",
                         hover_data=["危害"], size_max=28,
                         color_discrete_map={"CCP（本番で管理）": "#c0504d", "前提条件（事前に整える）": "#c98a2b",
                                             "様子を見る": "#9bb884"})
        fig.update_traces(textposition="middle center")
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10),
                          xaxis=dict(range=[0.5, 3.5], dtick=1), yaxis=dict(range=[0.5, 3.5], dtick=1))
        st.plotly_chart(fig, width="stretch")
        st.dataframe(hz[["種類", "危害", "リスク点", "区分", "予防措置"]], width="stretch", hide_index=True)
        n_ccp = int((hz["区分"] == "CCP（本番で管理）").sum())
        st.info(f"判断：本番で管理する点（CCP）は **{n_ccp} 件**。重大さ3（命・健康・個人情報）は、"
                "起こりにくくても CCP に残します。→ ❸ の管理表へ。")

        memo = fp.strategy_memo(theme, fw_day, grade, int(n_students), units, hz_in)
        st.download_button("🗂️ 戦略情報メモ（Markdown）をダウンロード", memo.encode("utf-8"),
                           f"戦略情報メモ_{fw_day:%Y%m%d}.md", "text/markdown")
        st.download_button("危害分析の表をCSVで保存", sg.safe_csv(hz), "危害分析.csv", "text/csv")
    st.markdown('<p class="note">※ 点数づけは教育用の簡易法です。安全の最終判断は学校・受け入れ先の基準に従ってください。</p>',
                unsafe_allow_html=True)

# ═════════════════════════════════════════════
# ❷ 日々の伴走
# ═════════════════════════════════════════════
with tabs[2]:
    st.header("❷ 本番までの、日々の自主的探究への伴走")
    st.write("本番の日から逆算して、**1日1つの小さな課題**を出します。できた・できないの記録から"
             "準備度を**ベイズ推定**し、「誰に・何と声をかけるか」の順番を決めます。")

    st.subheader("① 逆算スケジュール")
    st.dataframe(fp.task_schedule(fw_day), width="stretch", hide_index=True)

    st.subheader("② 記録（匿名ID）")
    up = st.file_uploader("記録CSV（列：生徒ID,出された課題,できた課題,作った問い,出典を書いた数値）",
                          type="csv", key="fw_daily_up")
    if "fw_daily" not in st.session_state:
        st.session_state.fw_daily = fp.sample_daily_log()
    if up is not None:
        _df = sg.read_csv_safely(up, page=PAGE, kind="daily")
        need = set(fp.sample_daily_log().columns)
        if _df is not None and need <= set(_df.columns):
            st.session_state.fw_daily = _df[list(fp.sample_daily_log().columns)]
        elif _df is not None:
            st.error("列名が足りません：" + "・".join(sorted(need - set(_df.columns))))
    daily = st.data_editor(st.session_state.fw_daily, num_rows="dynamic", width="stretch",
                           hide_index=True, key="fw_daily_editor")
    daily = daily.dropna()
    daily = daily[(daily["できた課題"] >= 0) & (daily["できた課題"] <= daily["出された課題"])]

    st.subheader("③ 計算する：準備度のベイズ推定")
    th = st.slider("「準備ができた」とみなす準備度", 0.5, 0.9, 0.7, 0.05, key="fw_th")
    st.caption("事前分布 Beta(1, 1)（何も知らない状態）に、できた課題・できなかった課題を足して事後分布を作ります。"
               "課題の数が少ないうちは区間が広く、「まだ判断できない」と読みます。")
    if len(daily):
        rank = fp.rank_for_coaching(daily, threshold=th)
        col_p = f"準備度≧{th:.0%}の確率"
        fig = go.Figure(go.Bar(x=rank["生徒ID"], y=rank[col_p],
                               marker_color=["#c0504d" if v < 0.5 else "#6a9a4a" for v in rank[col_p]]))
        fig.add_hline(y=0.5, line_dash="dot", annotation_text="0.5 未満から声をかける")
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), yaxis=dict(range=[0, 1], title=col_p))
        st.plotly_chart(fig, width="stretch")
        st.subheader("④ 判断する：声かけの順番")
        st.dataframe(rank, width="stretch", hide_index=True)
        st.download_button("伴走の記録をCSVで保存", sg.safe_csv(daily), "日々の伴走.csv", "text/csv")

    with st.expander("伴走の声かけ（答えを言わずに問い返す）"):
        st.dataframe(pd.DataFrame(fp.COACHING, columns=["見立て", "声かけの例"]), width="stretch", hide_index=True)

# ═════════════════════════════════════════════
# ❸ 本番：CCP
# ═════════════════════════════════════════════
with tabs[3]:
    st.header("❸ 本番支援：CCP（重要管理点）の設定と日常管理")
    st.write("**臨機応変**の段です。全部を見張るのではなく、❶で決めた要所だけを**決まった基準で測り**、"
             "外れたら**その場で是正**して**記録に残します**。")
    st.subheader("① CCP 管理表")
    st.dataframe(fp.CCP_PLAN, width="stretch", hide_index=True)
    st.download_button("CCP管理表をCSVで保存（当日印刷用）", sg.safe_csv(fp.CCP_PLAN), "CCP管理表.csv", "text/csv")

    st.subheader("② 計算する：暑さ指数（WBGT）の判断")
    w = st.slider("いまの暑さ指数（WBGT）", 10.0, 35.0, 22.0, 0.5, key="fw_wbgt")
    act = fp.wbgt_action(w)
    (st.error if w >= 28 else st.warning if w >= 25 else st.success)(f"WBGT {w:.1f} → {act}")
    st.caption("区分は日本スポーツ協会「熱中症予防運動指針」に合わせています。ハウスの中は外より高くなるので、ハウス内でも測ります。"
               "冬は「濡れ＋風」で体温が奪われるため、雨の日は屋内の作業に切り替えます。")

    st.subheader("③ 当日の管理記録（モニタリング）")
    if "fw_mon" not in st.session_state:
        st.session_state.fw_mon = fp.sample_monitoring()
    mon = st.data_editor(
        st.session_state.fw_mon, num_rows="dynamic", width="stretch", hide_index=True, key="fw_mon_editor",
        column_config={"CCP": st.column_config.SelectboxColumn(options=fp.CCP_PLAN["CCP"].tolist()),
                       "基準内": st.column_config.CheckboxColumn(default=True)})
    mon = mon.dropna(subset=["CCP"])
    if len(mon):
        s = fp.monitoring_summary(mon)
        m1, m2, m3 = st.columns(3)
        m1.metric("記録の数", s["n"])
        m2.metric("基準から外れた数", s["n_off"])
        m3.metric("是正を書き忘れた数", s["n_missing"])
        if s["n_missing"]:
            st.error("基準から外れたのに、是正の内容が書かれていない記録があります。HACCPでは「外れた → 何をしたか」までが1組の記録です。")
            st.dataframe(s["missing_rows"], width="stretch", hide_index=True)
        else:
            st.success("基準から外れた記録には、すべて是正の内容が書かれています。")
        st.download_button("当日の管理記録をCSVで保存", sg.safe_csv(mon), "当日の管理記録.csv", "text/csv")

    st.subheader("④ T2のつまずき記録（個別伴走 → 次の❶へ戻す）")
    st.write("ティーム・ティーチングのサポート役（T2）が、授業・実習中のつまずきを**1行ずつ**残します。"
             "「その場で解消した／T1へつないだ」と「次の予防」までが1組。集計は❹の振り返りと、次回の❶（危害分析）に戻します。")
    with st.expander("種類の見分け方（L・P・I・S・R）"):
        st.dataframe(pd.DataFrame(list(fp.STUMBLE_KINDS.items()), columns=["種類", "内容"]),
                     width="stretch", hide_index=True)
    up_st = st.file_uploader("つまずき記録CSV（列：" + ",".join(fp.STUMBLE_COLS) + "）",
                             type="csv", key="fw_stumble_up")
    if "fw_stumble" not in st.session_state:
        st.session_state.fw_stumble = fp.sample_stumble_log()
    if up_st is not None:
        _st = sg.read_csv_safely(up_st, page=PAGE, kind="stumble")
        if _st is not None and set(fp.STUMBLE_COLS) <= set(_st.columns):
            _st = _st[fp.STUMBLE_COLS]
            _st["日付"] = pd.to_datetime(_st["日付"], errors="coerce").dt.date
            _st["解消"] = _st["解消"].astype(str).str.strip().str.lower().isin(["true", "1", "はい", "○"])
            st.session_state.fw_stumble = _st
        elif _st is not None:
            st.error("列名が足りません：" + "・".join(sorted(set(fp.STUMBLE_COLS) - set(_st.columns))))
    stl = st.data_editor(
        st.session_state.fw_stumble, num_rows="dynamic", width="stretch", hide_index=True, key="fw_stumble_editor",
        column_config={
            "日付": st.column_config.DateColumn(),
            "種類": st.column_config.SelectboxColumn(options=list(fp.STUMBLE_KINDS)),
            "解消": st.column_config.CheckboxColumn("その場で解消", default=False),
            "分": st.column_config.NumberColumn("解消までの分", min_value=0, max_value=50, step=1),
        })
    stl = stl.dropna(subset=["生徒ID", "種類"])
    st.caption("生徒の氏名・学校名は書かず、匿名IDで記録します。初期表示は架空の記入例です。")
    if len(stl):
        predicted = st.multiselect("事前の打ち合わせ（❶）で予想していた種類", list(fp.STUMBLE_KINDS),
                                   default=["P", "L"], key="fw_stumble_pred")
        sm = fp.stumble_summary(stl, predicted=predicted)
        c1, c2, c3 = st.columns(3)
        c1.metric("つまずきの数", sm["n"])
        c2.metric("その場で解消した割合", f"{sm['solved']:.0%}")
        c3.metric("対応にかかった分（合計）", f"{sm['minutes']:.0f} 分")
        st.dataframe(sm["by_kind"], width="stretch", hide_index=True)
        if sm["unexpected"]:
            st.warning("予想していなかった種類：" + "・".join(sm["unexpected"])
                       + " → インサイトです。次回の打ち合わせで CCP の候補にします。")
        if len(sm["missing_rows"]):
            st.error("その場で解消しなかったのに、「次の予防」が空の記録があります。")
            st.dataframe(sm["missing_rows"], width="stretch", hide_index=True)
        st.markdown("**次の授業で、手立てを変えて先に見に行く順**")
        st.caption("同じ声かけで解消しなかった回数が多い生徒ほど上に来ます。後回しにするための順番ではなく、"
                   "**手立てを変える**ための順番です。")
        st.dataframe(fp.next_visit_priority(stl), width="stretch", hide_index=True)
        st.download_button("つまずき記録をCSVで保存", sg.safe_csv(stl), "T2つまずき記録.csv", "text/csv")

# ═════════════════════════════════════════════
# ❹ 事後：振り返り
# ═════════════════════════════════════════════
with tabs[4]:
    st.header("❹ 事後学習：振り返り ── 予想と事実の「ずれ」がインサイト")
    st.write("**未来最適**の段です。❷ の D-1 に書いた「答えの予想」と、現地の事実を並べます。"
             "**予想と逆だった・予想になかった**ずれほど、次の探究の種になります。")
    st.caption("インサイト点 ＝ ずれの重み（予想どおり 0.5／逆・新発見 1／確かめられなかった 0）× 驚き（1〜5）")
    if "fw_ref" not in st.session_state:
        st.session_state.fw_ref = fp.sample_reflection()
    ref = st.data_editor(
        st.session_state.fw_ref, num_rows="dynamic", width="stretch", hide_index=True, key="fw_ref_editor",
        column_config={"ずれの種類": st.column_config.SelectboxColumn(options=fp.GAP_TYPES, required=True),
                       "驚き": st.column_config.NumberColumn(min_value=1, max_value=5, step=1, required=True),
                       "使った単元": st.column_config.SelectboxColumn(options=fp.UNIT_BRIDGE["単元"].tolist())})
    ref = ref.dropna(subset=["班", "ずれの種類", "驚き"])
    if len(ref):
        sc = fp.insight_score(ref)
        fig = px.bar(sc, x="インサイト点", y="現地の事実", color="ずれの種類", orientation="h",
                     hover_data=["班", "事前の予想"],
                     color_discrete_map={"予想と逆": "#c98a2b", "予想になかった発見": "#6a9a4a",
                                         "予想どおり": "#9bb0c4", "確かめられなかった": "#c9c2b4"})
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(autorange="reversed", title=None))
        st.plotly_chart(fig, width="stretch")
        st.caption("どの単元のレンズが、ずれ（インサイト）を生んだか")
        st.dataframe(sc.groupby("使った単元", as_index=False)["インサイト点"].sum()
                     .sort_values("インサイト点", ascending=False), width="stretch", hide_index=True)

    st.subheader("事前・事後の自己評価（1〜4）")
    if "fw_rub" not in st.session_state:
        st.session_state.fw_rub = fp.sample_rubric()
    rub = st.data_editor(st.session_state.fw_rub, width="stretch", hide_index=True, key="fw_rub_editor")
    fig = go.Figure()
    for col, color in (("事前", "#9bb0c4"), ("事後", "#c98a2b")):
        fig.add_trace(go.Scatterpolar(r=list(rub[col]) + [rub[col].iloc[0]],
                                      theta=list(rub["観点"]) + [rub["観点"].iloc[0]],
                                      name=col, line=dict(color=color), fill="toself", opacity=0.6))
    fig.update_layout(height=380, polar=dict(radialaxis=dict(range=[0, 4])), margin=dict(l=30, r=30, t=30, b=30))
    st.plotly_chart(fig, width="stretch")
    st.warning("読み方の注意：比べる相手（フィールドワークに行かなかった組）がないので、"
               "「伸びた」とは言えても「フィールドワークのおかげで伸びた」とまでは言えません。"
               "因果を言いたいときは、⚖️ 比べて確かめる探究 の「くじで分ける」「差の差」を使います。")

# ═════════════════════════════════════════════
# ❺ 次の一手
# ═════════════════════════════════════════════
with tabs[5]:
    st.header("❺ 次の一手：是正処置の企画と提案、そして伴走")
    st.write("HACCPの**是正処置**は「外れた原因を直し、次は外れないようにする」こと。探究では、"
             "❹で見つけたずれを、**次の探究の一手**に変えて生徒に提案します。決めるのは生徒です。")
    with st.expander("ずれの種類 → 次の一手の型"):
        st.dataframe(pd.DataFrame([(k, *v) for k, v in fp.NEXT_MOVES.items()],
                                  columns=["ずれの種類", "次の一手", "具体案", "使うページ"]),
                     width="stretch", hide_index=True)
    base = ref if len(ref) else fp.sample_reflection()  # ❹ で入力した振り返りを使う
    top = st.slider("インサイト点の高いものから何件を提案するか", 1, 6, 3, key="fw_top")
    moves = fp.next_moves(base, top=top)
    st.dataframe(moves, width="stretch", hide_index=True)
    st.caption("「確かめられなかった」ずれは、点数に関係なく必ず次の一手に入れます（聞きそびれを放置しない）。")

    st.subheader("班のミッション（共通）")
    st.info(fp.MISSION)

    st.subheader("提案書と伴走の予定")
    teams = moves["班"].unique().tolist()
    if teams:
        c1, c2 = st.columns([1, 2])
        team = c1.selectbox("班", teams, key="fw_team")
        start = c1.date_input("伴走の開始日", fw_day + dt.timedelta(days=4), key="fw_start")
        weeks = c1.slider("伴走の週数", 2, 8, 4, key="fw_weeks")
        plan = fp.coaching_plan(start, weeks)
        c2.dataframe(plan, width="stretch", hide_index=True)
        text = fp.proposal_text(team, moves, plan)
        with st.expander("提案書の中身を見る", expanded=True):
            st.markdown(text)
        st.download_button(f"📨 {team}への提案書（Markdown）", text.encode("utf-8"),
                           f"次の一手_{team}.md", "text/markdown")
    st.success("❺ の結果は、次のフィールドワークの ❶（危害分析）に戻します。"
               "「確かめられなかった」が多かった観点は、次回の CCP4（問いの質）の基準を見直す材料になります。")

ss.render("bakery", "フィールドワーク伴走")
st.divider()
st.write(f"この伴走キットへのご意見・試してみたい学校の先生は、{sn.NAMES}からお声がけください。"
         "受け入れ実績はまだありません（フェーズ0：実証・記録）。")
sn.buttons("で声をかける")
st.markdown(f'<p class="note">※ 初期表示はすべて架空の記入例です。最終更新：{UPDATED}</p>', unsafe_allow_html=True)

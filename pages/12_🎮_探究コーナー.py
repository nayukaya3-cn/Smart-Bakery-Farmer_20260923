"""
探究コーナー ─ ゲーム運営の目で、農園の体験会を分析する
配置先: pages/12_🎮_探究コーナー.py （Streamlit のマルチページ構成）

ピボット（軸）にしたもの：
  ThinkingData『ゲームデータアナリティクス よりよい開発・運営に向けたデータ分析の教科書』（翔泳社）
  ゲーム会社が毎日まわしている「集める → 指標にする → 探す → 確かめる → 運営に生かす」を、
  農園の体験会・直売所に置き換えて、高校「情報Ⅰ（データの活用）」の探究として体験する。

骨格はリポジトリ共通の3段構え：
  ① 現象を計算する（指標・ファネル・検定）→ ② 数値を可視化する（グラフ・地図）
  → ③ 自分の条件で判断する（どの施策を、何人分のデータで決めるか）

方針
  - 計算は game_lab.py（`python game_lab.py` で自己チェック）。
  - 初期表示はすべて架空データ（実測ではありません）。
  - アップロードした記録はセッション内だけで使い、サーバーには残さない。氏名は扱わない。
  - 外部の生成AIは呼び出さない。
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import os

import game_lab as gl
import security_guard as sg

st.set_page_config(page_title="探究コーナー：ゲーム運営の目で見る", page_icon="🎮", layout="wide")

import social as sn  # noqa: E402  SNSのURLは social.py で一括管理

UPDATED = "2026-10-16"
PAGE = "game_lab"
BOOK = "ThinkingData『ゲームデータアナリティクス よりよい開発・運営に向けたデータ分析の教科書』（翔泳社）"
AI_MODEL = os.environ.get("GAME_AI_MODEL", "claude-sonnet-5-5")
FLYER_COLORS = {gl.FLYERS[0]: "#c98a2b", gl.FLYERS[1]: "#3f7cac"}



def gl_ai_ready() -> bool:
    """生成AIが使えるか（ライブラリとAPIキーの両方がある）。"""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(api_key())


def api_key() -> str:
    """APIキー：Streamlit の secrets、なければ環境変数（security_guard と同じ読み方）。"""
    return sg._secret("ANTHROPIC_API_KEY")


if "gl_ev" not in st.session_state:
    st.session_state.gl_ev = gl.normalize_events(gl.sample_events())
    st.session_state.gl_is_sample = True

# ─────────────────────────────────────────────
# サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("🎮 探究コーナー")
    st.caption("来訪ログのCSVを読み込むと、すべてのタブがその記録で計算し直されます。")
    up = st.file_uploader("来訪ログCSVを読み込む", type="csv", key="up_gl",
                          help=f"列：{', '.join(gl.EVENT_COLS)}")
    if up is not None and st.session_state.get("gl_loaded") != up.file_id:
        _df = sg.read_csv_safely(up, page=PAGE, kind="events")
        if _df is not None:
            st.session_state.gl_ev = gl.normalize_events(_df)
            st.session_state.gl_is_sample = False
        st.session_state.gl_loaded = up.file_id
    st.divider()
    n_vis = st.slider("架空データの来訪者数", 60, 600, 240, 20)
    seed = st.number_input("くじの番号", 0, 9999, 2026, 1, help="同じ番号なら同じ架空データになります。")
    if st.button("この条件で架空データを作り直す", width="stretch"):
        st.session_state.gl_ev = gl.normalize_events(gl.sample_events(int(n_vis), int(seed)))
        st.session_state.gl_is_sample = True
    st.divider()
    sn.buttons("で相談する", stacked=True)

EV: pd.DataFrame = st.session_state.gl_ev.dropna(subset=["日付", "来訪者ID"])
EV = EV[EV["できごと"].isin(gl.STEPS)]

st.title("🎮 探究コーナー：ゲーム運営の目で、農園を分析する")
st.caption(f"ピボット：{BOOK}　／　更新 {UPDATED}")
if st.session_state.gl_is_sample:
    st.info("いま表示しているのは **架空の来訪ログ** です（実測ではありません）。"
            "サイドバーで条件を変えて作り直すか、記録CSVを読み込んで切り替えます。")
if EV.empty:
    st.warning("計算できる行がありません。「① 集める」タブでデータの形を確かめてください。")
    st.stop()

tab_flow, tab_c, tab_k, tab_e, tab_t, tab_j = st.tabs([
    "🧭 この探究の流れ", "📥 ① 集める", "📊 ② 指標にする", "🔍 ③ 探す",
    "⚖️ ④ 確かめる", "🤖 ⑤ AIアプリ・判断する",
])

# ═════════════════════════════════════════════
# 0. 流れ
# ═════════════════════════════════════════════
with tab_flow:
    st.header("🧭 なぜ「ゲーム」を軸にするのか")
    st.write(
        "スマホゲームの会社は、毎日たくさんの人の行動ログを集め、**数字で次の一手を決める**仕組みを"
        "いちばん磨いてきた業界のひとつです。その型を借りると、農園の体験会や直売所でも"
        "「なんとなく」ではなく「数字で確かめて決める」ことができます。"
        "これは高校「情報Ⅰ」のデータの活用（収集・整理・分析・可視化）そのものです。"
    )
    st.subheader("ゲームの言葉 ↔ 農園の言葉 ↔ 研究の言葉")
    st.dataframe(pd.DataFrame([
        ("プレイヤー", "来訪者（匿名ID）", "観測の単位", "① 集める", "4章 収集"),
        ("チュートリアル突破率", "種まき→収穫→パン焼き の残り具合", "ファネル分析", "② 指標にする", "2・5章"),
        ("翌日継続率", "翌月にまた来た割合", "コホート別リテンション", "② 指標にする", "6章 改善型"),
        ("課金率・ARPPU", "購入率・客単価", "KPIツリー（掛け算分解）", "② 指標にする", "5章 指標体系"),
        ("プレイヤーのタイプ", "来訪の仕方のタイプ", "k-means・主成分分析", "③ 探す", "7.1 探索的分析"),
        ("A/Bテスト", "案内チラシ2種", "並べ替え検定・ベイズ", "④ 確かめる", "7.2 因果推論とテスト"),
        ("きめ細やかな運営", "相手ごとに次の体験メニューを勧める", "文脈付きバンディット（AIおすすめ係）", "⑤ AIアプリ", "11章"),
        ("AIとの融合", "分析結果の読み方を相談する", "生成AI（AI家庭教師）", "⑤ AIアプリ", "12.4"),
    ], columns=["ゲーム", "農園", "研究での言い方", "このページのタブ", "書籍の章"]),
        width="stretch", hide_index=True)

    st.subheader("3段構えとの対応")
    st.dataframe(pd.DataFrame([
        ("① 現象を計算する", "指標・残存率・差・確率を出す", "②③④のタブの数字"),
        ("② 数値を可視化する", "ファネル・ヒートマップ・散布図・分布", "②③④のタブのグラフ"),
        ("③ 自分の条件で判断する", "定員・期間・目標から「何で決めるか」を選ぶ", "⑤ のマイ判断シート"),
    ], columns=["段", "やること", "このページのどこ"]), width="stretch", hide_index=True)

    st.subheader("考え方の骨組み：結果（目的変数）と原因（説明変数）")
    st.markdown(
        "- **目的変数 y**（結果）：例「パン焼き体験まで進んだか」「買ったか」\n"
        "- **説明変数 x**（その結果の原因の候補）：例「経路」「受け取ったチラシ」「来た月」\n"
        "- 探索的分析（③）で **原因の仮説** を立て、確証的分析（④）で **検定して確かめる**。\n"
        "- ベイズ推定は、結果から原因を逆に読む道具：**P(x | y)**（買った人の中で経路が何か）と"
        "**P(y | x)**（その経路から来た人が買う確率）を行き来する（③の最後）。"
    )
    st.subheader("90分の当日の流れ（例）")
    st.dataframe(pd.DataFrame([
        ("0–15分", "好きなゲームの「つい続けてしまう仕掛け」を出し合う", "🧭 流れ"),
        ("15–30分", "農園で何を記録すれば同じ分析ができるか、データプランを作る", "① 集める"),
        ("30–55分", "ファネルとリテンションを見て「どこで人が抜けるか」を探す", "② 指標・③ 探す"),
        ("55–75分", "チラシA/Bの差は偶然か。並べ替え検定とベイズで確かめる", "④ 確かめる"),
        ("75–90分", "AIおすすめ係を動かし、自分が運営者なら何で決めるかを書いて発表", "⑤ AIアプリ・判断する"),
    ], columns=["時間", "内容", "タブ"]), width="stretch", hide_index=True)
    st.caption(f"参考：{BOOK}。本ページの文章・データ・計算はこのアプリ独自のもので、書籍の内容の転載ではありません。")

# ═════════════════════════════════════════════
# 1. 集める
# ═════════════════════════════════════════════
with tab_c:
    st.header("📥 ① 集める：データプランを先に決める")
    st.write("ゲームでは「分析したい問い」から逆算して、記録するできごと（イベント）を最初に決めます。"
             "あとから「その列があれば…」と思っても、過去の分は取り直せないからです。")
    st.dataframe(pd.DataFrame(gl.DATA_PLAN, columns=["項目", "例", "型", "なぜ要るか", "守ること"]),
                 width="stretch", hide_index=True)

    st.subheader("記録（1行＝1つのできごと）")
    show = EV.copy()
    show["日付"] = show["日付"].dt.strftime("%Y-%m-%d")
    st.dataframe(show, width="stretch", hide_index=True, height=260)
    st.download_button("来訪ログをCSVで保存", sg.safe_csv(show), "来訪ログ.csv", "text/csv")

    st.subheader("データ品質のチェック")
    issues = gl.quality_report(st.session_state.gl_ev.reset_index(drop=True))
    if issues.empty:
        st.success(f"{len(EV)} 行：記入漏れ・選択肢外・ありえない金額・重複は見つかりませんでした。")
    else:
        st.warning(f"確認が必要な箇所が {len(issues)} 件あります（計算からは自動で除いています）。")
        st.dataframe(issues, width="stretch", hide_index=True)

    with st.expander("🔒 記録の約束（プライバシーとセキュリティ）"):
        st.markdown(
            "- 氏名・連絡先・顔写真はログに入れない。IDと本人の対応表は別の場所に鍵付きで保管する\n"
            "- 「経路」「できごと」は選択肢から選ぶ。自由記述は入れない（個人が特定される書き込みを防ぐ）\n"
            "- 保存したCSVは Excel で開いても数式が動かないように処理しています（CSVインジェクション対策）\n"
            "- 書籍12章の「データセキュリティとプライバシー保護」は、データを集める側の責任です"
        )

# 以降のタブで共通に使う集計
KT = gl.kpi_tree(EV)
FU = gl.funnel(EV)
VF = gl.visitor_features(EV)

# ═════════════════════════════════════════════
# 2. 指標にする
# ═════════════════════════════════════════════
with tab_k:
    st.header("📊 ② 指標にする：売上を掛け算に分ける")
    st.latex(r"\text{売上} = \text{来訪数} \times \text{購入率} \times \text{客単価}")
    st.write("売上が下がったとき、「人が来なかった」のか「来たけど買わなかった」のか「買った額が小さかった」のかで、"
             "打つ手がまったく違います。掛け算に分けると、どこが動いたかが見えます。")
    st.dataframe(KT.style.format({"購入率": "{:.0%}", "客単価": "{:,.0f}円", "売上": "{:,.0f}円"}),
                 width="stretch", hide_index=True)

    if len(KT) >= 2:
        months = KT["月"].tolist()
        c1, c2 = st.columns(2)
        m0 = c1.selectbox("比べる前の月", months, index=len(months) - 2)
        m1 = c2.selectbox("比べる後の月", months, index=len(months) - 1)
        b, a = KT.set_index("月").loc[m0], KT.set_index("月").loc[m1]
        if min(b["購入数"], a["購入数"]) > 0:
            dc = gl.decompose_change(b, a)
            fig = go.Figure(go.Waterfall(
                x=["前の売上"] + dc["指標"].tolist() + ["後の売上"],
                measure=["absolute", "relative", "relative", "relative", "total"],
                y=[b["売上"]] + dc["売上の差への寄与（円）"].tolist() + [0],
                connector={"line": {"color": "#bbb"}}))
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10),
                              title=f"{m0} → {m1}：売上の差はどこから来たか")
            st.plotly_chart(fig, width="stretch")
            top = dc.loc[dc["売上の差への寄与（円）"].abs().idxmax(), "指標"]
            st.caption(f"いちばん大きく効いたのは **{top}**。次に手を打つならここから。")

    st.subheader("ファネル：どの段で人が抜けるか（チュートリアル突破率の考え方）")
    by = st.radio("分ける軸", ["全体", "経路", "チラシ"], horizontal=True)
    fu = gl.funnel(EV, None if by == "全体" else by)
    fig = px.funnel(fu, x="人数", y="段", color="グループ" if by != "全体" else None)
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch")
    weak = FU.iloc[1:].loc[FU["前の段からの残存率"].iloc[1:].idxmin()]
    st.caption(f"全体でいちばん残存率が低いのは **「{weak['段']}」**（前の段から {weak['前の段からの残存率']:.0%}）。"
               "ゲームなら、まずここのチュートリアルを直します。")

    st.subheader("リテンション：初めて来た月ごとに、何か月後まで来続けたか")
    rt = gl.retention(EV)
    heat = rt.drop(columns="人数")
    fig = px.imshow(heat, text_auto=".0%", color_continuous_scale="Greens", aspect="auto",
                    labels=dict(x="", y="初めて来た月", color="割合"))
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch")
    st.caption("右下が空白なのは、まだその月が来ていないからです（0%ではありません）。")

    st.subheader("アラート：いつもと違う月に印をつける")
    k = st.slider("何σ外れたら知らせるか", 1.0, 3.0, 2.0, 0.5,
                  help="小さくすると見逃しは減るが、空振り（誤報）が増えます。")
    al = gl.alerts(KT.set_index("月")["来訪数"], window=3, k=k)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=al.index, y=al["上限"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=al.index, y=al["下限"], fill="tonexty", line=dict(width=0),
                             fillcolor="rgba(63,124,172,.15)", name="いつもの幅"))
    fig.add_trace(go.Scatter(x=al.index, y=al["値"], mode="lines+markers", name="来訪数",
                             marker=dict(color=np.where(al["アラート"], "#d6453d", "#3f7cac"), size=10)))
    fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch")
    n_al = int(al["アラート"].sum())
    st.caption(f"アラート {n_al} 件。アラートは「調べに行け」の合図で、「異常だ」という結論ではありません。"
               "数字を見てから慌てるのではなく、数字で先に知っておくための仕組みです。")

# ═════════════════════════════════════════════
# 3. 探す
# ═════════════════════════════════════════════
with tab_e:
    st.header("🔍 ③ 探す：課題を見つけ、原因の仮説を立てる")
    st.write("探索的分析は「答えを出す」のではなく「確かめる価値のある仮説を見つける」段階です。")

    X = VF[gl.FEATURES].to_numpy(float)
    st.subheader("指標どうしの相関")
    corr = VF[gl.FEATURES].corr()
    fig = px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu", zmin=-1, zmax=1, aspect="auto")
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch")
    st.caption("来訪回数と合計金額は強く結びつきます。でも「何度も来たから買った」のか"
               "「買う人だから何度も来た」のかは、相関だけでは分かりません。")

    st.subheader("来訪者のタイプ分け（k-means）と、2次元への要約（主成分分析）")
    c1, c2 = st.columns([1, 2])
    with c1:
        el = gl.elbow(X, 6)
        fig = px.line(el, x="k", y="群内平方和", markers=True, title="エルボー：折れ曲がる所が目安")
        fig.update_layout(height=260, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, width="stretch")
        kk = st.slider("タイプの数 k", 2, 6, 3)
    lab, _ = gl.kmeans(X, kk)
    sc, var, load = gl.pca(X)
    VF2 = VF.assign(タイプ=[f"タイプ{i + 1}" for i in lab], 第1主成分=sc[:, 0], 第2主成分=sc[:, 1])
    with c2:
        fig = px.scatter(VF2, x="第1主成分", y="第2主成分", color="タイプ", hover_data=gl.FEATURES + ["経路"],
                         title=f"主成分で見た来訪者（2軸で情報の {var.sum():.0%} を保持）")
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, width="stretch")
    prof = VF2.groupby("タイプ")[gl.FEATURES].mean().round(1)
    prof.insert(0, "人数", VF2.groupby("タイプ").size())
    st.dataframe(prof, width="stretch")
    st.caption("タイプ番号は合計金額の小さい順。表を見て、それぞれに名前をつけてみましょう"
               "（例：「一度きりの見学」「体験は好きだが買わない」「常連」）。")
    with st.expander("主成分の中身（負荷量）"):
        st.dataframe(pd.DataFrame(load.T, index=gl.FEATURES, columns=["第1主成分", "第2主成分"]).round(2),
                     width="stretch")

    st.subheader("ベイズで逆に読む：買った人は、どこから来た人か")
    buyer = VF["購入回数"] > 0
    prior = VF["経路"].value_counts(normalize=True).reindex(gl.ROUTES).fillna(0)
    like = VF.loc[buyer, "経路"].value_counts(normalize=True).reindex(gl.ROUTES).fillna(0)
    p_buy = buyer.mean()
    post = (like * p_buy / prior.replace(0, np.nan)).fillna(0)
    bt = pd.DataFrame({"P(経路)：全体での割合": prior, "P(経路 | 買った)": like, "P(買った | 経路)": post})
    st.dataframe(bt.style.format("{:.0%}"), width="stretch")
    st.latex(r"P(\text{買う}\mid\text{経路})=\frac{P(\text{経路}\mid\text{買う})\,P(\text{買う})}{P(\text{経路})}")
    best_r = post.idxmax()
    st.caption(f"「{best_r}」から来た人の購入率が最も高い。ただし経路は**くじで決まっていない**ので、"
               "経路そのものの効果か、そもそも買う気のある人がその経路を通るのかは区別できません。"
               "→ 原因を確かめるには、くじで配ったもの（チラシ）を ④ で比べます。")

# ═════════════════════════════════════════════
# 4. 確かめる
# ═════════════════════════════════════════════
with tab_t:
    st.header("⚖️ ④ 確かめる：チラシAとB、差は偶然か")
    st.write("チラシは来訪者に**くじで**配っています。くじで分けたものの差なら、原因として言える可能性が出てきます。")
    c1, c2 = st.columns(2)
    base = c1.selectbox("どの段まで来た人の中で", gl.STEPS[:-1], index=2)
    step = c2.selectbox("どの段まで進んだ割合を比べるか", gl.STEPS[gl.STEPS.index(base) + 1:], index=0)
    ab = gl.ab_table(EV, step=step, base=base)
    st.dataframe(ab.style.format({"割合": "{:.0%}", "人数": "{:.0f}", "成功": "{:.0f}"}), width="stretch")

    na, sa = int(ab.loc[gl.FLYERS[0], "人数"]), int(ab.loc[gl.FLYERS[0], "成功"])
    nb, sb = int(ab.loc[gl.FLYERS[1], "人数"]), int(ab.loc[gl.FLYERS[1], "成功"])
    if min(na, nb) < 5:
        st.warning("どちらかのチラシの人数が少なすぎて比べられません。")
    else:
        y = np.r_[np.ones(sa), np.zeros(na - sa), np.ones(sb), np.zeros(nb - sb)]
        g = np.r_[np.zeros(na), np.ones(nb)]
        obs, pval, null = gl.permutation_test(y, g, 5000)
        prob, pa, pb = gl.prob_b_beats_a(sa, na, sb, nb)

        m1, m2, m3 = st.columns(3)
        m1.metric("差（B − A）", f"{obs:+.0%}")
        m2.metric("くじを引き直して同じくらいの差が出る割合（p）", f"{pval:.3f}")
        m3.metric("BのほうがAより良い確率（ベイズ）", f"{prob:.0%}")

        c1, c2 = st.columns(2)
        with c1:
            fig = px.histogram(x=null, nbins=40, title="① 頻度論：チラシを配り直した5000回の差")
            fig.add_vline(x=obs, line_color="#d6453d", annotation_text="実際の差")
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=40, b=10), showlegend=False,
                              xaxis_title="差", yaxis_title="回数")
            st.plotly_chart(fig, width="stretch")
        with c2:
            fig = go.Figure()
            for name, smp in [(gl.FLYERS[0], pa), (gl.FLYERS[1], pb)]:
                fig.add_trace(go.Histogram(x=smp, nbinsx=60, name=name, opacity=.6,
                                           marker_color=FLYER_COLORS[name], histnorm="probability density"))
            fig.update_layout(barmode="overlay", height=300, margin=dict(l=10, r=10, t=40, b=10),
                              title="② ベイズ：本当の割合がどこにありそうか", xaxis_title="割合")
            st.plotly_chart(fig, width="stretch")
        st.caption("p が小さいほど「偶然だけでは出にくい差」。ベイズの確率は「Bが上である」ことへの確信の度合い。"
                   "二つは問いが違うので、両方を読み比べてみましょう。")

    with st.expander("この比べ方の限界"):
        st.markdown(
            "- 同じ人が何度来ても、1人1回として数えています（同じ人の回を独立に数えない）\n"
            "- いろいろな段の組み合わせを試していくと、偶然の差を「発見」しやすくなります（多重比較）。"
            "**どこを比べるかは、データを見る前に決めておく**のが原則です\n"
            "- くじで配っていない「経路」の差は、ここでは原因として扱いません（③の注意）"
        )

# ═════════════════════════════════════════════
# 5. AIアプリ・判断する
# ═════════════════════════════════════════════
with tab_j:
    st.header("🤖 ⑤ AIアプリ・判断する")
    st.write("ゲームの「きめ細やかな運営」は、相手ごとに次の一手を変えることです。"
             "ここでは、それを行う **AIおすすめ係** と、分析の読み取りを手伝う **AI家庭教師** を動かします。")
    j_intro, j_ai, j_tutor, j_sheet = st.tabs([
        "🎰 バンディット入門", "🤖 AIおすすめ係", "💬 AI家庭教師", "📝 マイ判断シート"])

    # ── 入門：相手を見ないバンディット ─────────────
    with j_intro:
        st.subheader("A/Bテストで決めるか、試しながら寄せていくか")
        st.write("A/Bテストは「全部を同じだけ試してから決める」方法。ゲームのきめ細やかな運営では、"
                 "**良さそうなものに少しずつ寄せながら試し続ける**方法（多腕バンディット）もよく使われます。"
                 "これは強化学習のいちばん小さな形で、中身はベイズ推論です。")
        cols = st.columns(3)
        tp = [cols[i].slider(f"「{m}」体験の本当の満足率（仮定）", 0.05, 0.95, v, 0.05)
              for i, (m, v) in enumerate(zip(gl.MENUS, [0.70, 0.55, 0.40]))]
        rounds = st.slider("勧める回数", 50, 1000, 300, 50)
        bs = gl.bandit_sim(tp, rounds, seed=7)
        c1, c2 = st.columns(2)
        with c1:
            fig = px.line(bs, x="回", y=["トンプソン抽出", "均等配分"],
                          title="取りこぼした満足の累計（小さいほど良い）")
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=40, b=10), legend_title="")
            st.plotly_chart(fig, width="stretch")
        with c2:
            share = (pd.Series(bs["選んだメニュー"]).map(dict(enumerate(gl.MENUS)))
                     .groupby(pd.cut(bs["回"], 5)).value_counts(normalize=True).unstack(fill_value=0))
            share.index = [f"{int(i.left) + 1}–{int(i.right)}回" for i in share.index]
            fig = px.bar(share, title="トンプソン抽出が勧めたメニューの割合の移り変わり")
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=40, b=10), legend_title="", yaxis_title="割合")
            st.plotly_chart(fig, width="stretch")
        st.caption("最初はばらばらに試し、だんだん満足率の高いメニューに寄っていきます。"
                   "でも、本当は「相手によって一番良いメニューが違う」としたら？ → 次のタブへ。")

    # ── AIおすすめ係：文脈付きバンディット ─────────
    with j_ai:
        st.subheader("🤖 AIおすすめ係：相手を見て、次の体験メニューを勧める")
        st.write("来訪者の **経路・来訪回数・前回どこまで進んだか** を見て、パン焼き・収穫・土づくりのどれを勧めるかを"
                 "AIが決めます。結果（満足したか）を受け取るたびに、AIは自分の考えを更新します。")
        with st.expander("このAIのしくみ（文脈付きトンプソン抽出）"):
            st.markdown(
                "1. 来訪者の状況を数のならび **x**（文脈）にする：" + "・".join(gl.CTX_NAMES[1:]) + "\n"
                "2. メニューごとに「満足の見込み = 重み・x」というベイズ線形回帰を持つ。重みは分布（迷い）で持つ\n"
                "3. 分布から重みを1組ずつ引いて、見込みが一番大きいメニューを勧める（迷っているうちは色々試す）\n"
                "4. 結果で、勧めたメニューの分布だけを更新する（ベイズ更新）\n\n"
                "深層強化学習（DQNなど）は数十万回の試行が要ります。農園に来る人は年に数百人なので、"
                "このくらい小さく、中身が説明できるモデルのほうが早く賢くなります。"
            )
            st.latex(r"\text{見込み}_{a}(x)=x^\top\theta_a,\quad \theta_a \sim \mathcal{N}(A_a^{-1}b_a,\ \sigma^2 A_a^{-1})"
                     r",\quad A_a \leftarrow A_a + xx^\top,\ b_a \leftarrow b_a + r\,x")

        st.markdown("##### ① シミュレーション：相手を見ると、どれだけ違うか")
        sim_n = st.slider("来訪者の数", 100, 1500, 400, 100, key="gl_sim_n")
        SIM = gl.contextual_sim(sim_n, seed=int(seed))
        st.session_state.gl_sim = SIM
        c1, c2 = st.columns([3, 2])
        with c1:
            fig = px.line(SIM, x="回", y=["文脈付きAI", "文脈なしAI", "順番に回す"],
                          title="取りこぼした満足の累計（小さいほど良い）")
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=40, b=10), legend_title="")
            st.plotly_chart(fig, width="stretch")
        with c2:
            last = SIM.iloc[-1]
            st.metric("文脈付きAIの取りこぼし", f"{last['文脈付きAI']:.1f}",
                      f"{last['文脈付きAI'] - last['文脈なしAI']:+.1f}（文脈なしAIと比べて）", delta_color="inverse")
            st.metric("文脈付きAIが本当の正解を選んだ割合", f"{last['文脈付きAIの正解率']:.0%}")
            st.caption("架空の「本当の満足のしくみ」では、学校経由の初回は収穫、常連はパン焼き、"
                       "口コミの初回は土づくりが一番になるように作ってあります。")

        st.markdown("##### ② AIの頭の中：代表的な来訪者に、何を勧めるか")
        if "gl_ai" not in st.session_state:
            st.session_state.gl_ai = gl.pretrain(200, seed=int(seed))
            st.session_state.gl_ai_fb = 0
        AI: gl.LinearThompson = st.session_state.gl_ai
        c1, c2, c3 = st.columns(3)
        n_pre = c1.number_input("前もって学ばせる人数", 0, 3000, 200, 100,
                                help="架空の来訪者でAIに経験を積ませます。0にすると何も知らないAIになります。")
        if c2.button("この人数で学び直す", width="stretch"):
            st.session_state.gl_ai = AI = gl.pretrain(int(n_pre), seed=int(seed))
            st.session_state.gl_ai_fb = 0
        c3.metric("AIの経験（人）", f"{int(AI.n.sum()):,}",
                  f"うち本物のフィードバック {st.session_state.gl_ai_fb}" if st.session_state.gl_ai_fb else None)
        pt = gl.persona_table(AI)
        st.dataframe(pt.style.format({c: "{:.0%}" for c in pt.columns if c.startswith("P(") or c == "その確信"}),
                     width="stretch", hide_index=True)
        st.caption(f"一致 {int((pt['一致'] == '✅').sum())}/{len(pt)}。本当の満足率が僅差の相手ほど、AIは迷います"
                   "（確信が低い）。学ばせる人数を0・50・1000と変えて、表がどう変わるか見てみましょう。")

        st.markdown("##### ③ 使ってみる：今日の来訪者に勧める")
        c1, c2, c3 = st.columns(3)
        route = c1.selectbox("経路", gl.ROUTES, key="gl_ai_route")
        nv = c2.number_input("来訪回数（今日を含む）", 1, 20, 1, 1, key="gl_ai_nv")
        prev = c3.checkbox("前回パン焼きまで進んだ", key="gl_ai_prev", disabled=nv == 1)
        x = gl.context(route, int(nv), bool(prev) and nv > 1)
        rng = np.random.default_rng()
        if st.button("🤖 AIに聞く", type="primary"):
            st.session_state.gl_ai_pick = (AI.choose(x, rng), x.tolist())
            sg.log_event("bandit_recommend", "INFO", page=PAGE)
        pick = st.session_state.get("gl_ai_pick")
        if pick and pick[1] == x.tolist():
            arm = pick[0]
            pb = AI.prob_best(x, rng)
            mean, sd = AI.posterior(x)
            st.success(f"おすすめ：**{gl.MENUS[arm]}体験**")
            fig = go.Figure()
            fig.add_trace(go.Bar(x=gl.MENUS, y=pb, name="一番である確率",
                                 marker_color=["#3f7cac" if i == arm else "#b8c7d6" for i in range(len(gl.MENUS))]))
            fig.update_layout(height=240, margin=dict(l=10, r=10, t=30, b=10), yaxis_tickformat=".0%",
                              title="AIの迷い：それぞれが一番である確率")
            st.plotly_chart(fig, width="stretch")
            st.caption("見込み（平均±標準偏差）：" + "、".join(
                f"{m} {mu:.2f}±{s:.2f}" for m, mu, s in zip(gl.MENUS, mean, sd)))
            st.write("体験のあと、結果をAIに教えてください（ここで教えた分だけ、AIが学びます）。")
            f1, f2, f3 = st.columns(3)
            if f1.button("😊 満足だった", width="stretch"):
                AI.update(arm, x, 1.0)
                st.session_state.gl_ai_fb += 1
                st.session_state.gl_ai_pick = None
                st.rerun()
            if f2.button("😐 いまいちだった", width="stretch"):
                AI.update(arm, x, 0.0)
                st.session_state.gl_ai_fb += 1
                st.session_state.gl_ai_pick = None
                st.rerun()
            if f3.button("🎲 架空の結果で答える", width="stretch",
                         help="架空の「本当の満足のしくみ」からサイコロを振って答えます（練習用）。"):
                AI.update(arm, x, float(rng.random() < gl.true_p(x)[arm]))
                st.session_state.gl_ai_fb += 1
                st.session_state.gl_ai_pick = None
                st.rerun()
        st.caption("AIのおすすめは「候補」です。体調・天候・アレルギーなど、AIが知らない事情は人が判断します"
                   "（Human-in-the-Loop）。学習結果はこの画面を閉じると消えます（サーバーに残しません）。")

    # ── AI家庭教師：生成AI ─────────────────────
    with j_tutor:
        st.subheader("💬 AI家庭教師：分析結果の読み方を一緒に考える")
        st.write("このページで計算した **数字の要約だけ** を生成AIに渡し、質問に答えてもらいます。"
                 "AIは答えを決めず、最後に考えるための問いを返します。")
        SUMMARY = gl.tutor_summary(EV, st.session_state.get("gl_sim"))
        with st.expander("AIに渡すデータ（これだけ。来訪ログの文字そのものは渡しません）"):
            st.json(SUMMARY)
        q = st.text_area("質問（300字まで）", key="gl_q", max_chars=gl.MAX_QUESTION, height=90,
                         placeholder="例：チラシBのほうが良いと言ってよいですか？ 売上が下がった月の原因は何でしょう？")
        has_ai = gl_ai_ready()
        c1, c2 = st.columns([1, 3])
        if c1.button("💬 AIに質問する", type="primary", disabled=not (has_ai and q.strip())):
            if sg.ai_quota_ok(PAGE):
                try:
                    with st.spinner("AIが数字を読んでいます…"):
                        st.session_state.gl_ans = gl.ask_tutor(q, SUMMARY, AI_MODEL, api_key())
                except Exception as e:  # noqa: BLE001
                    sg.log_event("ai_error", "WARNING", page=PAGE, error=type(e).__name__)
                    st.error("AIの呼び出しに失敗しました。下のヒントを使ってください。")
        if not has_ai:
            c2.caption("※ `ANTHROPIC_API_KEY` が設定されていないため、AIへの質問は使えません。"
                       "代わりに、決まった規則で数字を読んだヒントを出します。")
        if st.session_state.get("gl_ans"):
            with st.container(border=True):
                st.markdown(st.session_state.gl_ans)
            st.caption("AIの答えは間違うことがあります。必ず上のタブのグラフ・数字と照らし合わせてください"
                       "（情報の妥当性を確かめる練習）。")
        st.markdown("##### 🧩 数字から読めるヒント（AIなしでも動きます）")
        for h in gl.offline_tutor(SUMMARY):
            st.markdown(f"- {h}")
        with st.expander("🔒 生成AIを安全に使うための工夫（セキュリティの教材）"):
            st.markdown(
                "- **プロンプトインジェクション対策**：読み込んだCSVの文字（経路名など）はAIに渡さない。"
                "渡すのは決まった語彙のラベルと数字だけ。質問文の `<` `>` は無効化する\n"
                "- **役割の固定**：AIへの約束（システムプロンプト）で、データ中の指示に従わないよう決めておく\n"
                "- **出力の検査**：AIの返事のリンクは表示しない（偽サイトへの誘導を防ぐ）。長さも制限する\n"
                "- **使いすぎ防止**：1回の訪問・1日あたりの呼び出し回数に上限（APIキーの不正利用対策）\n"
                "- **記録**：呼び出しは匿名のセキュリティログに残す（質問の中身は残さない）"
            )

    # ── マイ判断シート ───────────────────────
    with j_sheet:
        st.subheader("📝 マイ判断シート：自分の条件で決める")
        st.write("答えは人によって違ってよい。自分の農園・自分の体験会の条件を入れてください。")
        c1, c2, c3 = st.columns(3)
        cap = c1.number_input("1回の体験会の定員（人）", 5, 200, 20, 5)
        per_month = c2.number_input("1か月の体験会の回数", 1, 20, 2, 1)
        months_ok = c3.number_input("結論を出すまで待てる月数", 1, 24, 6, 1)
        c4, c5 = st.columns(2)
        _now = FU.loc[3, "前の段からの残存率"] if len(FU) > 3 else np.nan  # 収穫→パン焼き の残存率
        _now = round(float(np.clip(_now, 0.05, 0.95)) * 20) / 20 if pd.notna(_now) else 0.60
        p0 = c4.slider("今の割合（例：収穫からパン焼きまで進む割合）", 0.05, 0.95, _now, 0.05)
        lift = c5.slider("見つけたい改善の大きさ（ポイント）", 0.02, 0.30, 0.10, 0.01)
        need = gl.sample_size_per_group(p0, lift) * 2
        have = int(cap * per_month * months_ok)
        m1, m2, m3 = st.columns(3)
        m1.metric("A/Bテストに要る人数（2群合計）", f"{need:,} 人")
        m2.metric("待てる期間に集まる人数", f"{have:,} 人")
        m3.metric("足りるまでの月数", f"{need / (cap * per_month):.1f} か月")
        if have >= need:
            st.success("期間内にA/Bテストで決着がつきそうです。比べる段と判定の基準を、データを見る前に書き残しましょう。")
        else:
            st.warning("この条件ではA/Bテストで決着がつく前に期間が終わります。"
                       "①見つけたい差を大きくする（小さな改善は狙わない）②期間を延ばす"
                       "③AIおすすめ係（バンディット）で寄せながら運営する、のどれを選ぶかを書いてください。")
        st.text_area("自分の判断と、その理由（数字を1つ以上入れる）", key="gl_note", height=120,
                     placeholder="例：定員20人×月2回だと12か月かかる。小さな改善を確かめるより、"
                                 "AIおすすめ係で相手ごとに寄せながら、半年後に満足率を見直す。")
        st.caption("この欄の文章はサーバーに保存されません。必要ならコピーして手元に残してください。")

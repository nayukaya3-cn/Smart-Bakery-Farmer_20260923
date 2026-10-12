"""
比べて確かめる探究 ─ 寒さに当てたほうれん草は甘くなるか
配置先: pages/3_⚖️_比べて確かめる探究.py （Streamlit のマルチページ構成）

骨格はリポジトリ共通の3段構えに「比べる」を足した4段：
  ① 測る（くじで区を分け、糖度を記録）→ ② 比べる（列ごとにまとめ、差と幅を出す）
  → ③ グラフにする（株のばらつきと、日ごとの差）→ ④ 自分で判断する（いつ収穫するか）
  発展：すでにある地域データ（農水省「地域の農業を見て・知って・活かすDB」）で比べ、
        「くじで分けた比較」と「すでにあるデータでの比較」の違いを体験する。

方針
  - 計算は compare_lab.py（`python compare_lab.py` で自己チェック）。
  - 初期表示はすべて架空データ（実測ではありません）。
  - アップロードした記録はセッション内だけで使い、サーバーには残さない。
  - 生徒の氏名は扱わない。外部の生成AIは呼び出さない。
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import compare_lab as cl
import security_guard as sg

st.set_page_config(page_title="比べて確かめる探究", page_icon="⚖️", layout="wide")

import social as sn  # noqa: E402  SNSのURLは social.py で一括管理

DATA = Path(__file__).parent.parent / "data"
UPDATED = "2026-10-13"
DB_URL = "https://www.maff.go.jp/j/tokei/census/shuraku_data/index.html"
COLORS = {cl.TREAT: "#3f7cac", cl.CONTROL: "#c98a2b"}
PAGE = "compare"


def load_sample_brix() -> pd.DataFrame:
    path = DATA / "sample_spinach_brix.csv"
    df = pd.read_csv(path) if path.exists() else cl.sample_brix()
    return cl.normalize_brix(df)


def load_sample_did() -> pd.DataFrame:
    path = DATA / "sample_shuraku_did.csv"
    df = pd.read_csv(path) if path.exists() else cl.sample_did()
    return cl.normalize_did(df)


if "cmp_brix" not in st.session_state:
    st.session_state.cmp_brix = load_sample_brix()   # 表の元データ（読み込み・切り替え時だけ変わる）
    st.session_state.cmp_is_sample = True
    st.session_state.cmp_ver = 0                      # 元データを替えたら表の入力欄を作り直す


def set_brix(df: pd.DataFrame, is_sample: bool) -> None:
    st.session_state.cmp_brix = df
    st.session_state.cmp_is_sample = is_sample
    st.session_state.cmp_ver += 1
if "cmp_did" not in st.session_state:
    st.session_state.cmp_did = load_sample_did()
    st.session_state.cmp_did_is_sample = True

# ─────────────────────────────────────────────
# サイドバー：保存・復元
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("⚖️ 記録の保存・復元")
    st.caption("終わったら必ずCSVで保存してください（公開ページには残りません）。")
    st.caption("保存は「📏 ① 測る」タブの「糖度の記録をCSVで保存」から。")
    up = st.file_uploader("糖度の記録CSVを読み込む", type="csv", key="up_cmp_brix",
                          help=f"列：{', '.join(cl.BRIX_COLS)}")
    if up is not None and st.session_state.get("cmp_loaded") != up.file_id:
        _df = sg.read_csv_safely(up, page=PAGE, kind="brix")
        if _df is not None:
            set_brix(cl.normalize_brix(_df), False)
        st.session_state.cmp_loaded = up.file_id
    st.divider()
    if st.button("記入例（架空）に戻す", width="stretch"):
        set_brix(load_sample_brix(), True)
    if st.button("空の記録から始める", width="stretch"):
        set_brix(cl.normalize_brix(pd.DataFrame(columns=cl.BRIX_COLS)), False)
    st.divider()
    sn.buttons("で相談する", stacked=True)

BRIX: pd.DataFrame = st.session_state.cmp_brix   # ① 測る の表で編集した後の値に置き換わる

st.title("⚖️ 比べて確かめる探究")
st.caption("寒さに当てたほうれん草は甘くなるか ── 測る・比べる・グラフにする・自分で判断する")
if st.session_state.cmp_is_sample:
    st.info("いま表示しているのは **架空の記入例** です（実測ではありません）。"
            "サイドバーの「空の記録から始める」か、記録CSVの読み込みで切り替えます。")

tab_flow, tab_m, tab_c, tab_g, tab_j, tab_ext = st.tabs([
    "🧭 この探究の流れ", "📏 ① 測る", "⚖️ ② 比べる", "📈 ③ グラフにする", "🧭 ④ 判断する",
    "🗾 発展：地域データと比べる",
])

# ═════════════════════════════════════════════
# 0. 流れ
# ═════════════════════════════════════════════
with tab_flow:
    st.header("🧭 「寒さで甘くなった」と言えるのは、どんなときか")
    st.write("寒さ以外の条件がそろった野菜と比べたときだけです。そこで、畑の中に"
             f"**{cl.TREAT}** と **{cl.CONTROL}** を作り、くじで列を割り振ります。")
    st.dataframe(pd.DataFrame([
        ("📏 ① 測る", "くじで列を区に分ける。糖度計で1列3株以上を測る",
         "くじの記録・糖度の記録", "調べたいこと以外をそろえる"),
        ("⚖️ ② 比べる", "株ではなく列ごとにまとめ、2区の差と、その幅を出す",
         "差・95%の幅・くじを引き直したときの出やすさ", "一株だけで決めない"),
        ("📈 ③ グラフにする", "株の値を点で並べ、測定日ごとの差の変化を見る",
         "点のグラフ・差の推移", "平均だけでなく、ばらつきを見る"),
        ("🧭 ④ 判断する", "目標の糖度と自分の条件から、いつ収穫するかを決める",
         "判断ワークシート", "答えは人によって違ってよい"),
    ], columns=["段", "やること", "残る記録", "身につけること"]), width="stretch", hide_index=True)

    st.subheader("二つの物差し")
    st.dataframe(pd.DataFrame([
        ("使うもの", "同じ品種・同じ日にまいたほうれん草を2区に分ける",
         "農林水産省「地域の農業を見て・知って・活かすDB」"),
        ("分かること", "寒さが糖度を上げるか、どれくらい上げるか",
         "地域の農家数・耕地がどう変わってきたか"),
        ("分からないこと", "他の畑や他の年でも同じになるか", "野菜の甘さ（糖度は調べられていない）"),
        ("区の分け方", "くじ（ランダム）", "くじではない（交付金は条件の厳しい集落ほど受けやすい）"),
    ], columns=["", "畑の中の実験（①〜④）", "地域データ（発展タブ）"]), width="stretch", hide_index=True)
    st.caption("地域データは、畑の実験の「比べる相手（対照）」にはなりません。測っているもの・単位・時期が違うためです。")

    st.subheader("90分の当日の流れ（例）")
    st.dataframe(pd.DataFrame([
        ("0–15分", "安全説明・体調確認／食べ比べで予想（どちらの区か知らせずに）", "① 測る"),
        ("15–40分", "糖度計で測る（1区あたり4列×3株）", "① 測る"),
        ("40–60分", "列ごとにまとめて差を出し、点のグラフにする", "② 比べる・③ グラフにする"),
        ("60–90分", "「差は寒さのせいと言えるか」「自分ならいつ収穫するか」を書いて発表", "④ 判断する"),
    ], columns=["時間", "内容", "このページのタブ"]), width="stretch", hide_index=True)
    st.caption("比べる区は種まき（10月下旬〜11月上旬）から用意が要ります。"
               "当日だけ参加する場合は、指導者の畑で用意した2区を持ち込みます。")

# ═════════════════════════════════════════════
# 1. 測る
# ═════════════════════════════════════════════
with tab_m:
    st.header("📏 ① 測る：くじで分けて、記録する")

    st.subheader("くじで列を区に割り振る")
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        n_rows = st.number_input("畝の列の数", min_value=2, max_value=40, value=8, step=1)
    with c2:
        seed = st.number_input("くじの番号（生徒が決める）", min_value=0, max_value=9999, value=42, step=1,
                               help="同じ番号なら、何度やっても同じ割り振りになります。番号は記録に残します。")
    plan = cl.assign_rows(int(n_rows), int(seed))
    with c3:
        fig = go.Figure(go.Bar(
            x=plan["列"], y=[1] * len(plan), marker_color=plan["区"].map(COLORS),
            text=plan["区"].str.replace("区", ""), textposition="inside", hoverinfo="x+text"))
        fig.update_layout(height=170, margin=dict(l=10, r=10, t=10, b=30), showlegend=False,
                          yaxis=dict(visible=False), xaxis=dict(title="列（畑の端から）", dtick=1))
        st.plotly_chart(fig, width="stretch")
    st.caption("くじで分けると、日当たりや土の違いが偶然どちらかの区に偏ることはあっても、"
               "「わざと良い列を選ぶ」ことは起きません。")
    st.download_button("くじの記録をCSVで保存",
                       sg.safe_csv(plan.assign(くじの番号=int(seed))), f"くじの記録_{int(seed)}.csv", "text/csv")

    st.subheader("糖度を記録する")
    st.caption("1行＝1株。区は「くじの記録」と同じにします。糖度はBrix（%）。")
    edited = st.data_editor(
        st.session_state.cmp_brix, num_rows="dynamic", width="stretch",
        key=f"cmp_editor_{st.session_state.cmp_ver}",
        column_config={
            "測定日": st.column_config.DateColumn(required=True),
            "列": st.column_config.NumberColumn(min_value=1, max_value=40, step=1, required=True),
            "区": st.column_config.SelectboxColumn(options=list(cl.GROUPS), required=True),
            "株": st.column_config.NumberColumn(min_value=1, step=1),
            "糖度": st.column_config.NumberColumn("糖度（Brix %）", min_value=0.0, max_value=30.0,
                                                step=0.1, format="%.1f"),
        })
    BRIX = cl.normalize_brix(edited)
    st.download_button("糖度の記録をCSVで保存", sg.safe_csv(BRIX), "糖度の記録.csv", "text/csv")

    issues = cl.problems_brix(BRIX)
    if issues.empty:
        st.success(f"記録 {len(BRIX)} 行：記入漏れ・ありえない値・区の取り違えは見つかりませんでした。")
    else:
        st.warning(f"確認が必要な行が {issues['行'].nunique()} 行あります。")
        st.dataframe(issues, width="stretch", hide_index=True)

    with st.expander("測るときの約束"):
        st.markdown(
            "- 同じ日の同じ時間帯に測る（朝と夕方で糖度が変わることがあります）\n"
            "- 葉の同じ部分（葉柄の付け根に近い所など）を、毎回同じやり方で絞る\n"
            "- 糖度計は測るたびに水で0合わせをする\n"
            "- できれば、測る人はどちらの区か知らないまま測る（思い込みで読み取りがずれないように）"
        )

DATES = sorted(BRIX["測定日"].dropna().unique())
RM = cl.row_means(BRIX)

# ═════════════════════════════════════════════
# 2. 比べる
# ═════════════════════════════════════════════
with tab_c:
    st.header("⚖️ ② 比べる：くじを引いた単位で数える")
    if not DATES:
        st.info("① 測る で記録を入れると、ここで比べられます。")
    else:
        date = st.selectbox("比べる測定日", DATES, index=len(DATES) - 1, key="cmp_date")
        day = RM[RM["測定日"] == date]
        n_plants = cl.naive_plant_count(BRIX, date)
        st.write(f"この日の記録は **{n_plants} 株** ですが、くじを引いたのは **列** なので、"
                 f"比べる単位は **{len(day)} 列** です。同じ列の株は土や日当たりが似ているため、"
                 "株を別々に数えると、データが実際より多く見えてしまいます。")
        try:
            c = cl.compare(day)
        except ValueError as e:
            st.warning(f"比べられません：{e}")
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric(f"{cl.TREAT}（列の平均）", f"{c.mean_treat:.1f} %")
            m2.metric(f"{cl.CONTROL}（列の平均）", f"{c.mean_control:.1f} %")
            m3.metric("差", f"{c.diff:+.1f} ポイント")
            m4.metric("差の幅（95%）", f"{c.ci_low:+.1f} 〜 {c.ci_high:+.1f}")
            st.markdown(
                f"**くじを引き直しても、これくらいの差が出るか**：区の名前をでたらめに付け替えて "
                f"{c.n_perm:,} 回計算すると、今回以上の差が出たのは約 **{c.p_value:.0%}** でした。"
                "小さいほど「偶然のくじの偏りだけでは説明しにくい」ことを表します。"
            )
            if c.ci_low > 0:
                st.success("差の幅がすべてプラス側にあります。この畑・この冬では、"
                           f"{cl.TREAT}のほうが甘いと言えそうです。")
            elif c.ci_high < 0:
                st.success(f"差の幅がすべてマイナス側にあります。{cl.CONTROL}のほうが甘いと言えそうです。")
            else:
                st.info("差の幅が0をまたいでいます。この記録だけでは、どちらが甘いとは言えません。")
            st.caption(f"各区 {c.n_treat}・{c.n_control} 列では、どんなに差があっても"
                       "「くじを引き直したときの出やすさ」はある値より小さくなりません"
                       "（4列ずつなら約3%）。確かめたいなら、列を増やします。")
            st.dataframe(day.rename(columns={"糖度": "糖度（列の平均）"}).round(2),
                         width="stretch", hide_index=True)

        st.subheader("測定日ごとの比較")
        by_date = cl.compare_by_date(BRIX)
        if not by_date.empty:
            st.dataframe(by_date.round(2), width="stretch", hide_index=True)
            st.download_button("比較の表をCSVで保存", sg.safe_csv(by_date.round(3)),
                               "測定日ごとの比較.csv", "text/csv")

# ═════════════════════════════════════════════
# 3. グラフにする
# ═════════════════════════════════════════════
with tab_g:
    st.header("📈 ③ グラフにする：平均だけでなく、ばらつきを見る")
    if not DATES:
        st.info("① 測る で記録を入れると、ここにグラフが出ます。")
    else:
        d = BRIX.dropna(subset=["糖度", "区", "測定日"]).copy()
        d["測定日"] = d["測定日"].astype(str)
        fig = px.strip(d, x="区", y="糖度", color="区", facet_col="測定日",
                       color_discrete_map=COLORS, hover_data=["列", "株"],
                       category_orders={"区": list(cl.GROUPS)})
        rm = RM.copy()
        rm["測定日"] = rm["測定日"].astype(str)
        for i, dd in enumerate(sorted(rm["測定日"].unique()), start=1):
            for g in cl.GROUPS:
                mean = rm[(rm["測定日"] == dd) & (rm["区"] == g)]["糖度"].mean()
                if pd.notna(mean):
                    fig.add_trace(go.Scatter(x=[g], y=[mean], mode="markers", showlegend=False,
                                             marker=dict(symbol="line-ew-open", size=40, color="#22313f",
                                                         line=dict(width=3)),
                                             hovertemplate=f"{g} の平均 %{{y:.1f}}<extra></extra>"),
                                  row=1, col=i)
        fig.update_layout(height=420, showlegend=False, margin=dict(t=40, b=10))
        fig.update_yaxes(title_text="糖度（Brix %）", col=1)
        fig.update_xaxes(title_text="")
        fig.for_each_annotation(lambda a: a.update(text=a.text.replace("測定日=", "")))
        st.plotly_chart(fig, width="stretch")
        st.caption("点＝1株、横棒＝列の平均の平均。点の重なり具合が、差の確かさの見た目の手がかりです。")

        by_date = cl.compare_by_date(BRIX)
        if len(by_date) >= 2:
            st.subheader("差は、寒さに当てるほど開いたか")
            bd = by_date.copy()
            bd["測定日"] = bd["測定日"].astype(str)
            fig2 = go.Figure(go.Scatter(
                x=bd["測定日"], y=bd["差"], mode="lines+markers", line=dict(color=COLORS[cl.TREAT]),
                error_y=dict(type="data", symmetric=False,
                             array=bd["差_上限95"] - bd["差"], arrayminus=bd["差"] - bd["差_下限95"]),
                hovertemplate="%{x}<br>差 %{y:+.1f}<extra></extra>"))
            fig2.add_hline(y=0, line_dash="dot", line_color="#888")
            fig2.update_layout(height=320, margin=dict(t=10, b=10),
                               yaxis_title=f"差（{cl.TREAT} − {cl.CONTROL}、ポイント）")
            st.plotly_chart(fig2, width="stretch")
            st.caption("縦線は差の95%の幅。0の点線にかかっている日は、まだ差があるとは言えません。")

# ═════════════════════════════════════════════
# 4. 判断する
# ═════════════════════════════════════════════
with tab_j:
    st.header("🧭 ④ 自分で判断する")
    st.subheader("問い1：差は「寒さのせい」と言えるか")
    st.caption("当てはまるものにチェックします。チェックが少ないほど、寒さ以外の理由が残ります。")
    checks = {
        "同じ品種・同じ日にまいた": True,
        "列はくじで区に割り振った": True,
        "水やり・肥料は2区で同じにした": True,
        "同じ日・同じ時間帯に、同じやり方で測った": True,
        "測る人は、どちらの区か知らずに測った": False,
        "差の幅（95%）が0をまたいでいない": False,
    }
    by_date = cl.compare_by_date(BRIX) if DATES else pd.DataFrame()
    if not by_date.empty:
        checks["差の幅（95%）が0をまたいでいない"] = bool(by_date.iloc[-1]["差_下限95"] > 0)
    ticked = [k for k, v in checks.items() if st.checkbox(k, value=v, key=f"chk_{k}")]
    st.progress(len(ticked) / len(checks), text=f"そろっている条件：{len(ticked)} / {len(checks)}")
    missing = [k for k in checks if k not in ticked]
    if missing:
        st.write("寒さ以外の理由として残るもの：" + "、".join(f"「{m}」でない" for m in missing))
    reason = st.text_area("自分の判断と、その理由", placeholder="例：差は寒さのせいと言えると思う。理由は…",
                          key="cmp_reason")

    st.subheader("問い2：自分なら、いつ収穫するか")
    c1, c2 = st.columns(2)
    with c1:
        target = st.slider("目標の糖度（Brix %）", 5.0, 15.0, 9.0, 0.5,
                           help="お客さんに出すならこれくらい、という自分の基準")
    with c2:
        strict = st.radio("どの列まで届いたら収穫するか",
                          ["区の平均が届いたら", "いちばん低い列でも届いたら"], horizontal=True) != "区の平均が届いたら"
    if DATES:
        res = []
        for g in cl.GROUPS:
            hit = cl.first_date_reaching(RM, g, target, strict)
            res.append((g, str(hit) if hit is not None else "記録の範囲では届かない"))
        st.dataframe(pd.DataFrame(res, columns=["区", f"目標 {target:.1f}% に届いた最初の測定日"]),
                     width="stretch", hide_index=True)
    my_cond = st.text_area("自分の条件（例：寒波の予報、出荷の予定、畑までの距離、手伝える人数）",
                           key="cmp_cond")
    decision = st.text_input("自分なら、この日に収穫する", placeholder="例：1月22日。理由は…", key="cmp_decision")
    st.caption("答えは人によって違ってかまいません。目標の糖度や慎重さを変えると、収穫日がどう動くかも確かめます。")

    sheet = f"""判断ワークシート（比べて確かめる探究）
作成日：{pd.Timestamp.today():%Y-%m-%d}
記録：{'架空の記入例' if st.session_state.cmp_is_sample else 'このページで入力・読み込んだ記録'}（{len(BRIX)} 行）

【問い1】差は寒さのせいと言えるか
 そろっている条件（{len(ticked)}/{len(checks)}）：{'、'.join(ticked) or 'なし'}
 そろっていない条件：{'、'.join(missing) or 'なし'}
 自分の判断と理由：{reason}

【問い2】自分ならいつ収穫するか
 目標の糖度：{target:.1f} %（{'いちばん低い列でも届いたら' if strict else '区の平均が届いたら'}）
 自分の条件：{my_cond}
 判断：{decision}

【比較の要約（列の平均で比べた結果）】
{by_date.round(2).to_string(index=False) if not by_date.empty else '記録なし'}
"""
    st.download_button("判断ワークシートを保存（テキスト）", sheet.encode("utf-8-sig"),
                       f"判断ワークシート_{pd.Timestamp.today():%Y%m%d}.txt", "text/plain")

# ═════════════════════════════════════════════
# 5. 発展：地域データと比べる
# ═════════════════════════════════════════════
with tab_ext:
    st.header("🗾 発展：すでにある地域データで比べる")
    st.write("畑ではくじで区を分けました。では、**くじで配られていないもの**の効果は、どう比べればよいでしょう。"
             "ここでは「中山間地域等直接支払交付金を受けた集落は、耕地を守れているか」を例に、"
             "2020年→2025年の変化を、受けた集落と受けなかった集落で比べます（差の差）。")
    st.markdown(f"データの入手先：[農林水産省「地域の農業を見て・知って・活かすDB」]({DB_URL})"
                "（農林業センサス・交付金などを農業集落ごとに整理した公開データ）")

    with st.expander("自分でダウンロードしたデータを使う"):
        st.markdown(
            "1. 活かすDBから、農林業センサス（2020年・2025年、2025農業集落基準）と、"
            "中山間地域等直接支払交付金の集落別データを取得する\n"
            f"2. 1行＝1集落×1年 で、列 `{', '.join(cl.DID_COLS)}` の形に整える"
            "（交付金は 受けた=1／受けていない=0）\n"
            "3. 下から読み込む"
        )
        up_did = st.file_uploader("集落データCSV", type="csv", key="up_cmp_did")
        if up_did is not None and st.session_state.get("cmp_did_loaded") != up_did.file_id:
            _df = sg.read_csv_safely(up_did, page=PAGE, kind="shuraku")
            if _df is not None:
                st.session_state.cmp_did = cl.normalize_did(_df)
                st.session_state.cmp_did_is_sample = False
            st.session_state.cmp_did_loaded = up_did.file_id
        if st.button("架空の集落データに戻す"):
            st.session_state.cmp_did = load_sample_did()
            st.session_state.cmp_did_is_sample = True

    if st.session_state.cmp_did_is_sample:
        st.info("いま表示しているのは **架空の集落データ** です（実在の集落・数値ではありません）。"
                "架空データには「交付金の本当の効果は +4ポイント」という答えを仕込んであります。")

    DID = st.session_state.cmp_did
    years = sorted(DID["年"].dropna().unique().tolist())
    if len(years) < 2:
        st.warning("2つ以上の年のデータが必要です。")
    else:
        c1, c2 = st.columns(2)
        pre = c1.selectbox("前の年", years, index=0)
        post = c2.selectbox("後の年", years, index=len(years) - 1)
        try:
            r = cl.did(DID, int(pre), int(post))
        except ValueError as e:
            st.warning(f"計算できません：{e}")
        else:
            m1, m2, m3 = st.columns(3)
            m1.metric(f"交付金あり（{r['n_treated']}集落）の変化", f"{r['change_treated']:+.1%}")
            m2.metric(f"交付金なし（{r['n_control']}集落）の変化", f"{r['change_control']:+.1%}")
            m3.metric("差の差", f"{r['did'] * 100:+.1f} ポイント")

            t = r["table"].copy()
            t["交付金"] = t["交付金"].map({1: "あり", 0: "なし"})
            fig = px.strip(t, x="交付金", y="変化率", color="交付金", hover_data=["集落"],
                           color_discrete_map={"あり": COLORS[cl.TREAT], "なし": COLORS[cl.CONTROL]})
            fig.add_hline(y=0, line_dash="dot", line_color="#888")
            fig.update_layout(height=340, showlegend=False, margin=dict(t=10, b=10),
                              yaxis=dict(title=f"経営耕地の変化率（{pre}→{post}）", tickformat="+.0%"))
            st.plotly_chart(fig, width="stretch")

            st.subheader("この差は、交付金のせいと言えるか")
            st.markdown(
                f"- **始まりがそろっていない**：{pre}年の平均耕地は、交付金あり {r['pre_treated']:.1f} ha／"
                f"なし {r['pre_control']:.1f} ha。\n"
                "- **配られ方がくじではない**：交付金は、傾斜がきつく条件の厳しい集落ほど受けやすい制度です。"
                "そうした集落は、交付金がなくても耕地が減りやすい可能性があります。\n"
                "- **確かめられないこと**：前の年が1つしかないと、「交付金がなければ、両方が同じように変化したはず」"
                "（平行トレンド）を確かめられません。2015年のデータも使うと、交付金以前の変化を比べられます。\n"
                "- **データの性質**：農水省は、集落別データは境界に合わせて按分した加工値で、"
                "特定の集落を正確に表すものではないと注意しています。"
            )
            if st.session_state.cmp_did_is_sample:
                st.warning(f"架空データの答え合わせ：本当の効果は +4.0 ポイントですが、差の差は "
                           f"{r['did'] * 100:+.1f} ポイントでした。条件の厳しい集落ほど交付金を受けているため、"
                           "効果が打ち消されて見えています。くじで分けた畑の実験では、この偏りは起きません。")
            st.text_area("自分の判断：この差は交付金のせいと言えるか。言えないなら、何を調べれば言えそうか",
                         key="cmp_did_reason")
            st.download_button("集落ごとの変化をCSVで保存", sg.safe_csv(r["table"].round(4)),
                               "集落ごとの変化.csv", "text/csv")
    st.caption("成果物には出典を書きます。例：農林水産省統計部「地域の農業を見て・知って・活かすDB"
               "（2025年農林業センサス）」を〇〇が編集して作成")

st.markdown(
    f'<p style="font-size:.85rem;color:#5a6a75">※ 初期表示はすべて架空データです。最終更新：{UPDATED}</p>',
    unsafe_allow_html=True,
)

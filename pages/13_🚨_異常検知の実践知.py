"""
探究コーナー ─ 異常検知の実践知：「いつもと違う」を、データの形から手法を選んで見つける
配置先: pages/13_🚨_異常検知の実践知.py （Streamlit のマルチページ構成）

探究の3つの問い（タブ）
  ❶ 対象データをどう分析するか？       型・変数の数・時間の順番・入出力・分布の形・ラベルを「診断カード」に
  ❷ 分析結果に基づきどの手法を選ぶか？   診断カードから、理由つきで手法を選ぶ（選び方の木）
  ❸ 手法をどう実践し、どう評価するか？   分ける → 学ぶ → 異常度 → 閾値 → テストで評価 → ベイズでアラートの信頼度

骨格はリポジトリ共通の3段構え：
  ① 現象を計算する（異常度・閾値）→ ② 数値を可視化する（分布・時系列・ROC/PR曲線）
  → ③ 自分の条件で判断する（見逃しと誤報、どちらをどれだけ許すか）

方針
  - 計算は anomaly_lab.py（`python anomaly_lab.py` で自己チェック）。
  - 初期表示はすべて架空データ（実測ではありません）。正解ラベルは評価（答え合わせ）にだけ使う。
  - アップロードした記録はセッション内だけで使い、サーバーには残さない。外部の生成AIは呼び出さない。
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import anomaly_lab as al
import security_guard as sg

st.set_page_config(page_title="探究コーナー：異常検知の実践知", page_icon="🚨", layout="wide")

import media_gallery as mg  # noqa: E402
import social as sn  # noqa: E402  SNSのURLは social.py で一括管理

UPDATED = "2026-10-17"
PAGE = "anomaly_lab"
NOTEBOOK = "notebooks/anomaly_detection_practice.ipynb"
BOOKS = ("中村謙太『まるごと学べる 異常検知の実践知』／笛田薫 監修・江崎剛史・李鍾賛『Pythonではじめる異常検知入門』"
         "／馬場嘉朗『マイコンによる異常検知入門』")
C_NORMAL, C_ANOM, C_THR = "#7a9cbf", "#d6453d", "#c98a2b"
PALETTE = ["#3f7cac", "#c98a2b", "#6a9a4a", "#8a5fa8"]


def plot(fig, h: int = 320, **kw) -> None:
    has_title = bool(kw.get("title") or fig.layout.title.text)
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=50 if has_title else 10, b=10), **kw)
    st.plotly_chart(fig, width="stretch")


# ─────────────────────────────────────────────
# サイドバー：どのデータで探究するか
# ─────────────────────────────────────────────
NAMES = {k: f(seed=0).name for k, f in al.SAMPLES.items()}
with st.sidebar:
    st.header("🚨 異常検知の実践知")
    src = st.radio("探究するデータ", list(NAMES) + ["upload"],
                   format_func=lambda k: NAMES.get(k, "📂 自分のCSVを読み込む"), key="an_src")
    seed = int(st.number_input("くじの番号", 0, 9999, 0, 1, help="同じ番号なら同じ架空データ・同じ分け方になります。"))
    DS = None
    if src == "upload":
        up = st.file_uploader("CSV（1行＝1観測）", type="csv", key="an_up")
        if up is not None:
            raw = sg.read_csv_safely(up, page=PAGE, kind="anomaly_csv")
            if raw is not None:
                num = [c for c in raw.columns if pd.api.types.is_numeric_dtype(raw[c])]
                cols = st.multiselect("異常度に使う数値の列", num, default=num[:min(3, len(num))])
                others = ["（なし）"] + list(raw.columns)
                tcol = st.selectbox("時刻の列（あれば）", others)
                lcol = st.selectbox("正解ラベルの列（あれば：1＝異常）", others)
                ocol = st.selectbox("結果の列（入出力があれば）", ["（なし）"] + cols)
                per = st.number_input("周期（時系列のとき・行数）", 0, 1000, 24, 1)
                if cols:
                    DS = al.from_upload(raw, cols, None if lcol == "（なし）" else lcol,
                                        None if tcol == "（なし）" else tcol,
                                        None if ocol == "（なし）" else ocol, int(per) or None)
        st.caption("氏名などの個人情報は入れないでください。読み込んだ記録はこの画面の中だけで使い、保存しません。")
    else:
        DS = al.sample(src, seed)
    st.divider()
    sn.buttons("で相談する", stacked=True)

st.title("🚨 探究コーナー：異常検知の実践知")
st.caption(f"下敷き：{BOOKS}　／　更新 {UPDATED}")
if DS is None:
    st.info("サイドバーでCSVを読み込み、列を選んでください。")
    st.stop()
if src != "upload":
    st.info(f"いま表示しているのは **架空のデータ**（{DS.name}）です。実測ではありません。")

DG = al.diagnose(DS)
REC = al.recommend(DG, DS)
AVAIL = al.available(DS)
HAS_LABEL = DG["正解ラベルのある異常"] > 0

tab_flow, tab1, tab2, tab3, tab4 = st.tabs([
    "🧭 この探究の流れ", "❶ データをどう分析するか", "❷ どの手法を選ぶか",
    "❸ どう実践し、どう評価するか", "📝 実践知チェック・マイ判断",
])

# ═════════════════════════════════════════════
# 0. 流れ
# ═════════════════════════════════════════════
with tab_flow:
    st.header("🧭 異常検知は「手法」より先に「データ」を見る")
    st.write("異常検知の本でいちばん多く書かれている失敗は、**手法を先に選んでしまうこと**です。"
             "「流行りのAI（オートエンコーダ）で」と決めてからデータを集めると、"
             "データの形と手法の前提が合わず、誤報だらけで誰も見なくなります。"
             "このページは、次の3つの問いを順に通ります。")
    st.dataframe(pd.DataFrame([
        ("❶ 対象データをどう分析するか？", "「いつも」とは何か。型・変数の数・時間の順番・原因と結果・分布の形・異常の数を診断カードに",
         "① 計算する・② 可視化する"),
        ("❷ 分析結果に基づきどの手法を選ぶか？", "診断カードの結果から、前提が合う手法を理由つきで選ぶ。比べる相手も選ぶ",
         "③ 判断する（手法の判断）"),
        ("❸ 手法をどう実践し、どう評価するか？", "学習／検証／テストに分け、閾値はテストを見ずに決め、再現率・適合率・PR曲線で評価する",
         "① 計算 → ② 可視化 → ③ 判断"),
    ], columns=["問い", "やること", "3段構えとの対応"]), width="stretch", hide_index=True)

    st.subheader("導入：ポアンカレとパン屋（点の異常と、分布の異常）")
    st.write("数学者ポアンカレは、毎日買う「1000gのパン」の重さを1年間量ったと伝えられています。"
             "以下は、その逸話を架空のデータで再現したものです。")
    PC = al.poincare(seed=seed)
    c1, c2 = st.columns([3, 2])
    with c1:
        fig = px.histogram(PC, x="重さ_g", color="年", barmode="overlay", nbins=40, opacity=.6,
                           color_discrete_sequence=[PALETTE[0], PALETTE[1]])
        fig.add_vline(x=1000, line_dash="dash", line_color="#555", annotation_text="表示 1000g")
        plot(fig, 300)
    with c2:
        for y in ["1年目", "2年目"]:
            v = PC.loc[PC["年"] == y, "重さ_g"].to_numpy()
            sk, _ = al._skew_kurt(v)
            st.metric(f"{y}：平均", f"{v.mean():.0f} g", f"歪度 {sk:+.2f}", delta_color="off")
        st.caption("1年目は山の形は普通なのに、**中心が950g**。2年目は平均が上がったのに、"
                   "**左側の裾が切れて右に歪んでいる**（軽いものを渡さなくなった）。"
                   "1個ずつを見ても異常は見えず、**分布の形**を見て初めて分かる異常です。")
    st.caption("※ 逸話の細部には諸説あります。ここでは「分布を見る」ことの例として使っています。")

    st.subheader("パン屋・農家・学校・セキュリティの「いつもと違う」")
    st.dataframe(pd.DataFrame([
        ("パン屋", "焼き色・形の外観検査", "良品だけを学び、それ以外を弾く（1クラス分類）", "多変数・画像", "ノートブック"),
        ("パン屋", "パンの重さ・工程の記録", "1変数の管理図／多変数のホテリングT²・MT法", "1変数・多変数", "🍞・🥖"),
        ("パン屋", "いつもと違う売れ行き（ロス）", "需要予測の残差", "入出力・時系列", "🌡️ と同じ考え方"),
        ("農家", "ハウスの温度・換気", "原因（日射）からの予想とのずれ／時系列の残差", "入出力・時系列", "🌡️・📈"),
        ("農家", "病害虫・生育不良", "画像の色の異常（葉色）", "画像", "ホームの AI土壌診断"),
        ("農家", "獣害・盗難（動体検知）", "夜間の動きの回数", "計数・時刻", "🔐 と同じ考え方"),
        ("学校", "学習の離脱の兆候", "ログイン・提出の回数の急な減り", "計数・時系列", "🔐 と同じ考え方"),
        ("セキュリティ", "不正ログイン", "時間帯ごとのいつもの回数（ポアソン）", "計数・時刻", "🔐"),
    ], columns=["現場", "何を見張るか", "考え方", "データの形", "このページのデータ"]), width="stretch", hide_index=True)
    st.caption("学校の例は、生徒を「異常」と呼ぶためではなく、声をかけるきっかけを早く得るためのものです。"
               "人に関わるデータは、本人の同意・目的の限定・最後は人が判断する、を必ず守ります。")

    st.subheader("HACCP・ロボット安全・サイバー防御と、同じ形をしている")
    st.dataframe(pd.DataFrame([
        ("いつもの状態を決める", "管理基準（CL）", "正常動作の範囲", "平常時の通信・ログイン", "学習データ（正常）"),
        ("見張る", "モニタリング", "監視（センサ・柵）", "ログ監視（SIEM）", "異常度を計算する"),
        ("線を引く", "許容限界", "停止条件", "検知ルールの閾値", "閾値（検証データで決める）"),
        ("鳴ったら", "是正措置", "非常停止 → 点検", "インシデント対応", "人が調べる（Human-in-the-Loop）"),
        ("見直す", "検証・記録", "リスクアセスメントの更新", "検知ルールの改善", "再現率・適合率で評価し直す"),
    ], columns=["段", "HACCP", "ロボット安全", "サイバー防御", "異常検知"]), width="stretch", hide_index=True)

    st.subheader("5つの架空データ（サイドバーで切り替え）")
    st.dataframe(pd.DataFrame([
        (NAMES["bread"], "1変数", "変数ごとの管理図／ロバストz", "学習データに異常が混ざると「いつも」の幅が広がる"),
        (NAMES["login"], "計数・時刻", "ポアソン（時間帯別）", "時間帯を分けないと、深夜の少数試行を見逃す"),
        (NAMES["dough"], "多変数", "ホテリングT²・MT法・k近傍", "1つずつ見ると普通なのに、組み合わせが崩れている異常がある"),
        (NAMES["house_io"], "入出力", "回帰の残差", "原因を無視すると、晴れて暑いだけの時間を異常と呼ぶ"),
        (NAMES["house_ts"], "時系列", "時系列の残差＋固着ルール", "1つの手法では見えない種類の異常がある"),
    ], columns=["データ", "形", "選ぶ手法", "見つかる実践知"]), width="stretch", hide_index=True)

    st.subheader("90分の当日の流れ（例）")
    st.dataframe(pd.DataFrame([
        ("0–10分", "ポアンカレとパン屋：1個ずつでは見えない異常を体験", "🧭"),
        ("10–30分", "データを1つ選び、診断カードを埋める（グラフは答えを隠して見る）", "❶"),
        ("30–45分", "選び方の木をたどり、本命の手法と比べる相手を選ぶ", "❷"),
        ("45–75分", "閾値の決め方を変え、見逃しと誤報の取り合いを体験する", "❸"),
        ("75–90分", "自分の現場の条件で「何件の誤報まで許すか」を決めて発表", "📝"),
    ], columns=["時間", "内容", "タブ"]), width="stretch", hide_index=True)

# ═════════════════════════════════════════════
# ❶ 対象データをどう分析するか
# ═════════════════════════════════════════════
with tab1:
    st.header("❶ 対象データをどう分析するか？")
    st.write(f"**{DS.name}**：{DS.story}")
    st.write("手法を選ぶ前に、次の6つを確かめます。答えはデータの中にあります。")
    st.dataframe(pd.DataFrame([
        ("1行は何の単位か", "1個のパン？ 1時間？ 1バッチ？", "数え方が変わる"),
        ("値は回数か、連続値か", "0,1,2… の回数なら正規分布は使いにくい", "計数 → ポアソン"),
        ("変数はいくつか、互いに結びついているか", "結びつきがあると、組み合わせの崩れが異常になる", "多変数 → T²・MT法"),
        ("時間の順番はあるか", "前後の時刻が結びつく・昼と夜で「いつも」が違う", "時系列 → 残差"),
        ("原因と結果はあるか", "結果だけ見ると、原因による普通の変化を異常と呼ぶ", "入出力 → 回帰の残差"),
        ("異常は何件あり、記録は残っているか", "異常が少ない・種類が分からないのが普通", "教師なしが基本"),
    ], columns=["問い", "なぜ大事か", "手法への影響"]), width="stretch", hide_index=True)

    st.subheader("診断カード")
    m = st.columns(6)
    m[0].metric("行数", f"{DG['行数']:,}")
    m[1].metric("変数の数", DG["変数の数"])
    m[2].metric("値の型", "計数" if DG["計数"] else "連続値")
    m[3].metric("時間の順番", "あり" if DG["時間の順番"] else "なし")
    m[4].metric("原因→結果", "あり" if DG["入出力（原因→結果）"] else "なし")
    m[5].metric("異常の割合（正解）", f"{DG['異常の割合']:.1%}" if HAS_LABEL else "不明")
    st.markdown("##### 所見（❷ の手法選びの根拠になります）")
    for f in al.findings(DG):
        st.markdown(f"- {f}")
    with st.expander("診断カードの数字をすべて見る"):
        st.json({k: (round(v, 3) if isinstance(v, float) else v) for k, v in DG.items()})

    st.subheader("グラフで見る")
    show_ans = st.toggle("正解ラベルで色をつける（答え合わせ）", value=False,
                         help="現場ではふつう正解は分かりません。まずは色なしで「怪しいところ」を探してみましょう。")
    D = DS.df.copy()
    D["状態"] = np.where(D[al.LABEL] == 1, D[al.TYPE], "正常") if show_ans else "（正解は隠しています）"
    color_kw = dict(color="状態", color_discrete_map={"正常": C_NORMAL, "（正解は隠しています）": C_NORMAL})
    if DS.kind == "時系列" or (DS.kind == "計数" and DS.time_col):
        y = DS.cols[0]
        fig = px.scatter(D, x=DS.time_col, y=y, **color_kw)
        fig.add_trace(go.Scatter(x=D[DS.time_col], y=D[y], mode="lines", line=dict(color="#bbb", width=1),
                                 showlegend=False, hoverinfo="skip"))
        fig.data = fig.data[::-1]
        plot(fig, 300, title="時間の流れ")
        c1, c2 = st.columns(2)
        with c1:
            lags = list(range(1, min(49, len(D) // 3)))
            ac = [al.acf(D[y].to_numpy(float), k) for k in lags]
            fig = px.bar(x=lags, y=ac, labels={"x": "何時点前と比べるか（ラグ）", "y": "相関"})
            plot(fig, 260, title="自己相関：前の時刻とどれだけ似ているか")
        with c2:
            hh = D[DS.time_col].dt.hour
            fig = px.box(D.assign(時=hh), x="時", y=y, points=False)
            plot(fig, 260, title="時刻ごとの「いつも」の幅")
        st.caption("自己相関が高い・時刻ごとに幅が違う → 「1行ずつ独立」「いつもは1つの山」という前提が崩れています。")
    elif DS.kind == "入出力":
        fig = px.scatter(D, x=DS.inputs[0], y=DS.output, symbol="状態" if show_ans else None,
                         color=DS.inputs[1] if not show_ans else "状態",
                         color_discrete_map={"正常": C_NORMAL} if show_ans else None)
        plot(fig, 360, title=f"原因（{DS.inputs[0]}）と結果（{DS.output}）")
        fig = px.histogram(D, x=DS.output, nbins=40, **color_kw)
        plot(fig, 240, title=f"結果だけを見たときの分布（{DS.output}）")
        st.caption("結果だけの分布では、晴れて暑いだけの時間と、換気窓の故障の区別がつきません。")
    elif DS.kind == "多変数":
        fig = px.scatter_matrix(D, dimensions=DS.cols, **color_kw)
        fig.update_traces(diagonal_visible=False, marker=dict(size=4, opacity=.7))
        plot(fig, 560, title="散布図行列：2つずつの組み合わせ")
        corr = D[DS.cols].corr()
        fig = px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu", zmin=-1, zmax=1, aspect="auto")
        plot(fig, 320, title="相関")
        st.caption("相関の強い組み合わせ（例：焼成温度と焼き色）は、片方だけ見れば普通の値でも、"
                   "組み合わせが崩れれば異常です。散布図の「帯」から外れた点を探してみましょう。")
    else:
        y = DS.cols[0]
        fig = px.histogram(D, x=y, nbins=50, **color_kw)
        plot(fig, 300, title=f"{y} の分布")
        st.caption("山の形は左右対称か、裾に飛び離れた点はないか。飛び離れた点が多いと、"
                   "平均・標準偏差が引っ張られて「いつも」の幅が広がります（❸で確かめます）。")
    st.download_button("このデータをCSVで保存", sg.safe_csv(DS.df), f"{DS.key}.csv", "text/csv")

# ═════════════════════════════════════════════
# ❷ どの手法を選ぶか
# ═════════════════════════════════════════════
def tree_dot(dg: dict) -> str:
    """選び方の木（Graphviz）。いまのデータがたどる道を色付きで示す。"""
    io, cnt = dg["入出力（原因→結果）"], dg["計数"]
    ts = dg["時間の順番"] and abs(dg["1時点前との相関 r(1)"] or 0) > 0.5
    mv = dg["変数の数"] > 1
    nm = al._is_normal(dg["歪度（外れ値候補を除く）"], dg["尖度（外れ値候補を除く）"])
    cr = (dg["変数どうしの最大相関"] or 0) > 0.3
    ol = dg["外れ値候補の割合"] > 0.01
    path = {"q0", "q1"}
    if io:
        path |= {"回帰"}
    else:
        path |= {"q2"}
        if cnt:
            path |= {"ポアソン"}
        else:
            path |= {"q3"}
            if ts:
                path |= {"時系列"}
            else:
                path |= {"q4"}
                if mv:
                    path |= {"q5", "T2" if (nm and cr) else "kNN"}
                else:
                    path |= {"q6"}
                    path |= {"kNN"} if not nm else {"q7", "ロバスト" if ol else "管理図"}
    nodes = {
        "q0": ("異常の正解ラベルが十分あり、\n新しい種類の異常は来ない？", "q"),
        "教師あり": ("教師あり（ロジスティック回帰など）\n※ 教師なしと併用", "m"),
        "q1": ("原因→結果（入出力）がある？", "q"), "回帰": ("回帰の残差", "m"),
        "q2": ("値は回数（計数）？", "q"), "ポアソン": ("ポアソン（時間帯別）", "m"),
        "q3": ("時間の順番があり、\n前後が強く結びつく？", "q"), "時系列": ("時系列の残差\n＋固着ルール", "m"),
        "q4": ("変数は2つ以上？", "q"),
        "q5": ("外れ値候補を除いて正規分布に近く、\n変数どうしに相関がある？", "q"),
        "T2": ("ホテリングT² ／ MT法", "m"), "kNN": ("k近傍距離\n（形を仮定しない）", "m"),
        "q6": ("外れ値候補を除いて\n正規分布に近い？", "q"),
        "q7": ("外れ値候補が混ざっている？", "q"),
        "ロバスト": ("ロバストz（中央値・MAD）", "m"), "管理図": ("変数ごとの管理図\n（1変数ホテリング）", "m"),
    }
    edges = [("q0", "教師あり", "はい"), ("q0", "q1", "いいえ（ふつう）"), ("q1", "回帰", "はい"), ("q1", "q2", "いいえ"),
             ("q2", "ポアソン", "はい"), ("q2", "q3", "いいえ"), ("q3", "時系列", "はい"), ("q3", "q4", "いいえ"),
             ("q4", "q5", "はい"), ("q4", "q6", "いいえ"), ("q5", "T2", "はい"), ("q5", "kNN", "いいえ"),
             ("q6", "q7", "はい"), ("q6", "kNN", "いいえ"), ("q7", "ロバスト", "はい"), ("q7", "管理図", "いいえ")]
    out = ['digraph G { rankdir=TB; bgcolor="transparent"; nodesep=0.25; ranksep=0.3; node [fontname="sans-serif", fontsize=14]; '
           'edge [fontname="sans-serif", fontsize=11, fontcolor="#888888", color="#999"];']
    for k, (lab, kind) in nodes.items():
        on = k in path
        shape = "diamond" if kind == "q" else "box"
        fill = ("#f6e3c3" if kind == "q" else "#cfe3f3") if on else "#f4f4f4"
        pen = "#c98a2b" if on else "#bbb"
        out.append(f'"{k}" [label="{lab}", shape={shape}, style="filled,rounded", fillcolor="{fill}", color="{pen}", '
                   f'penwidth={2.5 if on else 1}];')
    for a, b, lab in edges:
        on = a in path and b in path
        out.append(f'"{a}" -> "{b}" [label="{lab}", color="{"#c98a2b" if on else "#bbb"}", penwidth={2.5 if on else 1}];')
    out.append("}")
    return "\n".join(out)


with tab2:
    st.header("❷ 分析結果に基づき、どの手法を選ぶか？")
    st.write("診断カードの答えで、木を上からたどります。色のついた道が、いまのデータの道です。")
    st.graphviz_chart(tree_dot(DG), width="stretch")
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("##### このデータへのおすすめ")
        for i, (mth, why) in enumerate(REC):
            st.markdown(f"{'**本命**' if i == 0 else '比べる相手'}：**{mth}**  \n<small>{why}</small>",
                        unsafe_allow_html=True)
    with c2:
        st.info("いちばん上の「教師あり」は、異常の記録が十分あり、**新しい種類の異常が来ない**ときだけ。"
                "現場ではほとんど満たされないので、ふつうは「いいえ」に進みます。")

    st.subheader("❸ で比べる手法を選ぶ（3つまで）")
    default = [mth for mth, _ in REC][:3]
    if st.session_state.get("an_methods_src") != (src, DS.kind):
        st.session_state.an_methods = default
        st.session_state.an_methods_src = (src, DS.kind)
    st.multiselect("手法", AVAIL, key="an_methods", max_selections=3,
                   help="本命と、前提の違う手法を並べると、何が効いているのかが分かります。")

    st.subheader("手法のカタログ")
    cat = pd.DataFrame([(k, *v, "✅" if k in AVAIL else "—") for k, v in al.METHODS.items()],
                       columns=["手法", "向いているデータ", "異常度", "閾値", "苦手なこと", "考え方の出どころ", "このデータで使える"])
    st.dataframe(cat, width="stretch", hide_index=True)
    with st.expander("式で見る"):
        st.latex(r"\text{1変数：}\ a(x)=\left(\frac{x-\hat\mu}{\hat\sigma}\right)^2 \sim \chi^2(1)")
        st.latex(r"\text{ホテリング}T^2：\ a(\mathbf{x})=(\mathbf{x}-\hat{\boldsymbol\mu})^\top\hat\Sigma^{-1}"
                 r"(\mathbf{x}-\hat{\boldsymbol\mu}) \sim \chi^2(M)\quad\text{（MT法は } D^2=a/M\text{）}")
        st.latex(r"\text{ポアソン：}\ a(x)=-\log_{10}P(X\ge x\mid\hat\lambda_{\text{時間帯}}),\quad "
                 r"\hat\lambda_{\text{時間帯}}=\text{その時間帯の平均回数}")
        st.latex(r"\text{回帰の残差：}\ a=\left(\frac{y-\hat y(\text{原因})}{\hat\sigma_{\text{残差}}}\right)^2")
        st.latex(r"\text{時系列：}\ d_t=y_t-\operatorname{median}(y_{t-P},y_{t-2P},y_{t-3P}),\quad "
                 r"e_t=d_t-\hat\phi\, d_{t-1},\quad a_t=(e_t/\hat\sigma_e)^2")
        st.caption("MT法の閾値は「D² > 4」が慣例ですが、正しくは変数の数 M によって変わります（χ²(M)/M）。"
                   "変数が多いほど、正常でも D² が大きめに出やすいことに注意します。")

# ═════════════════════════════════════════════
# ❸ どう実践し、どう評価するか
# ═════════════════════════════════════════════
with tab3:
    st.header("❸ 手法をどう実践し、どう評価するか？")
    METHODS_SEL = st.session_state.get("an_methods") or [mth for mth, _ in REC][:2]
    if not HAS_LABEL:
        st.warning("正解ラベルがないので、評価（再現率・適合率）は計算できません。異常度と閾値までを表示します。"
                   "現場では、アラートが鳴った記録を人が確かめて、少しずつラベルを作っていきます。")

    st.subheader("ステップ1：学習・検証・テストに分ける")
    SP = al.split(DS, seed=seed)
    c1, c2 = st.columns([3, 2])
    with c1:
        clean = st.checkbox("学習データから「記録のある異常」を除く（掃除する）", value=True,
                            help="教師なしの手法は「正常のいつも」を学びます。異常が混ざると、いつもの幅が広がります。")
        st.dataframe(pd.DataFrame({
            "使い道": ["「いつも」を学ぶ（平均・分散・係数）", "閾値を決める", "最後に1回だけ評価する"],
            "行数": [len(SP[k]) for k in SP],
            "うち異常（正解）": [int(DS.df[al.LABEL].iloc[SP[k]].sum()) for k in SP],
        }, index=list(SP)), width="stretch")
    with c2:
        st.markdown(
            ("- 時間の順番があるので、**時間順**に分けています（過去で学び、未来で確かめる）\n" if DS.time_col
             else "- くじで分けています（くじの番号はサイドバー）\n")
            + "- 平均・標準偏差・係数は **学習データだけ** で計算し、検証・テストに当てはめます（データリーク防止）\n"
            "- 閾値は **検証データ** で決めます。**テストデータは最後の評価にしか使いません**\n"
            + ("- 掃除できるのは「記録のある異常」だけ。記録のない種類の異常は、正常のふりをして学習データに残ります\n"
               if DS.known_types else "- この架空データでは、掃除に正解ラベルを使っています（現場では人が記録から除きます）\n"))

    st.subheader("ステップ2：閾値の決め方")
    c1, c2, c3 = st.columns(3)
    strategy = c1.radio("決め方", ["分位点", "理論", "コスト最小"], horizontal=True,
                        help="分位点：検証データの正常の(1−α)点。理論：分布の仮定から（χ²など）。"
                             "コスト最小：検証データで 見逃し×重み＋誤報 が最小になる点。")
    alpha = c2.select_slider("α（正常を誤報してよい割合）", [0.001, 0.005, 0.01, 0.02, 0.05, 0.1], value=0.01)
    c_fn = c3.slider("見逃し1件は、誤報何件分の損か", 1, 100, 10, disabled=strategy != "コスト最小")

    y_all = DS.df[al.LABEL].to_numpy()
    va, te = SP["検証"], SP["テスト"]
    RES, FLAGS, SCORES = {}, {}, {}
    for mth in METHODS_SEL:
        tr = al.train_rows(DS, SP, clean, mth)
        if len(tr) < max(5, len(DS.cols) + 2):
            st.error(f"{mth}：学習データが少なすぎます。")
            continue
        s, th = al.score(mth, DS, tr, alpha)
        thr = al.threshold(strategy, s[va], y_all[va], alpha, th, c_fn=float(c_fn))
        SCORES[mth] = (s, thr, th)
        FLAGS[mth] = s[te] > thr
        if HAS_LABEL:
            RES[mth] = al.evaluate(y_all[te], s[te], thr)
    if not SCORES:
        st.stop()
    if strategy == "理論" and any(th is None for _, _, th in SCORES.values()):
        st.caption("※ k近傍距離には理論の閾値がないため、分位点で決めています。")

    st.subheader("ステップ3：異常度を見る（検証＋テスト）")
    mtabs = st.tabs(list(SCORES))
    for mt, (mth, (s, thr, th)) in zip(mtabs, SCORES.items()):
        with mt:
            idx = np.r_[va, te]
            P = DS.df.iloc[idx].copy()
            P["異常度"] = s[idx]
            P["区分"] = np.where(np.isin(idx, te), "テスト", "検証")
            P["状態"] = np.where(P[al.LABEL] == 1, P[al.TYPE], "正常")
            xcol = DS.time_col if DS.time_col else "番号"
            if not DS.time_col:
                P["番号"] = np.arange(len(P))
            ylog = mth not in ("教師あり（ロジスティック回帰）", "固着ルール（同じ値が続く）")
            fig = px.scatter(P, x=xcol, y=P["異常度"] + (1e-3 if ylog else 0), color="状態", symbol="区分",
                             color_discrete_map={"正常": C_NORMAL}, log_y=ylog, labels={"y": "異常度"})
            if ylog:
                yv = np.r_[P["異常度"].to_numpy() + 1e-3, thr + 1e-3]
                fig.update_yaxes(range=[np.log10(yv.min()) - 0.2, np.log10(yv.max()) + 0.2])
            fig.add_hline(y=thr + (1e-3 if ylog else 0), line_color=C_THR, line_dash="dash",
                          annotation_text=f"閾値 {thr:.2f}（{strategy}）")
            if not DS.time_col:
                fig.add_vline(x=len(va) - .5, line_color="#999", annotation_text="← 検証｜テスト →")
            plot(fig, 340, title=f"{mth}：閾値の線より上がアラート")
            if th is not None and strategy != "理論":
                st.caption(f"参考：理論の閾値は {th:.2f}。検証データから決めた閾値 {thr:.2f} と比べてみましょう"
                           "（大きく違えば、分布の仮定がデータに合っていません）。")

    if HAS_LABEL:
        st.subheader("ステップ4：テストデータで評価する")
        R = pd.DataFrame(RES).T
        if len(FLAGS) > 1:
            any_flag = np.any(np.vstack(list(FLAGS.values())), axis=0)
            best = max(RES, key=lambda k: RES[k]["ROC-AUC"])
            R.loc["組み合わせ（どれかが鳴ればアラート）"] = al.evaluate(y_all[te], SCORES[best][0][te], 0, any_flag)
            R.loc["組み合わせ（どれかが鳴ればアラート）", ["ROC-AUC", "平均適合率(AP)"]] = np.nan
        R = R.astype(float)[["再現率", "適合率", "F1", "誤報率", "ROC-AUC", "平均適合率(AP)", "TP", "FP", "FN"]]
        show = R.copy().astype(object)
        for c in R.columns:
            fmt = "{:.0%}" if c in ("再現率", "適合率", "F1", "誤報率") else "{:.3f}" if c in ("ROC-AUC", "平均適合率(AP)") else "{:.0f}"
            show[c] = [("—" if pd.isna(v) else fmt.format(v)) for v in R[c]]
        st.dataframe(show, width="stretch")
        st.caption("再現率＝本物の異常のうち見つけた割合（見逃しの少なさ）。適合率＝アラートのうち本物の割合（空振りの少なさ）。"
                   "正解率（Accuracy）は使いません。異常が5%なら「全部正常」と言うだけで95%になるからです。")

        c1, c2 = st.columns(2)
        roc_fig, pr_fig = go.Figure(), go.Figure()
        for i, (mth, (s, thr, _)) in enumerate(SCORES.items()):
            cv = al.curves(y_all[te], s[te])
            col = PALETTE[i % len(PALETTE)]
            roc_fig.add_trace(go.Scatter(x=cv["誤報率"], y=cv["再現率"], name=f"{mth}（AUC {RES[mth]['ROC-AUC']:.2f}）",
                                         line=dict(color=col, shape="hv")))
            pr_fig.add_trace(go.Scatter(x=cv["再現率"], y=cv["適合率"], name=f"{mth}（AP {RES[mth]['平均適合率(AP)']:.2f}）",
                                        line=dict(color=col, shape="hv")))
            ev = RES[mth]
            roc_fig.add_trace(go.Scatter(x=[ev["誤報率"]], y=[ev["再現率"]], mode="markers", showlegend=False,
                                         marker=dict(color=col, size=11, symbol="x")))
            pr_fig.add_trace(go.Scatter(x=[ev["再現率"]], y=[ev["適合率"]], mode="markers", showlegend=False,
                                        marker=dict(color=col, size=11, symbol="x")))
        roc_fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], line=dict(color="#ccc", dash="dot"), showlegend=False))
        base = y_all[te].mean()
        pr_fig.add_hline(y=base, line_color="#ccc", line_dash="dot", annotation_text=f"でたらめ（{base:.0%}）")
        with c1:
            plot(roc_fig, 360, title="ROC曲線（×＝いまの閾値）", xaxis_title="誤報率", yaxis_title="再現率",
                 legend=dict(orientation="h", y=-0.25))
        with c2:
            plot(pr_fig, 360, title="PR曲線（異常が少ないときはこちらが本音）", xaxis_title="再現率",
                 yaxis_title="適合率", legend=dict(orientation="h", y=-0.25))

        st.markdown("##### 異常の種類ごとに：どの手法が、どの種類を見つけたか")
        typ_te = DS.df[al.TYPE].iloc[te]
        BT = pd.concat({mth: al.by_type(typ_te, f).set_index("種類")["割合"] for mth, f in FLAGS.items()}, axis=1)
        if len(FLAGS) > 1:
            BT["組み合わせ"] = al.by_type(typ_te, np.any(np.vstack(list(FLAGS.values())), 0)).set_index("種類")["割合"]
        cnt = al.by_type(typ_te, np.zeros(len(te), bool)).set_index("種類")["件数"]
        BT.insert(0, "件数", cnt)
        BT = BT.rename(index={"正常": "正常（＝誤報になった割合）"})
        st.dataframe(BT, width="stretch", column_config={
            c: st.column_config.ProgressColumn(c, format="percent", min_value=0, max_value=1)
            for c in BT.columns if c != "件数"})

        # 結果から読める実践知（データと手法の組み合わせで、自動で言葉にする）
        notes = []
        anom_types = [t for t in BT.index if not t.startswith("正常")]
        for t in anom_types:
            row = BT.loc[t].drop(["件数", "組み合わせ"], errors="ignore")
            if len(row) > 1 and row.max() - row.min() >= 0.5:
                notes.append(f"「{t}」は **{row.idxmax()}** が {row.max():.0%} 見つけたのに、"
                             f"**{row.idxmin()}** は {row.min():.0%}。手法の前提の違いが、そのまま見える異常の違いになっています。")
        if "組み合わせ" in BT and len(anom_types):
            best_single = BT.drop(columns=["件数", "組み合わせ"]).loc[anom_types].min(axis=0).max()
            if BT.loc[anom_types, "組み合わせ"].min() > best_single + 0.2:
                notes.append("どの手法も単独では取りこぼす種類があり、**組み合わせ**で埋まりました。"
                             "見張る異常の種類ごとに、手法（や作った特徴量）を足すのが現場の定番です。")
        sup = [mth for mth in FLAGS if mth.startswith("教師あり")]
        if sup and DS.known_types:
            unk = [t for t in anom_types if t not in DS.known_types]
            if unk and BT.loc[unk, sup[0]].max() < 0.5:
                notes.append(f"教師ありは、記録のある「{'・'.join(DS.known_types)}」はよく見つけても、"
                             f"記録のない「{'・'.join(unk)}」をほとんど見逃しました。**教師なしを主、教師ありを補助**に。")
        if notes:
            st.success("**この結果から読める実践知**\n\n" + "\n\n".join(f"- {n}" for n in notes))

        st.subheader("ステップ5：アラートが鳴ったら、それは本物か（ベイズの定理）")
        pick = st.selectbox("どの手法の性能で考えるか", list(RES), key="an_bayes_m")
        ev = RES[pick]
        c1, c2 = st.columns([2, 3])
        with c1:
            prev = st.select_slider("本番での異常の割合（基準率）",
                                    [0.0001, 0.0005, 0.001, 0.005, 0.01, 0.02, 0.05, 0.1],
                                    value=min([0.0001, 0.0005, 0.001, 0.005, 0.01, 0.02, 0.05, 0.1],
                                              key=lambda v: abs(v - max(DG["異常の割合"], 1e-4))))
            fpr = max(ev["誤報率"], 1e-4)
            pt = al.alarm_truth(prev, ev["再現率"], fpr)
            st.metric("アラートが本物である確率", f"{pt:.1%}")
            st.latex(r"P(\text{異常}\mid\text{アラート})=\frac{\text{再現率}\times\pi}"
                     r"{\text{再現率}\times\pi+\text{誤報率}\times(1-\pi)}")
            st.caption(f"再現率 {ev['再現率']:.0%}・誤報率 {fpr:.2%}（テストデータで0件なら0.01%とみなす）で計算。")
        with c2:
            pis = np.logspace(-4, -0.7, 60)
            fig = px.line(x=pis, y=[al.alarm_truth(p, ev["再現率"], fpr) for p in pis], log_x=True,
                          labels={"x": "異常の割合（基準率）", "y": "アラートが本物である確率"})
            fig.add_vline(x=prev, line_color=C_THR, line_dash="dash")
            fig.update_yaxes(tickformat=".0%", range=[0, 1])
            plot(fig, 300, title="異常が珍しいほど、アラートの多くは空振りになる")
        st.caption("同じ検知器でも、異常が珍しい現場に持っていくと空振りが増えます。"
                   "誤報が続くと人はアラートを見なくなる（アラート疲れ）ので、閾値は「何件の空振りまで人が付き合えるか」で決めます。")

# ═════════════════════════════════════════════
# 実践知チェック・マイ判断
# ═════════════════════════════════════════════
with tab4:
    st.header("📝 実践知チェック・マイ判断")
    st.subheader("落とし穴チェックリスト")
    st.write("自分の分析で確かめたものに ✅ をつけます。")
    ck = pd.DataFrame(al.PITFALLS, columns=["落とし穴", "どう起きるか", "対策", "このページで確かめる場所"])
    ck.insert(0, "確かめた", False)
    ed = st.data_editor(ck, width="stretch", hide_index=True, disabled=list(ck.columns[1:]), key="an_check")
    st.progress(float(ed["確かめた"].mean()), text=f"{int(ed['確かめた'].sum())} / {len(ed)}")

    st.subheader("持ち込みノートブックの点検（Anomaly_detection_01.ipynb：画像の異常検知）")
    st.write("良品画像だけを学ぶ One-Class SVM と畳み込みオートエンコーダの例です。考え方（良品だけを学ぶ）は正しいので、"
             "実践の段で起きている問題を直しました。")
    st.dataframe(pd.DataFrame(al.NOTEBOOK_REVIEW, columns=["見つかったこと", "なぜ問題か", "直し方"]),
                 width="stretch", hide_index=True)
    st.link_button("▶ 直したノートブックを Google Colab で開く", mg.colab_url(NOTEBOOK))
    st.caption("ノートブックは画像フォルダがなくても、架空のパン画像（焦げ・欠け）を作って最後まで動きます。")

    st.subheader("マイ判断シート：自分の現場で、どこに線を引くか")
    if not (HAS_LABEL and RES):
        st.info("正解ラベルのあるデータで ❸ を実行すると、その性能で計算できます。")
    else:
        pick2 = st.selectbox("使う手法", list(RES), key="an_sheet_m")
        ev = RES[pick2]
        c1, c2, c3, c4 = st.columns(4)
        per_day = c1.number_input("1日の観測数（パン・時間・バッチなど）", 1, 100000, 24 if DS.time_col else 100, 1)
        prev2 = c2.number_input("異常の割合（%）", 0.01, 50.0, round(max(DG["異常の割合"] * 100, 0.01), 2), 0.1) / 100
        loss_fn = c3.number_input("見逃し1件の損失（円）", 0, 10_000_000, 30_000, 1000)
        loss_fp = c4.number_input("誤報1件の確認の手間（円換算）", 0, 1_000_000, 500, 100)
        fpr = ev["誤報率"]
        alerts = per_day * (ev["再現率"] * prev2 + fpr * (1 - prev2))
        miss = per_day * 30 * prev2 * (1 - ev["再現率"])
        cost = per_day * 30 * (prev2 * (1 - ev["再現率"]) * loss_fn + (1 - prev2) * fpr * loss_fp)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("1日のアラート数", f"{alerts:.1f} 件")
        m2.metric("うち本物の割合", f"{al.alarm_truth(prev2, ev['再現率'], max(fpr, 1e-4)):.0%}")
        m3.metric("1か月の見逃し", f"{miss:.1f} 件")
        m4.metric("1か月の損失＋手間", f"{cost:,.0f} 円")
        if alerts > 10:
            st.warning("1日10件を超えるアラートは、人が全部は確かめられません。閾値を上げる（α を小さく）か、"
                       "アラートを「まとめて1日1回の報告」にするかを考えましょう。")
        st.text_area("自分の判断と、その理由（数字を1つ以上入れる）", key="an_note", height=120,
                     placeholder="例：見逃し1件は3万円、誤報は500円。1日のアラートは2件なら朝の見回りで確かめられる。"
                                 "だから α=0.01 のホテリングT²を使い、毎月テストし直す。")
        st.caption("この欄の文章はサーバーに保存されません。必要ならコピーして手元に残してください。")

    with st.expander("次の一歩（研究・ロボット・セキュリティへ）"):
        st.markdown(
            "- **ベイズ統計モデリング**：農園ごと・季節ごとの違いを階層モデル（GLMM）で持ち、"
            "「この農園にしては珍しい」を測る（データが少ない現場ほど効く）\n"
            "- **因果**：アラートの原因を「相関の崩れ」から探す（T²への寄与の大きい変数＝最初に点検する場所）\n"
            "- **ロボット（ROS2）**：関節トルク・モーター電流を時系列の残差で見張り、閾値を超えたら減速・停止"
            "（安全側に倒す判断は人が設計する）\n"
            "- **マイコン**：ESP32 などでハウスの温度・振動を集め、マイコンの中で FFT・固着ルールまでを動かす\n"
            "- **セキュリティ**：このページの 🔐 と同じ考え方で、セキュリティログ（管理ページ）の失敗回数を時間帯別に見張る"
        )
    st.caption(f"参考：{BOOKS}。本ページの文章・データ・計算はこのアプリ独自のもので、書籍の内容の転載ではありません。")

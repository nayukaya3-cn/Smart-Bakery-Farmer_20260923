"""
離れる顧客を先に見つける（本人のみ）─ 多分野データ解析実践演習 ケース3：顧客離反予測
配置先: pages/24_🛒_離れる顧客を先に見つける.py （左メニュー「🔒 管理」）

探究の3つの問い（タブ）― 構成は「🚨 異常検知の実践知」と同じ
  ❶「離れる」をどう定義し、データをどう見るか？  基準日で時間を切る／観察期間・予測期間／顧客カルテ（RFM）
  ❷ どの機械学習モデルを選ぶか？                ベースライン・ロジスティック回帰・ランダムフォレスト・勾配ブースティング
  ❸ どう評価し、どう使うか？                    混同行列・ROC/PR・リフト・重要度 → 📝 費用対効果と引き留めリスト

骨格はリポジトリ共通の3段構え：
  ① 現象を計算する（離反確率）→ ② 数値を可視化する（分布・曲線・リフト）
  → ③ 自分の条件で判断する（ムダ打ちと取りこぼし、どちらをどれだけ許すか）

方針
  - 所有者専用（owner_gate.py）。一般公開しない。
  - 計算は churn_lab.py（`python churn_lab.py` で自己チェック）。機械学習は scikit-learn。
  - データは UCI Online Retail II を請求書単位に要約したもの（CC BY 4.0、出典を明記）。
  - アップロードした記録はセッション内だけで使い、サーバーには残さない。外部の生成AIは呼び出さない。
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import churn_lab as cl  # noqa: E402
import owner_gate as og  # noqa: E402
import security_guard as sg  # noqa: E402

st.set_page_config(page_title="離れる顧客を先に見つける（本人のみ）", page_icon="🛒", layout="wide")
og.require_owner("churn_lab")

import media_gallery as mg  # noqa: E402

UPDATED = "2026-10-28"
PAGE = "churn_lab"
NOTEBOOK = "notebooks/churn_prediction_practice.ipynb"
C_STAY, C_CHURN, C_THR, C_BASE = "#3f7cac", "#d6453d", "#c98a2b", "#999999"
COLOR_MAP = {"継続": C_STAY, "離反": C_CHURN}
MODEL_COLORS = {"ベースライン（全員「継続」）": C_BASE, "ロジスティック回帰": "#3f7cac",
                "ランダムフォレスト": "#6a9a4a", "勾配ブースティング": "#8a5fa8"}
FEAT_JP = {k: v[0] for k, v in {**cl.FEATURES, **cl.FEATURES_LEAK}.items()}


def plot(fig, h: int = 320, **kw) -> None:
    has_title = bool(kw.get("title") or fig.layout.title.text)
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=50 if has_title else 10, b=10), **kw)
    st.plotly_chart(fig, width="stretch")


def pct(x: float) -> str:
    return f"{x:.1%}"


# ─────────────────────────────────────────────
# 計算（キャッシュ）
# ─────────────────────────────────────────────
@st.cache_data(show_spinner="データを読み込んでいます…")
def load_sample() -> pd.DataFrame:
    return cl.load_invoices()


@st.cache_data(max_entries=24, show_spinner=False)
def get_snapshot(inv: pd.DataFrame, cutoff, obs_m: int, hor_m: int, net: bool, leak: bool) -> pd.DataFrame:
    return cl.snapshot(inv, cutoff, obs_m, hor_m, net, leak)


@st.cache_data(max_entries=24, show_spinner="4つのモデルを学習・交差検証しています…")
def fit_all(Xtr: pd.DataFrame, ytr: pd.Series, Xte: pd.DataFrame, yte: pd.Series,
            params: tuple, seed: int) -> dict:
    p = dict(params) | {"seed": seed}
    out = {}
    for name in ["ベースライン（全員「継続」）", *cl.MODELS]:
        cv = cl.cv_auc(cl.make_model(name, **p), Xtr, ytr, seed) if "ベースライン" not in name else np.full(5, 0.5)
        m = cl.make_model(name, **p).fit(Xtr, ytr)
        p_tr, p_te = m.predict_proba(Xtr)[:, 1], m.predict_proba(Xte)[:, 1]
        out[name] = {"model": m, "cv": cv, "train_auc": cl.auc(ytr, p_tr), "test_auc": cl.auc(yte, p_te), "p": p_te}
    return out


@st.cache_data(max_entries=8, show_spinner="重要度を計算しています…")
def get_importance(_model, model_key: str, Xte: pd.DataFrame, yte: pd.Series, seed: int) -> pd.Series:
    return cl.importance(_model, Xte, yte, seed)


@st.cache_data(max_entries=8, show_spinner="最新の基準日で、全顧客の離反確率を出しています…")
def deploy(inv: pd.DataFrame, latest, obs_m: int, hor_m: int, net: bool, cols: tuple,
           name: str, params: tuple, seed: int) -> tuple[pd.DataFrame, pd.Timestamp]:
    """答えが分かっている最新の時点（latest − 予測期間）で学び直し、latest 時点の顧客に確率を付ける。"""
    train_cut = pd.Timestamp(latest) - pd.DateOffset(months=hor_m)
    tr = cl.snapshot(inv, train_cut, obs_m, hor_m, net)
    m = cl.make_model(name, **(dict(params) | {"seed": seed})).fit(tr[list(cols)], tr["churn"])
    f = cl.make_features(inv, latest, obs_m, net)
    f["churn_proba"] = m.predict_proba(f[list(cols)])[:, 1]
    f["expected_loss"] = f["churn_proba"] * f["monetary"]
    return f, train_cut


# ─────────────────────────────────────────────
# サイドバー：データと「離反」の定義
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("🛒 離れる顧客を先に見つける")
    src = st.radio("探究するデータ", ["sample", "upload"], key="ch_src",
                   format_func=lambda k: {"sample": "🛒 Online Retail II（英国の雑貨卸・小売）",
                                          "upload": "📂 自分の取引CSVを読み込む"}[k])
    INV = None
    if src == "upload":
        up = st.file_uploader("CSV（1行＝1注文 または 1明細）", type="csv", key="ch_up")
        if up is not None:
            raw = sg.read_csv_safely(up, page=PAGE, kind="churn_csv")
            if raw is not None:
                cols_all = list(raw.columns)
                c_id = st.selectbox("顧客IDの列", cols_all)
                c_inv = st.selectbox("注文番号の列（C始まり＝キャンセル）", cols_all)
                c_dt = st.selectbox("日時の列", cols_all)
                mode = st.radio("金額", ["金額の列がある", "数量×単価で計算"], horizontal=True)
                if mode == "金額の列がある":
                    c_amt = st.selectbox("金額の列（マイナス＝キャンセル）", cols_all)
                    args = dict(amount=c_amt)
                else:
                    args = dict(qty=st.selectbox("数量の列", cols_all), price=st.selectbox("単価の列", cols_all))
                try:
                    INV = cl.from_upload(raw, c_id, c_dt, c_inv, **args)
                    if INV.empty:
                        st.error("使える行がありませんでした。列の選び方を確認してください。")
                        INV = None
                except Exception as e:  # noqa: BLE001
                    sg.log_event("churn_upload_failed", "WARNING", page=PAGE, error=type(e).__name__)
                    st.error("列の組み合わせを読み取れませんでした。")
        st.caption("氏名などの個人情報は入れないでください。顧客IDは仮名の番号に置きかえてから。"
                   "読み込んだ記録はこの画面の中だけで使い、保存しません。")
    else:
        INV = load_sample()

    if INV is not None:
        st.divider()
        st.subheader("「離反」の定義")
        obs_m = st.select_slider("観察期間（特徴量を作る）", [3, 6, 12], value=12, format_func=lambda m: f"{m}か月")
        hor_m = st.select_slider("予測期間（この間に1回も買わなければ離反）", [3, 6, 12], value=12,
                                 format_func=lambda m: f"{m}か月")
        months = cl.month_starts(INV)
        valid = [m for m in months if cl.window_ok(INV, m, obs_m, hor_m) is None]
        if not valid:
            st.error("この観察期間・予測期間は、データの長さに収まりません。短くしてください。")
            st.stop()
        default = pd.Timestamp("2010-12-01") if pd.Timestamp("2010-12-01") in valid else valid[-1]
        cutoff = st.select_slider("基準日（ここで時間を切る）", valid, value=default,
                                  format_func=lambda d: f"{d:%Y/%m/%d}", key=f"ch_cut_{obs_m}_{hor_m}")
        if len(valid) == 1:
            st.caption(f"観察{obs_m}か月＋予測{hor_m}か月はデータ（約2年）にちょうど収まるので、基準日は1つだけです。"
                       "基準日を動かすには、どちらかを短くしてください。")
        net = st.toggle("購入額からキャンセルを差し引く（純購入額）", value=False,
                        help="巨額の注文をすぐ全量キャンセルした顧客が「上得意」に見えるのを防ぎます。")
        seed = int(st.number_input("くじの番号", 0, 9999, 42, 1, help="同じ番号なら同じ分け方・同じ学習結果になります。"))

st.title("🛒 離れる顧客を先に見つける（顧客離反予測）")
st.caption(f"多分野データ解析実践演習 ケース3 ／ データ：{cl.SOURCE} ／ 更新 {UPDATED}")
if INV is None:
    st.info("サイドバーでCSVを読み込み、列を選んでください。")
    st.stop()

SNAP = get_snapshot(INV, cutoff, obs_m, hor_m, net, False)
DATA_A, DATA_B = cl.data_range(INV)
CUT = pd.Timestamp(cutoff)
OBS_START, HOR_END = CUT - pd.DateOffset(months=obs_m), CUT + pd.DateOffset(months=hor_m)
if len(SNAP) < 50 or SNAP["churn"].nunique() < 2:
    st.warning("対象顧客が少なすぎるか、離反・継続のどちらかしかいません。定義を変えてください。")
    st.stop()

tab_flow, tab1, tab2, tab3, tab4 = st.tabs([
    "🧭 この探究の流れ", "❶ 「離れる」を定義し、データを見る", "❷ どのモデルを選ぶか",
    "❸ どう評価し、どう使うか", "📝 マイ判断シート",
])

# ═════════════════════════════════════════════
# 0. 流れ
# ═════════════════════════════════════════════
with tab_flow:
    st.header("🧭 離反予測は「モデル」より先に「定義」を決める")
    st.write("サブスクなら「解約ボタン」で離反がはっきりしますが、この店（英国のオンライン雑貨卸・小売）には"
             "ありません。顧客は**黙って来なくなるだけ**です。だから最初の仕事は、AIを選ぶことではなく、"
             "**「離れた」とは何かを自分たちで決めること**です。決め方で、答えも打ち手も変わります。")
    st.dataframe(pd.DataFrame([
        ("① ビジネス理解", "何を当てたら会社が助かる？「離反」を定義する", "🧭・❶"),
        ("② データ理解", "107万行の明細。欠損・キャンセル・重複を確かめる", "❶"),
        ("③ 前処理", "請求書単位に要約し、基準日で時間を切る（未来を混ぜない）", "❶"),
        ("④ 特徴量", "明細 → 顧客1人1行のカルテ（RFM＋α）", "❶"),
        ("⑤ モデリング", "ベースラインと3つの機械学習モデルを比べる", "❷"),
        ("⑥ 評価・展開", "当たり外れ・リフト・重要度 → 費用対効果 → 引き留めリスト", "❸・📝"),
    ], columns=["DSプロセス（CRISP-DM）", "このページでやること", "タブ"]), width="stretch", hide_index=True)

    st.subheader("「🚨 異常検知の実践知」と、どこが同じで、どこが違うか")
    st.dataframe(pd.DataFrame([
        ("見つけたいもの", "いま起きている「いつもと違う」", "これから起きる「来なくなる」"),
        ("正解ラベル", "ほとんど無い → 教師なしが基本", "時間がたてば分かる → 教師ありが使える"),
        ("いちばんの落とし穴", "手法を先に選ぶ", "未来の情報を特徴量に混ぜる（リーケージ）"),
        ("線を引く", "見逃し と 誤報", "取りこぼし と ムダ打ち（クーポン・電話のコスト）"),
        ("評価", "再現率・適合率・PR曲線", "同じ＋リフト（上位○%で何倍当たるか）"),
        ("鳴ったら", "人が調べる", "人が連絡する（最後は人が判断）"),
    ], columns=["", "異常検知", "離反予測"]), width="stretch", hide_index=True)

    st.subheader("パン屋・農家・学校の「離れる」")
    st.dataframe(pd.DataFrame([
        ("パン屋", "常連の来店が途切れる", "ポイントカードの来店日・購入額", "RFM・来店間隔の伸び"),
        ("農家", "直売所の会員・定期便（CSA）の解約", "注文履歴・受け取り忘れ", "このページと同じ形"),
        ("農業法人", "取引先（スーパー・飲食店）が離れる", "受注データ・クレーム件数", "取引先単位のRFM"),
        ("学校", "学習から離れていく兆候", "提出・ログインの回数", "声かけのきっかけ（判定ではない）"),
    ], columns=["現場", "何が起きるか", "使えるデータ", "考え方"]), width="stretch", hide_index=True)
    st.caption("人に関わる予測は、本人の同意・目的の限定・最後は人が判断する、を必ず守ります。"
               "離反確率は「声をかける順番」を決める道具で、人を評価する点数ではありません。")

    st.subheader("90分の当日の流れ（例）")
    st.dataframe(pd.DataFrame([
        ("0–15分", "定義を決める：観察期間・予測期間・基準日を動かし、離反率がどう変わるかを見る", "❶"),
        ("15–30分", "顧客カルテを見る：離反した人としなかった人は、どこが違う？（仮説を立てる）", "❶"),
        ("30–50分", "モデルを比べる：ベースラインの罠／リーケージの体験／過学習", "❷"),
        ("50–70分", "しきい値と上位○%を動かし、ムダ打ちと取りこぼしの取り合いを体験する", "❸"),
        ("70–90分", "コストと引き留め率を決め、「誰に何をするか」をチームで発表", "📝"),
    ], columns=["時間", "内容", "タブ"]), width="stretch", hide_index=True)

    with st.expander("このページのデータについて"):
        st.markdown(
            f"- 出典：{cl.SOURCE}\n"
            "- 元は約107万行の明細（1行＝1回の注文の中の1商品）。このページでは、ノートブックの前処理③と同じ規則"
            "（完全重複・顧客ID欠損を除く／購入は数量>0・単価>0／C始まりはキャンセル）で、"
            f"**請求書（1回の注文）単位の {len(INV):,} 行**に要約したものを使います（`scripts/build_churn_data.py`）。\n"
            "- そのためノートブックにある「買った商品の種類数」は作れません。ノートブックで重要度がマイナス"
            "（役に立っていない）だったので、省いても精度はほぼ変わりません。\n"
            f"- Colab ノートブック（明細から全部やる版）：`{NOTEBOOK}`（📝 タブの下から開けます）"
        )

# ═════════════════════════════════════════════
# ❶ 定義とデータ
# ═════════════════════════════════════════════
with tab1:
    st.header("❶ 「離れる」をどう定義し、データをどう見るか？")
    st.write("サイドバーで **観察期間・予測期間・基準日** を動かすと、ここから先のすべてが作り直されます。")

    MON = cl.monthly(INV)
    fig = go.Figure()
    fig.add_bar(x=MON.index, y=MON["購入した顧客数"], marker_color="#c8cdd3", name="購入した顧客数",
                hovertemplate="%{x|%Y/%m}：%{y:,} 人<extra></extra>")
    fig.add_vrect(x0=OBS_START, x1=CUT, fillcolor=C_STAY, opacity=.13, line_width=0,
                  annotation_text="観察期間（特徴量）", annotation_position="top left")
    fig.add_vrect(x0=CUT, x1=HOR_END, fillcolor=C_CHURN, opacity=.10, line_width=0,
                  annotation_text="予測期間（正解）", annotation_position="top right")
    fig.add_vline(x=CUT, line_color=C_THR, line_width=2)
    fig.update_yaxes(title="購入した顧客数（月）")
    plot(fig, 300, title=f"基準日 {CUT:%Y/%m/%d} で時間を切る", showlegend=False)

    m = st.columns(4)
    m[0].metric("対象顧客", f"{len(SNAP):,} 人", help="観察期間に1回以上買った顧客")
    m[1].metric("離反率", pct(SNAP["churn"].mean()), help="予測期間に1回も買わなかった割合")
    m[2].metric(f"観察期間（{OBS_START:%Y/%m/%d}〜）", f"{obs_m}か月")
    m[3].metric(f"予測期間（{CUT:%Y/%m/%d}〜）", f"{hor_m}か月")
    st.dataframe(pd.DataFrame([
        ("対象顧客", f"観察期間（{OBS_START:%Y/%m/%d}〜{CUT - pd.Timedelta(days=1):%Y/%m/%d}）に1回以上購入した顧客"),
        ("離反＝1", f"予測期間（{CUT:%Y/%m/%d}〜{HOR_END - pd.Timedelta(days=1):%Y/%m/%d}）に1回も購入しなかった"),
        ("継続＝0", "予測期間に1回以上購入した"),
    ], columns=["用語", "定義"]), width="stretch", hide_index=True)
    st.warning("**鉄則：基準日より後の情報を特徴量に混ぜない（リーケージ防止）。** 現場では明日の行動は見えません。"
               "混ぜると精度が不当に高く出ます（❷ で体験できます）。")

    with st.expander("定義を変えると、離反率はどう変わる？（予測期間 3・6・12か月の比較）"):
        rows = []
        for h in [3, 6, 12]:
            if cl.window_ok(INV, CUT, obs_m, h) is None:
                s_ = get_snapshot(INV, CUT, obs_m, h, net, False)
                rows.append((f"{h}か月", len(s_), s_["churn"].mean()))
        if rows:
            t = pd.DataFrame(rows, columns=["予測期間", "対象顧客", "離反率"])
            st.dataframe(t.style.format({"離反率": "{:.1%}", "対象顧客": "{:,}"}), width="stretch", hide_index=True)
        st.caption("予測期間が短いほど「たまたま買わなかっただけ」の人も離反に数えられ、離反率は上がります。"
                   "卸売の顧客は季節ごとにまとめて買うので、短すぎる定義は誤報のもとです。")

    st.subheader("顧客カルテ（特徴量）")
    st.dataframe(pd.DataFrame([(k, *v) for k, v in cl.FEATURES.items()],
                              columns=["列名", "名前", "意味", "直感（離反との関係）"]), width="stretch", hide_index=True)

    st.subheader("離反した人と、継続した人はどこが違う？")
    show_ans = st.toggle("離反・継続で色を分ける（答え合わせ）", value=True,
                         help="現場の基準日の時点では、まだ誰が離れるかは分かりません。")
    D = SNAP.assign(状態=np.where(SNAP["churn"] == 1, "離反", "継続") if show_ans else "（正解は隠しています）")
    c1, c2 = st.columns([3, 2])
    with c1:
        feat_pick = st.selectbox("見る特徴量", list(cl.FEATURES), format_func=lambda k: FEAT_JP[k], key="ch_eda")
        logx = st.checkbox("横軸を対数にする（金額・回数の偏りをならす）",
                           value=feat_pick in ("frequency", "monetary", "avg_order_value", "monetary_last90"))
        Dp = D.copy()
        if logx:
            Dp[feat_pick] = np.log10(Dp[feat_pick].clip(lower=0) + 1)
        fig = px.histogram(Dp, x=feat_pick, color="状態", barmode="overlay", nbins=40, opacity=.6,
                           histnorm="percent",
                           color_discrete_map=COLOR_MAP | {"（正解は隠しています）": C_STAY},
                           labels={feat_pick: FEAT_JP[feat_pick] + ("（log10(x+1)）" if logx else "")})
        fig.update_yaxes(title="各グループ内の割合（%）")
        plot(fig, 320)
    with c2:
        if show_ans:
            q = pd.qcut(SNAP[feat_pick].rank(method="first"), 4, labels=["①小さい", "②", "③", "④大きい"])
            r = SNAP.groupby(q, observed=True)["churn"].mean()
            fig = px.bar(x=r.index.astype(str), y=r.values, text=[pct(v) for v in r.values],
                         labels={"x": FEAT_JP[feat_pick] + "（4等分）", "y": "離反率"},
                         color_discrete_sequence=[C_CHURN])
            fig.update_yaxes(tickformat=".0%", range=[0, 1])
            plot(fig, 320, title="4等分したグループごとの離反率")
        else:
            st.info("まず色なしで分布を眺め、「どんな人が離れそうか」の仮説を書き出してから、答え合わせをしましょう。")
    if show_ans:
        comp = SNAP.groupby("churn")[list(cl.FEATURES)].median().T
        comp.columns = ["継続の中央値", "離反の中央値"]
        comp.index = [FEAT_JP[i] for i in comp.index]
        st.dataframe(comp.style.format("{:,.2f}"), width="stretch")
        st.caption("離反した人は、最終購入が古く（R大）、回数が少なく（F小）、金額が小さい（M小）。"
                   "👉 仮説：「一見さん（1回だけ購入）」と「最近ご無沙汰の人」が離反の中心では？ ❷ で確かめます。")

    with st.expander("「見かけの上得意」を探す（キャンセルの扱い）"):
        top = SNAP.sort_values("monetary", ascending=False).head(8)[["monetary", "frequency", "n_cancel", "churn"]]
        top.columns = ["購入額合計£", "注文回数", "キャンセル回数", "離反"]
        st.dataframe(top.style.format({"購入額合計£": "{:,.0f}"}), width="stretch")
        st.caption("購入額が大きいのに注文回数1回・キャンセルありの顧客は、「巨額注文 → すぐ全量キャンセル」の可能性があります"
                   "（例：顧客 12346 は観察期間によって上位に出ます）。サイドバーの「キャンセルを差し引く」で消えるか確かめましょう。")
    st.download_button("この顧客カルテをCSVで保存", sg.safe_csv(SNAP, index=True),
                       f"churn_snapshot_{CUT:%Y%m%d}.csv", "text/csv")

# ═════════════════════════════════════════════
# ❷ モデル
# ═════════════════════════════════════════════
with tab2:
    st.header("❷ どの機械学習モデルを選ぶか？")
    st.dataframe(pd.DataFrame([(k, *v) for k, v in cl.MODELS.items()],
                              columns=["モデル", "イメージ", "長所", "短所"]), width="stretch", hide_index=True)

    c1, c2 = st.columns([3, 2])
    with c1:
        how = st.radio("学習用とテスト用の分け方", ["random", "time"], horizontal=True, key="ch_how",
                       format_func=lambda k: {"random": "ランダムに分ける（同じ時期の顧客）",
                                              "time": "時間をずらす（過去で学び、次の期間を当てる）"}[k])
        cols = st.multiselect("使う特徴量", list(cl.FEATURES), default=list(cl.FEATURES),
                              format_func=lambda k: FEAT_JP[k], key="ch_cols")
        leak = st.checkbox("⚠️ リーケージを体験する：「最終購入日」を基準日で切らずにデータ全体から計算した列を混ぜる",
                           key="ch_leak")
    with c2:
        with st.expander("モデルの設定（ハイパーパラメータ）", expanded=False):
            C = st.select_slider("ロジスティック回帰：正則化の弱さ C", [0.01, 0.1, 1.0, 10.0, 100.0], value=1.0)
            n_est = st.select_slider("ランダムフォレスト：木の数", [50, 100, 200, 400], value=200)
            leaf = st.select_slider("ランダムフォレスト：葉の最小人数", [1, 5, 20, 50], value=20,
                                    help="1にすると1人ずつ覚え込める＝過学習しやすい")
            lr = st.select_slider("勾配ブースティング：学習率", [0.01, 0.03, 0.1, 0.3], value=0.03)
            depth = st.select_slider("勾配ブースティング：木の深さ", [2, 3, 5, 8], value=3)
        st.caption("葉の最小人数を 1 に、学習率を 0.3・深さを 8 にすると、学習用AUCだけが上がり、"
                   "テストAUCは上がらない（過学習）様子が見られます。")
    if not cols:
        st.warning("特徴量を1つ以上選んでください。")
        st.stop()
    use = cols + ([cl.LEAK] if leak else [])
    PARAMS = (("C", C), ("n_estimators", n_est), ("min_samples_leaf", leaf),
              ("learning_rate", lr), ("max_depth", depth))

    if how == "random":
        S = get_snapshot(INV, CUT, obs_m, hor_m, net, leak)
        Xtr, Xte, ytr, yte = cl.split(S, use, seed=seed)
        SPLIT_NOTE = f"基準日 {CUT:%Y/%m/%d} の顧客を、学習用 {len(Xtr):,} 人／テスト用 {len(Xte):,} 人にランダムに分けました。"
    else:
        tr_cut = CUT - pd.DateOffset(months=hor_m)
        why = cl.window_ok(INV, tr_cut, obs_m, hor_m)
        if why:
            st.error(f"時間をずらすには、学習用の基準日 {tr_cut:%Y/%m/%d} が必要ですが、{why}"
                     "観察期間・予測期間を短くするか（例：6か月・6か月）、基準日を後ろにしてください。")
            st.stop()
        S_tr = get_snapshot(INV, tr_cut, obs_m, hor_m, net, leak)
        S = get_snapshot(INV, CUT, obs_m, hor_m, net, leak)
        Xtr, ytr, Xte, yte = S_tr[use], S_tr["churn"], S[use], S["churn"]
        SPLIT_NOTE = (f"学習用＝基準日 {tr_cut:%Y/%m/%d} の顧客 {len(Xtr):,} 人（答えは {CUT:%Y/%m/%d} までに確定）、"
                      f"テスト用＝基準日 {CUT:%Y/%m/%d} の顧客 {len(Xte):,} 人。本番と同じ「過去で学んで未来を当てる」形です。")
    st.info(SPLIT_NOTE)
    RES = fit_all(Xtr, ytr, Xte, yte, PARAMS, seed)

    tbl = pd.DataFrame([(k, v["cv"].mean(), v["cv"].std(), v["train_auc"], v["test_auc"]) for k, v in RES.items()],
                       columns=["モデル", "交差検証AUC（平均）", "ばらつき", "学習用AUC", "テストAUC"])
    c1, c2 = st.columns([3, 2])
    with c1:
        fig = go.Figure()
        for _, r in tbl.iterrows():
            fig.add_bar(x=[r["モデル"]], y=[r["交差検証AUC（平均）"]], name=r["モデル"],
                        marker_color=MODEL_COLORS[r["モデル"]],
                        error_y=dict(type="data", array=[r["ばらつき"]], visible=True),
                        text=[f"{r['交差検証AUC（平均）']:.3f}"], textposition="outside",
                        hovertemplate="%{x}<br>CV AUC %{y:.3f}<extra></extra>")
        fig.add_hline(y=0.5, line_dash="dash", line_color=C_BASE, annotation_text="0.5＝サイコロと同じ")
        fig.update_yaxes(range=[0.4, 1.05], title="AUC（5分割交差検証）")
        plot(fig, 340, showlegend=False, title="学習用データの中での実力比べ（テストはまだ見ない）")
    with c2:
        st.dataframe(tbl.set_index("モデル").style.format("{:.3f}"), width="stretch")
        st.markdown("**AUC**：離反者と継続者を1人ずつ選んだとき、離反者の方を「より危ない」と正しく並べられる確率。"
                    "0.5＝サイコロ、1.0＝完璧。")
        b = cl.confusion(yte, RES["ベースライン（全員「継続」）"]["p"])
        st.markdown(f"**ベースラインの罠**：全員「継続」と答えるだけで正解率 **{pct(b['正解率'])}**。"
                    f"でも離反者は **{b['TP']} 人**しか見つけていません。正解率だけでAIを評価してはいけません。")

    best_ml = max(cl.MODELS, key=lambda k: RES[k]["cv"].mean())
    spread = tbl.set_index("モデル").loc[list(cl.MODELS), "交差検証AUC（平均）"]
    if leak:
        st.error(f"⚠️ AUC が {RES[best_ml]['test_auc']:.3f} まで跳ね上がりました。これは喜ぶ数字ではなく**疑う数字**です。"
                 "「最終購入日」をデータ全体から計算したため、基準日より後に買った人＝継続、と答えが漏れています。"
                 "現場では、基準日の時点で未来の購入日は分かりません。")
    elif spread.max() - spread.min() < 0.02:
        st.success(f"3モデルの差は {spread.max() - spread.min():.3f} とごくわずか（ばらつきの範囲内）。"
                   "👉 **複雑なAIほど強いとは限らない。** 精度を決めているのは、モデルの種類より**顧客カルテ（特徴量）の質**です。")
    gap = {k: RES[k]["train_auc"] - RES[k]["test_auc"] for k in cl.MODELS}
    if max(gap.values()) > 0.1:
        k = max(gap, key=gap.get)
        st.warning(f"**過学習**：{k} は学習用AUC {RES[k]['train_auc']:.3f} に対し、テストAUC {RES[k]['test_auc']:.3f}。"
                   "学習用の顧客を「暗記」して、初めての顧客には効いていません。")

    MAIN = st.selectbox("❸・📝 で使うモデル", list(cl.MODELS), index=list(cl.MODELS).index("ランダムフォレスト"),
                        key="ch_main", help=f"交差検証で最も高かったのは「{best_ml}」です。")

# ═════════════════════════════════════════════
# ❸ 評価と使い方
# ═════════════════════════════════════════════
with tab3:
    st.header("❸ どう評価し、どう使うか？")
    R = RES[MAIN]
    P, Y = R["p"], yte.to_numpy()
    st.markdown(f"##### 使うモデル：{MAIN}（❷ の下で切り替え）")
    m = st.columns(4)
    m[0].metric("学習用AUC", f"{R['train_auc']:.3f}")
    m[1].metric("テストAUC", f"{R['test_auc']:.3f}")
    m[2].metric("テスト用の顧客", f"{len(Y):,} 人")
    m[3].metric("実際の離反率", pct(Y.mean()))

    st.subheader("① しきい値：何%以上を「離反しそう」と判定するか")
    thr = st.slider("しきい値（離反確率）", 0.05, 0.95, 0.50, 0.05, key="ch_thr")
    cf = cl.confusion(Y, P, thr)
    c1, c2 = st.columns([2, 3])
    with c1:
        z = [[cf["TN"], cf["FP"]], [cf["FN"], cf["TP"]]]
        txt = [[f"継続を継続<br><b>{cf['TN']}</b>", f"ムダ打ち<br><b>{cf['FP']}</b>"],
               [f"取りこぼし<br><b>{cf['FN']}</b>", f"見つけた<br><b>{cf['TP']}</b>"]]
        fig = go.Figure(go.Heatmap(z=z, x=["継続と予測", "離反と予測"], y=["実際は継続", "実際は離反"],
                                   text=txt, texttemplate="%{text}", colorscale="Blues", showscale=False,
                                   hoverinfo="skip"))
        fig.update_yaxes(autorange="reversed")
        plot(fig, 300, title="混同行列")
    with c2:
        mm = st.columns(3)
        mm[0].metric("適合率", pct(cf["適合率"]), help="「離反」と判定した人のうち、本当に離反した割合（ムダ打ちの少なさ）")
        mm[1].metric("再現率", pct(cf["再現率"]), help="本当に離反した人のうち、見つけられた割合（取りこぼしの少なさ）")
        mm[2].metric("連絡する人数", f"{cf['離反と判定した人数']:,} 人")
        st.dataframe(pd.DataFrame([
            ("しきい値を下げる", "連絡する人が増える", "取りこぼし↓・ムダ打ち↑", "施策が安い（メール）とき"),
            ("しきい値を上げる", "連絡する人が減る", "取りこぼし↑・ムダ打ち↓", "施策が高い（訪問・値引き）とき"),
        ], columns=["操作", "人数", "結果", "向いている場面"]), width="stretch", hide_index=True)
        st.caption("どちらを優先するかはAIではなく**ビジネスの判断**です（📝 で金額にして決めます）。")

    roc, prc = cl.curves(Y, P)
    c1, c2 = st.columns(2)
    with c1:
        fig = px.line(roc, x="誤報率", y="再現率", color_discrete_sequence=[MODEL_COLORS[MAIN]])
        fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(dash="dash", color=C_BASE), hoverinfo="skip")
        fig.add_scatter(x=[cf["FP"] / max(cf["FP"] + cf["TN"], 1)], y=[cf["再現率"]], mode="markers",
                        marker=dict(size=12, color=C_THR), hovertemplate="いまのしきい値<extra></extra>")
        plot(fig, 300, title=f"ROC曲線（AUC {R['test_auc']:.3f}）", showlegend=False)
    with c2:
        fig = px.line(prc, x="再現率", y="適合率", color_discrete_sequence=[MODEL_COLORS[MAIN]])
        fig.add_hline(y=Y.mean(), line_dash="dash", line_color=C_BASE, annotation_text="ランダムに選んだ場合")
        fig.add_scatter(x=[cf["再現率"]], y=[cf["適合率"]], mode="markers", marker=dict(size=12, color=C_THR),
                        hovertemplate="いまのしきい値<extra></extra>")
        fig.update_yaxes(range=[0, 1.02])
        plot(fig, 300, title="PR曲線：取りこぼしとムダ打ちの取り合い", showlegend=False)

    st.subheader("② 現場の使い方：「危ない順」の上位だけに手を打つ")
    k = st.slider("施策を打つ顧客の割合（離反確率の高い順）", 0.05, 1.0, 0.30, 0.05, key="ch_k", format="%.2f")
    gc = cl.gain_curve(Y, P)
    covered = gc["カバーできた離反者の割合"].iloc[max(int(round(len(gc) * k)) - 1, 0)]
    c1, c2 = st.columns([3, 2])
    with c1:
        fig = px.line(gc, x="施策を打つ割合", y="カバーできた離反者の割合", color_discrete_sequence=[C_CHURN])
        fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(dash="dash", color=C_BASE), hoverinfo="skip")
        fig.add_vline(x=k, line_color=C_THR, annotation_text=f"上位{k:.0%} → 離反者の{covered:.0%}")
        fig.update_xaxes(tickformat=".0%")
        fig.update_yaxes(tickformat=".0%")
        plot(fig, 320, title="累積ゲイン曲線（点線＝ランダムに選んだ場合）", showlegend=False)
    with c2:
        g = cl.gain_table(Y, P, sorted({0.1, 0.2, 0.3, 0.5, round(k, 2)}))
        st.dataframe(g.style.format({"当たり率（適合率）": "{:.1%}", "カバー率（再現率）": "{:.1%}",
                                     "リフト（倍）": "{:.2f}"}), width="stretch", hide_index=True)
        st.caption(f"ランダムに選ぶと当たり率は {pct(Y.mean())}。**リフト**は「AIの順位で選ぶと何倍当たるか」です。")

    st.subheader("③ 解釈：AIは何を手がかりにしたか")
    c1, c2 = st.columns(2)
    with c1:
        imp = get_importance(R["model"], f"{MAIN}|{PARAMS}|{use}|{how}|{CUT}|{obs_m}|{hor_m}|{net}|{seed}",
                             Xte, yte, seed).sort_values()
        fig = px.bar(x=imp.values, y=[FEAT_JP[i] for i in imp.index], orientation="h",
                     color_discrete_sequence=[MODEL_COLORS[MAIN]],
                     labels={"x": "シャッフルしたときのAUCの下がり幅", "y": ""})
        plot(fig, 380, title=f"順列重要度（{MAIN}）")
        st.caption("その列だけをでたらめに並べ替えたとき、AUCがどれだけ下がるか。0以下＝無くても困らない列です。")
    with c2:
        co = cl.coefficients(RES["ロジスティック回帰"]["model"], use)
        if co is not None:
            fig = px.bar(x=co.values, y=[FEAT_JP[i] for i in co.index], orientation="h",
                         color=np.where(co.values > 0, "離反しやすい方向", "継続しやすい方向"),
                         color_discrete_map={"離反しやすい方向": C_CHURN, "継続しやすい方向": C_STAY},
                         labels={"x": "係数（標準化後）", "y": "", "color": ""})
            plot(fig, 380, title="ロジスティック回帰の係数（向きが読める）")
    st.warning("**相関は原因ではありません。** 「最終購入からの日数が長いから離れる」のではなく、"
               "「離れつつある人は日数が長くなる」のかもしれません。施策で離反が減るかは、A/Bテストや因果推論で確かめます。")

# ═════════════════════════════════════════════
# 📝 マイ判断シート
# ═════════════════════════════════════════════
with tab4:
    st.header("📝 マイ判断シート：誰に、いくらかけて、何をするか")
    st.subheader("① 費用対効果（テスト用の顧客で答え合わせ）")
    c1, c2, c3 = st.columns(3)
    cost = c1.number_input("1人あたり施策コスト（£）", 0.0, 1000.0, 30.0, 1.0,
                           help="クーポン・郵送・担当者の時間など（仮定）")
    save = c2.slider("引き留められる割合（施策を打った離反予定者のうち）", 0.0, 1.0, 0.20, 0.05)
    order = c3.radio("並べ順", ["期待損失（確率×購入額）", "離反確率"], horizontal=False)
    roi = cl.roi_table(Y, P, S.loc[Xte.index, "monetary"], cost, save,
                       by_expected_loss=order.startswith("期待"))
    best = roi.loc[roi["差引£"].idxmax()]
    fig = go.Figure()
    fig.add_scatter(x=roi["割合"], y=roi["守れた売上£"], name="守れた売上", line=dict(color=C_STAY, width=2))
    fig.add_scatter(x=roi["割合"], y=roi["施策コスト£"], name="施策コスト", line=dict(color=C_BASE, width=2, dash="dash"))
    fig.add_scatter(x=roi["割合"], y=roi["差引£"], name="差引", line=dict(color=C_CHURN, width=2))
    fig.add_vline(x=best["割合"], line_color=C_THR, annotation_text=f"差引が最大：上位{best['割合']:.0%}")
    fig.update_xaxes(tickformat=".0%", title="施策を打つ顧客の割合")
    fig.update_yaxes(title="£（前年の購入額で近似）")
    plot(fig, 340, title="上位何%まで施策を打つか")
    mm = st.columns(4)
    mm[0].metric(f"差引が最大になる範囲（{int(best['人数']):,}人）", f"上位 {best['割合']:.0%}")
    mm[1].metric("そのときの差引", f"£{best['差引£']:,.0f}")
    mm[2].metric("費用対効果", f"{best['費用対効果（倍）']:.1f} 倍")
    mm[3].metric("全員に打った場合の差引", f"£{roi['差引£'].iloc[-1]:,.0f}")
    st.caption("上位に絞るほど費用対効果（倍）は高い一方、差引の総額は対象を広げると増えることもあります。"
               "「あと1人増やしたときの増分がコストを上回るか」（限界効果）で止める場所を決めます。"
               "コストを £10（メールだけ）や £50（担当者が訪問）に変えると、止めるべき場所が動きます。")

    st.subheader(f"② 本番：最新の基準日で「次の{hor_m}か月に離れそうな顧客」リスト")
    LATEST = DATA_B
    why = cl.window_ok(INV, LATEST - pd.DateOffset(months=hor_m), obs_m, hor_m)
    if why:
        st.error(f"本番用の学習に必要な期間がデータに収まりません：{why}")
    else:
        scored, tr_cut = deploy(INV, LATEST, obs_m, hor_m, net, tuple(cols), MAIN, PARAMS, seed)
        st.info(f"答えが確定している最新の時点（基準日 {tr_cut:%Y/%m/%d}）で「{MAIN}」を学び直し、"
                f"データ最終日の翌日 **{LATEST:%Y/%m/%d}** を基準日に、{len(scored):,} 人の離反確率を出しました。"
                "**この答えはまだ誰も知りません**（ここが本番の運用です）。リーケージの列は使っていません。")
        c1, c2 = st.columns(2)
        risk_thr = c1.slider("離反リスクが高いとみなす確率", 0.1, 0.9, 0.5, 0.05, key="ch_risk")
        vq = c2.slider("価値が高いとみなす購入額（上位何%）", 0.05, 0.5, 0.25, 0.05, key="ch_vq")
        vline = scored["monetary"].quantile(1 - vq)
        scored["segment"] = cl.segment(scored["churn_proba"], scored["monetary"], risk_thr, vline)
        summ = scored.groupby("segment").agg(人数=("churn_proba", "size"), 平均離反確率=("churn_proba", "mean"),
                                             購入額合計=("monetary", "sum"), 期待損失合計=("expected_loss", "sum"))
        summ.index = [f"{cl.SEGMENTS[s][0]}：{cl.SEGMENTS[s][1]}" for s in summ.index]
        c1, c2 = st.columns([2, 3])
        with c1:
            cnt = scored["segment"].value_counts()
            grid = [[f"{cl.SEGMENTS['A'][0]}<br><b>{cnt.get('A', 0):,}人</b>", f"{cl.SEGMENTS['B'][0]}<br><b>{cnt.get('B', 0):,}人</b>"],
                    [f"{cl.SEGMENTS['C'][0]}<br><b>{cnt.get('C', 0):,}人</b>", f"{cl.SEGMENTS['D'][0]}<br><b>{cnt.get('D', 0):,}人</b>"]]
            fig = go.Figure(go.Heatmap(z=[[3, 2], [1, 0]], x=[f"価値が高い（上位{vq:.0%}）", "価値がふつう"],
                                       y=[f"リスク高（≥{risk_thr:.0%}）", "リスク低"], text=grid,
                                       texttemplate="%{text}", showscale=False, hoverinfo="skip",
                                       colorscale=[[0, "#eef2f6"], [0.34, "#cfe3f3"], [0.67, "#f6e3c3"], [1, "#f3c9c5"]]))
            fig.update_yaxes(autorange="reversed")
            plot(fig, 280, title="リスク × 価値 の4区分")
        with c2:
            st.dataframe(summ.style.format({"平均離反確率": "{:.1%}", "購入額合計": "£{:,.0f}", "期待損失合計": "£{:,.0f}",
                                            "人数": "{:,}"}), width="stretch")
            st.caption("A は人数が少ないのに期待損失が大きい＝少人数に手厚く。C は離反確率が低くても売上の大半を占めるので、"
                       "離反予測とは別に「守り」の施策が要ります。")
        out = scored.sort_values("expected_loss", ascending=False)[
            ["segment", "churn_proba", "monetary", "expected_loss", "recency_days", "frequency", "n_cancel"]]
        out.columns = ["区分", "離反確率", "購入額£", "期待損失£", "最終購入からの日数", "注文回数", "キャンセル回数"]
        st.markdown("##### 引き留め優先リスト（期待損失の大きい順・上位20）")
        st.dataframe(out.head(20).style.format({"離反確率": "{:.0%}", "購入額£": "{:,.0f}", "期待損失£": "{:,.0f}"}),
                     width="stretch")
        if not net and 12346 in out.index[:20]:
            st.warning("⚠️ 顧客 12346 が上位にいます。「巨額注文 → 直後に全量キャンセル」の顧客で、価値が過大に見えています。"
                       "**AIのリストは最後に人が確かめる。** サイドバーの「キャンセルを差し引く」をオンにすると消えます。")
        st.download_button("引き留め優先リストをCSVで保存", sg.safe_csv(out, index=True),
                           f"churn_priority_{LATEST:%Y%m%d}.csv", "text/csv")

    st.subheader("③ 自分の判断と、その理由")
    st.text_area("（数字を1つ以上入れる）", key="ch_note", height=120,
                 placeholder="例：施策コスト£30・引き留め率20%なら、差引が最大になるのは上位45%前後。"
                             "A区分の35人は担当者が電話、B区分はクーポンメール。12346 は人が確認してから。"
                             "3か月後に、打った人と打たなかった人の購入率を比べて引き留め率を測り直す。")
    st.caption("この欄の文章はサーバーに保存されません。必要ならコピーして手元に残してください。")

    st.subheader("Colab ノートブック（明細107万行から全部やる版）")
    st.write("このページは要約データで動きます。前処理から自分の手で通したいときはノートブックを使います"
             "（`online_retail_II.xlsx` を Google ドライブの「マイドライブ」直下に置いて、上から ▶）。")
    st.link_button("▶ ノートブックを Google Colab で開く", mg.colab_url(NOTEBOOK))

    with st.expander("次の一歩（因果・ベイズ・強化学習・セキュリティへ）"):
        st.markdown(
            "- **因果AI（アップリフトモデリング）**：「施策を打つと行動が変わる人」だけを狙う。"
            "放っておいても残る人・何をしても去る人に打つのはムダ。A/Bテストで「打った群／打たない群」を作り、"
            "T-learner・X-learner で効果の個人差を推定する\n"
            "- **ベイズ推論（BG/NBD・Pareto/NBD）**：「まだ顧客であり続けている確率 P(alive)」を購入回数と最終購入日から"
            "確率モデルで推定し、機械学習の離反確率と比べる。データの少ない顧客ほど事前分布が効く（`pymc-marketing`）\n"
            "- **強化学習（文脈付きバンディット）**：誰に・どの施策（メール／クーポン／電話）を打つかを、"
            "反応を見ながら学び直す。報酬＝守れた売上 − コスト\n"
            "- **時間をずらした検証を標準に**：❷ の「時間をずらす」で、6か月→6か月の検証を回す（本番に近い評価）\n"
            "- **生成AI×セキュリティ**：顧客データは仮名化・最小権限で扱う。生成AIに顧客リストを渡すときは"
            "IDだけにし、プロンプトに指示が混ざっていないか（プロンプトインジェクション）を確かめる"
        )
    st.caption(f"データ：{cl.SOURCE}。本ページの文章・計算はこのアプリ独自のものです。")

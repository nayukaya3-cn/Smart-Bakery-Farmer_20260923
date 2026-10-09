"""
スマートパン屋農家を始める！ — 情報発信ダッシュボード
Streamlit + Plotly

起動: streamlit run app.py
構成: 計算する → 可視化する → 自分の条件で判断する（3段構え）
"""
import re
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import media_gallery as mg
import security_guard as sg
import soil_vision as sv

# ─────────────────────────────────────────────
# 基本設定
# ─────────────────────────────────────────────
FACEBOOK_URL = "https://www.facebook.com/profile.php?id=100079624235158"
COCRE_HUB_URL = "https://cocrehub.com/"
FIELD_AREA_M2 = 96  # 圃場面積（㎡）
JOHO1_NOTEBOOK = "notebooks/joho1_examples.ipynb"  # 情報Ⅰの例題ノートブック（Colabで開く）
ASSETS = Path(__file__).parent / "assets"
PHOTO_LOG = {  # フォルダ名(YYYYMMDD) → 写真キャプション
    "20260913": "草刈り後、小麦畑の整備を開始",
    "20260923": "圃場に風車（かざぐるま）を設置",
    "20261003": "米ぬか発酵肥料・果樹の植栽・AI土壌診断・獣害対策",
}
SOW_DAY = date(2026, 10, 20)  # 播種目標日（実体験上の発芽率最適期）
SCHOOL_PAGE = "pages/1_📋_学校向け_記録が残る探究.py"  # 学校向け：ルーブリック・活動ログ・記録ダッシュボード


def safe_page_link(page: str, label: str, icon: str) -> None:
    """ページが見つからない環境でもアプリ全体が止まらないようにする。"""
    try:
        st.page_link(page, label=label, icon=icon)
    except Exception:  # noqa: BLE001
        st.caption(f"{icon} {label}（左のメニューから開けます）")


def school_banner() -> None:
    """学校向けページへの入口（ホーム・探究学習・受け入れ体制で共用）。"""
    with st.container(border=True):
        b1, b2 = st.columns([3, 1])
        b1.markdown(
            "**📋 学校の先生方へ：記録が残る探究**　"
            "生徒が「いつ・何時間・何をして・何を身につけたか」を、"
            "**ルーブリック・活動ログ・記録ダッシュボード**の3点セットで残し、学校にお渡しします。"
            "外部と連携した学習の「適正な教育」を、学校が説明できる形にします。"
        )
        with b2:
            safe_page_link(SCHOOL_PAGE, "記録の仕組みを見る", "➡️")

st.set_page_config(
    page_title="スマートパン屋農家を始める！",
    page_icon="🌾",
    layout="wide",
)

st.markdown(
    """
    <style>
    .hero {padding: 1.8rem 2rem 1.6rem; border-radius: 16px;
           background: linear-gradient(120deg, #f6e7c8 0%, #e3efd6 100%);
           color: #3b2f1e; margin-bottom: 1rem;}
    .hero .eyebrow {font-size: .85rem; letter-spacing: .08em; color: #8a6a3a; margin: 0 0 .4rem 0;}
    .hero h1 {margin: 0 0 .6rem 0; font-size: 2.2rem; line-height: 1.25; color: #3b2f1e;}
    .hero .lead {margin: 0 0 .9rem 0; font-size: 1.08rem; line-height: 1.8;}
    .hero .motto {display: inline-block; margin: 0; padding: .35rem .8rem; border-radius: 999px;
                  background: rgba(255,255,255,.65); font-size: .95rem; font-weight: 600;}
    .cycle {display: flex; flex-wrap: wrap; align-items: center; gap: .35rem; margin: .4rem 0 1rem;}
    .cycle span.step {padding: .35rem .75rem; border-radius: 10px; background: #f3ecdf;
                      color: #3b2f1e; font-size: .92rem; white-space: nowrap;}
    .cycle span.arrow {color: #a08a68;}
    .note {font-size: .85rem; color: #7a6a55;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────
# サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("🌾 スマートパン屋農家")
    st.write("麦を育て、数値で判断し、パンを焼く。")
    st.link_button("📘 Facebookで活動を見る", FACEBOOK_URL, width="stretch")
    safe_page_link(SCHOOL_PAGE, "学校向け：記録が残る探究", "📋")
    st.divider()
    st.caption("拠点：広島県三原市西部（ハウス・畑区画）")
    st.caption(f"圃場面積：約 {FIELD_AREA_M2} ㎡")
    st.caption("このページの数値モデルは説明用の仮定値を含みます。")

# ─────────────────────────────────────────────
# データ：ロードマップと活動ログ（ホームと活動ログタブで共用）
# ─────────────────────────────────────────────
ROADMAP = [
    ("草刈り・片付け",                 "2026-09-13", "2026-09-30"),
    ("獣害対策（柵・周囲の草刈り）",   "2026-09-17", "2026-10-31"),
    ("米ぬか発酵肥料づくり",           "2026-09-22", "2026-10-31"),
    ("土壌診断（AI画像解析＋分析）",   "2026-09-24", "2026-10-14"),
    ("ハウス周囲の通路（車椅子対応）", "2026-10-04", "2026-10-25"),
    ("耕起・畝立て",                   "2026-10-10", "2026-10-18"),
    ("播種（最適期 10/20頃）",         "2026-10-18", "2026-10-31"),
    ("生育管理・センサー観測",         "2026-11-01", "2027-05-31"),
    ("追肥（AI生育ムラ診断）",         "2027-02-01", "2027-03-31"),
    ("収穫・乾燥・製粉",               "2027-06-01", "2027-07-15"),
    ("試作パン・教材づくり",           "2027-07-01", "2027-09-30"),
]


def roadmap_with_status(today: date) -> pd.DataFrame:
    df = pd.DataFrame(ROADMAP, columns=["工程", "開始", "終了"])
    s, e = pd.to_datetime(df["開始"]).dt.date, pd.to_datetime(df["終了"]).dt.date
    df["状態"] = np.where(e < today, "完了", np.where(s <= today, "進行中", "予定"))
    return df


LOG_CSV = Path(__file__).parent / "data" / "activity_log.csv"  # 活動ログの保存先（ここを更新すれば消えない）


def load_activity_log() -> pd.DataFrame:
    """data/activity_log.csv を読む。無い・壊れているときは、下の初期データで表示を続ける。"""
    try:
        df = pd.read_csv(LOG_CSV, encoding="utf-8-sig", dtype=str).fillna("")
        df = df[["日付", "カテゴリ", "内容"]]
        # CSV保存時に付けた数式よけの「'」を外す
        df = df.apply(lambda c: c.str.replace(r"^'(?=[=+\-@])", "", regex=True).str.strip())
        df["日付"] = pd.to_datetime(df["日付"], errors="coerce").dt.date
        df = df.dropna(subset=["日付"])
        df = df[df["内容"] != ""]
        if not df.empty:
            return df.reset_index(drop=True)
    except Exception:  # noqa: BLE001  ファイルが無い・列が違う
        pass
    return pd.DataFrame([
        dict(日付=date(2026, 9, 13), カテゴリ="圃場", 内容="草刈り後、小麦畑の整備を開始。"),
        dict(日付=date(2026, 9, 17), カテゴリ="圃場", 内容="ハウス脇・母屋裏の2区画で草刈り。工具・ガラの片付けと土壌診断の準備へ。"),
        dict(日付=date(2026, 9, 17), カテゴリ="獣害対策", 内容="イノシシ対策：物理的な柵と周囲の草刈り（隠れ場所・エサをなくす環境整備）を開始、継続中。焼き畑の煙は数日で効果が切れるため主対策にしない。"),
        dict(日付=date(2026, 9, 23), カテゴリ="土づくり", 内容="米ぬか発酵肥料づくり開始。柿の小枝・天日干しした雑草の上に米ぬか2袋を投入。"),
        dict(日付=date(2026, 9, 23), カテゴリ="圃場", 内容="ペットボトルでモグラよけ風車を作り、圃場に設置。"),
        dict(日付=date(2026, 9, 23), カテゴリ="発信", 内容="「スマートパン屋農家を始める！」発信開始。"),
        dict(日付=date(2026, 9, 24), カテゴリ="発信", 内容="AI土壌診断（写真→生育ムラ→施肥設計、指標植物のベイズ推定）をダッシュボードに追加。"),
        dict(日付=date(2026, 10, 3), カテゴリ="栽培", 内容="果樹（柿・キウイ・栗）を植栽。"),
        dict(日付=date(2026, 10, 4), カテゴリ="圃場", 内容="ハウスの周囲に通路づくりを開始。車椅子でも一周できる幅で整備中。"),
    ])


if "log" not in st.session_state:
    st.session_state.log = load_activity_log()

# 表に出すのは、学校の先生が3分で判断するのに必要な4つだけ。
# ほかは「🔎 詳しく見る」の中にまとめる（中身のコードは変えずに、置き場所だけ変える）。
MAIN_TABS = ["🏠 ホーム", "🎓 探究学習（構想）", "🤝 受け入れ体制", "📝 活動ログ"]
MORE_TAB = "🔎 詳しく見る"
DETAIL_TABS = [
    "🌱 小麦の播種シミュレーター", "📡 圃場モニター", "🍞 原料レジリエンス",
    "📷 圃場フォト", "🔬 AI土壌診断", "🖨️ 3Dプリンター", "🤖 AIロボット", "💻 情報Ⅰ",
]
_main = st.tabs(MAIN_TABS + [MORE_TAB])
T = dict(zip(MAIN_TABS, _main))  # タブは名前で指定する（並べ替えても壊れない）
with _main[-1]:
    st.caption("畑のデータ・AI・ものづくりの記録です。気になるものからどうぞ。")
    T.update(zip(DETAIL_TABS, st.tabs(DETAIL_TABS)))


def three_minute_course() -> None:
    """学校の先生向け3分コース：どんな場所か → 安全と記録 → 次の一歩。"""
    st.subheader("⏱️ 学校の先生向け 3分コース")
    st.caption("このページは情報が多いので、判断に必要なことだけを3つにまとめました。")
    a, b, c = st.columns(3)
    with a.container(border=True):
        st.markdown(
            "**① 1分：どんな場所か**\n\n"
            f"三原市西部の約{FIELD_AREA_M2}㎡の畑。小麦を育ててパンを焼くまでを、"
            "**計算する → 可視化する → 自分の条件で判断する** の3段構えで探究します。\n\n"
            "想定する連携先：通信制高校・サポート校の探究、総合型選抜に向けた探究、特別支援学校の現場実習。"
        )
        st.caption("詳しくは「🎓 探究学習（構想）」タブ")
    with b.container(border=True):
        st.markdown(
            "**② 1分：安全と記録**\n\n"
            "生徒が「いつ・何時間・何をして・何を身につけたか」を、"
            "ルーブリック・活動ログ・実施報告書の3点で残し、学校にお渡しします。\n\n"
            "受け入れ準備の進み具合（保険・緊急時対応など）は、**未整備の項目も含めて**公開しています。"
        )
        safe_page_link(SCHOOL_PAGE, "記録の仕組みを見る", "📋")
        st.caption("準備状況は「🤝 受け入れ体制」タブ")
    with c.container(border=True):
        st.markdown(
            "**③ 1分：次の一歩**\n\n"
            "いまは畑の土台づくりの段階で、**受け入れ実績はまだありません**。"
            "本格的な受け入れは2029年ごろを目安にしています。\n\n"
            "それまでの間も、ご意見や情報交換は歓迎です。"
        )
        st.link_button("📘 Facebookで声をかける", FACEBOOK_URL, width="stretch")
    st.divider()

# ═════════════════════════════════════════════
# 1. ホーム
# ═════════════════════════════════════════════
with T["🏠 ホーム"]:
    st.markdown(
        f"""
        <div class="hero">
          <p class="eyebrow">広島県三原市 ・ 約{FIELD_AREA_M2}㎡の小さな畑から</p>
          <h1>スマートパン屋農家を始める！</h1>
          <p class="lead">畑の小麦から、一斤のパンまで。<br>
          土の状態も、麦の育ち方も、パンの原価も。センサー・AI・ロボットで<b>数字にして見える化</b>し、必要な道具は3Dプリンターで自作しながら、
          小さな農とパンの循環を、三原でひとつずつ形にしていきます。</p>
          <p class="motto">噂や雰囲気ではなく、自分の数値で決める。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    three_minute_course()

    # この畑でつくる循環（米ぬか・残渣 → 発酵肥料 → 土 へ戻す）
    cycle = ["🌱 土づくり", "🌾 小麦を育てる", "⚙️ 収穫・製粉", "🍞 パンを焼く", "♻️ 米ぬか・残渣を発酵肥料に"]
    st.markdown(
        '<div class="cycle">'
        + '<span class="arrow">→</span>'.join(f'<span class="step">{s}</span>' for s in cycle)
        + '<span class="arrow">→ 土へ戻す</span></div>',
        unsafe_allow_html=True,
    )

    today = date.today()
    current = roadmap_with_status(today)
    # 進行中の工程のうち、いちばん最近始めたものを「いまの工程」として表示
    doing = current[current["状態"] == "進行中"].sort_values("開始", ascending=False)["工程"].tolist()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("圃場面積", f"{FIELD_AREA_M2} ㎡")
    c1.caption("ハウス・畑の2区画")
    c2.metric("播種目標日", SOW_DAY.strftime("%m/%d"))
    c2.caption(f"あと {(SOW_DAY - today).days} 日（発芽率の最適期）" if SOW_DAY >= today else "播種済み")
    c3.metric("栽培品目", "パン用小麦")
    c3.caption("ほかに柿・キウイ・栗")
    c4.metric("進行中の工程", f"{len(doing)} 件")
    c4.caption(f"最新：{doing[0]}" if doing else "—")

    left, right = st.columns([3, 2])
    with left:
        st.subheader("3段構えで進めます")
        s1, s2, s3 = st.columns(3)
        s1.info("**① 計算する**\n\n発芽率・播種量・原価・在庫日数を数式で出す。\n\n→ 🔎 詳しく見る › 播種シミュレーター")
        s2.success("**② 可視化する**\n\n「いま畑で何が起きているか」をグラフと写真で共有する。\n\n→ 🔎 詳しく見る › 圃場モニター・AI土壌診断")
        s3.warning("**③ 自分の条件で判断する**\n\n自分の畑・自分の在庫・自分の資金で決める。\n\n→ 🔎 詳しく見る › 原料レジリエンス")
    with right:
        st.subheader("最近の畑")
        recent = st.session_state.log.sort_values("日付", ascending=False).head(4)
        for _, r in recent.iterrows():
            st.markdown(f"**{r['日付']:%m/%d}**　`{r['カテゴリ']}`　{r['内容']}")
        st.link_button("📘 Facebookで毎日の様子を見る", FACEBOOK_URL)

    st.subheader("ロードマップ")
    fig = px.timeline(current, x_start="開始", x_end="終了", y="工程", color="状態",
                      color_discrete_map={"完了": "#c9c2b4", "進行中": "#c98a2b", "予定": "#9bb884"},
                      category_orders={"状態": ["完了", "進行中", "予定"]})
    fig.update_yaxes(autorange="reversed", title=None)
    fig.add_vline(x=pd.Timestamp(today), line_dash="dot", line_color="#555")
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="")
    st.plotly_chart(fig, width="stretch")
    st.caption("状態（完了／進行中／予定）は今日の日付から自動で判定しています。点線が今日です。")

# ═════════════════════════════════════════════
# 2. 小麦の播種シミュレーター
# ═════════════════════════════════════════════
with T["🌱 小麦の播種シミュレーター"]:
    st.header("🌱 播種日 × 発芽率 × 播種量")
    st.write(
        "実体験では **10月下旬（10/20頃）** が発芽率の最適点で、11月以降にずれ込むと発芽率が下がり、"
        "同じ苗立ち本数を確保するために播種量を増やす必要がありました。その関係をモデル化しています。"
    )

    col_in, col_out = st.columns([1, 2])
    with col_in:
        sow = st.date_input("播種日", value=date(2026, 10, 20),
                            min_value=date(2026, 10, 1), max_value=date(2026, 12, 15))
        peak_rate = st.slider("最適日の発芽率（%）", 60, 98, 90)
        decay = st.slider("最適日から1日ずれるごとの低下（%pt）", 0.1, 1.5, 0.5, 0.1)
        target_plants = st.number_input("目標苗立ち本数（本/㎡）", 100, 400, 200, 10)
        tkw = st.number_input("千粒重（g）", 30.0, 50.0, 40.0, 0.5)

    optimum = date(sow.year, 10, 20)

    def germ_rate(d: date) -> float:
        diff = (d - optimum).days
        # 早すぎる側は緩やか、遅い側（11月以降）は急に落ちる非対称モデル
        slope = decay * (0.6 if diff < 0 else (1.0 if d.month == 10 else 1.8))
        return float(np.clip(peak_rate - slope * abs(diff), 20, 100))

    rate = germ_rate(sow)
    seeds_per_m2 = target_plants / (rate / 100)
    seed_g_m2 = seeds_per_m2 * tkw / 1000
    seed_total_kg = seed_g_m2 * FIELD_AREA_M2 / 1000
    base_g_m2 = target_plants / (peak_rate / 100) * tkw / 1000

    with col_out:
        m1, m2, m3 = st.columns(3)
        m1.metric("予測発芽率", f"{rate:.1f} %", f"{rate - peak_rate:+.1f} pt")
        m2.metric("必要播種量", f"{seed_g_m2:.1f} g/㎡",
                  f"{(seed_g_m2 / base_g_m2 - 1) * 100:+.0f} % vs 最適日")
        m3.metric(f"圃場全体（{FIELD_AREA_M2}㎡）", f"{seed_total_kg:.2f} kg")

        days = [date(sow.year, 10, 1) + timedelta(days=i) for i in range(76)]
        df = pd.DataFrame({"播種日": days, "発芽率(%)": [germ_rate(d) for d in days]})
        df["播種量(g/㎡)"] = target_plants / (df["発芽率(%)"] / 100) * tkw / 1000
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["播種日"], y=df["発芽率(%)"], name="発芽率(%)",
                                 line=dict(color="#6a9a4a", width=3)))
        fig.add_trace(go.Scatter(x=df["播種日"], y=df["播種量(g/㎡)"], name="播種量(g/㎡)",
                                 yaxis="y2", line=dict(color="#c98a2b", dash="dot")))
        fig.add_vline(x=pd.Timestamp(sow), line_color="#555", line_dash="dash")
        fig.add_vrect(x0=pd.Timestamp(date(sow.year, 11, 1)), x1=pd.Timestamp(df["播種日"].max()),
                      fillcolor="#f2c9c0", opacity=0.25, line_width=0,
                      annotation_text="11月以降：発芽率低下域")
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10),
                          yaxis=dict(title="発芽率(%)"),
                          yaxis2=dict(title="播種量(g/㎡)", overlaying="y", side="right"),
                          legend=dict(orientation="h", y=1.12))
        st.plotly_chart(fig, width="stretch")

    st.markdown('<p class="note">※ 低下幅はスライダーで調整できる仮定値です。実測の発芽率を記録し、'
                "次年度はベイズ更新でパラメータを推定する予定です。</p>", unsafe_allow_html=True)

# ═════════════════════════════════════════════
# 3. 圃場モニター
# ═════════════════════════════════════════════
with T["📡 圃場モニター"]:
    st.header("📡 圃場モニター")
    st.write("センサー（気温・地温・土壌水分）のデータを表示します。CSVをアップロードすると実データに切り替わります。")

    up = st.file_uploader("センサーCSV（列: timestamp, air_temp, soil_temp, soil_moisture）", type="csv")

    @st.cache_data
    def demo_sensor(days: int = 30) -> pd.DataFrame:
        rng = np.random.default_rng(42)
        t = pd.date_range(end=pd.Timestamp.today().normalize(), periods=days * 24, freq="h")
        hour = t.hour.to_numpy()
        trend = np.linspace(24, 17, len(t))
        air = trend + 5 * np.sin((hour - 9) / 24 * 2 * np.pi) + rng.normal(0, 0.8, len(t))
        soil = trend - 1 + 1.5 * np.sin((hour - 12) / 24 * 2 * np.pi) + rng.normal(0, 0.3, len(t))
        moist = np.clip(32 - np.cumsum(rng.normal(0.02, 0.05, len(t))) % 12, 15, 40)
        return pd.DataFrame({"timestamp": t, "air_temp": air, "soil_temp": soil, "soil_moisture": moist})

    sdf = None
    if up is not None:
        sdf = sg.read_csv_safely(up, page="field_monitor", kind="sensor_csv", parse_dates=["timestamp"])
        need = {"timestamp", "air_temp", "soil_temp", "soil_moisture"}
        if sdf is not None and not need.issubset(sdf.columns):
            sg.log_event("csv_schema_mismatch", "WARNING", page="field_monitor")
            st.error("列名が違います。timestamp, air_temp, soil_temp, soil_moisture の4列が必要です。")
            sdf = None
        if sdf is not None:
            st.success(f"{len(sdf)} 行の実データを読み込みました。")
    if sdf is None:
        sdf = demo_sensor()
        st.caption("※ 現在はデモデータを表示中です。")

    latest = sdf.iloc[-1]
    k1, k2, k3 = st.columns(3)
    k1.metric("気温", f"{latest.air_temp:.1f} ℃")
    k2.metric("地温", f"{latest.soil_temp:.1f} ℃",
              "播種の目安域" if 10 <= latest.soil_temp <= 20 else "目安域外")
    k3.metric("土壌水分", f"{latest.soil_moisture:.1f} %")

    var = st.radio("表示項目", ["air_temp", "soil_temp", "soil_moisture"], horizontal=True,
                   format_func={"air_temp": "気温", "soil_temp": "地温", "soil_moisture": "土壌水分"}.get)
    daily = sdf.set_index("timestamp")[var].resample("D").agg(["mean", "min", "max"]).reset_index()
    fig = go.Figure([
        go.Scatter(x=daily["timestamp"], y=daily["max"], line=dict(width=0), showlegend=False),
        go.Scatter(x=daily["timestamp"], y=daily["min"], fill="tonexty", line=dict(width=0),
                   fillcolor="rgba(106,154,74,.2)", name="日最小〜最大"),
        go.Scatter(x=daily["timestamp"], y=daily["mean"], line=dict(color="#6a9a4a", width=3), name="日平均"),
    ])
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch")

    # 積算温度（小麦の生育ステージの目安）
    daily_mean = sdf.set_index("timestamp")["air_temp"].resample("D").mean()
    gdd = np.clip(daily_mean - 0, 0, None).cumsum()
    st.metric("積算温度（基準0℃, 期間累計）", f"{gdd.iloc[-1]:.0f} ℃・日")

# ═════════════════════════════════════════════
# 4. 原料レジリエンス（計算 → 可視化 → 判断）
# ═════════════════════════════════════════════
with T["🍞 原料レジリエンス"]:
    st.header("🍞 原料レジリエンス")
    st.write(
        "外部ショック（価格高騰・供給不安のニュース）が来たとき、慌てて買いだめするのではなく、"
        "**自分の数値で判断する**ための計算です。サプライチェーン研究の標準的な概念で整理しています。"
    )

    st.subheader("① 計算する：パン1斤あたり原価の感応度")
    cc = st.columns(5)
    flour = cc[0].number_input("小麦粉 円/kg", 100, 1000, 300, 10)
    butter = cc[1].number_input("バター 円/kg", 500, 5000, 1800, 50)
    energy = cc[2].number_input("電気・ガス 円/斤", 10, 200, 45, 5)
    pack = cc[3].number_input("包装資材 円/斤", 5, 100, 15, 1)
    own_share = cc[4].slider("自家産小麦の比率 %", 0, 100, 30)

    shock = st.slider("外部原料の価格ショック（%）", 0, 100, 30, 5)
    own_cost = 180  # 自家産小麦の実質コスト（円/kg, 仮定）

    def loaf_cost(s: float) -> dict:
        f = 0.25 * ((1 - own_share / 100) * flour * (1 + s) + own_share / 100 * own_cost)
        return {"小麦粉": f, "バター": 0.02 * butter * (1 + s),
                "エネルギー": energy * (1 + s), "包装": pack * (1 + s * 0.5)}

    base, shocked = loaf_cost(0), loaf_cost(shock / 100)
    cdf = pd.DataFrame({"項目": list(base), "平常時": list(base.values()), "ショック時": list(shocked.values())})
    cdf_m = cdf.melt(id_vars="項目", var_name="状態", value_name="円")

    st.subheader("② 可視化する")
    g1, g2 = st.columns([3, 2])
    fig = px.bar(cdf_m, x="状態", y="円", color="項目", text_auto=".0f",
                 color_discrete_sequence=["#c98a2b", "#e6c36a", "#8aa6c1", "#b5b5b5"])
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10))
    g1.plotly_chart(fig, width="stretch")
    tb, ts = sum(base.values()), sum(shocked.values())
    g2.metric("1斤あたり原価（平常時）", f"{tb:.0f} 円")
    g2.metric("1斤あたり原価（ショック時）", f"{ts:.0f} 円", f"{(ts / tb - 1) * 100:+.1f} %", delta_color="inverse")
    g2.caption("自家産小麦の比率を上げると、ショック時の上昇幅がどう縮むかを確認できます。")

    st.subheader("③ 自分の条件で判断する：3つの指標")
    r1, r2, r3 = st.columns(3)
    with r1:
        st.markdown("**調達先の集中度（HHI）**")
        shares = [st.slider(f"仕入先{n}のシェア %", 0, 100, v, key=f"s{n}")
                  for n, v in zip("ABC", [60, 30, 10])]
        tot = sum(shares) or 1
        hhi = sum((s / tot * 100) ** 2 for s in shares)
        st.metric("HHI", f"{hhi:.0f}", "高集中" if hhi > 2500 else ("中程度" if hhi > 1500 else "分散"),
                  delta_color="off")
    with r2:
        st.markdown("**在庫バッファ（在庫日数）**")
        stock = st.number_input("小麦粉在庫 kg", 0, 2000, 150)
        use = st.number_input("1日の使用量 kg", 1, 200, 10)
        lead = st.number_input("調達リードタイム 日", 1, 60, 7)
        days_cover = stock / use
        st.metric("在庫日数", f"{days_cover:.0f} 日",
                  "十分" if days_cover >= lead * 2 else "要補充検討", delta_color="off")
    with r3:
        st.markdown("**財務レジリエンス（手元資金月数）**")
        cash = st.number_input("手元資金 万円", 0, 5000, 120)
        burn = st.number_input("月間固定費 万円", 1, 500, 20)
        months = cash / burn
        st.metric("運転可能月数", f"{months:.1f} か月",
                  "安全圏" if months >= 6 else "注意", delta_color="off")

    st.divider()
    st.subheader("ブルウィップ効果シミュレーター：過剰反応が在庫の波をつくる")
    st.write(
        "多くの店が「欠品が怖い」と少しずつ多めに発注すると、上流ほど注文の振れ幅が増幅されます。"
        "過剰反応係数 β を下げる（＝事前に数値で状況を把握している）と波がどう収まるかを比べてください。"
    )
    bc = st.columns(3)
    beta = bc[0].slider("過剰反応係数 β", 0.0, 1.0, 0.6, 0.05)
    stages = bc[1].slider("サプライチェーン段数", 2, 5, 4)
    news_week = bc[2].slider("「供給不安」ニュースの週", 5, 30, 10)

    def bullwhip(beta: float, stages: int, T: int = 52, seed: int = 0) -> pd.DataFrame:
        rng = np.random.default_rng(seed)
        demand = 100 + rng.normal(0, 5, T)
        demand[news_week:news_week + 3] += 15  # ニュースによる一時的な需要増
        rows, orders = [], demand
        names = ["消費者", "パン屋", "製粉", "商社", "原料輸入"][:stages + 1]
        rows.append(pd.DataFrame({"週": range(T), "段階": names[0], "発注量": demand}))
        for k in range(1, stages + 1):
            prev = np.r_[orders[0], orders[:-1]]
            new = orders + beta * 2.0 * (orders - prev) + beta * 3 * np.maximum(orders - 100, 0)
            new = np.clip(new, 0, None)
            rows.append(pd.DataFrame({"週": range(T), "段階": names[k], "発注量": new}))
            orders = new
        return pd.concat(rows)

    bw = bullwhip(beta, stages)
    fig = px.line(bw, x="週", y="発注量", color="段階",
                  color_discrete_sequence=px.colors.sequential.Oranges_r)
    fig.add_vline(x=news_week, line_dash="dash", annotation_text="ニュース")
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch")
    amp = bw.groupby("段階", sort=False)["発注量"].std()
    st.caption("振れ幅の増幅率（最上流の標準偏差 ÷ 消費者需要の標準偏差）："
               f"**{amp.iloc[-1] / amp.iloc[0]:.1f} 倍**")
    st.markdown('<p class="note">参考：Lee, Padmanabhan & Whang (1997) ブルウィップ効果／'
                "Kahneman & Tversky (1979) プロスペクト理論／Bikhchandani et al. (1992) 情報カスケード。"
                "本シミュレーターは説明用の簡易モデルです。</p>", unsafe_allow_html=True)

# ═════════════════════════════════════════════
# 5. 探究学習プログラム
# ═════════════════════════════════════════════
with T["🎓 探究学習（構想）"]:
    st.header("🎓 畑とパンの探究学習フィールド（構想）")
    st.write(
        "畑はまだ整備を始めたばかりです。まずは自分で小麦を育て、パンを焼き、"
        "記録とデータを積み重ねるところから始めます。"
        "その経験をもとに、**3年後（2029年ごろ）を目安に**、「探究学習」の外部フィールドとして"
        "畑を開くことを目指しています。"
    )

    st.subheader("ステップ")
    phases = pd.DataFrame([
        ("1年目", "2026〜2027", "畑とパンの土台づくり", "小麦からパンまで一通り試し、データと写真を記録する"),
        ("2年目", "2027〜2028", "教材づくり・小さく試す", "記録を教材にまとめる。知人や少人数での見学・体験を試しに行う"),
        ("3年目〜", "2029ごろ〜", "外部フィールドとして開く", "学校・支援機関と相談しながら、受け入れの形を整える"),
    ], columns=["段階", "時期", "目標", "内容"])
    st.dataframe(phases, width="stretch", hide_index=True)

    with st.expander("将来、こんな場とつながれたらと考えています"):
        st.markdown(
            "- **総合型選抜・推薦入試を目指す人**：自分で立てた問いを畑で確かめ、探究の過程を記録する場\n"
            "- **特別支援学校の職場体験（現場実習）**：手順が見える作業を通じた体験の場"
            "（ハウスの周囲に車椅子でも通れる通路を整備中）\n"
            "- **通信制高校・サポート校**：「総合的な探究の時間」の外部フィールド\n\n"
            "いずれも現時点では構想です。受け入れの体制が整ってから、改めてお知らせします。"
        )
    st.caption("受け入れの準備がどこまで進んでいるかは、となりの「🤝 受け入れ体制」タブで公開しています。")
    school_banner()

    with st.expander("探究テーマの案（いま自分で試していること）"):
        prog = pd.DataFrame([
            ("種まき", "10月", "播種日と発芽率の関係を記録", "理科・データ分析"),
            ("観測", "11〜5月", "気温・地温・水分を計測し可視化", "情報・Python"),
            ("土づくり", "通年", "米ぬか発酵肥料、写真からの土壌診断", "化学・生物"),
            ("収穫・製粉", "6〜7月", "収量を予測し、実測と比較", "数学・統計"),
            ("パン", "7〜9月", "原価計算と、価格が上がったときの判断", "家庭・経済"),
        ], columns=["テーマ", "時期", "内容", "つながる教科"])
        st.dataframe(prog, width="stretch", hide_index=True)

    st.info("この構想に関心をお持ちの方、ご意見をいただける方は、Facebookから気軽に声をかけてください。"
            "畑の様子も随時発信しています。")
    st.link_button("📘 Facebookで活動を見る", FACEBOOK_URL)

# ═════════════════════════════════════════════
# 5-2. 受け入れ体制（記録する → 見せる → 相手が判断できる）
#   ※ 状況が変わったら、下の ACCEPT_* を書きかえるだけで更新できます
# ═════════════════════════════════════════════
ACCEPT_UPDATED = "2026-10-07"
ACCEPT_STATUS = [  # (項目, 現状, 今後の予定)
    ("車椅子が通れる通路",           "整備中",       "2026年10月4日に着工。ハウスの周囲を一周できる幅で整備"),
    ("試行プログラム",               "実施 0 回",    "2027年度に 1〜2 回、少人数で試す予定"),
    ("保険",                         "未加入",       "試行までに、受け入れに合った保険を選んで加入"),
    ("緊急時の対応",                 "準備中",       "連絡体制・最寄りの医療機関・応急手当の手順を文書にまとめる"),
    ("トイレ・休憩場所",             "確認中",       "使える場所と、車椅子での利用可否を確認して記載"),
    ("見学の受け入れ",               "準備中",       "体制が整い次第、このページでお知らせ"),
]
ACCEPT_QUALS = [  # (資格・経験, 区分)
    ("高等学校教諭一種免許状（理科）", "保有"),
    ("職業訓練指導員（パン・菓子製造）", "保有"),
    ("危険物取扱者（乙種第4類）", "保有"),
    ("産業用ロボット特別教育 修了（インストラクターコースは2026年12月修了予定）", "保有"),
    ("高等学校教諭免許状（情報）", "取得予定（2027年9月）"),
    ("特別支援学校 高等部での作業学習（農業・食品加工など）の実習助手", "経験 5年4か月"),
]

with T["🤝 受け入れ体制"]:
    st.header("🤝 見学・実習の受け入れ体制（準備中）")
    st.write(
        "学校や支援機関の方が「ここなら任せられるか」をご自身で判断できるよう、"
        "**いま整っていること・まだ整っていないこと**を、そのまま公開しています。"
        "実績はまだありません。整った項目から順に更新していきます。"
    )
    st.caption(f"最終更新：{ACCEPT_UPDATED}　｜　このページの流れ：記録する → 見せる → 相手が判断できる")
    school_banner()

    n_trial = 0
    c1, c2, c3 = st.columns(3)
    c1.metric("車椅子が通れる通路", "整備中")
    c1.caption("2026年10月着工")
    c2.metric("試行プログラムの実施", f"{n_trial} 回")
    c2.caption("2027年度に 1〜2 回予定")
    held = sum(1 for _, k in ACCEPT_QUALS if k.startswith("保有"))
    c3.metric("指導者の資格", f"{held} 種")
    c3.caption("理科免許・職業訓練指導員ほか")

    st.subheader("受け入れ準備の状況")
    st.dataframe(pd.DataFrame(ACCEPT_STATUS, columns=["項目", "現状", "今後の予定"]),
                 width="stretch", hide_index=True)
    done = sum(1 for _, s_, _ in ACCEPT_STATUS if s_ in ("整備済み", "加入済み", "完了", "受け入れ中"))
    st.progress(done / len(ACCEPT_STATUS), text=f"準備が整った項目：{done} / {len(ACCEPT_STATUS)}")

    st.subheader("指導者の資格・経験")
    st.dataframe(pd.DataFrame(ACCEPT_QUALS, columns=["資格・経験", "区分"]), width="stretch", hide_index=True)

    st.subheader("1回分の流れ（案：90分）")
    st.dataframe(pd.DataFrame({
        "時間": ["0–15分", "15–60分", "60–90分"],
        "内容": ["安全説明・圃場観察", "小麦の生育測定とデータ入力", "パン生地の観察・振り返り"],
        "生徒が持ち帰るもの": ["観察記録", "自分で取ったデータ", "探究の問い1つ"],
    }), width="stretch", hide_index=True)
    st.caption("※ 試行前の案です。参加する方の目的や体調に合わせて、時間と内容は調整します。")

    st.info("受け入れ体制は準備中です。「こういう準備があると安心」というご意見があれば、"
            "Facebookからお寄せください。今後の整備の参考にさせていただきます。")
    st.link_button("📘 Facebookで声をかける", FACEBOOK_URL)

# ═════════════════════════════════════════════
# 6. 活動ログ
# ═════════════════════════════════════════════
with T["📝 活動ログ"]:
    st.header("📝 活動ログ")

    with st.expander("✏️ 記録を追加する・ずっと残す方法"):
        st.caption(
            "ここで追加した記録は、ページを閉じると消えます。ずっと残すには、追加したあと"
            "下の「CSVでダウンロード」を押し、GitHub の `data/activity_log.csv` をそのファイルで置きかえてください。"
            "数分でこのページに反映されます。"
        )
        with st.form("add_log", clear_on_submit=True):
            d = st.date_input("日付", value=date.today())
            cat = st.selectbox("カテゴリ", ["圃場", "土づくり", "栽培", "獣害対策", "パン", "探究学習", "発信"])
            txt = st.text_area("内容")
            if st.form_submit_button("追加") and txt.strip():
                st.session_state.log = pd.concat(
                    [st.session_state.log, pd.DataFrame([dict(日付=d, カテゴリ=cat, 内容=txt)])],
                    ignore_index=True)

    log = st.session_state.log.sort_values("日付", ascending=False)
    cat_filter = st.multiselect("カテゴリで絞り込み", sorted(log["カテゴリ"].unique()))
    if cat_filter:
        log = log[log["カテゴリ"].isin(cat_filter)]
    for _, r in log.iterrows():
        st.markdown(f"**{r['日付']:%Y/%m/%d}**　`{r['カテゴリ']}`　{r['内容']}")
    # 絞り込みに関係なく、全件を保存する（一部だけ保存して記録が欠けるのを防ぐ）
    full = st.session_state.log.sort_values("日付", ascending=False)
    st.download_button("CSVでダウンロード（全件）", sg.safe_csv(full),
                       "activity_log.csv", "text/csv")

# ═════════════════════════════════════════════
# 7. 圃場フォト（assets/YYYYMMDD/*.jpg を自動で読み込む）
# ═════════════════════════════════════════════
with T["📷 圃場フォト"]:
    st.header("📷 圃場フォト")
    st.write("整備の進み具合を日付ごとに記録しています。`assets/YYYYMMDD/` に写真を置くと自動で追加されます。")
    folders = sorted([p for p in ASSETS.glob("*") if p.is_dir()], reverse=True) if ASSETS.exists() else []
    if not folders:
        st.caption("写真はまだありません。")
    for folder in folders:
        d = folder.name
        label = f"{d[:4]}/{d[4:6]}/{d[6:]}" if len(d) == 8 and d.isdigit() else d
        st.subheader(f"{label}　{PHOTO_LOG.get(d, '')}")
        photos = sorted(folder.glob("*.jp*g")) + sorted(folder.glob("*.png"))
        cols = st.columns(4)
        for i, p in enumerate(photos):
            # ファイル名（例：米ぬか発酵肥料づくり開始-1.jpg）をそのままキャプションに使う
            cap = re.sub(r"[_ ]?\d{8}$", "", p.stem.rsplit("-", 1)[0]).replace("_", " ")
            cols[i % 4].image(str(p), width="stretch",
                              caption=None if cap.startswith(("img", "IMG", "sns")) else cap)

# ═════════════════════════════════════════════
# 8. AI土壌診断（写真 → 生育ムラ → 施肥設計／指標植物）
# ═════════════════════════════════════════════
with T["🔬 AI土壌診断"]:
    st.header("🔬 AI土壌診断：写真から畑のムラを読む")
    st.write(
        "スマホ写真から植物の緑の濃さと分布を計算し、**どこに・どれだけ肥料を撒くか**、"
        "**どこの土を本格的に分析すべきか**を提案します。生えている雑草（指標植物）から土の傾向も推定します。"
    )
    st.markdown(
        "| Step | 内容 | このタブ |\n|---|---|---|\n"
        "| 1 | 画像撮影（スマホ／ドローン） | 写真を選ぶ・アップロード |\n"
        "| 2 | AI解析（生育ムラ・雑草分布） | 植生指数ExGで自動計算 |\n"
        "| 3 | 施肥設計（処方箋） | 区画ごとの肥料量を算出 |\n"
        "| 4 | ピンポイント施肥 | 区画表を見ながら手撒き |"
    )

    # ── 写真の選択 ──
    all_photos = sorted(ASSETS.glob("*/*.jp*g")) if ASSETS.exists() else []
    src_mode = st.radio("写真", ["圃場フォトから選ぶ", "アップロード"], horizontal=True)
    img_src = None
    if src_mode == "アップロード":
        img_src = st.file_uploader("畑の写真（できるだけ真上から）", type=["jpg", "jpeg", "png"], key="soil_up")
        if img_src is not None and not sg.check_upload(img_src, sg.MAX_IMAGE_BYTES, "soil", "image"):
            img_src = None
    elif all_photos:
        img_src = st.selectbox("写真を選択", all_photos,
                               format_func=lambda p: f"{p.parent.name} / {p.name}")

    if img_src is None:
        st.info("写真を選ぶかアップロードしてください。")
    else:
        try:
            rgb = sv.load_image(img_src)
        except Exception as e:  # noqa: BLE001  解凍爆弾・壊れた画像・偽装ファイル
            sg.log_event("image_rejected", "WARNING", page="soil", error=type(e).__name__)
            st.error("この画像は読み込めませんでした（形式・大きさを確認してください）。")
            st.stop()
        with st.expander("✂️ 解析範囲を畑の部分だけに絞る（壁・空・通路を除く）"):
            cr1, cr2 = st.columns(2)
            top, bottom = cr1.slider("上下の範囲 %", 0, 100, (0, 100), key="crop_v")
            left, right = cr2.slider("左右の範囲 %", 0, 100, (0, 100), key="crop_h")
            H0, W0 = rgb.shape[:2]
            if bottom - top >= 10 and right - left >= 10:
                rgb = rgb[H0 * top // 100: H0 * bottom // 100, W0 * left // 100: W0 * right // 100]
        idx = sv.vegetation_indices(rgb)

        st.subheader("① 計算する：植物と土を分ける")
        p1, p2, p3 = st.columns(3)
        th_mode = p1.radio("しきい値", ["固定（推奨）", "大津の自動二値化"])
        th = p1.slider("ExG しきい値", 0.0, 0.3, 0.05, 0.01) if th_mode.startswith("固定") \
            else sv.otsu_threshold(idx["ExG"])
        rows_n = p2.slider("グリッド 行", 2, 8, 4)
        cols_n = p2.slider("グリッド 列", 2, 8, 4)
        mask = (idx["ExG"] > th) & (rgb[..., 1] > rgb[..., 0])  # 黄色い物体などを除外
        p3.metric("植被率（写真全体）", f"{mask.mean() * 100:.0f} %")
        p3.metric("しきい値", f"{th:.3f}")
        p3.caption("ExG = 2g − r − b（r,g,b は明るさで正規化したRGB）")

        st.subheader("② 可視化する：生育ムラマップ")
        grid = sv.grid_stats(idx["ExG"], mask, rows_n, cols_n)
        v1, v2 = st.columns(2)
        overlay = rgb.copy()
        overlay[mask] = overlay[mask] * 0.4 + np.array([40, 220, 60]) * 0.6
        v1.image(overlay.astype(np.uint8), caption="緑色＝植物と判定した部分", width="stretch")
        heat = grid.pivot(index="行", columns="列", values="緑の濃さ").to_numpy()
        labels = grid.pivot(index="行", columns="列", values="区画").to_numpy()
        fig = px.imshow(heat, color_continuous_scale="YlGn", aspect="auto",
                        labels=dict(color="緑の濃さ(ExG)"))
        fig.update_traces(text=labels, texttemplate="%{text}<br>%{z:.2f}")
        fig.update_xaxes(showticklabels=False)
        fig.update_yaxes(showticklabels=False)
        fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10))
        v2.plotly_chart(fig, width="stretch")
        v2.caption("色が薄い区画ほど緑が薄い＝窒素不足の可能性。空欄は植物がほぼ無い区画。")

        st.subheader("③ 自分の条件で判断する：可変施肥の処方箋")
        f1, f2, f3, f4 = st.columns(4)
        area = f1.number_input("写真に写る範囲の面積 ㎡", 1.0, 1000.0, float(FIELD_AREA_M2), 1.0)
        base_n = f2.number_input("標準の追肥 窒素 kg/10a", 0.0, 10.0, 2.0, 0.5)
        fert = f3.selectbox("肥料", {"硫安（N 21%）": 0.21, "尿素（N 46%）": 0.46,
                                   "化成肥料 8-8-8（N 8%）": 0.08, "油かす（N 約5%）": 0.05})
        n_ratio = {"硫安（N 21%）": 0.21, "尿素（N 46%）": 0.46,
                   "化成肥料 8-8-8（N 8%）": 0.08, "油かす（N 約5%）": 0.05}[fert]
        gain = f4.slider("ムラへの反応の強さ", 0.0, 1.0, 0.5, 0.1)
        rx = sv.prescription(grid, base_n, n_ratio, area, gain)

        t1, t2 = st.columns([3, 2])
        t1.dataframe(
            rx[["区画", "植被率", "緑の濃さ", "倍率", "肥料量(g)", "判定"]].style.format(
                {"植被率": "{:.0%}", "緑の濃さ": "{:.3f}", "倍率": "{:.2f}", "肥料量(g)": "{:.0f}"}),
            hide_index=True, width="stretch", height=320)
        uniform = base_n * area / n_ratio
        t2.metric("可変施肥の肥料合計", f"{rx['肥料量(g)'].sum():.0f} g",
                  f"{(rx['肥料量(g)'].sum() / uniform - 1) * 100:+.0f} % vs 均一散布", delta_color="inverse")
        pts = sv.sampling_points(rx)
        t2.success("**本格的な土壌分析に回す区画**：" + "・".join(pts))
        t2.caption("裸地・最も緑が薄い区画・比較対照として最も濃い区画を選んでいます。"
                   "画像で当たりをつけ、その場所だけ土壌分析へ（ハイブリッド方式）。")
        t2.download_button("処方箋をCSVで保存", sg.safe_csv(rx),
                           "prescription.csv", "text/csv")

        st.divider()
        st.subheader("指標植物から土の傾向を推定する（ベイズ更新）")
        w1, w2 = st.columns([2, 3])
        with w1:
            if sv.ai_available():
                if st.button("🤖 生成AIに雑草の候補を提案させる") and sg.ai_quota_ok("soil"):
                    with st.spinner("解析中…"):
                        try:
                            res = sv.ai_suggest_weeds(rgb)
                            st.session_state.ai_weeds = res
                            st.session_state.weeds = [c["name"] for c in res.get("candidates", [])
                                                      if c.get("name") in sv.INDICATORS
                                                      and c.get("confidence", 0) >= 0.5]
                        except Exception as e:  # noqa: BLE001
                            sg.log_event("ai_call_failed", "WARNING", page="soil", error=type(e).__name__)
                            st.error("AI解析に失敗しました。時間をおいて試すか、手動で選んでください。")
                if "ai_weeds" in st.session_state:
                    for c in st.session_state.ai_weeds.get("candidates", []):
                        st.text(f"・{c.get('name')}（確信度 {c.get('confidence', 0):.2f}）{c.get('reason', '')}")
            else:
                st.caption("※ `ANTHROPIC_API_KEY` を設定すると、生成AIが写真から雑草の候補を提案します"
                           "（最終判断は人が行う半自動方式）。未設定のため手動で選んでください。")
            observed = st.multiselect("多く生えている雑草", list(sv.INDICATORS), key="weeds")
            prior = st.slider("事前確率（何も見ていない時点の確からしさ）", 0.05, 0.9, 0.3, 0.05)
        post = sv.bayes_soil(observed, prior)
        fig = px.bar(post, x="事後確率", y="傾向", orientation="h", range_x=[0, 1],
                     text=post["事後確率"].map("{:.0%}".format),
                     color_discrete_sequence=["#6a9a4a"])
        fig.add_vline(x=prior, line_dash="dot", annotation_text="事前確率")
        fig.update_layout(height=260, margin=dict(l=10, r=10, t=30, b=10))
        w2.plotly_chart(fig, width="stretch")
        w2.caption("事後オッズ ＝ 事前オッズ × Π（雑草ごとの尤度比）。尤度比は資料に基づく仮定値で、"
                   "実際の土壌分析の結果が出たら見直します。")

        with st.expander("⚠️ この診断の限界"):
            st.markdown(
                "- 本物のNDVIには近赤外（NIR）が必要です。ここではRGBで代わりになる指数（ExG）を使っています。\n"
                "- pHや成分量（mg単位）は出せません。**傾向をつかみ、土壌分析をする場所を絞る**ための道具です。\n"
                "- 壁・空・生け垣など畑以外が写っている場合は、上の「解析範囲」で除いてください。\n"
                "- 斜めに撮ると奥の区画ほど面積が小さく写ります。施肥設計には真上からの写真が向いています。\n"
                "- 施肥設計が最も効くのは、小麦が育ち始めた後の**追肥**の時期（2〜3月頃）です。今の時期の写真は雑草の分布を見る練習になります。\n"
                "- 雑草の種類は地域差があり、AIの判定は間違えることがあります。必ず人の目で確認してください。"
            )

# ═════════════════════════════════════════════
# 9. 3Dプリンター（自助具 → 畑とパンの道具）
# ═════════════════════════════════════════════
with T["🖨️ 3Dプリンター"]:
    st.header("🖨️ 3Dプリンターで、道具を自分でつくる")
    st.write(
        "3Dプリンターは、まったくの初心者からのスタートです。"
        "いきなり設計はせず、**本で基本を学び、公開されているデータを印刷する**ところから始めます。"
        "慣れてきたら、寸法を変えて自分の手や畑に合わせ、最後は畑とパンの道具を自分で設計します。"
    )

    st.subheader("手引きにするもの")
    r1, r2 = st.columns(2)
    with r1:
        st.markdown(
            "##### 📗 『はじめてでも簡単！3Dプリンタで自助具を作ろう』\n"
            "林 園子 著（三輪書店）。作業療法士の視点で、自助具（食事・書字・つまむ動作などを助ける道具）を"
            "3Dプリンターで作る手順が、はじめての人向けにまとめられています。"
        )
    with r2:
        st.markdown(
            "##### 🌐 COCRE HUB（コクリハブ）\n"
            "自助具など、誰もが暮らしやすくなる道具の3Dデータを共有し、**ともにつくる**ためのプラットフォーム。"
            "公開データをダウンロードして、そのまま、または寸法を調整して印刷できます。"
        )
        st.link_button("🌐 COCRE HUB を見る", COCRE_HUB_URL)

    st.subheader("ステップ：ハードルを低く、少しずつ")
    steps3d = pd.DataFrame([
        ("① 学ぶ", "本で、プリンターの仕組み・材料・安全な使い方を知る", "書籍", "いまここ"),
        ("② 印刷する", "COCRE HUB の公開データを、そのまま印刷してみる", "COCRE HUB", "次"),
        ("③ 合わせる", "持ち手の太さ・長さなど、寸法だけ変えて自分や家族に合わせる", "書籍＋COCRE HUB", "予定"),
        ("④ つくる", "畑やパンで「あったら便利」な道具を自分で設計する", "自分の現場", "予定"),
    ], columns=["段階", "やること", "手がかり", "状況"])
    st.dataframe(steps3d, width="stretch", hide_index=True)

    st.subheader("つくってみたいもの（アイデア）")
    ideas = pd.DataFrame([
        ("自助具", "スコップ・ハサミ・スプーンの太い持ち手", "握る力が弱くても、畑やパンづくりの作業がしやすくなる"),
        ("自助具", "ペットボトル・袋のオープナー", "作業の合間の「ちょっとした不便」を減らす"),
        ("畑", "苗ラベル・支柱どうしを留めるクリップ", "壊れたら同じものをすぐ印刷し直せる"),
        ("畑", "土壌センサーのケース・取り付け台", "圃場モニターのセンサーを雨や泥から守る"),
        ("畑", "モグラよけ風車の軸受け部品", "ペットボトル風車の回転をなめらかにする"),
        ("パン", "生地の厚みをそろえるガイド・カードの台", "形と焼きムラをそろえる"),
    ], columns=["分野", "つくるもの", "ねらい"])
    st.dataframe(ideas, width="stretch", hide_index=True)
    st.caption("車椅子でも通れる通路づくりと同じく、「誰でも作業に参加しやすい畑」にするための道具として考えています。")

    st.subheader("① 計算する：1個つくるといくら？")
    q = st.columns(5)
    grams = q[0].number_input("使う樹脂の量 g", 1, 1000, 30)
    fil_price = q[1].number_input("フィラメント 円/kg", 1000, 10000, 2500, 100)
    hours = q[2].number_input("印刷時間 時間", 0.1, 48.0, 2.0, 0.5)
    watt = q[3].number_input("消費電力 W", 50, 500, 120, 10)
    kwh_price = q[4].number_input("電気代 円/kWh", 10, 80, 31)
    mat_cost = grams / 1000 * fil_price
    elec_cost = watt / 1000 * hours * kwh_price
    m1, m2, m3 = st.columns(3)
    m1.metric("材料費", f"{mat_cost:.0f} 円")
    m2.metric("電気代", f"{elec_cost:.0f} 円")
    m3.metric("1個あたり合計", f"{mat_cost + elec_cost:.0f} 円")
    st.caption("※ 失敗印刷・プリンター本体の購入費・手間は含みません。目安を知るための簡易計算です。")

    with st.expander("⚠️ 注意しておくこと"):
        st.markdown(
            "- **食品に直接ふれる道具は慎重に**：積層のすき間に汚れや菌が残りやすく、洗浄しにくいことがあります。"
            "パンの生地に直接ふれるものは、用途と材料を確かめてから使います。\n"
            "- **自助具は使う人に合わせる**：体の状態に合わせた調整が大切です。"
            "必要に応じて作業療法士などの専門職に相談します。\n"
            "- 公開データを使うときは、各データの**利用条件（ライセンス）**を確認します。\n"
            "- 印刷中は高温になります。換気をし、子どもの手が届かないようにします。"
        )

    st.divider()
    mg.media_section(ASSETS / "3d_printer", key="p3d", title="📂 3Dプリンターの記録・資料")

# ═════════════════════════════════════════════
# 10. AIロボット（記録 → シミュレーション → 実機）
# ═════════════════════════════════════════════
with T["🤖 AIロボット"]:
    st.header("🤖 AIロボットで、畑を見回る")
    st.write(
        "最終的には、小さなロボットが畑を巡回して写真やセンサー値を集め、"
        "「AI土壌診断」につなげることを目指しています。"
        "ただし、いまは**人の手とスマホで記録している段階**です。"
        "実機を動かす前に、まずはパソコンの中（シミュレーション）で試すところから進めます。"
    )

    st.subheader("ステップ")
    steps_rb = pd.DataFrame([
        ("① 人が記録する", "スマホで同じ位置から定点撮影し、写真とメモを残す", "スマホ・活動ログ", "いまここ"),
        ("② シミュレーションで試す", "ROS 2 とシミュレーターで、約96㎡の畑を巡回する経路を作る", "ROS 2・Gazebo", "次"),
        ("③ 小型ロボットで巡回", "カメラ付きの小型ローバーで、決めた経路を走って撮影する", "小型ローバー", "予定"),
        ("④ AIとつなぐ", "集めた写真を「AI土壌診断」に流し、生育ムラや雑草の分布を自動で集計する", "AI土壌診断タブ", "予定"),
    ], columns=["段階", "やること", "使うもの", "状況"])
    st.dataframe(steps_rb, width="stretch", hide_index=True)

    st.subheader("① 計算する → ② 可視化する：巡回ルートを設計する")
    st.write("畑を往復しながら撮影する「芝刈り型」のルートで、走る距離・時間・撮影枚数を見積もります。")
    rc_in, rc_out = st.columns([1, 2])
    with rc_in:
        fw = st.number_input("畑の幅 m", 2.0, 50.0, 8.0, 0.5)
        fd = st.number_input("畑の奥行き m", 2.0, 50.0, 12.0, 0.5)
        swath = st.slider("カメラが1回で写す幅 m", 0.5, 3.0, 1.5, 0.1)
        overlap = st.slider("写真の重なり %", 0, 60, 30, 5)
        speed = st.slider("走る速さ m/秒", 0.05, 1.0, 0.2, 0.05)

    step = swath * (1 - overlap / 100)
    n_lanes = int(np.ceil(fw / step))
    xs, ys = [], []
    for k in range(n_lanes):
        x = min(step / 2 + k * step, fw)
        y0, y1 = (0, fd) if k % 2 == 0 else (fd, 0)
        xs += [x, x]
        ys += [y0, y1]
    path_len = float(np.sum(np.hypot(np.diff(xs), np.diff(ys))))
    n_photos = int(np.ceil(path_len / step)) + 1

    with rc_out:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("往復の本数", f"{n_lanes} 本")
        k2.metric("走る距離", f"{path_len:.0f} m")
        k3.metric("所要時間", f"{path_len / speed / 60:.0f} 分")
        k4.metric("撮影枚数", f"{n_photos} 枚")
        fig = go.Figure()
        fig.add_shape(type="rect", x0=0, y0=0, x1=fw, y1=fd,
                      fillcolor="rgba(155,184,132,.25)", line=dict(color="#9a9a9a", dash="dot", width=1))
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name="巡回ルート",
                                 line=dict(color="#8a4b12", width=2), marker=dict(size=4, color="#8a4b12")))
        fig.add_trace(go.Scatter(x=[xs[0]], y=[ys[0]], mode="markers+text", text=["スタート"],
                                 textposition="bottom center", marker=dict(size=12, color="#3b2f1e"),
                                 showlegend=False))
        fig.update_xaxes(title="幅 m", range=[-0.5, fw + 0.5])
        fig.update_yaxes(title="奥行き m", range=[-1, fd + 0.5], scaleanchor="x", scaleratio=1)
        fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
        st.plotly_chart(fig, width="stretch")
    st.caption(f"畑の面積 {fw * fd:.0f} ㎡ のモデル。曲がる時間や充電は含まない簡易計算です。"
               "シミュレーションでは、この経路をROS 2のナビゲーションに渡して走らせることを想定しています。")

    st.subheader("③ 自分の条件で判断する：ロボットに任せる？ 人がやる？")
    cmp_ = pd.DataFrame([
        ("定点撮影（週1回）", "人", "数分で終わる。まずは人で十分"),
        ("畑全体の撮影（生育ムラ）", "ロボット候補", "毎回同じ経路・同じ高さで撮れるとAIの比較精度が上がる"),
        ("雑草の判定", "AI＋人", "AIが候補を出し、最終判断は人が行う"),
        ("草刈り・収穫", "人", "刃物や重い作業は、当面ロボットに任せない"),
    ], columns=["作業", "担い手", "理由"])
    st.dataframe(cmp_, width="stretch", hide_index=True)

    with st.expander("⚠️ 安全について"):
        st.markdown(
            "- ロボットを動かすのは、**人が近くで見守れるとき**だけにします。非常停止の手段を必ず用意します。\n"
            "- 実機の前に、必ずシミュレーションで経路と動きを確かめます。\n"
            "- 撮影した写真に人や近所の家が写り込まないよう、撮影範囲に気をつけます。\n"
            "- 通信でつながる機器なので、初期パスワードの変更など**基本的なセキュリティ対策**を行います。"
        )

    st.divider()
    mg.media_section(ASSETS / "robot", key="robot", title="📂 AIロボットの記録・資料")

# ═════════════════════════════════════════════
# 11. 情報Ⅰ（データの活用・プログラミング）からアプローチする
# ═════════════════════════════════════════════
with T["💻 情報Ⅰ"]:
    st.header("💻 「情報Ⅰ」の視点（データの活用・プログラミング）からアプローチする")
    st.write(
        "共通テストの「情報Ⅰ」では、数学・理科・社会の場面設定を題材にした問題がよく出ます。"
        "ここでは題材を**この畑のデータ**に置きかえて、Pythonのプログラムを読む・動かす練習をします。"
        "畑で起きていることが、そのままデータ分析とプログラミングの教材になります。"
    )
    st.caption("※ 教材の試作段階です。データは説明用のサンプルで、実測データがたまり次第、差し替えていきます。"
               "問題はすべてオリジナルの模擬問題です。")

    with st.container(border=True):
        cb1, cb2 = st.columns([3, 2])
        cb1.markdown(
            "**▶ Google Colab で動かしてみよう**\n\n"
            "下の例題1〜3のプログラムを、ブラウザだけで実行できるノートブックにまとめました。"
            "インストール不要・Googleアカウントがあれば無料で使えます。"
            "数値を書きかえたり、まちがいを直したりしながら、動作を確かめられます。"
        )
        cb2.link_button("▶ Google Colab で例題を開く", mg.colab_url(JOHO1_NOTEBOOK), width="stretch")
        nb_path = Path(__file__).parent / JOHO1_NOTEBOOK
        if nb_path.exists():
            cb2.download_button("ノートブック（.ipynb）を保存", nb_path.read_bytes(),
                                file_name=nb_path.name, width="stretch")
        cb2.caption("開いたら、上から順にセルの ▶ を押します。自分のドライブに保存すると書きかえを残せます。")

    st.subheader("教科のつながり")
    link = pd.DataFrame([
        ("生物基礎", "植生調査（コドラート法）で雑草を数える", "文字列・辞書を使った頻度の集計", "例題1"),
        ("数学Ⅰ・A（データの分析）", "区画ごとの発芽本数", "平均・分散・箱ひげ図、データの変換", "例題2"),
        ("理科基礎（地温・季節）", "地温と、発芽までの日数", "散布図・相関係数を求めるループ", "例題3"),
        ("物理基礎", "ロボットの巡回（距離・速さ・時間）", "ループと条件分岐でシミュレーション", "🤖 AIロボット"),
        ("公共・政治経済", "原料価格の高騰と在庫・買いだめ", "モデル化とシミュレーション", "🍞 原料レジリエンス"),
    ], columns=["教科・科目", "畑での題材", "情報Ⅰの視点", "このページ"])
    st.dataframe(link, width="stretch", hide_index=True)

    def quiz(key: str, question: str, options: list[str], answer: int, explain: str) -> None:
        st.markdown(f"**❓ {question}**")
        pick = st.radio("選択肢", options, index=None, key=key, label_visibility="collapsed")
        if pick is not None:
            if options.index(pick) == answer:
                st.success("正解です。")
            else:
                st.error(f"ちがいます。正解は {options[answer]}")
            st.info(explain)

    # ── 例題1：生物基礎 × 辞書による集計 ──────────────────
    st.divider()
    st.subheader("例題1　生物基礎 × プログラミング：コドラート法で雑草を数える")
    st.write(
        "畑の5か所に1m四方の枠（コドラート）を置き、枠の中の雑草を記録しました。"
        "1行が1つの枠です（雑草名をカンマで区切る）。自由に書きかえて、結果の変化を確かめられます。"
    )
    q_text = st.text_area(
        "記録（1行＝1つの枠）",
        "スギナ, スギナ, ハコベ, ナズナ\nスギナ, オオバコ\nハコベ, ハコベ, スギナ, シロザ\n"
        "スギナ, スギナ, スギナ\nオオバコ, カラスノエンドウ, ハコベ",
        height=130, key="quad_text",
    )
    quadrats = [[w.strip() for w in line.split(",") if w.strip()] for line in q_text.splitlines() if line.strip()]
    code1 = """count = {}                  # 雑草名 → 個体数
for q in quadrats:          # 枠ごとに
    for name in q:          # 枠の中の雑草を1本ずつ
        if name in count:
            count[name] += 1
        else:
            count[name] = 1
"""
    e1, e2 = st.columns([1, 1])
    e1.code(code1, language="python")
    ind, freq = {}, {}
    for qd in quadrats:
        for name in qd:
            ind[name] = ind.get(name, 0) + 1
        for name in set(qd):
            freq[name] = freq.get(name, 0) + 1
    res1 = pd.DataFrame({"雑草": list(ind), "個体数": list(ind.values()),
                         "出現した枠の数（頻度）": [freq[k] for k in ind]}).sort_values("個体数", ascending=False)
    if len(res1):
        fig = px.bar(res1, x="雑草", y="個体数", text="個体数", color_discrete_sequence=["#6a9a4a"])
        fig.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10))
        e2.plotly_chart(fig, width="stretch")
        e2.caption(f"優占種（いちばん多い雑草）：**{res1.iloc[0]['雑草']}**　→ 🔬 AI土壌診断の「指標植物」につながります。")
    st.dataframe(res1, width="stretch", hide_index=True)
    quiz("q1", "各雑草が「いくつの枠に出てきたか（頻度）」を数えたい。プログラムの2行目 `for name in q:` の q を何に変えればよいか。",
         ["① sorted(q)", "② set(q)", "③ len(q)", "④ quadrats"], 1,
         "set(q) で同じ枠の中の重複を取り除くと、1つの枠につき1回だけ数えられます。"
         "上の表の「出現した枠の数（頻度）」がその結果です。個体数と頻度のどちらで比べるかで、"
         "「優占している」の意味が変わる点に注意しましょう。")

    # ── 例題2：数学Ⅰ・A × データの分析 ──────────────────
    st.divider()
    st.subheader("例題2　数学Ⅰ・A × データの分析：発芽本数のばらつき")
    st.write("小麦を条まきした畑で、20区画（各1m）の発芽本数を数えました。")
    rng2 = np.random.default_rng(7)
    sprouts = np.clip(np.round(rng2.normal(38, 6, 20)), 20, 55).astype(int).tolist()
    sprouts[13] = 19  # 水がたまりやすい区画（外れ値）
    code2 = f"""sprouts = {sprouts}
n = len(sprouts)
mean = sum(sprouts) / n
var = sum([(x - mean) ** 2 for x in sprouts]) / n

# 1mあたり → 1㎡あたりに換算（条間20cm → 1㎡に5列）
per_m2 = [5 * x for x in sprouts]
"""
    st.code(code2, language="python")
    mean2 = float(np.mean(sprouts))
    var2 = float(np.var(sprouts))
    per_m2 = [5 * x for x in sprouts]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("平均（本/m）", f"{mean2:.1f}")
    c2.metric("分散", f"{var2:.2f}")
    c3.metric("換算後の平均（本/㎡）", f"{np.mean(per_m2):.1f}")
    c4.metric("換算後の分散", f"{np.var(per_m2):.2f}")
    fig = px.box(pd.DataFrame({"発芽本数（本/m）": sprouts}), x="発芽本数（本/m）", points="all",
                 color_discrete_sequence=["#c98a2b"])
    fig.update_layout(height=200, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch")
    st.caption("箱ひげ図の左に離れた点（19本）は外れ値です。区画14は水がたまりやすく、発芽が悪かったという設定です。")
    quiz("q2", f"元の分散が {var2:.2f} のとき、1㎡あたりに換算した（すべて5倍した）データの分散はいくつになるか。",
         [f"① {var2:.2f}", f"② {var2 * 5:.2f}", f"③ {var2 * 25:.2f}", f"④ {var2 + 5:.2f}"], 2,
         "データを y = ax + b と変換すると、分散は a² 倍になります（b は影響しない）。a = 5 なので 25 倍です。"
         "上の「換算後の分散」の値と一致することを確かめましょう。")

    # ── 例題3：理科基礎 × 相関係数 ──────────────────
    st.divider()
    st.subheader("例題3　理科基礎 × プログラミング：地温と、発芽までの日数")
    st.write("播種した日の平均地温と、発芽がそろうまでの日数を記録しました（サンプル）。")
    soil_t = [20.5, 19.0, 18.2, 17.5, 16.1, 15.0, 14.2, 13.0, 12.1, 11.0, 10.2, 9.0]
    days_g = [5, 6, 6, 7, 7, 8, 9, 10, 11, 13, 14, 17]
    code3 = """import math
n = len(soil_temp)
mean_x = sum(soil_temp) / n
mean_y = sum(days) / n
sum_xx = sum_yy = sum_xy = 0
for i in range(n):
    dx = soil_temp[i] - mean_x
    dy = days[i] - mean_y
    sum_xx += dx ** 2
    sum_yy += dy ** 2
    sum_xy += dx * dy
r = sum_xy / math.sqrt(sum_xx * sum_yy)
"""
    g1, g2 = st.columns([1, 1])
    g1.code(code3, language="python")
    mx, my = np.mean(soil_t), np.mean(days_g)
    sxx = sum((x - mx) ** 2 for x in soil_t)
    syy = sum((y - my) ** 2 for y in days_g)
    sxy = sum((x - mx) * (y - my) for x, y in zip(soil_t, days_g))
    r3 = sxy / np.sqrt(sxx * syy)
    fig = px.scatter(pd.DataFrame({"平均地温（℃）": soil_t, "発芽までの日数": days_g}),
                     x="平均地温（℃）", y="発芽までの日数", trendline=None,
                     color_discrete_sequence=["#6a9a4a"])
    b = sxy / sxx
    xs3 = np.array([min(soil_t), max(soil_t)])
    fig.add_trace(go.Scatter(x=xs3, y=my + b * (xs3 - mx), mode="lines", name="回帰直線",
                             line=dict(color="#c98a2b", dash="dot")))
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
    g2.plotly_chart(fig, width="stretch")
    g2.metric("相関係数 r", f"{r3:.2f}")
    g2.caption("−1 に近いほど強い負の相関（地温が高いほど、早く発芽する傾向）")
    quiz("q3", "もし、すべての記録で「発芽までの日数」が同じ値だったら、このプログラムはどうなるか。",
         ["① r = 0 と出力される", "② r = 1 と出力される",
          "③ sum_yy が 0 になり、0で割るエラーで止まる", "④ r = −1 と出力される"], 2,
         "日数がすべて同じだと偏差 dy がすべて 0 になり、sum_yy = 0 です。最後の行で 0 で割ることになり、"
         "ZeroDivisionError で停止します。ばらつきのないデータでは、相関係数は定義できません。")
    with st.expander("考えてみよう：相関があれば、地温が原因と言えるか？"):
        st.markdown(
            "地温が低い日は、たいてい**播種が遅い日（11月以降）**でもあります。日の長さや雨など、"
            "ほかの要因も同時に変わっているかもしれません。相関だけでは原因は決められません。\n\n"
            "原因を確かめるには、条件をそろえて**播種日だけを変える実験**が必要です。"
            "→ 🌱 小麦の播種シミュレーター"
        )

    st.divider()
    sample = pd.DataFrame({"区画": range(1, 21), "発芽本数_本per_m": sprouts})
    temp_df = pd.DataFrame({"平均地温_C": soil_t, "発芽までの日数": days_g})
    d1, d2 = st.columns(2)
    d1.download_button("例題2のデータ（CSV）", sample.to_csv(index=False).encode("utf-8-sig"),
                       "sprouts.csv", "text/csv")
    d2.download_button("例題3のデータ（CSV）", temp_df.to_csv(index=False).encode("utf-8-sig"),
                       "soil_temp_days.csv", "text/csv")
    st.caption("Google Colab の左の 📁 にドラッグすると、ノートブックの最後のセルで読み込めます。")

    st.divider()
    mg.media_section(
        ASSETS / "joho1", key="joho1", title="📂 教材テキストの追加",
        accept="PDF・テキスト（md / txt）・ノートブック（ipynb）・Python（py）・CSV・画像",
    )
    st.caption("`assets/joho1/YYYYMMDD/` に置いたファイルが、ここに自動で並びます。"
               ".ipynb には「Google Colab で開く」ボタンが付き、.py は Colab 用ノートブックに変換して保存できます。")

st.divider()
st.caption("© スマートパン屋農家プロジェクト ｜ 数値モデルは説明用の仮定を含みます。")

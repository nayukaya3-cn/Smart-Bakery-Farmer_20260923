"""
スマートパン屋農家を始める！ — 情報発信ダッシュボード
Streamlit + Plotly

起動: streamlit run app.py
構成: 計算する → 可視化する → 自分の条件で判断する（3段構え）
"""
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import soil_vision as sv

# ─────────────────────────────────────────────
# 基本設定
# ─────────────────────────────────────────────
FACEBOOK_URL = "https://www.facebook.com/profile.php?id=100079624235158"
FIELD_AREA_M2 = 96  # 圃場面積（㎡）
ASSETS = Path(__file__).parent / "assets"
PHOTO_LOG = {  # フォルダ名(YYYYMMDD) → 写真キャプション
    "20260913": "草刈り後、小麦畑の整備を開始",
    "20260923": "圃場に風車（かざぐるま）を設置",
}

st.set_page_config(
    page_title="スマートパン屋農家を始める！",
    page_icon="🌾",
    layout="wide",
)

st.markdown(
    """
    <style>
    .hero {padding: 1.6rem 1.8rem; border-radius: 14px;
           background: linear-gradient(120deg, #f6e7c8 0%, #e3efd6 100%);
           color: #3b2f1e; margin-bottom: 1rem;}
    .hero h1 {margin: 0 0 .3rem 0; font-size: 2.1rem;}
    .hero p {margin: 0; font-size: 1.05rem;}
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
    st.write("麦を育て、データで判断し、パンを焼く。")
    st.link_button("📘 Facebookで活動を見る", FACEBOOK_URL, width="stretch")
    st.divider()
    st.caption("拠点：広島県三原市西部（ハウス・畑区画）")
    st.caption(f"圃場面積：約 {FIELD_AREA_M2} ㎡")
    st.caption("このページの数値モデルは説明用の仮定値を含みます。")

tabs = st.tabs(
    ["🏠 ホーム", "🌱 小麦の播種シミュレーター", "📡 圃場モニター",
     "🍞 原料レジリエンス", "🎓 探究学習プログラム", "📝 活動ログ", "📷 圃場フォト", "🔬 AI土壌診断"]
)

# ═════════════════════════════════════════════
# 1. ホーム
# ═════════════════════════════════════════════
with tabs[0]:
    st.markdown(
        """
        <div class="hero">
          <h1>スマートパン屋農家を始める！</h1>
          <p>畑の小麦から一斤のパンまで。センサー・AI・ロボットで「見える化」しながら、
          小さな農とパンの循環を三原でつくります。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    sow_day = date(2026, 10, 20)
    today = date.today()
    c1.metric("圃場面積", f"{FIELD_AREA_M2} ㎡")
    c2.metric("播種目標日", sow_day.strftime("%m/%d"),
              f"あと {(sow_day - today).days} 日" if sow_day >= today else "播種済み")
    c3.metric("栽培品目", "パン用小麦")
    c4.metric("現在のフェーズ", "圃場整備")

    st.subheader("3段構えの考え方")
    s1, s2, s3 = st.columns(3)
    s1.info("**① 計算する**\n\n発芽率・収量・原価・在庫日数を数式で出す。")
    s2.success("**② 可視化する**\n\nグラフで「いま何が起きているか」を共有する。")
    s3.warning("**③ 自分の条件で判断する**\n\n噂や雰囲気ではなく、自分の数値で決める。")

    st.subheader("ロードマップ")
    roadmap = pd.DataFrame([
        dict(工程="草刈り・片付け",           開始="2026-09-13", 終了="2026-09-30", 状態="進行中"),
        dict(工程="土壌診断・堆肥投入",       開始="2026-09-25", 終了="2026-10-14", 状態="予定"),
        dict(工程="耕起・畝立て",             開始="2026-10-10", 終了="2026-10-18", 状態="予定"),
        dict(工程="播種（最適期 10/20頃）",   開始="2026-10-18", 終了="2026-10-31", 状態="予定"),
        dict(工程="生育管理・センサー観測",   開始="2026-11-01", 終了="2027-05-31", 状態="予定"),
        dict(工程="収穫・乾燥・製粉",         開始="2027-06-01", 終了="2027-07-15", 状態="予定"),
        dict(工程="試作パン・探究学習の実施", 開始="2027-07-01", 終了="2027-09-30", 状態="予定"),
    ])
    fig = px.timeline(roadmap, x_start="開始", x_end="終了", y="工程", color="状態",
                      color_discrete_map={"進行中": "#c98a2b", "予定": "#9bb884"})
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch")

# ═════════════════════════════════════════════
# 2. 小麦の播種シミュレーター
# ═════════════════════════════════════════════
with tabs[1]:
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
with tabs[2]:
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

    if up is not None:
        sdf = pd.read_csv(up, parse_dates=["timestamp"])
        st.success(f"{len(sdf)} 行の実データを読み込みました。")
    else:
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
with tabs[3]:
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
with tabs[4]:
    st.header("🎓 畑とパンの探究学習フィールド")
    st.write(
        "通信制高校・サポート校の「探究学習」の外部フィールドとして、"
        "小麦づくりからパンまでをデータで探究するプログラムを準備しています。"
    )
    prog = pd.DataFrame([
        ("種まき", "10月", "播種日と発芽率の関係を実験・記録", "理科・データ分析"),
        ("観測", "11〜5月", "センサーで気温・地温・水分を計測し可視化", "情報・Python"),
        ("ロボット", "通年", "簡易ロボットで圃場を巡回・撮影（ROS2入門）", "情報・工学"),
        ("収穫・製粉", "6〜7月", "収量を予測し、実測と比較", "数学・統計"),
        ("パン", "7〜9月", "原価計算と価格設定、ショック時の判断を体験", "家庭・経済"),
    ], columns=["テーマ", "時期", "活動", "つながる教科"])
    st.dataframe(prog, width="stretch", hide_index=True)

    st.subheader("1コマの流れ（例：90分）")
    flow = pd.DataFrame({"パート": ["導入・問い立て", "圃場で観察・計測", "データ可視化", "発表・ふりかえり"],
                         "分": [15, 35, 25, 15]})
    fig = px.pie(flow, names="パート", values="分", hole=0.5,
                 color_discrete_sequence=["#c98a2b", "#6a9a4a", "#8aa6c1", "#e6c36a"])
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch")
    st.info("学校・団体の方で関心をお持ちの方は、Facebookからお気軽にご連絡ください。")
    st.link_button("📘 Facebookで問い合わせる", FACEBOOK_URL)

# ═════════════════════════════════════════════
# 6. 活動ログ
# ═════════════════════════════════════════════
with tabs[5]:
    st.header("📝 活動ログ")
    if "log" not in st.session_state:
        st.session_state.log = pd.DataFrame([
            dict(日付=date(2026, 9, 13), カテゴリ="圃場", 内容="草刈り後、小麦畑の整備を開始。"),
            dict(日付=date(2026, 9, 17), カテゴリ="圃場", 内容="ハウス脇・母屋裏の2区画で草刈り。工具・ガラの片付けと土壌診断の準備へ。"),
            dict(日付=date(2026, 9, 17), カテゴリ="獣害対策", 内容="イノシシ対策：物理的な柵と周囲の草刈り（隠れ場所・エサをなくす環境整備）を開始、継続中。"),
            dict(日付=date(2026, 9, 23), カテゴリ="圃場", 内容="圃場に風車を設置。"),
            dict(日付=date(2026, 9, 24), カテゴリ="発信", 内容="AI土壌診断（写真→生育ムラ→施肥設計、指標植物のベイズ推定）をダッシュボードに追加。"),
            dict(日付=date(2026, 9, 23), カテゴリ="発信", 内容="「スマートパン屋農家を始める！」発信開始。"),
        ])

    with st.expander("✏️ 記録を追加（このセッション内のみ保持）"):
        with st.form("add_log", clear_on_submit=True):
            d = st.date_input("日付", value=date.today())
            cat = st.selectbox("カテゴリ", ["圃場", "栽培", "獣害対策", "パン", "探究学習", "発信"])
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
    st.download_button("CSVでダウンロード", log.to_csv(index=False).encode("utf-8-sig"),
                       "activity_log.csv", "text/csv")

# ═════════════════════════════════════════════
# 7. 圃場フォト（assets/YYYYMMDD/*.jpg を自動で読み込む）
# ═════════════════════════════════════════════
with tabs[6]:
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
            cols[i % 4].image(str(p), width="stretch")

# ═════════════════════════════════════════════
# 8. AI土壌診断（写真 → 生育ムラ → 施肥設計／指標植物）
# ═════════════════════════════════════════════
with tabs[7]:
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
    elif all_photos:
        img_src = st.selectbox("写真を選択", all_photos,
                               format_func=lambda p: f"{p.parent.name} / {p.name}")

    if img_src is None:
        st.info("写真を選ぶかアップロードしてください。")
    else:
        rgb = sv.load_image(img_src)
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
        t2.download_button("処方箋をCSVで保存", rx.to_csv(index=False).encode("utf-8-sig"),
                           "prescription.csv", "text/csv")

        st.divider()
        st.subheader("指標植物から土の傾向を推定する（ベイズ更新）")
        w1, w2 = st.columns([2, 3])
        with w1:
            if sv.ai_available():
                if st.button("🤖 生成AIに雑草の候補を提案させる"):
                    with st.spinner("解析中…"):
                        try:
                            res = sv.ai_suggest_weeds(rgb)
                            st.session_state.ai_weeds = res
                            st.session_state.weeds = [c["name"] for c in res.get("candidates", [])
                                                      if c.get("name") in sv.INDICATORS
                                                      and c.get("confidence", 0) >= 0.5]
                        except Exception as e:  # noqa: BLE001
                            st.error(f"AI解析に失敗しました：{e}")
                if "ai_weeds" in st.session_state:
                    for c in st.session_state.ai_weeds.get("candidates", []):
                        st.caption(f"・{c.get('name')}（確信度 {c.get('confidence', 0):.2f}）{c.get('reason', '')}")
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

st.divider()
st.caption("© スマートパン屋農家プロジェクト ｜ 数値モデルは説明用の仮定を含みます。")

"""
探究コーナー ─ 衛星データ解析（Python実装）：宇宙から、自分の畑と川を「数値で」見る
配置先: pages/14_🛰️_衛星データ解析.py （Streamlit のマルチページ構成）

探究の問い（タブ）
  ❶ 光学：色を計算すると何が見えるか？         バンド演算（NDVI・NDWI）／雲という限界／小麦の1シーズン
  ❷ SAR：雲の下をどう見るか？                   後方散乱とdB／スペックル／Leeフィルタ／大津の方法で水域
  ❸ 変化をどう見つけるか？                      大雨の前後の2枚の差で「新しく浸水した所」／わたしの圃場の面積
  ❹ 土地の種類をどう分けるか？                  教師あり（ナイーブベイズ）と教師なし（k-means）／分け方の落とし穴
  ❺ 言説と観測をどう比べるか？                  船をCFARで数え、「港が空っぽ」という言説と比べる（情報の妥当性確認）
  ❻ 3層の観測をどうつなぐか？                   衛星（広域・ときどき）→ ドローン・地上ロボット（圃場・すぐ）→ 目視・スマホ（地点・いま）
                                                 を、ベイズの定理（対数オッズの足し算）で1枚の浸水確率の地図に重ねる

骨格はリポジトリ共通の3段構え：
  ① 現象を計算する（反射率・後方散乱・指数・閾値）→ ② 数値を可視化する（地図・ヒストグラム・時系列）
  → ③ 自分の条件で判断する（自分の圃場・自分の閾値・自分の行動）

方針
  - 計算は satellite_lab.py（`python satellite_lab.py` で自己チェック）。numpy と pandas だけで動く。
  - 初期表示はすべて架空データ（三原の小麦畑と川沿いを想定して作った地図。実測ではありません）。
  - アップロードした記録はセッション内だけで使い、サーバーには残さない。外部の生成AIは呼び出さない。
  - 下敷き：『SAR衛星データ解析入門』（講談社）・『Pythonで学ぶ衛星データ解析基礎』、実データの入手先として Tellus。
    文章・データ・コードは独自のもので、書籍の転載ではありません。
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import satellite_lab as sl
import security_guard as sg

st.set_page_config(page_title="探究コーナー：衛星データ解析", page_icon="🛰️", layout="wide")

import media_gallery as mg  # noqa: E402
import social as sn  # noqa: E402  SNSのURLは social.py で一括管理

UPDATED = "2026-10-17"
PAGE = "satellite_lab"
NOTEBOOK = "notebooks/satellite_analysis_practice.ipynb"
BOOKS = ("安井秀輔・佐藤功一・藤原寛朗『SAR衛星データ解析入門』（講談社 KS情報科学専門書）"
         "／田中康平・田村賢哉・玉置慎吾 著、宮﨑浩之 監修『Pythonで学ぶ衛星データ解析基礎』")
CLASS_RGB = np.array([[63, 124, 172], [46, 110, 64], [201, 170, 90], [140, 140, 140]], dtype=np.uint8)
C_WATER, C_FLOOD, C_MINE = "#3f7cac", "#d6453d", "#c98a2b"
PALETTE = ["#3f7cac", "#c98a2b", "#6a9a4a", "#8a5fa8"]


def plot(fig, h: int = 340, **kw) -> None:
    has_title = bool(kw.get("title") or fig.layout.title.text)
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=50 if has_title else 10, b=10), **kw)
    st.plotly_chart(fig, width="stretch")


def show_img(arr: np.ndarray, title: str, h: int = 330, box: tuple | None = None, **kw) -> None:
    """2次元（数値）または3次元（RGB）の配列を地図として表示。box は「わたしの圃場」の枠。"""
    if arr.ndim == 3:
        fig = px.imshow(arr)
    else:
        fig = px.imshow(arr, color_continuous_scale=kw.pop("cmap", "gray"), zmin=kw.pop("zmin", None),
                        zmax=kw.pop("zmax", None), aspect="equal")
    if box is not None:
        r0, r1, c0, c1 = box
        fig.add_shape(type="rect", x0=c0 - .5, x1=c1 - .5, y0=r0 - .5, y1=r1 - .5,
                      line=dict(color=C_MINE, width=3))
    fig.update_xaxes(showticklabels=False)
    fig.update_yaxes(showticklabels=False)
    plot(fig, h, title=title, **kw)


def rgb(opt: np.ndarray, bands=(2, 1, 0), gain: float = 3.5) -> np.ndarray:
    return (np.clip(np.stack([opt[b] for b in bands], -1) * gain, 0, 1) * 255).astype(np.uint8)


def overlay(base: np.ndarray, masks: list[tuple[np.ndarray, str]], alpha: float = .7) -> np.ndarray:
    """グレーの地図の上に、マスクを色で重ねる。"""
    g = np.clip((base - np.percentile(base, 1)) / (np.ptp(np.percentile(base, [1, 99])) + 1e-9), 0, 1)
    img = np.stack([g, g, g], -1) * 255
    for m, hexcol in masks:
        c = np.array([int(hexcol[i:i + 2], 16) for i in (1, 3, 5)])
        img[m] = (1 - alpha) * img[m] + alpha * c
    return img.astype(np.uint8)


def legend_classes() -> None:
    st.caption("　".join(f"<span style='color:rgb{tuple(int(v) for v in CLASS_RGB[i])}'>■</span> {c}"
                        for i, c in enumerate(sl.CLASSES)), unsafe_allow_html=True)


# ─────────────────────────────────────────────
# サイドバー：架空の地図の条件
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("🛰️ 衛星データ解析")
    seed = int(st.number_input("くじの番号（地図の作り直し）", 0, 9999, 0, 1,
                               help="同じ番号なら同じ架空の地図になります。"))
    cloud = st.slider("光学の日の雲の量", 0.0, 0.7, 0.25, 0.05, help="光学センサーは雲を通り抜けられません。")
    looks = st.select_slider("SARのルック数（ならしの回数）", [1, 2, 4], value=1,
                             help="衛星の側で何回分を平均したか。多いほどザラつきは減り、細かさは落ちます。")
    flood_m = st.slider("大雨で川の水位がどれだけ上がるか（m・想定）", 0.5, 3.0, 1.5, 0.25)
    st.caption("地図はすべて架空です（三原の小麦畑と川沿いを想定。1画素＝10m×10m）。")
    st.divider()
    sn.buttons("で相談する", stacked=True)

SC = sl.make_scene(seed, cloud_cover=cloud, flood_m=flood_m, looks=looks)
H, W = SC.cls.shape
DB_FILT = sl.to_db(sl.lee_filter(SC.sar_before, 2, looks))
THR_AUTO = sl.water_threshold(DB_FILT)

st.title("🛰️ 探究コーナー：衛星データ解析（Python実装）")
st.caption(f"下敷き：{BOOKS}　／　実データの入手先：Tellus ほか　／　更新 {UPDATED}")
st.info("いま表示しているのは **架空の地図** です。実測ではありません。実データでの試し方は 📝 タブにあります。")

tab0, tab1, tab2, tab3, tab4, tab5, tab7, tab6 = st.tabs([
    "🧭 この探究の流れ", "❶ 光学：色を計算する", "❷ SAR：雲の下を見る", "❸ 変化を見つける",
    "❹ 土地を分類する", "❺ 言説と観測を比べる", "❻ 3層の観測をつなぐ", "📝 マイ判断・実データへ",
])

# ═════════════════════════════════════════════
# 0. 流れ
# ═════════════════════════════════════════════
with tab0:
    st.header("🧭 衛星データは「写真」ではなく「数値の表」")
    st.write("衛星の画像は、1画素ごとに **数値** が入った大きな表です。だから、計算できます。"
             "このページでは、自分の畑と川を、宇宙から見た数値で確かめます。")
    st.dataframe(pd.DataFrame([
        ("❶ 光学：色を計算する", "赤と近赤外の反射率から NDVI（植物の元気さ）・NDWI（水）を計算。雲の日は見えない",
         "① 計算 → ② 可視化"),
        ("❷ SAR：雲の下を見る", "電波をあてて返ってきた強さ（後方散乱）。水は暗く、建物は明るい。ザラつきをならして水を探す",
         "① 計算 → ② 可視化 → ③ 閾値の判断"),
        ("❸ 変化を見つける", "大雨の前と後の2枚の差で「新しく浸水した所」を探し、わたしの圃場の面積を数える",
         "③ 自分の条件で判断する"),
        ("❹ 土地を分類する", "教師あり・教師なしの機械学習で土地の種類を当て、答え合わせの仕方まで確かめる",
         "① 計算 → ③ 判断（どこまで信じるか）"),
        ("❺ 言説と観測を比べる", "「港が空っぽ」という言説と、SARで数えた船の数を比べる。差を「確かめる合図」にする",
         "③ 判断（情報の妥当性確認）"),
        ("❻ 3層の観測をつなぐ", "衛星（広域）→ ドローン・地上ロボット（圃場）→ 目視・スマホ（地点）を、ベイズの定理で1枚の確率の地図に",
         "① 計算 → ② 可視化 → ③ 判断（次にどこを確かめるか）"),
    ], columns=["問い", "やること", "3段構えとの対応"]), width="stretch", hide_index=True)

    st.subheader("光学とSAR：2つの「目」")
    st.dataframe(pd.DataFrame([
        ("しくみ", "太陽の光の反射を測る（受け身）", "自分で電波を出し、はね返りを測る（能動）"),
        ("雲・夜", "雲の下・夜は見えない", "雲を通り抜け、夜も見える"),
        ("見えるもの", "色・植物の元気さ（NDVI）・水の色", "表面のでこぼこ・水面（鏡のように暗い）・建物（明るい）"),
        ("ザラつき", "少ない", "スペックルという掛け算の雑音が大きい → ならしてから使う"),
        ("農業で", "生育の良し悪し・収穫の時期", "梅雨・台風の日の浸水・作付けの確認"),
        ("このページ", "❶", "❷・❸・❺"),
    ], columns=["", "光学（例：Sentinel-2）", "SAR 合成開口レーダー（例：Sentinel-1）"]),
        width="stretch", hide_index=True)

    c1, c2 = st.columns(2)
    with c1:
        show_img(SC.cls, "正解の地図（ふつうは分からない）", cmap=[[0, "rgb(63,124,172)"], [.33, "rgb(46,110,64)"],
                 [.67, "rgb(201,170,90)"], [1, "rgb(140,140,140)"]], box=SC.my_field, coloraxis_showscale=False)
        legend_classes()
    with c2:
        show_img(SC.elev, "標高（川からの高さ m）", cmap="earth", box=SC.my_field)
    st.caption("🟧 の枠が「わたしの圃場」（架空）。川に近く、少し低い場所にあります。")

    with st.expander("このページとつながる教科・研究"):
        st.markdown(
            "- **情報Ⅰ**：データの活用（表・可視化・分類・評価）／**情報Ⅱ**：機械学習・画像処理\n"
            "- **物理**：電磁波（光と電波の波長）・反射・dB（対数）／**生物基礎**：光合成と葉の反射\n"
            "- **地理**：地形・ハザードマップ／**科学と人間生活**：水のリスク（浸水の判断）\n"
            "- **研究とのつながり**：衝撃を受ける前に「数値で知っている」状態をつくる＝情報の非対称性を減らす。"
            "❺ の乖離指標 D は、言説と観測のずれを測る操作化の一例です。"
        )

# ═════════════════════════════════════════════
# 1. 光学
# ═════════════════════════════════════════════
with tab1:
    st.header("❶ 光学：色を計算すると何が見えるか？")
    st.write("植物の葉は **赤い光をよく吸い**（光合成に使う）、**近赤外をよく反射** します。"
             "その差を割り算で 0〜1 にそろえたのが NDVI です。")
    st.latex(r"\mathrm{NDVI}=\frac{\mathrm{NIR}-\mathrm{Red}}{\mathrm{NIR}+\mathrm{Red}},\qquad "
             r"\mathrm{NDWI}=\frac{\mathrm{Green}-\mathrm{NIR}}{\mathrm{Green}+\mathrm{NIR}}")
    o = SC.optical
    ND = sl.ndvi(o[2], o[3])
    NW = sl.ndwi(o[1], o[3])
    c1, c2, c3 = st.columns(3)
    with c1:
        show_img(rgb(o), "トゥルーカラー（赤・緑・青）", box=SC.my_field)
    with c2:
        show_img(rgb(o, (3, 2, 1), 2.5), "フォールスカラー（近赤外を赤に）", box=SC.my_field)
    with c3:
        show_img(ND, "NDVI（緑ほど植物が元気）", cmap="RdYlGn", zmin=-0.5, zmax=0.9, box=SC.my_field)
    st.caption("フォールスカラーでは、近赤外をよく反射する植物が **赤く** 見えます。")

    st.subheader("① 計算：土地の種類ごとの数値")
    df = pd.DataFrame({"土地": np.array(sl.CLASSES)[SC.cls.ravel()], "NDVI": ND.ravel(), "NDWI": NW.ravel(),
                       "雲": np.where(SC.cloud.ravel(), "雲あり", "雲なし")})
    st.dataframe(df[df["雲"] == "雲なし"].groupby("土地")[["NDVI", "NDWI"]].mean().round(2).T,
                 width="stretch")
    st.subheader("② 可視化：2つの指数で散布図にすると")
    smp = df.sample(min(3000, len(df)), random_state=seed)
    fig = px.scatter(smp, x="NDVI", y="NDWI", color="土地", symbol="雲", opacity=.55,
                     color_discrete_sequence=[f"rgb{tuple(int(v) for v in c)}" for c in CLASS_RGB],
                     category_orders={"土地": sl.CLASSES})
    plot(fig, 380)
    if cloud > 0:
        st.warning(f"雲の画素（{SC.cloud.mean():.0%}）は、森でも畑でも NDVI が 0 近くに集まります。"
                   "**雲の日を「植物がない日」と読まない** ことが、光学で最初の落とし穴です。")

    st.subheader("小麦の1シーズン：光学は雲で欠け、SARは欠けない")
    stress = st.checkbox("途中で湿害（生育の鈍り）が起きたことにする", key="sat_stress")
    S = sl.season(seed, stress_day=120 if stress else None)
    fig = go.Figure([
        go.Scatter(x=S["日付"], y=S["NDVI（真の値）"], name="NDVI（真の値・ふつうは分からない）",
                   line=dict(color="#999", dash="dot")),
        go.Scatter(x=S["日付"], y=S["NDVI（光学で見えた日）"], name="NDVI（光学で見えた日）", mode="markers",
                   marker=dict(color=PALETTE[2], size=8)),
        go.Scatter(x=S["日付"], y=S["VH後方散乱 dB（SAR）"], name="VH dB（SAR・右の目盛り）", mode="markers+lines",
                   yaxis="y2", marker=dict(color=PALETTE[0], size=6, symbol="diamond"), line=dict(width=1)),
    ])
    fig.update_layout(yaxis=dict(title="NDVI"), yaxis2=dict(title="VH [dB]", overlaying="y", side="right"),
                      legend=dict(orientation="h", y=-0.2))
    plot(fig, 380)
    m1, m2, m3 = st.columns(3)
    m1.metric("光学で見えた日", f"{S['NDVI（光学で見えた日）'].notna().sum()} 回")
    m2.metric("光学の最長の空白", f"{sl.longest_gap(S['NDVI（光学で見えた日）'])} 日")
    m3.metric("SARの観測（雲に関係なく）", f"{S['VH後方散乱 dB（SAR）'].notna().sum()} 回")
    st.caption("曲線・雲の確率・SARとNDVIの関係はすべて架空の近似です。梅雨（6月）に光学の空白が長くなりやすい、"
               "という傾向を体験するためのものです。")

    with st.expander("📂 自分の NDVI 時系列（CSV）を重ねる"):
        st.write("Tellus や Copernicus Browser で自分の圃場の NDVI を書き出し、`日付`・`NDVI` の2列の CSV にして読み込みます。")
        up = st.file_uploader("CSV（日付, NDVI）", type="csv", key="sat_up")
        if up is not None:
            raw = sg.read_csv_safely(up, page=PAGE, kind="ndvi_csv")
            if raw is not None and {"日付", "NDVI"} <= set(raw.columns):
                raw["日付"] = pd.to_datetime(raw["日付"], errors="coerce")
                raw = raw.dropna(subset=["日付", "NDVI"]).sort_values("日付")
                fig = px.line(raw, x="日付", y="NDVI", markers=True)
                fig.add_scatter(x=S["日付"], y=S["NDVI（真の値）"], name="架空の小麦の曲線", line=dict(dash="dot"))
                plot(fig, 320)
            elif raw is not None:
                st.error("列名を `日付` と `NDVI` にしてください。")
        st.caption("読み込んだ記録はこの画面の中だけで使い、保存しません。")

# ═════════════════════════════════════════════
# 2. SAR
# ═════════════════════════════════════════════
with tab2:
    st.header("❷ SAR：雲の下をどう見るか？")
    st.write("SARは自分で電波を出し、はね返ってきた強さ（**後方散乱係数 σ⁰**）を測ります。"
             "値の幅がとても広いので、**dB（デシベル）** という対数の目盛りにします。")
    st.latex(r"\sigma^0_{\mathrm{dB}} = 10\log_{10}\sigma^0 \qquad(\sigma^0=0.01 \Rightarrow -20\,\mathrm{dB},\ "
             r"\sigma^0=1 \Rightarrow 0\,\mathrm{dB})")
    st.dataframe(pd.DataFrame([
        ("水面", "鏡のように電波を向こう側へはね返す → 衛星に戻らない", "とても暗い（−20 dB 前後）"),
        ("畑・草地", "表面のでこぼこで少しずつ散らばる", "中くらい（−15 dB 前後）"),
        ("森", "葉や枝の中で何度も散らばる", "やや明るい（−8 dB 前後）"),
        ("建物", "壁と地面の角で、まっすぐ衛星に返る（二回反射）", "とても明るい（0 dB 前後）"),
    ], columns=["土地", "電波のふるまい", "SARでの見え方（この架空の地図の目安）"]), width="stretch", hide_index=True)

    r = st.slider("ならし（Lee フィルタ）の窓の半径（画素）", 0, 4, 2, key="sat_r")
    DBR = sl.to_db(SC.sar_before)
    DBF = sl.to_db(sl.lee_filter(SC.sar_before, r, looks)) if r > 0 else DBR
    c1, c2 = st.columns(2)
    with c1:
        show_img(DBR, "① 生のSAR画像（dB）：ザラザラ＝スペックル", zmin=-28, zmax=2)
    with c2:
        show_img(DBF, f"② Lee フィルタ（半径 {r}）でならした画像", zmin=-28, zmax=2)
    st.caption("スペックルは、1画素の中のたくさんの小さな反射が強め合ったり弱め合ったりして起きる「掛け算の雑音」です。"
               "雲のある日でも、SARの画像は変わりません。")

    st.subheader("① 計算 → ② 可視化：ヒストグラムで水の閾値を決める")
    thr_auto = sl.water_threshold(DBF)
    fig = px.histogram(pd.DataFrame({"dB": DBF.ravel(), "土地（正解）": np.array(sl.CLASSES)[SC.cls.ravel()]}),
                       x="dB", color="土地（正解）", nbins=120, barmode="overlay", opacity=.6,
                       color_discrete_sequence=[f"rgb{tuple(int(v) for v in c)}" for c in CLASS_RGB],
                       category_orders={"土地（正解）": sl.CLASSES})
    fig.add_vline(x=thr_auto, line_dash="dash", line_color=C_FLOOD, annotation_text=f"大津（2段） {thr_auto:.1f} dB")
    fig.add_vline(x=sl.otsu(DBF), line_dash="dot", line_color="#777", annotation_text="大津（1段）",
                  annotation_position="bottom right")
    plot(fig, 330)
    st.caption("大津の方法は「2つの山のあいだ」を自動で探します。水は面積が小さいので、1回だけだと"
               "「暗い所／明るい所（建物・森）」の境目を選んでしまいます。そこで暗い側をもう一度分けます（2段）。")

    st.subheader("③ 判断：閾値を自分で動かす")
    thr = st.slider("水とみなす閾値（dB）", -26.0, -8.0, float(round(thr_auto, 1)), 0.5, key="sat_thr")
    pred = DBF < thr
    s_raw = sl.scores(SC.cls == sl.WATER, DBR < thr)
    s_f = sl.scores(SC.cls == sl.WATER, pred)
    c1, c2 = st.columns([3, 2])
    with c1:
        show_img(overlay(DBF, [(pred & (SC.cls == sl.WATER), C_WATER), (pred & (SC.cls != sl.WATER), C_FLOOD)]),
                 "水と判定した所（青＝正しい・赤＝誤報）")
    with c2:
        st.dataframe(pd.DataFrame({"生のまま": s_raw, "ならした後": s_f}).loc[
            ["見つけた", "誤報", "見逃し", "再現率", "適合率", "F1"]].T.round(2), width="stretch")
        st.metric("ならした後の水の面積", f"{pred.sum() * sl.PIXEL_HA:.1f} ha",
                  f"正解 {(SC.cls == sl.WATER).sum() * sl.PIXEL_HA:.1f} ha", delta_color="off")
        st.write("閾値を上げる（明るい側へ）と見逃しは減り、誤報が増えます。"
                 "**どちらを許すか** は、何に使うか（避難の判断か、面積の集計か）で変わります。")

# ═════════════════════════════════════════════
# 3. 変化
# ═════════════════════════════════════════════
with tab3:
    st.header("❸ 変化をどう見つけるか？：大雨の前と後")
    st.write("1枚だけで「水」を探すと、もともとの川やため池も数えてしまいます。"
             "**前と後の2枚の差**（dB の引き算＝真数の対数比）を見ると、「新しく水になった所」だけが残ります。")
    st.latex(r"\Delta = \sigma^0_{\mathrm{後,dB}}-\sigma^0_{\mathrm{前,dB}} = 10\log_{10}\frac{\sigma^0_{\mathrm{後}}}"
             r"{\sigma^0_{\mathrm{前}}}\quad\Rightarrow\quad \Delta<-T\ かつ\ \sigma^0_{\mathrm{後,dB}}<\text{水の閾値}")
    c0, c00 = st.columns(2)
    drop = c0.slider("「下がった」とみなす差 T（dB）", 1.0, 8.0, 3.0, 0.5, key="sat_drop")
    wthr = c00.slider("水の閾値（dB）", -26.0, -10.0, float(round(THR_AUTO, 1)), 0.5, key="sat_wthr")
    DIFF, CHG = sl.change_map(SC.sar_before, SC.sar_after, drop, wthr, 2, looks)
    ONE = sl.water_map(SC.sar_after, wthr, 2, looks)
    AFTER_DB = sl.to_db(sl.lee_filter(SC.sar_after, 2, looks))
    c1, c2, c3 = st.columns(3)
    with c1:
        show_img(DB_FILT, "大雨の前（ならした dB）", zmin=-28, zmax=2, box=SC.my_field)
    with c2:
        show_img(AFTER_DB, "大雨の後（ならした dB）", zmin=-28, zmax=2, box=SC.my_field)
    with c3:
        show_img(DIFF, "差 Δ（赤いほど暗くなった＝浸水の候補）", cmap="RdBu", zmin=-12, zmax=12, box=SC.my_field)

    s_chg = sl.scores(SC.flood, CHG)
    s_one = sl.scores(SC.flood, ONE)
    c1, c2 = st.columns([3, 2])
    with c1:
        show_img(overlay(AFTER_DB, [(CHG & SC.flood, C_WATER), (CHG & ~SC.flood, C_FLOOD),
                                    (SC.flood & ~CHG, "#f0c050")]),
                 "新しい浸水（青＝当たり・赤＝誤報・黄＝見逃し）", h=380, box=SC.my_field)
    with c2:
        st.dataframe(pd.DataFrame({"後の1枚だけ": s_one, "前後の差": s_chg}).loc[
            ["見つけた", "誤報", "見逃し", "再現率", "適合率", "F1"]].T.round(2), width="stretch")
        st.caption("「後の1枚だけ」は、もともとの川・池をすべて誤報として数えてしまいます。")

    st.subheader("③ 自分の条件で判断する：わたしの圃場")
    mine = sl.crop(CHG, SC.my_field)
    mine_true = sl.crop(SC.flood, SC.my_field)
    area = mine.size * sl.PIXEL_HA
    m1, m2, m3 = st.columns(3)
    m1.metric("わたしの圃場の広さ", f"{area:.2f} ha")
    m2.metric("SARで浸水と判定", f"{mine.sum() * sl.PIXEL_HA:.2f} ha", f"{mine.mean():.0%}", delta_color="off")
    m3.metric("（答え合わせ）本当の浸水", f"{mine_true.sum() * sl.PIXEL_HA:.2f} ha", delta_color="off")
    act = st.slider("何％以上浸かったら、行動を起こすか", 0, 50, 10, 5, key="sat_act")
    if mine.mean() * 100 >= act:
        st.error(f"判定：**行動する**（浸水 {mine.mean():.0%} ≥ {act}%）。例：排水溝の点検、播種の延期、"
                 "保険・共済への連絡の準備。")
    else:
        st.success(f"判定：**見守る**（浸水 {mine.mean():.0%} < {act}%）。次の観測日に、もう一度確かめる。")
    st.write("サイドバーの「川の水位がどれだけ上がるか」を動かして、**何 m で自分の圃場が浸かり始めるか** を探しましょう。"
             "これは、自分の土地の「デッドライン」を決める作業です。")
    with st.expander("SARの浸水判定が苦手なところ"):
        st.markdown(
            "- **背の高い作物の中の水**：茎と水面の二回反射で、かえって **明るく** なることがある\n"
            "- **建物のあいだの水**：建物の明るさにまぎれる\n"
            "- **山の陰（レーダーシャドウ）**：もともと暗いので水と間違える → 標高と重ねて確かめる\n"
            "- **観測のタイミング**：衛星が来る日しか見えない。ピークを逃すことがある\n\n"
            "だから、実際の避難判断は **自治体のハザードマップ・気象庁の情報・避難指示** に従います。"
            "衛星は「あとから確かめる」「次に備える」ための道具です。"
        )

# ═════════════════════════════════════════════
# 4. 分類
# ═════════════════════════════════════════════
with tab4:
    st.header("❹ 土地の種類をどう分けるか？：教師あり と 教師なし")
    st.write("**教師あり**：人が地図に「ここは水」「ここは森」と点を打ち（教師データ）、そこから規則を学ぶ。"
             "**教師なし**：数値の似たもの同士をまとめるだけ。グループの名前は、あとから人がつける。")
    all_cols = list(sl.features(SC).columns)
    cols = st.multiselect("使う特徴（バンド・指数・SAR）", all_cols,
                          default=["赤", "近赤外", "短波長赤外", "NDVI", "NDWI", "VV dB（ならし後）"], key="sat_cols")
    c1, c2 = st.columns(2)
    how = c1.radio("学習用とテスト用の分け方", ["場所で分ける", "ランダム"], horizontal=True, key="sat_how",
                   help="場所で分ける：20画素四方の区画ごとに分ける。ランダム：1画素ずつ分ける。")
    n_train = c2.slider("教師データの数（人が打つ点）", 20, 2000, 400, 20, key="sat_n")
    if not cols:
        st.info("特徴を1つ以上選んでください。")
    else:
        R = sl.classify(SC, cols, how, seed, n_train)
        c1, c2, c3 = st.columns(3)
        lab_rgb = lambda a: CLASS_RGB[a]  # noqa: E731
        with c1:
            show_img(lab_rgb(SC.cls), "正解")
        with c2:
            show_img(lab_rgb(R["教師あり（ナイーブベイズ）"]),
                     f"教師あり　正解率 {R['正解率']['教師あり（ナイーブベイズ）']:.1%}")
        with c3:
            show_img(lab_rgb(R["教師なし（k-means→名前づけ）"]),
                     f"教師なし　正解率 {R['正解率']['教師なし（k-means→名前づけ）']:.1%}")
        legend_classes()
        st.caption("正解率はテスト側の画素だけで数えています（学習に使った場所では答え合わせしない）。")
        st.subheader("混同行列（教師あり・テスト側）：どの種類を、どれと間違えたか")
        st.dataframe(R["混同行列"], width="stretch")
        if cloud > 0.1 and not any(c.startswith("VV") for c in cols):
            st.warning("光学だけで分類すると、雲の画素はどれかの種類に無理やり入れられます。"
                       "「VV dB（ならし後）」を足すと、どう変わるでしょう。")
    with st.expander("答え合わせの落とし穴：隣の画素は、ほぼ同じ"):
        st.write("衛星画像の隣り合う画素はよく似ています（空間の自己相関）。1画素ずつランダムに分けると、"
                 "テストの画素のすぐ隣が学習に入っていて、**答えを横から教わった状態** で評価することになります。"
                 "この架空の地図では種類どうしの差が大きいので差は小さめですが、"
                 "近くの画素を丸ごと覚える手法（k近傍法・深層学習）や、区画ごとの違いを当てる課題では、"
                 "ランダムに分けた正解率が実力より高く出ることがあります。**場所で分けて** 評価するのが安全です。")

# ═════════════════════════════════════════════
# 5. 言説と観測
# ═════════════════════════════════════════════
with tab5:
    st.header("❺ 言説と観測をどう比べるか？：港の船を数える")
    st.write("「港から船が消えた」「原料が入ってこない」――危機のときには、強い言葉の情報が広がり、"
             "それを見た人が **念のため多めに買う** ことで、本当に品薄が深まることがあります（ブルウィップ効果・情報カスケード）。"
             "SARは雲の日でも海の上の船を見つけられます。**言説が示す変化** と **観測が示す変化** を並べてみます。")

    st.subheader("① 計算：CFAR で船を見つける")
    c1, c2, c3 = st.columns(3)
    n_ships = c1.slider("本物の船の数（架空）", 0, 40, 18, key="sat_ns")
    wind = c2.slider("海の荒れ（風）", 0.0, 1.0, 0.3, 0.05, key="sat_wind",
                     help="風が強いと海面がでこぼこし、明るくザラつきます（船と間違えやすい）。")
    pfa_exp = c3.slider("誤報の起きやすさ（10の何乗）", -6, -2, -4, key="sat_pfa",
                        help="CFAR の誤報確率。小さくするほど慎重になり、見逃しが増えます。")
    inten, truth, land = sl.port_scene(n_ships, seed=seed, wind=wind)
    found = sl.components(sl.cfar(inten, land, 10.0 ** pfa_exp))
    mt = sl.match_ships(found, truth)
    c1, c2 = st.columns([3, 2])
    with c1:
        fig = px.imshow(sl.to_db(inten), color_continuous_scale="gray", zmin=-28, zmax=4, aspect="equal")
        if found:
            fig.add_scatter(x=[f[1] for f in found], y=[f[0] for f in found], mode="markers",
                            marker=dict(symbol="circle-open", size=14, color=C_FLOOD, line=dict(width=2)),
                            name="検出")
        fig.update_xaxes(showticklabels=False)
        fig.update_yaxes(showticklabels=False)
        plot(fig, 360, title="架空の港の沖（上の明るい帯は陸）", coloraxis_showscale=False)
    with c2:
        st.dataframe(pd.DataFrame([mt]).T.rename(columns={0: "隻"}), width="stretch")
        st.caption("CFAR（一定誤報率）：周りの海の明るさの平均より何倍も明るい点だけを船とみなす。"
                   "周りに合わせて基準が動くので、海が荒れた所でも誤報の割合を一定に保とうとする。")

    st.subheader("② 可視化：12週間の「言説」と「観測」")
    c1, c2, c3 = st.columns(3)
    real_drop = c1.slider("実際の減り方（架空）", 0.0, 0.8, 0.2, 0.05, key="sat_real")
    claim_drop = c2.slider("言説が語る減り方", 0.0, 0.95, 0.8, 0.05, key="sat_claim")
    change_week = c3.slider("変化が始まった週", 3, 10, 7, key="sat_cw")
    WK = sl.weekly_port(12, 20, real_drop, claim_drop, change_week, seed, wind, 10.0 ** pfa_exp)
    fig = go.Figure([
        go.Scatter(x=WK["週"], y=WK["言説が示す隻数"], name="言説が示す隻数", line=dict(color=C_FLOOD, width=3)),
        go.Scatter(x=WK["週"], y=WK["SARで数えた隻数"], name="SARで数えた隻数", mode="lines+markers",
                   line=dict(color=PALETTE[0], width=3)),
        go.Scatter(x=WK["週"], y=WK["本物の隻数（ふつうは分からない）"], name="本物（ふつうは分からない）",
                   line=dict(color="#999", dash="dot")),
    ])
    fig.add_vline(x=change_week - .5, line_dash="dash", line_color="#777")
    fig.update_layout(xaxis_title="週", yaxis_title="隻", legend=dict(orientation="h", y=-0.25))
    plot(fig, 360)

    st.subheader("③ 判断：乖離指標 D")
    st.latex(r"\Delta=\frac{\overline{x}_{\mathrm{変化後}}}{\overline{x}_{\mathrm{変化前}}}-1,\qquad "
             r"D=\left|\,\Delta_{\text{言説}}-\Delta_{\text{観測}}\,\right|")
    G = sl.gap_index(WK, change_week)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("言説の変化率", f"{G['言説の変化率']:+.0%}")
    m2.metric("観測の変化率", f"{G['観測の変化率']:+.0%}")
    m3.metric("乖離指標 D", f"{G['D']:.2f}")
    m4.metric("観測の不確かさ", f"±{G['観測の不確かさ（±）']:.0%}")
    dthr = st.slider("D がいくつを超えたら「確かめる」に切り替えるか", 0.1, 1.0, 0.5, 0.05, key="sat_dthr")
    if G["D"] > max(dthr, G["観測の不確かさ（±）"]):
        st.warning(f"D = {G['D']:.2f} は、決めた基準（{dthr:.2f}）も観測の不確かさも超えています。"
                   "**すぐに買い増す前に、他の情報源（統計・取引先・公式発表）で確かめる** 合図です。")
    elif G["D"] > dthr:
        st.info("D は基準を超えていますが、観測の不確かさの範囲内です。観測を増やす（週を延ばす）まで判断を保留します。")
    else:
        st.success("言説と観測は、だいたい一致しています。")
    st.markdown(
        "**D が大きい＝誰かがだまそうとしている、ではありません。** 観測の誤差、SARで見えない物（岸壁の中の船・小舟）、"
        "時期のずれ、「船の数」と「積み荷の量」の違いでも D は大きくなります。"
        "D は **立ち止まって確かめるための合図** であり、判断の材料の一つです。"
    )
    st.caption("この「言説と観測のずれ」を数値で持つことは、情報の妥当性を確かめる力（IVCS）を、"
               "手を動かして育てる練習になります。")

# ═════════════════════════════════════════════
# 6. 3層の観測をつなぐ
# ═════════════════════════════════════════════
ROS2_SKETCH = """# ros2 run sat_bridge goal_from_satellite（スケッチ）
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
import satellite_lab as sl

class GoalFromSatellite(Node):
    def __init__(self, p_map, origin_xy, pixel_m=10.0):
        super().__init__("goal_from_satellite")
        self.pub = self.create_publisher(PoseStamped, "goal_pose", 10)   # Nav2 が受け取る目的地
        r0, r1, c0, c1 = sl.best_box(p_map, size=24)                      # いちばん迷っている区域
        self.goal = (origin_xy[0] + (c0 + c1) / 2 * pixel_m,              # 画素 → 圃場の座標（m）
                     origin_xy[1] - (r0 + r1) / 2 * pixel_m)
        self.create_timer(1.0, self.send)

    def send(self):
        msg = PoseStamped()
        msg.header.frame_id = "map"
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.pose.position.x, msg.pose.position.y = self.goal
        msg.pose.orientation.w = 1.0
        self.pub.publish(msg)   # 人が「出発してよい」と確認してから動かす（安全側の設計）
"""

with tab7:
    st.header("❻ 3層の観測をどうつなぐか？：広く・ときどき ／ 狭く・すぐ ／ 点・いま")
    st.write("観測の手段には、**見る範囲の広さ** と **更新の速さ（いまに近いか）** の取り引きがあります。"
             "広く見る衛星は「来た日」しか見えず、いまを伝えるスマホ写真は「その1点」しか見えません。"
             "どれか1つでは足りないので、**3つの層を1枚の地図に重ねます**。")
    st.caption("この「広域 → 区域 → 地点」の階層は、安全保障の情報活動（戦略・戦術・現場）でも同じ形で整理されます。"
               "このページでは、同じ構造を **防災と農業** に使います。")
    st.dataframe(pd.DataFrame(sl.LAYERS, columns=["層", "見る範囲", "更新の速さ", "細かさ", "確かさ",
                                                 "農業・防災での役割", "苦手なこと"]),
                 width="stretch", hide_index=True)
    st.markdown(
        "**つなぎ方（流れ）**　🛰️ 衛星が地域全体で「迷っている所」を見つける → "
        "🚁 ドローン・地上ロボットをそこへ向けて確かめる → 📱 現地の写真で地点を答え合わせ → "
        "🗺️ 1枚の地図（確率）に重ね、次にどこを見るかを決める"
    )
    st.latex(r"\underbrace{\log\frac{p}{1-p}}_{\text{事後（いまの見積もり）}}=\underbrace{\log\frac{p_0}{1-p_0}}"
             r"_{\text{事前（ハザードマップ）}}+\ \lambda_{\text{衛星}}+\lambda_{\text{ドローン}}+\sum\lambda_{\text{スマホ}}")
    st.caption("λ（対数尤度比）＝「その観測は、浸水のときと、浸水でないときで、どちらで起きやすいか」。"
               "ベイズの定理は、オッズの世界では **足し算** になります。")

    st.subheader("① 計算：各層の条件を決める")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**🗺️ 事前（ハザードマップ）**")
        hz = st.slider("ハザードマップの想定水位（m）", 0.5, 3.0, float(max(flood_m - 0.5, 0.5)), 0.25, key="sat_hz",
                       help="本当の水位はサイドバーで決めた値。想定がずれていることもあります。")
        st.markdown("**🛰️ 衛星**")
        lag = st.slider("衛星が来たとき、水位はあと何 m 低かったか", 0.0, 1.5, 0.0, 0.25, key="sat_lag",
                        help="衛星は「来た日」の姿しか見ません。水位が上がりきる前に来ることもあります。")
        w_sat = st.slider("衛星の証拠をどれだけ信じるか", 0.0, 1.0, 1.0, 0.1, key="sat_w",
                          help="古い観測ほど割り引く。0 にすると衛星を使わない。")
    with c2:
        st.markdown("**🚁 ドローン・地上ロボット**")
        dr = st.radio("どこへ向けるか", ["迷っている所", "わたしの圃場", "でたらめな所", "飛ばさない"], key="sat_dr",
                      help="迷っている所＝衛星までの見積もりで、浸水か分からない画素（エントロピーが大きい）がいちばん多い区域。")
        dsize = st.slider("一度に見られる広さ（画素四方）", 10, 40, 24, 2, key="sat_dsize",
                          help="1画素＝10m。24画素四方＝240m四方（電池1本で見られる広さの目安・架空）。")
    with c3:
        st.markdown("**📱 目視・スマホ写真**")
        n_ph = st.slider("集まった報告の数", 0, 100, 30, 5, key="sat_nph")
        trust = st.slider("報告の中身が正しい確率（ふつうは分からない）", 0.5, 0.99, 0.85, 0.05, key="sat_trust")
        stale = st.slider("古い写真・別の場所の写真が混ざる割合", 0.0, 0.6, 0.1, 0.05, key="sat_stale")
        a_trust = st.slider("受け手（自分）がどれだけ信じるか", 0.55, 0.99, 0.85, 0.02, key="sat_atrust")

    sat_day = SC if lag == 0 else sl.make_scene(seed, cloud_cover=cloud, flood_m=max(flood_m - lag, 0.0), looks=looks)
    LY = sl.layered(SC, hz, dr, dsize, n_ph, trust, stale, a_trust, seed, sat_scene=sat_day, sat_weight=w_sat)

    st.subheader("② 可視化：層を重ねるごとに、浸水確率の地図が変わる")
    r0, r1, c0, c1 = SC.my_field
    for (name, pmap), col in zip(LY["maps"].items(), st.columns(4)):
        with col:
            fig = px.imshow(np.where(SC.cls == sl.FARM, pmap, np.nan), color_continuous_scale="Blues", zmin=0, zmax=1,
                            aspect="equal")
            fig.add_shape(type="rect", x0=c0 - .5, x1=c1 - .5, y0=r0 - .5, y1=r1 - .5, line=dict(color=C_MINE, width=2))
            if LY["box"] is not None and name in ("③ ＋ドローン", "④ ＋スマホ"):
                b0, b1, b2, b3 = (int(v) for v in LY["box"])
                fig.add_shape(type="rect", x0=b2 - .5, x1=b3 - .5, y0=b0 - .5, y1=b1 - .5,
                              line=dict(color=PALETTE[3], width=2, dash="dash"))
            if name == "④ ＋スマホ" and not LY["reports"].empty:
                rp = LY["reports"]
                fig.add_scatter(x=rp["列"], y=rp["行"], mode="markers", showlegend=False,
                                marker=dict(symbol=np.where(rp["浸水と報告"], "x", "circle-open").tolist(), size=7,
                                            color=np.where(rp["浸水と報告"], C_FLOOD, "#333").tolist()))
            fig.update_xaxes(showticklabels=False)
            fig.update_yaxes(showticklabels=False)
            plot(fig, 260, title=name, coloraxis_showscale=False)
    c1_, c2_ = st.columns([1, 3])
    with c1_:
        show_img(np.where(SC.cls == sl.FARM, SC.flood.astype(float), np.nan), "正解（ふつうは分からない）",
                 h=260, cmap="Blues", zmin=0, zmax=1, box=SC.my_field, coloraxis_showscale=False)
    with c2_:
        st.caption("濃い青ほど「浸水している確率が高い」。農地だけを表示。🟧＝わたしの圃場、紫の点線＝ドローンの区域、"
                   "✕＝スマホの「浸水」報告、○＝「浸水していない」報告。")
        tab_s = LY["scores"]
        show_cols = [c for c in ["ブライアスコア", "F1", "誤報", "見逃し", "ドローンの区域のブライア",
                                 "わたしの圃場：浸水面積の見積もり(ha)"] if c in tab_s.columns]
        st.dataframe(tab_s[show_cols].round(3), width="stretch")
        st.caption("ブライアスコア＝(確率−正解)² の平均。0 に近いほど良い。"
                   f"わたしの圃場の本当の浸水は **{LY['わたしの圃場：本当の浸水(ha)']:.2f} ha**。")

    with st.expander("やってみよう：4つの実験"):
        st.markdown(
            "1. **衛星が遅れて来る**：「水位はあと何 m 低かったか」を 0.5 にする → ②＋衛星 が ① より **悪くなる**。"
            "衛星は「来た日の乾いた畑」を正しく見ているのに、いまの判断には古い。→「衛星の証拠をどれだけ信じるか」を下げる、"
            "またはドローンを「わたしの圃場」へ向ける。\n"
            "2. **ドローンの向け先**：「迷っている所」と「でたらめな所」で、ドローンの区域のブライアの下がり方を比べる。"
            "**分かっている所を見ても、地図は良くならない**。\n"
            "3. **うわさに強いのはどちら**：古い写真の割合を 0.5、受け手の信じる度合いを 0.97 にする。"
            "衛星を 0（スマホだけ）にしたときと 1 にしたときで、④ がどう変わるか。"
            "**層が重なっていると、まちがった点は打ち消される**。\n"
            "4. **ハザードマップのずれ**：想定水位を本当の水位から大きくずらすと、① はどう外れ、② 以降でどこまで直るか。"
        )

    st.subheader("③ 判断：わたしの圃場で、次に何をするか")
    pm = LY["maps"]["④ ＋スマホ"][r0:r1, c0:c1]
    exp_ha = float(pm.sum() * sl.PIXEL_HA)
    sd_ha = float(np.sqrt((pm * (1 - pm)).sum()) * sl.PIXEL_HA)
    unsure = float(((pm > 0.2) & (pm < 0.8)).mean())
    share = exp_ha / (pm.size * sl.PIXEL_HA) * 100
    m1, m2, m3 = st.columns(3)
    m1.metric("浸水面積の見積もり", f"{exp_ha:.2f} ha", f"±{2 * sd_ha:.2f} ha（画素が独立と仮定）", delta_color="off")
    m2.metric("浸水の割合", f"{share:.0f}%")
    m3.metric("まだ迷っている画素", f"{unsure:.0%}", help="浸水確率が 20〜80% の画素の割合")
    c1_, c2_ = st.columns(2)
    act6 = c1_.slider("何％以上浸かっていそうなら行動するか", 0, 50, 10, 5, key="sat_act6")
    unsure_max = c2_.slider("迷っている画素が何％を超えたら、先に確かめるか", 0, 50, 15, 5, key="sat_uns")
    if unsure * 100 > unsure_max:
        st.warning(f"判定：**先に確かめる**（迷っている画素 {unsure:.0%} > {unsure_max}%）。"
                   "ドローン・地上ロボットを圃場へ向けるか、安全が確保できてから見回る。")
    elif share >= act6:
        st.error(f"判定：**行動する**（浸水の見積もり {share:.0f}% ≥ {act6}%）。排水・播種の延期・共済への連絡の準備。")
    else:
        st.success(f"判定：**見守る**（浸水の見積もり {share:.0f}% < {act6}%）。次の衛星・次の報告で更新する。")
    st.caption("⚠️ 大雨の最中に見回りへ出ない。見回り・ドローンは安全が確保できてから。避難は自治体の情報に従います。")

    with st.expander("🤖 ロボットへつなぐ（ROS2）：衛星の「迷っている所」を巡回の目的地にする"):
        st.write("衛星までの見積もりから「迷っている区域」を選び、その中心を地上ロボットの目的地として渡す流れのスケッチです"
                 "（このアプリの中では動きません。ROS2 と Nav2 がある環境での例・未検証）。")
        st.code(ROS2_SKETCH, language="python")
        st.caption("ロボットが見た結果（浸水かどうか）は、ドローンと同じく λ として地図に足し戻します。"
                   "観測 → 更新 → 次に見る場所を決める、は強化学習の「行動 → 観測 → 更新」と同じ形です。")

    with st.expander("🔒 スマホ写真のセキュリティ：位置情報と出所"):
        st.markdown(
            "- スマホの写真には、撮った **場所（緯度・経度）と日時** が埋め込まれていることがある（Exif）。"
            "投稿すると、家や畑の場所が分かってしまう → **投稿前に位置情報を消す**／共有する相手と範囲を決める\n"
            "- 受け取る側は **撮影日時・場所・同じ写真の再投稿** を確かめる（古い写真・別の場所の写真が混ざる）\n"
            "- 写真もデータも改ざんされうる。受け取った日時・入手先・ハッシュ値を記録して、出所をたどれるようにする\n"
            "- 生成AIで作った画像が混ざることもある。1枚の写真だけで決めず、**別の層（衛星・ドローン）と重ねて** 確かめる"
        )

# ═════════════════════════════════════════════
# 7. マイ判断・実データ
# ═════════════════════════════════════════════
with tab6:
    st.header("📝 マイ判断シート・実データへの一歩")
    st.subheader("落とし穴チェックリスト")
    ck = pd.DataFrame(sl.PITFALLS, columns=["落とし穴", "どう起きるか", "対策", "このページで確かめる場所"])
    ck.insert(0, "確かめた", False)
    ed = st.data_editor(ck, width="stretch", hide_index=True, disabled=list(ck.columns[1:]), key="sat_check")
    st.progress(float(ed["確かめた"].mean()), text=f"{int(ed['確かめた'].sum())} / {len(ed)}")

    st.subheader("マイ・タイムライン：自分の圃場の「デッドライン」")
    c1, c2, c3 = st.columns(3)
    c1.text_input("圃場の場所（地名まで。番地は書かない）", key="sat_place", placeholder="例：三原市大和町")
    c2.number_input("圃場の広さ（ha）", 0.0, 100.0, 0.3, 0.1, key="sat_ha")
    c3.selectbox("いちばん近い水の場所", ["川", "ため池", "水路", "海"], key="sat_near")
    st.text_area("判断と理由（数字を1つ以上入れる）", key="sat_note", height=120,
                 placeholder="例：水位が 2 m 上がると圃場の2割が浸かる（❸）。SARの次の観測は最長12日後なので、"
                             "大雨の予報が出た時点で排水溝を点検し、播種は1週間ずらす。")
    st.caption("この欄の文章はサーバーに保存されません。必要ならコピーして手元に残してください。")

    st.subheader("実データの入手先")
    st.dataframe(pd.DataFrame(sl.SOURCES, columns=["どこで", "何ができるか", "最初の一歩"]),
                 width="stretch", hide_index=True)
    st.link_button("▶ 練習ノートブックを Google Colab で開く", mg.colab_url(NOTEBOOK))
    st.caption("ノートブックは、このページと同じ架空の地図で最後まで動きます。最後の節は、ネットにつながる環境で"
               "Sentinel-2 の実データ（無料の公開データ）を読み込む例です（任意）。")

    with st.expander("次の一歩（研究・ロボット・セキュリティへ）"):
        st.markdown(
            "- **ベイズ推論**：浸水判定を 0/1 ではなく「浸水の確率」で持ち、標高（事前分布）と SAR（観測）を合わせる\n"
            "- **因果AI**：湿害（浸水）が収量をどれだけ下げたかを、区画ごとの前後比較（差の差）で推定する\n"
            "- **深層学習**：U-Net などで水域・圃場の境目を学ぶ（評価は必ず場所で分けて）\n"
            "- **ロボット（ROS2）**：NDVI の低い区画だけを巡回する経路を、圃場ロボットに渡す\n"
            "- **サイバーセキュリティ**：衛星画像も「改ざんされうるデータ」。入手先・日付・ハッシュ値を記録して出所を確かめる"
        )
    st.caption(f"参考：{BOOKS}。本ページの文章・データ・計算はこのアプリ独自のもので、書籍の内容の転載ではありません。")

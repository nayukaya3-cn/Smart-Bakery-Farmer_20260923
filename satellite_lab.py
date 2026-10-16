"""
探究コーナー「🛰️ 衛星データ解析（Python実装）」の計算部品。
pages/14_🛰️_衛星データ解析.py から呼び出します。画面を持たない純粋な関数だけを置き、
`python satellite_lab.py` で自己チェックできます（numpy・pandas だけで動きます）。

下敷きにした考え方（文章・データ・コードはこのアプリ独自のもので、書籍の転載ではありません）
  - 安井秀輔・佐藤功一・藤原寛朗『SAR衛星データ解析入門』（講談社 KS情報科学専門書）
      後方散乱とdB／スペックル／水域検出／農業利用／変化（災害）検知／船舶検知
  - 田中康平・田村賢哉・玉置慎吾 著、宮﨑浩之 監修『Pythonで学ぶ衛星データ解析基礎』
      バンド演算（NDVI など）／農業での利用／教師あり・教師なし学習
  - 衛星データプラットフォーム Tellus（実データの入手先の一つとして紹介）

ここにあるデータはすべて **架空**（三原の小麦畑と川沿いを想定して作った地図）です。実測ではありません。
1画素＝10m×10m（0.01ha）として面積を数えます。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

PIXEL_HA = 0.01  # 10m × 10m
CLASSES = ["水域", "森林", "農地", "建物・道路"]
WATER, FOREST, FARM, URBAN = range(4)
BANDS = ["青", "緑", "赤", "近赤外", "短波長赤外"]

# 光学の反射率（0〜1）の目安：青・緑・赤・近赤外・短波長赤外
REFLECT = {
    WATER: (0.06, 0.07, 0.05, 0.03, 0.01),
    FOREST: (0.03, 0.06, 0.04, 0.35, 0.15),
    URBAN: (0.12, 0.13, 0.14, 0.20, 0.22),
}
VEG = np.array([0.04, 0.08, 0.05, 0.38, 0.18])   # 育っている麦
SOIL = np.array([0.08, 0.11, 0.14, 0.22, 0.30])  # 耕したばかりの土
# SAR（VV偏波）の後方散乱係数 σ0 の目安 [dB]
SAR_DB = {WATER: -22.0, FOREST: -8.0, FARM: -14.0, URBAN: -2.0}


# ─────────────────────────────────────────────
# 基本の計算
# ─────────────────────────────────────────────
def to_db(x: np.ndarray) -> np.ndarray:
    """後方散乱（真数）→ dB。0 は小さな数に置き換える。"""
    return 10 * np.log10(np.maximum(x, 1e-6))


def from_db(d: np.ndarray) -> np.ndarray:
    return 10 ** (np.asarray(d) / 10)


def ndvi(red: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """正規化植生指数：(近赤外−赤)/(近赤外+赤)。植物が元気なほど 1 に近い。"""
    return (nir - red) / np.maximum(nir + red, 1e-6)


def ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """正規化水指数（McFeeters）：(緑−近赤外)/(緑+近赤外)。水は正になりやすい。"""
    return (green - nir) / np.maximum(green + nir, 1e-6)


def box_mean(img: np.ndarray, r: int) -> np.ndarray:
    """一辺 2r+1 の窓の平均（端は折り返し）。累積和で速く計算する。"""
    if r <= 0:
        return img.astype(float).copy()
    p = np.pad(img.astype(float), r, mode="reflect")
    c = np.cumsum(np.cumsum(p, 0), 1)
    c = np.pad(c, ((1, 0), (1, 0)))
    k = 2 * r + 1
    s = c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]
    return s / (k * k)


def speckle(sigma0_lin: np.ndarray, looks: int, rng: np.random.Generator) -> np.ndarray:
    """SAR特有のザラザラ（スペックル）：真の値に、平均1のガンマ乱数を掛ける（掛け算の雑音）。"""
    return sigma0_lin * rng.gamma(looks, 1.0 / looks, size=sigma0_lin.shape)


def lee_filter(intensity: np.ndarray, r: int = 2, looks: int = 1) -> np.ndarray:
    """Lee フィルタ：平らな所はならし、境目（川岸・建物）は残す。強度（真数）で計算する。"""
    m = box_mean(intensity, r)
    v = box_mean(intensity ** 2, r) - m ** 2
    cu2 = 1.0 / looks
    var_x = np.maximum((v - m ** 2 * cu2) / (1 + cu2), 0)
    k = var_x / np.maximum(var_x + m ** 2 * cu2, 1e-12)
    return m + k * (intensity - m)


def otsu(values: np.ndarray, bins: int = 256) -> float:
    """大津の方法：2つの山の間で、クラス間分散が最大になる閾値。"""
    v = np.asarray(values, float)
    v = v[np.isfinite(v)]
    hist, edges = np.histogram(v, bins=bins)
    mids = (edges[:-1] + edges[1:]) / 2
    w = hist / hist.sum()
    w0 = np.cumsum(w)
    mu = np.cumsum(w * mids)
    mu_t = mu[-1]
    w1 = 1 - w0
    with np.errstate(divide="ignore", invalid="ignore"):
        between = (mu_t * w0 - mu) ** 2 / (w0 * w1)
    between[~np.isfinite(between)] = -1
    return float(mids[int(np.argmax(between))])


def water_threshold(db: np.ndarray) -> float:
    """水の閾値を大津の方法で2段階に決める。
    水は面積が小さいので、1回目は「暗い所／明るい所（建物・森）」で分かれてしまう。
    そこで暗い側だけをもう一度2つに分け、「水／農地」の境目を探す。"""
    t1 = otsu(db)
    return otsu(db[db < t1])


def scores(truth: np.ndarray, pred: np.ndarray) -> dict:
    """2値の地図どうしの答え合わせ。"""
    t, p = truth.astype(bool).ravel(), pred.astype(bool).ravel()
    tp, fp, fn = int((t & p).sum()), int((~t & p).sum()), int((t & ~p).sum())
    tn = t.size - tp - fp - fn
    rec = tp / max(tp + fn, 1)
    pre = tp / max(tp + fp, 1)
    return {"見つけた": tp, "誤報": fp, "見逃し": fn, "正しく陰性": tn,
            "再現率": rec, "適合率": pre, "F1": 2 * rec * pre / max(rec + pre, 1e-9),
            "IoU": tp / max(tp + fp + fn, 1), "正解率": (tp + tn) / t.size}


# ─────────────────────────────────────────────
# 架空の地図：三原の小麦畑と川沿い
# ─────────────────────────────────────────────
@dataclass
class Scene:
    cls: np.ndarray        # 土地の種類（0〜3）
    elev: np.ndarray       # 標高 [m]（川からの高さ）
    green: np.ndarray      # 農地の緑の割合（0〜1）
    optical: np.ndarray    # (5, H, W) 反射率
    cloud: np.ndarray      # 雲のある画素
    sar_before: np.ndarray  # 強度（真数・スペックル入り）
    sar_after: np.ndarray   # 大雨のあと
    flood: np.ndarray       # 大雨で新しく水に浸かった画素（正解）
    my_field: tuple        # わたしの圃場 (行0, 行1, 列0, 列1)
    looks: int


def _blob(shape, rng, smooth: int = 6) -> np.ndarray:
    z = rng.normal(size=shape)
    for _ in range(3):
        z = box_mean(z, smooth)
    return (z - z.mean()) / (z.std() + 1e-9)


def make_scene(seed: int = 0, size: int = 100, cloud_cover: float = 0.0, flood_m: float = 1.5,
               looks: int = 1) -> Scene:
    """架空の地図をつくる。flood_m は大雨で川の水位がどれだけ上がるか（m）の想定。"""
    rng = np.random.default_rng(seed)
    H = W = size
    yy, xx = np.mgrid[0:H, 0:W]
    # 川：左上から右下へ曲がりながら流れる
    center = 0.55 * W + 0.12 * W * np.sin(yy / H * 3.0)
    dist = np.abs(xx - center)
    cls = np.full((H, W), FARM)
    forest = (_blob((H, W), rng, 8) + (W * 0.35 - xx) / (W * 0.25) + (H * 0.35 - yy) / (H * 0.3)) > 1.2
    cls[forest] = FOREST
    urban = (xx > 0.80 * W) & (yy > 0.62 * H)
    road = (np.abs(yy - 0.85 * H) < 1.2) | (np.abs(xx - 0.25 * W) < 0.8)
    cls[urban | road] = URBAN
    pond = (yy - 0.25 * H) ** 2 + (xx - 0.80 * W) ** 2 < (0.07 * W) ** 2
    river = dist < 3.0
    cls[river | pond] = WATER
    # 標高：川から離れるほど高い（なだらか）＋ゆらぎ
    elev = 0.12 * np.maximum(dist - 3, 0) + 0.6 * _blob((H, W), rng, 5) + 0.3
    elev[cls == WATER] = 0
    elev[forest] += 3
    # 農地は 10画素四方の区画ごとに生育が違う
    green = np.zeros((H, W))
    pg = rng.uniform(0.15, 1.0, size=(H // 10 + 1, W // 10 + 1))
    green = pg[yy // 10, xx // 10] * (cls == FARM)
    # 光学
    opt = np.zeros((5, H, W))
    for c, ref in REFLECT.items():
        opt[:, cls == c] = np.array(ref)[:, None]
    g = green[cls == FARM]
    opt[:, cls == FARM] = (np.outer(VEG, g) + np.outer(SOIL, 1 - g))
    opt *= 1 + 0.06 * rng.normal(size=opt.shape)
    opt += 0.004 * rng.normal(size=opt.shape)
    cloud = np.zeros((H, W), bool)
    if cloud_cover > 0:
        cb = _blob((H, W), rng, 10)
        cloud = cb > np.quantile(cb, 1 - cloud_cover)
        opt[:, cloud] = 0.40 + 0.03 * rng.normal(size=(5, int(cloud.sum())))
    opt = np.clip(opt, 0.001, 1)
    # SAR（雲を通り抜ける）
    db = np.zeros((H, W))
    for c, v in SAR_DB.items():
        db[cls == c] = v
    db[cls == FARM] += 2.0 * (green[cls == FARM] - 0.5)  # 葉が多いほど少し強い
    db += 0.8 * _blob((H, W), rng, 3)
    before = speckle(from_db(db), looks, rng)
    flood = (cls == FARM) & (elev < flood_m)
    db_after = db.copy()
    db_after[cls == FARM] += 1.5          # 雨で土が湿ると少し明るくなる
    db_after[flood] = SAR_DB[WATER] + 1.0  # 水面は鏡のように電波をはね返して暗い
    after = speckle(from_db(db_after), looks, rng)
    my = (int(0.55 * H), int(0.70 * H), int(0.36 * W), int(0.50 * W))
    return Scene(cls, elev, green, opt, cloud, before, after, flood, my, looks)


def water_map(intensity: np.ndarray, thr_db: float, r: int = 2, looks: int = 1) -> np.ndarray:
    """フィルタをかけた dB 画像で、閾値より暗い所を水とみなす。"""
    return to_db(lee_filter(intensity, r, looks)) < thr_db


def change_map(before: np.ndarray, after: np.ndarray, thr_drop_db: float, water_thr_db: float,
               r: int = 2, looks: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """対数比（dB の差）：after−before が大きく下がり、かつ after が水の暗さなら「新しく浸水」。"""
    b = to_db(lee_filter(before, r, looks))
    a = to_db(lee_filter(after, r, looks))
    diff = a - b
    return diff, (diff < -abs(thr_drop_db)) & (a < water_thr_db)


def crop(mask: np.ndarray, box: tuple) -> np.ndarray:
    r0, r1, c0, c1 = box
    return mask[r0:r1, c0:c1]


# ─────────────────────────────────────────────
# 時系列：小麦のNDVI（光学は雲で欠ける）と SAR の VH
# ─────────────────────────────────────────────
SOW = date(2026, 10, 20)


def wheat_ndvi(d: np.ndarray) -> np.ndarray:
    """播種からの日数 → 小麦のNDVI（二つのロジスティック曲線の和で近似した架空の曲線）。"""
    up1 = 0.30 / (1 + np.exp(-(d - 30) / 6))     # 発芽・分げつ
    up2 = 0.40 / (1 + np.exp(-(d - 165) / 10))   # 春の茎立ち〜出穂
    down = 0.65 / (1 + np.exp(-(d - 215) / 7))   # 登熟〜枯れ上がり
    return 0.15 + up1 + up2 - down


def cloud_prob(m: int) -> float:
    """月ごとの「光学で地面が見えない」確率の目安（架空。梅雨は高い）。"""
    return {10: .35, 11: .35, 12: .40, 1: .45, 2: .45, 3: .45, 4: .45, 5: .45, 6: .75, 7: .55}.get(m, .45)


def season(seed: int = 0, optical_every: int = 5, sar_every: int = 12, stress_day: int | None = None) -> pd.DataFrame:
    """播種〜収穫の日ごとの表。stress_day を入れると、その日から生育が鈍る（湿害などの想定）。"""
    rng = np.random.default_rng(seed)
    days = np.arange(0, 240)
    dates = [SOW + timedelta(int(x)) for x in days]
    true = wheat_ndvi(days.astype(float))
    if stress_day is not None:
        lag = np.clip(days - stress_day, 0, None)
        true = true - 0.25 * (1 - np.exp(-lag / 20)) * (true - 0.15)
    df = pd.DataFrame({"日付": pd.to_datetime(dates), "播種からの日数": days, "NDVI（真の値）": true})
    opt = np.full(len(days), np.nan)
    for i in range(0, len(days), optical_every):
        if rng.random() > cloud_prob(dates[i].month):
            opt[i] = true[i] + rng.normal(0, 0.02)
    sar = np.full(len(days), np.nan)
    for i in range(0, len(days), sar_every):
        sar[i] = -22 + 9 * (true[i] - 0.15) / 0.7 + rng.normal(0, 0.6)
    df["NDVI（光学で見えた日）"] = opt
    df["VH後方散乱 dB（SAR）"] = sar
    return df


def longest_gap(observed: pd.Series) -> int:
    """観測と観測のあいだで、いちばん長く空いた日数。"""
    idx = np.flatnonzero(observed.notna().to_numpy())
    return int(np.diff(idx).max()) if len(idx) > 1 else len(observed)


# ─────────────────────────────────────────────
# 分類：教師なし（k-means）と教師あり（ガウス型ナイーブベイズ）
# ─────────────────────────────────────────────
def features(sc: Scene) -> pd.DataFrame:
    o = sc.optical
    f = {b: o[i].ravel() for i, b in enumerate(BANDS)}
    f["NDVI"] = ndvi(o[2], o[3]).ravel()
    f["NDWI"] = ndwi(o[1], o[3]).ravel()
    f["VV dB（ならし後）"] = to_db(lee_filter(sc.sar_before, 2, sc.looks)).ravel()
    return pd.DataFrame(f)


def kmeans(X: np.ndarray, k: int, seed: int = 0, iters: int = 50) -> np.ndarray:
    rng = np.random.default_rng(seed)
    Z = (X - X.mean(0)) / (X.std(0) + 1e-9)
    C = Z[rng.choice(len(Z), 1)]
    for _ in range(1, k):  # k-means++ の初期値
        d = ((Z[:, None, :] - C[None]) ** 2).sum(-1).min(1)
        C = np.vstack([C, Z[rng.choice(len(Z), p=d / d.sum())]])
    lab = np.zeros(len(Z), int)
    for _ in range(iters):
        lab = ((Z[:, None, :] - C[None]) ** 2).sum(-1).argmin(1)
        newC = np.array([Z[lab == j].mean(0) if (lab == j).any() else C[j] for j in range(k)])
        if np.allclose(newC, C):
            break
        C = newC
    return lab


def name_clusters(lab: np.ndarray, truth: np.ndarray) -> np.ndarray:
    """教師なしの「グループ番号」に、あとから人が名前をつける（いちばん多い正解の名前）。"""
    out = np.zeros_like(truth)
    for j in np.unique(lab):
        vals, cnt = np.unique(truth[lab == j], return_counts=True)
        out[lab == j] = vals[cnt.argmax()]
    return out


class GaussianNB:
    def fit(self, X: np.ndarray, y: np.ndarray):
        self.classes = np.unique(y)
        self.mu = np.array([X[y == c].mean(0) for c in self.classes])
        self.var = np.array([X[y == c].var(0) + 1e-6 for c in self.classes])
        self.prior = np.array([(y == c).mean() for c in self.classes])
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        ll = -0.5 * (((X[:, None, :] - self.mu[None]) ** 2) / self.var[None] + np.log(2 * np.pi * self.var[None])).sum(-1)
        return self.classes[(ll + np.log(self.prior)[None]).argmax(1)]


def split_masks(H: int, W: int, how: str, seed: int = 0, frac: float = 0.5, block: int = 20,
                cls: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """学習用とテスト用の分け方。
    "ランダム"：1画素ずつくじで分ける → ほぼ同じ隣の画素が学習とテストの両方に入る。
    "場所で分ける"：block 画素四方の区画ごとにくじで分ける（区画の中は同じ側）。"""
    rng = np.random.default_rng(seed)
    if how == "ランダム":
        tr = rng.random((H, W)) < frac
    else:
        nb_r, nb_c = -(-H // block), -(-W // block)
        for _ in range(50):  # どの種類も学習・テストの両方に入るまで引き直す
            blk = rng.random((nb_r, nb_c)) < frac
            tr = np.kron(blk, np.ones((block, block), bool))[:H, :W]
            if cls is None or all((cls[tr] == c).any() and (cls[~tr] == c).any() for c in np.unique(cls)):
                break
    return tr.ravel(), ~tr.ravel()


def confusion(y: np.ndarray, p: np.ndarray, k: int = 4) -> pd.DataFrame:
    m = np.zeros((k, k), int)
    np.add.at(m, (y, p), 1)
    return pd.DataFrame(m, index=[f"正解：{c}" for c in CLASSES[:k]], columns=[f"予測：{c}" for c in CLASSES[:k]])


def classify(sc: Scene, cols: list[str], how: str = "場所で分ける", seed: int = 0,
             n_train: int = 400) -> dict:
    """教師あり（少ない教師データ）と教師なしを、同じテスト画素で答え合わせする。"""
    F = features(sc)
    X = F[cols].to_numpy()
    y = sc.cls.ravel()
    H, W = sc.cls.shape
    tr, te = split_masks(H, W, how, seed, cls=sc.cls)
    rng = np.random.default_rng(seed)
    tr_idx = np.flatnonzero(tr)
    # 教師データは「人が地図に点を打つ」想定で、各種類から同じくらいずつ集める
    pick = np.concatenate([rng.choice(tr_idx[y[tr_idx] == c], min(n_train // 4, int((y[tr_idx] == c).sum())),
                                      replace=False) for c in range(4) if (y[tr_idx] == c).any()])
    nb = GaussianNB().fit(X[pick], y[pick])
    p_nb = nb.predict(X)
    km = kmeans(X, 4, seed)
    p_km = name_clusters(km[tr], y[tr])
    p_km_full = np.zeros_like(y)
    for j in np.unique(km):  # 名前は学習側でつけ、テスト側にはそのまま当てる
        in_tr = tr & (km == j)
        if in_tr.any():
            vals, cnt = np.unique(y[in_tr], return_counts=True)
            p_km_full[km == j] = vals[cnt.argmax()]
    _ = p_km
    acc = lambda p: float((p[te] == y[te]).mean())  # noqa: E731
    return {"教師あり（ナイーブベイズ）": p_nb.reshape(H, W), "教師なし（k-means→名前づけ）": p_km_full.reshape(H, W),
            "正解率": {"教師あり（ナイーブベイズ）": acc(p_nb), "教師なし（k-means→名前づけ）": acc(p_km_full)},
            "混同行列": confusion(y[te], p_nb[te]), "テスト": te.reshape(H, W), "教師データ": pick}


def leak_gap(sc: Scene, cols: list[str], seed: int = 0) -> dict:
    """分け方による正解率の違い：ランダムに分けると、隣の画素が答えを教えてしまい高く出やすい。"""
    return {how: classify(sc, cols, how, seed, n_train=4000)["正解率"]["教師あり（ナイーブベイズ）"]
            for how in ["ランダム", "場所で分ける"]}


# ─────────────────────────────────────────────
# 船の検出（CFAR）と、言説と観測の比較
# ─────────────────────────────────────────────
def port_scene(n_ships: int, seed: int = 0, wind: float = 0.3, H: int = 80, W: int = 120,
               looks: int = 1) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """架空の港の沖：上の帯が陸。船は 2×4 画素の明るい点。wind が強いと海面が明るくザラつく。"""
    rng = np.random.default_rng(seed)
    land = np.zeros((H, W), bool)
    land[:12] = True
    db = np.full((H, W), -22.0 + 8 * wind) + 1.0 * _blob((H, W), rng, 4) * (0.5 + wind)
    db[land] = -3 + 2 * rng.normal(size=int(land.sum()))
    truth = np.zeros((H, W), bool)
    placed = 0
    tries = 0
    while placed < n_ships and tries < 2000:
        tries += 1
        r, c = rng.integers(16, H - 4), rng.integers(2, W - 6)
        if truth[r - 3:r + 5, c - 3:c + 7].any():
            continue
        db[r:r + 2, c:c + 4] = rng.uniform(-2, 6)
        truth[r:r + 2, c:c + 4] = True
        placed += 1
    inten = speckle(from_db(db), looks, rng)
    return inten, truth, land


def cfar(intensity: np.ndarray, land: np.ndarray, pfa: float = 1e-4, guard: int = 3, train: int = 8,
         looks: int = 1) -> np.ndarray:
    """CA-CFAR：周りの海（ガード帯の外）の平均より何倍明るいかで判定。誤報率 pfa を一定に保つ。"""
    a = 2 * (guard + train) + 1
    b = 2 * guard + 1
    s_out = box_mean(intensity, guard + train) * a * a
    s_in = box_mean(intensity, guard) * b * b
    n = a * a - b * b
    bg = (s_out - s_in) / n
    # 指数分布（1ルック）のとき：倍率 α = N(pfa^(-1/N) − 1)。ルック数が多いほど控えめでよい
    alpha = n * (pfa ** (-1.0 / n) - 1) / max(np.sqrt(looks), 1)
    return (intensity > alpha * bg) & ~land


def components(mask: np.ndarray, min_size: int = 2) -> list[tuple[float, float, int]]:
    """つながっている画素を1つの物体として数える（8近傍）。(行の中心, 列の中心, 画素数)。"""
    H, W = mask.shape
    seen = np.zeros_like(mask, bool)
    out = []
    for r0, c0 in zip(*np.nonzero(mask)):
        if seen[r0, c0]:
            continue
        stack, pts = [(r0, c0)], []
        seen[r0, c0] = True
        while stack:
            r, c = stack.pop()
            pts.append((r, c))
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < H and 0 <= cc < W and mask[rr, cc] and not seen[rr, cc]:
                        seen[rr, cc] = True
                        stack.append((rr, cc))
        if len(pts) >= min_size:
            p = np.array(pts)
            out.append((float(p[:, 0].mean()), float(p[:, 1].mean()), len(pts)))
    return out


def match_ships(found: list, truth: np.ndarray) -> dict:
    """見つけた物体の中心が本物の船の上（±1画素）にあれば当たり。"""
    tl = components(truth, 1)
    hit_true = set()
    tp = 0
    for r, c, _ in found:
        for j, (tr, tc, _) in enumerate(tl):
            if j not in hit_true and abs(r - tr) <= 2 and abs(c - tc) <= 3:
                hit_true.add(j)
                tp += 1
                break
    return {"本物の船": len(tl), "検出": len(found), "当たり": tp, "誤報": len(found) - tp,
            "見逃し": len(tl) - tp}


def weekly_port(weeks: int = 12, base: float = 20.0, real_drop: float = 0.20, claim_drop: float = 0.80,
                change_week: int = 7, seed: int = 0, wind: float = 0.3, pfa: float = 1e-4) -> pd.DataFrame:
    """週ごとの港。実際の船は change_week から real_drop だけ減る。言説は claim_drop 減ったと語る。
    SAR で数えた隻数と並べる（風の強い週は海が荒れて誤報が増える）。"""
    rng = np.random.default_rng(seed)
    rows = []
    for w in range(1, weeks + 1):
        lam = base * (1 - real_drop if w >= change_week else 1)
        n = int(rng.poisson(lam))
        wnd = float(np.clip(wind + rng.normal(0, 0.15), 0, 1))
        inten, truth, land = port_scene(n, seed=seed * 100 + w, wind=wnd)
        found = components(cfar(inten, land, pfa))
        claim = base * (1 - claim_drop if w >= change_week else 1)
        rows.append({"週": w, "本物の隻数（ふつうは分からない）": n, "SARで数えた隻数": len(found),
                     "言説が示す隻数": claim, "海の荒れ（風）": round(wnd, 2)})
    return pd.DataFrame(rows)


def gap_index(df: pd.DataFrame, change_week: int, obs_col: str = "SARで数えた隻数",
              claim_col: str = "言説が示す隻数") -> dict:
    """乖離指標 D：言説が示す変化率と、観測が示す変化率の差（0〜。0なら一致）。
    D が大きいことは「言説を鵜呑みにせず、確かめよう」という合図であって、誰かの意図の証明ではない。"""
    pre, post = df[df["週"] < change_week], df[df["週"] >= change_week]
    d_obs = post[obs_col].mean() / max(pre[obs_col].mean(), 1e-9) - 1
    d_claim = post[claim_col].mean() / max(pre[claim_col].mean(), 1e-9) - 1
    # 観測のばらつき（変化前の週の標準誤差）も添える：差がこれより小さければ「区別できない」
    se = float(np.sqrt(pre[obs_col].var(ddof=1) / max(len(pre), 1) + post[obs_col].var(ddof=1) / max(len(post), 1))
               / max(pre[obs_col].mean(), 1e-9))
    return {"観測の変化率": float(d_obs), "言説の変化率": float(d_claim), "D": float(abs(d_claim - d_obs)),
            "観測の不確かさ（±）": 2 * se}


# ─────────────────────────────────────────────
# 3層の観測をつなぐ：衛星（広域）→ ドローン・地上ロボット（圃場）→ 目視・スマホ（地点）
#   ベイズの定理で、浸水の確率を1枚の地図に重ねていく（対数オッズの足し算）
# ─────────────────────────────────────────────
LAYERS = [
    # 層, 見る範囲, 更新の速さ, 細かさ, 確かさ, 農業・防災での役割, 苦手なこと
    ("🛰️ 衛星（広域）", "市町村〜県（数十km）", "数日〜2週間に1回（来る日だけ）", "10m前後", "中（ならせば安定）",
     "地域全体の浸水・生育の様子をつかむ／どこを詳しく見るか決める", "細かい所・来ない日・雲（光学）"),
    ("🚁 ドローン・地上ロボット（圃場）", "圃場〜集落（数百m〜数km）", "数時間〜1日（飛ばせばすぐ）", "数cm", "高",
     "衛星が気になった所を、細かく確かめる／排水の詰まり・倒伏の場所", "広い範囲・強風や大雨の最中・電池"),
    ("📱 目視・スマホ写真（地点）", "1点（その人のいる所）", "数分（いま起きていること）", "その場所だけ", "ばらつく（古い写真・場所違い）",
     "いま・ここの様子／衛星やドローンの答え合わせ", "全体が分からない・まちがった投稿・位置情報の扱い"),
]


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def sigmoid(z: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-z))


def prior_from_elev(elev: np.ndarray, level_m: float, scale: float = 0.4) -> np.ndarray:
    """事前確率：標高が想定水位より低いほど浸水しやすい（ハザードマップに相当）。"""
    return sigmoid((level_m - elev) / scale)


def sar_llr(diff_db: np.ndarray, mu_f: float = -9.0, sd_f: float = 3.0, mu_n: float = 0.5, sd_n: float = 1.8) -> np.ndarray:
    """衛星の証拠：前後の差 Δ が「浸水なら −9±3 dB、浸水でなければ +0.5±1.8 dB」と仮定した対数尤度比。"""
    lf = -0.5 * ((diff_db - mu_f) / sd_f) ** 2 - np.log(sd_f)
    ln = -0.5 * ((diff_db - mu_n) / sd_n) ** 2 - np.log(sd_n)
    return np.clip(lf - ln, -8, 8)


def best_box(p: np.ndarray, size: int) -> tuple[int, int, int, int]:
    """いちばん「迷っている」（エントロピーが大きい）四角い区域を探す＝ドローンを飛ばす場所。"""
    q = np.clip(p, 1e-6, 1 - 1e-6)
    ent = -(q * np.log2(q) + (1 - q) * np.log2(1 - q))
    m = box_mean(ent, size // 2)
    H, W = p.shape
    h = size // 2
    m[:h, :] = m[H - h:, :] = -1
    m[:, :h] = m[:, W - h:] = -1
    r, c = np.unravel_index(int(np.argmax(m)), m.shape)
    return (r - h, r - h + size, c - h, c - h + size)


def drone_llr(truth: np.ndarray, box: tuple | None, acc: float = 0.97, seed: int = 0) -> np.ndarray:
    """ドローン：区域の中だけ、確かさ acc で浸水かどうかを見分ける。"""
    out = np.zeros(truth.shape)
    if box is None:
        return out
    rng = np.random.default_rng(seed)
    r0, r1, c0, c1 = box
    t = truth[r0:r1, c0:c1]
    obs = np.where(rng.random(t.shape) < acc, t, ~t)
    w = np.log(acc / (1 - acc))
    out[r0:r1, c0:c1] = np.where(obs, w, -w)
    return out


def phone_reports(truth: np.ndarray, n: int, trust: float = 0.85, stale: float = 0.1, seed: int = 0) -> pd.DataFrame:
    """スマホ写真の報告。trust：内容が正しい確率。stale：古い写真・別の場所の写真が混ざる割合（いつも「浸水」と言う）。"""
    rng = np.random.default_rng(seed)
    H, W = truth.shape
    rows = []
    dry = np.argwhere(~truth)
    for _ in range(n):
        r, c = int(rng.integers(0, H)), int(rng.integers(0, W))
        if rng.random() < stale and len(dry):
            # 古い写真・別の場所の写真が「ここが浸水」として広まる（実際は乾いている場所）
            r, c = (int(v) for v in dry[rng.integers(0, len(dry))])
            says, kind = True, "古い・別の場所の写真"
        else:
            correct = rng.random() < trust
            says, kind = (bool(truth[r, c]) if correct else not truth[r, c]), ("正しい報告" if correct else "見まちがい")
        rows.append({"行": r, "列": c, "浸水と報告": says, "中身（ふつうは分からない）": kind})
    return pd.DataFrame(rows, columns=["行", "列", "浸水と報告", "中身（ふつうは分からない）"])


def phone_llr(reports: pd.DataFrame, shape: tuple, trust: float = 0.85, radius: float = 3.0) -> np.ndarray:
    """報告1件は、その地点のまわり（半径 radius 画素）に、離れるほど弱まる証拠として効く。
    受け手は trust（どれくらい信じるか）を自分で決める。"""
    out = np.zeros(shape)
    if reports.empty:
        return out
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    w = np.log(trust / (1 - trust))
    for r, c, says in reports[["行", "列", "浸水と報告"]].itertuples(index=False):
        k = np.exp(-((yy - r) ** 2 + (xx - c) ** 2) / (2 * radius ** 2))
        out += (w if says else -w) * k
    return out


def fuse(prior: np.ndarray, *llrs: np.ndarray) -> np.ndarray:
    """ベイズの定理（対数オッズ版）：事後の対数オッズ ＝ 事前の対数オッズ ＋ 証拠の対数尤度比の和。"""
    z = logit(prior)
    for l in llrs:
        z = z + l
    return sigmoid(z)


def prob_scores(truth: np.ndarray, p: np.ndarray, mask: np.ndarray | None = None) -> dict:
    """確率の地図の答え合わせ：ブライアスコア（小さいほど良い）と、0.5で切ったときの F1。"""
    t, q = truth.astype(float), p
    if mask is not None:
        t, q = t[mask], q[mask]
    s = scores(t > 0.5, q > 0.5)
    return {"ブライアスコア": float(((q - t) ** 2).mean()), "F1": s["F1"], "誤報": s["誤報"], "見逃し": s["見逃し"]}


def layered(sc: "Scene", level_m: float, drone: str = "迷っている所", drone_size: int = 24, n_phone: int = 30,
            trust: float = 0.85, stale: float = 0.1, assumed_trust: float = 0.85, seed: int = 0,
            sat_scene: "Scene | None" = None, sat_weight: float = 1.0) -> dict:
    """3層を順に重ねたときの、浸水確率の地図と答え合わせ。対象は農地（もともとの水・建物・森は除く）。
    level_m：ハザードマップが想定する水位（事前）。
    sat_scene：衛星が来た日の地図（水位が上がりきる前に来た場合など。省略すると sc と同じ日）。
    衛星は「来た日」の姿しか見ない。
    sat_weight：衛星の証拠をどれだけ信じるか（0〜1）。古い観測ほど割り引く。"""
    farm = sc.cls == FARM
    prior = prior_from_elev(box_mean(sc.elev, 5), level_m)  # ハザードマップは粗い（標高をならしたもの）
    sat = sc if sat_scene is None else sat_scene
    diff, _ = change_map(sat.sar_before, sat.sar_after, 3, -15, 2, sat.looks)
    l_sat = sat_weight * sar_llr(diff)
    p_sat = fuse(prior, l_sat)
    if drone == "迷っている所":
        box = best_box(np.where(farm, p_sat, 0.0), drone_size)
    elif drone == "わたしの圃場":
        r0, r1, c0, c1 = sc.my_field
        box = (r0, r1, c0, c1)
    elif drone == "でたらめな所":
        rng = np.random.default_rng(seed + 7)
        H, W = sc.cls.shape
        r, c = int(rng.integers(0, H - drone_size)), int(rng.integers(0, W - drone_size))
        box = (r, r + drone_size, c, c + drone_size)
    else:
        box = None
    l_dr = drone_llr(sc.flood, box, seed=seed)
    rep = phone_reports(sc.flood | (sc.cls == WATER), n_phone, trust, stale, seed)
    rep = rep[farm[rep["行"], rep["列"]] | rep["浸水と報告"]]
    l_ph = phone_llr(rep, sc.cls.shape, assumed_trust)
    maps = {"① 標高だけ（事前）": prior, "② ＋衛星": p_sat, "③ ＋ドローン": fuse(prior, l_sat, l_dr),
            "④ ＋スマホ": fuse(prior, l_sat, l_dr, l_ph)}
    tab = pd.DataFrame({k: prob_scores(sc.flood, v, farm) for k, v in maps.items()}).T
    if box is not None:
        inbox = np.zeros_like(farm)
        inbox[box[0]:box[1], box[2]:box[3]] = True
        tab["ドローンの区域のブライア"] = [prob_scores(sc.flood, v, farm & inbox)["ブライアスコア"] for v in maps.values()]
    mine = np.zeros_like(farm)
    r0, r1, c0, c1 = sc.my_field
    mine[r0:r1, c0:c1] = True
    tab["わたしの圃場：浸水面積の見積もり(ha)"] = [float(v[mine].sum() * PIXEL_HA) for v in maps.values()]
    return {"maps": maps, "scores": tab, "box": box, "reports": rep,
            "わたしの圃場：本当の浸水(ha)": float(sc.flood[mine].sum() * PIXEL_HA)}


# ─────────────────────────────────────────────
# チェックリスト・入手先
# ─────────────────────────────────────────────
PITFALLS = [
    ("雲の日を『植物がない日』と読む", "光学は雲を通らない。雲は白く、NDVI が低く出る", "雲マスクで除く／SARで補う", "❶ 光学"),
    ("SARの暗い所をすべて水と思う", "道路・アスファルト・電波の影（山の裏）も暗い", "標高・地図と重ねる／浸水前と比べる", "❷ SAR・❸ 変化"),
    ("スペックルのまま閾値を引く", "1画素ずつの判定はザラつきで誤報だらけになる", "Lee フィルタなどでならしてから", "❷ SAR"),
    ("1枚の画像だけで『浸水』と言う", "もともと水の所も数えてしまう", "前後の2枚の差（対数比）で、新しく水になった所だけ", "❸ 変化"),
    ("隣の画素で答え合わせする", "ランダムに分けると、ほぼ同じ隣の画素が答えを教え、正解率が高く出ることがある（空間の自己相関）", "場所で分けて学習・テストする", "❹ 分類"),
    ("教師なしの結果に勝手に名前をつけて終わる", "グループは数字。名前は人が正解と照らしてつける", "名前づけを学習側だけで行い、テストで評価", "❹ 分類"),
    ("船の数＝積み荷の量と思う", "船の大きさ・積み荷・岸壁内の船は見えない", "数え方の限界を書き添える／他の統計と組み合わせる", "❺ 言説と観測"),
    ("いちばん生々しい情報（スマホ写真）を、いちばん確かだと思う", "古い写真・別の場所・見まちがいが混ざる。全体は分からない",
     "撮影日時と場所を確かめ、衛星・ドローンと重ねて確率で扱う", "❻ 3層をつなぐ"),
    ("ドローンを『見やすい所』に飛ばす", "もう分かっている所を見ても、地図は良くならない", "衛星で『迷っている所』を選んで飛ばす", "❻ 3層をつなぐ"),
    ("位置情報つきの写真をそのまま投稿する", "写真の中の位置情報（Exif）から、家や畑の場所が分かってしまう", "投稿前に位置情報を消す／共有の範囲を決める", "❻ 3層をつなぐ"),
    ("D が大きい＝誰かが操作している、と決めつける", "観測の誤差・見えない物・時期のずれでも D は大きくなる", "不確かさの幅と一緒に示し、『確かめる合図』として使う", "❺ 言説と観測"),
]

SOURCES = [
    ("Tellus（テルース）", "日本の衛星データプラットフォーム。ブラウザ上でデータを探し、開発環境で解析できる",
     "まず無料の範囲でアカウント登録し、光学（だいち等）やSARのデータを探す"),
    ("Copernicus Browser（欧州）", "Sentinel-1（SAR）・Sentinel-2（光学）を無料で閲覧・ダウンロードできる",
     "三原市大和町を検索し、日付を変えて NDVI や VV を見比べる"),
    ("書籍のサポートページ（GitHub）", "『SAR衛星データ解析入門』の Python コード（github.com/syu-tan/sar-python-book）",
     "このページの考え方を、実データで試す次の一歩に"),
    ("国土地理院の地図・ハザードマップ", "標高・浸水想定区域", "衛星で見えた水と、地形の『低い所』を重ねて確かめる"),
]


# ─────────────────────────────────────────────
# 自己チェック
# ─────────────────────────────────────────────
if __name__ == "__main__":
    # dB の往復
    assert np.allclose(to_db(from_db(np.array([-20.0, 0.0, 3.0]))), [-20, 0, 3])
    # 箱型平均は一定値を変えない
    assert np.allclose(box_mean(np.full((20, 20), 3.0), 2), 3.0)

    sc = make_scene(0)
    H, W = sc.cls.shape
    # NDVI：森林・農地 > 水
    nd = ndvi(sc.optical[2], sc.optical[3])
    assert nd[sc.cls == FOREST].mean() > 0.6 > 0 > nd[sc.cls == WATER].mean()
    # スペックル：生の画素で引くより、Lee でならした方が水域の F1 が高い
    truth_w = sc.cls == WATER
    thr = water_threshold(to_db(lee_filter(sc.sar_before, 2)))
    assert otsu(to_db(lee_filter(sc.sar_before, 2))) > -12  # 1段だけだと建物・森との境目になる
    raw = scores(truth_w, to_db(sc.sar_before) < thr)["F1"]
    filt = scores(truth_w, water_map(sc.sar_before, thr))["F1"]
    assert filt > raw + 0.15 and filt > 0.8, (raw, filt)
    assert -20 < thr < -12, thr
    # 変化検出：浸水前後の差で、新しく浸水した農地を見つける（1枚だけより誤報が少ない）
    _, chg = change_map(sc.sar_before, sc.sar_after, 3, thr)
    s_chg = scores(sc.flood, chg)
    s_one = scores(sc.flood, water_map(sc.sar_after, thr))
    assert sc.flood.sum() > 200 and s_chg["F1"] > 0.75 and s_chg["誤報"] < s_one["誤報"], (s_chg, s_one)
    # 雲：光学の NDVI は雲の下で低く出る
    scc = make_scene(0, cloud_cover=0.3)
    ndc = ndvi(scc.optical[2], scc.optical[3])
    assert scc.cloud.mean() > 0.2 and ndc[scc.cloud & (scc.cls == FARM)].mean() < 0.1 < ndc[~scc.cloud & (scc.cls == FARM)].mean()
    # 時系列：梅雨には光学の空白が長くなりやすい／SAR は欠けない
    ss = season(0)
    assert ss["VH後方散乱 dB（SAR）"].notna().sum() == len(range(0, 240, 12))
    assert ss["NDVI（真の値）"].max() > 0.75 and ss["NDVI（真の値）"].iloc[-1] < 0.35
    assert longest_gap(ss["NDVI（光学で見えた日）"]) >= 10
    st2 = season(0, stress_day=120)
    assert st2["NDVI（真の値）"].max() < ss["NDVI（真の値）"].max() - 0.05
    # 分類：場所で分けても、少ない教師データで土地の種類を当てられる
    cols = ["赤", "近赤外", "短波長赤外", "NDVI", "NDWI", "VV dB（ならし後）"]
    res = classify(sc, cols)
    assert res["正解率"]["教師あり（ナイーブベイズ）"] > 0.85, res["正解率"]
    gap = leak_gap(make_scene(1), cols)
    assert min(gap.values()) > 0.8, gap
    # 船：CFAR は穏やかな海でよく当たり、荒れた海では誤報が増える
    inten, truth, land = port_scene(15, seed=3, wind=0.2)
    m_calm = match_ships(components(cfar(inten, land)), truth)
    assert m_calm["当たり"] >= 12 and m_calm["誤報"] <= 3, m_calm
    inten2, truth2, land2 = port_scene(15, seed=3, wind=0.9)
    m_rough = match_ships(components(cfar(inten2, land2, pfa=1e-2)), truth2)
    assert m_rough["誤報"] > m_calm["誤報"], (m_calm, m_rough)
    # 言説と観測：実際は2割減、言説は8割減 → D は大きい
    wk = weekly_port(seed=0)
    g = gap_index(wk, 7)
    assert g["D"] > 0.4 and -0.45 < g["観測の変化率"] < 0.05, g
    g0 = gap_index(weekly_port(seed=0, claim_drop=0.20), 7)
    assert g0["D"] < 0.2, g0
    # 3層：その日に来た衛星は標高だけ（ハザードマップ）より良く、迷っている所へのドローンでさらに良くなる
    sc3 = make_scene(0, flood_m=2.0)
    L = layered(sc3, 1.5)
    b = L["scores"]["ブライアスコア"]
    assert b.iloc[1] < b.iloc[0] and b.iloc[2] < b.iloc[1], b
    assert L["scores"]["ドローンの区域のブライア"].iloc[2] < 0.5 * L["scores"]["ドローンの区域のブライア"].iloc[1]
    # 衛星が水位の上がりきる前に来ると、古い「乾いている」が判断を誤らせる → 自分の圃場はドローンで確かめる
    early = make_scene(0, flood_m=1.5)  # 衛星は、水位がまだ 0.5 m 低いうちに来た
    Lo = layered(sc3, 1.5, sat_scene=early)
    assert Lo["scores"]["ブライアスコア"].iloc[1] > Lo["scores"]["ブライアスコア"].iloc[0]
    Lm = layered(sc3, 1.5, sat_scene=early, drone="わたしの圃場")
    true_ha = Lm["わたしの圃場：本当の浸水(ha)"]
    est = Lm["scores"]["わたしの圃場：浸水面積の見積もり(ha)"]
    assert abs(est.iloc[2] - true_ha) < abs(est.iloc[1] - true_ha), (est, true_ha)
    # スマホ：衛星がないと、古い写真を信じすぎて悪くなる。衛星があれば、うその点は打ち消される（層を重ねる強さ）
    kw = dict(drone="飛ばさない", n_phone=60)
    good = layered(sc3, 1.5, sat_weight=0, **kw)["scores"]["ブライアスコア"]
    bad = layered(sc3, 1.5, sat_weight=0, trust=0.6, stale=0.5, assumed_trust=0.97, **kw)["scores"]["ブライアスコア"]
    bad_sat = layered(sc3, 1.5, sat_weight=1, trust=0.6, stale=0.5, assumed_trust=0.97, **kw)["scores"]["ブライアスコア"]
    assert good.iloc[3] < good.iloc[0] < bad.iloc[3], (good, bad)
    assert bad_sat.iloc[3] <= bad_sat.iloc[1] + 0.002, bad_sat
    print("ok", {"3層ブライア": [round(x, 3) for x in b], "水域F1(生/ならし)": f"{raw:.2f}/{filt:.2f}", "浸水F1": f"{s_chg['F1']:.2f}",
                 "分類": {k: f"{v:.2f}" for k, v in res["正解率"].items()}, "漏れ": gap,
                 "船": m_calm, "D": round(g["D"], 2)})

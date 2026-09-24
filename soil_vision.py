"""
soil_vision.py — 圃場写真の半自動AI画像解析（RGBカメラ／スマホ写真用）

① 計算する  : RGB植生指数（ExG・VARI）と大津の二値化で植生／裸地を分離
② 可視化する: グリッドごとの「生育ムラマップ」
③ 判断する  : 可変施肥の処方箋、指標植物のベイズ更新、土壌サンプリング地点の提案

注意：本物の NDVI は近赤外(NIR)バンドが必要。ここでは RGB で代替する指数を使う。
"""
from __future__ import annotations

import base64
import io
import json
import os

import numpy as np
import pandas as pd
from PIL import Image, ImageOps


# ─────────────────────────────────────────────
# ① 計算：植生指数
# ─────────────────────────────────────────────
def load_image(src, max_side: int = 900) -> np.ndarray:
    """ファイルパス／アップロードファイルを読み込み、向きを補正して縮小した RGB 配列を返す。"""
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    im.thumbnail((max_side, max_side))
    return np.asarray(im).astype(np.float32)


def vegetation_indices(rgb: np.ndarray) -> dict[str, np.ndarray]:
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    s = R + G + B + 1e-6
    r, g, b = R / s, G / s, B / s
    exg = 2 * g - r - b                                  # Excess Green（Woebbecke 1995）
    vari = np.clip((G - R) / (G + R - B + 1e-6), -1, 1)  # VARI（Gitelson 2002）
    return {"ExG": exg, "VARI": vari}


def otsu_threshold(x: np.ndarray, bins: int = 256) -> float:
    """大津の二値化（numpy 実装）。"""
    hist, edges = np.histogram(x.ravel(), bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(hist)
    w1 = w0[-1] - w0
    m0 = np.cumsum(hist * centers) / np.maximum(w0, 1)
    m1 = (np.sum(hist * centers) - np.cumsum(hist * centers)) / np.maximum(w1, 1)
    between = w0 * w1 * (m0 - m1) ** 2
    return float(centers[np.argmax(between)])


def grid_stats(exg: np.ndarray, mask: np.ndarray, rows: int, cols: int) -> pd.DataFrame:
    """画像を rows×cols のグリッドに分け、区画ごとの植被率と緑の濃さを集計する。"""
    H, W = exg.shape
    out = []
    for i in range(rows):
        for j in range(cols):
            ys = slice(i * H // rows, (i + 1) * H // rows)
            xs = slice(j * W // cols, (j + 1) * W // cols)
            m, e = mask[ys, xs], exg[ys, xs]
            cover = float(m.mean())
            green = float(e[m].mean()) if m.any() else np.nan
            out.append(dict(行=i, 列=j, 区画=f"{chr(65 + i)}{j + 1}", 植被率=cover, 緑の濃さ=green))
    return pd.DataFrame(out)


# ─────────────────────────────────────────────
# ③ 判断：可変施肥の処方箋
# ─────────────────────────────────────────────
def prescription(grid: pd.DataFrame, base_n_kg_10a: float, n_ratio: float,
                 field_m2: float, gain: float = 0.5, min_cover: float = 0.15) -> pd.DataFrame:
    """
    緑が薄い区画ほど多く、濃い区画ほど少なく配分する線形ルール。
      倍率 = clip(1 + gain × (中央値 − 区画値) / IQR, 0.5, 1.5)
    植被率が min_cover 未満の区画は「裸地・要確認」として施肥しない（まず原因を確認）。
    """
    g = grid.copy()
    valid = g["植被率"] >= min_cover
    v = g.loc[valid, "緑の濃さ"]
    med = v.median() if len(v) else 0.0
    iqr = (v.quantile(0.75) - v.quantile(0.25)) if len(v) > 3 else 0.0
    iqr = iqr if iqr > 1e-6 else 1.0
    g["倍率"] = np.where(valid, np.clip(1 + gain * (med - g["緑の濃さ"]) / iqr, 0.5, 1.5), 0.0)
    cell_m2 = field_m2 / len(g)
    n_g = base_n_kg_10a * cell_m2 * g["倍率"]   # 1 kg/10a = 1 g/㎡
    g["窒素量(g)"] = n_g
    g["肥料量(g)"] = n_g / n_ratio
    g["判定"] = np.select(
        [~valid, g["倍率"] >= 1.2, g["倍率"] <= 0.8],
        ["裸地・要確認", "追肥 多め", "追肥 少なめ"], "標準")
    return g


def sampling_points(g: pd.DataFrame, k: int = 3) -> list[str]:
    """土壌分析に回すべき区画：裸地・最も緑が薄い区画・最も濃い区画（比較対照）。"""
    pts = list(g.loc[g["判定"] == "裸地・要確認", "区画"])[:1]
    valid = g[g["判定"] != "裸地・要確認"].dropna(subset=["緑の濃さ"])
    if len(valid):
        pts += list(valid.nsmallest(k - 1, "緑の濃さ")["区画"])
        pts.append(valid.nlargest(1, "緑の濃さ")["区画"].iloc[0])
    return list(dict.fromkeys(pts))


# ─────────────────────────────────────────────
# ③ 判断：指標植物 × ベイズ更新
# ─────────────────────────────────────────────
# 尤度比(LR)：その雑草が「多い」とき、仮説が真である証拠がどれだけ強まるか（仮定値）
TENDENCIES = ["酸性に傾いている", "窒素が多く肥沃", "土が硬い・排水が悪い"]
INDICATORS = {
    "スギナ":           {"酸性に傾いている": 3.0},
    "ハコベ":           {"酸性に傾いている": 1.5, "窒素が多く肥沃": 1.5},
    "ヒメスイバ":       {"酸性に傾いている": 3.0},
    "シロザ":           {"窒素が多く肥沃": 3.0},
    "ナズナ":           {"窒素が多く肥沃": 2.0},
    "オオバコ":         {"土が硬い・排水が悪い": 3.0},
    "カラスノエンドウ": {"土が硬い・排水が悪い": 1.5},
}


def bayes_soil(observed: list[str], prior: float = 0.3) -> pd.DataFrame:
    """事後オッズ = 事前オッズ × Π(尤度比)。各傾向を独立な二値仮説として扱う。"""
    rows = []
    for t in TENDENCIES:
        odds = prior / (1 - prior)
        for w in observed:
            odds *= INDICATORS.get(w, {}).get(t, 1.0)
        rows.append(dict(傾向=t, 事前確率=prior, 事後確率=odds / (1 + odds)))
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
# 半自動：生成AI（Claude）に雑草候補を提案させる（任意）
# ─────────────────────────────────────────────
def ai_available() -> bool:
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def ai_suggest_weeds(rgb: np.ndarray, model: str = "claude-sonnet-5") -> dict:
    """
    写真を Claude に送り、INDICATORS のうち写っていそうな雑草を JSON で返させる。
    返り値は「候補」であり、最終判断は人が行う（Human-in-the-Loop）。
    """
    import anthropic

    buf = io.BytesIO()
    Image.fromarray(rgb.astype(np.uint8)).save(buf, format="JPEG", quality=85)
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    names = "、".join(INDICATORS)
    prompt = (
        "これは日本（広島県）の畑の写真です。次の雑草のうち、写真に写っている可能性があるものを選び、"
        f"確信度(0〜1)と根拠を付けてください。候補：{names}。\n"
        "判別できない場合は無理に選ばないでください。出力は JSON のみ："
        '{"candidates":[{"name":"...","confidence":0.0,"reason":"..."}],"note":"..."}'
    )
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=model, max_tokens=800,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
            {"type": "text", "text": prompt},
        ]}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])

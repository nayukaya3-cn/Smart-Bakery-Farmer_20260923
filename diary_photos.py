"""
diary_photos.py ─ 作業日誌と、取り込み済みの写真（assets）を結びつける部品

写真の置き方（どちらでも結びつきます）
  ① 日誌IDで結びつける（Googleフォームから取り込んだ写真）
       assets/diary/20261018/D012_1.jpg   ← ファイル名の先頭が日誌ID
     Apps Script（docs/work_diary_form.gs）のメニュー「写真をZIPで保存（assets用）」で、
     この形のフォルダごとZIPになります。展開して assets/ の中に置きます。
  ② 同じ日の写真として結びつける（これまでの記録写真）
       assets/20261003/米ぬか発酵肥料づくり開始-1.jpg ← 日付フォルダ（YYYYMMDD）と日誌の日付が同じ

方針
  - 写真は公開リポジトリに置かれるので、位置情報（GPS）が残っていないかを必ず確かめる。
      python diary_photos.py --check assets   … GPS付きの写真があれば一覧を出して終了コード1
      python diary_photos.py --strip assets   … GPSなどのExifを消して上書き保存（向きは保つ）
  - 画面に出すときも、Exifを外して縮小した画像だけを渡す（clean_image）。
  - 人の顔・車のナンバー・取引先の看板が写った写真は置かない（人の目で確かめる）。
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

import pandas as pd

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
GPS_TAG = 34853
ID_RE = re.compile(r"^([A-Z]\d{2,})_")          # D012_1.jpg → D012
DATE_DIR_RE = re.compile(r"^\d{8}$")
COLS = ["パス", "日付", "ID", "説明"]


def _caption(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"-\d+$", "", stem)
    stem = re.sub(r"[_ ]?\d{8}$", "", stem)
    return stem.replace("_", " ")


def scan(assets: Path) -> pd.DataFrame:
    """assets 以下の画像を一覧にする。日付は親フォルダ（YYYYMMDD）、IDはファイル名の先頭から取る。"""
    rows = []
    if not assets.exists():
        return pd.DataFrame(columns=COLS)
    for p in sorted(assets.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in IMAGE_EXT:
            continue
        day = next((d.name for d in p.parents if DATE_DIR_RE.match(d.name)), None)
        m = ID_RE.match(p.name)
        rows.append((p, f"{day[:4]}-{day[4:6]}-{day[6:]}" if day else None,
                     m.group(1) if m else None, _caption(p.name)))
    return pd.DataFrame(rows, columns=COLS)


def link(diary: pd.DataFrame, photos: pd.DataFrame, by_id: bool = True, by_date: bool = True,
         days: int = 0) -> pd.DataFrame:
    """日誌の各行と写真を結びつける。返す列：ID, 日付, パス, 説明, 結びつけ方。

    by_id   … ファイル名の先頭が日誌ID、または日誌の「写真」列にファイル名がある
    by_date … 日付フォルダが日誌の日付と同じ（days>0 なら前後 days 日まで）。IDで結びついた写真は重ねない
    """
    out = []
    if diary.empty or photos.empty:
        return pd.DataFrame(columns=["ID", "日付", "パス", "説明", "結びつけ方"])
    d = diary.copy()
    d["ID"] = d["ID"].astype(str)
    d["_日付"] = pd.to_datetime(d["日付"], errors="coerce").dt.strftime("%Y-%m-%d")
    names = {}
    if "写真" in d.columns:  # フォームから来たCSV：「D012_1.jpg;D012_2.jpg」
        for i, v in zip(d["ID"], d["写真"].fillna("").astype(str)):
            for n in re.split(r"[;；,、\s]+", v):
                if n:
                    names[n] = i
    used = set()
    if by_id:
        for _, p in photos.iterrows():
            pid = p["ID"] if p["ID"] in set(d["ID"]) else names.get(Path(p["パス"]).name)
            if pid:
                day = d.loc[d["ID"] == pid, "_日付"].iloc[0]
                out.append((pid, day, p["パス"], p["説明"], "日誌ID"))
                used.add(str(p["パス"]))
    if by_date:
        ph = photos[photos["日付"].notna()].copy()
        ph["_d"] = pd.to_datetime(ph["日付"])
        ph = ph[~ph["パス"].astype(str).isin(used)]
        for _, r in d.dropna(subset=["_日付"]).iterrows():
            gap = (ph["_d"] - pd.Timestamp(r["_日付"])).dt.days
            for (_, p), g in zip(ph[gap.abs() <= days].iterrows(), gap[gap.abs() <= days]):
                how = "同じ日" if g == 0 else f"近い日（{g:+d}日）"
                out.append((r["ID"], r["_日付"], p["パス"], p["説明"], how))
    return pd.DataFrame(out, columns=["ID", "日付", "パス", "説明", "結びつけ方"])


# ──────────────── 位置情報（GPS） ────────────────
def has_gps(path: Path) -> bool:
    from PIL import Image

    try:
        with Image.open(path) as im:
            ex = im.getexif()
            return bool(ex.get(GPS_TAG)) or bool(ex.get_ifd(GPS_TAG))
    except Exception:  # noqa: BLE001  壊れた画像は別のチェックで扱う
        return False


def clean_image(path: Path, max_side: int = 1600):
    """表示用：向きを直し、Exif（位置情報を含む）を外し、長い辺を max_side に縮める。"""
    from PIL import Image, ImageOps

    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        im.thumbnail((max_side, max_side))
        out = im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB")
    out.info = {}  # Exif・コメントなどの付随情報を持たせない
    return out


def strip_exif(path: Path) -> bool:
    """Exifを消して上書き保存する（向きは画素に反映してから消す）。消したら True。"""
    from PIL import Image, ImageOps

    with Image.open(path) as im:
        if not im.getexif():
            return False
        fixed = ImageOps.exif_transpose(im)
        fmt = im.format or "JPEG"
        buf = io.BytesIO()
        save_kw = {"quality": 92} if fmt == "JPEG" else {}
        fixed.save(buf, format=fmt, **save_kw)
    path.write_bytes(buf.getvalue())
    return True


MAX_ZIP_FILES = 300
MAX_ZIP_UNPACKED = 300 * 1024 * 1024     # 展開後の合計（ZIP爆弾よけ）
ZIP_PATH_RE = re.compile(r"^diary/\d{8}/[A-Z]\d{2,}_\d+\.(jpe?g|png|webp)$", re.I)


def clean_zip(data: bytes, max_side: int = 2000) -> tuple[bytes, pd.DataFrame]:
    """フォームの写真ZIP（diary/YYYYMMDD/D012_1.jpg の形）を、位置情報を消して縮小したZIPにする。

    決まった形でない名前（../ を含む・別のフォルダ・画像以外）は入れずに、理由を一覧で返す。
    """
    import zipfile

    from PIL import Image, ImageOps

    out_buf, rows, total = io.BytesIO(), [], 0
    with zipfile.ZipFile(io.BytesIO(data)) as zin, zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as zout:
        infos = [i for i in zin.infolist() if not i.is_dir()]
        if len(infos) > MAX_ZIP_FILES:
            raise ValueError(f"ファイルが多すぎます（上限 {MAX_ZIP_FILES} 個）")
        for info in infos:
            name = info.filename.replace("\\", "/")
            if not ZIP_PATH_RE.match(name):
                rows.append((name, "入れない", "diary/日付/日誌ID_番号.jpg の形ではない"))
                continue
            total += info.file_size
            if total > MAX_ZIP_UNPACKED:
                raise ValueError("展開後の大きさが上限を超えました")
            try:
                with Image.open(io.BytesIO(zin.read(info))) as im:
                    gps = bool(im.getexif().get_ifd(GPS_TAG))
                    im = ImageOps.exif_transpose(im)
                    im.thumbnail((max_side, max_side))
                    im = im.convert("RGB")
                    buf = io.BytesIO()
                    im.save(buf, format="JPEG", quality=88)  # Exifは渡さない＝消える
            except Exception:  # noqa: BLE001
                rows.append((name, "入れない", "画像として読めない"))
                continue
            new = re.sub(r"\.(png|webp|jpeg)$", ".jpg", name, flags=re.I)
            zout.writestr(new, buf.getvalue())
            rows.append((new, "入れた", "位置情報を消した" if gps else "位置情報なし"))
    return out_buf.getvalue(), pd.DataFrame(rows, columns=["ファイル", "結果", "メモ"])


def gps_list(root: Path) -> list[Path]:
    return [p for p in sorted(root.rglob("*")) if p.suffix.lower() in IMAGE_EXT and has_gps(p)]


# ──────────────── 自己チェック・コマンド ────────────────
def _selftest() -> None:
    import tempfile

    from PIL import Image

    with tempfile.TemporaryDirectory() as t:
        root = Path(t) / "assets"
        (root / "diary" / "20261018").mkdir(parents=True)
        (root / "20261003").mkdir(parents=True)
        Image.new("RGB", (40, 30), "green").save(root / "diary" / "20261018" / "D012_1.jpg")
        Image.new("RGB", (40, 30), "brown").save(root / "20261003" / "米ぬか発酵肥料づくり開始-1.jpg")
        # GPS付きの写真（緯度経度のタグだけ入れる）
        im = Image.new("RGB", (40, 30), "blue")
        ex = im.getexif()
        ex.get_ifd(GPS_TAG).update({1: "N", 2: (34.0, 24.0, 0.0)})
        im.save(root / "20261003" / "gps_test-1.jpg", exif=ex)

        ph = scan(root)
        assert len(ph) == 3 and set(ph["ID"].dropna()) == {"D012"}
        diary = pd.DataFrame({"ID": ["D012", "D013"], "日付": ["2026-10-18", "2026-10-03"], "本文": ["a", "b"]})
        lk = link(diary, ph)
        assert set(lk[lk["結びつけ方"] == "日誌ID"]["ID"]) == {"D012"}
        assert len(lk[(lk["ID"] == "D013") & (lk["結びつけ方"] == "同じ日")]) == 2
        near = link(pd.DataFrame({"ID": ["D014"], "日付": ["2026-10-02"], "本文": ["c"]}), ph, days=1)
        assert len(near) == 2 and set(near["結びつけ方"]) == {"近い日（+1日）"}
        g = gps_list(root)
        assert [p.name for p in g] == ["gps_test-1.jpg"], g
        assert strip_exif(g[0]) and not gps_list(root)
        assert clean_image(root / "diary" / "20261018" / "D012_1.jpg").size == (40, 30)

        # ZIPの掃除：GPS付き写真は位置情報が消え、決まった形でない名前は入らない
        import zipfile
        b = io.BytesIO()
        im2 = Image.new("RGB", (50, 40), "blue")
        ex2 = im2.getexif()
        ex2.get_ifd(GPS_TAG).update({1: "N", 2: (34.0, 24.0, 0.0)})
        g2 = io.BytesIO()
        im2.save(g2, format="JPEG", exif=ex2)
        with zipfile.ZipFile(b, "w") as z:
            z.writestr("diary/20261018/D012_1.jpg", g2.getvalue())
            z.writestr("../evil.jpg", g2.getvalue())
            z.writestr("diary/20261018/memo.txt", "x")
        cleaned, rep = clean_zip(b.getvalue())
        with zipfile.ZipFile(io.BytesIO(cleaned)) as z:
            assert z.namelist() == ["diary/20261018/D012_1.jpg"]
            with Image.open(io.BytesIO(z.read("diary/20261018/D012_1.jpg"))) as im3:
                assert not im3.getexif().get_ifd(GPS_TAG)
        assert (rep["結果"] == "入れない").sum() == 2
    print("OK: 自己チェックを通過しました")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="日誌の写真：位置情報の確認・削除")
    ap.add_argument("--check", metavar="DIR", help="GPS付きの写真を探す（あれば終了コード1）")
    ap.add_argument("--strip", metavar="DIR", help="Exif（GPSを含む）を消して上書き保存")
    a = ap.parse_args(argv)
    if a.check:
        found = gps_list(Path(a.check))
        for p in found:
            print(f"GPS付き: {p}")
        print(f"{len(found)} 枚の写真に位置情報が残っています" if found else "位置情報の残った写真はありません")
        return 1 if found else 0
    if a.strip:
        n = sum(strip_exif(p) for p in sorted(Path(a.strip).rglob("*")) if p.suffix.lower() in IMAGE_EXT)
        print(f"{n} 枚の写真からExifを消しました")
        return 0
    _selftest()
    return 0


if __name__ == "__main__":
    sys.exit(main())

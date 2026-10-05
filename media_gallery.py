"""
media_gallery.py — タブに画像・動画・PDF・テキストを組み込むための共通部品

使い方（app.py の各タブ内で）:
    import media_gallery as mg
    mg.media_section(ASSETS / "3d_printer", key="p3d", title="📂 記録・資料")

ファイルの置き方:
    assets/3d_printer/20261010/自助具_太い持ち手-1.jpg
    assets/3d_printer/20261010/初めての印刷.mov
    assets/3d_printer/資料/COCRE_HUBの使い方.pdf
    → 日付フォルダ（YYYYMMDD）ごとに新しい順で表示。ファイル名がそのまま説明文になります。
"""
from __future__ import annotations

import io
import re
from pathlib import Path

import streamlit as st

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXT = {".mov", ".mp4", ".m4v", ".webm"}
PDF_EXT = {".pdf"}
TEXT_EXT = {".txt", ".md"}
ALL_EXT = IMAGE_EXT | VIDEO_EXT | PDF_EXT | TEXT_EXT
VIDEO_MIME = {".mov": "video/quicktime", ".mp4": "video/mp4", ".m4v": "video/mp4", ".webm": "video/webm"}
MAX_PDF_PAGES = 10  # 画面に並べるPDFのページ数の上限（全ページはダウンロードで）


def _caption(name: str) -> str:
    """ファイル名 → 説明文（末尾の -1 や _20261004 は取り除く）"""
    stem = Path(name).stem
    stem = re.sub(r"-\d+$", "", stem)
    stem = re.sub(r"[_ ]?\d{8}$", "", stem)
    return stem.replace("_", " ")


def _folder_label(name: str) -> str:
    return f"{name[:4]}/{name[4:6]}/{name[6:]}" if len(name) == 8 and name.isdigit() else name


@st.cache_data(show_spinner=False)
def _pdf_pages(data: bytes, max_pages: int = MAX_PDF_PAGES, scale: float = 1.4):
    """PDFの各ページを画像にする（スマホでも確実に表示できるように）"""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    n = len(pdf)
    pages = [pdf[i].render(scale=scale).to_pil() for i in range(min(n, max_pages))]
    return pages, n


def show_file(name: str, data: bytes, key: str) -> None:
    """1つのファイルを種類に応じて表示する"""
    ext = Path(name).suffix.lower()
    cap = _caption(name)
    if ext in IMAGE_EXT:
        st.image(data, caption=cap, width="stretch")
    elif ext in VIDEO_EXT:
        st.markdown(f"🎬 **{cap}**")
        st.video(io.BytesIO(data), format=VIDEO_MIME.get(ext, "video/mp4"))
        if ext == ".mov":
            st.caption("※ .mov が再生できないブラウザでは、下のボタンから保存して再生してください。")
            st.download_button("動画を保存", data, file_name=name, key=f"{key}_dl")
    elif ext in PDF_EXT:
        try:
            pages, n = _pdf_pages(data)
        except Exception as e:  # noqa: BLE001
            st.warning(f"PDFを表示できませんでした：{e}")
            pages, n = [], 0
        with st.expander(f"📄 {cap}（{n} ページ）", expanded=False):
            for i, img in enumerate(pages, 1):
                st.image(img, caption=f"{i} / {n}", width=720)
            if n > len(pages):
                st.caption(f"※ 最初の {len(pages)} ページのみ表示しています。")
        st.download_button("PDFを保存", data, file_name=name, mime="application/pdf", key=f"{key}_dl")
    elif ext in TEXT_EXT:
        with st.expander(f"📝 {cap}", expanded=False):
            text = data.decode("utf-8", errors="replace")
            st.markdown(text) if ext == ".md" else st.text(text)


def _grid(items: list[tuple[str, bytes]], key: str, ncols: int = 3) -> None:
    """画像・動画はカード状に並べ、PDF・テキストは全幅で並べる"""
    visual = [(n, d) for n, d in items if Path(n).suffix.lower() in IMAGE_EXT | VIDEO_EXT]
    docs = [(n, d) for n, d in items if Path(n).suffix.lower() in PDF_EXT | TEXT_EXT]
    for row in range(0, len(visual), ncols):
        cols = st.columns(ncols)
        for j, (n, d) in enumerate(visual[row:row + ncols]):
            with cols[j]:
                show_file(n, d, key=f"{key}_v{row + j}")
    for i, (n, d) in enumerate(docs):
        show_file(n, d, key=f"{key}_d{i}")


def media_section(folder: Path, key: str, title: str = "📂 記録・資料") -> None:
    """フォルダの中身を表示し、その場でのアップロードも受け付ける"""
    st.subheader(title)

    # ① リポジトリのフォルダに置いたファイル（公開ページにずっと残る）
    files = sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in ALL_EXT) \
        if folder.exists() else []
    if not files:
        st.caption(f"まだ記録はありません。`{folder.relative_to(folder.parents[1])}/YYYYMMDD/` に"
                   "写真・動画・PDFを置くと、ここに自動で表示されます。")
    groups: dict[str, list[Path]] = {}
    for p in files:
        groups.setdefault(p.parent.name if p.parent != folder else "", []).append(p)
    for g in sorted(groups, reverse=True):
        if g:
            st.markdown(f"##### {_folder_label(g)}")
        _grid([(p.name, p.read_bytes()) for p in groups[g]], key=f"{key}_{g or 'root'}")

    # ② その場で取り込む（このセッションのみ。公開ページには残らない）
    with st.expander("➕ ファイルを取り込んで確認する（このセッション内のみ）"):
        ups = st.file_uploader(
            "画像（jpg / png）・動画（mov / mp4）・PDF・テキスト（txt / md）",
            type=sorted(e.lstrip(".") for e in ALL_EXT),
            accept_multiple_files=True, key=f"{key}_up",
        )
        if ups:
            _grid([(u.name, u.getvalue()) for u in ups], key=f"{key}_up")
            st.info("ここで取り込んだファイルは、ページを閉じると消えます。公開ページに残すには、"
                    f"GitHub の `{folder.relative_to(folder.parents[1])}/` に日付フォルダを作ってアップロードしてください。")

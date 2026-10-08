"""
media_gallery.py — タブに画像・動画・PDF・テキストを組み込むための共通部品

使い方（app.py の各タブ内で）:
    import media_gallery as mg
    mg.media_section(ASSETS / "3d_printer", key="p3d", title="📂 記録・資料")

ファイルの置き方:
    assets/3d_printer/20261010/自助具_太い持ち手-1.jpg
    assets/3d_printer/20261010/初めての印刷.mov
    assets/3d_printer/資料/COCRE_HUBの使い方.pdf
    assets/joho1/20261010/例題4_収量予測.ipynb   → 「Google Colab で開く」ボタン付き
    assets/joho1/20261010/練習問題.py            → Colab 用ノートブックに変換して保存できる
    → 日付フォルダ（YYYYMMDD）ごとに新しい順で表示。ファイル名がそのまま説明文になります。
"""
from __future__ import annotations

import io
import re
from pathlib import Path

import streamlit as st

import security_guard as sg

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXT = {".mov", ".mp4", ".m4v", ".webm"}
PDF_EXT = {".pdf"}
TEXT_EXT = {".txt", ".md"}
CODE_EXT = {".ipynb", ".py"}
DATA_EXT = {".csv"}
ALL_EXT = IMAGE_EXT | VIDEO_EXT | PDF_EXT | TEXT_EXT | CODE_EXT | DATA_EXT
GITHUB_REPO = "nayukaya3-cn/Smart-Bakery-Farmer_20260923"  # Colab で開くときの GitHub リポジトリ
GITHUB_BRANCH = "main"
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


def colab_url(repo_path: str) -> str:
    """リポジトリ内の .ipynb のパス → Google Colab で開くURL"""
    from urllib.parse import quote
    return f"https://colab.research.google.com/github/{GITHUB_REPO}/blob/{GITHUB_BRANCH}/{quote(repo_path)}"


def py_to_ipynb(code: str, title: str) -> bytes:
    """.py のコードを、Colab で開ける .ipynb に変換する（# %% でセルを区切れる）"""
    import json

    chunks = [c.strip("\n") for c in re.split(r"^# ?%%.*$", code, flags=re.M)]
    cells = [{"cell_type": "markdown", "metadata": {}, "source": [f"# {title}\n", "▶ でセルを順に実行してください。"]}]
    cells += [{"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
               "source": c.splitlines(keepends=True)} for c in chunks if c.strip()]
    nb = {"nbformat": 4, "nbformat_minor": 5, "cells": cells,
          "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"},
                       "language_info": {"name": "python"}}}
    return json.dumps(nb, ensure_ascii=False, indent=1).encode("utf-8")


def _ipynb_preview(data: bytes, max_cells: int = 30) -> None:
    import json

    try:
        nb = json.loads(data.decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        st.warning(f"ノートブックを読み込めませんでした：{e}")
        return
    for c in nb.get("cells", [])[:max_cells]:
        src = "".join(c.get("source", []))
        if not src.strip():
            continue
        if c.get("cell_type") == "code":
            st.code(src, language="python")
        else:
            st.markdown(src, unsafe_allow_html=False)


def show_file(name: str, data: bytes, key: str, repo_path: str | None = None) -> None:
    """1つのファイルを種類に応じて表示する（repo_path があれば Colab で開くボタンを付ける）"""
    ext = Path(name).suffix.lower()
    cap = _caption(name)
    if ext in IMAGE_EXT:
        st.image(data, caption=cap, width="stretch")
    elif ext in VIDEO_EXT:
        st.markdown("🎬 **" + re.sub(r"([\\`*_{}\[\]()#+\-.!<>|~])", r"\\\1", cap) + "**")
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
    elif ext == ".ipynb":
        st.markdown(f"📓 **{cap}**（Jupyter ノートブック）")
        b1, b2 = st.columns(2)
        if repo_path:
            b1.link_button("▶ Google Colab で開く", colab_url(repo_path), width="stretch")
        b2.download_button("ノートブックを保存", data, file_name=name, key=f"{key}_dl", width="stretch")
        if not repo_path:
            st.caption("※ 保存して、Colab の「ファイル → ノートブックをアップロード」から開けます。")
        with st.expander("中身を見る"):
            _ipynb_preview(data)
    elif ext == ".py":
        st.markdown(f"🐍 **{cap}**（Python）")
        with st.expander("コードを見る"):
            st.code(data.decode("utf-8", errors="replace"), language="python")
        b1, b2 = st.columns(2)
        b1.download_button("Colab 用ノートブック（.ipynb）に変換して保存",
                           py_to_ipynb(data.decode("utf-8", errors="replace"), cap),
                           file_name=Path(name).with_suffix(".ipynb").name, key=f"{key}_nb", width="stretch")
        b2.download_button(".py を保存", data, file_name=name, key=f"{key}_dl", width="stretch")
    elif ext in DATA_EXT:
        import pandas as pd

        st.markdown(f"📊 **{cap}**（CSV）")
        try:
            st.dataframe(pd.read_csv(io.BytesIO(data)), width="stretch", height=220)
        except Exception as e:  # noqa: BLE001
            st.warning(f"CSVを読み込めませんでした：{e}")
        st.download_button("CSVを保存", data, file_name=name, mime="text/csv", key=f"{key}_dl")


def _grid(items: list[tuple], key: str, ncols: int = 3) -> None:
    """画像・動画はカード状に並べ、PDF・テキスト・コードは全幅で並べる
    items: (ファイル名, 中身) または (ファイル名, 中身, リポジトリ内パス)"""
    items = [(t[0], t[1], t[2] if len(t) > 2 else None) for t in items]
    visual = [t for t in items if Path(t[0]).suffix.lower() in IMAGE_EXT | VIDEO_EXT]
    docs = [t for t in items if Path(t[0]).suffix.lower() not in IMAGE_EXT | VIDEO_EXT]
    for row in range(0, len(visual), ncols):
        cols = st.columns(ncols)
        for j, (n, d, rp) in enumerate(visual[row:row + ncols]):
            with cols[j]:
                show_file(n, d, key=f"{key}_v{row + j}", repo_path=rp)
    for i, (n, d, rp) in enumerate(docs):
        show_file(n, d, key=f"{key}_d{i}", repo_path=rp)
        st.write("")


def media_section(folder: Path, key: str, title: str = "📂 記録・資料",
                  accept: str = "画像（jpg / png）・動画（mov / mp4）・PDF・テキスト（txt / md）") -> None:
    """フォルダの中身を表示し、その場でのアップロードも受け付ける"""
    st.subheader(title)
    root = folder.parents[1]  # リポジトリのいちばん上（assets/xxx → ルート）

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
        _grid([(p.name, p.read_bytes(), p.relative_to(root).as_posix()) for p in groups[g]],
              key=f"{key}_{g or 'root'}")

    # ② その場で取り込む（このセッションのみ。公開ページには残らない）
    with st.expander("➕ ファイルを取り込んで確認する（このセッション内のみ）"):
        ups = st.file_uploader(
            accept,
            type=sorted(e.lstrip(".") for e in ALL_EXT),
            accept_multiple_files=True, key=f"{key}_up",
        )
        ups = [u for u in (ups or []) if sg.check_upload(u, sg.MAX_IMAGE_BYTES * 4, "gallery", Path(u.name).suffix.lower())]
        if ups:
            _grid([(u.name, u.getvalue()) for u in ups], key=f"{key}_up")
            st.info("ここで取り込んだファイルは、ページを閉じると消えます。公開ページに残すには、"
                    f"GitHub の `{folder.relative_to(folder.parents[1])}/` に日付フォルダを作ってアップロードしてください。")

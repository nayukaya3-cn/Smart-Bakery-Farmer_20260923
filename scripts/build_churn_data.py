"""
Online Retail II（UCI）の明細 約107万行 → 請求書（1回の注文）単位の小さな表に要約する

  python scripts/build_churn_data.py path/to/online_retail_II.xlsx
  → data/online_retail_ii_invoices.csv.gz（約4万行・1MB未満）

ページ「🛒 離れる顧客を先に見つける」は、この要約だけで動きます（43MBの元データは置きません）。
要約のしかたは churn_lab.invoices_from_lines() と同じ（ノートブックの前処理③と同じ規則）。

出典：Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository.
      https://doi.org/10.24432/C5CG6D  ライセンス CC BY 4.0（出典を書けば改変・再配布可）
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import churn_lab as cl  # noqa: E402


def main(xlsx: str) -> None:
    sheets = pd.read_excel(xlsx, sheet_name=None)          # 年度ごとの2シート
    lines = pd.concat(sheets.values(), ignore_index=True)
    inv = cl.invoices_from_lines(lines)
    out = ROOT / cl.DATA_PATH.relative_to(ROOT)
    inv.to_csv(out, index=False, compression="gzip")
    print(f"{len(lines):,} 明細 → {len(inv):,} 請求書 / 顧客 {inv[cl.CID].nunique():,} 人 → {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "online_retail_II.xlsx")

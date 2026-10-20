"""
scripts/nisshi.py ─ 作業日誌の「毎日3分・毎週10分」ルーティンを Claude Code から回すための道具

これまでの流れ（フォーム → スプレッドシート → CSV → ダッシュボード → claude.ai に貼る → JSON を貼り戻す
→ CSV を保存 → data/ に置く → push）は、手で受け渡す場所が多く、毎日は回らなかった。
ここでは受け渡しを Claude Code に任せ、人がするのは「撮る・1行話す・確かめる」の3つだけにする。

  毎日  /nisshi  … prep（写真を整える）→ Claude Code が写真を見てタグ案 → 人が直す → add（記録）
  毎週  /shukei  … week（数える・一致率・次に撮る写真）→ 人が原文を読んで判定
  毎月  /tsuki   … week --days 31 → 人が優先順位を決める

判断の部品は既存のものをそのまま使う（新しい判定ロジックは足さない）：
  diary_text  … 匿名化 mask・3語の検索・打ち消しの規則 rule_label
  diary_vision… 指示文 prompt・答えの検査 parse_many（語彙外は捨てる）・観察 OBS
  diary_photos… 位置情報の確認 has_gps・Exif を外した縮小 clean_image

置き場所
  inbox/                         撮った写真を入れる（git に入れない）
  .nisshi/today/                 今日の作業場所（git に入れない）
  data/private/work_diary.csv    日誌の本文（匿名化済み。git に入れない）
  data/private/tags_log.jsonl    Claude の案と人の確定版（一致率の計算用。git に入れない）
  data/private/mask_dict.txt     伏せる名前の辞書（git に入れない）
  data/private/hold/             顔・ナンバー等が写った写真（公開しない）
  data/private/reports/          週報・月報
  data/photo_ai.csv              公開してよい写真のタグ（ダッシュボードが読む）
  assets/YYYYMMDD/D001_1.jpg     公開してよい写真（位置情報なし）
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import diary_photos as dp  # noqa: E402
import diary_text as dt  # noqa: E402
import diary_vision as dv  # noqa: E402

INBOX = ROOT / "inbox"
TODAY = ROOT / ".nisshi" / "today"
PRIV = ROOT / "data" / "private"
DIARY = PRIV / "work_diary.csv"
TAGS_LOG = PRIV / "tags_log.jsonl"
MASK_DICT = PRIV / "mask_dict.txt"
HOLD = PRIV / "hold"
REPORTS = PRIV / "reports"
PHOTO_AI = ROOT / "data" / "photo_ai.csv"
ASSETS = ROOT / "assets"

DIARY_COLS = ["ID", "日付", "記入者", "作業", "本文", "止まった時間(分)", "写真"]
WORKS = ["除草", "出荷", "機械整備", "収穫", "播種", "育苗", "圃場整備", "獣害対策", "肥料づくり", "果樹管理",
         "製パン", "その他"]
SOURCE = "Claude Code（案）→ 人が確定"
TAG_FIELDS = ["種類", "場面", "写っているもの", "遅れ", "故障", "人手", "次の1枚"]


# ───────────────────────── 共通 ─────────────────────────
def load_dict() -> tuple[list[str], list[str]]:
    """mask_dict.txt：1行に1つ。取引先は「取引先:みどり青果」のように書く。# で始まる行は無視。"""
    names, partners = [], []
    if MASK_DICT.exists():
        for line in MASK_DICT.read_text(encoding="utf-8").splitlines():
            w = line.strip()
            if not w or w.startswith("#"):
                continue
            if w.startswith(("取引先:", "取引先：")):
                partners.append(w.split(":", 1)[-1].split("：", 1)[-1].strip())
            else:
                names.append(w)
    return names, partners


def load_diary() -> pd.DataFrame:
    if not DIARY.exists():
        return pd.DataFrame(columns=DIARY_COLS)
    return pd.read_csv(DIARY, encoding="utf-8-sig", dtype=str).fillna("")


def next_id(diary: pd.DataFrame) -> str:
    nums = [int(m.group(1)) for i in diary["ID"] if (m := re.fullmatch(r"D(\d+)", str(i)))]
    return f"D{(max(nums) + 1 if nums else 1):03d}"


def manifest() -> list[dict]:
    f = TODAY / "manifest.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def read_tags(path: str | None, n: int) -> dict[int, dict]:
    """タグの JSON（1枚なら {...}、複数なら [...]）を読み、diary_vision の検査を通す。語彙外は捨てられる。"""
    if not path or n == 0:
        return {}
    return dv.parse_many(Path(path).read_text(encoding="utf-8"), n)



# ───────────────────────── prep ─────────────────────────
def cmd_prep(args) -> int:
    """写真を整える：向きを直し、位置情報（Exif）を外し、縮小して .nisshi/today/1.jpg… に置く。指示文も書き出す。"""
    srcs = [Path(p) for p in args.paths] if args.paths else sorted(
        p for p in INBOX.glob("*") if p.suffix.lower() in dp.IMAGE_EXT)
    heic = [p for p in (args.paths or INBOX.glob("*")) if Path(p).suffix.lower() in {".heic", ".heif"}]
    if heic:
        print(f"⚠ HEIC は読めません（{len(heic)} 枚）。iPhone の 設定→カメラ→フォーマット→「互換性優先」で撮るか、JPEG で書き出してください。")
    srcs = srcs[: dv.MAX_BATCH]
    if TODAY.exists():
        shutil.rmtree(TODAY)
    TODAY.mkdir(parents=True)
    items = []
    for i, p in enumerate(srcs, start=1):
        gps = dp.has_gps(p)
        img = dp.clean_image(p, max_side=1600)
        out = TODAY / f"{i}.jpg"
        img.convert("RGB").save(out, "JPEG", quality=88)
        m = dv.quality_flags(dv.metrics(dv.load_small(out)))
        items.append({"no": i, "src": str(p), "gps_removed": gps, "flags": m, "file": str(out.relative_to(ROOT))})
    (TODAY / "manifest.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    (TODAY / "prompt.txt").write_text(dv.prompt(max(len(items), 1)), encoding="utf-8")
    print(f"写真 {len(items)} 枚を整えました（位置情報を外した数：{sum(x['gps_removed'] for x in items)}）")
    for x in items:
        note = "・".join(x["flags"]) if x["flags"] else ""
        print(f"  {x['no']}: {x['file']}  ← {Path(x['src']).name}  {note}")
    print(f"指示文：{(TODAY / 'prompt.txt').relative_to(ROOT)}")
    return 0


# ───────────────────────── add ─────────────────────────
def summarize(row: dict, tags: dict[int, dict]) -> list[str]:
    """人に見せる3〜5行。判定はしない。『候補』と『次の一手』だけ。"""
    lines = []
    text = row["本文"]
    hits = [f"{kw}（{dt.rule_label(text, kw)}）" for kw in dt.KEYWORDS if kw in text]
    syn = [kw for kw, pats in dt.SYNONYMS.items() for p in pats if re.search(p, text) and kw not in text]
    lines.append("📝 本文の候補：" + ("、".join(hits + [f"{k}（言い換え）" for k in syn]) or "困りごとの語なし"))
    sig = [f"{k} {t[k]:.1f}（{n}枚目）" for n, t in tags.items() for k in dt.KEYWORDS if t[k] >= 0.5]
    if tags:
        lines.append("📷 写真の手がかり：" + ("、".join(sig) or "なし（0.5 未満）"))
    obs = {}
    for t in tags.values():
        for part in str(t.get("観察", "")).split(";"):
            b = part.split(":", 2)
            if len(b) >= 2 and b[0] in dv.OBS and float(b[1]) >= 0.5:
                obs[b[0]] = max(obs.get(b[0], 0.0), float(b[1]))
    for k in sorted(obs, key=obs.get, reverse=True)[:3]:
        lines.append(f"🌱 {k}（{obs[k]:.1f}）→ {dv.OBS[k][1]}")
    shots = sorted({t["次の1枚"] for t in tags.values() if t.get("次の1枚") not in ("", "なし")})
    if shots:
        lines.append("📸 次に撮る1枚：" + "、".join(shots))
    return lines


def cmd_add(args) -> int:
    items = manifest() if not args.no_photos else []
    n = len(items)
    final = read_tags(args.final, n)
    proposal = read_tags(args.proposal, n) if args.proposal else {}
    if n and len(final) != n:
        print(f"✖ 確定タグが {len(final)}/{n} 枚分しかありません。足りない番号を確かめてください。")
        return 1

    names, partners = load_dict()
    text = dt.mask(dt.normalize(args.text), names, partners)
    left = dt.residual([text], names + partners)
    if left:
        print(f"✖ 伏せきれない語が残っています：{left}")
        return 1
    if args.who and args.who in names:
        print("✖ 記入者は仮名（記入者A など）にしてください。")
        return 1

    diary = load_diary()
    did = next_id(diary)
    day = args.date or date.today().isoformat()
    folder = day.replace("-", "")

    photo_rows, held, saved = [], [], []
    for x in items:
        t = final[x["no"]]
        src = ROOT / x["file"]
        name = f"{did}_{x['no']}.jpg"
        private = any(t[label] for label in dv.PRIVACY.values())
        dest = (HOLD / folder / name) if private else (ASSETS / folder / name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        (held if private else saved).append(name)
        if not private:
            photo_rows.append({"パス": dv.key(dest, ROOT), **{c: t.get(c, "") for c in dv.RESULT_COLS if c not in ("パス", "出どころ")},
                               "出どころ": SOURCE})

    row = {"ID": did, "日付": day, "記入者": args.who or "", "作業": args.work, "本文": text,
           "止まった時間(分)": str(args.minutes or 0), "写真": ";".join(saved + held)}
    PRIV.mkdir(parents=True, exist_ok=True)
    pd.concat([diary, pd.DataFrame([row])], ignore_index=True)[DIARY_COLS].to_csv(DIARY, index=False, encoding="utf-8-sig")

    if photo_rows:
        old = dv.load_results(PHOTO_AI)
        dv.merge_results(old, pd.DataFrame(photo_rows, columns=dv.RESULT_COLS)).to_csv(
            PHOTO_AI, index=False, encoding="utf-8-sig")
    if items:
        with TAGS_LOG.open("a", encoding="utf-8") as f:
            for x in items:
                f.write(json.dumps({"ID": did, "日付": day, "no": x["no"], "案": proposal.get(x["no"]),
                                    "確定": final[x["no"]]}, ensure_ascii=False, default=str) + "\n")

    print(f"✅ {did}（{day}・{args.work}）を記録しました。写真：公開 {len(saved)} 枚／保留 {len(held)} 枚")
    if held:
        print(f"   保留（顔・ナンバー・看板・文字が写っている）：{', '.join(held)} → data/private/hold/{folder}/")
    for line in summarize(row, final):
        print("   " + line)
    if not args.keep:
        shutil.rmtree(TODAY, ignore_errors=True)
        for x in items:
            s = Path(x["src"])
            if s.is_relative_to(INBOX) and s.exists():
                (INBOX / "done").mkdir(exist_ok=True)
                shutil.move(str(s), INBOX / "done" / s.name)
    return 0


# ───────────────────────── week ─────────────────────────
def agreement_table(log: list[dict]) -> pd.DataFrame:
    rows = []
    pairs = [(r["案"], r["確定"]) for r in log if r.get("案") and r.get("確定")]
    for f in TAG_FIELDS:
        if f in dt.KEYWORDS:   # 確信度は 0.5 で「あり/なし」にそろえて比べる
            same = sum((a[f] >= 0.5) == (b[f] >= 0.5) for a, b in pairs)
        else:
            same = sum(str(a.get(f, "")) == str(b.get(f, "")) for a, b in pairs)
        rows.append({"項目": f, "一致": same, "枚数": len(pairs),
                     "一致率": f"{same / len(pairs):.0%}" if pairs else "—"})
    return pd.DataFrame(rows)


def cmd_week(args) -> int:
    end = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else date.today()
    start = end - timedelta(days=args.days - 1)
    diary = load_diary()
    d = diary[(pd.to_datetime(diary["日付"]).dt.date >= start) & (pd.to_datetime(diary["日付"]).dt.date <= end)] \
        if len(diary) else diary
    n_days = args.days
    days_written = d["日付"].nunique() if len(d) else 0

    hits = dt.hit_table(d) if len(d) else pd.DataFrame(columns=["ID", "語", "規則の判定"])
    syn = dt.synonym_hits(d) if len(d) else pd.DataFrame(columns=["ID", "分類"])
    mins = pd.to_numeric(d.get("止まった時間(分)", pd.Series(dtype=str)), errors="coerce").fillna(0)
    stop = d.assign(分=mins).groupby("作業")["分"].sum().sort_values(ascending=False) if len(d) else pd.Series(dtype=float)

    log = [json.loads(l) for l in TAGS_LOG.read_text(encoding="utf-8").splitlines()] if TAGS_LOG.exists() else []
    ids = set(d["ID"]) if len(d) else set()
    log_w = [r for r in log if r["ID"] in ids]
    obs = {}
    shots = []
    for r in log_w:
        t = r["確定"]
        for part in str(t.get("観察", "")).split(";"):
            b = part.split(":", 2)
            if len(b) >= 2 and b[0] in dv.OBS and float(b[1]) >= 0.5:
                obs.setdefault(b[0], []).append(r["ID"])
        if t.get("次の1枚") not in ("", "なし", None):
            shots.append(f"{r['ID']}-{r['no']}：{t['次の1枚']}")

    L = [f"# 作業日誌 {'週報' if args.days <= 7 else '月報'}（{start}〜{end}）", "",
         "> 数えたのはコンピュータ。**困りごとかどうかを決めるのは、原文を読んだ人**です。", "",
         "## 分母", f"- 日誌 **{len(d)} 件**／記入した日 **{days_written} / {n_days} 日**"
         + ("（書いていない日がある＝「問題なし」の日も1行書く）" if days_written < n_days else ""), "",
         "## 困りごとの候補（本文・規則の仮判定）", "", "| 語 | 困りごと候補 | 打ち消し | 該当ID |", "|---|---|---|---|"]
    for kw in dt.KEYWORDS:
        h = hits[hits["語"] == kw]
        L.append(f"| {kw} | {(h['規則の判定'] == '困りごと').sum()} 件 | {(h['規則の判定'] == '否定').sum()} 件 | "
                 f"{', '.join(h['ID'].astype(str)) or '—'} |")
    if len(syn):
        L.append(f"\n言い換えでだけ拾えたもの：{', '.join(f'{a}（{b}）' for a, b in zip(syn['ID'], syn['分類']))}")
    L += ["", "## 止まった時間（作業別）", ""]
    L += [f"- {k}：{int(v)} 分" for k, v in stop.items() if v > 0] or ["- 記録なし"]
    L += ["", "## 写真から見えた圃場の状態（確信度 0.5 以上）", ""]
    L += [f"- **{k}**：写真 {len(v)} 枚（日誌 {', '.join(sorted(set(v)))}）→ {dv.OBS[k][1]}" for k, v in obs.items()] or ["- なし"]
    L += ["", "## 次に撮る写真", ""] + ([f"- {s}" for s in shots] or ["- なし"])
    ag = agreement_table(log_w)
    L += ["", "## Claude の案と人の確定の一致率（どこまで任せられるか）", "",
          "| 項目 | 一致 / 枚数 | 一致率 |", "|---|---|---|"]
    L += [f"| {r.項目} | {r.一致} / {r.枚数} | {r.一致率} |" for r in ag.itertuples()]
    L += ["", "## 人が読む順番（原文に戻る）", "",
          "次の ID の本文を読み、「本当に困りごとか」を判定してください：" +
          (", ".join(sorted(set(hits.loc[hits['規則の判定'] == '困りごと', 'ID'].astype(str)))) or "なし")]

    REPORTS.mkdir(parents=True, exist_ok=True)
    tag = f"{end.isocalendar().year}-W{end.isocalendar().week:02d}" if args.days <= 7 else f"{end:%Y-%m}"
    out = REPORTS / f"{'weekly' if args.days <= 7 else 'monthly'}_{tag}.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    print(f"\n→ {out.relative_to(ROOT)}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prep", help="写真を整える（位置情報を外す・縮小）")
    p.add_argument("paths", nargs="*")
    p = sub.add_parser("prompt", help="写真タグの指示文を表示")
    p.add_argument("--n", type=int, default=1)
    p = sub.add_parser("add", help="日誌1件と写真タグを記録する")
    p.add_argument("--date")
    p.add_argument("--who", default="")
    p.add_argument("--work", required=True, choices=WORKS)
    p.add_argument("--text", required=True)
    p.add_argument("--minutes", type=int, default=0)
    p.add_argument("--proposal", help="Claude の最初の案（一致率の計算用）")
    p.add_argument("--final", help="人が確かめた確定版")
    p.add_argument("--no-photos", action="store_true")
    p.add_argument("--keep", action="store_true", help="作業場所と inbox を片づけない")
    p = sub.add_parser("week", help="週報（--days 31 で月報）")
    p.add_argument("--end")
    p.add_argument("--days", type=int, default=7)
    a = ap.parse_args(argv)
    if a.cmd == "prompt":
        print(dv.prompt(a.n))
        return 0
    return {"prep": cmd_prep, "add": cmd_add, "week": cmd_week}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())

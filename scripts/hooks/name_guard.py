"""
Claude Code の UserPromptSubmit フック：伏せる名前の辞書（data/private/mask_dict.txt）に載った
氏名・取引先名が、送る前のメッセージに入っていたら止める（Claude に届く前に止まる）。

止まったら：名前を「記入者A」「［取引先］」などに書きかえて、もう一度送ってください。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DICT = ROOT / "data" / "private" / "mask_dict.txt"


def words() -> list[str]:
    if not DICT.exists():
        return []
    out = []
    for line in DICT.read_text(encoding="utf-8").splitlines():
        w = line.strip()
        if not w or w.startswith("#"):
            continue
        for head in ("取引先:", "取引先："):
            if w.startswith(head):
                w = w[len(head):].strip()
        if len(w) >= 2:  # 1文字の語は誤検出が多いので見ない
            out.append(w)
    return out


def main() -> int:
    try:
        prompt = json.load(sys.stdin).get("prompt", "")
    except Exception:  # noqa: BLE001  フックが壊れても作業は止めない
        return 0
    hit = sorted({w for w in words() if w in prompt})
    if hit:
        print(f"🛑 伏せる名前が入っています（{len(hit)} 語）。仮名（記入者A・［取引先］など）に書きかえて送り直してください。",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

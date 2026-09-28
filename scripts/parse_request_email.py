#!/usr/bin/env python3
"""解析 .eml 需求信：標頭、內文、附件（含 SHA-256）。

用法:
    python3 parse_request_email.py mail.eml
    python3 parse_request_email.py mail.eml --body           # 連內文一起印
    python3 parse_request_email.py --diff a.eml b.eml        # 逐字元比對兩封信

為什麼要算附件的 SHA-256：同一封需求信常被寄兩次；附件雜湊相同代表版本一致，
差異只在正文，這樣就能聚焦在真正改變的地方。
"""
import argparse
import difflib
import email
import hashlib
import sys
from email import policy
from pathlib import Path


def load(path: Path):
    with path.open("rb") as fh:
        return email.message_from_binary_file(fh, policy=policy.default)


def bodies(msg):
    """回傳 [(content_type, text), ...]"""
    out = []
    for part in msg.walk():
        ct = part.get_content_type()
        if ct in ("text/plain", "text/html") and not part.get_filename():
            try:
                out.append((ct, part.get_content()))
            except Exception:
                pass
    return out


def attachments(msg):
    out = []
    for part in msg.walk():
        name = part.get_filename()
        if not name:
            continue
        payload = part.get_payload(decode=True) or b""
        out.append((name, len(payload), hashlib.sha256(payload).hexdigest()))
    return out


def show(msg, path: Path, with_body: bool) -> None:
    print("=" * 72)
    print(f"檔案      : {path}")
    for label, key in (("寄件者", "From"), ("收件者", "To"),
                       ("副本", "Cc"), ("日期", "Date"), ("主旨", "Subject")):
        if msg.get(key):
            print(f"{label:<10}: {msg.get(key)}")
    atts = attachments(msg)
    print(f"附件 ({len(atts)})")
    for name, size, digest in atts:
        print(f"  - {name}  ({size} bytes)  sha256={digest[:16]}…")
    if with_body:
        for ct, text in bodies(msg):
            print("-" * 72)
            print(f"[{ct}]")
            print(text)
    print()


def diff(a: Path, b: Path) -> int:
    ma, mb = load(a), load(b)
    ta = "".join(t for _, t in bodies(ma))
    tb = "".join(t for _, t in bodies(mb))
    if ta == tb:
        print("正文完全相同")
    else:
        print("正文差異（逐行）：")
        for line in difflib.unified_diff(
                ta.splitlines(), tb.splitlines(),
                fromfile=str(a), tofile=str(b), lineterm="", n=1):
            print(line)
    sa = {d for _, _, d in attachments(ma)}
    sb = {d for _, _, d in attachments(mb)}
    print()
    print("附件完全相同:", sa == sb)
    print("提醒：差異處不要自行取捨，回報需求方確認。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="解析 .eml 需求信")
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--body", action="store_true", help="一併印出內文")
    ap.add_argument("--diff", action="store_true", help="比對前兩個檔案")
    args = ap.parse_args()

    if args.diff:
        if len(args.files) != 2:
            print("--diff 需要正好兩個檔案", file=sys.stderr)
            return 2
        return diff(*args.files)

    for p in args.files:
        if not p.exists():
            print(f"找不到 {p}", file=sys.stderr)
            continue
        show(load(p), p, args.body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

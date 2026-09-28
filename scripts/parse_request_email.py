#!/usr/bin/env python3
"""解析 .eml 需求信：標頭、內文、附件（含 SHA-256）。

用法:
    python3 parse_request_email.py mail.eml
    python3 parse_request_email.py mail.eml --body           # 連內文一起印（憑證欄位會遮蔽）
    python3 parse_request_email.py --diff a.eml b.eml        # 逐字元比對兩封信

安全設計:
    本工具**刻意**遮蔽密碼類欄位，且沒有關閉遮蔽的選項。
    需求信幾乎一定會夾帶密碼；agent 讀信時不該把它印進對話或日誌。

    遮蔽後仍要判斷「是不是同一組密碼」時，會附上該值的 sha256 前綴
    （例如 `[REDACTED sha256:a1b2c3d4]`）：前綴相同=同值，不同=值不同。
    既能判斷差異，又不揭露內容。

為什麼要算附件的 SHA-256:
    同一封需求信常被寄兩次；附件雜湊相同代表版本一致，差異只在正文，
    這樣就能聚焦在真正改變的地方。
"""
import argparse
import difflib
import email
import hashlib
import re
import sys
from email import policy
from pathlib import Path

# 「一整行就是某個憑證欄位」的形式
SECRET_LINE = re.compile(
    r"(?im)^(\s*)(pw|passwd|pass(word)?|パスワード|初期パスワード|一時パスワード|"
    r"secret|token|api[ _-]?key|復原碼|recovery[ _-]?code)\s*[:：]\s*(?!\[REDACTED)(\S.*)$"
)
# 行內「標籤：值」的形式（負向先行斷言避免把已遮蔽的值再遮一次）
SECRET_INLINE = re.compile(
    r"(?i)(pw|pass(word)?|パスワード|secret|token)\s*[:：]\s*(?!\[REDACTED)([^\s,;|]+)"
)


def _mask_value(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8", "ignore")).hexdigest()[:8]
    return "[REDACTED sha256:" + digest + "]"


def mask(text: str) -> str:
    """遮蔽文字中的憑證類欄位。"""
    def line_sub(m):
        return m.group(1) + m.group(2) + ": " + _mask_value(m.group(4))

    text = SECRET_LINE.sub(line_sub, text)
    text = SECRET_INLINE.sub(lambda m: m.group(1) + ": " + _mask_value(m.group(3)), text)
    return text


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
    print("檔案      : " + str(path))
    for label, key in (("寄件者", "From"), ("收件者", "To"),
                       ("副本", "Cc"), ("日期", "Date"), ("主旨", "Subject")):
        if msg.get(key):
            print(label + ": " + mask(msg.get(key)))
    atts = attachments(msg)
    print("附件 (" + str(len(atts)) + ")")
    for name, size, digest in atts:
        print("  - " + name + "  (" + str(size) + " bytes)  sha256=" + digest[:16] + "…")
    if with_body:
        for ct, text in bodies(msg):
            print("-" * 72)
            print("[" + ct + "]")
            print(mask(text))
    print()


def diff(a: Path, b: Path) -> int:
    ma, mb = load(a), load(b)
    ta = mask("".join(t for _, t in bodies(ma)))
    tb = mask("".join(t for _, t in bodies(mb)))
    if ta == tb:
        print("正文完全相同")
    else:
        print("正文差異（逐行；憑證類欄位已遮蔽為 sha256 前綴，前綴不同＝值不同）:")
        for line in difflib.unified_diff(
                ta.splitlines(), tb.splitlines(),
                fromfile=str(a), tofile=str(b), lineterm="", n=1):
            print(line)
    sa = set(d for _, _, d in attachments(ma))
    sb = set(d for _, _, d in attachments(mb))
    print()
    print("附件完全相同:", sa == sb)
    print("提醒：差異處不要自行取捨，回報需求方確認。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="解析 .eml 需求信（憑證欄位自動遮蔽）")
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--body", action="store_true", help="一併印出內文（憑證會遮蔽）")
    ap.add_argument("--diff", action="store_true", help="比對前兩個檔案")
    args = ap.parse_args()

    if args.diff:
        if len(args.files) != 2:
            print("--diff 需要正好兩個檔案", file=sys.stderr)
            return 2
        return diff(*args.files)

    for p in args.files:
        if not p.exists():
            print("找不到 " + str(p), file=sys.stderr)
            continue
        show(load(p), p, args.body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

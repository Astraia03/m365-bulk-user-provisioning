#!/usr/bin/env python3
"""從人員名單產生 Microsoft 365 管理センター（日文介面）可匯入的 CSV。

用法:
    python3 build_import_csv.py roster.csv --domain example.onmicrosoft.com --out Import_Users.csv
    python3 build_import_csv.py roster.csv --domain example.onmicrosoft.com --default-country 台湾

roster.csv 表頭（alias/last/first 必要，其餘可留空）:
    alias,last,first,display,job_title,department,office,work_phone,mobile,fax,email,street,city,prefecture,zip,country

說明:
    - 輸出 UTF-8 BOM + CRLF，管理センター與 Excel 皆可讀
    - 表頭順序對應官方模板；介面語言不同時表頭也不同，
      建議先從管理センター下載一次空白模板核對
    - 國別要用當地語系標籤（實測台灣 = 台湾），不是英文國名
"""
import argparse
import csv
import sys
from pathlib import Path

HEADER = ["ユーザー名", "名", "姓", "表示名", "役職", "部署", "事業所番号",
          "職場の電話", "携帯電話", "FAX", "連絡用メール アドレス",
          "住所", "市区町村", "都道府県", "郵便番号", "国または地域"]

FIELDS = ["alias", "first", "last", "display", "job_title", "department", "office",
          "work_phone", "mobile", "fax", "email",
          "street", "city", "prefecture", "zip", "country"]


def main() -> int:
    ap = argparse.ArgumentParser(description="產生 M365 管理センター 匯入 CSV")
    ap.add_argument("roster", help="人員名單 CSV")
    ap.add_argument("--domain", required=True, help="UPN 網域，例如 example.onmicrosoft.com")
    ap.add_argument("--out", default="Import_Users.csv", help="輸出檔名")
    ap.add_argument("--default-country", default="台湾", help="未指定國別時的預設值（當地語系標籤）")
    args = ap.parse_args()

    src = Path(args.roster)
    if not src.exists():
        print(f"找不到 {src}", file=sys.stderr)
        return 2

    rows, seen = [], set()
    with src.open(encoding="utf-8-sig", newline="") as fh:
        for i, rec in enumerate(csv.DictReader(fh), start=2):
            rec = {k: (v or "").strip() for k, v in rec.items() if k}
            alias = rec.get("alias", "")
            if not alias:
                print(f"第 {i} 列缺 alias，略過", file=sys.stderr)
                continue
            if alias in seen:
                print(f"第 {i} 列 alias 重複：{alias}，略過", file=sys.stderr)
                continue
            seen.add(alias)
            upn = alias if "@" in alias else f"{alias}@{args.domain}"
            first, last = rec.get("first", ""), rec.get("last", "")
            display = rec.get("display") or f"{last}{first}"
            rows.append([
                upn, first, last, display,
                rec.get("job_title", ""), rec.get("department", ""), rec.get("office", ""),
                rec.get("work_phone", ""), rec.get("mobile", ""), rec.get("fax", ""),
                rec.get("email", ""), rec.get("street", ""), rec.get("city", ""),
                rec.get("prefecture", ""), rec.get("zip", ""),
                rec.get("country", "") or args.default_country,
            ])

    if not rows:
        print("沒有任何有效資料列", file=sys.stderr)
        return 1

    with open(args.out, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(HEADER)
        w.writerows(rows)

    print(f"已寫出 {args.out}：{len(rows)} 筆")
    print(f"  UPN 網域：{args.domain}")
    print(f"  預設國別：{args.default_country}")
    print("提醒：匯入前先與需求方核對人數與授權數量。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# 網域關卡：免費子網域（dynv6）+ M365 網域驗證

目標：讓測試租戶有一個「自訂網域」，員工 UPN 與信箱不必掛在 `@<tenant>.onmicrosoft.com`，
而且**不用花錢買網域**。dynv6 提供免費子網域（`dynv6.net` / `dns.army` / `v6.rocks` 等）
以及可程式化的 DNS API。

## 0. 為什麼要這樣做
- M365 的自訂網域必須「證明你擁有它」（DNS TXT 或 MX）
- 員工 UPN、SMTP 位址、SPF／DKIM／DMARC 全部要掛在這個網域上
- 測試情境不想牽涉採購，所以用免費子網域；**但它不是企業級**（dynv6 官網自述：無 SLA、無企業級 DDoS 防護）

## 1. 申請（人機分工）
| 步驟 | 誰做 |
|---|---|
| 註冊帳號（Email + 密碼 + 確認密碼） | 密碼由**人**輸入（agent 不代打）；位置較低調的同意橫幅也由人處理 |
| 收確認信、點連結 | **人**（帳號未確認前，zone 不會啟用） |
| 建立 zone、產生／取得 API token | agent 可代操，token 走安全儲存 |

**註冊頁沒有 CAPTCHA**（實測），所以人只需要：填密碼 + 點確認信。

## 2. 三個必踩的坑（實測）

### 坑 1：`name` 是**相對**名稱，不是 FQDN
REST API 建立記錄時，`name` 會被接上 zone 名稱。若你傳 FQDN：

```
傳入 name = "zone.dynv6.net"  →  實際變成 "zone.dynv6.net.zone.dynv6.net"（重複）
```

正確用法：
- **apex（zone 本身）** → `name` 傳 `"@"`（API 會正規化為空字串）

### 坑 2：MX／CNAME 的 `data` 也當成相對名稱
```
data = "autodiscover.outlook.com"   → autodiscover.outlook.com.<zone>（錯）
data = "autodiscover.outlook.com."  → autodiscover.outlook.com.（對，結尾加點）
```

**絕對目標一律在結尾加一個點。** TXT 的 data 是字面文字，不受影響。

### 坑 3：zone 的 token 會明文印在 Instructions 頁
`/zones/<id>/instructions` 的 ddclient 範例會直接把 token 秀出來 → 開那個頁面等於把憑證
寫進對話紀錄。**要拿 token 請走 `/keys` → `Details` → `Copy`**，再從剪貼簿落地到
600 權限的檔案。

另外：`element.click()` **不是受信任的使用者手勢**，複製到剪貼簿會靜默失敗。
要用真實滑鼠事件（CDP `Input.dispatchMouseEvent`）點。

## 3. REST API 用法（實測可用）
- Endpoint：`https://dynv6.com/api/v2/zones/{zoneID}/records`
- 認證：**Keys 頁的 HTTP token 直接當 Bearer 用**（同一個 token 也供 Update API 使用）
- 支援型別：A / AAAA / CAA / CNAME / MX / SPF / SRV / TXT
- MX 的優先度放在 `priority` 欄位

```bash
TOKEN=$(cut -d= -f2- ~/.hermes/.dynv6.env)
ZONE=1234567
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://dynv6.com/api/v2/zones/$ZONE/records"

curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"@","type":"MX","priority":0,"data":"<tenant>.mail.protection.outlook.com."}' \
  "https://dynv6.com/api/v2/zones/$ZONE/records"
```

## 4. M365 端的流程
1. 管理センター → 設定 → **ドメイン** → 「ドメインの追加」
2. 輸入網域名稱 → 選「TXT レコードを追加」→ **続行**
3. 畫面會給你 `TXT 名` 與 `TXT 値`（`MS=msXXXXXXXX`）
4. 用 API 把 TXT 加到 zone 的 apex（`name="@"`）
5. **等公開 DNS 查得到**（用 DoH 查，比本機 `dig` 可靠）→ 回精靈按「確認」
6. 驗證通過後進入「ドメインの接続」→ 選「自分の DNS レコードを追加する」
   - **這裡一定要下載它的 CSV 或 zone file，不要用截圖／爬 DOM 猜值**
     （畫面按鈕：「CSV ファイルをダウンロード」）
7. 依 CSV 建立 MX / Autodiscover CNAME / SPF TXT（記得坑 2 的結尾點）
8. 回精靈按「続行」讓它複查 → 完成後網域狀態會變「正常」

## 5. 驗證（每一步都要做，不要憑畫面宣稱成功）
```bash
# 用 DoH 查，不受本機 resolver 快取影響
curl -s -H "accept: application/dns-json" \
  "https://cloudflare-dns.com/dns-query?name=<zone>&type=TXT"
# 也直接問權威伺服器（dynv6 有 3 台，傳播可能不同步）
dig +short @ns1.dynv6.com MX <zone>
```

**dynv6 的三台 NS 可能短暫回不同內容**——看到新舊值交錯時等 1 分鐘再查，
不要立刻判定失敗或重複建立記錄。

## 6. 停止條件（依計畫）
- 網域被 M365 拒絕 → 保留實際錯誤、**停止此關卡**，不改用公司正式網域、不自動購買付費網域
- 免費子網域只供能力測試：其可靠性、寄送信譽、管理權都**不等同**企業正式網域
- 郵件寄達 ≠ SPF／DKIM／DMARC 通過；要用完整郵件標頭驗證

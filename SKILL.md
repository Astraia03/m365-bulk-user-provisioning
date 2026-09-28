---
name: m365-bulk-user-provisioning
description: Use when bulk-provisioning M365 users from a request.
version: 1.0.0
author: Astraia03
license: MIT
metadata:
  hermes:
    tags: [m365, entra, onboarding, provisioning, 1password, browser-automation, csv-import]
    related_skills: [hermes-1password-vault]
---

# M365 批次建立使用者與派發授權

從「收到需求」到「驗證完成」的完整流程。主軸是 Microsoft 365 管理センター的
**CSV 批次匯入**；CSV 做不到的部分（主管鏈、優先語言、employeeId）用 Graph API 補。

## When to Use
- 收到含人員清單／部門／職稱／授權規則的需求（信件、工單、試算表），要在 M365 租戶批次建立帳號
- 要派發授權並**驗證**建立結果
- 要重跑、交接或稽核這條流程（換人、換 harness 都適用）

## 硬規則（不可妥協）
1. **密碼／TOTP 種子／API token 絕不進對話，也絕不進命令列輸出。**
   讀取時重導向到檔案或 `pbcopy`，只印長度／型別／前綴。
2. **不代替使用者輸入密碼。** 走憑證管理員注入，或讓使用者在遮蔽提示中自行輸入。
3. **MFA 由使用者處理，不嘗試繞過。** Entra security defaults 為伺服器端強制
   （2024/7 起移除寬限期）；也不要建議關閉它或關閉 CA 政策。
4. **含臨時密碼的輸出檔 `chmod 600`，且不貼進對話。**
5. **建帳號是不可逆寫入 → 動手前先與需求方確認範圍**（人數、UPN 規則、授權種類、是否覆蓋既有帳號）。

---

## Phase 0 — 解析需求
目的：把信件變成一份可執行的規格。

1. 存下原始 `.eml`（Outlook for Mac：`ファイル → 名前を付けて保存…`）。
2. `python3 scripts/parse_request_email.py <file.eml> [more.eml] [--body]`
   → 列出主旨、寄件者、時間、內文、附件清單與 **SHA-256**。
3. **同一封信收到多份時，逐字元 diff。** 實務上真的會出現「只差一個字元」的情況
   （例如管理員密碼的末字元）。此時以**內文與截圖為準**，並向需求方確認——
   不要自己挑一份。附件 SHA-256 相同，就代表差異只在正文。
4. 抽出規格：帳號數量、UPN／alias 命名規則、姓名、部門、職稱、地點、
   **授權種類與數量**、禁止事項。
5. **矛盾或缺漏一律問，不要猜。**（數量對不上、授權庫存不足、欄位沒給、
   附件與任務無關的檔案也要提出來問。）

→ 產出一份規格表，請需求方確認後才往下走。

## Phase 1 — 憑證就緒
目標：讓自動化能取得密碼與 TOTP，而人類不必把密碼貼給它。

- **1Password 路線（推薦）**：見 `references/credential-harness-setup.md`
  - 服務帳戶 token → `<HERMES_HOME>/.op.env`（`chmod 600`）
  - 項目必須放在**自訂 vault**：服務帳戶讀不到內建 Personal / Private / **Employee** / 預設 Shared
  - 服務帳戶模式下 `op item get` 必須帶 `--vault` → 用 wrapper 補（reference 內有原始碼）
- 沒有 1Password 時：用 harness 自帶的本地憑證庫，或讓使用者在遮蔽提示中輸入。

## Phase 2 — 登入租戶
1. 開 `https://admin.cloud.microsoft/`
2. 填管理員 UPN
3. 由憑證管理員注入密碼
4. 需要 MFA 時，由憑證管理員**產生並填入 TOTP**
   （沒有 TOTP 種子就停下來交還使用者，不要嘗試繞過）
5. **確認登入成功才往下走**：看到管理センター主頁／租戶名稱。

> 想重測登入、又不想登出使用者的其他工作階段：用 `prompt=login` 授權 URL，
> 見 `references/credential-harness-setup.md`。**不要用 logout 端點。**

## Phase 3 — 租戶盤點（動手前必做）
| 檢查 | 位置 | 為什麼 |
|---|---|---|
| 現有使用者 | ユーザー → アクティブなユーザー | 避免 UPN 衝突、算清楚淨增人數 |
| 可用授權 | 課金情報 → ライセンス | 庫存必須 ≥ 需求；不足先回報 |
| 網域 | 設定 → ドメイン | 決定 UPN 用哪個網域 |
| 命名規則 | 對照需求 | 統一 alias 格式 |

## Phase 4 — 產生匯入 CSV
用 `scripts/build_import_csv.py`，欄位規格見 `references/csv-import-format.md`。

最容易錯的三件事：
1. **表頭是管理センター的介面語言。** 最保險：先從管理センター下載官方空白模板，
   照它的表頭填。日文介面的表頭見 reference。
2. **`ユーザー名` 要放完整 UPN**，不是裸 alias。
3. **`国または地域` 要用當地語系標籤**（台灣＝`台湾`，不是 `Taiwan`）。
   可從頁面 `window.m365config.supportCentralConfig.SupportedRegions` 查證。

## Phase 5 — 批次建立
1. ユーザー → アクティブなユーザー → **複数のユーザーの追加**（`#/addmultipleusers`）
2. 選 CSV 模式 → 掛上檔案
   - 用 CDP 自動化時 `DOM.setFileInputFiles` **不會觸發 React 的 onChange**，
     要補 `dispatchEvent(new Event('change', {bubbles: true}))`
3. 「次へ」→ 確認解析結果（人數、地點是否自動帶入）
4. 勾選授權 → 確認頁 → 執行
5. 完成後**下載含臨時密碼的明細**，立刻 `chmod 600` 並移到安全位置

## Phase 6 — 驗證（不可跳過）
| 驗證項 | 期望 |
|---|---|
| 使用者總數 | 既有 + 新增，逐一核對 |
| 授權派發 | 「割り当て済み / 總數」等於需求數量 |
| 抽查屬性 | 姓／名／表示名／部署／国 都正確 |
| 登入測試 | 至少一個新帳號能完成登入（走 Phase 2 的流程） |

只看「使用者數」或只看「授權數」都會漏——**兩者都要核對**。

## Phase 7 — CSV 做不到的部分
管理センター的 CSV 匯入**不支援**主管鏈（manager）、優先語言（preferredLanguage）、
employeeId。要這些得走 Graph API：見 `references/graph-api-post-import.md`。

---

## 常見坑（實際踩過的）
- **MFA 無法跳過**：security defaults 對全體強制。正解是準備好 TOTP，不是想辦法繞過。
- **需求信可能有兩個版本**：先 diff、問清楚，不要自己選。
- **服務帳戶讀不到內建 vault**：項目要先搬到自訂 vault。
  `op item move` **只在同一帳號內**有效，跨帳號只能重建項目。
- **匯入檔的國別要用當地語系標籤。**
- **CDP 設檔案要補 `change` 事件**，否則前端的檔案狀態不會更新。
- **CSV 匯入欄位支援有限**（Phase 7）。
- **`op signin --raw` 在 1Password App 整合模式下不回 token**，所以「解鎖」那條路走不通，
  要用服務帳戶 token。細節見 reference。
- **憑證管線通了不代表資料對**：填入成功但網站拒絕，通常是項目裡的密碼本身錯了。
  用長度／雜湊比對診斷，不要印出字元。

## 交接檢查清單
- [ ] 需求規格已與需求方確認（含矛盾點與無關附件）
- [ ] 憑證全程經管理員注入，未出現於對話或日誌
- [ ] 匯入 CSV 的表頭與國別標籤正確
- [ ] 建立後已下載臨時密碼明細並 `chmod 600`
- [ ] 使用者數**與**授權派發數都已核對
- [ ] 已抽查屬性、已用至少一個新帳號測試登入
- [ ] 未完成項（主管鏈／語言／employeeId）已明確列給需求方
- [ ] 授權／token 的到期日已記錄

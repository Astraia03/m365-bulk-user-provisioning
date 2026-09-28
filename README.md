# m365-bulk-user-provisioning

M365 批次建立使用者與派發授權的 **agent-agnostic** 流程技能。
可用於 Hermes、Claude Code、Codex 以及其他支援 `SKILL.md` / `AGENTS.md` 的 harness。

流程涵蓋：解析需求信件 → 憑證就緒（1Password）→ 登入租戶 → 租戶盤點 →
產生匯入 CSV → 批次建立 → 派發授權 → 驗證 → 補齊 CSV 做不到的欄位。

## 安裝

### Hermes
```bash
ln -s "$(pwd)" ~/.hermes/skills/m365-bulk-user-provisioning
# 或複製：cp -R . ~/.hermes/skills/m365-bulk-user-provisioning
```

### Claude Code
```bash
mkdir -p ~/.claude/skills
ln -s "$(pwd)" ~/.claude/skills/m365-bulk-user-provisioning
```

### Codex / 其他 harness
把 `SKILL.md` 的內容併進專案的 `AGENTS.md`，或在 prompt 中直接指向
`SKILL.md` 的絕對路徑請 agent 讀取。

## 檔案結構

| 路徑 | 內容 |
|---|---|
| `SKILL.md` | 主流程：Phase 0–7、硬規則、檢查清單 |
| `references/credential-harness-setup.md` | 1Password 服務帳戶、`op` wrapper、瀏覽器憑證注入 |
| `references/csv-import-format.md` | 管理センター匯入 CSV 欄位、國別標籤、驗證方式 |
| `references/graph-api-post-import.md` | 主管鏈／優先語言／employeeId 的 Graph 指令 |
| `scripts/parse_request_email.py` | 解析 `.eml`：標頭、內文、附件 SHA-256 |
| `scripts/build_import_csv.py` | 從名單產生可匯入的 CSV |
| `scripts/op-hermes-vault` | `op item get` 補 `--vault` 的 wrapper |

## 硬規則

1. 密碼／TOTP 種子／token 不進對話、不進命令列輸出
2. 不代替使用者輸入密碼
3. MFA 由使用者處理，不嘗試繞過
4. 含臨時密碼的輸出檔 `chmod 600`
5. 建帳號前先確認範圍

## 不含什麼

本技能**不含任何真實客戶資料或憑證**。所有範例都是佔位符
（`example.onmicrosoft.com`、`EMP001`、`admin@example.onmicrosoft.com`）。

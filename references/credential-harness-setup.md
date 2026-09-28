# 憑證管線設定（1Password → 瀏覽器自動填入）

目標：讓 agent 能取得密碼與 TOTP 並填入網頁，而**人類不必把密碼貼給它**。

## 為什麼不能走「解鎖主密碼」那條路
某些 harness 的 1Password 後端把主密碼餵給 `op signin --raw` 的 stdin，期待回傳 session token。
但 `op` 2.x 開啟 **App 整合（Integrate with 1Password CLI）** 後，`op signin` 既不讀 stdin
也不回 token（實測零輸出）→ 判斷永遠是「未解鎖」。

**正解：改用服務帳戶 token。** 與 App 整合無關，且可獨立撤銷。

## 1. 項目必須放在「自訂」vault
服務帳戶**不能**存取內建 vault：`Personal` / `Private` / `Employee` / 預設 `Shared`。
一定要先建一個自訂 vault 並把要用到的項目放進去。

```bash
op vault list                       # 列出可見 vault
op vault create "agent-vault" --account <account>
# 搬移只在「同一帳號內」有效；跨帳號只能重建項目
op item move <item-id> --current-vault <src> --destination-vault "agent-vault"
```

## 2. 建立服務帳戶並落地 token

```bash
op service-account create "agent-<用途>" --account <account> \
  --vault "agent-vault:read_items" --expires-in 90d --raw > /tmp/sa.txt

printf 'OP_SERVICE_ACCOUNT_TOKEN=%s\n' "$(cat /tmp/sa.txt)" > <HERMES_HOME>/.op.env
chmod 600 <HERMES_HOME>/.op.env
rm -f /tmp/sa.txt
```

- token **只顯示一次**，用重導向避免進 shell history
- 服務帳戶的**權限建立後不可修改**，要改只能重建
- 設 `--expires-in` 並把到期日記下來（例如放進交接清單）
- 驗證最小權限：帶 token 執行 `op vault list` 應該**只看得到授權的那個 vault**

## 3. wrapper：服務帳戶模式下 `op item get` 必須帶 `--vault`

服務帳戶認證時，`op item get <id>` 會直接拒絕：

```
a vault query must be provided when this command is called by a service account.
Please specify one either through the --vault flag or through piped input
```

但 harness 內部呼叫時不會帶 `--vault`。**不要改 harness 原始碼**——用 `binary_path`
之類的設定指到一個 wrapper，升級也不會被蓋掉。原始碼見 `scripts/op-hermes-vault`。

```bash
install -m 755 scripts/op-hermes-vault ~/.local/bin/op-agent-vault
# 1Password 的項目欄位填寫模式；把 vault 名稱改成實際授權的那個
hermes config set vault.onepassword.binary_path ~/.local/bin/op-agent-vault
# 還原： hermes config unset vault.onepassword.binary_path
```

## 4. 瀏覽器憑證注入

| 動作 | Hermes / browser-harness |
|---|---|
| 列出可填的登入 | `browser_vault_list` → 出現 `op:<item-id>` handle，且該後端不再列在 `locked` |
| 填帳號 | 自己用 `fill_input` 填 UPN（登入項目的 identifier 可從 handle 的中繼資料取得） |
| 填密碼 | `browser_vault_fill` + `op:<item-id>` |
| 填 TOTP | `browser_vault_enter_code` + **同一個 handle**（項目裡有 type=OTP 欄位就會自動產生） |

前置條件：瀏覽器必須可被 harness 接手（Hermes 需 `browser.cdp_url` 指向
`http://127.0.0.1:9222`，否則憑證注入掛不上）。

其他 harness 的對應物：Claude Code / Codex 沒有內建憑證注入，
改用「讓 `op` 讀出到環境變數 → 以腳本驅動瀏覽器」或請使用者在瀏覽器現有的
密碼管理員擴充功能中自行完成該次登入。

## 5. 驗證登入時不要登出使用者的工作階段

用 `prompt=login` 強制重新驗證即可（不影響瀏覽器內其他帳號）：

```
https://login.microsoftonline.com/common/oauth2/v2.0/authorize
  ?client_id=04b07795-8ddb-461a-bbee-02f9e1bf7b46   # Azure CLI 公開用戶端
  &response_type=code&redirect_uri=http%3A%2F%2Flocalhost
  &prompt=login&scope=openid+profile&login_hint=<UPN>
```

成功會導向 `http://localhost/?code=...`；**連線被拒是預期的**（代表已通過認證）。
通過 MFA 後可能出現「保護您的帳號」追加驗證方式提示，選「今はしない / Not now」跳過。

## 6. 紅線

- 密碼、TOTP 種子、token **一律不顯示**：讀取時重導向到檔案或 `pbcopy`，只印長度／型別／前綴
- 要使用者把值貼進 1Password 時，用 `pbcopy < file` 傳遞，不要印出來
- 診斷「密碼對不對」用**長度或雜湊比對**，不要印出字元

## 7. 除錯順序

1. 後端一直顯示 `locked` → 服務帳戶 token 沒生效（檢查 `.op.env` 與 harness 的 secret scope）
2. 填入報 `a vault query must be provided` → wrapper 沒套用（檢查 `binary_path` 設定）
3. 填入成功但網站拒絕 → **換到已知可用的憑證來源對照**，確認是資料問題而非管線問題
4. 完全連不上 → 瀏覽器沒有以遠端除錯埠啟動

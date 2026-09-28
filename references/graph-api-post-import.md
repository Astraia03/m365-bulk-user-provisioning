# CSV 匯入做不到的部分：Graph API 補齊

管理センター的 CSV 批次匯入**不支援**：
- 主管鏈（manager）
- 優先語言（preferredLanguage）
- employeeId

這些要建立後另外設。以下都需要 `User.ReadWrite.All` 權限。

## 取得權杖（最省事的兩種）

```bash
# Azure CLI（人在電腦前、有租戶權限時最快）
az login --tenant example.onmicrosoft.com --allow-no-subscriptions
TOKEN=$(az account get-access-token --resource https://graph.microsoft.com \
        --query accessToken -o tsv)
```

```powershell
# PowerShell + Microsoft Graph SDK
Connect-MgGraph -Scopes "User.ReadWrite.All"
```

長時間或無互動的環境改用**應用程式註冊**（client credentials），
把 client id / secret / tenant id 放進憑證管理員，不要寫進腳本。

## 設定主管

```bash
curl -sS -X PUT \
  "https://graph.microsoft.com/v1.0/users/kid@example.onmicrosoft.com/manager/\$ref" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"@odata.id": "https://graph.microsoft.com/v1.0/users/boss@example.onmicrosoft.com"}'
```

```powershell
$params = @{ "@odata.id" = "https://graph.microsoft.com/v1.0/users/boss@example.onmicrosoft.com" }
Set-MgUserManagerByRef -UserId "kid@example.onmicrosoft.com" -BodyParameter $params
```

## 優先語言與 employeeId

```bash
curl -sS -X PATCH \
  "https://graph.microsoft.com/v1.0/users/kid@example.onmicrosoft.com" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"preferredLanguage": "zh-TW", "employeeId": "EMP001"}'
```

`preferredLanguage` 用 BCP-47（繁中 = `zh-TW`）。

## 授權指派（若要改用 Graph）

指派前**必須先設 `usageLocation`**，否則會被拒：

```bash
curl -sS -X PATCH ".../users/<upn>" -d '{"usageLocation": "TW"}'
curl -sS -X POST ".../users/<upn>/assignLicense" -d '{
  "addLicenses":[{"skuId":"<sku-uuid>"}], "removeLicenses":[] }'
```

查 SKU：`GET /subscribedSkus`。

## 大量處理
- 每個物件都有速率限制；數十筆以上用 `$batch`（每批上限 20 個請求）
- 逐一呼叫時加退避重試，並把每次回應記錄下來（誰成功、誰失敗、為什麼）
- **完成後仍要做 Phase 6 的驗證**，不要只看 API 回 200

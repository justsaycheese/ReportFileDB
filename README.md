# ReportFileDB

ReportFileDB 是一個簡易的 SQLite 工具，協助你把常用的報告全文直接存進資料庫，
並透過類似同人圖庫（Danbooru）的樹狀子母標籤快速檢索舊資料。

## 功能特色

- ✅ 支援整篇報告或文件全文存放，懶得切段也沒問題。
- ✅ 可建立任意深度的標籤父子關係，搜尋父標籤時自動包含所有子孫標籤。
- ✅ 以 CLI 或 GUI 操作：新增報告、維護標籤、依標籤搜尋、匯出報告。

## 安裝與使用

1. 建議使用 Python 3.11 或更新版本。
2. 使用 CLI：

```bash
python -m reportdb_cli add-report "四月月報" --file ./reports/2024-04.md --tag 月報 --tag 財報
python -m reportdb_cli add-tag "財報/收入" --parent 財報
python -m reportdb_cli assign-tag 1 --tag "財報/收入"
python -m reportdb_cli search --tag 財報
```

`add-report` 指令支援 `--content`、`--file` 或 `--stdin`（從標準輸入讀取）。

3. 若想用圖形化介面，直接啟動 GUI：

```bash
python -m reportdb_gui
```

GUI 介面提供左側標籤樹與右側報告清單，可直接新增報告、建立標籤並匯出報告。

## 指令列表

| 指令 | 說明 |
| --- | --- |
| `add-report` | 新增報告，支援一次設定多個標籤。 |
| `add-tag` | 新增標籤，可指定父標籤建立子母樹。 |
| `set-parent` | 調整既有標籤的父標籤。 |
| `assign-tag` | 為既有報告補上標籤。 |
| `list-reports` | 列出所有報告，可選擇顯示內容。 |
| `list-tags` | 以樹狀結構顯示全部標籤。 |
| `search` | 依指定標籤（含所有子孫）搜尋報告。 |
| `export` | 將指定報告匯出成檔案。 |

## 開發筆記

- 所有資料存放於同目錄下的 `reportdb.sqlite3`（可用 `--database` 指定其他路徑）。
- 搜尋時會自動展開標籤的子孫節點，達成類似 Danbooru 的瀏覽體驗。
- 程式碼使用標準函式庫 `sqlite3`，不需額外安裝套件。

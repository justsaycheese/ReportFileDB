# ReportFileDB

ReportFileDB 是一個簡易的 SQLite 工具，協助你把常用的報告全文直接存進資料庫，
並透過類似同人圖庫（Danbooru）的樹狀子母標籤快速檢索舊資料。

## 功能特色

- ✅ 支援整篇報告或文件全文存放，懶得切段也沒問題。
- ✅ 可建立任意深度的標籤父子關係，搜尋父標籤時自動包含所有子孫標籤。

- ✅ 以 CLI 或 GUI 操作：新增 / 編輯 / 刪除報告、維護 / 刪除標籤、依標籤搜尋、匯出報告。
=======


## 安裝與使用

1. 建議使用 Python 3.11 或更新版本。
2. 使用 CLI：

```bash

 codex/add-tag-based-retrieval-system-for-reports-ljyr5q
python -m reportdb_cli edit-report 1 --title "四月財報總結" --tag 財報 --tag "財報/收入"
python -m reportdb_cli delete-report 1
python -m reportdb_cli delete-tag 財報 --cascade
=======

```

`add-report` 指令支援 `--content`、`--file` 或 `--stdin`（從標準輸入讀取）。

3. 若想用圖形化介面，直接啟動 GUI：

```bash
python -m reportdb_gui
```


GUI 介面提供左側標籤樹與右側報告清單，可直接新增 / 編輯 / 刪除報告、建立 / 刪除標籤並匯出內容。
=======


## 指令列表

| 指令 | 說明 |
| --- | --- |
| `add-report` | 新增報告，支援一次設定多個標籤。 |
| `add-tag` | 新增標籤，可指定父標籤建立子母樹。 |
| `set-parent` | 調整既有標籤的父標籤。 |
| `assign-tag` | 為既有報告補上標籤。 |
| `edit-report` | 編輯報告，支援更新標題、內容與標籤。 |
| `delete-report` | 依 ID 刪除報告。 |
| `delete-tag` | 刪除標籤，可搭配 `--cascade` 一併移除所有子標籤。 |
=======



## 開發筆記

- 所有資料存放於同目錄下的 `reportdb.sqlite3`（可用 `--database` 指定其他路徑）。
- 搜尋時會自動展開標籤的子孫節點，達成類似 Danbooru 的瀏覽體驗。
- 程式碼使用標準函式庫 `sqlite3`，不需額外安裝套件。

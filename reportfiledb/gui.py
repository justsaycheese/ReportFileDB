"""Tkinter GUI for ReportFileDB."""

from __future__ import annotations

import argparse
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, simpledialog, ttk
from typing import Dict, Optional

from .database import Report, ReportDatabase, Tag


@dataclass
class _TagNode:
    item_id: str
    tag: Optional[Tag]


class ReportApp:
    """Main application window for browsing and editing reports."""

    def __init__(self, root: tk.Tk, *, database: str = "reportdb.sqlite3") -> None:
        self.root = root
        self.root.title("ReportFileDB")
        self.db = ReportDatabase(database)

        self._tag_nodes: Dict[str, _TagNode] = {}
        self._reports: list[Report] = []

        self._build_ui()
        self._populate_tags()
        self._load_reports(None)

    # ------------------------------------------------------------------
    # UI 建立
    def _build_ui(self) -> None:
        self.root.geometry("1000x600")
        self.root.minsize(900, 500)

        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # 左側：標籤樹
        tag_frame = ttk.Frame(paned)
        paned.add(tag_frame, weight=1)

        tag_header = ttk.Label(tag_frame, text="標籤")
        tag_header.pack(anchor=tk.W, padx=8, pady=(8, 4))

        self.tag_tree = ttk.Treeview(tag_frame, show="tree")
        self.tag_tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.tag_tree.bind("<<TreeviewSelect>>", self._on_tag_selected)

        tag_buttons = ttk.Frame(tag_frame)
        tag_buttons.pack(fill=tk.X, padx=8, pady=(0, 8))

        ttk.Button(tag_buttons, text="新增標籤", command=self._add_tag).pack(side=tk.LEFT)
        ttk.Button(tag_buttons, text="重新整理", command=self._populate_tags).pack(side=tk.LEFT, padx=(8, 0))

        # 右側：報告與內容
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=3)

        report_header = ttk.Label(right_frame, text="報告清單")
        report_header.pack(anchor=tk.W, padx=8, pady=(8, 4))

        self.report_list = tk.Listbox(right_frame, exportselection=False)
        self.report_list.pack(fill=tk.BOTH, expand=False, padx=8, pady=(0, 8))
        self.report_list.bind("<<ListboxSelect>>", self._on_report_selected)
        self.report_list.configure(height=10)

        button_bar = ttk.Frame(right_frame)
        button_bar.pack(fill=tk.X, padx=8, pady=(0, 8))

        ttk.Button(button_bar, text="新增報告", command=self._add_report).pack(side=tk.LEFT)
        ttk.Button(button_bar, text="匯出報告", command=self._export_report).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(button_bar, text="重新整理", command=self._refresh_data).pack(side=tk.LEFT, padx=(8, 0))

        detail_header = ttk.Label(right_frame, text="報告內容")
        detail_header.pack(anchor=tk.W, padx=8, pady=(0, 4))

        detail_container = ttk.Frame(right_frame)
        detail_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self.detail_text = tk.Text(detail_container, wrap=tk.WORD)
        self.detail_text.pack(fill=tk.BOTH, expand=True)
        self.detail_text.configure(state=tk.DISABLED)

        self.status_var = tk.StringVar(value="共 0 筆報告")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, anchor=tk.W)
        status_bar.pack(fill=tk.X)

    # ------------------------------------------------------------------
    # 資料載入
    def _populate_tags(self) -> None:
        self.tag_tree.delete(*self.tag_tree.get_children())
        self._tag_nodes.clear()

        root_id = self.tag_tree.insert("", tk.END, text="全部報告")
        self._tag_nodes[root_id] = _TagNode(item_id=root_id, tag=None)

        tree = self.db.build_tag_tree()

        def add_children(parent_item: str, parent_tag_id: Optional[int]) -> None:
            for tag in tree.get(parent_tag_id, []):
                item = self.tag_tree.insert(parent_item, tk.END, text=tag.name)
                self._tag_nodes[item] = _TagNode(item_id=item, tag=tag)
                add_children(item, tag.id)

        add_children(root_id, None)
        self.tag_tree.item(root_id, open=True)
        self.tag_tree.selection_set(root_id)

    def _load_reports(self, tag: Optional[Tag]) -> None:
        if tag is None:
            reports = self.db.list_reports()
        else:
            reports = self.db.search_reports([tag.name])

        self._reports = reports
        self.report_list.delete(0, tk.END)
        for report in reports:
            created = report.created_at.strftime("%Y-%m-%d %H:%M")
            self.report_list.insert(tk.END, f"[{report.id}] {report.title} - {created}")

        self.status_var.set(f"共 {len(reports)} 筆報告")
        self.detail_text.configure(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.configure(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # 事件處理
    def _on_tag_selected(self, event: tk.Event) -> None:
        selection = self.tag_tree.selection()
        if not selection:
            return
        node = self._tag_nodes.get(selection[0])
        tag = node.tag if node else None
        self._load_reports(tag)

    def _on_report_selected(self, _: tk.Event) -> None:
        selection = self.report_list.curselection()
        if not selection:
            return
        index = selection[0]
        if index >= len(self._reports):
            return
        report = self._reports[index]
        tags = ", ".join(tag.name for tag in self.db.get_tags_for_report(report.id)) or "<無標籤>"
        created = report.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")

        detail_lines = [
            f"標題：{report.title}",
            f"建立時間：{created}",
            f"來源：{report.source_path or '-'}",
            f"標籤：{tags}",
            "",
            report.content,
        ]

        self.detail_text.configure(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("1.0", "\n".join(detail_lines))
        self.detail_text.configure(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # 動作
    def _refresh_data(self) -> None:
        selection = self.tag_tree.selection()
        tag = None
        if selection:
            node = self._tag_nodes.get(selection[0])
            tag = node.tag if node else None
        self._load_reports(tag)

    def _add_tag(self) -> None:
        name = simpledialog.askstring("新增標籤", "請輸入標籤名稱：", parent=self.root)
        if not name:
            return

        parent_tag: Optional[Tag] = None
        selection = self.tag_tree.selection()
        if selection:
            node = self._tag_nodes.get(selection[0])
            if node and node.tag:
                parent_tag = node.tag

        try:
            parent_name = parent_tag.name if parent_tag else None
            self.db.ensure_tag(name, parent=parent_name)
        except Exception as exc:  # pragma: no cover - GUI 錯誤顯示
            messagebox.showerror("新增標籤失敗", str(exc), parent=self.root)
            return

        self._populate_tags()
        messagebox.showinfo("完成", f"標籤 '{name}' 已建立", parent=self.root)

    def _add_report(self) -> None:
        dialog = _ReportDialog(self.root)
        self.root.wait_window(dialog.window)
        if not dialog.result:
            return

        title, content, tags = dialog.result
        try:
            report_id = self.db.add_report(title, content, tags=tags)
        except Exception as exc:  # pragma: no cover - GUI 錯誤顯示
            messagebox.showerror("新增報告失敗", str(exc), parent=self.root)
            return

        self._refresh_data()
        messagebox.showinfo("完成", f"報告 #{report_id} 已新增", parent=self.root)

    def _export_report(self) -> None:
        selection = self.report_list.curselection()
        if not selection:
            messagebox.showwarning("請先選擇報告", "請在清單中選擇要匯出的報告。", parent=self.root)
            return
        report = self._reports[selection[0]]

        filename = simpledialog.askstring(
            "匯出報告", "請輸入輸出檔名 (例如 output.txt)：", parent=self.root
        )
        if not filename:
            return

        try:
            path = self.db.export_report(report.id, filename)
        except Exception as exc:  # pragma: no cover - GUI 錯誤顯示
            messagebox.showerror("匯出失敗", str(exc), parent=self.root)
            return

        messagebox.showinfo("完成", f"已匯出至 {path}", parent=self.root)


class _ReportDialog:
    """簡易彈窗，讓使用者輸入報告內容。"""

    def __init__(self, parent: tk.Tk):
        self.window = tk.Toplevel(parent)
        self.window.title("新增報告")
        self.window.grab_set()
        self.window.transient(parent)

        ttk.Label(self.window, text="標題").grid(row=0, column=0, sticky=tk.W, padx=8, pady=(8, 4))
        self.title_var = tk.StringVar()
        ttk.Entry(self.window, textvariable=self.title_var).grid(
            row=0, column=1, sticky=tk.EW, padx=8, pady=(8, 4)
        )

        ttk.Label(self.window, text="內容").grid(row=1, column=0, sticky=tk.NW, padx=8, pady=4)
        self.content_text = tk.Text(self.window, width=60, height=15, wrap=tk.WORD)
        self.content_text.grid(row=1, column=1, sticky=tk.NSEW, padx=8, pady=4)

        ttk.Label(self.window, text="標籤 (以逗號分隔)").grid(
            row=2, column=0, sticky=tk.W, padx=8, pady=4
        )
        self.tags_var = tk.StringVar()
        ttk.Entry(self.window, textvariable=self.tags_var).grid(
            row=2, column=1, sticky=tk.EW, padx=8, pady=4
        )

        button_bar = ttk.Frame(self.window)
        button_bar.grid(row=3, column=0, columnspan=2, sticky=tk.E, padx=8, pady=(4, 8))
        ttk.Button(button_bar, text="取消", command=self.window.destroy).pack(side=tk.RIGHT)
        ttk.Button(button_bar, text="新增", command=self._on_submit).pack(side=tk.RIGHT, padx=(0, 8))

        self.window.columnconfigure(1, weight=1)
        self.window.rowconfigure(1, weight=1)

        self.result: Optional[tuple[str, str, list[str]]] = None

    def _on_submit(self) -> None:
        title = self.title_var.get().strip()
        content = self.content_text.get("1.0", tk.END).strip()
        tags_text = self.tags_var.get().strip()

        if not title:
            messagebox.showwarning("缺少標題", "請輸入報告標題。", parent=self.window)
            return
        if not content:
            messagebox.showwarning("缺少內容", "請輸入報告內容。", parent=self.window)
            return

        tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()] if tags_text else []
        self.result = (title, content, tags)
        self.window.destroy()


def launch(database: str = "reportdb.sqlite3") -> None:
    root = tk.Tk()
    ReportApp(root, database=database)
    root.mainloop()


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="ReportFileDB 圖形介面")
    parser.add_argument(
        "--database",
        default="reportdb.sqlite3",
        help="資料庫檔案路徑 (預設: reportdb.sqlite3)",
    )
    args = parser.parse_args(argv)
    launch(args.database)


if __name__ == "__main__":
    main()

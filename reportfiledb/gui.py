"""Tkinter GUI for ReportFileDB."""

from __future__ import annotations

import argparse
from pathlib import Path
import tkinter as tk
from dataclasses import dataclass
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Dict, Optional, Sequence



from .database import Report, ReportDatabase, Tag


@dataclass
class _TagNode:
    item_id: str
    tag: Optional[Tag]


@dataclass
class ReportDialogResult:
    """Result payload returned from the report dialog."""

    title: str
    content: str
    tags: list[str]
    source_path: Optional[str]
    set_source: bool


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
        ttk.Button(tag_buttons, text="刪除標籤", command=self._delete_tag).pack(side=tk.LEFT, padx=(8, 0))

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
        ttk.Button(button_bar, text="編輯報告", command=self._edit_report).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(button_bar, text="刪除報告", command=self._delete_report).pack(side=tk.LEFT, padx=(8, 0))


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

    def _on_report_selected(self, _: Optional[tk.Event] = None) -> None:

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

    def _refresh_data(self, selected_report_id: Optional[int] = None) -> None:

        selection = self.tag_tree.selection()
        tag = None
        if selection:
            node = self._tag_nodes.get(selection[0])
            tag = node.tag if node else None
        self._load_reports(tag)

        if selected_report_id is not None:
            for index, report in enumerate(self._reports):
                if report.id == selected_report_id:
                    self.report_list.selection_clear(0, tk.END)
                    self.report_list.selection_set(index)
                    self.report_list.activate(index)
                    self.report_list.see(index)
                    self._on_report_selected()
                    break

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

    def _delete_tag(self) -> None:
        selection = self.tag_tree.selection()
        if not selection:
            messagebox.showwarning("請先選擇標籤", "請選擇要刪除的標籤。", parent=self.root)
            return

        node = self._tag_nodes.get(selection[0])
        if not node or node.tag is None:
            messagebox.showwarning("無法刪除", "請選擇欲刪除的標籤，而非根節點。", parent=self.root)
            return

        tag = node.tag
        has_children = bool(self.tag_tree.get_children(selection[0]))

        if has_children:
            confirm = messagebox.askyesno(
                "刪除標籤",
                f"'{tag.name}' 含有子標籤，確定要一併刪除嗎？",
                parent=self.root,
            )
            cascade = True
        else:
            confirm = messagebox.askyesno(
                "刪除標籤",
                f"確定要刪除標籤 '{tag.name}' 嗎？",
                parent=self.root,
            )
            cascade = False

        if not confirm:
            return

        try:
            self.db.delete_tag(tag.name, cascade=cascade)
        except Exception as exc:  # pragma: no cover - GUI 錯誤顯示
            messagebox.showerror("刪除標籤失敗", str(exc), parent=self.root)
            return

        self._populate_tags()
        self._refresh_data()
        messagebox.showinfo("完成", f"標籤 '{tag.name}' 已刪除", parent=self.root)

    def _add_report(self) -> None:
        dialog = _ReportDialog(
            self.root,
            available_tags=[tag.name for tag in self.db.list_tags()],
        )
        self.root.wait_window(dialog.window)
        if not dialog.result:
            return

        result = dialog.result
        try:
            report_id = self.db.add_report(
                result.title,
                result.content,
                source_path=result.source_path,
                tags=result.tags,
            )
        except Exception as exc:  # pragma: no cover - GUI 錯誤顯示
            messagebox.showerror("新增報告失敗", str(exc), parent=self.root)
            return

        self._refresh_data(selected_report_id=report_id)
        messagebox.showinfo("完成", f"報告 #{report_id} 已新增", parent=self.root)

    def _delete_report(self) -> None:
        selection = self.report_list.curselection()
        if not selection:
            messagebox.showwarning("請先選擇報告", "請在清單中選擇要刪除的報告。", parent=self.root)
            return

        index = selection[0]
        if index >= len(self._reports):
            return

        report = self._reports[index]
        confirm = messagebox.askyesno(
            "刪除報告",
            f"確定要刪除報告 '{report.title}' (# {report.id}) 嗎？",
            parent=self.root,
        )
        if not confirm:
            return

        try:
            self.db.delete_report(report.id)
        except Exception as exc:  # pragma: no cover - GUI 錯誤顯示
            messagebox.showerror("刪除報告失敗", str(exc), parent=self.root)
            return

        self._refresh_data()
        messagebox.showinfo("完成", f"報告 #{report.id} 已刪除", parent=self.root)

    def _edit_report(self) -> None:
        selection = self.report_list.curselection()
        if not selection:
            messagebox.showwarning("請先選擇報告", "請在清單中選擇要編輯的報告。", parent=self.root)
            return

        index = selection[0]
        if index >= len(self._reports):
            return

        report = self._reports[index]
        tags = [tag.name for tag in self.db.get_tags_for_report(report.id)]

        dialog = _ReportDialog(
            self.root,
            title="編輯報告",
            submit_label="儲存",
            initial_title=report.title,
            initial_content=report.content,
            initial_tags=tags,
            initial_source=report.source_path,
            available_tags=[tag.name for tag in self.db.list_tags()],
            allow_clear_source=True,
        )
        self.root.wait_window(dialog.window)
        if not dialog.result:
            return

        result = dialog.result

        try:
            self.db.update_report(
                report.id,
                title=result.title,
                content=result.content,
                tags=result.tags,
                source_path=result.source_path,
                set_source=result.set_source,
            )
        except Exception as exc:  # pragma: no cover - GUI 錯誤顯示
            messagebox.showerror("編輯報告失敗", str(exc), parent=self.root)
            return

        self._refresh_data(selected_report_id=report.id)
        messagebox.showinfo("完成", f"報告 #{report.id} 已更新", parent=self.root)


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

    def __init__(
        self,
        parent: tk.Tk,
        *,
        title: str = "新增報告",
        submit_label: str = "新增",
        initial_title: str = "",
        initial_content: str = "",
        initial_tags: Optional[Sequence[str]] = None,
        initial_source: Optional[str] = None,
        available_tags: Optional[Sequence[str]] = None,
        allow_clear_source: bool = False,
    ):
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.grab_set()
        self.window.transient(parent)

        ttk.Label(self.window, text="標題").grid(row=0, column=0, sticky=tk.W, padx=8, pady=(8, 4))
        self.title_var = tk.StringVar(value=initial_title)
        ttk.Entry(self.window, textvariable=self.title_var).grid(
            row=0, column=1, sticky=tk.EW, padx=8, pady=(8, 4)
        )

        ttk.Label(self.window, text="內容").grid(row=1, column=0, sticky=tk.NW, padx=8, pady=4)
        self.content_text = tk.Text(self.window, width=60, height=15, wrap=tk.WORD)
        self.content_text.grid(row=1, column=1, sticky=tk.NSEW, padx=8, pady=4)
        if initial_content:
            self.content_text.insert("1.0", initial_content)

        ttk.Label(self.window, text="來源").grid(row=2, column=0, sticky=tk.W, padx=8, pady=4)
        source_row = ttk.Frame(self.window)
        source_row.grid(row=2, column=1, sticky=tk.EW, padx=8, pady=4)
        source_row.columnconfigure(0, weight=1)

        self.initial_source = initial_source
        self.source_var = tk.StringVar(value=initial_source or "")
        self.source_entry = ttk.Entry(source_row, textvariable=self.source_var)
        self.source_entry.grid(row=0, column=0, sticky=tk.EW)

        self.load_file_button = ttk.Button(
            source_row, text="從檔案載入…", command=self._on_load_file
        )
        self.load_file_button.grid(row=0, column=1, padx=(4, 0))

        self.clear_source_var: Optional[tk.BooleanVar]
        if allow_clear_source:
            self.clear_source_var = tk.BooleanVar(value=False)
            self.clear_source_check = ttk.Checkbutton(
                source_row,
                text="清除來源",
                variable=self.clear_source_var,
                command=self._on_clear_source_toggle,
            )
            self.clear_source_check.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(4, 0))
        else:
            self.clear_source_var = None
            self.clear_source_check = None

        ttk.Label(self.window, text="標籤").grid(row=3, column=0, sticky=tk.NW, padx=8, pady=4)

        tags_container = ttk.Frame(self.window)
        tags_container.grid(row=3, column=1, sticky=tk.NSEW, padx=8, pady=4)
        tags_container.columnconfigure(0, weight=1)

        selector_row = ttk.Frame(tags_container)
        selector_row.grid(row=0, column=0, sticky=tk.EW)
        selector_row.columnconfigure(0, weight=1)

        self._all_tags = sorted(
            {tag.strip() for tag in (available_tags or []) if tag}, key=str.casefold
        )
        self._available_tags = list(self._all_tags)
        self.tag_var = tk.StringVar()
        self.tag_combobox = ttk.Combobox(
            selector_row,
            textvariable=self.tag_var,
            values=self._available_tags,
        )
        self.tag_combobox.grid(row=0, column=0, sticky=tk.EW)

        self.tag_combobox.bind("<<ComboboxSelected>>", self._on_combobox_selected)
        self.tag_combobox.bind("<Return>", self._on_combobox_return)
        self.tag_combobox.bind("<KeyRelease>", self._on_combobox_keyrelease)
        self.tag_combobox.bind("<FocusIn>", self._on_combobox_focus)
        self.tag_combobox.bind("<FocusOut>", self._on_combobox_focus_out)

        ttk.Button(selector_row, text="加入", command=self._on_add_tag).grid(
            row=0, column=1, padx=(4, 0)
        )

        self.selected_tags_listbox = tk.Listbox(
            tags_container,
            height=6,
            exportselection=False,
        )
        self.selected_tags_listbox.grid(row=1, column=0, sticky=tk.NSEW, pady=(4, 0))

        tags_container.rowconfigure(1, weight=1)

        ttk.Button(tags_container, text="移除選取", command=self._on_remove_tag).grid(
            row=2, column=0, sticky=tk.E, pady=(4, 0)
        )

        self._selected_tags: set[str] = set()
        for tag in initial_tags or []:
            self._add_tag_value(tag)

        button_bar = ttk.Frame(self.window)
        button_bar.grid(row=4, column=0, columnspan=2, sticky=tk.E, padx=8, pady=(4, 8))
        ttk.Button(button_bar, text=submit_label, command=self._on_submit).pack(
            side=tk.RIGHT, padx=(0, 8)
        )


        self.window.columnconfigure(1, weight=1)
        self.window.rowconfigure(1, weight=1)
        self.window.rowconfigure(3, weight=1)

        self.result: Optional[ReportDialogResult] = None
        self._update_source_state()

    def _on_submit(self) -> None:
        title = self.title_var.get().strip()
        content = self.content_text.get("1.0", tk.END).strip()

        if not title:
            messagebox.showwarning("缺少標題", "請輸入報告標題。", parent=self.window)
            return
        if not content:
            messagebox.showwarning("缺少內容", "請輸入報告內容。", parent=self.window)
            return

        tags = list(self.selected_tags_listbox.get(0, tk.END))

        source_path = self.source_var.get().strip() or None
        set_source = False
        if self.clear_source_var is not None and self.clear_source_var.get():
            set_source = True
            source_path = None
        else:
            if (self.initial_source or None) != source_path:
                set_source = bool(source_path) or self.initial_source is not None

        self.result = ReportDialogResult(
            title=title,
            content=content,
            tags=tags,
            source_path=source_path,
            set_source=set_source,
        )
        self.window.destroy()

    def _on_add_tag(self) -> None:
        value = self.tag_var.get().strip()
        if not value:
            messagebox.showwarning("未輸入標籤", "請先選擇或輸入標籤名稱。", parent=self.window)
            return

        if value in self._selected_tags:
            messagebox.showinfo("重複標籤", f"'{value}' 已在清單中。", parent=self.window)
            return

        self._add_tag_value(value)
        if value not in self._all_tags:
            self._all_tags.append(value)
            self._all_tags.sort(key=str.casefold)
        self.tag_var.set("")
        self._apply_tag_filter(self.tag_var.get())

    def _add_tag_value(self, value: str) -> None:
        value = value.strip()
        if not value:
            return
        if value in self._selected_tags:
            return
        self._selected_tags.add(value)
        self.selected_tags_listbox.insert(tk.END, value)

    def _on_remove_tag(self) -> None:
        selection = self.selected_tags_listbox.curselection()
        if not selection:
            messagebox.showwarning("未選擇標籤", "請先選擇要移除的標籤。", parent=self.window)
            return

        index = selection[0]
        value = self.selected_tags_listbox.get(index)
        self.selected_tags_listbox.delete(index)
        self._selected_tags.discard(value)

    # ------------------------------------------------------------------
    # 標籤下拉選單優化

    def _apply_tag_filter(self, query: str) -> None:
        query = query.strip().lower()
        if not query:
            filtered = list(self._all_tags)
        else:
            filtered = [tag for tag in self._all_tags if query in tag.lower()]
        self._available_tags = filtered
        self.tag_combobox.configure(values=self._available_tags)

    def _on_combobox_selected(self, _: tk.Event) -> None:
        # 選單選取後直接加入標籤，減少操作步驟。
        self._on_add_tag()

    def _on_combobox_return(self, event: tk.Event) -> None:
        self._on_add_tag()
        return "break"

    def _on_combobox_keyrelease(self, event: tk.Event) -> None:
        if event.keysym in {"Return", "Escape", "Tab", "Up", "Down", "Left", "Right"}:
            return
        self._apply_tag_filter(self.tag_var.get())

    def _on_combobox_focus(self, _: tk.Event) -> None:
        # 聚焦時重新顯示完整清單，方便瀏覽。
        self._apply_tag_filter(self.tag_var.get())

    def _on_combobox_focus_out(self, _: tk.Event) -> None:
        # 離開時恢復全部選項，避免保留舊的過濾狀態。
        self._apply_tag_filter("")

    # ------------------------------------------------------------------
    # 來源處理

    def _on_load_file(self) -> None:
        filename = filedialog.askopenfilename(parent=self.window)
        if not filename:
            return
        path = Path(filename)
        try:
            data = path.read_text(encoding="utf-8")
        except Exception as exc:  # pragma: no cover - GUI 錯誤顯示
            messagebox.showerror("讀取檔案失敗", str(exc), parent=self.window)
            return

        self.content_text.delete("1.0", tk.END)
        self.content_text.insert("1.0", data)
        self.source_var.set(str(path))

        if self.clear_source_var is not None:
            self.clear_source_var.set(False)
        self._update_source_state()

    def _on_clear_source_toggle(self) -> None:
        self._update_source_state()

    def _update_source_state(self) -> None:
        clearing = bool(self.clear_source_var.get()) if self.clear_source_var else False
        state = tk.NORMAL if not clearing else tk.DISABLED
        self.source_entry.configure(state=state)
        self.load_file_button.configure(state=tk.NORMAL if not clearing else tk.DISABLED)
        if clearing:
            self.source_var.set("")


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

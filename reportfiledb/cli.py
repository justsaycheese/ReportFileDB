"""Command line interface for ReportFileDB."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List, Optional

from .database import ReportDatabase


def _print_report(report_db: ReportDatabase, report_id: int, *, show_content: bool) -> None:
    report = report_db.get_report(report_id)
    tags = ", ".join(tag.name for tag in report_db.get_tags_for_report(report.id)) or "<無標籤>"
    print(f"[{report.id}] {report.title} ({report.created_at.isoformat()} UTC)")
    if report.source_path:
        print(f"  來源: {report.source_path}")
    print(f"  標籤: {tags}")
    if show_content:
        print("  內容:")
        for line in report.content.splitlines():
            print(f"    {line}")


def _print_tag_tree(report_db: ReportDatabase) -> None:
    tree = report_db.build_tag_tree()

    def walk(parent_id: Optional[int], prefix: str = "") -> None:
        children = tree.get(parent_id, [])
        for index, tag in enumerate(children):
            connector = "└─" if index == len(children) - 1 else "├─"
            print(f"{prefix}{connector} {tag.name}")
            extension = "   " if connector == "└─" else "│  "
            walk(tag.id, prefix + extension)

    roots = tree.get(None, [])
    if not roots:
        print("(尚未建立標籤)")
        return

    for index, tag in enumerate(roots):
        connector = "└─" if index == len(roots) - 1 else "├─"
        print(f"{connector} {tag.name}")
        extension = "   " if connector == "└─" else "│  "
        walk(tag.id, extension)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="報告檢索資料庫管理工具")
    parser.add_argument(
        "--database",
        default="reportdb.sqlite3",
        help="資料庫檔案路徑 (預設: reportdb.sqlite3)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # add-report -------------------------------------------------------------
    add_report = subparsers.add_parser("add-report", help="新增報告內容")
    add_report.add_argument("title", help="報告標題")
    content_group = add_report.add_mutually_exclusive_group()
    content_group.add_argument(
        "--content", help="直接提供內容文字"
    )
    content_group.add_argument(
        "--file", type=Path, help="從檔案讀取報告內容"
    )
    content_group.add_argument(
        "--stdin", action="store_true", help="從標準輸入讀取內容"
    )
    add_report.add_argument(
        "--tag",
        action="append",
        dest="tags",
        help="要套用的標籤，可重複使用",
    )

    # edit-report ------------------------------------------------------------
    edit_report = subparsers.add_parser("edit-report", help="編輯既有報告")
    edit_report.add_argument("report_id", type=int, help="報告 ID")
    edit_report.add_argument("--title", help="新的標題")
    edit_content_group = edit_report.add_mutually_exclusive_group()
    edit_content_group.add_argument("--content", help="新的內容文字")
    edit_content_group.add_argument(
        "--file", type=Path, help="從檔案讀取新的內容"
    )
    edit_content_group.add_argument(
        "--stdin", action="store_true", help="從標準輸入讀取新的內容"
    )
    edit_report.add_argument(
        "--tag",
        action="append",
        dest="tags",
        help="重新指派的標籤，可重複使用",
    )
    edit_report.add_argument(
        "--clear-tags",
        action="store_true",
        help="移除所有標籤",
    )

    # add-tag ----------------------------------------------------------------
    add_tag = subparsers.add_parser("add-tag", help="新增標籤")
    add_tag.add_argument("name", help="標籤名稱")
    add_tag.add_argument("--parent", help="父標籤名稱 (如需建立子母標籤)")

    # set-parent -------------------------------------------------------------
    set_parent = subparsers.add_parser("set-parent", help="調整標籤的父子關係")
    set_parent.add_argument("name", help="標籤名稱")
    set_parent.add_argument("--parent", help="新的父標籤名稱，留空表示移除父標籤")

    # assign-tags ------------------------------------------------------------
    assign = subparsers.add_parser("assign-tag", help="為既有報告指派標籤")
    assign.add_argument("report_id", type=int, help="報告 ID")
    assign.add_argument("--tag", action="append", dest="tags", required=True, help="標籤名稱，可重複")

    # delete-report ----------------------------------------------------------
    delete_report = subparsers.add_parser("delete-report", help="刪除報告")
    delete_report.add_argument("report_id", type=int, help="報告 ID")

    # delete-tag -------------------------------------------------------------
    delete_tag = subparsers.add_parser("delete-tag", help="刪除標籤")
    delete_tag.add_argument("name", help="標籤名稱")
    delete_tag.add_argument(
        "--cascade", action="store_true", help="同時刪除所有子標籤"
    )

    # list-reports -----------------------------------------------------------
    list_reports = subparsers.add_parser("list-reports", help="列出所有報告")
    list_reports.add_argument(
        "--show-content",
        action="store_true",
        help="同時顯示報告內容",
    )

    # list-tags --------------------------------------------------------------
    subparsers.add_parser("list-tags", help="以樹狀結構顯示全部標籤")

    # search -----------------------------------------------------------------
    search = subparsers.add_parser("search", help="依標籤搜尋報告")
    search.add_argument("--tag", action="append", dest="tags", required=True, help="標籤名稱，可重複")
    search.add_argument(
        "--show-content",
        action="store_true",
        help="同時顯示內容",
    )

    # export -----------------------------------------------------------------
    export = subparsers.add_parser("export", help="匯出報告內容至檔案")
    export.add_argument("report_id", type=int, help="報告 ID")
    export.add_argument("destination", type=Path, help="輸出檔案路徑")

    return parser


def _read_content_from_args(args: argparse.Namespace) -> str:
    if args.content is not None:
        return args.content
    if args.file is not None:
        return args.file.read_text(encoding="utf-8")
    if getattr(args, "stdin", False):
        return sys.stdin.read()
    raise SystemExit("請使用 --content、--file 或 --stdin 提供報告內容")

def _read_optional_content(args: argparse.Namespace) -> Optional[str]:
    if args.content is not None:
        return args.content
    if args.file is not None:
        return args.file.read_text(encoding="utf-8")
    if getattr(args, "stdin", False):
        return sys.stdin.read()
    return None

def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    db = ReportDatabase(args.database)

    if args.command == "add-report":
        content = _read_content_from_args(args)
        report_id = db.add_report(args.title, content, tags=args.tags)
        print(f"已新增報告 #{report_id}")
        return 0

    if args.command == "add-tag":
        tag_id = db.ensure_tag(args.name, parent=args.parent)
        print(f"標籤 '{args.name}' (ID: {tag_id}) 已建立")
        return 0

    if args.command == "set-parent":
        db.set_tag_parent(args.name, args.parent)
        if args.parent:
            print(f"已將 '{args.name}' 設為 '{args.parent}' 的子標籤")
        else:
            print(f"已移除 '{args.name}' 的父標籤設定")
        return 0

    if args.command == "assign-tag":
        db.assign_tags(args.report_id, args.tags)
        print(f"已為報告 #{args.report_id} 新增標籤: {', '.join(args.tags)}")
        return 0

    if args.command == "edit-report":
        if args.tags and args.clear_tags:
            parser.error("請勿同時使用 --tag 與 --clear-tags")

        content = _read_optional_content(args)
        tags: Optional[List[str]]
        if args.clear_tags:
            tags = []
        else:
            tags = args.tags

        if args.title is None and content is None and tags is None:
            parser.error("請至少指定要更新的標題、內容或標籤")

        try:
            db.update_report(args.report_id, title=args.title, content=content, tags=tags)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        print(f"已更新報告 #{args.report_id}")
        return 0

    if args.command == "delete-report":
        try:
            db.delete_report(args.report_id)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"已刪除報告 #{args.report_id}")
        return 0

    if args.command == "delete-tag":
        try:
            db.delete_tag(args.name, cascade=args.cascade)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if args.cascade:
            print(f"已刪除標籤 '{args.name}'（含所有子標籤）")
        else:
            print(f"已刪除標籤 '{args.name}'")
        return 0

    if args.command == "list-reports":
        for report in db.list_reports():
            _print_report(db, report.id, show_content=args.show_content)
        return 0

    if args.command == "list-tags":
        _print_tag_tree(db)
        return 0

    if args.command == "search":
        tags = args.tags or []
        reports = db.search_reports(tags)
        if not reports:
            print("找不到符合的報告")
            return 0
        for report in reports:
            _print_report(db, report.id, show_content=args.show_content)
        return 0

    if args.command == "export":
        destination = db.export_report(args.report_id, args.destination)
        print(f"已匯出至 {destination}")
        return 0

    parser.error("未知的指令")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

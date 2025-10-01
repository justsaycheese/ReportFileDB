"""SQLite-backed storage layer for report snippets with hierarchical tagging."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Set
import sqlite3


@dataclass(frozen=True)
class Report:
    """A container holding report metadata fetched from the database."""

    id: int
    title: str
    content: str
    created_at: datetime
    source_path: Optional[str]


@dataclass(frozen=True)
class Tag:
    """Representation of a tag including its parent-child relationship."""

    id: int
    name: str
    parent_id: Optional[int]


class ReportDatabase:
    """Simple report storage database using SQLite."""

    def __init__(self, path: Path | str = "reportdb.sqlite3") -> None:
        self.path = Path(path)
        self._ensure_schema()

    # ------------------------------------------------------------------
    # private helpers
    def _ensure_schema(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_path TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    parent_id INTEGER,
                    FOREIGN KEY(parent_id) REFERENCES tags(id)
                );

                CREATE TABLE IF NOT EXISTS report_tags (
                    report_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,
                    PRIMARY KEY (report_id, tag_id),
                    FOREIGN KEY(report_id) REFERENCES reports(id) ON DELETE CASCADE,
                    FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
                );
                """
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _row_to_report(self, row: sqlite3.Row) -> Report:
        return Report(
            id=int(row["id"]),
            title=row["title"],
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]),
            source_path=row["source_path"],
        )

    def _resolve_tag_and_children(
        self, conn: sqlite3.Connection, tag_name: str
    ) -> Set[int]:
        cursor = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        row = cursor.fetchone()
        if row is None:
            return set()
        tag_id = int(row["id"])
        descendants: Set[int] = {tag_id}

        queue = [tag_id]
        while queue:
            current = queue.pop()
            child_cursor = conn.execute(
                "SELECT id FROM tags WHERE parent_id = ?", (current,)
            )
            for child in child_cursor.fetchall():
                child_id = int(child["id"])
                if child_id not in descendants:
                    descendants.add(child_id)
                    queue.append(child_id)

        return descendants

    # ------------------------------------------------------------------
    # public API
    def add_report(
        self,
        title: str,
        content: Optional[str] = None,
        *,
        source_path: Optional[Path | str] = None,
        tags: Optional[Sequence[str]] = None,
    ) -> int:
        """Insert a new report entry and return its identifier."""

        if content is None:
            if source_path is None:
                raise ValueError("Either content or source_path must be provided")
            data = Path(source_path).read_text(encoding="utf-8")
        else:
            data = content

        source_value = str(source_path) if source_path is not None else None
        created_at = datetime.utcnow().isoformat(timespec="seconds")

        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO reports (title, content, source_path, created_at) VALUES (?, ?, ?, ?)",
                (title, data, source_value, created_at),
            )
            report_id = int(cursor.lastrowid)

            if tags:
                for tag_name in tags:
                    tag_id = self.ensure_tag(tag_name)
                    conn.execute(
                        "INSERT OR IGNORE INTO report_tags (report_id, tag_id) VALUES (?, ?)",
                        (report_id, tag_id),
                    )

        return report_id

    def ensure_tag(self, name: str, *, parent: Optional[str] = None) -> int:
        """Return the identifier of ``name`` creating it (and parent) if missing."""

        with self._connect() as conn:
            parent_id: Optional[int] = None
            if parent is not None:
                parent_id = self.ensure_tag(parent)

            cursor = conn.execute("SELECT id FROM tags WHERE name = ?", (name,))
            row = cursor.fetchone()
            if row:
                tag_id = int(row["id"])
                if parent_id is not None:
                    conn.execute(
                        "UPDATE tags SET parent_id = ? WHERE id = ?",
                        (parent_id, tag_id),
                    )
                return tag_id

            cursor = conn.execute(
                "INSERT INTO tags (name, parent_id) VALUES (?, ?)", (name, parent_id)
            )
            return int(cursor.lastrowid)

    def set_tag_parent(self, name: str, parent: Optional[str]) -> None:
        """Explicitly set the parent of ``name`` to ``parent`` (creating parent if needed)."""

        with self._connect() as conn:
            cursor = conn.execute("SELECT id FROM tags WHERE name = ?", (name,))
            row = cursor.fetchone()
            if row is None:
                raise ValueError(f"Tag '{name}' does not exist")

            parent_id = None
            if parent is not None:
                parent_id = self.ensure_tag(parent)

            conn.execute("UPDATE tags SET parent_id = ? WHERE id = ?", (parent_id, row["id"]))

    def assign_tags(self, report_id: int, tag_names: Iterable[str]) -> None:
        """Assign multiple tags to an existing report."""

        with self._connect() as conn:
            for name in tag_names:
                tag_id = self.ensure_tag(name)
                conn.execute(
                    "INSERT OR IGNORE INTO report_tags (report_id, tag_id) VALUES (?, ?)",
                    (report_id, tag_id),
                )

    def get_report(self, report_id: int) -> Report:
        with self._connect() as conn:
            cursor = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
            row = cursor.fetchone()
            if row is None:
                raise ValueError(f"Report {report_id} does not exist")
            return self._row_to_report(row)

    def get_tags_for_report(self, report_id: int) -> List[Tag]:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT t.id, t.name, t.parent_id
                FROM tags AS t
                JOIN report_tags AS rt ON rt.tag_id = t.id
                WHERE rt.report_id = ?
                ORDER BY t.name
                """,
                (report_id,),
            )
            return [Tag(int(row["id"]), row["name"], row["parent_id"]) for row in cursor.fetchall()]

    def list_reports(self) -> List[Report]:
        with self._connect() as conn:
            cursor = conn.execute("SELECT * FROM reports ORDER BY created_at DESC")
            return [self._row_to_report(row) for row in cursor.fetchall()]

    def list_tags(self) -> List[Tag]:
        with self._connect() as conn:
            cursor = conn.execute("SELECT id, name, parent_id FROM tags ORDER BY name")
            return [Tag(int(row["id"]), row["name"], row["parent_id"]) for row in cursor.fetchall()]

    def search_reports(self, tag_names: Sequence[str]) -> List[Report]:
        """Return reports that contain *all* of the provided ``tag_names``.

        Each tag expands to include its descendants, mimicking a tag tree similar
        to what Danbooru offers.
        """

        if not tag_names:
            return self.list_reports()

        with self._connect() as conn:
            tag_id_sets = [self._resolve_tag_and_children(conn, name) for name in tag_names]
            if any(not ids for ids in tag_id_sets):
                return []

            subqueries: List[str] = []
            params: List[int] = []
            for ids in tag_id_sets:
                placeholders = ",".join("?" * len(ids))
                subqueries.append(
                    f"SELECT DISTINCT report_id FROM report_tags WHERE tag_id IN ({placeholders})"
                )
                params.extend(ids)

            intersect_sql = " INTERSECT ".join(subqueries)
            query = f"SELECT r.* FROM reports AS r WHERE r.id IN ({intersect_sql}) ORDER BY r.created_at DESC"
            cursor = conn.execute(query, params)
            return [self._row_to_report(row) for row in cursor.fetchall()]

    # Convenience -----------------------------------------------------------------
    def build_tag_tree(self) -> Dict[Optional[int], List[Tag]]:
        """Return a mapping from parent_id to a list of children tags."""

        with self._connect() as conn:
            cursor = conn.execute("SELECT id, name, parent_id FROM tags")
            tree: Dict[Optional[int], List[Tag]] = {}
            for row in cursor.fetchall():
                tag = Tag(int(row["id"]), row["name"], row["parent_id"])
                tree.setdefault(tag.parent_id, []).append(tag)
            for children in tree.values():
                children.sort(key=lambda t: t.name)
            return tree

    def export_report(self, report_id: int, destination: Path | str) -> Path:
        """Write the report content to ``destination`` and return the path."""

        report = self.get_report(report_id)
        dest_path = Path(destination)
        dest_path.write_text(report.content, encoding="utf-8")
        return dest_path

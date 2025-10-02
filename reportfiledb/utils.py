"""輔助函式集合。"""

from __future__ import annotations

import locale
from codecs import (
    BOM_UTF16_BE,
    BOM_UTF16_LE,
    BOM_UTF32_BE,
    BOM_UTF32_LE,
    BOM_UTF8,
)
from pathlib import Path
from typing import Iterator, List, Sequence


_BOM_TO_ENCODING = {
    BOM_UTF8: "utf-8-sig",
    BOM_UTF16_LE: "utf-16-le",
    BOM_UTF16_BE: "utf-16-be",
    BOM_UTF32_LE: "utf-32-le",
    BOM_UTF32_BE: "utf-32-be",
}


def _iter_candidate_encodings(
    preferred: str, extra_candidates: Sequence[str] | None
) -> Iterator[str]:
    """依序回傳可能適用的編碼名稱，避免重複測試。"""

    seen = set()
    if preferred:
        seen.add(preferred)

    if extra_candidates:
        for name in extra_candidates:
            if name and name not in seen:
                seen.add(name)
                yield name

    # 針對常見 BOM 與中文編碼提供的候選清單。
    for name in (
        "utf-8-sig",
        "utf-16",
        "utf-16-le",
        "utf-16-be",
        "utf-32",
        "utf-32-le",
        "utf-32-be",
        "gb18030",
        "big5",
        "cp950",
        "shift_jis",
    ):
        if name not in seen:
            seen.add(name)
            yield name


def read_text_with_fallback(
    path: Path,
    *,
    encoding: str = "utf-8",
    candidates: Sequence[str] | None = None,
) -> str:
    """讀取 ``path`` 並嘗試以多種編碼解碼，盡可能保留原始內容。

    會優先使用 ``encoding``，若失敗則依序測試 ``candidates`` 與常見的
    Unicode / 中文編碼（例如 Big5 / CP950、GB18030）。全部失敗時，
    最後會以 ``errors="replace"`` 回傳，避免拋出例外。
    """

    try:
        return path.read_text(encoding=encoding)
    except UnicodeDecodeError:
        data = path.read_bytes()

    bom_encoding = next(
        (name for bom, name in _BOM_TO_ENCODING.items() if data.startswith(bom)),
        None,
    )
    extra_candidates: List[str] = []
    if bom_encoding:
        extra_candidates.append(bom_encoding)
    if candidates:
        extra_candidates.extend(candidates)
    locale_encoding = locale.getpreferredencoding(False)
    if locale_encoding:
        extra_candidates.append(locale_encoding)

    for candidate in _iter_candidate_encodings(encoding, extra_candidates):
        try:
            return data.decode(candidate)
        except UnicodeDecodeError:
            continue

    return data.decode(encoding, errors="replace")

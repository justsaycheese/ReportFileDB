"""輔助函式集合。"""

from __future__ import annotations

from pathlib import Path


def read_text_with_fallback(path: Path, *, encoding: str = "utf-8") -> str:
    """以 UTF-8 讀取 ``path``，必要時以替代策略避免解碼失敗。

    由於部分匯入的報告檔案可能含有非標準的位元組序列或雜訊，
    直接以 :func:`Path.read_text` 讀取時會觸發 ``UnicodeDecodeError``。
    此函式先嘗試以標準 UTF-8 解碼，若失敗則回退為逐位元組
    讀取並以 ``errors="replace"`` 方式解碼，確保能得到字串內容，
    同時保留問題位元組的資訊（以 � 代表）。
    """

    try:
        return path.read_text(encoding=encoding)
    except UnicodeDecodeError:
        data = path.read_bytes()
        return data.decode(encoding, errors="replace")

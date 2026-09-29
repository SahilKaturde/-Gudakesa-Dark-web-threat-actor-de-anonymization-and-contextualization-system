"""
extractor/loader.py
File loader with line-indexed access, boilerplate detection, and offset conversion.
"""
import pathlib
from typing import List, Optional, Tuple, Union


class TextLoader:
    """Load a scraped text file and provide index-safe operations."""

    def __init__(self, file_path: Union[str, pathlib.Path]):
        self.file_path = pathlib.Path(file_path)
        self.filename = self.file_path.name
        self._raw_text = self.file_path.read_text(encoding="utf-8", errors="ignore")
        self._lines: List[str] = self._raw_text.splitlines()
        self._core_start: int = 0
        self._core_end: int = len(self._lines)
        self._detect_boilerplate()

    @property
    def raw_text(self) -> str:
        return self._raw_text

    @property
    def lines(self) -> List[str]:
        return self._lines

    @property
    def line_count(self) -> int:
        return len(self._lines)

    def get_line(self, n: int) -> str:
        """Get line by 1-based index."""
        if 1 <= n <= len(self._lines):
            return self._lines[n - 1]
        return ""

    def get_lines(self, start: int, end: int) -> List[str]:
        """Get lines by 1-based inclusive range."""
        s = max(0, start - 1)
        e = min(len(self._lines), end)
        return self._lines[s:e]

    def get_core_text(self) -> str:
        """Return text with nav/footer boilerplate stripped."""
        return "\n".join(self._lines[self._core_start:self._core_end])

    def get_core_line_range(self) -> Tuple[int, int]:
        """Return 1-based (start, end) of core content."""
        return (self._core_start + 1, self._core_end)

    def find_line_number(self, substring: str) -> Optional[int]:
        """Find 1-based line number of first occurrence of substring."""
        sub_lower = substring.lower()
        for i, line in enumerate(self._lines):
            if sub_lower in line.lower():
                return i + 1
        return None

    def find_line_number_near(self, substring: str, after_line: int = 0) -> Optional[int]:
        """Find 1-based line containing substring, searching after a given line."""
        sub_lower = substring.lower()
        for i in range(max(0, after_line), len(self._lines)):
            if sub_lower in self._lines[i].lower():
                return i + 1
        return None

    def char_offset_to_line(self, char_offset: int) -> int:
        """Convert a character offset in raw_text to a 1-based line number."""
        running = 0
        for i, line in enumerate(self._lines):
            running += len(line) + 1  # +1 for newline
            if running > char_offset:
                return i + 1
        return len(self._lines)

    def _detect_boilerplate(self):
        """Detect navigation header end and footer/sidebar beginning."""
        for i, line in enumerate(self._lines):
            if line.startswith("# ") and not line.startswith("## "):
                self._core_start = max(0, i - 1)
                break
            if line.startswith("Home /") or line.startswith("Home/"):
                self._core_start = max(0, i - 1)
                break

        footer_markers = [
            "## cart", "## product categories", "free worldwide shipping",
            "copyright", "\u00a9", "100% secure checkout"
        ]
        for i in range(len(self._lines) - 1, self._core_start, -1):
            line_lower = self._lines[i].lower().strip()
            for marker in footer_markers:
                if marker in line_lower:
                    remaining = len(self._lines) - i
                    if remaining >= 2:
                        self._core_end = i
                        return

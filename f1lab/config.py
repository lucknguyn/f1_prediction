"""Cấu hình đường dẫn dùng chung, có thể thay root khi kiểm thử."""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    root: Path = Path(__file__).resolve().parents[1]

    @property
    def raw_dir(self) -> Path:
        return self.root / "data" / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.root / "data" / "processed"

    @property
    def artifacts_dir(self) -> Path:
        return self.root / "artifacts"

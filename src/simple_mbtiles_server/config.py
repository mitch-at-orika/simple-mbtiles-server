# %%
#|export
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class Config:
    mbtiles_file: Path
    start_browser: bool = False
    port: int = 8765
    host: str = "127.0.0.1"
    static_dir: Optional[str] = None 
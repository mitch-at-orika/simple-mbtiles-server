# %%
#|export
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Union
import contextlib

class MBTilesDB:
    def __init__(self, db_path: Union[str, Path]):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"MBTiles file not found: {db_path}")
    
    @contextlib.contextmanager
    def get_connection(self):
        """Create a new connection for each operation"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            yield conn
        finally:
            conn.close()
        
    def get_metadata(self) -> Dict:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT name, value FROM metadata')
            return {name: value for name, value in cursor.fetchall()}
    
    def get_tile(self, z: int, x: int, y: int) -> Optional[bytes]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?',
                (z, x, (2**z - 1 - y))  # TMS to XYZ conversion
            )
            result = cursor.fetchone()
            return result[0] if result else None

    def is_compressed(self) -> bool:
        metadata = self.get_metadata()
        return not any(
            "-pC" in opt 
            for opt in metadata.get('generator_options', '').split(';')
        ) 
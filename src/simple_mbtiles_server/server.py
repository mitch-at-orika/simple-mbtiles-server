# %%
#|export
from pathlib import Path
from typing import Union, Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
import logging
import gzip

from .core import MBTilesDB

logger = logging.getLogger(__name__)

def flip_y(zoom: int, y: int) -> int:
    """Convert between TMS and XYZ tile coordinates"""
    return (1 << zoom) - 1 - y

def create_app(mbtiles_path: Union[str, Path], static_dir: Optional[str] = None) -> FastAPI:
    app = FastAPI(title="Simple MBTiles Server")
    db = MBTilesDB(mbtiles_path)
    
    if static_dir:
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    @app.get("/metadata")
    async def get_metadata():
        return db.get_metadata()
    
    @app.get("/tiles/{z}/{x}/{y}")
    async def get_tile(z: int, x: int, y: str):
        # Strip file extension if present
        xyz_y = int(y.split('.')[0])
        
        # Convert XYZ to TMS
        tms_y = flip_y(z, xyz_y)
        logger.info(f"Tile request - XYZ:{z}/{x}/{xyz_y} -> TMS:{z}/{x}/{tms_y}")
        
        # Double check if tile exists
        tile_data = db.get_tile(z, x, tms_y)
        if not tile_data:
            # Try the original y coordinate as well
            tile_data = db.get_tile(z, x, xyz_y)
            if not tile_data:
                logger.warning(f"Tile not found in database - tried TMS:{z}/{x}/{tms_y} and XYZ:{z}/{x}/{xyz_y}")
                raise HTTPException(status_code=404, detail="Tile not found")
            else:
                logger.info(f"Found tile using XYZ coordinates: {z}/{x}/{xyz_y}")
        else:
            logger.info(f"Found tile using TMS coordinates: {z}/{x}/{tms_y}")
            
        # Check if the data is gzipped
        try:
            if tile_data.startswith(b'\x1f\x8b'):  # gzip magic number
                logger.info("Decompressing gzipped tile data")
                tile_data = gzip.decompress(tile_data)
        except Exception as e:
            logger.error(f"Error decompressing tile: {e}")
            raise HTTPException(status_code=500, detail="Error processing tile data")
            
        logger.info(f"Returning tile with size: {len(tile_data)} bytes")
        return Response(
            content=tile_data,
            media_type="application/x-protobuf"
        )
    
    return app 
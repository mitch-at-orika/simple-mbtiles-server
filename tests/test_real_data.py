# %%
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
import mapbox_vector_tile
import json
import sqlite3
import logging
import os
import gzip

from simple_mbtiles_server.server import create_app, flip_y

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# %%
@pytest.fixture
def scram_mbtiles():
    # Try multiple path formats using environment variables
    paths_to_try = [
        os.path.join(os.environ['USERPROFILE'], 'code', 'transvis-desktop', 'data', 'scram', 'links.mbtiles'),  # Windows
        os.path.expanduser('~/code/transvis-desktop/data/scram/links.mbtiles'),  # Cross-platform home
        os.path.join('%USERPROFILE%', 'code', 'transvis-desktop', 'data', 'scram', 'links.mbtiles')  # Windows var
    ]
    
    for path in paths_to_try:
        # Expand any environment variables in the path
        expanded_path = os.path.expandvars(path)
        p = Path(expanded_path)
        if p.exists():
            logger.info(f"Found MBTiles file at: {p}")
            return p
            
    raise FileNotFoundError(f"Could not find MBTiles file in any of: {paths_to_try}")

@pytest.fixture
def tile_coords(scram_mbtiles):
    """Get actual tile coordinates from the MBTiles file"""
    conn = sqlite3.connect(scram_mbtiles)
    cur = conn.cursor()
    
    # First, check the table structure
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='tiles'")
    table_def = cur.fetchone()
    logger.info(f"Tiles table definition: {table_def}")
    
    # Get tiles around Queensland (lng: 134.44, lat: -28.32)
    # At zoom level 8 and 9 which we saw in previous tests
    cur.execute("""
        SELECT zoom_level, tile_column, tile_row, LENGTH(tile_data) as size 
        FROM tiles 
        WHERE zoom_level IN (8, 9)
        ORDER BY zoom_level, tile_column, tile_row
        LIMIT 5
    """)
    tiles = cur.fetchall()
    
    # Log raw data from database (these are in TMS format)
    for t in tiles:
        logger.info(f"Raw tile from DB (TMS) - z:{t[0]} x:{t[1]} y:{t[2]} size:{t[3]}")
    
    conn.close()
    
    # Keep the TMS coordinates - don't convert them
    tms_tiles = [(t[0], t[1], t[2]) for t in tiles]
    
    # Log the tiles we'll be testing
    for t in tms_tiles:
        logger.info(f"Testing tile (TMS) - z:{t[0]} x:{t[1]} y:{t[2]}")
        xyz_y = flip_y(t[0], t[2])
        logger.info(f"Will request as XYZ - z:{t[0]} x:{t[1]} y:{xyz_y}")
    
    return tms_tiles

@pytest.fixture
def client(scram_mbtiles):
    app = create_app(scram_mbtiles)
    return TestClient(app)

# %% 
def test_metadata_endpoint(client):
    """Test that metadata endpoint returns expected SCRAM data"""
    response = client.get("/metadata")
    assert response.status_code == 200
    metadata = response.json()
    logger.info(f"MBTiles metadata: {metadata}")
    assert "name" in metadata
    assert "format" in metadata

# %%
def test_tile_content(client, tile_coords, scram_mbtiles):
    """Test that we can get actual tile data from the SCRAM mbtiles"""
    if not tile_coords:
        pytest.skip("No tiles found in database")
        
    # Test the first available tile (in TMS coordinates)
    z, x, tms_y = tile_coords[0]
    xyz_y = flip_y(z, tms_y)  # Convert to XYZ for request
    logger.info(f"Testing tile - TMS:{z}/{x}/{tms_y} -> XYZ:{z}/{x}/{xyz_y}")
    
    # Double-check the tile exists in the database (using TMS coordinates)
    conn = sqlite3.connect(scram_mbtiles)
    cur = conn.cursor()
    cur.execute("""
        SELECT tile_data
        FROM tiles 
        WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?
    """, (z, x, tms_y))
    result = cur.fetchone()
    if result:
        raw_data = result[0]
        logger.info(f"Raw tile size: {len(raw_data)} bytes")
        # Use bytes literal outside f-string
        gzip_header = b'\x1f\x8b'
        logger.info(f"Starts with gzip magic number: {raw_data.startswith(gzip_header)}")
    conn.close()
    
    # Request using XYZ coordinates
    response = client.get(f"/tiles/{z}/{x}/{xyz_y}")
    assert response.status_code == 200, f"Failed to get tile at XYZ:{z}/{x}/{xyz_y} (TMS:{z}/{x}/{tms_y})"
    
    # Try to decode the vector tile
    try:
        tile_data = mapbox_vector_tile.decode(response.content)
        logger.info(f"Successfully decoded tile with layers: {tile_data.keys()}")
        
        # There should be at least one layer
        assert len(tile_data) > 0
        
        # First layer should have features
        first_layer = next(iter(tile_data.values()))
        assert len(first_layer['features']) > 0
        
        # Log sample feature
        if first_layer['features']:
            logger.info(f"Sample feature: {first_layer['features'][0]}")
            
    except Exception as e:
        logger.error(f"Error decoding tile: {e}")
        logger.error(f"Response content starts with: {response.content[:20].hex()}")
        raise

# %%
def test_specific_tiles(client, tile_coords, scram_mbtiles):
    """Test specific tile coordinates from the database"""
    if not tile_coords:
        pytest.skip("No tiles found in database")
    
    for z, x, tms_y in tile_coords:
        xyz_y = flip_y(z, tms_y)  # Convert to XYZ for request
        logger.info(f"\nTesting tile - TMS:{z}/{x}/{tms_y} -> XYZ:{z}/{x}/{xyz_y}")
        
        # Check database directly (using TMS coordinates)
        conn = sqlite3.connect(scram_mbtiles)
        cur = conn.cursor()
        cur.execute("""
            SELECT LENGTH(tile_data) 
            FROM tiles 
            WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?
        """, (z, x, tms_y))
        result = cur.fetchone()
        logger.info(f"Database check for tile (TMS) {z}/{x}/{tms_y}: {'Found' if result else 'Not found'}")
        if result:
            logger.info(f"Tile size in database: {result[0]} bytes")
        conn.close()
        
        # Request using XYZ coordinates
        response = client.get(f"/tiles/{z}/{x}/{xyz_y}")
        assert response.status_code == 200
        
        tile_data = mapbox_vector_tile.decode(response.content)
        logger.info(f"Tile {z}/{x}/{xyz_y} layers: {tile_data.keys()}")
        
        # Fixed dictionary comprehension
        feature_counts = {layer_name: len(layer['features']) 
                         for layer_name, layer in tile_data.items()}
        logger.info(f"Feature counts: {feature_counts}")
        
        # Verify we got features
        for layer_name, layer in tile_data.items():
            if layer['features']:
                logger.info(f"Layer {layer_name} first feature properties: {layer['features'][0]['properties']}") 
# %% [markdown]
"""
# Test Suite for Simple MBTiles Server

This notebook contains tests for the MBTiles server including:
1. Creation of dummy vector tile data
2. Generation of test MBTiles database
3. Server response testing
4. Content encoding verification
"""

# %%
import sqlite3
import tempfile
from pathlib import Path
import json
from fastapi.testclient import TestClient
import pytest
import mapbox_vector_tile
from typing import Generator
from shapely.geometry import Point
import gzip
import httpx

from simple_mbtiles_server.core import MBTilesDB
from simple_mbtiles_server.server import create_app
from simple_mbtiles_server.config import Config

# %% [markdown]
"""
## Fixtures for Testing
"""

# %%
def create_dummy_vector_tile() -> bytes:
    """Create a simple vector tile with a single point feature"""
    # Create a Shapely point geometry
    point = Point(0, 0)
    
    layers = [{
        "name": "test_layer",
        "features": [{
            "geometry": point,
            "properties": {"name": "test_point"},
            "geometry_type": "Point"  # Using string type instead of integer
        }],
        "version": 2,
        "extent": 4096
    }]
    return mapbox_vector_tile.encode(layers)

# %%
@pytest.fixture
def test_mbtiles() -> Generator[Path, None, None]:
    """Create a temporary MBTiles file with test data"""
    with tempfile.NamedTemporaryFile(suffix='.mbtiles', delete=False) as tmp:
        conn = sqlite3.connect(tmp.name)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE metadata (name text, value text);
        ''')
        cursor.execute('''
            CREATE TABLE tiles (
                zoom_level integer,
                tile_column integer,
                tile_row integer,
                tile_data blob
            );
        ''')
        
        # Insert metadata
        metadata = {
            "name": "test_tiles",
            "format": "pbf",
            "generator_options": "test-options",  # No -pC option, so tiles will be treated as compressed
            "version": "2"
        }
        cursor.executemany(
            "INSERT INTO metadata VALUES (?, ?)",
            metadata.items()
        )
        
        # Insert test tile
        tile_data = create_dummy_vector_tile()
        # Store uncompressed data in the database
        cursor.execute(
            "INSERT INTO tiles VALUES (?, ?, ?, ?)",
            (0, 0, 0, tile_data)  # Single tile at zoom 0
        )
        
        conn.commit()
        conn.close()
        
        yield Path(tmp.name)
        
        # Cleanup
        Path(tmp.name).unlink()

# %%
@pytest.fixture
def test_client(test_mbtiles):
    """Create a TestClient instance for the FastAPI app"""
    app = create_app(test_mbtiles)
    # Create client with custom transport that doesn't auto-decode responses
    return TestClient(app, backend_options={"http2": False})

# %% [markdown]
"""
## Test Cases
"""

# %%
def test_metadata_endpoint(test_client):
    """Test the /metadata endpoint"""
    response = test_client.get("/metadata")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test_tiles"
    assert data["format"] == "pbf"

# %%
def test_tile_endpoint(test_client):
    """Test the /tiles endpoint"""
    # Make request without automatic decompression
    response = test_client.get(
        "/tiles/0/0/0.mvt",
        headers={"Accept-Encoding": "identity"}
    )
    assert response.status_code == 200
    
    # Decode the vector tile directly (no decompression needed)
    tile_data = mapbox_vector_tile.decode(response.content)
    assert "test_layer" in tile_data
    assert len(tile_data["test_layer"]["features"]) == 1
    feature = tile_data["test_layer"]["features"][0]
    assert feature["properties"]["name"] == "test_point"

# %%
def test_missing_tile(test_client):
    """Test requesting a non-existent tile"""
    response = test_client.get("/tiles/1/1/1.mvt")
    assert response.status_code == 404

# %%
def test_mbtiles_db_connection(test_mbtiles):
    """Test direct MBTilesDB class functionality"""
    db = MBTilesDB(test_mbtiles)
    metadata = db.get_metadata()
    assert metadata["name"] == "test_tiles"
    
    tile = db.get_tile(0, 0, 0)
    assert tile is not None
    
    # Verify tile content
    tile_data = mapbox_vector_tile.decode(tile)
    assert "test_layer" in tile_data 

# %%
def test_custom_port(test_mbtiles):
    """Test that the server can be configured with a custom port"""
    custom_port = 9999
    config = Config(
        mbtiles_file=test_mbtiles,
        port=custom_port
    )
    
    app = create_app(config.mbtiles_file)
    client = TestClient(app)
    
    # Test that metadata endpoint works
    response = client.get("/metadata")
    assert response.status_code == 200 
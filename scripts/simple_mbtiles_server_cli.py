# %%
import argparse
import webbrowser
from pathlib import Path
import uvicorn
import sys

from simple_mbtiles_server.config import Config
from simple_mbtiles_server.server import create_app

def main():
    parser = argparse.ArgumentParser(description="Simple MBTiles Server")
    parser.add_argument("mbtiles_file", type=str, nargs='?', help="Path to MBTiles file")
    parser.add_argument("--start-browser", action="store_true", help="Open browser automatically")
    parser.add_argument("--port", type=int, default=8765, help="Port to start server (default: 8765)")
    args = parser.parse_args()
    
    if not args.mbtiles_file:
        print("No mbtiles file specified")
        sys.exit(2)
    
    config = Config(
        mbtiles_file=Path(args.mbtiles_file),
        start_browser=args.start_browser,
        port=args.port
    )
    
    app = create_app(config.mbtiles_file)
    
    if config.start_browser:
        webbrowser.open(f"http://{config.host}:{config.port}/static/index.html")
    
    uvicorn.run(app, host=config.host, port=config.port)

if __name__ == "__main__":
    main() 
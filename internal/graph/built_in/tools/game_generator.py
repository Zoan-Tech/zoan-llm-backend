import os
import requests
import shutil
from pathlib import Path   
from typing import Annotated, List, Dict, Any
from langchain_core.tools import tool
from langchain_core.runnables.config import ensure_config

from config.logging import get_logger
from internal.graph.built_in.helper.minio_games import minio_games_helper
from internal.graph.built_in.helper.planning_game_theme import game_theme_planner

logger = get_logger()


def get_thread_data_path(thread_id: str) -> Path:
    """Get the data path for a thread"""
    return Path("data") / thread_id

@tool
def planning_game_theme(
    candidate_images: Annotated[List[str], "List of image URLs from search_library results to analyze"],
    game_requirements: Annotated[str, "User requirements or description for the game"]
) -> str:
    """
    Analyze candidate images for their intended game asset purpose and generate suggested game themes strategically.
    """
    if not candidate_images:
        return "Error: No candidate images provided. Use search_library() first to get image URLs."
    
    try:
        result = game_theme_planner.analyze_comprehensive(candidate_images, game_requirements)
        return result
            
    except Exception as e:
        logger.error(f"Error in planning_game_theme: {e}")
        return f"Error during theme planning: {str(e)}\n\nPlease continue with the process."
    
@tool
def init_or_load_game_source() -> str:
    """
    Initialize or load the game source for the current thread.
    - If source exists in MinIO (games/thread_id/v*), load the latest version to local data/thread_id/v*.
    - If no source exists in MinIO, just create the data/thread_id directory.
    - If loading fails, create empty directory for fresh start.
    
    Returns status message with instructions:
    - On successful load: "Loaded version vX. Next version to build: vY. You can modify the loaded files or build as-is."
    - On failed load: "Failed to load vX. Starting fresh with vY. Please construct the complete game source using write_game_file() and write_game_assets()."
    - On no existing versions: "No existing versions found. Starting with v1. Please construct the complete game source using write_game_file() and write_game_assets()."
    """
    config = ensure_config()
    configurable = config.get("configurable", {})
    thread_id = configurable.get("thread_id", "default")
    
    data_path = get_thread_data_path(thread_id)
    
    # Try to load from MinIO
    minio_prefix = f"{thread_id}/"
    try:
        folder_count = minio_games_helper._count_folders_in_thread(thread_id)
        if folder_count > 0:
            # Get latest version from MinIO
            current_version = "v" + str(folder_count)
            next_version = "v" + str(folder_count + 1)
            source_path = f"{minio_prefix}{current_version}/"  # Ensure trailing slash
            dest_path = str(data_path)  # Convert Path to string
            
            success = minio_games_helper._download_latest_game_version(thread_id, source_path, dest_path)
            if not success:
                # Failed to download, create empty directory and instruct agent to build from scratch
                os.makedirs(data_path, exist_ok=True)
                return (
                    f"⚠️ Failed to load previous version: {current_version} from MinIO. Starting fresh with {next_version}."
                )
            
            # Successfully loaded
            return (
                f"✅ Successfully loaded previous version: {current_version}. Next version to build: {next_version}."
            )
        else:
            # No versions found in MinIO, create empty directory
            data_path.mkdir(parents=True, exist_ok=True)
            return (
                f"📁 No existing versions found in MinIO. Starting with v1."
            )
            
    except Exception as e:
        logger.warning(f"Could not load from MinIO: {e}. Creating empty directory.")
        # Create empty directory
        data_path.mkdir(parents=True, exist_ok=True)
        return (
            f"⚠️ Exception while accessing MinIO: {str(e)}\n\n"
            f"Starting fresh with v1.\n\n"
        )


@tool
def write_game_file(
    folder_path: Annotated[str, "Relative folder path (e.g., 'css', 'js', 'assets/images', or empty string for root)"],
    file_name: Annotated[str, "Name of the file to write (e.g., 'index.html', 'style.css', 'game.js', 'bg.png')"],
    content: Annotated[str, "The complete file content to write (for regular files). Leave empty if using url parameter."] = "",
    url: Annotated[str, "URL to download asset from (for assets). Leave empty if using content parameter."] = ""
) -> str:
    """
    Write a game file to the local data directory OR download an asset from a URL.
    
    Usage:
    - For regular files (HTML, CSS, JS): provide 'content', leave 'url' empty
    - For asset downloads (images, audio): provide 'url', leave 'content' empty
    
    Path structure: data/thread_id/<folder_path>/file_name
    
    Examples:
    - write_game_file("", "index.html", content="<html>...</html>", url="")
    - write_game_file("src/scenes", "GameScene.js", content="class GameScene...", url="")
    - write_game_file("assets/images", "bg.png", content="", url=<candidate_img_url>)
    - write_game_file("assets/audio", "jump.mp3", content="", url=<candidate_img_url>)
    """
    config = ensure_config()
    configurable = config.get("configurable", {})
    thread_id = configurable.get("thread_id", "default")
    
    data_path = get_thread_data_path(thread_id)
    
    # Validate parameters
    if not content and not url:
        return "Error: Either 'content' or 'url' must be provided"
    if content and url:
        return "Error: Provide either 'content' or 'url', not both"
    
    # Construct full path
    if folder_path:
        full_path = data_path / folder_path
    else:
        full_path = data_path
    
    full_path.mkdir(parents=True, exist_ok=True)
    file_path = full_path / file_name
    
    try:
        if url:
            # Download asset from URL
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                path_display = f"{folder_path}/{file_name}" if folder_path else file_name
                logger.info(f"Downloaded {url} to {file_path}")
                return f"✓ Successfully downloaded asset: data/{thread_id}/{path_display}"
            else:
                return f"✗ Error downloading {file_name}: HTTP {response.status_code}"
        else:
            # Write content to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            path_display = f"{folder_path}/{file_name}" if folder_path else file_name
            return f"✓ Successfully wrote file: data/{thread_id}/{path_display}"
    except Exception as e:
        logger.error(f"Error writing/downloading file: {e}")
        return f"✗ Error: {str(e)}"



@tool
def debug_source() -> str:
    """
    Debug the game source by:
    1. Starting a local HTTP server on port 8080 in the data/thread_id directory
    2. Setting up a /log endpoint to capture console logs
    3. Making a request to localhost:8080
    4. Capturing logs and errors
    5. Analyzing and fixing any errors found
    
    Returns debug information and suggestions for fixes.
    """
    import subprocess
    import time
    import requests
    from http.server import HTTPServer, SimpleHTTPRequestHandler
    import threading
    import json as json_module
    
    config = ensure_config()
    configurable = config.get("configurable", {})
    thread_id = configurable.get("thread_id", "default")
    
    data_path = get_thread_data_path(thread_id)
    
    if not data_path.exists():
        return f"Error: Data path does not exist: {data_path}. Run init_or_load_game_source() first."
    
    # Store captured logs
    captured_logs = []
    
    # Custom HTTP handler that supports /log endpoint
    class LogCapturingHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(data_path), **kwargs)
        
        def do_POST(self):
            if self.path == '/log':
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                try:
                    log_data = json_module.loads(post_data.decode('utf-8'))
                    captured_logs.append(log_data)
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"status": "ok"}')
                except Exception as e:
                    logger.error(f"Error processing log: {e}")
                    self.send_response(500)
                    self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()
        
        def log_message(self, format, *args):
            # Suppress default logging
            pass
    
    # Start HTTP server
    server = None
    server_thread = None
    try:
        # Create and start server in a thread
        server = HTTPServer(('localhost', 8080), LogCapturingHandler)
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        # Wait for server to start
        time.sleep(2)
        
        # Make request to localhost:8080
        debug_info = []
        try:
            response = requests.get(f"http://localhost:8080/index.html", timeout=5)
            status = response.status_code
            text = response.text
            debug_info.append(f"HTTP Status: {status}")
            
            if status == 200:
                debug_info.append("✓ Successfully loaded index.html")
                
                # Check if console log capturing is implemented
                if 'window.console.log' in text and 'fetch(\'/log\'' in text:
                    debug_info.append("✓ Console log capturing is enabled")
                else:
                    debug_info.append("⚠ Warning: Console log capturing not found. Add this to your JS:")
                    debug_info.append("  window.console.log = (...args) => {")
                    debug_info.append("    fetch('/log', {")
                    debug_info.append("      method: 'POST',")
                    debug_info.append("      body: JSON.stringify({ logs: args }),")
                    debug_info.append("      headers: { 'Content-Type': 'application/json' }")
                    debug_info.append("    });")
                    debug_info.append("  };")
                
            else:
                debug_info.append(f"✗ Error loading index.html: HTTP {status}")
                debug_info.append(f"Response: {text[:500]}")
        except requests.exceptions.Timeout:
            debug_info.append("✗ Request timed out")
        except Exception as e:
            debug_info.append(f"✗ Request error: {str(e)}")
        
        # Wait a bit for any console logs to be captured
        time.sleep(2)
        
        # Display captured logs
        if captured_logs:
            debug_info.append(f"\n📋 Captured Console Logs ({len(captured_logs)} entries):")
            for i, log in enumerate(captured_logs[:10], 1):  # Limit to first 10 logs
                debug_info.append(f"  {i}. {log}")
            if len(captured_logs) > 10:
                debug_info.append(f"  ... and {len(captured_logs) - 10} more")
        else:
            debug_info.append("\n📋 No console logs captured (page may not have loaded or no console.log calls)")
        
        return "\n".join(debug_info)
        
    except Exception as e:
        logger.error(f"Error during debug: {e}")
        return f"Error during debug: {str(e)}"
    finally:
        # Stop server
        if server:
            server.shutdown()
            server.server_close()
        if server_thread:
            server_thread.join(timeout=2)


@tool
def build_source(
    version: Annotated[str, "Version prefix for MinIO upload (e.g., 'v1', 'v2', 'v3')"]
) -> str:
    """
    Build and upload the game source to MinIO.
    Uploads all files from data/thread_id/ to MinIO with version prefix.
    Path in MinIO: games/thread_id/{version}/
    """
    config = ensure_config()
    configurable = config.get("configurable", {})
    thread_id = configurable.get("thread_id", "default")
    
    data_path = get_thread_data_path(thread_id)
    
    if not data_path.exists():
        raise Exception(f"Data path does not exist: {data_path}. Run init_or_load_game_source() first.")

    dest_path = f"{thread_id}/{version}"
    success = minio_games_helper._upload_source_game(thread_id, str(data_path), dest_path)
    if success:
        shutil.rmtree(data_path)
        return f"{minio_games_helper.bucket}/{dest_path}/index.html"
    else:
        raise Exception("Failed to upload game source to MinIO.")
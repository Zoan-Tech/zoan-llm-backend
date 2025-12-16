import base64
import httpx
import json
import mimetypes
import shutil
import tarfile
from pathlib import Path
from typing import Annotated, Optional

import requests
from langchain.tools import InjectedToolCallId
from langchain.messages import HumanMessage, ToolMessage
from langchain_core.runnables.config import ensure_config
from langchain_core.tools import tool
from langgraph.types import Command

from config import Config
from config.logging import get_logger
from internal.graph.built_in.helper.minio_games import minio_games_helper
from internal.vectorizer.base import TEXT_EMBEDDING_MODEL
from model.client.app_preview import BuildStatus
from services.connector.app_preview import app_preview_client
from services.qdrant_library_client import qm, qdrant_library_client
from utils.const.multimodal import PAGINATION_OFFSET_MULTIPLIER

logger = get_logger()

SOURCE_TYPE = 'folder'
GAME_TAR = "project.tar.gz"
BUILD_COMPLETE_STATUSES = [
    BuildStatus.FAILED.value,
    BuildStatus.STOPPED.value,
    BuildStatus.DELETED.value,
    BuildStatus.RUNNING.value
]

def get_thread_data_path(thread_id: str) -> Path:
    """Get the data path for a thread"""
    return Path("data") / thread_id

@tool
def search_knowledge_hub(
    query: Annotated[str, "The search query, related to game specifications, features, or themes"],
    filter: Annotated[Optional[dict], "Optional filter to narrow down search results, in JSON format, for example: {'object_key': 'flappy bird'}"],
    offset: Annotated[int, "The offset for pagination, starting from 0, corresponds to the number of times the search has been performed."],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Search the library for relevant game specification/game feature or game themes/assets.
    
    Filter has keys that can be used to narrow down search:
    - object_key: Filter by object key (file name or path), this supports partial matching. Some assets will be stored under a specific folder structure, if a folder related available, you can query the whole folder path.
    - mimetype: Filter by MIME type (e.g., image/png, text/javascript), this supports exact matching
    
    Returns search results with text content and image URLs that will be automatically 
    injected into the conversation for visual analysis.
    """
    config = ensure_config()
    configurable = config.get("configurable", {})
    user_id = configurable.get("user_id", None)
    
    filter_ = qm.Filter(
        must=[
            qm.FieldCondition(
                key="owner",
                match=qm.MatchAny(any=[user_id, "public"])
            )
        ]
    ) if user_id else qm.Filter(
        must=[
            qm.FieldCondition(
                key="owner",
                match=qm.MatchAny(any=["public"])
            )
        ]
    )
    
    should_ = []
    
    if filter:
        for key, value in filter.items():
            if key == 'object_key':
                should_.append(
                    qm.FieldCondition(
                        key=key,
                        match=qm.MatchTextAny(text_any=value)
                    )
                )
            elif key == 'mimetype':
                should_.append(
                    qm.FieldCondition(
                        key=key,
                        match=qm.MatchText(text=value)
                    )
                )
                
    if len(should_) > 0:
        filter_.should = should_
    
    text_vector = TEXT_EMBEDDING_MODEL.embed_query(query)
        
    results = qdrant_library_client.client.query_points(
        collection_name=qdrant_library_client.collection_name,
        query=text_vector,
        using="text",
        query_filter=filter_,
        limit=5,
        offset=offset * PAGINATION_OFFSET_MULTIPLIER,
    ).points
    
    # Collect image URLs from results
    human_messages = []
    text_results = ""
    
    for idx, result in enumerate(results):
        try:
            bucket = result.payload.get("bucket")
            object_key = result.payload.get("object_key")
            text_results += f"{idx+1}. Object key: {object_key}\n"
            
            url = f"{Config.MINIO_BROWSER_URL}/{bucket}/{object_key}"
            mime_type = result.payload.get("mimetype")
            
            if not mime_type:
                mime_type, _ = mimetypes.guess_type(url)
            response = httpx.get(url, timeout=10.0)
            response.raise_for_status()
            
            encoded_image = base64.b64encode(response.content).decode("utf-8")  # Fixed variable name
            description = result.payload.get("description", "No description available.")
            # TODO: Handle other content types (e.g., text, audio) if needed
            human_messages.append(HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": f"Image found in `search_knowledge_hub`: {url}. {description}"
                    },
                    {
                        "type": "image",
                        "base64": encoded_image,
                        "mime_type": mime_type
                    },
                ]
            ))
        except Exception as e:
            logger.error(f"[search_knowledge_hub] Error processing search result: {str(e)}", exc_info=True)
            continue
        
    messages = [
        ToolMessage(
            content=f"Found {len(human_messages)} results for query: '{query}'\n{text_results}",
            tool_call_id=tool_call_id
        )
    ] + human_messages
    
    # Return structured data with both text and image URLs
    return Command(update={
        "messages": messages
    })
    
@tool
def read_source_structure() -> str:
    """
    Read the current game source structure for the thread.
    Returns a tree-like structure of all files and folders.
    """
    config = ensure_config()
    configurable = config.get("configurable", {})
    thread_id = configurable.get("thread_id", "default")
    
    data_path = get_thread_data_path(thread_id)
    
    if not data_path.exists():
        return f"✗ Error: Data path does not exist: {data_path}"
    
    def build_tree(directory: Path, prefix: str = "", is_last: bool = True) -> list:
        """Recursively build tree structure"""
        lines = []
        
        try:
            # Get all items in directory
            items = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            
            for i, item in enumerate(items):
                is_last_item = i == len(items) - 1
                current_prefix = "└── " if is_last_item else "├── "
                
                # Add current item
                if item.is_dir():
                    lines.append(f"{prefix}{current_prefix}{item.name}/")
                    # Add children with updated prefix
                    extension = "    " if is_last_item else "│   "
                    lines.extend(build_tree(item, prefix + extension, is_last_item))
                else:
                    lines.append(f"{prefix}{current_prefix}{item.name}")
        except PermissionError:
            lines.append(f"{prefix}[Permission Denied]")
        
        return lines
    
    # Build the tree
    tree_lines = [f"{data_path.name}/"]
    tree_lines.extend(build_tree(data_path))
    
    return "\n".join(tree_lines)
        
@tool
def init_or_load_game_source() -> str:
    """
    Initialize or load the game source for the current conversation.
    """
    config = ensure_config()
    configurable = config.get("configurable", {})
    thread_id = configurable.get("thread_id", "default")
    
    data_path = get_thread_data_path(thread_id)
    data_path.mkdir(parents=True, exist_ok=True)
    
    folder_count = minio_games_helper._count_folders_in_thread(thread_id)
    if folder_count > 0:
        # Get latest version from MinIO
        current_version = "v" + str(folder_count)
        next_version = "v" + str(folder_count + 1)
        
        if SOURCE_TYPE == 'file':
            source_path = f"{thread_id}/{current_version}/{GAME_TAR}"
        else:
            source_path = f"{thread_id}/{current_version}/"
        
        minio_games_helper._download_game_version(source_path, data_path, source_type=SOURCE_TYPE)
        
        if SOURCE_TYPE == 'file':
            # Extract the tar.gz file
            tar_file_path = data_path / GAME_TAR
            if tar_file_path.exists():
                with tarfile.open(tar_file_path, "r:gz") as tar:
                    tar.extractall(path=data_path)
                # Remove the tar file after extraction
                tar_file_path.unlink()
        
        return (
            f"✅ Successfully loaded current version: {current_version}\n"
            f"Structure:\n{read_source_structure.invoke({})}\n"
            f"Next version will be: {next_version}\n"
        )
    else:
        # No versions found in MinIO, create empty directory
        # Init v1 by downloading default template
        
        # source_path = f"default"
        
        # success = minio_games_helper._download_game_version(source_path, data_path, source_type="folder")
        response = (
            f"📁 No existing versions found in MinIO. Starting with v1.\n"
        )
        # if success:
        #     response += f"Read {data_path / 'README.md'} for init instructions."
        
        return response
        
@tool
def read_file(
    file: Annotated[str, "Path to the file to read (relative to data/thread_id/)"],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """
    Read the content of a specified file/image within the thread's data directory.
    
    Parameters:
    - file: Relative path to the file (e.g., "src/game/scenes/GameScene.ts")
    
    Returns: Content of the file as a string, or an error message if the file does not exist.
    """
    config = ensure_config()
    configurable = config.get("configurable", {})
    thread_id = configurable.get("thread_id", "default")
    
    data_path = get_thread_data_path(thread_id)
    file_path = data_path / file
    
    if not file_path.exists():
        return Command(update={
            "messages": [
                ToolMessage(
                    content=f"✗ Error: File does not exist: data/{thread_id}/{file}",
                    tool_call_id=tool_call_id
                ),
            ]
        })
    
    mimetype, _ = mimetypes.guess_type(file_path.as_posix())
    try:
        if mimetype and mimetype.startswith("image/"):
            with open(file_path, 'rb') as f:
                encoded_image = base64.b64encode(f.read()).decode('utf-8')
            return Command(update={
                "messages": [
                    ToolMessage(
                        content=f"Reading image file: data/{thread_id}/{file}",
                        tool_call_id=tool_call_id
                    ),
                    HumanMessage(
                        content=[
                            {
                                "type": "image",
                                "base64": encoded_image,
                                "mime_type": mimetype
                            },
                        ]
                    )
                ]
            })
        else:
            content = ""
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return Command(update={
                "messages": [
                    ToolMessage(
                        content=content,
                        tool_call_id=tool_call_id
                    ),
                ]
            })
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        return Command(update={
            "messages": [
                ToolMessage(
                    content=f"✗ Error: {str(e)}",
                    tool_call_id=tool_call_id
                ),
            ]
        })

@tool
def str_replace_editor(
    file: Annotated[str, "Path to the file to perform string replacement on (relative to data/thread_id/)"],
    original: Annotated[str, "The original string to be replaced in the file"],
    replacement: Annotated[str, "The new string to replace the original with"]
) -> str:
    """
    Replace a specific string/section in an existing file without rewriting the entire file.
    
    Parameters:
    - file: Relative path to the file (e.g., "src/game/scenes/GameScene.ts")
    - original: The exact string to find and replace (must match exactly)
    - replacement: The new string to replace it with
    
    Example:
    - Updating a score variable: original="let score = 0;", replacement="let score = 100;"
    - Fixing a function: original="movePlayer() { ... }", replacement="movePlayer() { [new implementation] }"
    
    Returns: Success/failure message with the file path.
    """
    config = ensure_config()
    configurable = config.get("configurable", {})
    thread_id = configurable.get("thread_id", "default")
    
    data_path = get_thread_data_path(thread_id)
    file_path = data_path / file
    
    if not file_path.exists():
        return f"✗ Error: File does not exist: data/{thread_id}/{file}"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        updated_content = content.replace(original, replacement)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        return f"✓ Successfully replaced text in file: data/{thread_id}/{file}"
    except Exception as e:
        logger.error(f"Error replacing text in file: {e}")
        return f"✗ Error: {str(e)}"

@tool
def write_game_file(
    folder_path: Annotated[str, "Relative folder path (e.g., 'css', 'js', 'assets/images', or empty string for root)"],
    file_name: Annotated[str, "Name of the file to write (e.g., 'index.html', 'style.css', 'game.js', 'bg.png')"],
    content: Annotated[str, "The complete file content to write (for regular files). Leave empty if using url parameter."] = "",
    url: Annotated[str, "URL to download asset from (for assets). Leave empty if using content parameter."] = ""
) -> str:
    """
    Write COMPLETE file content to create new files or completely overwrite existing files.
    
    Two modes of operation:
    1. **Write complete source files (HTML/CSS/JS/TS):** Provide 'content', leave 'url' empty
       - Must provide FULL, COMPLETE file content
       - No placeholders like "// ... rest of code ..." allowed
       - Every function, class, and logic must be fully implemented
       
    2. **Download picked assets (images/audio):** Provide 'url', leave 'content' empty
       - Downloads assets from web search results or other sources
    
    Path structure: data/thread_id/<folder_path>/file_name
    
    Examples:
    - write_game_file("", "package.json", content='{"name": "game", "dependencies": {...}}')
    - write_game_file("src/app", "page.tsx", content="[COMPLETE React component code]")
    - write_game_file("src/game/scenes", "GameScene.ts", content="[COMPLETE Phaser scene code]")
    - write_game_file("public/assets/images", "player.png", url="https://example.com/player.png")
    - write_game_file("public/assets/audio", "jump.mp3", url="https://example.com/jump.mp3")
    
    Returns: Success/failure message with the file path.
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
def check_build_status(
    build_id: Annotated[str, "Build ID returned from build_source()"]
) -> str:
    """
    Check build status and retrieve the logs/preview URL of the deployed game.
    
    Parameters:
    - build_id: The build ID from the build_source() response
    """
    config = ensure_config()
    configurable = config.get("configurable", {})
    auth_token = configurable.get("auth_token", "")
    
    extra_headers = {
        "Authorization": auth_token,
        "Content-Type": "application/json",
    }
    
    build_status = ""
    build_response = None

    try:
        while build_status not in BUILD_COMPLETE_STATUSES:
            # Get build status
            build_response = app_preview_client.get_build_status(build_id, extra_headers=extra_headers)
            
            if build_response and build_response.data:
                response = {
                    "build_response": build_response.data.model_dump()
                }
                    
                return json.dumps(response) 
        
        return (
            "Failed to get build status after multiple attempts.\n"
            "Status: {status}\n"
            "Message: {message}\n"
            "Error: {error}"
        ).format(
            status=build_response.status,
            message=build_response.message,
            error=build_response.error
        )
    except Exception as e:
        logger.error(f"Failed to get build status: {e}")
        return f"❌ Error getting build status: {str(e)}"

@tool
def build_source(
    version: Annotated[str, "Version prefix for MinIO upload (e.g., 'v1', 'v2', 'v3')"]
) -> str:
    """
    Upload game source and trigger build process for the input version.

    Parameters:
    - version: Version for the build, can be current or next (e.g., 'v1', 'v2', 'v3')
    Returns: Build trigger confirmation message
    """
    config = ensure_config()
    configurable = config.get("configurable", {})
    thread_id = configurable.get("thread_id", "default")
    auth_token = configurable.get("auth_token", "")
    build_response = {}
    if SOURCE_TYPE == 'file':
        object_name = f"{thread_id}/{version}/{GAME_TAR}"
    else:
        object_name = f"{thread_id}/{version}/"
    
    data_path = get_thread_data_path(thread_id)
    
    if not data_path.exists():
        raise Exception(f"Data path does not exist: {data_path}. Run init_or_load_game_source() first.")

    
    try:
        if SOURCE_TYPE == 'file':
                # Create tar.gz archive
            source_path = data_path.parent / f"{GAME_TAR}"
            with tarfile.open(source_path, "w:gz") as tar:
                tar.add(str(data_path), arcname=".")
        else:
            source_path = str(data_path)
        
        minio_games_helper._upload_source_game(
            source_path=source_path,
            dest_path=object_name,
            source_type=SOURCE_TYPE
        )
        
    except Exception as e:
        build_response.update({
            'status': "failed"
        })
        logger.error(f"Failed to build and deploy source: {e}")
    finally:
        return json.dumps(
            {
                **build_response,
                "game_url": object_name,
                "version": version
            }
        )

@tool
def clean_up():
    """
    Clean up local data directory for the current thread.
    """
    config = ensure_config()
    configurable = config.get("configurable", {})
    thread_id = configurable.get("thread_id", "default")
    
    data_path = get_thread_data_path(thread_id)
    
    try:
        if data_path.exists():
            shutil.rmtree(data_path)
            return f"✓ Successfully cleaned up data for thread: {thread_id}"
        else:
            return f"ℹ No data to clean for thread: {thread_id}"
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        return f"✗ Error during cleanup: {str(e)}"
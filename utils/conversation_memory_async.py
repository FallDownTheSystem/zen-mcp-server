"""
Conversation Memory for AI-to-AI Multi-turn Discussions (Async version)

This is the async version of conversation_memory.py that works with the async
storage backend to fix the threading.Lock deadlock issue.

All storage operations are now async and must be awaited.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Configuration constants
# Get max conversation turns from environment, default to 20 turns (10 exchanges)
try:
    MAX_CONVERSATION_TURNS = int(os.getenv("MAX_CONVERSATION_TURNS", "20"))
    if MAX_CONVERSATION_TURNS <= 0:
        logger.warning(f"Invalid MAX_CONVERSATION_TURNS value ({MAX_CONVERSATION_TURNS}), using default of 20 turns")
        MAX_CONVERSATION_TURNS = 20
except ValueError:
    logger.warning(
        f"Invalid MAX_CONVERSATION_TURNS value ('{os.getenv('MAX_CONVERSATION_TURNS')}'), using default of 20 turns"
    )
    MAX_CONVERSATION_TURNS = 20

# Get conversation timeout from environment (in hours), default to 3 hours
try:
    CONVERSATION_TIMEOUT_HOURS = int(os.getenv("CONVERSATION_TIMEOUT_HOURS", "3"))
    if CONVERSATION_TIMEOUT_HOURS <= 0:
        logger.warning(
            f"Invalid CONVERSATION_TIMEOUT_HOURS value ({CONVERSATION_TIMEOUT_HOURS}), using default of 3 hours"
        )
        CONVERSATION_TIMEOUT_HOURS = 3
except ValueError:
    logger.warning(
        f"Invalid CONVERSATION_TIMEOUT_HOURS value ('{os.getenv('CONVERSATION_TIMEOUT_HOURS')}'), using default of 3 hours"
    )
    CONVERSATION_TIMEOUT_HOURS = 3

CONVERSATION_TIMEOUT_SECONDS = CONVERSATION_TIMEOUT_HOURS * 3600


class ConversationTurn(BaseModel):
    """Single turn in a conversation"""

    role: str  # "user" or "assistant"
    content: str
    timestamp: str
    files: Optional[list[str]] = None  # Files referenced in this turn
    images: Optional[list[str]] = None  # Images referenced in this turn
    tool_name: Optional[str] = None  # Tool used for this turn
    model_provider: Optional[str] = None  # Model provider (google, openai, etc)
    model_name: Optional[str] = None  # Specific model used
    model_metadata: Optional[dict[str, Any]] = None  # Additional model info


class ThreadContext(BaseModel):
    """Complete conversation context for a thread"""

    thread_id: str
    parent_thread_id: Optional[str] = None  # Parent thread for conversation chains
    created_at: str
    last_updated_at: str
    tool_name: str  # Tool that created this thread (preserved for attribution)
    turns: list[ConversationTurn]
    initial_context: dict[str, Any]  # Original request parameters


def get_storage():
    """Get in-memory storage backend for conversation persistence."""
    from .storage_backend_async import get_storage_backend

    return get_storage_backend()


async def create_thread(tool_name: str, initial_request: dict[str, Any], parent_thread_id: Optional[str] = None) -> str:
    """
    Create new conversation thread and return thread ID.

    This is now an async function and must be awaited.
    """
    thread_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Filter out non-serializable parameters to avoid JSON encoding issues
    filtered_context = {
        k: v
        for k, v in initial_request.items()
        if k not in ["temperature", "thinking_mode", "model", "continuation_id"]
    }

    context = ThreadContext(
        thread_id=thread_id,
        parent_thread_id=parent_thread_id,  # Link to parent for conversation chains
        created_at=now,
        last_updated_at=now,
        tool_name=tool_name,  # Track which tool initiated this conversation
        turns=[],  # Empty initially, turns added via add_turn()
        initial_context=filtered_context,
    )

    # Store in memory with configurable TTL to prevent indefinite accumulation
    storage = get_storage()
    key = f"thread:{thread_id}"
    await storage.setex(key, CONVERSATION_TIMEOUT_SECONDS, context.model_dump_json())

    logger.debug(f"[THREAD] Created new thread {thread_id} with parent {parent_thread_id}")

    return thread_id


async def get_thread(thread_id: str) -> Optional[ThreadContext]:
    """
    Retrieve thread context from in-memory storage.

    This is now an async function and must be awaited.
    """
    if not thread_id or not _is_valid_uuid(thread_id):
        return None

    try:
        storage = get_storage()
        key = f"thread:{thread_id}"
        data = await storage.get(key)

        if data:
            return ThreadContext.model_validate_json(data)
        return None
    except Exception:
        # Silently handle errors to avoid exposing storage details
        return None


async def add_turn(
    thread_id: str,
    role: str,
    content: str,
    files: Optional[list[str]] = None,
    images: Optional[list[str]] = None,
    tool_name: Optional[str] = None,
    model_provider: Optional[str] = None,
    model_name: Optional[str] = None,
    model_metadata: Optional[dict[str, Any]] = None,
) -> bool:
    """
    Add turn to existing thread with atomic file ordering.

    This is now an async function and must be awaited.
    """
    logger.debug(f"[FLOW] Adding {role} turn to {thread_id} ({tool_name})")

    context = await get_thread(thread_id)
    if not context:
        logger.debug(f"[FLOW] Thread {thread_id} not found for turn addition")
        return False

    # Check turn limit to prevent runaway conversations
    if len(context.turns) >= MAX_CONVERSATION_TURNS:
        logger.debug(f"[FLOW] Thread {thread_id} at max turns ({MAX_CONVERSATION_TURNS})")
        return False

    # Create new turn with complete metadata
    turn = ConversationTurn(
        role=role,
        content=content,
        timestamp=datetime.now(timezone.utc).isoformat(),
        files=files,  # Preserved for cross-tool file context
        images=images,  # Preserved for cross-tool visual context
        tool_name=tool_name,  # Track which tool generated this turn
        model_provider=model_provider,  # Track model provider
        model_name=model_name,  # Track specific model
        model_metadata=model_metadata,  # Additional model info
    )

    context.turns.append(turn)
    context.last_updated_at = datetime.now(timezone.utc).isoformat()

    # Save back to storage and refresh TTL
    try:
        storage = get_storage()
        key = f"thread:{thread_id}"
        await storage.setex(
            key, CONVERSATION_TIMEOUT_SECONDS, context.model_dump_json()
        )  # Refresh TTL to configured timeout
        return True
    except Exception as e:
        logger.debug(f"[FLOW] Failed to save turn to storage: {type(e).__name__}")
        return False


async def get_thread_chain(thread_id: str, max_depth: int = 20) -> list[ThreadContext]:
    """
    Traverse the parent chain to get all threads in conversation sequence.

    This is now an async function and must be awaited.
    """
    chain = []
    current_id = thread_id
    seen_ids = set()

    # Build chain from current to oldest
    while current_id and len(chain) < max_depth:
        # Prevent circular references
        if current_id in seen_ids:
            logger.warning(f"[THREAD] Circular reference detected in thread chain at {current_id}")
            break

        seen_ids.add(current_id)

        context = await get_thread(current_id)
        if not context:
            logger.debug(f"[THREAD] Thread {current_id} not found in chain traversal")
            break

        chain.append(context)
        current_id = context.parent_thread_id

    # Reverse to get chronological order (oldest first)
    chain.reverse()

    logger.debug(f"[THREAD] Retrieved chain of {len(chain)} threads for {thread_id}")
    return chain


def get_conversation_file_list(context: ThreadContext) -> list[str]:
    """
    Extract all unique files from conversation turns with newest-first prioritization.

    This function remains synchronous as it doesn't interact with storage.
    """
    if not context.turns:
        logger.debug("[FILES] No turns found, returning empty file list")
        return []

    # Collect files by walking backwards (newest to oldest turns)
    seen_files = set()
    file_list = []

    logger.debug(f"[FILES] Collecting files from {len(context.turns)} turns (newest first)")

    # Process turns in reverse order (newest first)
    for i in range(len(context.turns) - 1, -1, -1):  # REVERSE: newest turn first
        turn = context.turns[i]
        if turn.files:
            logger.debug(f"[FILES] Turn {i + 1} has {len(turn.files)} files: {turn.files}")
            for file_path in turn.files:
                if file_path not in seen_files:
                    # First time seeing this file - add it (this is the NEWEST reference)
                    seen_files.add(file_path)
                    file_list.append(file_path)
                    logger.debug(f"[FILES] Added new file: {file_path} (from turn {i + 1})")
                else:
                    # File already seen from a NEWER turn - skip this older reference
                    logger.debug(f"[FILES] Skipping duplicate file: {file_path} (newer version already included)")

    logger.debug(f"[FILES] Final file list ({len(file_list)}): {file_list}")
    return file_list


def get_conversation_image_list(context: ThreadContext) -> list[str]:
    """
    Extract all unique images from conversation turns with newest-first prioritization.

    This function remains synchronous as it doesn't interact with storage.
    """
    if not context.turns:
        logger.debug("[IMAGES] No turns found, returning empty image list")
        return []

    # Collect images by walking backwards (newest to oldest turns)
    seen_images = set()
    image_list = []

    logger.debug(f"[IMAGES] Collecting images from {len(context.turns)} turns (newest first)")

    # Process turns in reverse order (newest first)
    for i in range(len(context.turns) - 1, -1, -1):  # REVERSE: newest turn first
        turn = context.turns[i]
        if turn.images:
            logger.debug(f"[IMAGES] Turn {i + 1} has {len(turn.images)} images: {turn.images}")
            for image_path in turn.images:
                if image_path not in seen_images:
                    # First time seeing this image - add it (this is the NEWEST reference)
                    seen_images.add(image_path)
                    image_list.append(image_path)
                    logger.debug(f"[IMAGES] Added new image: {image_path} (from turn {i + 1})")
                else:
                    # Image already seen from a NEWER turn - skip this older reference
                    logger.debug(f"[IMAGES] Skipping duplicate image: {image_path} (newer version already included)")

    logger.debug(f"[IMAGES] Final image list ({len(image_list)}): {image_list}")
    return image_list


# Include all the other helper functions from the original file that don't need async
# (build_conversation_history, _plan_file_inclusion_by_size, _get_tool_formatted_content, etc.)
# These functions remain the same as they don't interact with storage


def _plan_file_inclusion_by_size(all_files: list[str], max_file_tokens: int) -> tuple[list[str], list[str], int]:
    """Plan which files to include based on size constraints."""
    if not all_files:
        return [], [], 0

    files_to_include = []
    files_to_skip = []
    total_tokens = 0

    logger.debug(f"[FILES] Planning inclusion for {len(all_files)} files with budget {max_file_tokens:,} tokens")

    for file_path in all_files:
        try:
            from utils.file_utils import estimate_file_tokens

            if os.path.exists(file_path) and os.path.isfile(file_path):
                # Use centralized token estimation for consistency
                estimated_tokens = estimate_file_tokens(file_path)

                if total_tokens + estimated_tokens <= max_file_tokens:
                    files_to_include.append(file_path)
                    total_tokens += estimated_tokens
                    logger.debug(
                        f"[FILES] Including {file_path} - {estimated_tokens:,} tokens (total: {total_tokens:,})"
                    )
                else:
                    files_to_skip.append(file_path)
                    logger.debug(
                        f"[FILES] Skipping {file_path} - would exceed budget (needs {estimated_tokens:,} tokens)"
                    )
            else:
                files_to_skip.append(file_path)
                # More descriptive message for missing files
                if not os.path.exists(file_path):
                    logger.debug(
                        f"[FILES] Skipping {file_path} - file no longer exists (may have been moved/deleted since conversation)"
                    )
                else:
                    logger.debug(f"[FILES] Skipping {file_path} - file not accessible (not a regular file)")

        except Exception as e:
            files_to_skip.append(file_path)
            logger.debug(f"[FILES] Skipping {file_path} - error during processing: {type(e).__name__}: {e}")

    logger.debug(
        f"[FILES] Inclusion plan: {len(files_to_include)} include, {len(files_to_skip)} skip, {total_tokens:,} tokens"
    )
    return files_to_include, files_to_skip, total_tokens


def build_conversation_history(context: ThreadContext, model_context=None, read_files_func=None) -> tuple[str, int]:
    """
    Build formatted conversation history for tool prompts with embedded file contents.

    This function remains synchronous as it only reads from the context object.
    """
    # Get the complete thread chain
    if context.parent_thread_id:
        # This thread has a parent, get the full chain
        # Note: This function would need to be made async if we keep it
        # For now, we'll just use the current thread
        all_turns = context.turns
        total_turns = len(context.turns)
        all_files = get_conversation_file_list(context)
        logger.debug("[THREAD] Note: Thread chaining requires async implementation")
    else:
        # Single thread, no parent chain
        all_turns = context.turns
        total_turns = len(context.turns)
        all_files = get_conversation_file_list(context)

    if not all_turns:
        return "", 0

    logger.debug(f"[FILES] Found {len(all_files)} unique files in conversation history")

    # Get model-specific token allocation early (needed for both files and turns)
    if model_context is None:
        from config import DEFAULT_MODEL, IS_AUTO_MODE
        from utils.model_context import ModelContext

        # In auto mode, use an intelligent fallback model for token calculations
        # since "auto" is not a real model with a provider
        model_name = DEFAULT_MODEL
        if IS_AUTO_MODE and model_name.lower() == "auto":
            # Use intelligent fallback based on available API keys
            from providers.registry import ModelProviderRegistry

            model_name = ModelProviderRegistry.get_preferred_fallback_model()

        model_context = ModelContext(model_name)

    token_allocation = model_context.calculate_token_allocation()
    max_file_tokens = token_allocation.file_tokens
    max_history_tokens = token_allocation.history_tokens

    logger.debug(f"[HISTORY] Using model-specific limits for {model_context.model_name}:")
    logger.debug(f"[HISTORY]   Max file tokens: {max_file_tokens:,}")
    logger.debug(f"[HISTORY]   Max history tokens: {max_history_tokens:,}")

    history_parts = [
        "=== CONVERSATION HISTORY (CONTINUATION) ===",
        f"Thread: {context.thread_id}",
        f"Tool: {context.tool_name}",  # Original tool that started the conversation
        f"Turn {total_turns}/{MAX_CONVERSATION_TURNS}",
        "You are continuing this conversation thread from where it left off.",
        "",
    ]

    # Embed files referenced in this conversation with size-aware selection
    if all_files:
        logger.debug(f"[FILES] Starting embedding for {len(all_files)} files")

        # Plan file inclusion based on size constraints
        files_to_include, files_to_skip, estimated_tokens = _plan_file_inclusion_by_size(all_files, max_file_tokens)

        if files_to_skip:
            logger.info(f"[FILES] Excluding {len(files_to_skip)} files from conversation history: {files_to_skip}")
            logger.debug("[FILES] Files excluded for various reasons (size constraints, missing files, access issues)")

        if files_to_include:
            history_parts.extend(
                [
                    "=== FILES REFERENCED IN THIS CONVERSATION ===",
                    "The following files have been shared and analyzed during our conversation.",
                    (
                        ""
                        if not files_to_skip
                        else f"[NOTE: {len(files_to_skip)} files omitted (size constraints, missing files, or access issues)]"
                    ),
                    "Refer to these when analyzing the context and requests below:",
                    "",
                ]
            )

            if read_files_func is None:
                from utils.file_utils import read_file_content

                # Process files for embedding
                file_contents = []
                total_tokens = 0
                files_included = 0

                for file_path in files_to_include:
                    try:
                        logger.debug(f"[FILES] Processing file {file_path}")
                        formatted_content, content_tokens = read_file_content(file_path)
                        if formatted_content:
                            file_contents.append(formatted_content)
                            total_tokens += content_tokens
                            files_included += 1
                            logger.debug(
                                f"File embedded in conversation history: {file_path} ({content_tokens:,} tokens)"
                            )
                        else:
                            logger.debug(f"File skipped (empty content): {file_path}")
                    except Exception as e:
                        # More descriptive error handling for missing files
                        try:
                            if not os.path.exists(file_path):
                                logger.info(
                                    f"File no longer accessible for conversation history: {file_path} - file was moved/deleted since conversation (marking as excluded)"
                                )
                            else:
                                logger.warning(
                                    f"Failed to embed file in conversation history: {file_path} - {type(e).__name__}: {e}"
                                )
                        except Exception:
                            # Fallback if path translation also fails
                            logger.warning(
                                f"Failed to embed file in conversation history: {file_path} - {type(e).__name__}: {e}"
                            )
                        continue

                if file_contents:
                    files_content = "".join(file_contents)
                    if files_to_skip:
                        files_content += (
                            f"\n[NOTE: {len(files_to_skip)} additional file(s) were omitted due to size constraints, missing files, or access issues. "
                            f"These were older files from earlier conversation turns.]\n"
                        )
                    history_parts.append(files_content)
                    logger.debug(
                        f"Conversation history file embedding complete: {files_included} files embedded, {len(files_to_skip)} omitted, {total_tokens:,} total tokens"
                    )
                else:
                    history_parts.append("(No accessible files found)")
                    logger.debug(f"[FILES] No accessible files found from {len(files_to_include)} planned files")
            else:
                # Fallback to original read_files function
                files_content = read_files_func(all_files)
                if files_content:
                    # Add token validation for the combined file content
                    from utils.token_utils import check_token_limit

                    within_limit, estimated_tokens = check_token_limit(files_content)
                    if within_limit:
                        history_parts.append(files_content)
                    else:
                        # Handle token limit exceeded for conversation files
                        error_message = f"ERROR: The total size of files referenced in this conversation has exceeded the context limit and cannot be displayed.\nEstimated tokens: {estimated_tokens}, but limit is {max_file_tokens}."
                        history_parts.append(error_message)
                else:
                    history_parts.append("(No accessible files found)")

        history_parts.extend(
            [
                "",
                "=== END REFERENCED FILES ===",
                "",
            ]
        )

    history_parts.append("Previous conversation turns:")

    # Build conversation turns (keeping the dual prioritization strategy)
    turn_entries = []  # Will store (index, formatted_turn_content) for chronological ordering later
    total_turn_tokens = 0
    file_embedding_tokens = sum(model_context.estimate_tokens(part) for part in history_parts)

    # Process turns in REVERSE chronological order (newest to oldest)
    for idx in range(len(all_turns) - 1, -1, -1):
        turn = all_turns[idx]
        turn_num = idx + 1
        role_label = "Claude" if turn.role == "user" else "Gemini"

        # Build the complete turn content
        turn_parts = []

        # Add turn header with tool attribution for cross-tool tracking
        turn_header = f"\n--- Turn {turn_num} ({role_label}"
        if turn.tool_name:
            turn_header += f" using {turn.tool_name}"

        # Add model info if available
        if turn.model_provider and turn.model_name:
            turn_header += f" via {turn.model_provider}/{turn.model_name}"

        turn_header += ") ---"
        turn_parts.append(turn_header)

        # Get tool-specific formatting if available
        # This includes file references and the actual content
        tool_formatted_content = _get_tool_formatted_content(turn)
        turn_parts.extend(tool_formatted_content)

        # Calculate tokens for this turn
        turn_content = "\n".join(turn_parts)
        turn_tokens = model_context.estimate_tokens(turn_content)

        # Check if adding this turn would exceed history budget
        if file_embedding_tokens + total_turn_tokens + turn_tokens > max_history_tokens:
            # Stop adding turns - we've reached the limit
            logger.debug(f"[HISTORY] Stopping at turn {turn_num} - would exceed history budget")
            logger.debug(f"[HISTORY]   File tokens: {file_embedding_tokens:,}")
            logger.debug(f"[HISTORY]   Turn tokens so far: {total_turn_tokens:,}")
            logger.debug(f"[HISTORY]   This turn: {turn_tokens:,}")
            logger.debug(f"[HISTORY]   Would total: {file_embedding_tokens + total_turn_tokens + turn_tokens:,}")
            logger.debug(f"[HISTORY]   Budget: {max_history_tokens:,}")
            break

        # Add this turn to our collection (we'll reverse it later for chronological presentation)
        turn_entries.append((idx, turn_content))
        total_turn_tokens += turn_tokens

    # Reverse the collected turns to restore chronological order (oldest first)
    turn_entries.reverse()

    # Add the turns in chronological order for natural LLM comprehension
    for _, turn_content in turn_entries:
        history_parts.append(turn_content)

    # Log what we included
    included_turns = len(turn_entries)
    total_turns = len(all_turns)
    if included_turns < total_turns:
        logger.info(f"[HISTORY] Included {included_turns}/{total_turns} turns due to token limit")
        history_parts.append(f"\n[Note: Showing {included_turns} most recent turns out of {total_turns} total]")

    history_parts.extend(
        [
            "",
            "=== END CONVERSATION HISTORY ===",
            "",
            "IMPORTANT: You are continuing an existing conversation thread. Build upon the previous exchanges shown above,",
            "reference earlier points, and maintain consistency with what has been discussed.",
            "",
            "DO NOT repeat or summarize previous analysis, findings, or instructions that are already covered in the",
            "conversation history. Instead, provide only new insights, additional analysis, or direct answers to",
            "the follow-up question / concerns / insights. Assume the user has read the prior conversation.",
            "",
            f"This is turn {len(all_turns) + 1} of the conversation - use the conversation history above to provide a coherent continuation.",
        ]
    )

    # Calculate total tokens for the complete conversation history
    complete_history = "\n".join(history_parts)
    from utils.token_utils import estimate_tokens

    total_conversation_tokens = estimate_tokens(complete_history)

    # Summary log of what was built
    user_turns = len([t for t in all_turns if t.role == "user"])
    assistant_turns = len([t for t in all_turns if t.role == "assistant"])
    logger.debug(
        f"[FLOW] Built conversation history: {user_turns} user + {assistant_turns} assistant turns, {len(all_files)} files, {total_conversation_tokens:,} tokens"
    )

    return complete_history, total_conversation_tokens


def _get_tool_formatted_content(turn: ConversationTurn) -> list[str]:
    """Get tool-specific formatting for a conversation turn."""
    if turn.tool_name:
        try:
            # Dynamically import to avoid circular dependencies
            from server import TOOLS

            tool = TOOLS.get(turn.tool_name)
            if tool:
                # Use inheritance pattern - try to call the method directly
                try:
                    return tool.format_conversation_turn(turn)
                except AttributeError:
                    # Tool doesn't implement format_conversation_turn - use default
                    pass
        except Exception as e:
            # Log but don't fail - fall back to default formatting
            logger.debug(f"[HISTORY] Could not get tool-specific formatting for {turn.tool_name}: {e}")

    # Default formatting
    return _default_turn_formatting(turn)


def _default_turn_formatting(turn: ConversationTurn) -> list[str]:
    """Default formatting for conversation turns."""
    parts = []

    # Add files context if present
    if turn.files:
        parts.append(f"Files used in this turn: {', '.join(turn.files)}")
        parts.append("")  # Empty line for readability

    # Add the actual content
    parts.append(turn.content)

    return parts


def _is_valid_uuid(val: str) -> bool:
    """Validate UUID format for security"""
    try:
        uuid.UUID(val)
        return True
    except ValueError:
        return False

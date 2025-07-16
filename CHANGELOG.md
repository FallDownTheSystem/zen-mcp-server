# Changelog

## [6.6.8] - 2025-01-16

### Fixed
- **Thread Pool Exhaustion Fix**: Removed `asyncio.to_thread` calls from consensus tool
  - The mysterious limit of exactly 12 was caused by thread pool exhaustion
  - Each consensus call was using 4-5 threads for conversation management operations
  - With a possible default thread pool size of 12 (on 8-core systems), this explained the pattern:
    - 5 calls × ~2.4 threads average = 12 threads (deadlock on 6th)
    - 3 calls × 4 threads = 12 threads (deadlock on 4th)
  - Removed `asyncio.to_thread` calls for `get_thread()`, `add_turn()`, `create_thread()`, and `_format_consensus_for_storage()`
  - These operations are fast enough to run directly without threading
  - This eliminates the thread pool exhaustion issue entirely

### Changed
- **Enhanced Logging**: Added detailed thread pool state logging
  - Logs executor max_workers and active thread count on each consensus call
  - Added logging to HybridLock to track async lock creation
  - Helps diagnose thread pool issues in production

## [6.6.7] - 2025-01-17

### Added
- **HybridLock Implementation**: Added a dual-mode lock class for future async compatibility
  - Automatically uses asyncio.Lock() in async contexts and threading.Lock() in sync contexts
  - Prevents event loop blocking when registry is accessed from async code
  - Foundation for future registry improvements

### Changed
- **Registry Documentation**: Added warning about threading locks in async contexts
  - Documents that get_provider_for_model() uses threading locks
  - Recommends caching providers when making concurrent calls
  - Complements the consensus tool fix by explaining the underlying issue

## [6.6.6] - 2025-01-17

### Fixed
- **Consensus Tool Provider Reuse**: Fixed deadlock caused by redundant provider lookups
  - The refinement phase was calling `get_model_provider()` again, causing lock contention
  - Now reuses providers from the initial phase stored in a provider_map
  - This eliminates the deterministic deadlock pattern (5 calls with 2 models, 3 calls with 4 models)
  - The issue was that each `get_model_provider()` call acquires a threading.Lock in the registry
  - With multiple models running concurrently, this created a race condition leading to deadlock

## [6.6.5] - 2025-01-17

### Fixed
- **Thread Pool Exhaustion**: Fixed consensus tool deadlock after 5 calls
  - Increased default thread pool executor from ~32 to 100 workers
  - Each consensus call uses multiple threads for storage operations (get_thread, add_turn, create_thread)
  - With the default pool size, 5 consensus calls would exhaust available threads
  - Added automatic thread pool configuration when event loop is running
  - Custom thread name prefix "zen-consensus" for easier debugging

### Changed
- **Consensus Tool Simplification**: Refactored to use simpler async patterns
  - Replaced `asyncio.create_task()` + `asyncio.wait()` with `asyncio.gather()`
  - Added timeout wrapper methods for cleaner timeout handling
  - Removed unnecessary JSON serialization threading (fast enough for main thread)
  - Kept threading only for actual blocking I/O operations

## [6.6.4] - 2025-01-17

### Fixed
- **OpenAI Async Implementation**: Fixed AttributeError in OpenAI async implementation
  - Removed call to non-existent `_supports_temperature()` method
  - Now uses `_get_effective_temperature()` to determine temperature support
  - Added proper handling for o3-pro and o3-deep-research models to use responses endpoint
  - Matches the sync implementation's logic for parameter handling

## [6.6.3] - 2025-01-17

### Fixed
- **Gemini Async Content Format**: Fixed validation error in Gemini async implementation
  - Text content must be wrapped in {"text": content} dictionary, not passed as raw string
  - This matches the sync implementation's format requirements
  - Fixes "Input should be a valid dictionary" validation errors

## [6.6.2] - 2025-01-17

### Fixed
- **Critical Async Fix**: Fixed blocking I/O in Gemini async implementation
  - Image processing now uses `asyncio.to_thread()` to avoid blocking the event loop
  - Moved asyncio import to top of file for better performance
  - This prevents potential deadlocks when processing images with Gemini models

## [6.6.1] - 2025-07-16

### Added
- **Gemini Async Support**: Added native async support to Gemini provider
  - Implemented `agenerate_content()` method using `client.aio.models.generate_content`
  - Uses same retry logic as sync version but with async sleep
  - Completes the async migration for all major providers

### Removed
- **DIAL Provider**: Removed DIAL provider and all references
  - Deleted `providers/dial.py` and test files
  - Removed DIAL_API_KEY from all configuration files
  - Updated documentation and scripts to remove DIAL references
  - Cleaned up provider registry and model restrictions

### Changed
- **Simplified Provider List**: Streamlined to core providers only
  - Google Gemini (native)
  - OpenAI (native) 
  - X.AI GROK (native)
  - Custom endpoints (local/private)
  - OpenRouter (catch-all)

## [6.6.0] - 2025-07-16

### Added
- **Native Async Support**: Added `agenerate_content()` method to all providers
  - Base provider class now includes async method that wraps sync by default
  - OpenAI provider implements native async using AsyncOpenAI client
  - Eliminates all threading and deadlock issues by working WITH httpx's async nature
  - Consensus tool now uses async methods directly with asyncio.gather()

### Changed
- **Consensus Tool Refactored**: Removed all threading complexity
  - No more thread pools, semaphores, or asyncio.to_thread()
  - Uses native async provider methods for true parallel execution
  - Much simpler and more reliable implementation
  - Should completely eliminate the deadlock issues

### Removed
- **Threading Infrastructure**: Removed from consensus tool
  - Removed custom thread pool executor
  - Removed thread semaphore
  - Removed complex thread isolation attempts
  - All replaced with clean async/await patterns

## [6.5.13] - 2025-07-16

### Changed
- **Connection Pool Strategy**: Disabled connection pooling entirely as a temporary fix
  - Set max_connections=1 to prevent pool exhaustion
  - The consistent deadlock pattern (5th call with 2 models, 3rd with 4) suggests pool exhaustion
  - This is less efficient but should prevent the deadlock
  - Added more detailed logging to track client initialization

### Fixed
- **HTTP Client Configuration**: Simplified httpx client setup
  - Removed complex transport configuration that wasn't working
  - Using basic httpx.Client with minimal pooling
  - Added http1=True, http2=False to force HTTP/1.1

## [6.5.12] - 2025-07-16

### Fixed
- **CRITICAL FIX - Root Cause of Deadlock Found**: Fixed the actual cause of the consensus deadlock
  - The issue: `httpx.RequestsTransport` doesn't exist in modern httpx versions
  - This caused the custom httpx client initialization to fail silently
  - The code fell back to a default OpenAI client that uses async-aware httpcore
  - When called from a thread (via asyncio.to_thread), httpcore tries to interact with the main event loop
  - This creates a deadlock: the event loop waits for the thread, while the thread waits for the event loop
  - Solution: Removed dependency on non-existent RequestsTransport
  - Now using a properly configured synchronous httpx client with:
    - Disabled keepalive connections to prevent accumulation
    - Connection: close header to force connection closure
    - trust_env=False to avoid async proxy detection
  - Made the error handling fail loudly instead of silently falling back to a broken configuration

### Changed
- **Requirements Comment**: Updated comment for requests dependency
  - No longer mentions httpx.RequestsTransport which doesn't exist

## [6.5.11] - 2025-07-16

### Fixed
- **Critical Deadlock Fix - Thread Pool Exhaustion**: Fixed the root cause of the 5th call deadlock
  - The issue: Default asyncio thread pool was getting exhausted after multiple consensus calls
  - Each consensus call uses multiple threads (2-4 depending on models and phases)
  - The default thread pool has limited workers and they weren't being released properly
  - Solution: Implemented custom thread pool executor with 10 workers dedicated to consensus
  - This prevents thread exhaustion and ensures reliable parallel execution
  - The custom thread pool completely resolves the deadlock issue

### Changed
- **Fixed Provider Call Arguments**: Corrected the argument order when calling provider.generate_content()
  - Fixed positional argument mismatch causing "TypeError: takes from 3 to 6 positional arguments but 8 were given"
  - Added missing `max_output_tokens` parameter (as None) in the correct position
  - Changed timeout from positional to keyword argument for clarity
  - Applied fix to both initial consultation and refinement phases

### Removed
- **Isolation Test Code**: Removed temporary isolation test code that was used for debugging
  - Removed dummy sleep operations that replaced real provider calls
  - Restored original provider.generate_content() calls in refinement phase
  - Deleted ISOLATION_TEST_ACTIVE.md marker file

## [6.5.10] - 2025-07-16

### Fixed
- **Connection Pool Exhaustion Fix**: Addressed the 5th call deadlock issue
  - Added "Connection: close" header to prevent connection accumulation
  - Disabled retries (max_retries=0) to avoid connection buildup
  - Limited concurrent threads to 2 with semaphore to match typical consensus usage
  - The deadlock was caused by connections being kept alive and accumulating across calls

## [6.5.9] - 2025-07-16

### Fixed
- **Consensus Tool - Additional Pre-computation**: Moved more operations outside parallel tasks
  - Pre-create ModelContext instances before async tasks to avoid concurrent initialization
  - Pre-fetch system prompt once for all models instead of fetching in each task
  - Pass pre-created resources to async methods to minimize work inside parallel execution
  - This further reduces contention and potential deadlock scenarios

## [6.5.8] - 2025-07-16

### Fixed
- **Consensus Tool Deadlock - Registry Access**: Fixed concurrent registry access in async tasks
  - Moved `get_model_provider()` calls outside of async tasks in both initial and refinement phases
  - Providers are now obtained sequentially before creating parallel tasks
  - This prevents multiple async tasks from accessing the ModelProviderRegistry simultaneously
  - The deadlock was caused by concurrent threads trying to acquire registry locks at the same time

## [6.5.7] - 2025-07-16

### Fixed
- **Consensus Tool Deadlock - Caching Solution**: Fixed deadlock caused by repeated get_capabilities calls
  - Added timeout caching in `_get_model_timeout` to prevent repeated provider calls
  - The deadlock occurred when multiple threads called `get_capabilities()` during refinement phase
  - Now caches timeout values per model for the duration of each consensus execution
  - Cache is cleared at the start of each new execution to ensure fresh data
  - This prevents the threading deadlock that was freezing the server at turn 5-6

## [6.5.6] - 2025-07-16

### Fixed
- **Identified Deadlock in Consensus Refinement Phase**: Added debugging to pinpoint deadlock location
  - The deadlock occurs during refinement phase setup in `_get_phase_timeout`
  - Specifically when calling `_get_model_timeout` which calls `provider.get_capabilities()`
  - This is called in a loop for each model during timeout calculation
  - Added debug logging to track the exact point of failure
  - The issue appears to be that `get_capabilities()` is being called multiple times and causing a deadlock

## [6.5.5] - 2025-07-16

### Fixed
- **Added Debugging for Deadlock Investigation**: Added extensive logging to pinpoint deadlock location
  - The deadlock occurs in `ModelContext.calculate_token_allocation()` method
  - Specifically when accessing `self.capabilities.context_window`
  - Added debug logging in capabilities property getter and calculate_token_allocation
  - Added try/catch around token allocation formatting to catch any exceptions
  - This will help identify if the deadlock is in provider.get_capabilities() or elsewhere

## [6.5.4] - 2025-07-16

### Fixed
- **Consensus History Extraction Limit**: Limited extraction to last 10 turns to prevent deadlock
  - The deadlock at turn 6 was likely caused by processing increasingly large accumulated data
  - Now only processes the most recent 10 turns when extracting previous consensus responses
  - This prevents potential infinite loops or memory issues with very long conversations
  - Added detailed debugging logs to track turn processing
  - Removed incomplete async lock implementation that wasn't addressing the root cause

## [6.5.3] - 2025-07-16

### Fixed
- **Consensus Data Structure Issue**: Fixed potential circular reference and data explosion
  - The consensus tool was storing the entire `response_data` object in `model_metadata`
  - This included nested metadata that could create circular references or exponential growth
  - Now stores only essential data: model name, response text, and status
  - Added defensive error handling in `_extract_previous_consensus` to catch and log any issues
  - This was the root cause of the deadlock at turn 6 - not async/blocking operations
  - Reverted one of the asyncio.to_thread wraps from v6.5.1 as it's no longer needed

## [6.5.2] - 2025-07-16

### Fixed
- **Comprehensive Async Deadlock Fix**: Wrapped all blocking operations in consensus tool
  - `get_thread()` calls now wrapped in `asyncio.to_thread()` to prevent blocking on storage reads
  - `add_turn()` calls wrapped to prevent blocking on storage writes and Pydantic serialization
  - `create_thread()` wrapped to prevent blocking during thread creation
  - `_format_consensus_for_storage()` wrapped as it does CPU-intensive string operations
  - `json.dumps()` operations wrapped when serializing large response data
  - These operations were blocking the event loop when processing accumulated data from 6+ turns
  - The deadlock at turn 6 should now be fully resolved

## [6.5.1] - 2025-07-16

### Fixed
- **Consensus Tool Async Deadlock**: Fixed deadlock in consensus history extraction during continuations
  - The `_build_model_specific_history` method was doing synchronous operations in async context
  - When processing large accumulated consensus data (6+ turns), the synchronous extraction blocked the event loop
  - Now wrapped in `asyncio.to_thread()` to prevent blocking
  - This allows the event loop to remain responsive while processing conversation history
  - Deadlock that occurred at turn 6 should now be resolved

## [6.5.0] - 2025-07-16

### Fixed
- **Consensus Tool Prompt Deduplication**: Fixed issue where conversation history was included twice in consensus prompts
  - The server adds full conversation history to the prompt field during continuations
  - Consensus tool also adds its own model-specific history, causing duplication
  - Now consensus tool detects and uses `_original_user_prompt` to avoid this duplication
  - This significantly reduces prompt size and prevents token limit issues in multi-turn consensus
  - Each model still receives appropriate context without redundancy

### Improved
- **Cleaner Code Structure**: Aligned consensus tool with architectural patterns
  - Uses `model_config = {"extra": "allow"}` to accept server-provided fields
  - Maintains backward compatibility by falling back to full prompt if needed
  - Better separation of concerns between server and tool responsibilities

## [6.4.9] - 2025-07-16

### Reverted
- **Consensus Tool Full History**: Restored full conversation history for consensus tool
  - Reverted the change from v6.4.6 that limited consensus tool to only new user input
  - Consensus tool now receives the full conversation history like all other tools
  - The actual deadlock was caused by thread safety issues (fixed in v6.4.7), not prompt size
  - The consensus tool can handle large prompts with proper token validation in place

## [6.4.8] - 2025-07-16

### Improved
- **Complete Thread Safety for ModelProviderRegistry**: Extended thread safety to all mutating methods
  - Added thread locks to `register_provider()`, `clear_cache()`, and `unregister_provider()` methods
  - Added comprehensive class docstring documenting thread safety guarantees
  - Ensures all registry operations are thread-safe, not just provider access
  - Based on review feedback from Gemini confirming the implementation is correct

## [6.4.7] - 2025-07-16

### Fixed
- **Thread Safety in ModelProviderRegistry**: Fixed deadlock caused by race conditions in multi-threaded access
  - Added thread-safe singleton initialization with class-level lock
  - Added instance-level lock for provider initialization and caching
  - Implemented double-check locking pattern to prevent duplicate provider creation
  - Fixed race conditions when consensus tool runs multiple models in parallel via asyncio.to_thread()
  - The deadlock was occurring when two threads tried to initialize the same provider simultaneously
  - This was the actual cause of the consensus tool hanging on the 5th call

## [6.4.6] - 2025-07-16

### Fixed
- **Consensus Tool Deadlock - Final Fix**: Prevented server from embedding full conversation history in consensus prompts
  - The server was adding the entire conversation history to the prompt field for all tools
  - This caused exponential growth: by turn 8, the prompt was 15,895 chars (from a 14 char question!)
  - Consensus tool now receives only the new user input, not the full history
  - The consensus tool extracts its own conversation history via `_extract_previous_consensus()`
  - This prevents the double-embedding of conversation history that was causing exponential growth
  - Other tools (like chat) still receive the full conversation history as before

## [6.4.5] - 2025-07-16

### Fixed
- **Consensus Tool Deadlock - Root Cause**: Fixed exponential prompt growth causing deadlocks after 4-5 continuation turns
  - Modified `_format_consensus_for_storage()` to store only model responses, not the entire JSON structure
  - This prevents each turn from embedding all previous turns' full JSON, eliminating exponential growth
  - Consensus responses now store full model outputs but without metadata and conversation history
  - Added comprehensive debug logging throughout consensus workflow to identify bottlenecks
  - Integrated proper token limit validation using existing `_validate_token_limit()` method
  - Added automatic prompt truncation when conversation history exceeds token limits
  - The deadlock was caused by massive prompts (exponentially growing JSON) blocking the event loop

### Improved
- **Consensus Tool Logging**: Added detailed debug logging to trace execution flow
  - Logs prompt sizes at each stage of preparation
  - Tracks conversation history extraction and building
  - Reports token counts and validation results
  - Helps identify performance bottlenecks in production

## [6.4.4] - 2025-07-16

### Fixed
- **Complete AsyncIO Deadlock Fix**: Resolved all blocking I/O operations causing deadlocks in the consensus tool
  - Made `build_conversation_history` and `_plan_file_inclusion_by_size` async in conversation_memory.py
  - Made `_prepare_file_content_for_prompt` async in base_tool.py
  - Made `build_standard_prompt`, `build_user_prompt`, and `prepare_chat_style_prompt` async in SimpleTool
  - Wrapped all file I/O operations (os.path.exists, open, read_files, etc.) in asyncio.to_thread()
  - Updated all callers to properly await these async methods
  - This ensures the main event loop never blocks on file I/O, preventing deadlocks during parallel execution
  - The consensus tool can now safely run multiple model calls in parallel without freezing

### Changed
- Updated multiple test files to support async methods with @pytest.mark.asyncio decorator
- All file operations now run in thread pool workers instead of blocking the event loop

## [6.4.3] - 2025-07-16

### Fixed
- **AsyncIO Deadlock in Consensus Tool**: Fixed critical deadlock issue when using httpx with asyncio.to_thread()
  - Root cause: httpx.Client auto-detects event loops and tries to use asyncio from within thread pool workers
  - Solution: Configured httpx to use RequestsTransport backend instead of default HTTPTransport
  - This forces purely synchronous behavior and prevents event loop detection
  - Added `requests>=2.25.0` dependency to support the transport backend
  - Comprehensive fix validated by Gemini Pro as the most robust solution
  - All 526 tests pass with the fix applied

## [6.4.2] - 2025-07-16

### Improved
- **Consensus Model Name Storage**: Enhanced how consensus tool stores model information in conversation history
  - Now stores actual model names (e.g., "gemini-2.5-pro, o3, grok-4") instead of generic "3 models"
  - Added `consulted_models` array to model metadata for programmatic access
  - Improved conversation history display showing exact models used in each consensus round
  - Better tracking and transparency of which models participated in consensus

### Fixed
- **Consensus Continuation Fallback**: Fixed fallback model resolution for consensus tool continuations
  - When no model is found for consensus continuations, uses proper fallback model for token calculations
  - Prevents "Model 'auto' is not available" errors in edge cases

## [6.4.1] - 2025-07-16

### Fixed
- **Consensus Tool Continuation**: Fixed "Model '3 models' is not available" error when continuing consensus conversations
  - Modified `reconstruct_thread_context` to skip consensus tool turns when looking for a model to inherit
  - Consensus tool now properly handles continuations with same or different model sets
  - Each consensus request independently uses the models specified in the request
  - Preserves full conversation context while preventing model inheritance issues

## [6.4.0] - 2025-07-16

### Added
- **Model-Specific Timeout Configuration**: Added timeout field to ModelCapabilities for per-model timeout configuration
  - Standard models: 180s (3 minutes)
  - O3 models: 300s (5 minutes) 
  - O3-Pro: 1800s (30 minutes)
  - O3-Deep-Research: 3600s (1 hour)
  - Timeouts are properly propagated to HTTP clients

- **Phase-Level Timeouts for Consensus**: Implemented phase timeouts to prevent hanging on unresponsive models
  - Phase timeout = max(all model timeouts) + 60s coordination buffer
  - Uses `asyncio.wait()` with timeout parameter for proper task cancellation
  - Partial results are preserved when some models timeout

- **Comprehensive Timeout Tests**: Added test suites for timeout scenarios
  - `test_consensus_timeouts.py` - 14 tests covering timeout configuration and enforcement
  - `test_consensus_error_propagation.py` - 5 tests covering error handling

- **Async Architecture Documentation**: Created detailed documentation at `docs/consensus-async-architecture.md`
  - Explains timeout hierarchy (phase > model > HTTP)
  - Documents configuration options and best practices
  - Includes troubleshooting guide

### Fixed
- **Consensus Error Propagation**: Errors from model providers are now returned immediately without waiting for timeouts
  - Uses proper exception handling in async tasks
  - Maintains model order even with mixed success/error responses
  - Refinement phase errors don't affect initial responses

### Improved
- **Thread Safety**: Verified all storage operations happen outside parallel execution phases
  - No race conditions in conversation memory updates
  - Atomic turn additions after consensus gathering
  - Clean separation between parallel execution and storage

## [6.3.1] - 2025-07-14

### Fixed
- **o3-pro Model Support**: Fixed o3-pro API integration issues
  - Fixed response parsing to correctly extract text from `response.output[].content[].text` structure
  - Fixed request format to use simple `input` and `instructions` parameters for the `/v1/responses` endpoint
  - Removed unsupported `max_completion_tokens` parameter from responses API calls
  - Added comprehensive logging for debugging o3-pro responses
  - Increased default timeout from 30s to 5 minutes to accommodate o3-pro's longer processing times
  - o3-pro now correctly uses "high" reasoning effort mode

### Added
- **Response Timeout Configuration**: Added environment variable support for custom timeouts
  - `CUSTOM_CONNECT_TIMEOUT` - Connection timeout (default: 30s)
  - `CUSTOM_READ_TIMEOUT` - Read timeout (default: 10 minutes)
  - `CUSTOM_WRITE_TIMEOUT` - Write timeout (default: 10 minutes)
  - `CUSTOM_POOL_TIMEOUT` - Pool timeout (default: 10 minutes)

### Improved
- **Developer Experience**: Allow Python environment setup without API keys
  - Modified `run-server.sh` to warn but continue when API keys are missing
  - Modified `run-server.ps1` to warn but continue when API keys are missing
  - New contributors can now explore the codebase and run tests without obtaining API keys first

## [6.3.0] - 2025-07-12

### Fixed
- **Consensus Tool Parallel Execution**: Fixed critical performance issue where models were consulted sequentially instead of in parallel
  - Added `await asyncio.to_thread()` wrapper to make synchronous `generate_content` calls non-blocking
  - This allows true parallel execution when consulting multiple models
  - Performance improvement: Total time is now max(individual model times) instead of sum(individual model times)
  - Example: o3 (1 min) + Gemini (2 min) now takes 2 minutes total instead of 3 minutes

## [6.2.7] - 2025-07-12

### Fixed
- **Consensus Tool Response Timing**: Fixed timing metadata to report both initial and refinement response times separately
  - Added `initial_response_time` and `refinement_response_time` fields to track each phase
  - Added `total_response_time` field showing the sum of both phases
  - Similarly separated token usage tracking with `input_tokens_initial`, `output_tokens_initial`, `input_tokens_refinement`, and `output_tokens_refinement`
  - Provides total token counts in `total_input_tokens` and `total_output_tokens`
  - For models without refinement phase, renamed `response_time` to `initial_response_time` for consistency

## [6.2.6] - 2025-07-12

### Removed
- **Test Files for Deleted Tools**: Removed 3 simulator test files that tested non-existent tools
  - `test_line_number_validation.py` - Tested removed analyze/refactor tools
  - `test_openrouter_fallback.py` - Tested removed codereview/analyze/debug tools  
  - `test_ollama_custom_url.py` - Tested removed analyze tool

### Changed
- **Test Suite Cleanup**: Updated 12 test files to remove references to deleted tools
  - Replaced all mock usage of removed tools (analyze, thinkdeep, testgen, etc.) with chat or consensus
  - Updated test assertions and mock data to reflect only available tools
  - Fixed `test_consensus_refinement.py` to use `execute()` instead of non-existent `execute_workflow()`
- **Configuration Cleanup**: Removed unused constants and references
  - Removed `DEFAULT_THINKING_MODE_THINKDEEP` constant from config.py
  - Updated server.py comments to remove references to `/zen:thinkdeeper` shortcut
  - Cleaned up import statements for removed constants
- **Documentation Updates**: 
  - Updated `docker/README.md` to list only chat and consensus tools
  - Updated `tools/simple/__init__.py` docstring to remove references to deleted tools
  - Removed workflow-related comments from `tools/shared/schema_builders.py`

### Fixed
- **Import Errors**: Fixed `simulator_tests/__init__.py` by commenting out imports for deleted test files
- **Test Runner**: Fixed `communication_simulator_test.py` quick test list to use existing test names

## [6.2.5] - 2025-07-11

### Changed
- **Consensus Tool Prompts**: Refocused on breakthrough discovery and insight recognition
  - System prompt now emphasizes finding the key insight that makes everything click
  - Simplified format: Approach → Why This Works → Implementation → Trade-offs
  - Cross-feedback prompt changed from "REFINEMENT REQUEST" to "OTHER APPROACHES"
  - Encourages models to adopt superior solutions rather than defend positions
  - Aligned with Grok 4's multi-agent approach where agents spot each other's best insights
  - Removed consensus-building language in favor of best-solution-finding
- **Documentation Consolidation**: Merged all documentation into a comprehensive README
  - Incorporated WSL setup, Docker deployment, and platform-specific guides
  - Added context revival system explanation
  - Added localization configuration details
  - Removed separate docs folder as all content is now in README
  - Enhanced README with better formatting and organization
- **Documentation Cleanup**: Removed references to deleted tools
  - Updated advanced-usage.md, ai-collaboration.md, configuration.md
  - Updated locale-configuration.md to reflect only chat and consensus tools
  - Removed documentation for 14 deleted tools (analyze, debug, etc.)
  - Fixed simulator test imports for missing test files

## [6.2.4] - 2025-07-11

### Improved
- **Consensus Tool Response Format**: Simplified consensus tool output for better token efficiency
  - Now returns single `responses` array with only the final response from each model
  - Automatically uses refined response when cross-feedback is enabled, otherwise uses initial response
  - Removed separate `phases.initial` and `phases.refined` arrays to reduce token usage by ~50%
  - Updated refinement prompt to ensure models provide complete, self-contained responses
  - No more duplicate content between initial and refined phases

## [6.2.3] - 2025-07-11

### Added
- **Response Timing**: Added timing information to model response metadata
  - Response time (in seconds) now included in metadata field for all responses
  - Helps identify slow models when running consensus across multiple models
  - Implemented in SimpleTool base class for Chat tool
  - Added directly to consensus tool for each model's response
  - Includes timing even for error responses to track failed model performance

### Changed
- **Fork Attribution**: Added `__forked_by__ = "FallDownTheSystem"` to config.py alongside original author
- **Temperature as Parameter**: Moved temperature from hardcoded config values to tool request parameters
  - Chat tool now has `temperature` parameter with default 0.5 (balanced responses)
  - Consensus tool now has `temperature` parameter with default 0.2 (analytical/focused responses)
  - Removed `TEMPERATURE_ANALYTICAL` and `TEMPERATURE_BALANCED` from config.py
  - Users can now customize temperature per request instead of using fixed values

### Removed
- **Unused Config Variables**: Cleaned up config.py by removing unused variables
  - Removed `DEFAULT_CONSENSUS_TIMEOUT` and `DEFAULT_CONSENSUS_MAX_INSTANCES_PER_COMBINATION` (obsolete)
  - Simplified MCP_PROMPT_SIZE_LIMIT calculation by removing unused function
  - Updated tests to reflect the changes

## [6.2.2] - 2025-07-11

### Fixed
- **Token/Character Limit Mismatch**: Fixed validation bug where character limits were compared against token counts
  - `_validate_token_limit` now correctly converts character limit to token limit (÷4)
  - Prevents false validation failures when using large file contexts
  - Fixes issue where ~15k token files would fail against 60k character limit
  - Added comprehensive tests to prevent regression
- **Consensus Tool Error**: Fixed model context not being provided for file preparation
  - Added ModelContext creation for each model in _consult_model method
  - Ensures proper token allocation for file content across models

### Changed
- **Consensus Prompts**: Transformed from judgment-based to collaborative solution-finding
  - Removed confidence scores and timeline estimates
  - Focus on balanced analysis, trade-offs, and practical recommendations
  - Encourages models to build on each other's insights during refinement phase

## [6.2.1] - 2025-07-11

### Changed
- **Consensus Tool Simplified**: Removed step-based workflow parameters for cleaner interface
  - Changed from WorkflowTool to SimpleTool base class
  - Replaced `step` parameter with `prompt` for clarity
  - Removed unnecessary fields: `step_number`, `total_steps`, `next_step_required`, `findings`, `confidence`
  - Tool now inherits from ToolRequest instead of WorkflowRequest
  - Simplified test suite to match new interface
  - No functional changes - still parallel execution with cross-model feedback

### Improved
- **Tool Descriptions**: Reduced verbosity by 70-80% to preserve context
  - Chat tool: 297 → 66 words (78% reduction)
  - Consensus tool: 424 → 80 words (81% reduction)
  - Removed redundant use cases and implementation details
  - Focused on essential information for tool selection

### Removed
- **Workflow Infrastructure**: Removed unused workflow base classes and utilities
  - Deleted `tools/workflow/` directory and all its contents
  - Removed `WorkflowRequest`, `BaseWorkflowRequest`, and `ConsolidatedFindings` from base_models.py
  - Cleaned up imports in `tools/shared/__init__.py`
  - Removed obsolete workflow-based test files
  - No impact on functionality - workflow classes were no longer used after consensus simplification

## [6.2.0] - 2025-07-11

### Changed
- **Improved README**: Updated installation instructions to match original repository format
  - Added comprehensive uvx installation guide for Claude Desktop and Claude Code
  - Added proper shell command wrapper for cross-platform compatibility
  - Improved configuration documentation with detailed environment variables
  - Added collapsible sections for better organization

## [6.1.0] - 2025-07-11

### Added
- **Grok-4 Support**: Added support for xAI's latest Grok-4 model (grok-4-0709)
  - "grok" alias now defaults to grok-4 instead of grok-3
  - Added aliases: grok4, grok-4, grok-4-latest
  - Grok-4 supports extended thinking/reasoning capabilities
  - Updated tests and documentation

## [6.0.1] - 2025-07-11

### Changed
- **Breaking Change**: Removed stance-based analysis from consensus tool
  - Models no longer take for/against/neutral stances
  - Each model provides balanced, objective analysis
  - Simplified model configuration - just specify model name
  - System prompt updated to encourage balanced perspectives
  - All tests updated to work without stances

## [6.0.0] - 2025-07-11 - Simplified Fork

### Changed
- Simplified codebase to include only two essential tools: Chat and Consensus
- Updated documentation to reflect the streamlined architecture
- Reduced test suite to focus on the remaining tools
- **Major Enhancement**: Consensus tool completely redesigned for parallel execution with cross-model feedback
  - **Parallel Processing**: All models consulted simultaneously using asyncio.gather() (3x faster for 3 models)
  - **Two-Phase Workflow**:
    - Phase 1: Initial responses gathered from all models in parallel
    - Phase 2: Each model sees others' responses and can refine their position
  - **Cross-Model Learning**: Models incorporate insights from other perspectives, often converging toward consensus
  - **Single Atomic Operation**: Everything happens in one tool call (no more multi-step workflow)
  - **Robust Error Handling**: Individual model failures don't stop others (return_exceptions=True)
  - **Flexible Configuration**:
    - Enable/disable cross-feedback with `enable_cross_feedback` parameter
    - Custom refinement prompts via `cross_feedback_prompt` parameter
    - Same model can be used multiple times for different perspectives
  - **Response Structure**: Returns both initial and refined responses for comparison
  - **Performance**: ~2-3 seconds total for 3 models vs ~6-9 seconds sequential

### Removed
- Removed analyze tool
- Removed challenge tool
- Removed codereview tool
- Removed debug tool
- Removed docgen tool
- Removed listmodels tool
- Removed planner tool
- Removed precommit tool
- Removed refactor tool
- Removed secaudit tool
- Removed testgen tool
- Removed thinkdeep tool
- Removed tracer tool
- Removed version tool
- Removed associated test files for deleted tools
- Removed unused system prompts

### Maintained
- Full support for multiple AI providers (OpenAI, Gemini, xAI, OpenRouter, Ollama)
- Cross-tool conversation memory functionality
- File and image handling capabilities
- All core infrastructure and utilities

## Example: New Consensus Workflow

```python
# Single call to get consensus with cross-model feedback
arguments = {
    "prompt": "Should we implement real-time collaboration? 30% of support tickets request this feature",
    "models": [
        {"model": "gemini-pro"},
        {"model": "o3-mini"},
        {"model": "flash"}
    ],
    "enable_cross_feedback": true  # Enable two-phase refinement
}

# Returns both phases:
# 1. Initial responses (all models respond in parallel)
# 2. Refined responses (models adjust based on others' insights)
```

## Notes

This is a simplified fork of the original Zen MCP Server focused on providing just the essential Chat and Consensus tools for a streamlined experience. The parallel consensus workflow represents a major architectural improvement, providing faster and more nuanced multi-model analysis.
# Claude Development Guide for Zen MCP Server - Simplified

This file contains essential commands and workflows for developing and maintaining the Simplified Zen MCP Server when working with Claude. This version includes only the Chat and Consensus tools.

## Quick Reference Commands

### Code Quality Checks

Before making any changes or submitting PRs, always run the comprehensive quality checks:

```bash
# Activate virtual environment first
source venv/bin/activate

# Run all quality checks (linting, formatting, tests)
./code_quality_checks.sh
```

This script automatically runs:
- Ruff linting with auto-fix (excludes .zen_venv and test_simulation_files)
- Black code formatting (excludes .zen_venv and test_simulation_files)
- Import sorting with isort (excludes .zen_venv and test_simulation_files)
- Complete unit test suite (excluding integration tests)
- Verification that all checks pass 100%

**IMPORTANT:** The virtual environment (.zen_venv) is excluded from all formatting operations to prevent modifying dependencies.

**Run Integration Tests (requires API keys):**
```bash
# Run integration tests that make real API calls
./run_integration_tests.sh

# Run integration tests + simulator tests
./run_integration_tests.sh --with-simulator
```

### Server Management

#### Setup/Update the Server
```bash
# Run setup script (handles everything)
./run-server.sh
```

This script will:
- Set up Python virtual environment
- Install all dependencies
- Create/update .env file
- Configure MCP with Claude
- Verify API keys

#### View Logs
```bash
# Follow logs in real-time
./run-server.sh -f

# Or manually view logs
tail -f logs/mcp_server.log
```

### Log Management

#### View Server Logs
```bash
# View last 500 lines of server logs
tail -n 500 logs/mcp_server.log

# Follow logs in real-time
tail -f logs/mcp_server.log

# View specific number of lines
tail -n 100 logs/mcp_server.log

# Search logs for specific patterns
grep "ERROR" logs/mcp_server.log
grep "tool_name" logs/mcp_activity.log
```

#### Monitor Tool Executions Only
```bash
# View tool activity log (focused on tool calls and completions)
tail -n 100 logs/mcp_activity.log

# Follow tool activity in real-time
tail -f logs/mcp_activity.log

# Use simple tail commands to monitor logs
tail -f logs/mcp_activity.log | grep -E "(TOOL_CALL|TOOL_COMPLETED|ERROR|WARNING)"
```

### Testing

#### IMPORTANT: Activate Virtual Environment First
Before running ANY tests, you MUST activate the virtual environment:

**On Windows (Git Bash/WSL):**
```bash
# From the project root directory
source .zen_venv/Scripts/activate
```

**On macOS/Linux:**
```bash
# From the project root directory
source .zen_venv/bin/activate
```

If the virtual environment is not activated, tests will fail with import errors!

#### Run All Simulator Tests
```bash
# After activating venv, run the complete test suite
python communication_simulator_test.py

# Run tests with verbose output
python communication_simulator_test.py --verbose
```

#### Quick Test Mode (Recommended for Time-Limited Testing)
```bash
# Run quick test mode - 6 essential tests that provide maximum functionality coverage
python communication_simulator_test.py --quick

# Run quick test mode with verbose output
python communication_simulator_test.py --quick --verbose
```

**Quick mode runs these 6 essential tests:**
- `basic_conversation` - Basic chat functionality
- `content_validation` - Content validation and deduplication
- `model_thinking_config` - Flash/flashlite model testing
- `o3_model_selection` - O3 model selection testing
- `consensus_workflow_accurate` - Consensus tool testing
- `chat_validation` - Chat tool validation

#### Run Individual Simulator Tests (For Detailed Testing)
```bash
# List all available tests
python communication_simulator_test.py --list-tests

# Run a single test individually
python communication_simulator_test.py --individual basic_conversation

# Run individual test with verbose output for debugging
python communication_simulator_test.py --individual consensus_workflow_accurate --verbose
```

#### Run Unit Tests Only
```bash
# ALWAYS activate venv first!
source .zen_venv/Scripts/activate  # Windows Git Bash
# OR
source .zen_venv/bin/activate      # macOS/Linux

# Run all unit tests (excluding integration tests that require API keys)
python -m pytest tests/ -v -m "not integration"

# Run specific test file
python -m pytest tests/test_chat_simple.py -v

# Run specific test class
python -m pytest tests/test_litellm_provider.py::TestLiteLLMProvider -v

# Run specific test method
python -m pytest tests/test_litellm_provider.py::TestLiteLLMProvider::test_model_validation -v

# Run multiple specific tests
python -m pytest tests/test_litellm_provider.py tests/test_consensus.py -v -m "not integration"

# Run tests with coverage
python -m pytest tests/ --cov=. --cov-report=html -m "not integration"

# Run tests matching a pattern
python -m pytest tests/ -k "o3_deep_research" -v

# Stop at first failure (useful for debugging)
python -m pytest tests/ -v -x -m "not integration"
```

#### Common Test Issues and Solutions

**Issue: Import errors or module not found**
```bash
# Solution: Activate virtual environment
source .zen_venv/Scripts/activate  # Windows
source .zen_venv/bin/activate      # macOS/Linux
```

**Issue: Tests hanging or timing out**
```bash
# Solution: Exclude integration tests that make real API calls
python -m pytest tests/ -v -m "not integration"
```

**Issue: Specific test failing on Windows due to path issues**
```bash
# Solution: Run tests excluding problematic ones
python -m pytest tests/ -v -m "not integration" -k "not test_detect_home_patterns_linux"
```

### Development Workflow

#### Before Making Changes
1. Ensure virtual environment is activated: 
   - Windows: `source .zen_venv/Scripts/activate`
   - macOS/Linux: `source .zen_venv/bin/activate`
2. Run quality checks: `./code_quality_checks.sh`
3. Check logs to ensure server is healthy: `tail -n 50 logs/mcp_server.log`

#### After Making Changes
1. Run quality checks again: `./code_quality_checks.sh`
2. Run integration tests locally: `./run_integration_tests.sh`
3. Run quick test mode for fast validation: `python communication_simulator_test.py --quick`
4. Check logs for any issues: `tail -n 100 logs/mcp_server.log`
5. Restart Claude session to use updated code

#### Before Committing/PR
1. Final quality check: `./code_quality_checks.sh`
2. Run integration tests: `./run_integration_tests.sh`
3. Run quick test mode: `python communication_simulator_test.py --quick`
4. Verify all tests pass 100%

### Available Tools

This simplified version includes only two tools:

1. **Chat Tool** (`chat`)
   - General conversational AI
   - File and image support
   - Uses SimpleTool architecture

2. **Consensus Tool** (`consensus`)
   - Parallel multi-model consensus gathering
   - Two-phase workflow: initial responses + cross-model refinement
   - All models consulted simultaneously for speed
   - Models can see each other's responses and refine their answers
   - Single tool call with simplified interface
   - Robust error handling - partial failures don't stop other models
   - Optional: disable cross-feedback for faster single-phase consensus

## LiteLLM Migration

As of version 6.0, the Zen MCP Server has been migrated to use LiteLLM for unified model access:

### Key Changes:
- **Unified Provider**: All models now use a single `LiteLLMProvider` instead of separate provider implementations
- **Simplified Architecture**: Removed individual provider classes (OpenAI, Gemini, XAI, etc.)
- **Configuration**: Model configuration is now handled via `litellm_config.yaml` and `model_metadata.yaml`
- **Backward Compatibility**: All existing model aliases and functionality preserved

### Benefits:
- **Reduced Complexity**: Single provider handles all model routing
- **Better Reliability**: LiteLLM handles fallbacks, retries, and error handling
- **Easier Maintenance**: Single codebase for all model integrations
- **Future-Proof**: Easy to add new models supported by LiteLLM
- **Enhanced Observability**: Comprehensive monitoring and cost tracking via LiteLLM callbacks

### Using the Consensus Tool

The consensus tool operates in a single call with parallel processing:

```python
# Example request structure:
{
    "prompt": "Should we implement real-time collaboration features?",
    "models": [
        {"model": "gemini-pro"},
        {"model": "o3"},
        {"model": "flash"}
    ],
    "relevant_files": ["/path/to/spec.md"],  # Optional
    "enable_cross_feedback": true,           # Optional, defaults to true
    "cross_feedback_prompt": null            # Optional custom refinement prompt
}
```

The tool will:
1. Send your question to all models simultaneously (parallel execution)
2. Collect initial responses from each model
3. Share each model's response with the others for refinement
4. Allow models to refine their answers based on collective insights
5. Return both initial and refined responses in a single result

**Example Response Structure:**
```json
{
    "status": "consensus_complete",
    "models_consulted": 3,
    "successful_initial_responses": 3,
    "refined_responses": 3,
    "phases": {
        "initial": [
            {
                "model": "gemini-pro",
                "status": "success",
                "response": "I support this feature because...",
                "metadata": {"input_tokens": 150, "output_tokens": 180}
            }
            // ... other initial responses
        ],
        "refined": [
            {
                "model": "gemini-pro",
                "stance": "for", 
                "status": "success",
                "initial_response": "I support this feature because...",
                "refined_response": "After considering other perspectives, I still support but with caveats...",
                "metadata": {"input_tokens": 250, "output_tokens": 230}
            }
            // ... other refined responses
        ]
    }
}
```

**Performance Notes:**
- Parallel execution is ~3x faster than sequential for 3 models
- Cross-feedback adds one additional round of API calls
- Disable cross-feedback for fastest results: `"enable_cross_feedback": false`
- Models that fail don't block others - check `failed_models` array

## Observability and Monitoring

The Zen MCP Server includes comprehensive observability features that provide monitoring, cost tracking, and performance metrics for all LLM API calls through LiteLLM's callback system.

### Features

#### Cost Tracking
- **Per-model costs**: Track API costs for each model
- **Usage analytics**: Monitor token usage patterns
- **Cumulative tracking**: Track total costs across all calls
- **Cost optimization**: Identify expensive operations

#### Latency Monitoring
- **Response times**: Track API call latency by model
- **Performance trends**: Monitor average response times
- **Bottleneck identification**: Identify slow-performing models

#### Secure Logging
- **PII prevention**: Automatic redaction of sensitive information
- **Content safety**: Secure handling of user data
- **Configurable verbosity**: Control logging detail level

### Configuration

Configure observability via environment variables:

```bash
# Core Settings
OBSERVABILITY_ENABLED=true          # Enable/disable observability (default: true)
OBSERVABILITY_VERBOSE=false         # Enable verbose LiteLLM logging (default: false)
OBSERVABILITY_LOG_REQUESTS=false    # Log request content (default: false)
OBSERVABILITY_LOG_RESPONSES=false   # Log response content (default: false)
OBSERVABILITY_REDACT_PII=true       # Enable PII redaction (default: true)
```

#### Development Mode
```bash
# Enable detailed logging for development
OBSERVABILITY_ENABLED=true
OBSERVABILITY_VERBOSE=true
OBSERVABILITY_LOG_REQUESTS=true
OBSERVABILITY_LOG_RESPONSES=true
OBSERVABILITY_REDACT_PII=false
```

#### Production Mode
```bash
# Secure production configuration
OBSERVABILITY_ENABLED=true
OBSERVABILITY_VERBOSE=false
OBSERVABILITY_LOG_REQUESTS=false
OBSERVABILITY_LOG_RESPONSES=false
OBSERVABILITY_REDACT_PII=true
```

### Monitoring Output

#### Activity Logs
Observability events are logged to `logs/mcp_activity.log`:
- `LLM_CALL_START`: When LLM request begins
- `LLM_CALL_END`: When LLM request completes
- `LLM_SUCCESS`: When LLM request succeeds
- `LLM_FAILURE`: When LLM request fails

#### Cost Tracking Logs
Cost information is logged to `logs/mcp_server.log`:
```
COST_TRACKING: model=gpt-4o cost=$0.002500 usage={'input_tokens': 100, 'output_tokens': 50, 'total_tokens': 150} total_cost=$0.012500 calls=5
```

#### Latency Metrics
Performance metrics are logged to `logs/mcp_server.log`:
```
LATENCY_TRACKING: model=gpt-4o latency=2.345s avg_latency=2.123s calls=5
```

### Security Features

#### PII Redaction
The observability system automatically redacts sensitive information:
- Email addresses → `[EMAIL]`
- Phone numbers → `[PHONE]`
- Social security numbers → `[SSN]`
- Credit card numbers → `[CARD]`
- API keys → `[API_KEY]`
- Passwords/secrets → `[REDACTED]`

#### Content Safety
- Content length limits prevent excessive logging
- Configurable verbosity controls data exposure
- Error isolation ensures observability failures don't affect LLM calls

### Testing

Test the observability system:

```bash
# Run observability tests
source .zen_venv/Scripts/activate
python -m pytest tests/test_observability.py -v

# Test all components
python -m pytest tests/test_observability.py::TestSecureLogger -v
python -m pytest tests/test_observability.py::TestCostTracker -v
python -m pytest tests/test_observability.py::TestLatencyTracker -v
```

### Implementation

The observability system is implemented through:
- **ZenObservabilityHandler**: Custom LiteLLM callback handler
- **CostTracker**: Cost monitoring and analytics
- **LatencyTracker**: Performance monitoring
- **SecureLogger**: PII redaction and safe logging
- **LiteLLM Integration**: Automatic callback registration

For detailed implementation information, see `observability/README.md`.

### Common Troubleshooting

#### Server Issues
```bash
# Check if Python environment is set up correctly
./run-server.sh

# View recent errors
grep "ERROR" logs/mcp_server.log | tail -20

# Check virtual environment
which python
# Should show: .../zen-mcp-server/.zen_venv/bin/python
```

#### Test Failures
```bash
# First try quick test mode to see if it's a general issue
python communication_simulator_test.py --quick --verbose

# Check server logs during test execution
tail -f logs/mcp_server.log

# Run tests with debug output
LOG_LEVEL=DEBUG python communication_simulator_test.py --individual basic_conversation
```

#### Linting Issues
```bash
# Auto-fix most linting issues
ruff check . --fix
black .
isort .

# Check what would be changed without applying
ruff check .
black --check .
isort --check-only .
```

### File Structure Context

- `./code_quality_checks.sh` - Comprehensive quality check script
- `./run-server.sh` - Server setup and management
- `communication_simulator_test.py` - End-to-end testing framework
- `simulator_tests/` - Individual test modules
- `tests/` - Unit test suite
- `tools/` - MCP tool implementations (only chat.py and consensus.py)
- `providers/` - AI provider implementations (unified LiteLLM provider)
- `systemprompts/` - System prompt definitions (only chat and consensus prompts)
- `logs/` - Server log files

### Environment Requirements

- Python 3.11+ with virtual environment
- All dependencies from `requirements.txt` installed
- Proper API keys configured in `.env` file

### Versioning Guidelines

The project follows **Semantic Versioning** (MAJOR.MINOR.PATCH):

- **MAJOR**: Breaking changes or major architectural shifts (e.g., 5.x → 6.x for the simplified fork)
- **MINOR**: New features or significant improvements (e.g., adding Grok-4 support)
- **PATCH**: Bug fixes and small improvements (e.g., fixing token limit validation)

#### Version Bumping Process

1. **Update version using the bump script:**
   ```bash
   # For bug fixes:
   python scripts/bump_version.py patch

   # For new features:
   python scripts/bump_version.py minor

   # For breaking changes:
   python scripts/bump_version.py major
   ```

2. **The script automatically:**
   - Updates `__version__` in `config.py`
   - Updates `__updated__` to current date
   - Preserves file formatting

3. **Manual steps after bumping:**
   - Update CHANGELOG.md with the new version entry
   - Document all changes under appropriate categories (Added/Changed/Fixed/Removed)
   - Commit both config.py and CHANGELOG.md changes together

#### Version History Notes

- **5.8.2**: Last version before the simplified fork
- **6.0.0**: First version of the simplified fork (major version bump due to breaking changes)
- **Current**: Version is maintained in `config.py` as the single source of truth

### Troubleshooting Development Issues

#### Virtual Environment Issues

**Problem: "No virtual environment found!" when running scripts**
```bash
# Solution: Create/activate the virtual environment
./run-server.sh  # This creates .zen_venv if it doesn't exist
source .zen_venv/Scripts/activate  # Windows
source .zen_venv/bin/activate      # macOS/Linux
```

**Problem: Import errors when running tests**
```bash
# Solution: Always activate venv before running any Python commands
source .zen_venv/Scripts/activate  # Windows
python -m pytest tests/ -v
```

#### Code Quality Check Issues

**Problem: Black/ruff reformatting files in .zen_venv**
```bash
# This has been fixed in the latest version of code_quality_checks.sh
# If you still see this issue, manually update the script to exclude .zen_venv
```

**Problem: Tests failing due to linting issues**
```bash
# Run the quality checks with auto-fix before testing
./code_quality_checks.sh
```

#### Platform-Specific Issues

**Problem: Tests failing on Windows due to Linux path tests**
```bash
# Exclude problematic tests on Windows
python -m pytest tests/ -v -m "not integration" -k "not test_detect_home_patterns_linux"
```

**Problem: Line ending issues on Windows**
```bash
# Configure git to handle line endings
git config core.autocrlf true
```

This guide provides everything needed to efficiently work with the Simplified Zen MCP Server codebase using Claude.
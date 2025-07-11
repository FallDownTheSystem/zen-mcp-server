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
- Ruff linting with auto-fix
- Black code formatting 
- Import sorting with isort
- Complete unit test suite (excluding integration tests)
- Verification that all checks pass 100%

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

#### Run All Simulator Tests
```bash
# Run the complete test suite
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
# Run all unit tests (excluding integration tests that require API keys)
python -m pytest tests/ -v -m "not integration"

# Run specific test file
python -m pytest tests/test_chat_simple.py -v

# Run tests with coverage
python -m pytest tests/ --cov=. --cov-report=html -m "not integration"
```

### Development Workflow

#### Before Making Changes
1. Ensure virtual environment is activated: `source .zen_venv/bin/activate`
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
   - Multi-model consensus gathering
   - Sequential model consultation
   - Stance-based analysis (for/against/neutral)
   - Uses WorkflowTool architecture

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
- `providers/` - AI provider implementations
- `systemprompts/` - System prompt definitions (only chat and consensus prompts)
- `logs/` - Server log files

### Environment Requirements

- Python 3.11+ with virtual environment
- All dependencies from `requirements.txt` installed
- Proper API keys configured in `.env` file

This guide provides everything needed to efficiently work with the Simplified Zen MCP Server codebase using Claude.
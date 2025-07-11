# Changelog

## [Simplified Fork] - 2024-01-11

### Changed
- Simplified codebase to include only two essential tools: Chat and Consensus
- Updated documentation to reflect the streamlined architecture
- Reduced test suite to focus on the remaining tools

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

## Notes

This is a simplified fork of the original Zen MCP Server focused on providing just the essential Chat and Consensus tools for a streamlined experience.
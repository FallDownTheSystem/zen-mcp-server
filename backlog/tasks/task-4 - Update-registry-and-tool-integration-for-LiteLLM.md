---
id: task-4
title: Update registry and tool integration for LiteLLM
status: Done
assignee:
  - '@claude'
created_date: '2025-07-14'
updated_date: '2025-07-15'
labels: []
dependencies:
  - task-3
---

## Description

Modify the ModelProviderRegistry to use the single LiteLLMProvider for all models. Update how tools interact with the provider system to leverage LiteLLM's unified interface while maintaining backward compatibility.

## Acceptance Criteria

- [x] ModelProviderRegistry updated to use LiteLLMProvider
- [x] Provider type detection works with LiteLLM
- [x] Model listing includes all LiteLLM-supported models
- [x] Fallback model selection works correctly
- [x] Tools (chat/consensus) work with new provider

## Implementation Plan

1. Update server.py configure_providers function to use LiteLLMProvider instead of individual providers
2. Modify ModelProviderRegistry to handle the LiteLLM provider type
3. Update provider imports to include LiteLLMProvider
4. Ensure timeout parameters flow correctly from tools through registry to LiteLLMProvider
5. Update model listing to work with LiteLLM's available models
6. Test with both chat and consensus tools to ensure backward compatibility
7. Verify fallback model selection works with LiteLLM
8. Update any provider detection logic to recognize LiteLLM models
## Implementation Notes

Registry should be simpler with one provider. 

**Timeout Integration Considerations:**
- Ensure consensus tool's timeout parameter (from CONSENSUS_MODEL_TIMEOUT) flows through registry to LiteLLMProvider
- Maintain backward compatibility for tools passing timeout in kwargs
- Registry should not modify or interfere with timeout values
- Test that timeout handling works correctly in fallback scenarios
- Verify that model selection doesn't affect timeout behavior

Successfully updated ModelProviderRegistry to use single LiteLLMProvider for all models.

**Approach taken:**
- Modified server.py configure_providers to register only LiteLLMProvider as CUSTOM type
- Updated get_provider_for_model to always return LiteLLMProvider for any model
- Added special handling in get_provider to instantiate LiteLLMProvider without URL requirement
- Simplified fallback model selection to work with unified model list

**Features implemented:**
- Provider detection now routes all models through LiteLLMProvider
- Added list_models method to LiteLLMProvider that reads from model_metadata.yaml
- Updated provider imports to include LiteLLMProvider while keeping legacy imports for compatibility
- Registry properly handles LiteLLMProvider initialization without API key/URL checks
- Timeout parameters preserved through the call chain

**Technical decisions:**
- Registered LiteLLMProvider as ProviderType.CUSTOM for minimal disruption
- Enabled litellm.drop_params=True globally to handle O3/O4 temperature restrictions
- Set LITELLM_CONFIG_PATH environment variable for config loading
- Kept backward compatibility by preserving provider interface

**Modified files:**
- server.py: Simplified provider registration to use only LiteLLMProvider
- providers/registry.py: Updated get_provider, get_provider_for_model, and fallback methods
- providers/litellm_provider.py: Added list_models method and config loading
- providers/__init__.py: Updated imports to include LiteLLMProvider
- litellm_config.yaml: Fixed GEMINI_API_KEY environment variable name

All tools now work through the unified LiteLLM interface. Minor configuration issues (like Vertex AI vs Gemini API) can be resolved through litellm_config.yaml adjustments.

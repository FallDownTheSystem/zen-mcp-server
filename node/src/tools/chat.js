/**
 * Chat Tool
 *
 * Single-provider conversational AI with context and continuation support.
 * Handles context processing, provider calls, and state management.
 */

import { createToolResponse, createToolError } from './index.js';
import { processUnifiedContext, createFileContext } from '../utils/contextProcessor.js';
import { generateContinuationId, addMessageToHistory } from '../continuationStore.js';
import { CHAT_PROMPT } from '../systemPrompts.js';

/**
 * Chat tool implementation
 * @param {object} args - Tool arguments
 * @param {object} dependencies - Injected dependencies (config, providers, continuationStore)
 * @returns {object} MCP tool response
 */
export async function chatTool(args, dependencies) {
  try {
    const { config, providers, continuationStore } = dependencies;
    
    // Validate required arguments
    if (!args.prompt || typeof args.prompt !== 'string') {
      return createToolError('Prompt is required and must be a string');
    }

    // Extract and validate arguments
    const {
      prompt,
      model = 'auto',
      files = [],
      continuation_id,
      temperature = 0.5,
      use_websearch = false,
      images = [],
      reasoning_effort = 'medium'
    } = args;

    let conversationHistory = [];
    let continuationId = continuation_id;

    // Load existing conversation if continuation_id provided
    if (continuationId) {
      try {
        const existingState = await continuationStore.get(continuationId);
        if (existingState) {
          conversationHistory = existingState.messages || [];
        } else {
          // Invalid continuation ID - start fresh
          continuationId = generateContinuationId();
        }
      } catch (error) {
        console.error('Error loading conversation:', error);
        // Continue with fresh conversation on error
        continuationId = generateContinuationId();
      }
    } else {
      // Generate new continuation ID for new conversation
      continuationId = generateContinuationId();
    }

    // Process context (files, images, web search)
    let contextMessage = null;
    if (files.length > 0 || images.length > 0 || use_websearch) {
      try {
        const contextRequest = {
          files: Array.isArray(files) ? files : [],
          images: Array.isArray(images) ? images : [],
          webSearch: use_websearch ? prompt : null
        };
        
        const contextResult = await processUnifiedContext(contextRequest);
        
        // Create context message from files
        if (contextResult.files.length > 0) {
          contextMessage = createFileContext(contextResult.files, {
            includeMetadata: true,
            includeErrors: true
          });
        }
        
        // Add web search results if available (placeholder for now)
        if (contextResult.webSearch && !contextResult.webSearch.placeholder) {
          // Future implementation: add web search results to context
          console.log('[Chat] Web search results available but not yet implemented');
        }
        
      } catch (error) {
        console.error('Error processing context:', error);
        // Continue without context if processing fails
      }
    }

    // Build message array for provider
    const messages = [];
    
    // Add system prompt
    messages.push({
      role: 'system',
      content: CHAT_PROMPT
    });
    
    // Add conversation history
    messages.push(...conversationHistory);
    
    // Add context message if available
    if (contextMessage) {
      messages.push(contextMessage);
    }
    
    // Add user prompt
    messages.push({
      role: 'user',
      content: prompt
    });

    // Select provider
    let selectedProvider;
    let providerName;
    
    if (model === 'auto') {
      // Auto-select first available provider
      const availableProviders = Object.keys(providers.getProviders()).filter(name => {
        const provider = providers.getProvider(name);
        return provider && provider.isAvailable && provider.isAvailable(config);
      });
      
      if (availableProviders.length === 0) {
        return createToolError('No providers available. Please configure at least one API key.');
      }
      
      providerName = availableProviders[0];
      selectedProvider = providers.getProvider(providerName);
    } else {
      // Use specified provider/model
      // Try to map model to provider
      providerName = mapModelToProvider(model);
      selectedProvider = providers.getProvider(providerName);
      
      if (!selectedProvider) {
        return createToolError(`Provider not found for model: ${model}`);
      }
      
      if (!selectedProvider.isAvailable(config)) {
        return createToolError(`Provider ${providerName} is not available. Check API key configuration.`);
      }
    }

    // Prepare provider options
    const providerOptions = {
      model: model === 'auto' ? undefined : model,
      temperature,
      reasoning_effort,
      config
    };

    // Call provider
    let response;
    try {
      response = await selectedProvider.invoke(messages, providerOptions);
    } catch (error) {
      console.error(`Provider ${providerName} error:`, error);
      return createToolError(`Provider error: ${error.message}`);
    }

    // Validate response
    if (!response || !response.content) {
      return createToolError('Provider returned invalid response');
    }

    // Add assistant response to conversation history
    const assistantMessage = {
      role: 'assistant',
      content: response.content
    };
    
    const updatedMessages = [...messages, assistantMessage];

    // Save conversation state
    try {
      const conversationState = {
        messages: updatedMessages,
        provider: providerName,
        model: model,
        lastUpdated: Date.now()
      };
      
      await continuationStore.set(continuationId, conversationState);
    } catch (error) {
      console.error('Error saving conversation:', error);
      // Continue even if save fails
    }

    // Create response with continuation
    const result = {
      content: response.content,
      continuation: {
        id: continuationId,
        provider: providerName,
        model: model,
        messageCount: updatedMessages.length
      }
    };
    
    // Add metadata if available
    if (response.metadata) {
      result.metadata = response.metadata;
    }

    return createToolResponse(JSON.stringify(result, null, 2));

  } catch (error) {
    console.error('Chat tool error:', error);
    return createToolError('Chat tool failed', error);
  }
}

/**
 * Map model name to provider name
 * @param {string} model - Model name
 * @returns {string} Provider name
 */
function mapModelToProvider(model) {
  const modelLower = model.toLowerCase();
  
  // OpenAI models
  if (modelLower.includes('gpt') || modelLower.includes('o1') || 
      modelLower.includes('o3') || modelLower.includes('o4')) {
    return 'openai';
  }
  
  // XAI models
  if (modelLower.includes('grok')) {
    return 'xai';
  }
  
  // Google models
  if (modelLower.includes('gemini') || modelLower.includes('flash') || 
      modelLower.includes('pro') || modelLower === 'google') {
    return 'google';
  }
  
  // Default fallback
  return 'openai';
}

// Tool metadata
chatTool.description = 'GENERAL CHAT & COLLABORATIVE THINKING - For development assistance, brainstorming, and code analysis. Supports files, images, and conversation continuation.';
chatTool.inputSchema = {
  type: 'object',
  properties: {
    prompt: {
      type: 'string',
      description: 'Your question or topic with relevant context. More detail enables better responses. Example: "How should I structure the authentication module for this Express.js API?"',
    },
    model: {
      type: 'string',
      description: 'AI model to use. Examples: "auto" (recommended), "gemini-2.5-flash", "o3", "grok-4-0709". Defaults to auto-selection.',
    },
    files: {
      type: 'array',
      items: { type: 'string' },
      description: 'File paths to include as context (absolute paths required). Example: ["/path/to/src/auth.js", "/path/to/config.json"]',
    },
    images: {
      type: 'array',
      items: { type: 'string' },
      description: 'Image paths for visual context (absolute paths or base64 data). Example: ["/path/to/diagram.png", "data:image/jpeg;base64,/9j/4AAQ..."]',
    },
    continuation_id: {
      type: 'string',
      description: 'Continuation ID for persistent conversation. Example: "chat_1703123456789_abc123"',
    },
    temperature: {
      type: 'number',
      description: 'Response randomness (0.0-1.0). Examples: 0.2 (focused), 0.5 (balanced), 0.8 (creative). Default: 0.5',
      minimum: 0.0,
      maximum: 1.0,
      default: 0.5
    },
    reasoning_effort: {
      type: 'string',
      enum: ['minimal', 'low', 'medium', 'high', 'max'],
      description: 'Reasoning depth for thinking models. Examples: "minimal" (quick), "medium" (balanced), "high" (complex analysis). Default: "medium"',
      default: 'medium'
    },
    use_websearch: {
      type: 'boolean',
      description: 'Enable web search for current information and best practices. Example: true for framework documentation, false for private code analysis. Default: false',
      default: false
    },
  },
  required: ['prompt'],
};

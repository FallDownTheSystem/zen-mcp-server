/**
 * Consensus Tool
 *
 * Multi-provider parallel execution with response aggregation.
 * Calls all available providers simultaneously and aggregates responses.
 */

import { createToolResponse, createToolError } from './index.js';
import { processUnifiedContext, createFileContext } from '../utils/contextProcessor.js';
import { generateContinuationId, addMessageToHistory } from '../continuationStore.js';

/**
 * Consensus tool implementation
 * @param {object} args - Tool arguments
 * @param {object} dependencies - Injected dependencies (config, providers, continuationStore)
 * @returns {object} MCP tool response
 */
export async function consensusTool(args, dependencies) {
  try {
    const { config, providers, continuationStore } = dependencies;
    
    // Validate required arguments
    if (!args.prompt || typeof args.prompt !== 'string') {
      return createToolError('Prompt is required and must be a string');
    }

    if (!args.models || !Array.isArray(args.models) || args.models.length === 0) {
      return createToolError('Models array is required and must contain at least one model');
    }

    // Extract and validate arguments
    const {
      prompt,
      models,
      relevant_files = [],
      continuation_id,
      enable_cross_feedback = true,
      cross_feedback_prompt,
      temperature = 0.2
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

    // Process context (files)
    let contextMessage = null;
    if (relevant_files.length > 0) {
      try {
        const contextRequest = {
          files: Array.isArray(relevant_files) ? relevant_files : []
        };
        
        const contextResult = await processUnifiedContext(contextRequest);
        
        // Create context message from files
        if (contextResult.files.length > 0) {
          contextMessage = createFileContext(contextResult.files, {
            includeMetadata: true,
            includeErrors: true
          });
        }
        
      } catch (error) {
        console.error('Error processing context:', error);
        // Continue without context if processing fails
      }
    }

    // Build message array for providers
    const messages = [...conversationHistory];
    
    // Add context message if available
    if (contextMessage) {
      messages.push(contextMessage);
    }
    
    // Add user prompt
    messages.push({
      role: 'user',
      content: prompt
    });

    // Resolve model specifications to provider calls
    const providerCalls = [];
    const failedModels = [];

    for (const modelSpec of models) {
      if (!modelSpec.model || typeof modelSpec.model !== 'string') {
        failedModels.push({
          model: modelSpec.model || 'unknown',
          error: 'Invalid model specification',
          status: 'failed'
        });
        continue;
      }

      const modelName = modelSpec.model;
      const providerName = mapModelToProvider(modelName);
      const provider = providers.getProvider(providerName);

      if (!provider) {
        failedModels.push({
          model: modelName,
          provider: providerName,
          error: `Provider not found: ${providerName}`,
          status: 'failed'
        });
        continue;
      }

      if (!provider.isAvailable(config)) {
        failedModels.push({
          model: modelName,
          provider: providerName,
          error: `Provider ${providerName} not available (check API key)`,
          status: 'failed'
        });
        continue;
      }

      providerCalls.push({
        model: modelName,
        provider: providerName,
        providerInstance: provider,
        options: {
          model: modelName,
          temperature,
          ...modelSpec // Allow model-specific overrides
        }
      });
    }

    if (providerCalls.length === 0) {
      return createToolError(
        `No valid providers available for the specified models. Failed models: ${failedModels.map(f => f.model).join(', ')}`
      );
    }

    // Phase 1: Initial parallel provider calls
    console.log(`Consensus: Calling ${providerCalls.length} providers in parallel...`);
    const initialResults = await Promise.allSettled(
      providerCalls.map(async (call) => {
        try {
          const response = await call.providerInstance.invoke(messages, call.options);
          return {
            model: call.model,
            provider: call.provider,
            status: 'success',
            response: response.content,
            metadata: response.metadata || {},
            rawResponse: response.rawResponse
          };
        } catch (error) {
          return {
            model: call.model,
            provider: call.provider,
            status: 'failed',
            error: error.message,
            metadata: {}
          };
        }
      })
    );

    // Process initial results
    const initialPhase = {
      successful: [],
      failed: []
    };

    initialResults.forEach((result, index) => {
      if (result.status === 'fulfilled') {
        if (result.value.status === 'success') {
          initialPhase.successful.push(result.value);
        } else {
          initialPhase.failed.push(result.value);
        }
      } else {
        initialPhase.failed.push({
          model: providerCalls[index].model,
          provider: providerCalls[index].provider,
          status: 'failed',
          error: result.reason.message || 'Unknown error',
          metadata: {}
        });
      }
    });

    // Add pre-failed models to failed list
    initialPhase.failed.push(...failedModels);

    let refinedPhase = null;

    // Phase 2: Cross-feedback (if enabled and we have multiple successful responses)
    if (enable_cross_feedback && initialPhase.successful.length > 1) {
      console.log(`Consensus: Running cross-feedback phase with ${initialPhase.successful.length} responses...`);
      
      // Create cross-feedback prompt
      const feedbackPrompt = cross_feedback_prompt || 
        `Based on the other AI responses below, please refine your answer to the original question. Consider different perspectives and provide your final response:

Original Question: ${prompt}

Other AI Responses:
${initialPhase.successful.map((r, i) => `${i + 1}. ${r.model}: ${r.response}`).join('\n\n')}

Please provide your refined response:`;

      // Build feedback messages
      const feedbackMessages = [...messages];
      feedbackMessages.push({
        role: 'user',
        content: feedbackPrompt
      });

      // Run refinement calls in parallel
      const refinementResults = await Promise.allSettled(
        initialPhase.successful.map(async (initialResult) => {
          try {
            const call = providerCalls.find(c => c.model === initialResult.model);
            const response = await call.providerInstance.invoke(feedbackMessages, call.options);
            
            return {
              ...initialResult,
              refined_response: response.content,
              refined_metadata: response.metadata || {},
              initial_response: initialResult.response,
              status: 'success'
            };
          } catch (error) {
            return {
              ...initialResult,
              refined_response: null,
              refined_error: error.message,
              initial_response: initialResult.response,
              status: 'partial' // Had initial success but refinement failed
            };
          }
        })
      );

      // Process refinement results
      refinedPhase = [];
      refinementResults.forEach((result) => {
        if (result.status === 'fulfilled') {
          refinedPhase.push(result.value);
        } else {
          // This shouldn't happen with our error handling, but just in case
          const originalResult = result.value || {};
          refinedPhase.push({
            ...originalResult,
            refined_response: null,
            refined_error: 'Refinement phase failed unexpectedly',
            status: 'partial'
          });
        }
      });
    }

    // Save conversation state
    try {
      const consensusMessage = {
        role: 'assistant',
        content: `Consensus completed with ${initialPhase.successful.length} successful responses` +
                (refinedPhase ? ` and ${refinedPhase.filter(r => r.status === 'success').length} refined responses` : '')
      };

      const conversationState = {
        messages: [...messages, consensusMessage],
        type: 'consensus',
        lastUpdated: Date.now(),
        consensusData: {
          modelsRequested: models.length,
          providersSuccessful: initialPhase.successful.length,
          providersFailed: initialPhase.failed.length,
          crossFeedbackEnabled: enable_cross_feedback
        }
      };
      
      await continuationStore.set(continuationId, conversationState);
    } catch (error) {
      console.error('Error saving consensus conversation:', error);
      // Continue even if save fails
    }

    // Build result object
    const result = {
      status: 'consensus_complete',
      models_consulted: models.length,
      successful_initial_responses: initialPhase.successful.length,
      failed_responses: initialPhase.failed.length,
      refined_responses: refinedPhase ? refinedPhase.filter(r => r.status === 'success').length : 0,
      phases: {
        initial: initialPhase.successful,
        refined: refinedPhase,
        failed: initialPhase.failed
      },
      continuation: {
        id: continuationId,
        messageCount: messages.length + 1
      },
      settings: {
        enable_cross_feedback,
        temperature,
        models_requested: models.map(m => m.model)
      }
    };

    return createToolResponse(JSON.stringify(result, null, 2));

  } catch (error) {
    console.error('Consensus tool error:', error);
    return createToolError('Consensus tool failed', error);
  }
}

/**
 * Map model name to provider name (same as chat tool)
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
consensusTool.description = 'Multi-provider consensus gathering with parallel execution';
consensusTool.inputSchema = {
  type: 'object',
  properties: {
    prompt: {
      type: 'string',
      description: 'The question or problem to gather consensus on',
    },
    models: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          model: { type: 'string' },
        },
        required: ['model'],
      },
      description: 'List of model configurations to consult',
    },
    relevant_files: {
      type: 'array',
      items: { type: 'string' },
      description: 'List of file paths to include as context',
    },
    continuation_id: {
      type: 'string',
      description: 'Continuation ID for persistent conversation',
    },
    enable_cross_feedback: {
      type: 'boolean',
      description: 'Enable refinement phase where models see others responses',
      default: true,
    },
    cross_feedback_prompt: {
      type: 'string',
      description: 'Custom prompt for refinement phase',
    },
    temperature: {
      type: 'number',
      description: 'Response randomness (0.0-1.0)',
      default: 0.2,
    },
  },
  required: ['prompt', 'models'],
};

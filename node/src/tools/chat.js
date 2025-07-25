/**
 * Chat Tool
 *
 * Single-provider conversational AI with context and continuation support.
 * Will be implemented in subsequent tasks.
 */

import { createToolError } from './index.js';

/**
 * Chat tool implementation (placeholder)
 * @param {object} args - Tool arguments
 * @param {object} dependencies - Injected dependencies (config, providers, continuationStore)
 * @returns {object} MCP tool response
 */
export async function chatTool(_args, _dependencies) {
  try {
    // Placeholder implementation
    return createToolError('Chat tool not yet implemented');
  } catch (error) {
    return createToolError('Chat tool error', error);
  }
}

// Tool metadata
chatTool.description = 'Conversational AI tool with context and continuation support';
chatTool.inputSchema = {
  type: 'object',
  properties: {
    prompt: {
      type: 'string',
      description: 'The user prompt for the AI',
    },
    model: {
      type: 'string',
      description: 'AI model to use (optional, defaults to auto-selection)',
    },
    files: {
      type: 'array',
      items: { type: 'string' },
      description: 'File paths to include as context',
    },
    continuation_id: {
      type: 'string',
      description: 'Continuation ID for persistent conversation',
    },
    temperature: {
      type: 'number',
      description: 'Response randomness (0.0-1.0)',
    },
    use_websearch: {
      type: 'boolean',
      description: 'Enable web search for current information',
    },
  },
  required: ['prompt'],
};

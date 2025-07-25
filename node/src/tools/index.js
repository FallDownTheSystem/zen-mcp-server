/**
 * Tool Registry
 *
 * Central registry for all MCP tools following functional architecture.
 * Each tool receives dependencies via injection and returns MCP-compatible responses.
 */

// Import individual tools (will be implemented in subsequent tasks)
// import { chatTool } from './chat.js';
// import { consensusTool } from './consensus.js';

/**
 * Tool registry map
 * Each tool must implement: async function(args, dependencies) => mcpResponse
 * Tools also have metadata: description, inputSchema
 */
const tools = {
  // Will be populated by individual tool modules
  // chat: chatTool,
  // consensus: consensusTool,
};

/**
 * Get all available tools
 * @returns {object} Map of tool name to tool implementation
 */
export function getTools() {
  return tools;
}

/**
 * Get a specific tool by name
 * @param {string} name - Tool name
 * @returns {object|null} Tool implementation or null if not found
 */
export function getTool(name) {
  return tools[name] || null;
}

/**
 * Register a new tool
 * @param {string} name - Tool name
 * @param {function} toolHandler - Tool implementation function
 * @param {object} metadata - Tool metadata (description, inputSchema)
 */
export function registerTool(name, toolHandler, metadata = {}) {
  // Validate tool interface
  if (typeof toolHandler !== 'function') {
    throw new Error(`Tool ${name} must be a function`);
  }

  // Add metadata to tool function
  toolHandler.description = metadata.description || `${name} tool`;
  toolHandler.inputSchema = metadata.inputSchema || {
    type: 'object',
    properties: {},
  };

  tools[name] = toolHandler;
}

/**
 * Get list of available tool names
 * @returns {string[]} Array of tool names
 */
export function getAvailableTools() {
  return Object.keys(tools);
}

/**
 * Create MCP-compatible tool response
 * @param {string} content - Response content
 * @param {boolean} isError - Whether this is an error response
 * @returns {object} MCP tool response
 */
export function createToolResponse(content, isError = false) {
  return {
    content: [
      {
        type: 'text',
        text: content,
      },
    ],
    isError,
  };
}

/**
 * Create MCP-compatible tool error response
 * @param {string} message - Error message
 * @param {Error} error - Original error object
 * @returns {object} MCP error response
 */
export function createToolError(message, error = null) {
  const errorText = error ? `${message}: ${error.message}` : message;
  return createToolResponse(errorText, true);
}

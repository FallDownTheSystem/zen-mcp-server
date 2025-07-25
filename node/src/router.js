/**
 * Central Request Router
 *
 * Dispatcher that connects MCP server requests to tools and providers.
 * Follows functional architecture with dependency injection.
 */

import { CallToolRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { getContinuationStore } from './continuationStore.js';
import { getTools } from './tools/index.js';
import { getProviders } from './providers/index.js';

/**
 * Creates and configures the router for handling MCP requests
 * @param {object} server - MCP Server instance
 * @param {object} config - Configuration object
 */
export async function createRouter(server, config) {
  // Initialize dependencies
  const continuationStore = getContinuationStore();
  const tools = getTools();
  const providers = getProviders();

  // Create dependencies object for injection into tools
  const dependencies = {
    config,
    continuationStore,
    providers,
  };

  // Register tools with the MCP server
  for (const [toolName, toolHandler] of Object.entries(tools)) {
    server.setRequestHandler(CallToolRequestSchema, async (request) => {
      if (request.params.name === toolName) {
        try {
          return await toolHandler(request.params.arguments, dependencies);
        } catch (error) {
          console.error(`Error in tool ${toolName}:`, error);
          return {
            content: [
              {
                type: 'text',
                text: `Error executing ${toolName}: ${error.message}`,
              },
            ],
            isError: true,
          };
        }
      }
    });
  }

  // Register list_tools handler
  server.setRequestHandler({ method: 'tools/list' }, async () => {
    return {
      tools: Object.keys(tools).map(name => ({
        name,
        description: tools[name].description || `${name} tool`,
        inputSchema: tools[name].inputSchema || {
          type: 'object',
          properties: {},
        },
      })),
    };
  });

  console.error(`Router configured with ${Object.keys(tools).length} tools`);
}

/**
 * Helper function to validate tool arguments against schema
 * @param {object} args - Tool arguments
 * @param {object} schema - Input schema
 * @returns {boolean} True if valid
 */
export function validateToolArguments(args, schema) {
  // Basic validation - can be enhanced with JSON schema validator
  if (!schema || !schema.properties) {
    return true;
  }

  for (const [key, prop] of Object.entries(schema.properties)) {
    if (prop.required && !(key in args)) {
      return false;
    }
  }

  return true;
}

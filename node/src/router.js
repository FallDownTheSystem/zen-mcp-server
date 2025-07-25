/**
 * Central Request Router
 *
 * Single orchestration point that dispatches MCP requests to tools with dependency injection.
 * Handles tool lookup, error management, and consistent response formatting.
 * Follows functional architecture with comprehensive error handling.
 */

import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { getContinuationStore } from './continuationStore.js';
import { getTools } from './tools/index.js';
import { getProviders } from './providers/index.js';
import { processUnifiedContext } from './utils/contextProcessor.js';

/**
 * Custom error class for router operations
 */
export class RouterError extends Error {
  constructor(message, code = 'ROUTER_ERROR', details = {}) {
    super(message);
    this.name = 'RouterError';
    this.code = code;
    this.details = details;
  }
}

/**
 * Standard error response format for consistent error handling
 * @param {Error} error - The error that occurred
 * @param {string} toolName - Name of the tool that failed
 * @param {object} context - Additional context information
 * @returns {object} Standardized error response
 */
export function createErrorResponse(error, toolName = 'unknown', context = {}) {
  const errorResponse = {
    content: [
      {
        type: 'text',
        text: `Error in ${toolName}: ${error.message}`,
      },
    ],
    isError: true,
    error: {
      type: error.name || 'Error',
      code: error.code || 'UNKNOWN_ERROR',
      message: error.message,
      toolName,
      timestamp: new Date().toISOString(),
      ...context,
    },
  };

  // Add stack trace in development mode
  if (process.env.NODE_ENV === 'development' && error.stack) {
    errorResponse.error.stack = error.stack;
  }

  return errorResponse;
}

/**
 * Validate tool exists and is callable
 * @param {string} toolName - Name of the tool to validate
 * @param {object} tools - Available tools registry
 * @returns {object} Validation result
 */
function validateTool(toolName, tools) {
  if (!toolName || typeof toolName !== 'string') {
    throw new RouterError(
      'Tool name must be a non-empty string',
      'INVALID_TOOL_NAME'
    );
  }

  if (!tools[toolName]) {
    const availableTools = Object.keys(tools);
    throw new RouterError(
      `Unknown tool: ${toolName}. Available tools: ${availableTools.join(', ')}`,
      'UNKNOWN_TOOL',
      { requestedTool: toolName, availableTools }
    );
  }

  if (typeof tools[toolName] !== 'function') {
    throw new RouterError(
      `Tool ${toolName} is not callable`,
      'INVALID_TOOL_HANDLER',
      { toolName, toolType: typeof tools[toolName] }
    );
  }

  return {
    isValid: true,
    tool: tools[toolName]
  };
}

/**
 * Enhanced dependency injection with error handling
 * @param {object} config - Configuration object
 * @returns {object} Dependencies object for tool injection
 */
async function createDependencies(config) {
  try {
    const continuationStore = getContinuationStore();
    const tools = getTools();
    const providers = getProviders();

    // Validate that we have the necessary dependencies
    if (!continuationStore) {
      throw new RouterError(
        'Failed to initialize continuation store',
        'DEPENDENCY_ERROR'
      );
    }

    if (!tools || Object.keys(tools).length === 0) {
      throw new RouterError(
        'No tools available - tools registry is empty',
        'NO_TOOLS_AVAILABLE'
      );
    }

    if (!providers || Object.keys(providers).length === 0) {
      throw new RouterError(
        'No providers available - providers registry is empty',
        'NO_PROVIDERS_AVAILABLE'
      );
    }

    return {
      config,
      continuationStore,
      providers,
      contextProcessor: { processUnifiedContext },
      router: {
        createErrorResponse,
        validateToolArguments,
      },
    };

  } catch (error) {
    console.error('Failed to create dependencies:', error);
    throw error;
  }
}

/**
 * Creates and configures the central router for handling MCP requests
 * @param {object} server - MCP Server instance
 * @param {object} config - Configuration object with provider settings
 * @returns {Promise<void>}
 */
export async function createRouter(server, config) {
  try {
    // Initialize dependencies with validation
    const dependencies = await createDependencies(config);
    const tools = getTools();

    console.log(`Initializing router with ${Object.keys(tools).length} tools...`);

    // Register unified tool call handler with enhanced error handling
    server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const startTime = Date.now();
      const toolName = request.params?.name;
      const toolArgs = request.params?.arguments || {};

      try {
        // Validate tool existence and callability
        const { tool } = validateTool(toolName, tools);

        // Validate tool arguments if schema is provided
        if (tool.inputSchema) {
          const isValidArgs = validateToolArguments(toolArgs, tool.inputSchema);
          if (!isValidArgs) {
            throw new RouterError(
              `Invalid arguments for tool ${toolName}`,
              'INVALID_ARGUMENTS',
              {
                providedArgs: Object.keys(toolArgs),
                expectedSchema: tool.inputSchema
              }
            );
          }
        }

        console.log(`Executing tool: ${toolName}`);

        // Execute the tool with dependency injection
        const result = await tool(toolArgs, dependencies);

        const executionTime = Date.now() - startTime;
        console.log(`Tool ${toolName} completed in ${executionTime}ms`);

        // Ensure result has proper format
        if (!result || !result.content) {
          throw new RouterError(
            `Tool ${toolName} returned invalid result format`,
            'INVALID_TOOL_RESULT',
            { result }
          );
        }

        return result;

      } catch (error) {
        const executionTime = Date.now() - startTime;
        console.error(`Tool ${toolName} failed after ${executionTime}ms:`, error.message);

        return createErrorResponse(error, toolName, {
          executionTime,
          arguments: toolArgs,
          requestId: request.id || 'unknown'
        });
      }
    });

    // Register enhanced list_tools handler
    server.setRequestHandler(ListToolsRequestSchema, async () => {
      try {
        const toolList = Object.entries(tools).map(([name, handler]) => {
          const toolInfo = {
            name,
            description: handler.description || `${name} tool - no description provided`,
            inputSchema: handler.inputSchema || {
              type: 'object',
              properties: {},
              description: 'No input schema defined'
            },
          };

          // Add additional metadata if available
          if (handler.version) {
            toolInfo.version = handler.version;
          }
          if (handler.category) {
            toolInfo.category = handler.category;
          }

          return toolInfo;
        });

        return {
          tools: toolList,
          metadata: {
            totalTools: toolList.length,
            timestamp: new Date().toISOString(),
            routerVersion: '1.0.0'
          }
        };

      } catch (error) {
        console.error('Error listing tools:', error);
        throw new RouterError(
          'Failed to list available tools',
          'TOOLS_LIST_ERROR',
          { error: error.message }
        );
      }
    });

    // Note: Custom health endpoint removed - MCP uses standard protocol methods only

    console.log('✓ Router configured successfully:');
    console.log(`  - Tools: ${Object.keys(tools).length}`);
    console.log(`  - Providers: ${Object.keys(dependencies.providers).length}`);
    console.log(`  - Continuation store: ${dependencies.continuationStore.constructor.name}`);
    console.log(`  - Environment: ${config.environment.nodeEnv}`);

  } catch (error) {
    console.error('Failed to create router:', error);
    throw new RouterError(
      'Router initialization failed',
      'ROUTER_INIT_ERROR',
      { originalError: error.message }
    );
  }
}

/**
 * Enhanced tool argument validation against schema
 * @param {object} args - Tool arguments to validate
 * @param {object} schema - JSON schema for validation
 * @returns {boolean} True if arguments are valid
 * @throws {RouterError} If validation fails with details
 */
export function validateToolArguments(args, schema) {
  try {
    // If no schema provided, assume valid
    if (!schema) {
      return true;
    }

    // Basic type checking
    if (schema.type === 'object' && (typeof args !== 'object' || args === null)) {
      throw new RouterError(
        'Arguments must be an object',
        'INVALID_ARGUMENT_TYPE',
        { expected: 'object', received: typeof args }
      );
    }

    // Check required properties
    if (schema.required && Array.isArray(schema.required)) {
      const missing = schema.required.filter(key => !(key in args));
      if (missing.length > 0) {
        throw new RouterError(
          `Missing required arguments: ${missing.join(', ')}`,
          'MISSING_REQUIRED_ARGS',
          { missing, provided: Object.keys(args) }
        );
      }
    }

    // Validate individual properties
    if (schema.properties) {
      for (const [key, propSchema] of Object.entries(schema.properties)) {
        if (key in args) {
          const value = args[key];

          // Basic type validation
          if (propSchema.type && typeof value !== propSchema.type) {
            throw new RouterError(
              `Argument '${key}' must be of type ${propSchema.type}`,
              'INVALID_ARGUMENT_TYPE',
              {
                argument: key,
                expected: propSchema.type,
                received: typeof value
              }
            );
          }

          // String length validation
          if (propSchema.type === 'string') {
            if (propSchema.minLength && value.length < propSchema.minLength) {
              throw new RouterError(
                `Argument '${key}' must be at least ${propSchema.minLength} characters`,
                'ARGUMENT_TOO_SHORT',
                { argument: key, minLength: propSchema.minLength, actual: value.length }
              );
            }
            if (propSchema.maxLength && value.length > propSchema.maxLength) {
              throw new RouterError(
                `Argument '${key}' must be at most ${propSchema.maxLength} characters`,
                'ARGUMENT_TOO_LONG',
                { argument: key, maxLength: propSchema.maxLength, actual: value.length }
              );
            }
          }
        }
      }
    }

    return true;

  } catch (error) {
    if (error instanceof RouterError) {
      throw error;
    }
    throw new RouterError(
      `Argument validation failed: ${error.message}`,
      'VALIDATION_ERROR',
      { originalError: error.message }
    );
  }
}

/**
 * Get router statistics and health information
 * @param {object} dependencies - Router dependencies
 * @returns {Promise<object>} Router statistics
 */
export async function getRouterStats(dependencies) {
  try {
    const tools = getTools();
    const storeStats = await dependencies.continuationStore.getStats();

    return {
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
      tools: {
        count: Object.keys(tools).length,
        available: Object.keys(tools)
      },
      providers: {
        count: Object.keys(dependencies.providers).length,
        available: Object.keys(dependencies.providers)
      },
      continuationStore: storeStats,
      memory: process.memoryUsage(),
      environment: dependencies.config.environment.nodeEnv
    };

  } catch (error) {
    throw new RouterError(
      'Failed to get router statistics',
      'STATS_ERROR',
      { error: error.message }
    );
  }
}

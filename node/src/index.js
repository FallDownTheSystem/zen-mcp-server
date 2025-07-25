#!/usr/bin/env node

/**
 * Converse MCP Server - Main Entry Point
 *
 * Simplified, functional Node.js implementation of MCP server
 * with chat and consensus tools using modern Node.js practices.
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { loadConfig, validateRuntimeConfig, getMcpClientConfig, ConfigurationError } from './config.js';
import { createRouter } from './router.js';

async function main() {
  try {
    // Load and validate configuration
    const config = await loadConfig();
    await validateRuntimeConfig(config);

    // Get MCP client configuration
    const mcpConfig = getMcpClientConfig(config);

    // Create MCP server with configuration
    const server = new Server(
      {
        name: mcpConfig.name,
        version: mcpConfig.version,
      },
      mcpConfig
    );

    // Set up router with server and config
    await createRouter(server, config);

    // Start server with stdio transport
    const transport = new StdioServerTransport();
    await server.connect(transport);

    console.error('Converse MCP Server started successfully');
  } catch (error) {
    if (error instanceof ConfigurationError) {
      console.error('Configuration Error:');
      console.error(error.message);
      if (error.details?.errors) {
        console.error('\nDetailed errors:');
        error.details.errors.forEach(err => console.error(`  - ${err}`));
      }
      process.exit(1);
    } else {
      console.error('Failed to start Converse MCP Server:', error);
      process.exit(1);
    }
  }
}

// Handle graceful shutdown
process.on('SIGINT', () => {
  console.error('Shutting down Converse MCP Server...');
  process.exit(0);
});

process.on('SIGTERM', () => {
  console.error('Shutting down Converse MCP Server...');
  process.exit(0);
});

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});

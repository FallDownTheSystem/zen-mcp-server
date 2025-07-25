#!/usr/bin/env node

/**
 * Converse MCP Server - Main Entry Point
 *
 * Simplified, functional Node.js implementation of MCP server
 * with chat and consensus tools using modern Node.js practices.
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { loadConfig, validateRuntimeConfig, getMcpClientConfig } from './config.js';
import { createRouter } from './router.js';
import { createLogger, startTimer } from './utils/logger.js';
import { ConfigurationError } from './utils/errorHandler.js';

const logger = createLogger('server');

async function main() {
  const serverTimer = startTimer('server-startup', 'server');
  
  try {
    logger.info('Starting Converse MCP Server');

    // Load and validate configuration
    const config = await loadConfig();
    await validateRuntimeConfig(config);

    // Get MCP client configuration
    const mcpConfig = getMcpClientConfig(config);

    logger.debug('Creating MCP server instance', { 
      data: { name: mcpConfig.name, version: mcpConfig.version } 
    });

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

    const startupTime = serverTimer('completed');
    logger.info('Converse MCP Server started successfully', { 
      data: { startupTime: `${startupTime}ms` } 
    });
  } catch (error) {
    serverTimer('failed');
    
    if (error instanceof ConfigurationError) {
      logger.error('Configuration error during startup', { error });
      console.error('Configuration Error:');
      console.error(error.message);
      if (error.details?.errors) {
        console.error('\nDetailed errors:');
        error.details.errors.forEach(err => console.error(`  - ${err}`));
      }
      process.exit(1);
    } else {
      logger.error('Failed to start Converse MCP Server', { error });
      console.error('Failed to start Converse MCP Server:', error.message);
      process.exit(1);
    }
  }
}

// Handle graceful shutdown
process.on('SIGINT', () => {
  logger.info('Received SIGINT, shutting down gracefully');
  console.error('Shutting down Converse MCP Server...');
  process.exit(0);
});

process.on('SIGTERM', () => {
  logger.info('Received SIGTERM, shutting down gracefully');
  console.error('Shutting down Converse MCP Server...');
  process.exit(0);
});

process.on('uncaughtException', (error) => {
  logger.error('Uncaught exception', { error });
  console.error('Fatal error:', error);
  process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
  logger.error('Unhandled promise rejection', { 
    error: reason, 
    data: { promise: promise.toString() } 
  });
  console.error('Unhandled promise rejection:', reason);
  process.exit(1);
});

main().catch((error) => {
  logger.error('Fatal error in main', { error });
  console.error('Fatal error:', error);
  process.exit(1);
});

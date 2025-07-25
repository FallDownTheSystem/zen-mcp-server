/**
 * Configuration Management System
 *
 * Comprehensive environment-based configuration system for the Converse MCP Server.
 * Loads, validates, and manages all configuration from environment variables only.
 * Follows functional architecture with explicit dependencies.
 */

import dotenv from 'dotenv';
import { createLogger, configureLogger } from './utils/logger.js';
import { ConfigurationError } from './utils/errorHandler.js';

// Load environment variables from .env file (if it exists)
dotenv.config();

// Configure logger early
configureLogger({
  level: process.env.LOG_LEVEL || 'info',
  isDevelopment: process.env.NODE_ENV === 'development'
});

const logger = createLogger('config');

/**
 * Configuration schema defining all supported environment variables
 */
const CONFIG_SCHEMA = {
  // Server configuration
  server: {
    PORT: { type: 'number', default: 3000, description: 'Server port' },
    NODE_ENV: { type: 'string', default: 'development', description: 'Environment mode' },
    LOG_LEVEL: { type: 'string', default: 'info', description: 'Logging level' },
  },

  // API Keys (at least one required)
  apiKeys: {
    OPENAI_API_KEY: { type: 'string', required: false, secret: true, description: 'OpenAI API key' },
    XAI_API_KEY: { type: 'string', required: false, secret: true, description: 'XAI API key' },
    GOOGLE_API_KEY: { type: 'string', required: false, secret: true, description: 'Google API key' },
  },

  // Provider-specific configuration
  providers: {
    GOOGLE_LOCATION: { type: 'string', default: 'us-central1', description: 'Google Cloud location' },
    XAI_BASE_URL: { type: 'string', default: 'https://api.x.ai/v1', description: 'XAI API base URL' },
  },

  // MCP configuration
  mcp: {
    MCP_SERVER_NAME: { type: 'string', default: 'converse-mcp-server', description: 'MCP server name' },
    MCP_SERVER_VERSION: { type: 'string', default: '1.0.0', description: 'MCP server version' },
    MAX_MCP_OUTPUT_TOKENS: { type: 'number', default: 25000, description: 'Maximum tokens in MCP tool responses' },
  },
};

// ConfigurationError now imported from errorHandler

/**
 * Validates and parses environment variable value according to schema
 * @param {string} key - Environment variable key
 * @param {string|undefined} value - Environment variable value
 * @param {object} schema - Schema definition for the variable
 * @returns {any} Parsed and validated value
 */
function validateEnvVar(key, value, schema) {
  // Handle missing values
  if (value === undefined || value === '') {
    if (schema.required) {
      throw new ConfigurationError(`Required environment variable ${key} is missing`);
    }
    return schema.default;
  }

  // Type validation and conversion
  switch (schema.type) {
  case 'string':
    return value;
  case 'number':
    const num = parseInt(value, 10);
    if (isNaN(num)) {
      throw new ConfigurationError(
        `Environment variable ${key} must be a valid number, got: ${value}`
      );
    }
    return num;
  case 'boolean':
    const lower = value.toLowerCase();
    if (!['true', 'false', '1', '0', 'yes', 'no'].includes(lower)) {
      throw new ConfigurationError(
        `Environment variable ${key} must be a boolean value, got: ${value}`
      );
    }
    return ['true', '1', 'yes'].includes(lower);
  default:
    return value;
  }
}

/**
 * Validates API key format and basic structure
 * @param {string} provider - Provider name
 * @param {string} apiKey - API key to validate
 * @returns {boolean} True if API key appears valid
 */
function validateApiKeyFormat(provider, apiKey) {
  if (!apiKey || typeof apiKey !== 'string') {
    return false;
  }

  // Basic format validation for each provider
  switch (provider) {
  case 'openai':
    return apiKey.startsWith('sk-') && apiKey.length > 20;
  case 'xai':
    return apiKey.startsWith('xai-') && apiKey.length > 20;
  case 'google':
    return apiKey.length > 20; // Google keys vary in format
  default:
    return apiKey.length >= 10; // Basic minimum length check
  }
}

/**
 * Loads and validates complete configuration from environment variables
 * @returns {Promise<object>} Validated configuration object
 * @throws {ConfigurationError} If configuration is invalid or incomplete
 */
export async function loadConfig() {
  const configLogger = logger.operation('loadConfig');
  configLogger.debug('Starting configuration loading');
  
  const config = {
    server: {},
    apiKeys: {},
    providers: {},
    mcp: {},
    environment: {
      isDevelopment: false,
      isProduction: false,
      nodeEnv: '',
    },
  };

  const errors = [];

  try {
    // Load server configuration
    for (const [key, schema] of Object.entries(CONFIG_SCHEMA.server)) {
      try {
        config.server[key.toLowerCase()] = validateEnvVar(key, process.env[key], schema);
      } catch (error) {
        errors.push(error.message);
      }
    }

    // Load API keys
    for (const [key, schema] of Object.entries(CONFIG_SCHEMA.apiKeys)) {
      try {
        const value = validateEnvVar(key, process.env[key], schema);
        if (value) {
          const providerName = key.replace('_API_KEY', '').toLowerCase();
          config.apiKeys[providerName] = value;
        }
      } catch (error) {
        errors.push(error.message);
      }
    }

    // Load provider configuration
    for (const [key, schema] of Object.entries(CONFIG_SCHEMA.providers)) {
      try {
        const value = validateEnvVar(key, process.env[key], schema);
        const configKey = key.toLowerCase().replace(/_/g, '');
        config.providers[configKey] = value;
      } catch (error) {
        errors.push(error.message);
      }
    }

    // Load MCP configuration
    for (const [key, schema] of Object.entries(CONFIG_SCHEMA.mcp)) {
      try {
        const value = validateEnvVar(key, process.env[key], schema);
        const configKey = key.replace('MCP_SERVER_', '').toLowerCase();
        config.mcp[configKey] = value;
      } catch (error) {
        errors.push(error.message);
      }
    }

    // Set environment flags
    const nodeEnv = config.server.node_env || 'development';
    config.environment = {
      isDevelopment: nodeEnv === 'development',
      isProduction: nodeEnv === 'production',
      nodeEnv,
    };

    // Validate that at least one API key is present
    const availableKeys = Object.keys(config.apiKeys);
    if (availableKeys.length === 0) {
      errors.push(
        'At least one API key must be configured: OPENAI_API_KEY, XAI_API_KEY, or GOOGLE_API_KEY'
      );
    }

    // Validate API key formats
    for (const [provider, apiKey] of Object.entries(config.apiKeys)) {
      if (!validateApiKeyFormat(provider, apiKey)) {
        errors.push(`Invalid API key format for ${provider.toUpperCase()}_API_KEY`);
      }
    }

    // Throw accumulated errors
    if (errors.length > 0) {
      throw new ConfigurationError(
        `Configuration validation failed with ${errors.length} error(s):\n${errors.map(e => `  - ${e}`).join('\n')}`,
        { errors }
      );
    }

    // Log configuration summary (without secrets)
    logConfigurationSummary(config);
    configLogger.info('Configuration loaded successfully');

    return config;

  } catch (error) {
    configLogger.error('Configuration loading failed', { error });
    if (error instanceof ConfigurationError) {
      throw error;
    }
    throw new ConfigurationError(`Failed to load configuration: ${error.message}`, { originalError: error });
  }
}

/**
 * Gets configuration for a specific provider
 * @param {object} config - Main configuration object
 * @param {string} providerName - Name of the provider
 * @returns {object} Provider-specific configuration
 */
export function getProviderConfig(config, providerName) {
  const apiKey = config.apiKeys[providerName];
  const providerConfig = {};

  // Add provider-specific configuration
  switch (providerName) {
  case 'google':
    providerConfig.location = config.providers.googlelocation;
    break;
  case 'xai':
    providerConfig.baseUrl = config.providers.xaibaseurl;
    break;
  }

  return {
    apiKey,
    ...providerConfig,
  };
}

/**
 * Checks if a provider is available (has valid API key)
 * @param {object} config - Main configuration object
 * @param {string} providerName - Name of the provider
 * @returns {boolean} True if provider is available
 */
export function isProviderAvailable(config, providerName) {
  const apiKey = config.apiKeys[providerName];
  return apiKey && validateApiKeyFormat(providerName, apiKey);
}

/**
 * Gets list of available providers
 * @param {object} config - Main configuration object
 * @returns {string[]} Array of available provider names
 */
export function getAvailableProviders(config) {
  return Object.keys(config.apiKeys).filter(provider =>
    isProviderAvailable(config, provider)
  );
}

/**
 * Validates runtime configuration consistency
 * @param {object} config - Configuration object to validate
 * @returns {Promise<boolean>} True if configuration is valid
 * @throws {ConfigurationError} If configuration is invalid
 */
export async function validateRuntimeConfig(config) {
  try {
    // Validate server configuration
    if (config.server.port < 1 || config.server.port > 65535) {
      throw new ConfigurationError(`Invalid port number: ${config.server.port}`);
    }

    // Validate environment
    const validEnvs = ['development', 'production', 'test'];
    if (!validEnvs.includes(config.environment.nodeEnv)) {
      throw new ConfigurationError(
        `Invalid NODE_ENV: ${config.environment.nodeEnv}. Must be one of: ${validEnvs.join(', ')}`
      );
    }

    // Validate log level
    const validLogLevels = ['error', 'warn', 'info', 'debug'];
    if (!validLogLevels.includes(config.server.log_level)) {
      throw new ConfigurationError(
        `Invalid LOG_LEVEL: ${config.server.log_level}. Must be one of: ${validLogLevels.join(', ')}`
      );
    }

    // Production-specific validations
    if (config.environment.isProduction) {
      // Require at least 2 providers in production for redundancy
      const availableProviders = getAvailableProviders(config);
      if (availableProviders.length < 1) {
        console.warn('Warning: Only one provider configured in production environment');
      }
    }

    return true;

  } catch (error) {
    if (error instanceof ConfigurationError) {
      throw error;
    }
    throw new ConfigurationError(`Runtime validation failed: ${error.message}`);
  }
}

/**
 * Logs configuration summary (masking sensitive information)
 * @param {object} config - Configuration object
 */
function logConfigurationSummary(config) {
  const availableProviders = getAvailableProviders(config);

  console.error('Configuration loaded successfully:');
  console.error(`  Environment: ${config.environment.nodeEnv}`);
  console.error(`  Port: ${config.server.port}`);
  console.error(`  Log Level: ${config.server.log_level}`);
  console.error(`  Available Providers: ${availableProviders.join(', ') || 'none'}`);
  console.error(`  MCP Server: ${config.mcp.name} v${config.mcp.version}`);

  // Mask API keys in logs
  const maskedKeys = Object.keys(config.apiKeys).map(key => {
    const value = config.apiKeys[key];
    return `${key.toUpperCase()}: ${value ? `${value.substring(0, 8)}...` : 'not configured'}`;
  });
  console.error(`  API Keys: ${maskedKeys.join(', ')}`);
}

/**
 * Creates MCP client configuration object
 * @param {object} config - Main configuration object
 * @returns {object} MCP client configuration
 */
export function getMcpClientConfig(config) {
  return {
    name: config.mcp.name,
    version: config.mcp.version,
    capabilities: {
      tools: {},
    },
    environment: config.environment.nodeEnv,
    providers: getAvailableProviders(config),
  };
}

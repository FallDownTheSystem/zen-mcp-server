/**
 * Configuration Module
 *
 * Loads and validates environment variables for the Converse MCP Server.
 * Follows functional architecture with explicit dependencies.
 */

import dotenv from 'dotenv';

// Load environment variables from .env file
dotenv.config();

/**
 * Validates required API keys and configuration
 * @returns {object} Validated configuration object
 * @throws {Error} If required configuration is missing
 */
export async function loadConfig() {
  const config = {
    // Server configuration
    port: parseInt(process.env.PORT || '3000', 10),
    nodeEnv: process.env.NODE_ENV || 'development',
    logLevel: process.env.LOG_LEVEL || 'info',

    // API Keys (some are optional depending on which providers are used)
    apiKeys: {
      openai: process.env.OPENAI_API_KEY,
      xai: process.env.XAI_API_KEY,
      google: process.env.GOOGLE_API_KEY,
    },

    // Provider configuration
    providers: {
      google: {
        location: process.env.GOOGLE_LOCATION || 'us-central1',
      },
      xai: {
        baseUrl: process.env.XAI_BASE_URL || 'https://api.x.ai/v1',
      },
    },
  };

  // Validate at least one API key is present
  const hasApiKey = Object.values(config.apiKeys).some(key => key && key.length > 0);
  if (!hasApiKey) {
    throw new Error(
      'At least one API key must be configured: OPENAI_API_KEY, XAI_API_KEY, or GOOGLE_API_KEY'
    );
  }

  return config;
}

/**
 * Gets configuration for a specific provider
 * @param {object} config - Main configuration object
 * @param {string} providerName - Name of the provider
 * @returns {object} Provider-specific configuration
 */
export function getProviderConfig(config, providerName) {
  const apiKey = config.apiKeys[providerName];
  const providerConfig = config.providers[providerName] || {};

  return {
    apiKey,
    ...providerConfig,
  };
}

/**
 * Checks if a provider is available (has API key)
 * @param {object} config - Main configuration object
 * @param {string} providerName - Name of the provider
 * @returns {boolean} True if provider is available
 */
export function isProviderAvailable(config, providerName) {
  const apiKey = config.apiKeys[providerName];
  return apiKey && apiKey.length > 0;
}

/**
 * OpenAI Provider
 *
 * Provider implementation for OpenAI GPT models using the official SDK.
 * Will be implemented in subsequent tasks.
 */

// This is a placeholder - implementation will be added in a future task
export const openaiProvider = {
  // Placeholder implementation
  async invoke(_messages, _options) {
    throw new Error('OpenAI provider not yet implemented');
  },

  validateConfig(config) {
    return config.apiKeys.openai && config.apiKeys.openai.length > 0;
  },

  isAvailable(config) {
    return this.validateConfig(config);
  },
};

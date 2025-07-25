/**
 * Google (Gemini) Provider
 *
 * Provider implementation for Google Gemini models using the official @google/genai SDK.
 * Will be implemented in subsequent tasks.
 */

// This is a placeholder - implementation will be added in a future task
export const googleProvider = {
  // Placeholder implementation
  async invoke(_messages, _options) {
    throw new Error('Google provider not yet implemented');
  },

  validateConfig(config) {
    return config.apiKeys.google && config.apiKeys.google.length > 0;
  },

  isAvailable(config) {
    return this.validateConfig(config);
  },
};

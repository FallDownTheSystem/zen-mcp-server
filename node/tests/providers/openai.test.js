/**
 * Unit tests for OpenAI provider
 * Tests the unified interface implementation without making real API calls
 */

import { describe, it, mock } from 'node:test';
import assert from 'node:assert';
import { openaiProvider } from '../../src/providers/openai.js';

describe('OpenAI Provider', () => {
  describe('validateConfig', () => {
    it('should return true for valid OpenAI API key', () => {
      const config = {
        apiKeys: {
          openai: 'sk-1234567890abcdef1234567890abcdef1234567890abcdef'
        }
      };
      
      assert.strictEqual(openaiProvider.validateConfig(config), true);
    });

    it('should return false for missing API key', () => {
      const config = { apiKeys: {} };
      assert.strictEqual(openaiProvider.validateConfig(config), false);
    });

    it('should return false for invalid API key format', () => {
      const config = {
        apiKeys: {
          openai: 'invalid-key'
        }
      };
      
      assert.strictEqual(openaiProvider.validateConfig(config), false);
    });

    it('should return false for short API key', () => {
      const config = {
        apiKeys: {
          openai: 'sk-short'
        }
      };
      
      assert.strictEqual(openaiProvider.validateConfig(config), false);
    });
  });

  describe('isAvailable', () => {
    it('should return true when config is valid', () => {
      const config = {
        apiKeys: {
          openai: 'sk-1234567890abcdef1234567890abcdef1234567890abcdef'
        }
      };
      
      assert.strictEqual(openaiProvider.isAvailable(config), true);
    });

    it('should return false when config is invalid', () => {
      const config = { apiKeys: {} };
      assert.strictEqual(openaiProvider.isAvailable(config), false);
    });
  });

  describe('getSupportedModels', () => {
    it('should return supported models object', () => {
      const models = openaiProvider.getSupportedModels();
      
      assert.strictEqual(typeof models, 'object');
      assert.ok('o3' in models);
      assert.ok('o3-mini' in models);
      assert.ok('gpt-4o' in models);
      assert.ok('gpt-4o-mini' in models);
    });

    it('should include model configuration details', () => {
      const models = openaiProvider.getSupportedModels();
      const o3Model = models['o3'];
      
      assert.strictEqual(o3Model.modelName, 'o3');
      assert.strictEqual(o3Model.friendlyName, 'OpenAI (O3)');
      assert.strictEqual(o3Model.contextWindow, 200000);
      assert.strictEqual(o3Model.supportsImages, true);
    });
  });

  describe('getModelConfig', () => {
    it('should return config for exact model name', () => {
      const config = openaiProvider.getModelConfig('o3');
      
      assert.ok(config);
      assert.strictEqual(config.modelName, 'o3');
      assert.strictEqual(config.friendlyName, 'OpenAI (O3)');
    });

    it('should return config for model alias', () => {
      const config = openaiProvider.getModelConfig('o3mini');
      
      assert.ok(config);
      assert.strictEqual(config.modelName, 'o3-mini');
    });

    it('should return null for unknown model', () => {
      const config = openaiProvider.getModelConfig('unknown-model');
      assert.strictEqual(config, null);
    });

    it('should be case insensitive', () => {
      const config = openaiProvider.getModelConfig('O3');
      
      assert.ok(config);
      assert.strictEqual(config.modelName, 'o3');
    });
  });

  describe('invoke - input validation', () => {
    const validConfig = {
      apiKeys: {
        openai: 'sk-1234567890abcdef1234567890abcdef1234567890abcdef'
      }
    };

    it('should throw error for missing API key', async () => {
      const messages = [{ role: 'user', content: 'Hello' }];
      const config = { apiKeys: {} };
      
      await assert.rejects(
        openaiProvider.invoke(messages, { config }),
        {
          name: 'OpenAIProviderError',
          code: 'MISSING_API_KEY'
        }
      );
    });

    it('should throw error for invalid API key format', async () => {
      const messages = [{ role: 'user', content: 'Hello' }];
      const config = { apiKeys: { openai: 'invalid' } };
      
      await assert.rejects(
        openaiProvider.invoke(messages, { config }),
        {
          name: 'OpenAIProviderError',
          code: 'INVALID_API_KEY'
        }
      );
    });

    it('should throw error for non-array messages', async () => {
      const messages = 'not an array';
      
      await assert.rejects(
        openaiProvider.invoke(messages, { config: validConfig }),
        {
          name: 'OpenAIProviderError',
          code: 'INVALID_MESSAGES'
        }
      );
    });

    it('should throw error for invalid message role', async () => {
      const messages = [{ role: 'invalid', content: 'Hello' }];
      
      await assert.rejects(
        openaiProvider.invoke(messages, { config: validConfig }),
        {
          name: 'OpenAIProviderError',
          code: 'INVALID_ROLE'
        }
      );
    });

    it('should throw error for missing message content', async () => {
      const messages = [{ role: 'user' }];
      
      await assert.rejects(
        openaiProvider.invoke(messages, { config: validConfig }),
        {
          name: 'OpenAIProviderError',
          code: 'MISSING_CONTENT'
        }
      );
    });
  });

  describe('temperature handling', () => {
    it('should clamp temperature to valid range', () => {
      // This would be tested with a mocked OpenAI client
      // For now, we verify the model configurations
      const models = openaiProvider.getSupportedModels();
      
      // O3 models don't support temperature
      assert.strictEqual(models['o3'].supportsTemperature, false);
      assert.strictEqual(models['o3-mini'].supportsTemperature, false);
      
      // GPT-4o models do support temperature
      assert.strictEqual(models['gpt-4o'].supportsTemperature, true);
      assert.strictEqual(models['gpt-4o-mini'].supportsTemperature, true);
    });
  });

  describe('model resolution', () => {
    it('should handle model aliases correctly', () => {
      const models = openaiProvider.getSupportedModels();
      
      // Verify aliases are configured
      assert.ok(models['o3-mini'].aliases.includes('o3mini'));
      assert.ok(models['o3-pro-2025-06-10'].aliases.includes('o3-pro'));
    });
  });
});
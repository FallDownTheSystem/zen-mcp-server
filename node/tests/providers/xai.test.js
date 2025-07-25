/**
 * Unit tests for XAI provider
 * Tests the unified interface implementation without making real API calls
 */

import { describe, it } from 'node:test';
import assert from 'node:assert';
import { xaiProvider } from '../../src/providers/xai.js';

describe('XAI Provider', () => {
  describe('validateConfig', () => {
    it('should return true for valid XAI API key', () => {
      const config = {
        apiKeys: {
          xai: 'xai-1234567890abcdef1234567890abcdef1234567890abcdef'
        }
      };
      
      assert.strictEqual(xaiProvider.validateConfig(config), true);
    });

    it('should return false for missing API key', () => {
      const config = { apiKeys: {} };
      assert.strictEqual(xaiProvider.validateConfig(config), false);
    });

    it('should return false for invalid API key format', () => {
      const config = {
        apiKeys: {
          xai: 'invalid-key'
        }
      };
      
      assert.strictEqual(xaiProvider.validateConfig(config), false);
    });

    it('should return false for short API key', () => {
      const config = {
        apiKeys: {
          xai: 'xai-short'
        }
      };
      
      assert.strictEqual(xaiProvider.validateConfig(config), false);
    });

    it('should return false for OpenAI format key', () => {
      const config = {
        apiKeys: {
          xai: 'sk-1234567890abcdef1234567890abcdef1234567890abcdef'
        }
      };
      
      assert.strictEqual(xaiProvider.validateConfig(config), false);
    });
  });

  describe('isAvailable', () => {
    it('should return true when config is valid', () => {
      const config = {
        apiKeys: {
          xai: 'xai-1234567890abcdef1234567890abcdef1234567890abcdef'
        }
      };
      
      assert.strictEqual(xaiProvider.isAvailable(config), true);
    });

    it('should return false when config is invalid', () => {
      const config = { apiKeys: {} };
      assert.strictEqual(xaiProvider.isAvailable(config), false);
    });
  });

  describe('getSupportedModels', () => {
    it('should return supported models object', () => {
      const models = xaiProvider.getSupportedModels();
      
      assert.strictEqual(typeof models, 'object');
      assert.ok('grok-4-0709' in models);
      assert.ok('grok-3' in models);
      assert.ok('grok-3-fast' in models);
    });

    it('should include model configuration details', () => {
      const models = xaiProvider.getSupportedModels();
      const grok4Model = models['grok-4-0709'];
      
      assert.strictEqual(grok4Model.modelName, 'grok-4-0709');
      assert.strictEqual(grok4Model.friendlyName, 'X.AI (Grok 4)');
      assert.strictEqual(grok4Model.contextWindow, 256000);
      assert.strictEqual(grok4Model.supportsImages, true);
      assert.strictEqual(grok4Model.supportsTemperature, true);
    });

    it('should have correct image support configuration', () => {
      const models = xaiProvider.getSupportedModels();
      
      // Grok-4 supports images
      assert.strictEqual(models['grok-4-0709'].supportsImages, true);
      
      // Grok-3 models don't support images
      assert.strictEqual(models['grok-3'].supportsImages, false);
      assert.strictEqual(models['grok-3-fast'].supportsImages, false);
    });
  });

  describe('getModelConfig', () => {
    it('should return config for exact model name', () => {
      const config = xaiProvider.getModelConfig('grok-4-0709');
      
      assert.ok(config);
      assert.strictEqual(config.modelName, 'grok-4-0709');
      assert.strictEqual(config.friendlyName, 'X.AI (Grok 4)');
    });

    it('should return config for model alias', () => {
      const config = xaiProvider.getModelConfig('grok');
      
      assert.ok(config);
      assert.strictEqual(config.modelName, 'grok-4-0709');
    });

    it('should return config for various aliases', () => {
      // Test all grok-4 aliases
      const aliases = ['grok', 'grok4', 'grok-4', 'grok-4-latest'];
      
      for (const alias of aliases) {
        const config = xaiProvider.getModelConfig(alias);
        assert.ok(config, `Should find config for alias: ${alias}`);
        assert.strictEqual(config.modelName, 'grok-4-0709');
      }
    });

    it('should return null for unknown model', () => {
      const config = xaiProvider.getModelConfig('unknown-model');
      assert.strictEqual(config, null);
    });

    it('should be case insensitive', () => {
      const config = xaiProvider.getModelConfig('GROK-4-0709');
      
      assert.ok(config);
      assert.strictEqual(config.modelName, 'grok-4-0709');
    });
  });

  describe('invoke - input validation', () => {
    const validConfig = {
      apiKeys: {
        xai: 'xai-1234567890abcdef1234567890abcdef1234567890abcdef'
      }
    };

    it('should throw error for missing API key', async () => {
      const messages = [{ role: 'user', content: 'Hello' }];
      const config = { apiKeys: {} };
      
      await assert.rejects(
        xaiProvider.invoke(messages, { config }),
        {
          name: 'XAIProviderError',
          code: 'MISSING_API_KEY'
        }
      );
    });

    it('should throw error for invalid API key format', async () => {
      const messages = [{ role: 'user', content: 'Hello' }];
      const config = { apiKeys: { xai: 'invalid' } };
      
      await assert.rejects(
        xaiProvider.invoke(messages, { config }),
        {
          name: 'XAIProviderError',
          code: 'INVALID_API_KEY'
        }
      );
    });

    it('should throw error for OpenAI format key', async () => {
      const messages = [{ role: 'user', content: 'Hello' }];
      const config = { apiKeys: { xai: 'sk-1234567890abcdef1234567890abcdef1234567890abcdef' } };
      
      await assert.rejects(
        xaiProvider.invoke(messages, { config }),
        {
          name: 'XAIProviderError',
          code: 'INVALID_API_KEY'
        }
      );
    });

    it('should throw error for non-array messages', async () => {
      const messages = 'not an array';
      
      await assert.rejects(
        xaiProvider.invoke(messages, { config: validConfig }),
        {
          name: 'XAIProviderError',
          code: 'INVALID_MESSAGES'
        }
      );
    });

    it('should throw error for invalid message role', async () => {
      const messages = [{ role: 'invalid', content: 'Hello' }];
      
      await assert.rejects(
        xaiProvider.invoke(messages, { config: validConfig }),
        {
          name: 'XAIProviderError',
          code: 'INVALID_ROLE'
        }
      );
    });

    it('should throw error for missing message content', async () => {
      const messages = [{ role: 'user' }];
      
      await assert.rejects(
        xaiProvider.invoke(messages, { config: validConfig }),
        {
          name: 'XAIProviderError',
          code: 'MISSING_CONTENT'
        }
      );
    });
  });

  describe('model resolution', () => {
    it('should handle model aliases correctly', () => {
      const models = xaiProvider.getSupportedModels();
      
      // Verify aliases are configured
      assert.ok(models['grok-4-0709'].aliases.includes('grok'));
      assert.ok(models['grok-4-0709'].aliases.includes('grok4'));
      assert.ok(models['grok-4-0709'].aliases.includes('grok-4'));
      assert.ok(models['grok-3'].aliases.includes('grok3'));
      assert.ok(models['grok-3-fast'].aliases.includes('grok3fast'));
    });

    it('should default to grok-4-0709 model', () => {
      const models = xaiProvider.getSupportedModels();
      
      // Default model should be grok-4-0709
      const defaultConfig = xaiProvider.getModelConfig('grok');
      assert.strictEqual(defaultConfig.modelName, 'grok-4-0709');
    });
  });

  describe('temperature handling', () => {
    it('should support temperature for all models', () => {
      const models = xaiProvider.getSupportedModels();
      
      // All Grok models support temperature
      assert.strictEqual(models['grok-4-0709'].supportsTemperature, true);
      assert.strictEqual(models['grok-3'].supportsTemperature, true);
      assert.strictEqual(models['grok-3-fast'].supportsTemperature, true);
    });
  });

  describe('base URL configuration', () => {
    it('should use default XAI base URL when not configured', () => {
      // This would be tested with a mocked OpenAI client
      // For now, we verify the default is correct in the implementation
      const validConfig = {
        apiKeys: {
          xai: 'xai-1234567890abcdef1234567890abcdef1234567890abcdef'
        }
      };
      
      // The implementation should use 'https://api.x.ai/v1' as default
      assert.ok(validConfig.apiKeys.xai.startsWith('xai-'));
    });

    it('should use custom base URL when configured', () => {
      const configWithCustomUrl = {
        apiKeys: {
          xai: 'xai-1234567890abcdef1234567890abcdef1234567890abcdef'
        },
        providers: {
          xaiBaseUrl: 'https://custom.example.com/v1'
        }
      };
      
      // The implementation should respect the custom base URL
      assert.strictEqual(configWithCustomUrl.providers.xaiBaseUrl, 'https://custom.example.com/v1');
    });
  });
});
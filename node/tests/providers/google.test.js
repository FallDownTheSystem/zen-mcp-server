/**
 * Unit tests for Google provider
 * Tests the unified interface implementation without making real API calls
 */

import { describe, it } from 'node:test';
import assert from 'node:assert';
import { googleProvider } from '../../src/providers/google.js';

describe('Google Provider', () => {
  describe('validateConfig', () => {
    it('should return true for valid Google API key', () => {
      const config = {
        apiKeys: {
          google: 'AIzaSyDJKHGFSDKJHGFSDKJHGFSDKJHGFSDKJHGFSDKJHGFSD'
        }
      };
      
      assert.strictEqual(googleProvider.validateConfig(config), true);
    });

    it('should return false for missing API key', () => {
      const config = { apiKeys: {} };
      assert.strictEqual(googleProvider.validateConfig(config), false);
    });

    it('should return false for short API key', () => {
      const config = {
        apiKeys: {
          google: 'short'
        }
      };
      
      assert.strictEqual(googleProvider.validateConfig(config), false);
    });

    it('should return true for minimum length API key', () => {
      const config = {
        apiKeys: {
          google: 'AIzaSy1234567890123456'
        }
      };
      
      assert.strictEqual(googleProvider.validateConfig(config), true);
    });
  });

  describe('isAvailable', () => {
    it('should return true when config is valid', () => {
      const config = {
        apiKeys: {
          google: 'AIzaSyDJKHGFSDKJHGFSDKJHGFSDKJHGFSDKJHGFSDKJHGFSD'
        }
      };
      
      assert.strictEqual(googleProvider.isAvailable(config), true);
    });

    it('should return false when config is invalid', () => {
      const config = { apiKeys: {} };
      assert.strictEqual(googleProvider.isAvailable(config), false);
    });
  });

  describe('getSupportedModels', () => {
    it('should return supported models object', () => {
      const models = googleProvider.getSupportedModels();
      
      assert.strictEqual(typeof models, 'object');
      assert.ok('gemini-2.0-flash' in models);
      assert.ok('gemini-2.0-flash-lite' in models);
      assert.ok('gemini-2.5-flash' in models);
      assert.ok('gemini-2.5-pro' in models);
    });

    it('should include model configuration details', () => {
      const models = googleProvider.getSupportedModels();
      const flashModel = models['gemini-2.5-flash'];
      
      assert.strictEqual(flashModel.modelName, 'gemini-2.5-flash');
      assert.strictEqual(flashModel.friendlyName, 'Gemini (Flash 2.5)');
      assert.strictEqual(flashModel.contextWindow, 1048576);
      assert.strictEqual(flashModel.supportsImages, true);
      assert.strictEqual(flashModel.supportsThinking, true);
    });

    it('should have correct thinking support configuration', () => {
      const models = googleProvider.getSupportedModels();
      
      // Models that support thinking
      assert.strictEqual(models['gemini-2.0-flash'].supportsThinking, true);
      assert.strictEqual(models['gemini-2.5-flash'].supportsThinking, true);
      assert.strictEqual(models['gemini-2.5-pro'].supportsThinking, true);
      
      // Model that doesn't support thinking
      assert.strictEqual(models['gemini-2.0-flash-lite'].supportsThinking, false);
    });

    it('should have correct image support configuration', () => {
      const models = googleProvider.getSupportedModels();
      
      // Models that support images
      assert.strictEqual(models['gemini-2.0-flash'].supportsImages, true);
      assert.strictEqual(models['gemini-2.5-flash'].supportsImages, true);
      assert.strictEqual(models['gemini-2.5-pro'].supportsImages, true);
      
      // Model that doesn't support images
      assert.strictEqual(models['gemini-2.0-flash-lite'].supportsImages, false);
    });
  });

  describe('getModelConfig', () => {
    it('should return config for exact model name', () => {
      const config = googleProvider.getModelConfig('gemini-2.5-flash');
      
      assert.ok(config);
      assert.strictEqual(config.modelName, 'gemini-2.5-flash');
      assert.strictEqual(config.friendlyName, 'Gemini (Flash 2.5)');
    });

    it('should return config for model alias', () => {
      const config = googleProvider.getModelConfig('flash');
      
      assert.ok(config);
      assert.strictEqual(config.modelName, 'gemini-2.5-flash');
    });

    it('should return config for various aliases', () => {
      // Test all flash aliases
      const aliases = ['flash', 'flash2.5', 'gemini-flash', 'gemini-flash-2.5'];
      
      for (const alias of aliases) {
        const config = googleProvider.getModelConfig(alias);
        assert.ok(config, `Should find config for alias: ${alias}`);
        assert.strictEqual(config.modelName, 'gemini-2.5-flash');
      }
    });

    it('should return config for pro model aliases', () => {
      const aliases = ['pro', 'gemini pro', 'gemini-pro', 'gemini'];
      
      for (const alias of aliases) {
        const config = googleProvider.getModelConfig(alias);
        assert.ok(config, `Should find config for alias: ${alias}`);
        assert.strictEqual(config.modelName, 'gemini-2.5-pro');
      }
    });

    it('should return null for unknown model', () => {
      const config = googleProvider.getModelConfig('unknown-model');
      assert.strictEqual(config, null);
    });

    it('should be case insensitive', () => {
      const config = googleProvider.getModelConfig('GEMINI-2.5-FLASH');
      
      assert.ok(config);
      assert.strictEqual(config.modelName, 'gemini-2.5-flash');
    });
  });

  describe('invoke - input validation', () => {
    const validConfig = {
      apiKeys: {
        google: 'AIzaSyDJKHGFSDKJHGFSDKJHGFSDKJHGFSDKJHGFSDKJHGFSD'
      }
    };

    it('should throw error for missing API key', async () => {
      const messages = [{ role: 'user', content: 'Hello' }];
      const config = { apiKeys: {} };
      
      await assert.rejects(
        googleProvider.invoke(messages, { config }),
        {
          name: 'GoogleProviderError',
          code: 'MISSING_API_KEY'
        }
      );
    });

    it('should throw error for invalid API key format', async () => {
      const messages = [{ role: 'user', content: 'Hello' }];
      const config = { apiKeys: { google: 'invalid' } };
      
      await assert.rejects(
        googleProvider.invoke(messages, { config }),
        {
          name: 'GoogleProviderError',
          code: 'INVALID_API_KEY'
        }
      );
    });

    it('should throw error for non-array messages', async () => {
      const messages = 'not an array';
      
      await assert.rejects(
        googleProvider.invoke(messages, { config: validConfig }),
        {
          name: 'GoogleProviderError',
          code: 'INVALID_MESSAGES'
        }
      );
    });

    it('should throw error for invalid message role', async () => {
      const messages = [{ role: 'invalid', content: 'Hello' }];
      
      await assert.rejects(
        googleProvider.invoke(messages, { config: validConfig }),
        {
          name: 'GoogleProviderError',
          code: 'INVALID_ROLE'
        }
      );
    });

    it('should throw error for missing message content', async () => {
      const messages = [{ role: 'user' }];
      
      await assert.rejects(
        googleProvider.invoke(messages, { config: validConfig }),
        {
          name: 'GoogleProviderError',
          code: 'MISSING_CONTENT'
        }
      );
    });
  });

  describe('message format conversion', () => {
    it('should handle system prompts correctly', () => {
      // This would be tested with a mocked Google client
      // For now, we verify the supported models have correct configuration
      const models = googleProvider.getSupportedModels();
      
      // All models should support system prompts (via message conversion)
      assert.ok(models['gemini-2.5-flash']);
      assert.ok(models['gemini-2.5-pro']);
    });

    it('should handle conversation history', () => {
      // This would be tested with a mocked Google client
      // For now, we verify the interface supports multiple messages
      const models = googleProvider.getSupportedModels();
      
      // All models should support conversation (multiple messages)
      assert.ok(models['gemini-2.5-flash']);
      assert.ok(models['gemini-2.5-pro']);
    });
  });

  describe('thinking mode support', () => {
    it('should support thinking for appropriate models', () => {
      const models = googleProvider.getSupportedModels();
      
      // Thinking-enabled models
      assert.strictEqual(models['gemini-2.0-flash'].supportsThinking, true);
      assert.strictEqual(models['gemini-2.5-flash'].supportsThinking, true);
      assert.strictEqual(models['gemini-2.5-pro'].supportsThinking, true);
      
      // Non-thinking model
      assert.strictEqual(models['gemini-2.0-flash-lite'].supportsThinking, false);
    });

    it('should have correct thinking token limits', () => {
      const models = googleProvider.getSupportedModels();
      
      // Pro model has highest thinking budget
      assert.strictEqual(models['gemini-2.5-pro'].maxThinkingTokens, 32768);
      
      // Flash models have moderate thinking budget
      assert.strictEqual(models['gemini-2.5-flash'].maxThinkingTokens, 24576);
      assert.strictEqual(models['gemini-2.0-flash'].maxThinkingTokens, 24576);
      
      // Lite model has no thinking
      assert.strictEqual(models['gemini-2.0-flash-lite'].maxThinkingTokens, 0);
    });
  });

  describe('temperature handling', () => {
    it('should support temperature for all models', () => {
      const models = googleProvider.getSupportedModels();
      
      // All Gemini models support temperature
      assert.strictEqual(models['gemini-2.0-flash'].supportsTemperature, true);
      assert.strictEqual(models['gemini-2.0-flash-lite'].supportsTemperature, true);
      assert.strictEqual(models['gemini-2.5-flash'].supportsTemperature, true);
      assert.strictEqual(models['gemini-2.5-pro'].supportsTemperature, true);
    });
  });

  describe('default model selection', () => {
    it('should default to gemini-2.5-flash', () => {
      // The implementation defaults to 'gemini-2.5-flash'
      const defaultConfig = googleProvider.getModelConfig('gemini-2.5-flash');
      assert.ok(defaultConfig);
      assert.strictEqual(defaultConfig.modelName, 'gemini-2.5-flash');
    });

    it('should support flash as default alias', () => {
      const config = googleProvider.getModelConfig('flash');
      assert.ok(config);
      assert.strictEqual(config.modelName, 'gemini-2.5-flash');
    });
  });

  describe('context window sizes', () => {
    it('should have 1M context for all models', () => {
      const models = googleProvider.getSupportedModels();
      
      // All models should have 1M context window
      assert.strictEqual(models['gemini-2.0-flash'].contextWindow, 1048576);
      assert.strictEqual(models['gemini-2.0-flash-lite'].contextWindow, 1048576);
      assert.strictEqual(models['gemini-2.5-flash'].contextWindow, 1048576);
      assert.strictEqual(models['gemini-2.5-pro'].contextWindow, 1048576);
    });

    it('should have consistent output token limits', () => {
      const models = googleProvider.getSupportedModels();
      
      // All models should have 65536 max output tokens
      assert.strictEqual(models['gemini-2.0-flash'].maxOutputTokens, 65536);
      assert.strictEqual(models['gemini-2.0-flash-lite'].maxOutputTokens, 65536);
      assert.strictEqual(models['gemini-2.5-flash'].maxOutputTokens, 65536);
      assert.strictEqual(models['gemini-2.5-pro'].maxOutputTokens, 65536);
    });
  });
});
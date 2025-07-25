import { describe, it, expect, beforeAll, vi } from 'vitest'
import { loadConfig } from '../../src/config.js'
import { createRouter } from '../../src/router.js'
import { logger } from '../../src/utils/logger.js'
import 'dotenv/config'

// These tests make real API calls - they require valid API keys and will be skipped if not available
describe('Real API Integration Tests', () => {
  let config
  let router
  let hasAnyApiKey = false

  beforeAll(async () => {
    try {
      // Load configuration from environment
      config = await loadConfig()
      router = await createRouter(config)
      
      // Check if we have any API keys for testing
      hasAnyApiKey = !!(config?.apiKeys?.openai || config?.apiKeys?.xai || config?.apiKeys?.google)
      
      if (!hasAnyApiKey) {
        logger.warn('[real-api-test] No API keys found - real API tests will be skipped')
      } else {
        logger.info('[real-api-test] API keys found - running real API integration tests')
      }
    } catch (error) {
      logger.error('[real-api-test] Setup failed:', error)
      // Set config to empty object so skipIf conditions work
      config = { apiKeys: {} }
      hasAnyApiKey = false
    }
  })

  describe('Chat Tool with Real APIs', () => {
    it.skipIf(!hasAnyApiKey)('should complete a simple chat request with available provider', async () => {
      const result = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Hello! Please respond with exactly: "Integration test successful"',
          model: 'auto', // Use first available provider
          temperature: 0.1 // Low temperature for consistent responses
        }
      })

      expect(result).toBeDefined()
      expect(result.isError).toBe(false)
      expect(result.content).toBeDefined()
      expect(Array.isArray(result.content)).toBe(true)
      expect(result.content[0].type).toBe('text')
      expect(result.content[0].text).toBeDefined()
      
      // Should contain the expected response
      expect(result.content[0].text.toLowerCase()).toContain('integration test successful')
      
      // Should have continuation metadata
      expect(result.continuation).toBeDefined()
      expect(result.continuation.id).toBeDefined()
      expect(result.continuation.id.startsWith('conv_')).toBe(true)
      
      logger.info('[real-api-test] Chat tool integration test completed successfully')
    }, 30000) // 30 second timeout for API calls

    it.skipIf(!config?.apiKeys?.openai)('should work with OpenAI provider specifically', async () => {
      const result = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'What is 2+2? Answer with just the number.',
          model: 'gpt-4o-mini',
          temperature: 0
        }
      })

      expect(result.isError).toBe(false)
      expect(result.content[0].text).toContain('4')
      
      logger.info('[real-api-test] OpenAI integration test completed')
    }, 30000)

    it.skipIf(!config?.apiKeys?.xai)('should work with XAI provider specifically', async () => {
      const result = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'What is 3+3? Answer with just the number.',
          model: 'grok',
          temperature: 0
        }
      })

      expect(result.isError).toBe(false)
      expect(result.content[0].text).toContain('6')
      
      logger.info('[real-api-test] XAI integration test completed')
    }, 30000)

    it.skipIf(!config?.apiKeys?.google)('should work with Google provider specifically', async () => {
      const result = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'What is 5+5? Answer with just the number.',
          model: 'flash',
          temperature: 0
        }
      })

      expect(result.isError).toBe(false)
      expect(result.content[0].text).toContain('10')
      
      logger.info('[real-api-test] Google integration test completed')
    }, 30000)
  })

  describe('Consensus Tool with Real APIs', () => {
    it.skipIf(!hasAnyApiKey)('should gather consensus from available providers', async () => {
      // Create models list based on available API keys
      const models = []
      if (config?.apiKeys?.openai) models.push({ model: 'gpt-4o-mini' })
      if (config?.apiKeys?.xai) models.push({ model: 'grok' })
      if (config?.apiKeys?.google) models.push({ model: 'flash' })
      
      if (models.length === 0) {
        return // Skip if no models available
      }

      const result = await router.callTool({
        name: 'consensus',
        arguments: {
          prompt: 'Is the sky blue? Answer with "Yes" or "No" only.',
          models: models,
          enable_cross_feedback: false, // Disable for faster testing
          temperature: 0
        }
      })

      expect(result).toBeDefined()
      expect(result.isError).toBe(false)
      expect(result.content).toBeDefined()
      
      // Parse the consensus result
      const consensusResult = JSON.parse(result.content[0].text)
      expect(consensusResult.status).toBe('consensus_complete')
      expect(consensusResult.models_consulted).toBe(models.length)
      expect(consensusResult.successful_initial_responses).toBeGreaterThan(0)
      expect(consensusResult.phases).toBeDefined()
      expect(consensusResult.phases.initial).toBeDefined()
      
      // Check that we got responses
      consensusResult.phases.initial.forEach(response => {
        expect(response.model).toBeDefined()
        expect(response.status).toBe('success')
        expect(response.response).toBeDefined()
        expect(response.response.toLowerCase()).toContain('yes')
      })
      
      logger.info(`[real-api-test] Consensus test completed with ${models.length} providers`)
    }, 60000) // 60 second timeout for multiple API calls

    it.skipIf(!hasAnyApiKey || !(config?.apiKeys?.openai && config?.apiKeys?.google))('should test cross-feedback with multiple providers', async () => {
      // Only run if we have at least 2 providers
      const models = [
        { model: 'gpt-4o-mini' },
        { model: 'flash' }
      ]

      const result = await router.callTool({
        name: 'consensus',
        arguments: {
          prompt: 'What color is grass? Please be concise.',
          models: models,
          enable_cross_feedback: true,
          temperature: 0.1
        }
      })

      expect(result.isError).toBe(false)
      
      const consensusResult = JSON.parse(result.content[0].text)
      expect(consensusResult.phases.initial).toBeDefined()
      expect(consensusResult.phases.refined).toBeDefined()
      expect(consensusResult.refined_responses).toBeGreaterThan(0)
      
      logger.info('[real-api-test] Cross-feedback consensus test completed')
    }, 90000) // 90 second timeout for cross-feedback
  })

  describe('Conversation Continuity', () => {
    it.skipIf(!hasAnyApiKey)('should maintain conversation history across requests', async () => {
      // First message
      const firstResult = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Remember this number: 42. Just say "Remembered" to confirm.',
          model: 'auto',
          temperature: 0
        }
      })

      expect(firstResult.isError).toBe(false)
      const conversationId = firstResult.continuation.id
      expect(conversationId).toBeDefined()

      // Second message using continuation
      const secondResult = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'What number did I ask you to remember?',
          continuation: conversationId,
          model: 'auto',
          temperature: 0
        }
      })

      expect(secondResult.isError).toBe(false)
      expect(secondResult.content[0].text).toContain('42')
      
      logger.info('[real-api-test] Conversation continuity test completed')
    }, 60000)
  })

  describe('Error Handling with Real APIs', () => {
    it.skipIf(!hasAnyApiKey)('should handle invalid model names gracefully', async () => {
      const result = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Hello',
          model: 'nonexistent-model-123'
        }
      })

      // Should either succeed with a fallback or fail gracefully
      if (result.isError) {
        expect(result.error).toBeDefined()
        expect(result.error.message).toMatch(/(model|provider|not found|not available)/i)
      }
    })

    it.skipIf(!hasAnyApiKey)('should handle very large prompts appropriately', async () => {
      const largePrompt = 'This is a very long prompt. '.repeat(1000) + 'Please respond briefly.'
      
      const result = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: largePrompt,
          model: 'auto'
        }
      })

      // Should either succeed or fail with context length error
      if (result.isError) {
        expect(result.error.message).toMatch(/(context|length|token|limit)/i)
      } else {
        expect(result.content[0].text).toBeDefined()
      }
    }, 45000)
  })

  describe('Provider-Specific Features', () => {
    it.skipIf(!config?.apiKeys?.google)('should support Google thinking mode', async () => {
      const result = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Think step by step: What is 17 * 23?',
          model: 'gemini-2.5-pro',
          thinking: 'medium'
        }
      })

      expect(result.isError).toBe(false)
      expect(result.content[0].text).toBeDefined()
      
      logger.info('[real-api-test] Google thinking mode test completed')
    }, 45000)

    it.skipIf(!config?.apiKeys?.openai)('should support OpenAI reasoning effort for O3', async () => {
      const result = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'What is 2+2?',
          model: 'o3-mini',
          reasoningEffort: 'low'
        }
      })

      // May fail if O3 is not available, that's expected
      if (!result.isError) {
        expect(result.content[0].text).toContain('4')
      }
      
      logger.info('[real-api-test] OpenAI O3 reasoning effort test completed')
    }, 45000)
  })

  describe('Performance with Real APIs', () => {
    it.skipIf(!hasAnyApiKey)('should complete simple requests within reasonable time', async () => {
      const startTime = Date.now()
      
      const result = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Say "OK"',
          model: 'auto'
        }
      })

      const duration = Date.now() - startTime
      
      expect(result.isError).toBe(false)
      expect(duration).toBeLessThan(30000) // Should complete within 30 seconds
      
      logger.info(`[real-api-test] Performance test completed in ${duration}ms`)
    }, 35000)
  })
})
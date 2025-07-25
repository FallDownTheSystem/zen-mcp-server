import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { loadConfig } from '../../src/config.js'
import { createRouter } from '../../src/router.js'
import { logger } from '../../src/utils/logger.js'
import 'dotenv/config'

describe('Enhanced Real API Integration Tests', () => {
  let config
  let router
  let availableProviders = {
    openai: false,
    xai: false,
    google: false
  }

  beforeAll(async () => {
    try {
      config = await loadConfig()
      router = await createRouter(config)
      
      // Check which providers are available
      availableProviders.openai = !!(config?.apiKeys?.openai && config.apiKeys.openai.startsWith('sk-'))
      availableProviders.xai = !!(config?.apiKeys?.xai && config.apiKeys.xai.startsWith('xai-'))
      availableProviders.google = !!(config?.apiKeys?.google && config.apiKeys.google.length > 20)
      
      const available = Object.entries(availableProviders).filter(([_, isAvailable]) => isAvailable).map(([name]) => name)
      
      if (available.length === 0) {
        logger.warn('[real-api-enhanced-test] No API keys found - all real API tests will be skipped')
      } else {
        logger.info(`[real-api-enhanced-test] Available providers: ${available.join(', ')}`)
      }
    } catch (error) {
      logger.error('[real-api-enhanced-test] Setup failed:', error)
      config = { apiKeys: {} }
      availableProviders = { openai: false, xai: false, google: false }
    }
  })

  afterAll(async () => {
    logger.info('[real-api-enhanced-test] Enhanced real API test cleanup completed')
  })

  describe('Provider-Specific API Tests', () => {
    describe('OpenAI Integration', () => {
      it.skipIf(!availableProviders.openai)('should handle GPT-4o-mini requests correctly', async () => {
        const result = await router.callTool({
          name: 'chat',
          arguments: {
            prompt: 'Respond with exactly: "OpenAI API working"',
            model: 'gpt-4o-mini',
            temperature: 0
          }
        })

        expect(result.isError).toBe(false)
        expect(result.content[0].text).toContain('OpenAI API working')
        expect(result.continuation).toBeDefined()
        
        logger.info('[real-api-enhanced-test] OpenAI GPT-4o-mini integration successful')
      }, 30000)

      it.skipIf(!availableProviders.openai)('should handle O3-mini with reasoning effort', async () => {
        const result = await router.callTool({
          name: 'chat',
          arguments: {
            prompt: 'What is 17 * 23? Show your reasoning.',
            model: 'o3-mini',
            reasoningEffort: 'low',
            temperature: 0
          }
        })

        // May fail if O3 is not available, that's expected
        if (!result.isError) {
          expect(result.content[0].text).toContain('391')
          logger.info('[real-api-enhanced-test] OpenAI O3-mini reasoning effort successful')
        } else {
          logger.info('[real-api-enhanced-test] OpenAI O3-mini not available (expected)')
        }
      }, 60000)

      it.skipIf(!availableProviders.openai)('should handle token usage reporting', async () => {
        const result = await router.callTool({
          name: 'chat',
          arguments: {
            prompt: 'Count to 5.',
            model: 'gpt-4o-mini',
            temperature: 0
          }
        })

        expect(result.isError).toBe(false)
        
        // Check if token usage is reported in the response
        if (result.metadata?.tokenUsage) {
          expect(result.metadata.tokenUsage.inputTokens).toBeGreaterThan(0)
          expect(result.metadata.tokenUsage.outputTokens).toBeGreaterThan(0)
          expect(result.metadata.tokenUsage.totalTokens).toBeGreaterThan(0)
        }
      }, 30000)
    })

    describe('XAI Integration', () => {
      it.skipIf(!availableProviders.xai)('should handle Grok-4 requests correctly', async () => {
        const result = await router.callTool({
          name: 'chat',
          arguments: {
            prompt: 'Respond with exactly: "XAI Grok API working"',
            model: 'grok-4-0709',
            temperature: 0
          }
        })

        expect(result.isError).toBe(false)
        expect(result.content[0].text).toContain('XAI Grok API working')
        
        logger.info('[real-api-enhanced-test] XAI Grok-4 integration successful')
      }, 30000)

      it.skipIf(!availableProviders.xai)('should handle Grok model aliases', async () => {
        const aliases = ['grok', 'grok4', 'grok-4']
        
        for (const alias of aliases) {
          const result = await router.callTool({
            name: 'chat',
            arguments: {
              prompt: `Test alias ${alias}. Respond with "OK".`,
              model: alias,
              temperature: 0
            }
          })

          expect(result.isError).toBe(false)
          expect(result.content[0].text).toContain('OK')
        }
        
        logger.info('[real-api-enhanced-test] XAI model aliases working')
      }, 90000)
    })

    describe('Google Integration', () => {
      it.skipIf(!availableProviders.google)('should handle Gemini Flash requests correctly', async () => {
        const result = await router.callTool({
          name: 'chat',
          arguments: {
            prompt: 'Respond with exactly: "Google Gemini API working"',
            model: 'flash',
            temperature: 0
          }
        })

        expect(result.isError).toBe(false)
        expect(result.content[0].text).toContain('Google Gemini API working')
        
        logger.info('[real-api-enhanced-test] Google Gemini Flash integration successful')
      }, 30000)

      it.skipIf(!availableProviders.google)('should handle thinking mode correctly', async () => {
        const result = await router.callTool({
          name: 'chat',
          arguments: {
            prompt: 'Think step by step: What is 15 * 17?',
            model: 'gemini-2.5-pro',
            thinking: 'medium',
            temperature: 0
          }
        })

        expect(result.isError).toBe(false)
        expect(result.content[0].text).toContain('255')
        
        logger.info('[real-api-enhanced-test] Google thinking mode successful')
      }, 45000)

      it.skipIf(!availableProviders.google)('should handle Gemini model aliases', async () => {
        const aliases = ['flash', 'gemini-flash', 'pro', 'gemini-pro']
        
        for (const alias of aliases) {
          const result = await router.callTool({
            name: 'chat',
            arguments: {
              prompt: `Test alias ${alias}. Respond with "WORKING".`,
              model: alias,
              temperature: 0
            }
          })

          expect(result.isError).toBe(false)
          expect(result.content[0].text).toContain('WORKING')
        }
        
        logger.info('[real-api-enhanced-test] Google model aliases working')
      }, 120000)
    })
  })

  describe('Multi-Provider Consensus Tests', () => {
    it.skipIf(Object.values(availableProviders).filter(Boolean).length < 2)('should gather consensus from multiple providers', async () => {
      const models = []
      if (availableProviders.openai) models.push({ model: 'gpt-4o-mini' })
      if (availableProviders.xai) models.push({ model: 'grok' })
      if (availableProviders.google) models.push({ model: 'flash' })

      const result = await router.callTool({
        name: 'consensus',
        arguments: {
          prompt: 'What is the chemical symbol for gold? Answer with just the symbol.',
          models: models,
          enable_cross_feedback: false,
          temperature: 0
        }
      })

      expect(result.isError).toBe(false)
      
      const consensusResult = JSON.parse(result.content[0].text)
      expect(consensusResult.status).toBe('consensus_complete')
      expect(consensusResult.models_consulted).toBe(models.length)
      expect(consensusResult.successful_initial_responses).toBeGreaterThan(0)
      
      // Check that responses contain the correct answer
      consensusResult.phases.initial.forEach(response => {
        expect(response.status).toBe('success')
        expect(response.response.toUpperCase()).toContain('AU')
      })
      
      logger.info(`[real-api-enhanced-test] Multi-provider consensus successful with ${models.length} providers`)
    }, 90000)

    it.skipIf(Object.values(availableProviders).filter(Boolean).length < 2)('should handle cross-feedback consensus', async () => {
      const models = []
      if (availableProviders.openai) models.push({ model: 'gpt-4o-mini' })
      if (availableProviders.google) models.push({ model: 'flash' })

      if (models.length < 2) return // Skip if less than 2 providers

      const result = await router.callTool({
        name: 'consensus',
        arguments: {
          prompt: 'What is the capital of Japan? Be concise.',
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
      
      // Both phases should mention Tokyo
      consensusResult.phases.initial.forEach(response => {
        expect(response.response.toLowerCase()).toContain('tokyo')
      })
      
      consensusResult.phases.refined.forEach(response => {
        expect(response.refined_response.toLowerCase()).toContain('tokyo')
      })
      
      logger.info('[real-api-enhanced-test] Cross-feedback consensus successful')
    }, 120000)
  })

  describe('Advanced Real-World Scenarios', () => {
    it.skipIf(!Object.values(availableProviders).some(Boolean))('should handle complex conversation flow', async () => {
      // Start conversation
      const start = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'I want to learn about machine learning. What should I start with?',
          model: 'auto',
          temperature: 0.3
        }
      })

      expect(start.isError).toBe(false)
      const conversationId = start.continuation.id

      // Follow up
      const followUp = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'I have a background in statistics. How does that help?',
          continuation: conversationId,
          temperature: 0.3
        }
      })

      expect(followUp.isError).toBe(false)
      expect(followUp.continuation.id).toBe(conversationId)

      // Switch to consensus for comparison
      const consensus = await router.callTool({
        name: 'consensus',
        arguments: {
          prompt: 'Should I learn Python or R for machine learning?',
          models: [{ model: 'auto' }],
          continuation: conversationId,
          enable_cross_feedback: false,
          temperature: 0.3
        }
      })

      expect(consensus.isError).toBe(false)
      expect(consensus.continuation.id).toBe(conversationId)
      
      logger.info('[real-api-enhanced-test] Complex conversation flow successful')
    }, 120000)

    it.skipIf(!Object.values(availableProviders).some(Boolean))('should handle file context processing', async () => {
      const result = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Analyze the package.json file and tell me what this project does.',
          files: ['package.json'],
          model: 'auto',
          temperature: 0
        }
      })

      expect(result.isError).toBe(false)
      
      // Response should reference the package.json content
      const responseText = result.content[0].text.toLowerCase()
      expect(responseText).toMatch(/(package|node|javascript|converse|mcp|server)/i)
      
      logger.info('[real-api-enhanced-test] File context processing successful')
    }, 45000)

    it.skipIf(!Object.values(availableProviders).some(Boolean))('should handle parameter validation with real APIs', async () => {
      // Test temperature bounds
      const tempTest = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Test temperature parameter.',
          model: 'auto',
          temperature: 0.8
        }
      })

      expect(tempTest.isError).toBe(false)

      // Test max tokens
      const tokenTest = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Write a very brief response.',
          model: 'auto',
          maxTokens: 10
        }
      })

      expect(tokenTest.isError).toBe(false)
      // Response should be brief due to token limit
      expect(tokenTest.content[0].text.length).toBeLessThan(100)
      
      logger.info('[real-api-enhanced-test] Parameter validation successful')
    }, 60000)
  })

  describe('Error Handling with Real APIs', () => {
    it.skipIf(!Object.values(availableProviders).some(Boolean))('should handle rate limiting gracefully', async () => {
      // Make rapid requests to potentially trigger rate limiting
      const rapidRequests = []
      for (let i = 0; i < 5; i++) {
        rapidRequests.push(
          router.callTool({
            name: 'chat',
            arguments: {
              prompt: `Rapid request ${i + 1}`,
              model: 'auto',
              temperature: 0
            }
          })
        )
      }

      const results = await Promise.allSettled(rapidRequests)
      
      // At least some should succeed
      const successful = results.filter(r => r.status === 'fulfilled' && !r.value.isError)
      expect(successful.length).toBeGreaterThan(0)
      
      // If any failed due to rate limiting, should have appropriate error
      const rateLimited = results.filter(r => 
        r.status === 'fulfilled' && 
        r.value.isError && 
        r.value.error.message.toLowerCase().includes('rate')
      )
      
      if (rateLimited.length > 0) {
        logger.info(`[real-api-enhanced-test] Rate limiting detected and handled: ${rateLimited.length} requests`)
      }
    }, 90000)

    it.skipIf(!Object.values(availableProviders).some(Boolean))('should handle context length limits', async () => {
      const veryLongPrompt = 'This is a very long prompt. '.repeat(2000) + 'Respond briefly.'
      
      const result = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: veryLongPrompt,
          model: 'auto'
        }
      })

      // Should either succeed or fail with context length error
      if (result.isError) {
        expect(result.error.message.toLowerCase()).toMatch(/(context|length|token|limit)/i)
      } else {
        expect(result.content[0].text).toBeDefined()
      }
      
      logger.info('[real-api-enhanced-test] Context length handling verified')
    }, 45000)

    it.skipIf(!Object.values(availableProviders).some(Boolean))('should handle provider switching on failure', async () => {
      // Try with a model that might not be available
      const result = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Test provider fallback',
          model: 'auto' // Should pick best available
        }
      })

      // Should succeed with some provider
      expect(result.isError).toBe(false)
      expect(result.content[0].text).toBeDefined()
      
      logger.info('[real-api-enhanced-test] Provider fallback successful')
    }, 30000)
  })

  describe('Performance with Real APIs', () => {
    it.skipIf(!Object.values(availableProviders).some(Boolean))('should meet performance benchmarks', async () => {
      const performanceTests = [
        {
          name: 'Simple question',
          prompt: 'What is 2+2?',
          maxTime: 15000 // 15 seconds
        },
        {
          name: 'Medium complexity',
          prompt: 'Explain the concept of recursion in programming.',
          maxTime: 30000 // 30 seconds
        }
      ]

      for (const test of performanceTests) {
        const startTime = Date.now()
        
        const result = await router.callTool({
          name: 'chat',
          arguments: {
            prompt: test.prompt,
            model: 'auto',
            temperature: 0
          }
        })

        const duration = Date.now() - startTime
        
        expect(result.isError).toBe(false)
        expect(duration).toBeLessThan(test.maxTime)
        
        logger.info(`[real-api-enhanced-test] ${test.name} completed in ${duration}ms`)
      }
    }, 90000)

    it.skipIf(!Object.values(availableProviders).some(Boolean))('should handle concurrent real API calls', async () => {
      const concurrentRequests = 3
      const requests = []

      for (let i = 0; i < concurrentRequests; i++) {
        requests.push(
          router.callTool({
            name: 'chat',
            arguments: {
              prompt: `Concurrent real API test ${i + 1}`,
              model: 'auto',
              temperature: 0
            }
          })
        )
      }

      const results = await Promise.all(requests)
      
      // All should succeed
      results.forEach((result, index) => {
        expect(result.isError).toBe(false)
        expect(result.content[0].text).toBeDefined()
        expect(result.continuation.id).toBeDefined()
      })
      
      // All continuation IDs should be unique
      const continuationIds = results.map(r => r.continuation.id)
      const uniqueIds = new Set(continuationIds)
      expect(uniqueIds.size).toBe(concurrentRequests)
      
      logger.info(`[real-api-enhanced-test] ${concurrentRequests} concurrent real API calls successful`)
    }, 60000)
  })

  describe('Provider Compatibility', () => {
    it.skipIf(!Object.values(availableProviders).some(Boolean))('should produce consistent outputs across providers', async () => {
      const testPrompt = 'What is the capital of France? Answer with just the city name.'
      const results = []

      // Test each available provider
      if (availableProviders.openai) {
        const result = await router.callTool({
          name: 'chat',
          arguments: {
            prompt: testPrompt,
            model: 'gpt-4o-mini',
            temperature: 0
          }
        })
        results.push({ provider: 'openai', result })
      }

      if (availableProviders.xai) {
        const result = await router.callTool({
          name: 'chat',
          arguments: {
            prompt: testPrompt,
            model: 'grok',
            temperature: 0
          }
        })
        results.push({ provider: 'xai', result })
      }

      if (availableProviders.google) {
        const result = await router.callTool({
          name: 'chat',
          arguments: {
            prompt: testPrompt,
            model: 'flash',
            temperature: 0
          }
        })
        results.push({ provider: 'google', result })
      }

      // All should succeed and mention Paris
      results.forEach(({ provider, result }) => {
        expect(result.isError).toBe(false)
        expect(result.content[0].text.toLowerCase()).toContain('paris')
        logger.info(`[real-api-enhanced-test] ${provider} provider consistency verified`)
      })
    }, 120000)
  })
})
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { loadConfig } from '../../src/config.js'
import { createRouter } from '../../src/router.js'
import { logger } from '../../src/utils/logger.js'

describe('Consensus Performance Tests', () => {
  let config
  let router
  let hasMultipleProviders = false

  beforeAll(async () => {
    try {
      config = await loadConfig()
      router = await createRouter(config)
      
      // Check if we have multiple providers for performance testing
      const providerCount = [
        config?.apiKeys?.openai,
        config?.apiKeys?.xai,
        config?.apiKeys?.google
      ].filter(Boolean).length

      hasMultipleProviders = providerCount >= 2
      
      if (!hasMultipleProviders) {
        logger.warn('[performance-consensus-test] Less than 2 providers available - some tests will be skipped')
      } else {
        logger.info(`[performance-consensus-test] ${providerCount} providers available for performance testing`)
      }
    } catch (error) {
      logger.error('[performance-consensus-test] Setup failed:', error)
      config = { apiKeys: {} }
      hasMultipleProviders = false
    }
  })

  afterAll(async () => {
    logger.info('[performance-consensus-test] Consensus performance test cleanup completed')
  })

  describe('Parallel Execution Performance', () => {
    it('should execute consensus faster than sequential calls', async () => {
      const models = [
        { model: 'auto' },
        { model: 'auto' },
        { model: 'auto' }
      ]

      const testPrompt = 'What is 2+2? Answer with just the number.'

      // Test parallel execution (consensus tool)
      const parallelStartTime = Date.now()
      const parallelResult = await router.callTool({
        name: 'consensus',
        arguments: {
          prompt: testPrompt,
          models: models,
          enable_cross_feedback: false,
          temperature: 0
        }
      })
      const parallelDuration = Date.now() - parallelStartTime

      expect(parallelResult.isError).toBe(false)
      const consensusData = JSON.parse(parallelResult.content[0].text)
      
      // Test sequential execution (individual chat calls)
      const sequentialStartTime = Date.now()
      const sequentialResults = []
      
      for (const model of models) {
        const result = await router.callTool({
          name: 'chat',
          arguments: {
            prompt: testPrompt,
            model: model.model,
            temperature: 0
          }
        })
        sequentialResults.push(result)
      }
      const sequentialDuration = Date.now() - sequentialStartTime

      // Parallel should be faster than sequential
      expect(parallelDuration).toBeLessThan(sequentialDuration)
      
      // Calculate efficiency
      const efficiency = (sequentialDuration / parallelDuration).toFixed(2)
      
      logger.info(`[performance-consensus-test] Parallel: ${parallelDuration}ms, Sequential: ${sequentialDuration}ms, Efficiency: ${efficiency}x`)
      
      // Should be at least 1.5x faster for 3 models
      expect(efficiency).toBeGreaterThan(1.5)
    }, 120000)

    it('should maintain performance with increasing model count', async () => {
      const testPrompt = 'What is the capital of France?'
      const modelCounts = [1, 2, 3, 4, 5]
      const results = []

      for (const count of modelCounts) {
        const models = Array(count).fill({ model: 'auto' })
        
        const startTime = Date.now()
        const result = await router.callTool({
          name: 'consensus',
          arguments: {
            prompt: testPrompt,
            models: models,
            enable_cross_feedback: false,
            temperature: 0
          }
        })
        const duration = Date.now() - startTime

        expect(result.isError).toBe(false)
        
        results.push({
          modelCount: count,
          duration: duration,
          result: result
        })

        logger.info(`[performance-consensus-test] ${count} models: ${duration}ms`)
      }

      // Performance should scale reasonably
      // Duration shouldn't increase linearly with model count (that would indicate sequential execution)
      const singleModelTime = results[0].duration
      const multiModelTime = results[results.length - 1].duration
      
      // Multi-model should not be more than 2x slower than single model (indicating good parallelization)
      const performanceRatio = multiModelTime / singleModelTime
      expect(performanceRatio).toBeLessThan(2.5)
      
      logger.info(`[performance-consensus-test] Performance ratio (${modelCounts[modelCounts.length - 1]} vs 1 model): ${performanceRatio.toFixed(2)}x`)
    }, 300000) // 5 minute timeout for multiple calls

    it('should handle cross-feedback performance correctly', async () => {
      const models = [
        { model: 'auto' },
        { model: 'auto' }
      ]

      const testPrompt = 'What are the benefits of renewable energy?'

      // Test without cross-feedback
      const noCrossFeedbackStart = Date.now()
      const noCrossFeedbackResult = await router.callTool({
        name: 'consensus',
        arguments: {
          prompt: testPrompt,
          models: models,
          enable_cross_feedback: false,
          temperature: 0.1
        }
      })
      const noCrossFeedbackDuration = Date.now() - noCrossFeedbackStart

      expect(noCrossFeedbackResult.isError).toBe(false)

      // Test with cross-feedback
      const crossFeedbackStart = Date.now()
      const crossFeedbackResult = await router.callTool({
        name: 'consensus',
        arguments: {
          prompt: testPrompt,
          models: models,
          enable_cross_feedback: true,
          temperature: 0.1
        }
      })
      const crossFeedbackDuration = Date.now() - crossFeedbackStart

      expect(crossFeedbackResult.isError).toBe(false)

      // Cross-feedback should take longer (roughly 2x) due to additional round
      const ratio = crossFeedbackDuration / noCrossFeedbackDuration
      expect(ratio).toBeGreaterThan(1.5)
      expect(ratio).toBeLessThan(3.5) // But not more than 3.5x

      logger.info(`[performance-consensus-test] No cross-feedback: ${noCrossFeedbackDuration}ms, With cross-feedback: ${crossFeedbackDuration}ms, Ratio: ${ratio.toFixed(2)}x`)

      // Verify we got refinements
      const crossFeedbackData = JSON.parse(crossFeedbackResult.content[0].text)
      expect(crossFeedbackData.phases.refined).toBeDefined()
      expect(crossFeedbackData.refined_responses).toBeGreaterThan(0)
    }, 180000) // 3 minute timeout
  })

  describe('Concurrent Consensus Performance', () => {
    it('should handle multiple concurrent consensus requests', async () => {
      const concurrentRequests = 3
      const models = [
        { model: 'auto' },
        { model: 'auto' }
      ]

      const requests = []
      const startTime = Date.now()

      // Create concurrent consensus requests
      for (let i = 0; i < concurrentRequests; i++) {
        requests.push(
          router.callTool({
            name: 'consensus',
            arguments: {
              prompt: `Concurrent consensus test ${i + 1}: What is ${i + 2} + ${i + 3}?`,
              models: models,
              enable_cross_feedback: false,
              temperature: 0
            }
          })
        )
      }

      const results = await Promise.all(requests)
      const totalDuration = Date.now() - startTime

      // All should succeed
      results.forEach((result, index) => {
        expect(result.isError).toBe(false)
        const consensusData = JSON.parse(result.content[0].text)
        expect(consensusData.status).toBe('consensus_complete')
        expect(consensusData.models_consulted).toBe(models.length)
      })

      // Should complete all requests reasonably quickly
      const avgDurationPerRequest = totalDuration / concurrentRequests
      expect(avgDurationPerRequest).toBeLessThan(60000) // 1 minute per request on average

      logger.info(`[performance-consensus-test] ${concurrentRequests} concurrent consensus requests completed in ${totalDuration}ms (avg: ${avgDurationPerRequest}ms per request)`)
    }, 180000)

    it('should maintain quality under concurrent load', async () => {
      const concurrentRequests = 5
      const models = [{ model: 'auto' }]
      const testPrompt = 'What is the square root of 16?'

      const requests = []

      for (let i = 0; i < concurrentRequests; i++) {
        requests.push(
          router.callTool({
            name: 'consensus',
            arguments: {
              prompt: testPrompt,
              models: models,
              enable_cross_feedback: false,
              temperature: 0
            }
          })
        )
      }

      const results = await Promise.all(requests)

      // All should succeed and give correct answer
      results.forEach((result, index) => {
        expect(result.isError).toBe(false)
        
        const consensusData = JSON.parse(result.content[0].text)
        expect(consensusData.successful_initial_responses).toBe(1)
        
        // Should contain correct answer (4)
        const response = consensusData.phases.initial[0].response
        expect(response).toContain('4')
      })

      logger.info(`[performance-consensus-test] ${concurrentRequests} concurrent requests maintained quality`)
    }, 120000)
  })

  describe('Memory and Resource Usage', () => {
    it('should maintain reasonable memory usage during consensus', async () => {
      const initialMemory = process.memoryUsage()

      // Run a large consensus operation
      const models = Array(5).fill({ model: 'auto' })
      
      const result = await router.callTool({
        name: 'consensus',
        arguments: {
          prompt: 'Explain the importance of parallel processing in modern computing.',
          models: models,
          enable_cross_feedback: true,
          temperature: 0.2
        }
      })

      const finalMemory = process.memoryUsage()
      const memoryIncrease = finalMemory.heapUsed - initialMemory.heapUsed

      expect(result.isError).toBe(false)
      
      // Memory increase should be reasonable (less than 50MB)
      expect(memoryIncrease).toBeLessThan(50 * 1024 * 1024)

      logger.info(`[performance-consensus-test] Memory increase during consensus: ${Math.round(memoryIncrease / 1024 / 1024)}MB`)
    }, 120000)

    it('should handle resource cleanup correctly', async () => {
      const { getContinuationStore } = await import('../../src/continuationStore.js')
      const store = getContinuationStore()

      const initialStats = await store.getStats()
      const initialConversations = initialStats.totalConversations

      // Create multiple consensus conversations
      const conversations = []
      for (let i = 0; i < 3; i++) {
        const result = await router.callTool({
          name: 'consensus',
          arguments: {
            prompt: `Resource cleanup test ${i + 1}`,
            models: [{ model: 'auto' }],
            enable_cross_feedback: false
          }
        })
        conversations.push(result.continuation.id)
      }

      const midStats = await store.getStats()
      expect(midStats.totalConversations).toBe(initialConversations + 3)

      // Cleanup conversations
      for (const id of conversations) {
        await store.delete(id)
      }

      const finalStats = await store.getStats()
      expect(finalStats.totalConversations).toBe(initialConversations)

      logger.info('[performance-consensus-test] Resource cleanup verified')
    }, 90000)
  })

  describe('Error Handling Performance', () => {
    it('should fail fast when no providers are available', async () => {
      // Create config with no API keys
      const emptyConfig = {
        ...config,
        apiKeys: {
          openai: null,
          xai: null,
          google: null
        }
      }

      const emptyRouter = await createRouter(emptyConfig)

      const startTime = Date.now()
      const result = await emptyRouter.callTool({
        name: 'consensus',
        arguments: {
          prompt: 'This should fail fast',
          models: [{ model: 'auto' }]
        }
      })
      const duration = Date.now() - startTime

      expect(result.isError).toBe(true)
      // Should fail quickly (within 5 seconds)
      expect(duration).toBeLessThan(5000)

      logger.info(`[performance-consensus-test] Fast failure completed in ${duration}ms`)
    }, 15000)

    it('should handle partial provider failures efficiently', async () => {
      const models = [
        { model: 'auto' },
        { model: 'nonexistent-model' },
        { model: 'auto' }
      ]

      const startTime = Date.now()
      const result = await router.callTool({
        name: 'consensus',
        arguments: {
          prompt: 'Partial failure test',
          models: models,
          enable_cross_feedback: false,
          temperature: 0
        }
      })
      const duration = Date.now() - startTime

      // Should complete despite partial failures
      expect(result.isError).toBe(false)
      
      const consensusData = JSON.parse(result.content[0].text)
      expect(consensusData.successful_initial_responses).toBeGreaterThan(0)
      
      // Should complete in reasonable time
      expect(duration).toBeLessThan(60000)

      logger.info(`[performance-consensus-test] Partial failure handling completed in ${duration}ms`)
    }, 90000)
  })

  describe('Scalability Testing', () => {
    it.skipIf(!hasMultipleProviders)('should scale with real multiple providers', async () => {
      const availableModels = []
      
      if (config?.apiKeys?.openai) availableModels.push({ model: 'gpt-4o-mini' })
      if (config?.apiKeys?.xai) availableModels.push({ model: 'grok' })
      if (config?.apiKeys?.google) availableModels.push({ model: 'flash' })

      if (availableModels.length < 2) return

      const testPrompt = 'What is the speed of light?'

      // Test with increasing provider counts
      for (let count = 1; count <= availableModels.length; count++) {
        const models = availableModels.slice(0, count)
        
        const startTime = Date.now()
        const result = await router.callTool({
          name: 'consensus',
          arguments: {
            prompt: testPrompt,
            models: models,
            enable_cross_feedback: false,
            temperature: 0
          }
        })
        const duration = Date.now() - startTime

        expect(result.isError).toBe(false)
        
        const consensusData = JSON.parse(result.content[0].text)
        expect(consensusData.models_consulted).toBe(count)
        expect(consensusData.successful_initial_responses).toBeGreaterThan(0)

        logger.info(`[performance-consensus-test] ${count} real providers: ${duration}ms`)
      }
    }, 180000)

    it('should handle high-frequency consensus requests', async () => {
      const requestCount = 10
      const models = [{ model: 'auto' }]
      const requests = []

      const startTime = Date.now()

      // Fire off many requests quickly
      for (let i = 0; i < requestCount; i++) {
        requests.push(
          router.callTool({
            name: 'consensus',
            arguments: {
              prompt: `High frequency test ${i}`,
              models: models,
              enable_cross_feedback: false,
              temperature: 0
            }
          })
        )
      }

      const results = await Promise.allSettled(requests)
      const totalDuration = Date.now() - startTime

      // Count successes
      const successful = results.filter(r => r.status === 'fulfilled' && !r.value.isError)
      const failed = results.length - successful.length

      expect(successful.length).toBeGreaterThan(requestCount * 0.8) // At least 80% success rate

      const avgDuration = totalDuration / requestCount
      logger.info(`[performance-consensus-test] High frequency: ${successful.length}/${requestCount} successful, avg ${avgDuration}ms per request`)

      if (failed > 0) {
        logger.info(`[performance-consensus-test] ${failed} requests failed (rate limiting or provider issues)`)
      }
    }, 300000) // 5 minute timeout
  })

  describe('Performance Benchmarks', () => {
    it('should meet baseline performance requirements', async () => {
      const benchmarks = [
        {
          name: 'Simple question - 1 model',
          models: [{ model: 'auto' }],
          prompt: 'What is 1+1?',
          maxTime: 30000, // 30 seconds
          crossFeedback: false
        },
        {
          name: 'Medium complexity - 2 models',
          models: [{ model: 'auto' }, { model: 'auto' }],
          prompt: 'Explain the concept of machine learning briefly.',
          maxTime: 60000, // 1 minute
          crossFeedback: false
        },
        {
          name: 'Complex with cross-feedback - 2 models',
          models: [{ model: 'auto' }, { model: 'auto' }],
          prompt: 'Compare the advantages of renewable vs fossil fuels.',
          maxTime: 120000, // 2 minutes
          crossFeedback: true
        }
      ]

      for (const benchmark of benchmarks) {
        const startTime = Date.now()
        
        const result = await router.callTool({
          name: 'consensus',
          arguments: {
            prompt: benchmark.prompt,
            models: benchmark.models,
            enable_cross_feedback: benchmark.crossFeedback,
            temperature: 0.1
          }
        })

        const duration = Date.now() - startTime

        expect(result.isError).toBe(false)
        expect(duration).toBeLessThan(benchmark.maxTime)

        const consensusData = JSON.parse(result.content[0].text)
        expect(consensusData.models_consulted).toBe(benchmark.models.length)

        logger.info(`[performance-consensus-test] ${benchmark.name}: ${duration}ms (limit: ${benchmark.maxTime}ms)`)
      }
    }, 300000) // 5 minute timeout for all benchmarks
  })
})
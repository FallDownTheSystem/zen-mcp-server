import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest'
import { createRouter } from '../../src/router.js'
import { loadConfig } from '../../src/config.js'
import { logger } from '../../src/utils/logger.js'

describe('MCP Server Integration Tests', () => {
  let config
  let router

  beforeAll(async () => {
    // Load configuration for integration testing
    config = await loadConfig()
    
    // Create router with dependencies (without server parameter)
    router = await createRouter(config)
    
    logger.info('[integration-test] MCP Server integration test setup completed')
  })

  afterAll(async () => {
    // Cleanup any resources
    logger.info('[integration-test] MCP Server integration test cleanup completed')
  })

  describe('Router Integration', () => {
    it('should handle tools/list request', async () => {
      const result = await router.listTools()
      
      expect(result).toBeDefined()
      expect(result.tools).toBeDefined()
      expect(Array.isArray(result.tools)).toBe(true)
      
      // Should have both chat and consensus tools
      const toolNames = result.tools.map(tool => tool.name)
      expect(toolNames).toContain('chat')
      expect(toolNames).toContain('consensus')
      
      // Each tool should have proper structure
      result.tools.forEach(tool => {
        expect(tool).toHaveProperty('name')
        expect(tool).toHaveProperty('description')
        expect(tool).toHaveProperty('inputSchema')
        expect(tool.inputSchema).toHaveProperty('type')
        expect(tool.inputSchema).toHaveProperty('properties')
      })
    })

    it('should validate tool arguments properly', async () => {
      const validationTests = [
        {
          toolName: 'chat',
          args: { prompt: 'Hello' },
          shouldPass: true
        },
        {
          toolName: 'chat', 
          args: { }, // Missing required prompt
          shouldPass: false
        },
        {
          toolName: 'consensus',
          args: { 
            prompt: 'Test question',
            models: [{ model: 'flash' }]
          },
          shouldPass: true
        },
        {
          toolName: 'consensus',
          args: { prompt: 'Test' }, // Missing models array
          shouldPass: false
        },
        {
          toolName: 'nonexistent',
          args: { prompt: 'Test' },
          shouldPass: false
        }
      ]

      for (const test of validationTests) {
        try {
          const result = await router.callTool({
            name: test.toolName,
            arguments: test.args
          })
          
          if (test.shouldPass) {
            // Tool might fail due to API keys, but validation should pass
            expect(result).toBeDefined()
            expect(result.content).toBeDefined()
          } else {
            // Should not reach here for invalid args
            expect(true).toBe(false) // Force fail
          }
        } catch (error) {
          if (test.shouldPass) {
            // If it should pass but throws, check if it's an API/provider error (acceptable)
            expect(error.message).toMatch(/(API key|provider|configuration)/i)
          } else {
            // Should throw for invalid arguments
            expect(error).toBeDefined()
          }
        }
      }
    })

    it('should have proper error handling for invalid requests', async () => {
      // Test invalid tool name
      const invalidToolResult = await router.callTool({
        name: 'invalid-tool',
        arguments: { prompt: 'test' }
      })
      
      expect(invalidToolResult.isError).toBe(true)
      expect(invalidToolResult.error.type).toBe('RouterError')
      expect(invalidToolResult.error.code).toBe('TOOL_NOT_FOUND')
    })
  })

  describe('Provider Availability', () => {
    it('should report provider availability based on configuration', async () => {
      const { getAvailableProviders } = await import('../../src/providers/index.js')
      const availableProviders = getAvailableProviders(config)
      
      expect(Array.isArray(availableProviders)).toBe(true)
      
      // Should have providers based on API keys
      const providerNames = availableProviders.map(p => p.name)
      if (config.apiKeys.openai) {
        expect(providerNames).toContain('openai')
      }
      if (config.apiKeys.xai) {
        expect(providerNames).toContain('xai')
      }
      if (config.apiKeys.google) {
        expect(providerNames).toContain('google')
      }
    })

    it('should validate provider interfaces', async () => {
      const { getProviders } = await import('../../src/providers/index.js')
      const providers = getProviders()
      
      for (const [name, provider] of Object.entries(providers)) {
        expect(typeof provider.invoke).toBe('function')
        expect(typeof provider.validateConfig).toBe('function')
        expect(typeof provider.isAvailable).toBe('function')
        expect(typeof provider.getSupportedModels).toBe('function')
        expect(typeof provider.getModelConfig).toBe('function')
        
        logger.debug(`[integration-test] Provider ${name} has valid interface`)
      }
    })
  })

  describe('Configuration Integration', () => {
    it('should load configuration successfully', async () => {
      expect(config).toBeDefined()
      expect(config.server).toBeDefined()
      expect(config.apiKeys).toBeDefined()
      expect(config.providers).toBeDefined()
      expect(config.mcp).toBeDefined()
      
      // Should have proper types
      expect(typeof config.server.port).toBe('number')
      expect(typeof config.server.nodeEnv).toBe('string')
      expect(typeof config.server.logLevel).toBe('string')
    })

    it('should have proper MCP client configuration', async () => {
      const mcpConfig = config.getMcpClientConfig()
      
      expect(mcpConfig).toBeDefined()
      expect(mcpConfig.name).toBe('converse-mcp-server')
      expect(mcpConfig.version).toBe('1.0.0')
    })
  })

  describe('Context Processing Integration', () => {
    it('should process file context correctly', async () => {
      const { processFileContent } = await import('../../src/utils/contextProcessor.js')
      
      // Test with package.json file 
      try {
        const result = await processFileContent('package.json')
        
        expect(result).toBeDefined()
        expect(result.success).toBe(true)
        expect(result.content).toBeDefined()
        expect(result.metadata).toBeDefined()
        expect(result.metadata.fileName).toBe('package.json')
        expect(result.metadata.fileType).toBe('json')
        
        logger.debug('[integration-test] Context processing working correctly')
      } catch (error) {
        // File might not exist in test context, that's okay
        expect(error.code).toMatch(/(ENOENT|FILE_NOT_FOUND)/)
      }
    })

    it('should handle invalid file paths gracefully', async () => {
      const { processFileContent } = await import('../../src/utils/contextProcessor.js')
      
      try {
        await processFileContent('/nonexistent/file.txt')
        expect(true).toBe(false) // Should not reach here
      } catch (error) {
        expect(error).toBeDefined()
        expect(error.code).toMatch(/(ENOENT|FILE_NOT_FOUND|PATH_VALIDATION_FAILED)/)
      }
    })
  })

  describe('Continuation Store Integration', () => {
    it('should store and retrieve conversation state', async () => {
      const { getContinuationStore } = await import('../../src/continuationStore.js')
      const store = getContinuationStore()
      
      // Test basic store operations
      const testConversation = {
        messages: [
          { role: 'user', content: 'Hello' },
          { role: 'assistant', content: 'Hi there!' }
        ],
        provider: 'openai',
        model: 'gpt-4o-mini'
      }
      
      const conversationId = await store.set(testConversation)
      expect(conversationId).toBeDefined()
      expect(conversationId.startsWith('conv_')).toBe(true)
      
      const retrieved = await store.get(conversationId)
      expect(retrieved).toBeDefined()
      expect(retrieved.state.messages).toEqual(testConversation.messages)
      expect(retrieved.state.provider).toBe('openai')
      
      // Test deletion
      await store.delete(conversationId)
      const deletedResult = await store.get(conversationId)
      expect(deletedResult).toBeNull()
      
      logger.debug('[integration-test] Continuation store working correctly')
    })

    it('should provide store statistics', async () => {
      const { getContinuationStore } = await import('../../src/continuationStore.js')
      const store = getContinuationStore()
      
      const stats = await store.getStats()
      expect(stats).toBeDefined()
      expect(typeof stats.totalConversations).toBe('number')
      expect(typeof stats.memoryUsageBytes).toBe('number')
      expect(stats.backend).toBe('memory')
    })
  })

  describe('Error Handling Integration', () => {
    it('should handle provider errors gracefully', async () => {
      // Test chat tool with invalid configuration
      const invalidConfig = {
        ...config,
        apiKeys: {
          openai: null,
          xai: null,
          google: null
        }
      }
      
      const invalidRouter = await createRouter(invalidConfig)
      
      const result = await invalidRouter.callTool({
        name: 'chat',
        arguments: { prompt: 'Hello' }
      })
      
      expect(result.isError).toBe(true)
      expect(result.error).toBeDefined()
      expect(result.error.message).toMatch(/(API key|provider|not available)/i)
    })

    it('should create proper error responses', async () => {
      const { createErrorResponse } = await import('../../src/utils/errorHandler.js')
      
      const error = new Error('Test error')
      const response = createErrorResponse(error, 'test-context')
      
      expect(response.content).toBeDefined()
      expect(response.isError).toBe(true)
      expect(response.error).toBeDefined()
      expect(response.error.message).toBe('Test error')
      expect(response.error.context).toBe('test-context')
    })
  })

  describe('Performance Integration', () => {
    it('should have reasonable response times', async () => {
      const startTime = Date.now()
      
      // Test tools/list performance
      await router.listTools()
      const listToolsTime = Date.now() - startTime
      
      expect(listToolsTime).toBeLessThan(100) // Should be very fast
      
      logger.debug(`[integration-test] listTools took ${listToolsTime}ms`)
    })

    it('should handle multiple concurrent requests', async () => {
      const requests = []
      const concurrency = 5
      
      for (let i = 0; i < concurrency; i++) {
        requests.push(router.listTools())
      }
      
      const results = await Promise.all(requests)
      
      // All requests should succeed
      expect(results).toHaveLength(concurrency)
      results.forEach(result => {
        expect(result.tools).toBeDefined()
        expect(Array.isArray(result.tools)).toBe(true)
      })
      
      logger.debug(`[integration-test] Handled ${concurrency} concurrent requests successfully`)
    })
  })
})
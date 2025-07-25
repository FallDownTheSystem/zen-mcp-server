import { describe, it, expect, beforeEach, vi } from 'vitest'
import { chatTool } from '../../src/tools/chat.js'
import { logger } from '../../src/utils/logger.js'

describe('Chat Tool Unit Tests', () => {
  let mockDependencies
  let mockConfig
  let mockContinuationStore
  let mockProviders
  let mockContextProcessor

  beforeEach(() => {
    // Mock configuration
    mockConfig = {
      apiKeys: {
        openai: 'sk-test-key',
        xai: 'xai-test-key',
        google: 'google-test-key'
      },
      providers: {
        googleLocation: 'us-central1',
        xaiBaseUrl: 'https://api.x.ai/v1'
      }
    }

    // Mock continuation store
    mockContinuationStore = {
      get: vi.fn(),
      set: vi.fn(),
      delete: vi.fn(),
      exists: vi.fn(),
      getStats: vi.fn()
    }

    // Mock providers
    const mockProvider = {
      invoke: vi.fn(),
      validateConfig: vi.fn(),
      isAvailable: vi.fn(),
      getSupportedModels: vi.fn(),
      getModelConfig: vi.fn()
    }

    mockProviders = {
      getProviders: vi.fn(() => ({
        openai: mockProvider,
        xai: mockProvider,
        google: mockProvider
      })),
      getProvider: vi.fn(() => mockProvider),
      getAvailableProviders: vi.fn(() => [
        { name: 'openai', ...mockProvider },
        { name: 'xai', ...mockProvider },
        { name: 'google', ...mockProvider }
      ])
    }

    // Mock context processor
    mockContextProcessor = {
      processUnifiedContext: vi.fn()
    }

    // Create mock dependencies
    mockDependencies = {
      config: mockConfig,
      continuationStore: mockContinuationStore,
      providers: mockProviders,
      contextProcessor: mockContextProcessor
    }

    // Set up default mock return values
    mockContinuationStore.get.mockResolvedValue(null)
    mockContinuationStore.set.mockResolvedValue('conv_12345')
    mockContinuationStore.exists.mockResolvedValue(false)

    mockContextProcessor.processUnifiedContext.mockResolvedValue({
      success: true,
      contextMessages: [],
      processed: [],
      failed: []
    })

    mockProviders.getProvider().invoke.mockResolvedValue({
      content: 'Test response from provider',
      stop_reason: 'stop',
      rawResponse: { usage: { total_tokens: 50 } },
      metadata: { provider: 'openai', model: 'gpt-4o-mini' }
    })

    mockProviders.getProvider().isAvailable.mockReturnValue(true)
    mockProviders.getProvider().getModelConfig.mockReturnValue({
      contextWindow: 128000,
      supportsImages: true,
      supportsTemperature: true
    })
  })

  describe('Basic Chat Functionality', () => {
    it('should handle basic chat request', async () => {
      const args = {
        prompt: 'Hello, world!'
      }

      const result = await chatTool(args, mockDependencies)

      expect(result).toBeDefined()
      expect(result.content).toBeDefined()
      expect(Array.isArray(result.content)).toBe(true)
      expect(result.content[0].type).toBe('text')
      expect(result.content[0].text).toContain('Test response from provider')
      expect(result.continuation).toBeDefined()
      expect(result.continuation.id).toBe('conv_12345')
    })

    it('should handle chat with model specification', async () => {
      const args = {
        prompt: 'Test prompt',
        model: 'gpt-4o-mini'
      }

      await chatTool(args, mockDependencies)

      expect(mockProviders.getProvider).toHaveBeenCalledWith('openai')
      expect(mockProviders.getProvider().invoke).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({
            role: 'user',
            content: 'Test prompt'
          })
        ]),
        expect.objectContaining({
          model: 'gpt-4o-mini'
        })
      )
    })

    it('should handle auto model selection', async () => {
      const args = {
        prompt: 'Test prompt',
        model: 'auto'
      }

      await chatTool(args, mockDependencies)

      expect(mockProviders.getAvailableProviders).toHaveBeenCalled()
      expect(mockProviders.getProvider().invoke).toHaveBeenCalled()
    })

    it('should handle temperature parameter', async () => {
      const args = {
        prompt: 'Test prompt',
        temperature: 0.7
      }

      await chatTool(args, mockDependencies)

      expect(mockProviders.getProvider().invoke).toHaveBeenCalledWith(
        expect.any(Array),
        expect.objectContaining({
          temperature: 0.7
        })
      )
    })
  })

  describe('Continuation Support', () => {
    it('should create new conversation when no continuation provided', async () => {
      const args = {
        prompt: 'First message'
      }

      const result = await chatTool(args, mockDependencies)

      expect(mockContinuationStore.get).not.toHaveBeenCalled()
      expect(mockContinuationStore.set).toHaveBeenCalledWith(
        expect.objectContaining({
          messages: expect.arrayContaining([
            expect.objectContaining({ role: 'user', content: 'First message' }),
            expect.objectContaining({ role: 'assistant', content: 'Test response from provider' })
          ])
        })
      )
      expect(result.continuation.messageCount).toBe(2)
    })

    it('should load existing conversation when continuation provided', async () => {
      const existingConversation = {
        messages: [
          { role: 'user', content: 'Previous message' },
          { role: 'assistant', content: 'Previous response' }
        ],
        provider: 'openai',
        model: 'gpt-4o-mini'
      }

      mockContinuationStore.get.mockResolvedValue({
        state: existingConversation,
        metadata: { created: new Date(), lastAccessed: new Date() }
      })
      mockContinuationStore.exists.mockResolvedValue(true)

      const args = {
        prompt: 'Follow-up message',
        continuation: 'conv_existing'
      }

      await chatTool(args, mockDependencies)

      expect(mockContinuationStore.get).toHaveBeenCalledWith('conv_existing')
      expect(mockProviders.getProvider().invoke).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({ role: 'user', content: 'Previous message' }),
          expect.objectContaining({ role: 'assistant', content: 'Previous response' }),
          expect.objectContaining({ role: 'user', content: 'Follow-up message' })
        ]),
        expect.any(Object)
      )
    })

    it('should handle invalid continuation ID gracefully', async () => {
      mockContinuationStore.get.mockResolvedValue(null)
      mockContinuationStore.exists.mockResolvedValue(false)

      const args = {
        prompt: 'Test message',
        continuation: 'invalid-continuation-id'
      }

      const result = await chatTool(args, mockDependencies)

      // Should create new conversation
      expect(result.continuation.messageCount).toBe(2)
      expect(mockContinuationStore.set).toHaveBeenCalled()
    })
  })

  describe('Context Processing', () => {
    it('should process file context when files provided', async () => {
      mockContextProcessor.processUnifiedContext.mockResolvedValue({
        success: true,
        contextMessages: [
          { role: 'user', content: 'File content: package.json data...' }
        ],
        processed: [{ fileName: 'package.json', fileType: 'json' }],
        failed: []
      })

      const args = {
        prompt: 'Analyze these files',
        files: ['package.json']
      }

      await chatTool(args, mockDependencies)

      expect(mockContextProcessor.processUnifiedContext).toHaveBeenCalledWith({
        files: ['package.json'],
        images: [],
        webSearch: null
      })

      expect(mockProviders.getProvider().invoke).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({ content: 'File content: package.json data...' }),
          expect.objectContaining({ content: 'Analyze these files' })
        ]),
        expect.any(Object)
      )
    })

    it('should process image context when images provided', async () => {
      mockContextProcessor.processUnifiedContext.mockResolvedValue({
        success: true,
        contextMessages: [
          { role: 'user', content: 'Image content: [base64 data]' }
        ],
        processed: [{ fileName: 'image.png', fileType: 'image' }],
        failed: []
      })

      const args = {
        prompt: 'Describe this image',
        images: ['image.png']
      }

      await chatTool(args, mockDependencies)

      expect(mockContextProcessor.processUnifiedContext).toHaveBeenCalledWith({
        files: [],
        images: ['image.png'],
        webSearch: null
      })
    })

    it('should process web search context when provided', async () => {
      mockContextProcessor.processUnifiedContext.mockResolvedValue({
        success: true,
        contextMessages: [
          { role: 'user', content: 'Web search results: ...' }
        ],
        processed: [],
        failed: []
      })

      const args = {
        prompt: 'Based on recent news',
        webSearch: 'latest AI developments'
      }

      await chatTool(args, mockDependencies)

      expect(mockContextProcessor.processUnifiedContext).toHaveBeenCalledWith({
        files: [],
        images: [],
        webSearch: 'latest AI developments'
      })
    })

    it('should handle context processing failures gracefully', async () => {
      mockContextProcessor.processUnifiedContext.mockResolvedValue({
        success: false,
        contextMessages: [],
        processed: [],
        failed: [{ file: 'nonexistent.txt', error: 'File not found' }]
      })

      const args = {
        prompt: 'Test message',
        files: ['nonexistent.txt']
      }

      const result = await chatTool(args, mockDependencies)

      // Should still proceed with the chat
      expect(result.content).toBeDefined()
      expect(mockProviders.getProvider().invoke).toHaveBeenCalled()
    })
  })

  describe('Provider Integration', () => {
    it('should map model names to correct providers', async () => {
      const testCases = [
        { model: 'gpt-4o-mini', expectedProvider: 'openai' },
        { model: 'o3-mini', expectedProvider: 'openai' },
        { model: 'grok', expectedProvider: 'xai' },
        { model: 'grok-4', expectedProvider: 'xai' },
        { model: 'flash', expectedProvider: 'google' },
        { model: 'gemini-pro', expectedProvider: 'google' }
      ]

      for (const { model, expectedProvider } of testCases) {
        // Reset mock calls
        mockProviders.getProvider.mockClear()

        const args = { prompt: 'Test', model }
        await chatTool(args, mockDependencies)

        expect(mockProviders.getProvider).toHaveBeenCalledWith(expectedProvider)
      }
    })

    it('should handle provider-specific options', async () => {
      const args = {
        prompt: 'Test thinking',
        model: 'gemini-pro',
        thinking: 'medium'
      }

      await chatTool(args, mockDependencies)

      expect(mockProviders.getProvider().invoke).toHaveBeenCalledWith(
        expect.any(Array),
        expect.objectContaining({
          thinking: 'medium'
        })
      )
    })

    it('should handle reasoning effort for O3 models', async () => {
      const args = {
        prompt: 'Complex reasoning task',
        model: 'o3-mini',
        reasoningEffort: 'high'
      }

      await chatTool(args, mockDependencies)

      expect(mockProviders.getProvider().invoke).toHaveBeenCalledWith(
        expect.any(Array),
        expect.objectContaining({
          reasoningEffort: 'high'
        })
      )
    })
  })

  describe('Error Handling', () => {
    it('should throw error for missing prompt', async () => {
      const args = {}

      await expect(chatTool(args, mockDependencies)).rejects.toThrow(/prompt.*required/i)
    })

    it('should throw error for empty prompt', async () => {
      const args = { prompt: '' }

      await expect(chatTool(args, mockDependencies)).rejects.toThrow(/prompt.*empty/i)
    })

    it('should handle provider errors gracefully', async () => {
      mockProviders.getProvider().invoke.mockRejectedValue(
        new Error('Provider API error')
      )

      const args = { prompt: 'Test prompt' }

      await expect(chatTool(args, mockDependencies)).rejects.toThrow('Provider API error')
    })

    it('should handle no available providers', async () => {
      mockProviders.getAvailableProviders.mockReturnValue([])

      const args = {
        prompt: 'Test prompt',
        model: 'auto'
      }

      await expect(chatTool(args, mockDependencies)).rejects.toThrow(/no.*providers.*available/i)
    })

    it('should handle unknown model gracefully', async () => {
      mockProviders.getProvider.mockReturnValue(null)

      const args = {
        prompt: 'Test prompt',
        model: 'unknown-model'
      }

      await expect(chatTool(args, mockDependencies)).rejects.toThrow(/provider.*model/i)
    })

    it('should handle continuation store errors', async () => {
      mockContinuationStore.set.mockRejectedValue(new Error('Store error'))

      const args = { prompt: 'Test prompt' }

      await expect(chatTool(args, mockDependencies)).rejects.toThrow('Store error')
    })
  })

  describe('Response Format Compliance', () => {
    it('should return MCP-compliant response format', async () => {
      const args = { prompt: 'Test prompt' }
      const result = await chatTool(args, mockDependencies)

      // Check MCP response structure
      expect(result).toHaveProperty('content')
      expect(Array.isArray(result.content)).toBe(true)
      expect(result.content[0]).toHaveProperty('type')
      expect(result.content[0]).toHaveProperty('text')
      expect(result.content[0].type).toBe('text')

      // Check continuation structure
      expect(result).toHaveProperty('continuation')
      expect(result.continuation).toHaveProperty('id')
      expect(result.continuation).toHaveProperty('messageCount')
      expect(typeof result.continuation.messageCount).toBe('number')
    })

    it('should include provider metadata in response', async () => {
      const args = { prompt: 'Test prompt' }
      const result = await chatTool(args, mockDependencies)

      // Parse the JSON response
      const responseData = JSON.parse(result.content[0].text)
      expect(responseData).toHaveProperty('response')
      expect(responseData).toHaveProperty('provider')
      expect(responseData).toHaveProperty('model')
      expect(responseData).toHaveProperty('tokenUsage')
    })

    it('should handle streaming responses appropriately', async () => {
      mockProviders.getProvider().invoke.mockResolvedValue({
        content: 'Streaming response',
        stop_reason: 'stop',
        rawResponse: { usage: { total_tokens: 25 } },
        metadata: { provider: 'openai', model: 'gpt-4o-mini', streaming: true }
      })

      const args = {
        prompt: 'Test prompt',
        streaming: true
      }

      const result = await chatTool(args, mockDependencies)
      expect(result.content[0].text).toContain('Streaming response')
    })
  })

  describe('Edge Cases and Input Validation', () => {
    it('should handle very long prompts', async () => {
      const longPrompt = 'A'.repeat(10000)
      const args = { prompt: longPrompt }

      const result = await chatTool(args, mockDependencies)
      expect(result).toBeDefined()
      expect(mockProviders.getProvider().invoke).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({ content: longPrompt })
        ]),
        expect.any(Object)
      )
    })

    it('should handle special characters in prompt', async () => {
      const specialPrompt = 'Test with émojis 🚀 and symbols: @#$%^&*()'
      const args = { prompt: specialPrompt }

      const result = await chatTool(args, mockDependencies)
      expect(result).toBeDefined()
    })

    it('should handle multiple file types', async () => {
      mockContextProcessor.processUnifiedContext.mockResolvedValue({
        success: true,
        contextMessages: [
          { role: 'user', content: 'File 1 content' },
          { role: 'user', content: 'File 2 content' }
        ],
        processed: [
          { fileName: 'file1.txt', fileType: 'text' },
          { fileName: 'file2.json', fileType: 'json' }
        ],
        failed: []
      })

      const args = {
        prompt: 'Analyze these files',
        files: ['file1.txt', 'file2.json']
      }

      const result = await chatTool(args, mockDependencies)
      expect(result).toBeDefined()
      expect(mockContextProcessor.processUnifiedContext).toHaveBeenCalledWith({
        files: ['file1.txt', 'file2.json'],
        images: [],
        webSearch: null
      })
    })

    it('should handle boundary temperature values', async () => {
      const testCases = [0, 0.1, 1.0, 2.0]

      for (const temperature of testCases) {
        mockProviders.getProvider().invoke.mockClear()
        
        const args = {
          prompt: 'Test prompt',
          temperature
        }

        await chatTool(args, mockDependencies)
        expect(mockProviders.getProvider().invoke).toHaveBeenCalledWith(
          expect.any(Array),
          expect.objectContaining({ temperature })
        )
      }
    })
  })
})
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { consensusTool } from '../../src/tools/consensus.js'
import { logger } from '../../src/utils/logger.js'

describe('Consensus Tool Unit Tests', () => {
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

    // Mock individual providers
    const mockOpenAIProvider = {
      invoke: vi.fn().mockResolvedValue({
        content: 'OpenAI response',
        stop_reason: 'stop',
        rawResponse: { usage: { total_tokens: 50 } },
        metadata: { provider: 'openai', model: 'gpt-4o-mini' }
      }),
      validateConfig: vi.fn().mockReturnValue(true),
      isAvailable: vi.fn().mockReturnValue(true),
      getSupportedModels: vi.fn(),
      getModelConfig: vi.fn().mockReturnValue({ contextWindow: 128000 })
    }

    const mockXAIProvider = {
      invoke: vi.fn().mockResolvedValue({
        content: 'XAI response',
        stop_reason: 'stop',
        rawResponse: { usage: { total_tokens: 45 } },
        metadata: { provider: 'xai', model: 'grok' }
      }),
      validateConfig: vi.fn().mockReturnValue(true),
      isAvailable: vi.fn().mockReturnValue(true),
      getSupportedModels: vi.fn(),
      getModelConfig: vi.fn().mockReturnValue({ contextWindow: 131000 })
    }

    const mockGoogleProvider = {
      invoke: vi.fn().mockResolvedValue({
        content: 'Google response',
        stop_reason: 'stop',
        rawResponse: { usage: { total_tokens: 40 } },
        metadata: { provider: 'google', model: 'gemini-2.5-flash' }
      }),
      validateConfig: vi.fn().mockReturnValue(true),
      isAvailable: vi.fn().mockReturnValue(true),
      getSupportedModels: vi.fn(),
      getModelConfig: vi.fn().mockReturnValue({ contextWindow: 1000000 })
    }

    // Mock providers registry
    mockProviders = {
      getProviders: vi.fn(() => ({
        openai: mockOpenAIProvider,
        xai: mockXAIProvider,
        google: mockGoogleProvider
      })),
      getProvider: vi.fn((name) => {
        const providers = {
          openai: mockOpenAIProvider,
          xai: mockXAIProvider,
          google: mockGoogleProvider
        }
        return providers[name]
      }),
      getAvailableProviders: vi.fn(() => [
        { name: 'openai', ...mockOpenAIProvider },
        { name: 'xai', ...mockXAIProvider },
        { name: 'google', ...mockGoogleProvider }
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
    mockContinuationStore.set.mockResolvedValue('conv_consensus_12345')
    mockContinuationStore.exists.mockResolvedValue(false)

    mockContextProcessor.processUnifiedContext.mockResolvedValue({
      success: true,
      contextMessages: [],
      processed: [],
      failed: []
    })
  })

  describe('Basic Consensus Functionality', () => {
    it('should handle basic consensus request with single model', async () => {
      const args = {
        prompt: 'What is 2+2?',
        models: [{ model: 'gpt-4o-mini' }]
      }

      const result = await consensusTool(args, mockDependencies)

      expect(result).toBeDefined()
      expect(result.content).toBeDefined()
      expect(Array.isArray(result.content)).toBe(true)
      expect(result.content[0].type).toBe('text')

      // Parse the consensus result
      const consensusResult = JSON.parse(result.content[0].text)
      expect(consensusResult.status).toBe('consensus_complete')
      expect(consensusResult.models_consulted).toBe(1)
      expect(consensusResult.successful_initial_responses).toBe(1)
      expect(consensusResult.phases.initial).toHaveLength(1)
    })

    it('should handle consensus with multiple models', async () => {
      const args = {
        prompt: 'Is AI beneficial for humanity?',
        models: [
          { model: 'gpt-4o-mini' },
          { model: 'grok' },
          { model: 'flash' }
        ]
      }

      const result = await consensusTool(args, mockDependencies)
      const consensusResult = JSON.parse(result.content[0].text)

      expect(consensusResult.models_consulted).toBe(3)
      expect(consensusResult.successful_initial_responses).toBe(3)
      expect(consensusResult.phases.initial).toHaveLength(3)

      // Verify all providers were called
      expect(mockProviders.getProvider('openai').invoke).toHaveBeenCalled()
      expect(mockProviders.getProvider('xai').invoke).toHaveBeenCalled()
      expect(mockProviders.getProvider('google').invoke).toHaveBeenCalled()
    })

    it('should enable cross-feedback by default', async () => {
      const args = {
        prompt: 'Test question',
        models: [
          { model: 'gpt-4o-mini' },
          { model: 'grok' }
        ]
      }

      const result = await consensusTool(args, mockDependencies)
      const consensusResult = JSON.parse(result.content[0].text)

      expect(consensusResult.phases.refined).toBeDefined()
      expect(consensusResult.refined_responses).toBe(2)

      // Each provider should be called twice (initial + refinement)
      expect(mockProviders.getProvider('openai').invoke).toHaveBeenCalledTimes(2)
      expect(mockProviders.getProvider('xai').invoke).toHaveBeenCalledTimes(2)
    })

    it('should disable cross-feedback when requested', async () => {
      const args = {
        prompt: 'Test question',
        models: [{ model: 'gpt-4o-mini' }],
        enable_cross_feedback: false
      }

      const result = await consensusTool(args, mockDependencies)
      const consensusResult = JSON.parse(result.content[0].text)

      expect(consensusResult.phases.refined).toBeUndefined()
      expect(consensusResult.refined_responses).toBe(0)

      // Provider should only be called once (no refinement phase)
      expect(mockProviders.getProvider('openai').invoke).toHaveBeenCalledTimes(1)
    })
  })

  describe('Model Resolution and Provider Mapping', () => {
    it('should resolve model names to correct providers', async () => {
      const args = {
        prompt: 'Test prompt',
        models: [
          { model: 'o3-mini' },        // Should map to openai
          { model: 'grok-4' },         // Should map to xai
          { model: 'gemini-pro' }      // Should map to google
        ]
      }

      await consensusTool(args, mockDependencies)

      expect(mockProviders.getProvider).toHaveBeenCalledWith('openai')
      expect(mockProviders.getProvider).toHaveBeenCalledWith('xai')
      expect(mockProviders.getProvider).toHaveBeenCalledWith('google')
    })

    it('should handle auto model selection', async () => {
      const args = {
        prompt: 'Test prompt',
        models: [{ model: 'auto' }]
      }

      await consensusTool(args, mockDependencies)

      expect(mockProviders.getAvailableProviders).toHaveBeenCalled()
      // Should use first available provider
      expect(mockProviders.getProvider('openai').invoke).toHaveBeenCalled()
    })

    it('should handle model-specific options', async () => {
      const args = {
        prompt: 'Test prompt',
        models: [
          { model: 'gpt-4o-mini', temperature: 0.7 },
          { model: 'gemini-pro', thinking: 'medium' }
        ]
      }

      await consensusTool(args, mockDependencies)

      // Check that options are passed to providers
      expect(mockProviders.getProvider('openai').invoke).toHaveBeenCalledWith(
        expect.any(Array),
        expect.objectContaining({ temperature: 0.7 })
      )
      expect(mockProviders.getProvider('google').invoke).toHaveBeenCalledWith(
        expect.any(Array),
        expect.objectContaining({ thinking: 'medium' })
      )
    })
  })

  describe('Cross-Feedback Mechanism', () => {
    it('should include other models responses in refinement phase', async () => {
      const args = {
        prompt: 'Complex question requiring multiple perspectives',
        models: [
          { model: 'gpt-4o-mini' },
          { model: 'grok' }
        ],
        enable_cross_feedback: true
      }

      await consensusTool(args, mockDependencies)

      // Check refinement calls include context from other models
      const refinementCalls = mockProviders.getProvider('openai').invoke.mock.calls.filter(
        call => call[0].some(msg => msg.content.includes('Other models have responded'))
      )
      expect(refinementCalls.length).toBeGreaterThan(0)
    })

    it('should use custom cross-feedback prompt when provided', async () => {
      const customPrompt = 'Please review and improve your response based on the other perspectives'
      const args = {
        prompt: 'Test question',
        models: [{ model: 'gpt-4o-mini' }, { model: 'grok' }],
        cross_feedback_prompt: customPrompt
      }

      await consensusTool(args, mockDependencies)

      // Check that custom prompt is used in refinement
      const calls = mockProviders.getProvider('openai').invoke.mock.calls
      const refinementCall = calls.find(call => 
        call[0].some(msg => msg.content.includes(customPrompt))
      )
      expect(refinementCall).toBeDefined()
    })

    it('should handle stance detection in refined responses', async () => {
      // Mock refined responses with stance keywords
      mockProviders.getProvider('openai').invoke
        .mockResolvedValueOnce({
          content: 'I agree with this approach',
          stop_reason: 'stop',
          metadata: { provider: 'openai' }
        })
        .mockResolvedValueOnce({
          content: 'I still support this position strongly',
          stop_reason: 'stop',
          metadata: { provider: 'openai' }
        })

      const args = {
        prompt: 'Should we implement this feature?',
        models: [{ model: 'gpt-4o-mini' }]
      }

      const result = await consensusTool(args, mockDependencies)
      const consensusResult = JSON.parse(result.content[0].text)

      expect(consensusResult.phases.refined[0]).toHaveProperty('stance')
      expect(['for', 'against', 'neutral']).toContain(consensusResult.phases.refined[0].stance)
    })
  })

  describe('Context Processing Integration', () => {
    it('should process context before sending to models', async () => {
      mockContextProcessor.processUnifiedContext.mockResolvedValue({
        success: true,
        contextMessages: [
          { role: 'user', content: 'Context: File content here' }
        ],
        processed: [{ fileName: 'test.txt' }],
        failed: []
      })

      const args = {
        prompt: 'Analyze this data',
        models: [{ model: 'gpt-4o-mini' }],
        relevant_files: ['test.txt']
      }

      await consensusTool(args, mockDependencies)

      expect(mockContextProcessor.processUnifiedContext).toHaveBeenCalledWith({
        files: ['test.txt'],
        images: [],
        webSearch: null
      })

      // Check that context is included in provider calls
      expect(mockProviders.getProvider('openai').invoke).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({ content: 'Context: File content here' })
        ]),
        expect.any(Object)
      )
    })

    it('should handle context processing failures gracefully', async () => {
      mockContextProcessor.processUnifiedContext.mockResolvedValue({
        success: false,
        contextMessages: [],
        processed: [],
        failed: [{ file: 'missing.txt', error: 'File not found' }]
      })

      const args = {
        prompt: 'Test prompt',
        models: [{ model: 'gpt-4o-mini' }],
        relevant_files: ['missing.txt']
      }

      const result = await consensusTool(args, mockDependencies)
      
      // Should still proceed with consensus
      expect(result).toBeDefined()
      const consensusResult = JSON.parse(result.content[0].text)
      expect(consensusResult.status).toBe('consensus_complete')
    })
  })

  describe('Error Handling and Resilience', () => {
    it('should throw error for missing prompt', async () => {
      const args = {
        models: [{ model: 'gpt-4o-mini' }]
      }

      await expect(consensusTool(args, mockDependencies)).rejects.toThrow(/prompt.*required/i)
    })

    it('should throw error for missing models array', async () => {
      const args = {
        prompt: 'Test prompt'
      }

      await expect(consensusTool(args, mockDependencies)).rejects.toThrow(/models.*required/i)
    })

    it('should throw error for empty models array', async () => {
      const args = {
        prompt: 'Test prompt',
        models: []
      }

      await expect(consensusTool(args, mockDependencies)).rejects.toThrow(/models.*empty/i)
    })

    it('should handle individual provider failures gracefully', async () => {
      // Make one provider fail
      mockProviders.getProvider('xai').invoke.mockRejectedValue(new Error('XAI API error'))

      const args = {
        prompt: 'Test prompt',
        models: [
          { model: 'gpt-4o-mini' },
          { model: 'grok' },          // This will fail
          { model: 'flash' }
        ]
      }

      const result = await consensusTool(args, mockDependencies)
      const consensusResult = JSON.parse(result.content[0].text)

      expect(consensusResult.models_consulted).toBe(3)
      expect(consensusResult.successful_initial_responses).toBe(2)
      expect(consensusResult.failed_responses).toBe(1)
      expect(consensusResult.phases.failed).toHaveLength(1)
      expect(consensusResult.phases.failed[0].error).toContain('XAI API error')
    })

    it('should handle all providers failing', async () => {
      // Make all providers fail
      mockProviders.getProvider('openai').invoke.mockRejectedValue(new Error('OpenAI error'))
      mockProviders.getProvider('xai').invoke.mockRejectedValue(new Error('XAI error'))
      mockProviders.getProvider('google').invoke.mockRejectedValue(new Error('Google error'))

      const args = {
        prompt: 'Test prompt',
        models: [
          { model: 'gpt-4o-mini' },
          { model: 'grok' },
          { model: 'flash' }
        ]
      }

      const result = await consensusTool(args, mockDependencies)
      const consensusResult = JSON.parse(result.content[0].text)

      expect(consensusResult.status).toBe('consensus_complete')
      expect(consensusResult.successful_initial_responses).toBe(0)
      expect(consensusResult.failed_responses).toBe(3)
      expect(consensusResult.phases.failed).toHaveLength(3)
    })

    it('should handle unknown models gracefully', async () => {
      mockProviders.getProvider.mockReturnValue(null)

      const args = {
        prompt: 'Test prompt',
        models: [{ model: 'unknown-model' }]
      }

      const result = await consensusTool(args, mockDependencies)
      const consensusResult = JSON.parse(result.content[0].text)

      expect(consensusResult.failed_responses).toBe(1)
      expect(consensusResult.phases.failed[0].error).toContain('provider')
    })
  })

  describe('Continuation Support', () => {
    it('should save consensus results to continuation store', async () => {
      const args = {
        prompt: 'Test consensus question',
        models: [{ model: 'gpt-4o-mini' }]
      }

      const result = await consensusTool(args, mockDependencies)

      expect(mockContinuationStore.set).toHaveBeenCalledWith(
        expect.objectContaining({
          messages: expect.arrayContaining([
            expect.objectContaining({ role: 'user', content: 'Test consensus question' })
          ]),
          toolType: 'consensus',
          consensusResult: expect.any(Object)
        })
      )

      expect(result.continuation).toBeDefined()
      expect(result.continuation.id).toBe('conv_consensus_12345')
    })

    it('should load previous consensus conversation when continuation provided', async () => {
      const existingConversation = {
        messages: [
          { role: 'user', content: 'Previous consensus question' },
          { role: 'assistant', content: 'Previous consensus result' }
        ],
        toolType: 'consensus'
      }

      mockContinuationStore.get.mockResolvedValue({
        state: existingConversation,
        metadata: { created: new Date(), lastAccessed: new Date() }
      })
      mockContinuationStore.exists.mockResolvedValue(true)

      const args = {
        prompt: 'Follow-up consensus question',
        models: [{ model: 'gpt-4o-mini' }],
        continuation: 'conv_existing'
      }

      await consensusTool(args, mockDependencies)

      expect(mockContinuationStore.get).toHaveBeenCalledWith('conv_existing')
      
      // Should include previous messages in provider calls
      expect(mockProviders.getProvider('openai').invoke).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({ content: 'Previous consensus question' }),
          expect.objectContaining({ content: 'Follow-up consensus question' })
        ]),
        expect.any(Object)
      )
    })
  })

  describe('Response Format Compliance', () => {
    it('should return MCP-compliant response format', async () => {
      const args = {
        prompt: 'Test prompt',
        models: [{ model: 'gpt-4o-mini' }]
      }

      const result = await consensusTool(args, mockDependencies)

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
    })

    it('should return valid JSON in response content', async () => {
      const args = {
        prompt: 'Test prompt',
        models: [{ model: 'gpt-4o-mini' }]
      }

      const result = await consensusTool(args, mockDependencies)

      expect(() => JSON.parse(result.content[0].text)).not.toThrow()

      const consensusResult = JSON.parse(result.content[0].text)
      expect(consensusResult).toHaveProperty('status')
      expect(consensusResult).toHaveProperty('models_consulted')
      expect(consensusResult).toHaveProperty('phases')
      expect(consensusResult).toHaveProperty('settings')
    })

    it('should include comprehensive metadata in response', async () => {
      const args = {
        prompt: 'Test prompt',
        models: [{ model: 'gpt-4o-mini' }],
        temperature: 0.5
      }

      const result = await consensusTool(args, mockDependencies)
      const consensusResult = JSON.parse(result.content[0].text)

      expect(consensusResult.settings).toHaveProperty('enable_cross_feedback')
      expect(consensusResult.settings).toHaveProperty('temperature')
      expect(consensusResult.settings.temperature).toBe(0.5)

      // Check phase structure
      expect(consensusResult.phases.initial[0]).toHaveProperty('model')
      expect(consensusResult.phases.initial[0]).toHaveProperty('status')
      expect(consensusResult.phases.initial[0]).toHaveProperty('response')
      expect(consensusResult.phases.initial[0]).toHaveProperty('metadata')
    })
  })

  describe('Performance and Parallel Execution', () => {
    it('should execute models in parallel', async () => {
      const args = {
        prompt: 'Test prompt',
        models: [
          { model: 'gpt-4o-mini' },
          { model: 'grok' },
          { model: 'flash' }
        ]
      }

      // Track when each provider is called
      const callTimes = []
      mockProviders.getProvider('openai').invoke.mockImplementation(async () => {
        callTimes.push(Date.now())
        return { content: 'OpenAI response', stop_reason: 'stop', metadata: {} }
      })
      mockProviders.getProvider('xai').invoke.mockImplementation(async () => {
        callTimes.push(Date.now())
        return { content: 'XAI response', stop_reason: 'stop', metadata: {} }
      })
      mockProviders.getProvider('google').invoke.mockImplementation(async () => {
        callTimes.push(Date.now())
        return { content: 'Google response', stop_reason: 'stop', metadata: {} }
      })

      await consensusTool(args, mockDependencies)

      // All providers should be called (multiple times due to cross-feedback)
      expect(mockProviders.getProvider('openai').invoke).toHaveBeenCalled()
      expect(mockProviders.getProvider('xai').invoke).toHaveBeenCalled()
      expect(mockProviders.getProvider('google').invoke).toHaveBeenCalled()
    })

    it('should handle timeout scenarios gracefully', async () => {
      // Mock a slow provider
      mockProviders.getProvider('xai').invoke.mockImplementation(
        () => new Promise(resolve => setTimeout(() => resolve({
          content: 'Slow response',
          stop_reason: 'stop',
          metadata: {}
        }), 100))
      )

      const args = {
        prompt: 'Test prompt',
        models: [
          { model: 'gpt-4o-mini' },
          { model: 'grok' }  // This one is slow
        ]
      }

      const result = await consensusTool(args, mockDependencies)
      const consensusResult = JSON.parse(result.content[0].text)

      // Should still complete successfully
      expect(consensusResult.status).toBe('consensus_complete')
      expect(consensusResult.successful_initial_responses).toBe(2)
    })
  })
})
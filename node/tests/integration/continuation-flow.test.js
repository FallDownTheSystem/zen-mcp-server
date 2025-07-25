import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { loadConfig } from '../../src/config.js'
import { createRouter } from '../../src/router.js'
import { getContinuationStore } from '../../src/continuationStore.js'
import { logger } from '../../src/utils/logger.js'

describe('Continuation Flow Integration Tests', () => {
  let config
  let router
  let continuationStore

  beforeAll(async () => {
    try {
      // Load configuration
      config = await loadConfig()
      
      // Create router
      router = await createRouter(config)
      
      // Get continuation store
      continuationStore = getContinuationStore()
      
      logger.info('[continuation-flow-test] Continuation flow test setup completed')
    } catch (error) {
      logger.error('[continuation-flow-test] Setup failed:', error)
      throw error
    }
  })

  afterAll(async () => {
    // Cleanup all test conversations
    try {
      await continuationStore.cleanup(0) // Remove all conversations
      logger.info('[continuation-flow-test] Continuation flow test cleanup completed')
    } catch (error) {
      logger.error('[continuation-flow-test] Cleanup failed:', error)
    }
  })

  describe('Single Conversation Flow', () => {
    it('should create and maintain conversation across multiple requests', async () => {
      // First message - start conversation
      const firstResponse = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Remember this number: 42. Just acknowledge that you remember it.'
        }
      })

      expect(firstResponse.continuation).toBeDefined()
      const conversationId = firstResponse.continuation.id
      expect(conversationId.startsWith('conv_')).toBe(true)
      expect(firstResponse.continuation.messageCount).toBe(2) // user + assistant

      // Second message - test memory
      const secondResponse = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'What number did I ask you to remember?',
          continuation: conversationId
        }
      })

      expect(secondResponse.continuation.id).toBe(conversationId)
      expect(secondResponse.continuation.messageCount).toBe(4) // +2 more messages
      
      // Response should reference the number (though we can't test exact content without real API)
      expect(secondResponse.content).toBeDefined()
      expect(secondResponse.content[0].type).toBe('text')

      // Third message - continue conversation
      const thirdResponse = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Now add 8 to that number and tell me the result.',
          continuation: conversationId
        }
      })

      expect(thirdResponse.continuation.id).toBe(conversationId)
      expect(thirdResponse.continuation.messageCount).toBe(6) // +2 more messages
    })

    it('should handle conversation persistence across router instances', async () => {
      // Start conversation with one router instance
      const firstResponse = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Start a persistent conversation test'
        }
      })

      const conversationId = firstResponse.continuation.id

      // Create a new router instance (simulating server restart)
      const newRouter = await createRouter(config)

      // Continue conversation with new router instance
      const secondResponse = await newRouter.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Continue the conversation after restart',
          continuation: conversationId
        }
      })

      expect(secondResponse.continuation.id).toBe(conversationId)
      expect(secondResponse.continuation.messageCount).toBeGreaterThan(2)
    })
  })

  describe('Multiple Concurrent Conversations', () => {
    it('should handle multiple independent conversations simultaneously', async () => {
      const conversations = []
      const numConversations = 3

      // Start multiple conversations
      for (let i = 0; i < numConversations; i++) {
        const response = await router.callTool({
          name: 'chat',
          arguments: {
            prompt: `Start conversation ${i + 1} with identifier: CONV${i + 1}`
          }
        })

        conversations.push({
          id: response.continuation.id,
          identifier: `CONV${i + 1}`,
          messageCount: response.continuation.messageCount
        })
      }

      // Verify all conversations have unique IDs
      const conversationIds = conversations.map(c => c.id)
      const uniqueIds = new Set(conversationIds)
      expect(uniqueIds.size).toBe(numConversations)

      // Continue each conversation independently
      for (let i = 0; i < numConversations; i++) {
        const response = await router.callTool({
          name: 'chat',
          arguments: {
            prompt: `Continue conversation with identifier ${conversations[i].identifier}`,
            continuation: conversations[i].id
          }
        })

        expect(response.continuation.id).toBe(conversations[i].id)
        expect(response.continuation.messageCount).toBeGreaterThan(conversations[i].messageCount)
        
        // Update message count
        conversations[i].messageCount = response.continuation.messageCount
      }

      // Verify conversations remained independent
      for (let i = 0; i < numConversations; i++) {
        const state = await continuationStore.get(conversations[i].id)
        expect(state).toBeDefined()
        expect(state.state.messages.length).toBe(conversations[i].messageCount)
      }
    })

    it('should handle concurrent access to same conversation', async () => {
      // Start a conversation
      const initialResponse = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Start concurrent access test'
        }
      })

      const conversationId = initialResponse.continuation.id
      const concurrentRequests = 3
      const requests = []

      // Make multiple concurrent requests to same conversation
      for (let i = 0; i < concurrentRequests; i++) {
        requests.push(
          router.callTool({
            name: 'chat',
            arguments: {
              prompt: `Concurrent message ${i + 1}`,
              continuation: conversationId
            }
          })
        )
      }

      const responses = await Promise.allSettled(requests)
      
      // At least some should succeed (depending on implementation)
      const successful = responses.filter(r => r.status === 'fulfilled')
      expect(successful.length).toBeGreaterThan(0)

      // All successful responses should maintain the conversation ID
      successful.forEach(response => {
        expect(response.value.continuation.id).toBe(conversationId)
      })
    })
  })

  describe('Consensus Tool Continuation', () => {
    it('should maintain consensus conversation history', async () => {
      // Start consensus conversation
      const firstResponse = await router.callTool({
        name: 'consensus',
        arguments: {
          prompt: 'What is the capital of France? Keep it brief.',
          models: [{ model: 'auto' }],
          enable_cross_feedback: false
        }
      })

      expect(firstResponse.continuation).toBeDefined()
      const conversationId = firstResponse.continuation.id

      // Continue consensus conversation
      const secondResponse = await router.callTool({
        name: 'consensus',
        arguments: {
          prompt: 'What is the population of that city approximately?',
          models: [{ model: 'auto' }],
          continuation: conversationId,
          enable_cross_feedback: false
        }
      })

      expect(secondResponse.continuation.id).toBe(conversationId)
      expect(secondResponse.continuation.messageCount).toBeGreaterThan(firstResponse.continuation.messageCount)

      // Verify conversation state includes consensus history
      const state = await continuationStore.get(conversationId)
      expect(state).toBeDefined()
      expect(state.state.messages.length).toBeGreaterThan(2)
    })

    it('should handle mixed tool conversations', async () => {
      // Start with chat
      const chatResponse = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Start a mixed tool conversation'
        }
      })

      const conversationId = chatResponse.continuation.id

      // Continue with consensus
      const consensusResponse = await router.callTool({
        name: 'consensus',
        arguments: {
          prompt: 'Continue with consensus tool',
          models: [{ model: 'auto' }],
          continuation: conversationId,
          enable_cross_feedback: false
        }
      })

      expect(consensusResponse.continuation.id).toBe(conversationId)

      // Continue back with chat
      const finalChatResponse = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Final chat message',
          continuation: conversationId
        }
      })

      expect(finalChatResponse.continuation.id).toBe(conversationId)
      expect(finalChatResponse.continuation.messageCount).toBeGreaterThan(consensusResponse.continuation.messageCount)
    })
  })

  describe('Error Handling in Continuation Flow', () => {
    it('should handle invalid continuation IDs gracefully', async () => {
      const response = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Test with invalid continuation',
          continuation: 'invalid-continuation-id'
        }
      })

      // Should create new conversation instead of failing
      expect(response.continuation).toBeDefined()
      expect(response.continuation.id).not.toBe('invalid-continuation-id')
      expect(response.continuation.messageCount).toBe(2) // New conversation
    })

    it('should handle corrupted conversation state', async () => {
      // Create a valid conversation
      const initialResponse = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Test conversation for corruption'
        }
      })

      const conversationId = initialResponse.continuation.id

      // Manually corrupt the conversation state
      await continuationStore.set({ 
        invalidData: 'corrupted',
        messages: 'not-an-array'
      }, conversationId.replace('conv_', ''))

      // Try to continue the conversation
      const response = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Continue corrupted conversation',
          continuation: conversationId
        }
      })

      // Should handle gracefully (either fix or start new)
      expect(response.continuation).toBeDefined()
      expect(response.content).toBeDefined()
    })

    it('should handle provider errors during continuation', async () => {
      // Start conversation
      const initialResponse = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Start conversation for error test'
        }
      })

      const conversationId = initialResponse.continuation.id

      // Try to continue with invalid model
      const response = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Continue with error',
          continuation: conversationId,
          model: 'nonexistent-model'
        }
      })

      // Should maintain conversation ID even if provider fails
      if (response.isError) {
        // Error response should still maintain conversation metadata
        expect(response.error).toBeDefined()
      } else {
        // Or should succeed with fallback
        expect(response.continuation.id).toBe(conversationId)
      }
    })
  })

  describe('Continuation Store Management', () => {
    it('should provide accurate conversation statistics', async () => {
      const initialStats = await continuationStore.getStats()
      const initialCount = initialStats.totalConversations

      // Create some conversations
      const numNewConversations = 3
      const conversationIds = []

      for (let i = 0; i < numNewConversations; i++) {
        const response = await router.callTool({
          name: 'chat',
          arguments: {
            prompt: `Stats test conversation ${i + 1}`
          }
        })
        conversationIds.push(response.continuation.id)
      }

      const newStats = await continuationStore.getStats()
      expect(newStats.totalConversations).toBe(initialCount + numNewConversations)

      // Cleanup conversations
      for (const id of conversationIds) {
        await continuationStore.delete(id)
      }

      const finalStats = await continuationStore.getStats()
      expect(finalStats.totalConversations).toBe(initialCount)
    })

    it('should handle conversation cleanup correctly', async () => {
      // Create a conversation
      const response = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Cleanup test conversation'
        }
      })

      const conversationId = response.continuation.id

      // Verify it exists
      const state = await continuationStore.get(conversationId)
      expect(state).toBeDefined()

      // Delete it
      await continuationStore.delete(conversationId)

      // Verify it's gone
      const deletedState = await continuationStore.get(conversationId)
      expect(deletedState).toBeNull()
    })

    it('should handle bulk cleanup operations', async () => {
      // Create multiple conversations
      const conversationIds = []
      for (let i = 0; i < 5; i++) {
        const response = await router.callTool({
          name: 'chat',
          arguments: {
            prompt: `Bulk cleanup test ${i + 1}`
          }
        })
        conversationIds.push(response.continuation.id)
      }

      // Verify they exist
      for (const id of conversationIds) {
        const state = await continuationStore.get(id)
        expect(state).toBeDefined()
      }

      // Cleanup all old conversations (0ms = all)
      await continuationStore.cleanup(0)

      // Verify they're gone
      for (const id of conversationIds) {
        const state = await continuationStore.get(id)
        expect(state).toBeNull()
      }
    })
  })

  describe('Continuation Flow Performance', () => {
    it('should maintain reasonable performance with long conversations', async () => {
      // Start conversation
      let response = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Start performance test conversation'
        }
      })

      const conversationId = response.continuation.id
      const numMessages = 10

      // Add many messages to the conversation
      for (let i = 0; i < numMessages; i++) {
        const startTime = Date.now()
        
        response = await router.callTool({
          name: 'chat',
          arguments: {
            prompt: `Performance test message ${i + 1}`,
            continuation: conversationId
          }
        })

        const duration = Date.now() - startTime
        
        // Each message should process reasonably quickly
        expect(duration).toBeLessThan(10000) // 10 seconds max
        expect(response.continuation.id).toBe(conversationId)
      }

      // Final message count should be correct
      expect(response.continuation.messageCount).toBe((numMessages + 1) * 2) // +1 initial, *2 for user/assistant pairs
    })

    it('should handle rapid continuation requests', async () => {
      // Start conversation
      const initialResponse = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Rapid requests test'
        }
      })

      const conversationId = initialResponse.continuation.id
      const rapidRequests = []

      // Make rapid sequential requests
      for (let i = 0; i < 5; i++) {
        rapidRequests.push(
          router.callTool({
            name: 'chat',
            arguments: {
              prompt: `Rapid message ${i + 1}`,
              continuation: conversationId
            }
          })
        )
      }

      const responses = await Promise.allSettled(rapidRequests)
      
      // At least some should succeed
      const successful = responses.filter(r => r.status === 'fulfilled')
      expect(successful.length).toBeGreaterThan(0)

      // All successful responses should maintain conversation ID
      successful.forEach(response => {
        expect(response.value.continuation.id).toBe(conversationId)
      })
    })
  })

  describe('Real-World Continuation Scenarios', () => {
    it('should handle conversation interruption and resumption', async () => {
      // Start conversation
      const startResponse = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Start a conversation about artificial intelligence'
        }
      })

      const conversationId = startResponse.continuation.id

      // Continue for a few messages
      const continueResponse = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Tell me about machine learning specifically',
          continuation: conversationId
        }
      })

      expect(continueResponse.continuation.id).toBe(conversationId)

      // Simulate interruption (time delay or server restart)
      // In real scenario, there might be a delay here
      
      // Resume conversation
      const resumeResponse = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Actually, let me ask about neural networks instead',
          continuation: conversationId
        }
      })

      expect(resumeResponse.continuation.id).toBe(conversationId)
      expect(resumeResponse.continuation.messageCount).toBeGreaterThan(continueResponse.continuation.messageCount)
    })

    it('should handle conversation branching scenario', async () => {
      // Start base conversation
      const baseResponse = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Start base conversation for branching test'
        }
      })

      const baseId = baseResponse.continuation.id

      // Continue base conversation
      const continueBase = await router.callTool({
        name: 'chat',
        arguments: {
          prompt: 'Continue base conversation',
          continuation: baseId
        }
      })

      // Branch to consensus tool from same base
      const branchConsensus = await router.callTool({
        name: 'consensus',
        arguments: {
          prompt: 'Branch to consensus tool',
          models: [{ model: 'auto' }],
          continuation: baseId,
          enable_cross_feedback: false
        }
      })

      // Both should maintain the same conversation ID
      expect(continueBase.continuation.id).toBe(baseId)
      expect(branchConsensus.continuation.id).toBe(baseId)

      // Message counts should reflect the branching
      expect(branchConsensus.continuation.messageCount).toBeGreaterThan(continueBase.continuation.messageCount)
    })
  })
})
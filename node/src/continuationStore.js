/**
 * Continuation Store - State Management
 *
 * Manages conversation history and state for persistent conversations.
 * Pluggable implementation that can be swapped for different storage backends.
 */

/**
 * In-memory continuation store implementation
 * This is a simple implementation - can be replaced with Redis, database, etc.
 */
class MemoryContinuationStore {
  constructor() {
    this.conversations = new Map();
    this.maxConversations = 1000; // Prevent memory leaks
    this.maxMessagesPerConversation = 100;
  }

  /**
   * Store a conversation state
   * @param {string} continuationId - Unique continuation identifier
   * @param {object} state - Conversation state to store
   */
  async store(continuationId, state) {
    // Cleanup old conversations if we hit the limit
    if (this.conversations.size >= this.maxConversations) {
      const oldestKey = this.conversations.keys().next().value;
      this.conversations.delete(oldestKey);
    }

    // Limit messages per conversation
    if (state.messages && state.messages.length > this.maxMessagesPerConversation) {
      state.messages = state.messages.slice(-this.maxMessagesPerConversation);
    }

    this.conversations.set(continuationId, {
      ...state,
      lastAccessed: Date.now(),
    });
  }

  /**
   * Retrieve a conversation state
   * @param {string} continuationId - Unique continuation identifier
   * @returns {object|null} Conversation state or null if not found
   */
  async retrieve(continuationId) {
    const state = this.conversations.get(continuationId);
    if (state) {
      // Update last accessed time
      state.lastAccessed = Date.now();
      return state;
    }
    return null;
  }

  /**
   * Delete a conversation state
   * @param {string} continuationId - Unique continuation identifier
   */
  async delete(continuationId) {
    this.conversations.delete(continuationId);
  }

  /**
   * Get conversation statistics
   * @returns {object} Store statistics
   */
  getStats() {
    return {
      totalConversations: this.conversations.size,
      maxConversations: this.maxConversations,
      maxMessagesPerConversation: this.maxMessagesPerConversation,
    };
  }

  /**
   * Clean up old conversations (can be called periodically)
   * @param {number} maxAgeMs - Maximum age in milliseconds
   */
  cleanup(maxAgeMs = 24 * 60 * 60 * 1000) { // Default: 24 hours
    const now = Date.now();
    for (const [id, state] of this.conversations.entries()) {
      if (now - state.lastAccessed > maxAgeMs) {
        this.conversations.delete(id);
      }
    }
  }
}

// Singleton instance
let continuationStore = null;

/**
 * Get the continuation store instance
 * @returns {object} Continuation store instance
 */
export function getContinuationStore() {
  if (!continuationStore) {
    continuationStore = new MemoryContinuationStore();

    // Set up periodic cleanup
    setInterval(() => {
      continuationStore.cleanup();
    }, 60 * 60 * 1000); // Cleanup every hour
  }
  return continuationStore;
}

/**
 * Create a new continuation ID
 * @returns {string} Unique continuation ID
 */
export function generateContinuationId() {
  return `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Helper function to add a message to conversation history
 * @param {object} state - Current conversation state
 * @param {object} message - Message to add
 * @returns {object} Updated state
 */
export function addMessageToHistory(state, message) {
  const messages = state.messages || [];
  return {
    ...state,
    messages: [...messages, message],
    lastUpdated: Date.now(),
  };
}

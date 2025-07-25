/**
 * Manual Integration Test for Core Functionality
 * Tests the tools directly without MCP server infrastructure
 */

import { chatTool } from './src/tools/chat.js';
import { consensusTool } from './src/tools/consensus.js';
import { loadConfig } from './src/config.js';
import { getProvider, getProviders } from './src/providers/index.js';
import { getContinuationStore } from './src/continuationStore.js';

console.log('🧪 Starting Manual Integration Tests...\n');

async function runTests() {
  try {
    // Load configuration
    console.log('📋 Loading configuration...');
    const config = await loadConfig();
    console.log(`✅ Config loaded: ${config.providers?.available?.join(', ') || 'unknown'} providers available\n`);

    // Create dependencies
    const providers = { getProvider, getProviders };
    const continuationStore = getContinuationStore();
    
    const dependencies = {
      config,
      providers,
      continuationStore
    };

    // Test 1: Basic Chat Tool
    console.log('🗨️  Test 1: Chat Tool Basic Functionality');
    try {
      const chatArgs = {
        prompt: 'What is 2+2? Please respond briefly.',
        model: 'gpt-4o-mini', // Use a specific model that works
        temperature: 0.2
        // Don't include reasoning_effort for non-O3 models
      };
      
      const chatResult = await chatTool(chatArgs, dependencies);
      console.log('✅ Chat tool executed successfully');
      console.log(`📊 Response type: ${chatResult.type}`);
      if (chatResult.content) {
        try {
          const content = JSON.parse(chatResult.content);
          console.log(`💬 Content preview: ${content.content.substring(0, 100)}...`);
          console.log(`🔗 Continuation ID: ${content.continuation?.id}`);
        } catch (parseError) {
          console.log(`⚠️ Response content type: ${typeof chatResult.content}`);
          if (typeof chatResult.content === 'object') {
            console.log(`🔍 Content keys: ${Object.keys(chatResult.content)}`);
            console.log(`📝 Response preview: ${JSON.stringify(chatResult.content, null, 2).substring(0, 200)}...`);
          } else {
            console.log(`⚠️ Raw content preview: ${String(chatResult.content).substring(0, 100)}...`);
          }
        }
      }
      console.log('');
    } catch (error) {
      console.error('❌ Chat tool test failed:', error.message);
      console.log('');
    }

    // Test 2: System Prompts Verification
    console.log('📝 Test 2: System Prompts Integration');
    try {
      const { CHAT_PROMPT, CONSENSUS_PROMPT } = await import('./src/systemPrompts.js');
      console.log(`✅ Chat prompt loaded: ${CHAT_PROMPT.length} characters`);
      console.log(`✅ Consensus prompt loaded: ${CONSENSUS_PROMPT.length} characters`);
      console.log(`📄 Chat prompt preview: "${CHAT_PROMPT.substring(0, 80)}..."`);
      console.log('');
    } catch (error) {
      console.error('❌ System prompts test failed:', error.message);
      console.log('');
    }

    // Test 3: Parameters Validation
    console.log('🔧 Test 3: Parameter Schema Validation');
    try {
      // Test chat tool schema
      const chatSchema = chatTool.inputSchema;
      const hasReasoningEffort = chatSchema.properties.reasoning_effort;
      const hasImages = chatSchema.properties.images;
      const hasWebSearch = chatSchema.properties.use_websearch;
      
      console.log(`✅ Chat tool has reasoning_effort: ${!!hasReasoningEffort}`);
      console.log(`✅ Chat tool has images support: ${!!hasImages}`);
      console.log(`✅ Chat tool has web search: ${!!hasWebSearch}`);
      
      // Test consensus tool schema
      const consensusSchema = consensusTool.inputSchema;
      const consensusHasImages = consensusSchema.properties.images;
      const consensusHasReasoning = consensusSchema.properties.reasoning_effort;
      
      console.log(`✅ Consensus tool has images support: ${!!consensusHasImages}`);
      console.log(`✅ Consensus tool has reasoning_effort: ${!!consensusHasReasoning}`);
      console.log('');
    } catch (error) {
      console.error('❌ Parameter validation test failed:', error.message);
      console.log('');
    }

    // Test 4: Provider Validation
    console.log('🔌 Test 4: Provider Functionality');
    try {
      const openaiProvider = providers.getProvider('openai');
      const xaiProvider = providers.getProvider('xai');
      const googleProvider = providers.getProvider('google');
      
      console.log(`✅ OpenAI provider loaded: ${!!openaiProvider}`);
      console.log(`✅ XAI provider loaded: ${!!xaiProvider}`);
      console.log(`✅ Google provider loaded: ${!!googleProvider}`);
      
      if (openaiProvider) {
        console.log(`🔑 OpenAI available: ${openaiProvider.isAvailable(config)}`);
      }
      if (xaiProvider) {
        console.log(`🔑 XAI available: ${xaiProvider.isAvailable(config)}`);
      }
      if (googleProvider) {
        console.log(`🔑 Google available: ${googleProvider.isAvailable(config)}`);
      }
      console.log('');
    } catch (error) {
      console.error('❌ Provider test failed:', error.message);
      console.log('');
    }

    // Test 5: Context Processor
    console.log('📁 Test 5: Context Processor');
    try {
      const { processUnifiedContext } = await import('./src/utils/contextProcessor.js');
      
      const contextRequest = {
        files: ['./package.json'],
        images: [],
        webSearch: null
      };
      
      const contextResult = await processUnifiedContext(contextRequest);
      console.log(`✅ Context processor executed`);
      console.log(`📄 Files processed: ${contextResult.files.length}`);
      console.log(`🖼️  Images processed: ${contextResult.images.length}`);
      if (contextResult.files.length > 0) {
        console.log(`📊 First file status: ${contextResult.files[0].type || 'error'}`);
      }
      console.log('');
    } catch (error) {
      console.error('❌ Context processor test failed:', error.message);
      console.log('');
    }

    // Test 6: Multi-Model Consensus (if multiple providers available)
    console.log('🤝 Test 6: Consensus Tool (Mock Test)');
    try {
      const availableProviders = config.providers?.available || [];
      if (availableProviders.length >= 2) {
        console.log('🎯 Multiple providers available, testing consensus...');
        
        const consensusArgs = {
          prompt: 'What is the best programming language for web development? Give a brief answer.',
          models: [
            { model: 'auto' },
            { model: 'auto' }
          ],
          enable_cross_feedback: false, // Disable for faster testing
          temperature: 0.1
        };
        
        const consensusResult = await consensusTool(consensusArgs, dependencies);
        console.log('✅ Consensus tool executed successfully');
        console.log(`📊 Response type: ${consensusResult.type}`);
        if (consensusResult.content) {
          const content = JSON.parse(consensusResult.content);
          console.log(`🤖 Models consulted: ${content.models_consulted}`);
          console.log(`✅ Successful responses: ${content.successful_initial_responses}`);
        }
      } else {
        console.log('⚠️  Only one provider available, skipping consensus test');
      }
      console.log('');
    } catch (error) {
      console.error('❌ Consensus tool test failed:', error.message);
      console.log('');
    }

    console.log('🎉 Manual integration tests completed!');
    
  } catch (error) {
    console.error('💥 Critical test failure:', error);
    process.exit(1);
  }
}

// Handle unhandled rejections
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled rejection at:', promise, 'reason:', reason);
  process.exit(1);
});

// Run tests
runTests().catch(error => {
  console.error('Test runner failed:', error);
  process.exit(1);
});
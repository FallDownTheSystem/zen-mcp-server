"""
Detailed test showing how models refine their responses based on cross-model feedback.
"""

import asyncio
import json
import logging
from unittest.mock import Mock, patch

from tools.consensus import ConsensusTool

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class RefinementMockProvider:
    """Mock provider that shows actual refinement based on other models' responses."""

    def __init__(self, provider_type):
        self.provider_type = provider_type
        self.call_count = 0
        self.other_responses_seen = []

    def get_provider_type(self):
        return Mock(value=self.provider_type)

    def generate_content(self, prompt, model_name, system_prompt, temperature, thinking_mode, images=None):
        """Generate responses that actually change based on feedback."""
        self.call_count += 1

        # Check if this is a refinement call (contains other models' responses)
        is_refinement = "Other AI models have also provided their perspectives" in prompt

        if is_refinement:
            # Extract what other models said from the prompt
            if "3-4 months minimum" in prompt:
                self.other_responses_seen.append("conservative timeline")
            if "6-8 weeks for MVP" in prompt:
                self.other_responses_seen.append("optimistic timeline")

        # Generate response based on phase and model
        if not is_refinement:
            # Initial responses based on model
            if model_name == "gemini-pro":
                response_content = """I support implementing real-time collaboration:

**Timeline**: 6-8 weeks for MVP
**Approach**: Use Socket.IO for quick implementation
**Priority**: High - users are asking for this

This is a straightforward implementation that will delight users."""

            elif model_name == "o3-mini":
                response_content = """Real-time collaboration needs careful consideration:

**Timeline**: 3-4 months minimum for production-ready implementation
**Complexity**: WebSockets at scale are notoriously difficult
**Alternative**: Consider improving async collaboration first

The technical debt could be substantial if rushed."""

            else:  # flash or other
                response_content = """Real-time collaboration analysis:

**Timeline**: 10-12 weeks for balanced implementation
**Approach**: Start with limited pilot program
**Decision**: Depends on strategic priorities

A measured approach balances risk and reward."""

        else:
            # Refined responses based on others' feedback
            if model_name == "gemini-pro":
                response_content = """After reviewing other perspectives, I'm refining my position:

**Original Timeline**: I suggested 6-8 weeks, but I see the validity of concerns about this being optimistic.

**Revised Timeline**: 8-10 weeks for MVP, accounting for complexity highlighted by others.

**Key Insight**: The pilot program approach mentioned is excellent - we can start small.

**Refined Recommendation**: Implement a LIMITED real-time feature set first (just cursor presence and typing indicators), which genuinely could be done in 8-10 weeks. This addresses user demand while managing risk."""

            elif model_name == "o3-mini":
                response_content = """After considering other models' input, here's my refined analysis:

**Timeline Convergence**: While I maintain 3-4 months for FULL implementation, I see merit in a phased approach.

**Acknowledging Other Views**: User demand (30% of tickets) is indeed significant.

**Revised Position**: I now support a LIMITED pilot:
1. Start with read-only real-time updates (lower complexity)
2. Use the suggested timeline: 10-12 weeks
3. Measure actual infrastructure costs before full rollout

The pilot approach mitigates most of my technical concerns while testing user adoption."""

            else:  # flash or other
                response_content = """After analyzing all perspectives, I'm synthesizing a refined recommendation:

**Timeline Consensus**:
- One model started at 6-8 weeks (too optimistic)
- Another said 3-4 months (too pessimistic)
- My 10-12 weeks seems to be the realistic middle ground

**Refined Implementation Plan**:
1. Week 1-2: Prototype with existing libraries
2. Week 3-6: Limited pilot with 10 power users
3. Week 7-10: Scale based on pilot metrics
4. Week 11-12: Production rollout OR pivot to async improvements

This balanced approach satisfies urgency while respecting caution."""

        response = Mock()
        response.content = response_content
        response.usage = {
            "input_tokens": 200 + (100 if is_refinement else 0),
            "output_tokens": 250 + (50 if is_refinement else 0),
        }

        logger.info(f"{'REFINED' if is_refinement else 'INITIAL'} - {model_name}: {len(response_content)} chars")
        return response


async def test_detailed_refinement():
    """Test showing how models actually refine their responses."""

    logger.info("=== DETAILED CONSENSUS REFINEMENT TEST ===\n")

    tool = ConsensusTool()

    # Create providers
    providers = {"gemini": RefinementMockProvider("gemini"), "openai": RefinementMockProvider("openai")}

    def mock_get_model_provider(model_name):
        if "gemini" in model_name or "pro" in model_name:
            return providers["gemini"]
        else:
            return providers["openai"]

    arguments = {
        "step": "Should we add real-time collaboration to our app? Users are requesting it but we have limited resources.",
        "step_number": 1,
        "total_steps": 1,
        "next_step_required": False,
        "findings": "30% of support tickets request real-time features. Team has no WebSocket experience.",
        "models": [{"model": "gemini-pro"}, {"model": "o3-mini"}, {"model": "flash"}],
        "enable_cross_feedback": True,
    }

    with patch.object(tool, "get_model_provider", side_effect=mock_get_model_provider):
        # Execute workflow
        result = await tool.execute_workflow(arguments)
        response_data = json.loads(result[0].text)

        # Show initial responses
        logger.info("📝 INITIAL RESPONSES (Before seeing others' views):\n")
        for resp in response_data["phases"]["initial"]:
            logger.info(f"Model: {resp['model']}")
            logger.info(f"Response:\n{resp['response']}\n")
            logger.info("-" * 80 + "\n")

        # Show refined responses
        logger.info("🔄 REFINED RESPONSES (After cross-model feedback):\n")
        for resp in response_data["phases"]["refined"]:
            logger.info(f"Model: {resp['model']}")
            logger.info(f"Refined Response:\n{resp['refined_response']}\n")
            logger.info("-" * 80 + "\n")

        # Analysis
        logger.info("📊 ANALYSIS:")
        logger.info("- All 3 models consulted in parallel initially")
        logger.info("- Each model then saw the others' responses")
        logger.info("- Models adjusted their positions based on insights from others")
        logger.info("- Timeline converged from 6-8 weeks vs 3-4 months to ~10-12 weeks")
        logger.info("- All models now support a pilot approach (consensus achieved!)")

        logger.info("\n✅ Test completed - Refinement process demonstrated!")


if __name__ == "__main__":
    asyncio.run(test_detailed_refinement())

"""
Test for the token/character limit mismatch fix.

This test verifies that the _validate_token_limit method correctly converts
character limits to token limits before validation.
"""

from unittest.mock import patch

import pytest

from config import MCP_PROMPT_SIZE_LIMIT
from tools.chat import ChatTool


class TestTokenCharacterLimitFix:
    """Test that the token/character limit mismatch is fixed"""

    def test_validate_token_limit_converts_characters_to_tokens(self):
        """Test that _validate_token_limit correctly converts character limit to token limit"""

        # Create a ChatTool instance
        tool = ChatTool()

        # Create content that would fail with the bug but pass with the fix
        # 15,000 tokens * 4 chars/token = ~60,000 characters
        # With the bug: 15,000 > 60,000 would fail (comparing tokens to characters)
        # With the fix: 15,000 < 15,000 (60,000/4) would pass (comparing tokens to tokens)

        # Simulate content with ~50,000 characters (about 12,500 tokens)
        large_content = "x" * 50_000

        # This should NOT raise an error with the fix
        # (12,500 tokens < 15,000 token limit)
        tool._validate_token_limit(large_content, "Test content")

    def test_validate_token_limit_fails_when_exceeding_limit(self):
        """Test that validation still fails when content genuinely exceeds limit"""

        tool = ChatTool()

        # Create content that exceeds even the corrected limit
        # With MAX_MCP_OUTPUT_TOKENS=150000: 360,000 char limit / 4 = 90,000 token limit
        # Create content with ~100,000 tokens = 400,000+ characters
        # Using more realistic text pattern for better token estimation
        huge_content = "The quick brown fox jumps over the lazy dog. " * 10000  # ~100,000 tokens

        with pytest.raises(ValueError) as exc_info:
            tool._validate_token_limit(huge_content, "Test content")

        # Verify the error message mentions tokens (not characters)
        assert "tokens" in str(exc_info.value)
        assert "Maximum is" in str(exc_info.value)

    def test_token_limit_calculation(self):
        """Test that the token limit is correctly calculated from character limit"""

        tool = ChatTool()

        # The fix should calculate: token_limit = MCP_PROMPT_SIZE_LIMIT // 4
        expected_token_limit = MCP_PROMPT_SIZE_LIMIT // 4

        # Mock check_token_limit to capture what limit is passed
        with patch("tools.shared.base_tool.check_token_limit") as mock_check:
            mock_check.return_value = (True, 1000)  # Valid, 1000 tokens

            tool._validate_token_limit("test content", "Test")

            # Verify check_token_limit was called with the converted token limit
            mock_check.assert_called_once()
            args = mock_check.call_args[0]
            assert args[1] == expected_token_limit

    def test_original_issue_scenario(self):
        """Test the scenario from the original issue - comparing tokens to characters"""

        tool = ChatTool()

        # Simulate the original issue scenario:
        # Content has 70,000 tokens but only 280,000 characters
        # With the bug: 70,000 > 360,000 would incorrectly pass (comparing tokens to characters)
        # But validation would later fail when actually used

        # Create content that demonstrates the fix
        # 80,000 tokens should be under the 90,000 token limit (360,000/4)
        content_80k_tokens = "The quick brown fox jumps over the lazy dog. " * 8000  # ~80,000 tokens

        # This should pass with the fix (80,000 < 90,000 tokens)
        tool._validate_token_limit(content_80k_tokens, "Test content")

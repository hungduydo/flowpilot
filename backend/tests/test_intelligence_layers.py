"""Tests for the 4-layer intelligence pipeline.

Verifies keyword extraction, relevance scoring, context assembly ordering,
token budget enforcement, and RAG/template retrieval — all with mocks (no
real LLM, DB, or ChromaDB calls).
"""

import types

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.context_manager import estimate_tokens
from app.core.conversation_engine import ConversationEngine


# ── Helpers ────────────────────────────────────────────────────


def _make_note(content: str, category: str = "general", is_active: bool = True):
    """Create a mock KnowledgeNote."""
    return types.SimpleNamespace(
        id="note-1",
        content=content,
        category=category,
        is_active=is_active,
    )


def _make_learning(description: str, node_type: str | None, frequency: int):
    """Create a mock LearningRecord."""
    return types.SimpleNamespace(
        id="lr-1",
        record_type="fix",
        node_type=node_type,
        description=description,
        frequency=frequency,
    )


# ── T1: Keyword Extraction ────────────────────────────────────


class TestKeywordExtraction:
    def test_extracts_node_keywords(self):
        keywords = ConversationEngine._extract_keywords(
            "send a Slack message when webhook fires"
        )
        # Should find slack and webhook related keywords
        assert "slack" in keywords
        assert "webhook" in keywords

    def test_excludes_noise_words(self):
        keywords = ConversationEngine._extract_keywords(
            "create a workflow that sends a message"
        )
        # Noise words should be excluded
        assert "a" not in keywords
        assert "create" not in keywords
        assert "that" not in keywords
        assert "workflow" not in keywords

    def test_expands_with_node_types(self):
        keywords = ConversationEngine._extract_keywords("send Slack notification")
        # Should expand to include the full node type
        has_slack_type = any("slack" in kw.lower() for kw in keywords)
        assert has_slack_type

    def test_empty_message(self):
        keywords = ConversationEngine._extract_keywords("")
        assert isinstance(keywords, set)

    def test_mixed_case(self):
        keywords = ConversationEngine._extract_keywords("SLACK Webhook GitHub")
        assert "slack" in keywords
        assert "webhook" in keywords
        assert "github" in keywords


# ── T2: Relevance Scoring ─────────────────────────────────────


class TestRelevanceScoring:
    def test_high_relevance(self):
        score = ConversationEngine._relevance_score(
            "Slack message resource operation send channel",
            {"slack", "message", "send"},
        )
        assert score > 0.5

    def test_zero_relevance(self):
        score = ConversationEngine._relevance_score(
            "GitHub repository stars forks pull requests",
            {"slack", "message", "send"},
        )
        assert score == 0.0

    def test_partial_relevance(self):
        score = ConversationEngine._relevance_score(
            "Send notification via slack",
            {"slack", "email", "telegram", "discord", "teams", "webhook", "http", "api"},
        )
        assert 0.0 < score < 1.0

    def test_empty_keywords(self):
        score = ConversationEngine._relevance_score("any text", set())
        assert score == 0.0

    def test_case_insensitive(self):
        score = ConversationEngine._relevance_score(
            "SLACK MESSAGE SEND",
            {"slack", "message", "send"},
        )
        assert score > 0.5


# ── T3: Knowledge Notes Relevance Ordering ─────────────────────


class TestKnowledgeContextAssembly:
    @pytest.mark.asyncio
    async def test_relevant_notes_first(self):
        """Slack notes should appear before GitHub notes when keywords are Slack-related."""
        notes = [
            _make_note("GitHub: always use n8n-nodes-base.githubTrigger for repo events"),
            _make_note("Slack: use resource=message, operation=send for sending messages"),
            _make_note("GitHub: set owner and repository parameters"),
            _make_note("Slack: always specify channel parameter for Slack nodes"),
            _make_note("Telegram: use sendMessage operation for notifications"),
        ]

        engine = ConversationEngine()
        mock_session = AsyncMock()

        with patch(
            "app.core.conversation_engine.KnowledgeNoteRepository.list_all",
            new_callable=AsyncMock,
            return_value=notes,
        ):
            result = await engine._get_knowledge_context(
                mock_session,
                keywords={"slack", "n8n-nodes-base.slack", "message"},
            )

        # Slack notes should appear before GitHub notes
        slack_pos = result.find("Slack:")
        github_pos = result.find("GitHub:")
        assert slack_pos != -1, "Slack notes should be in output"
        assert github_pos != -1, "GitHub notes should be in output"
        assert slack_pos < github_pos, "Slack notes should appear before GitHub notes"

    @pytest.mark.asyncio
    async def test_empty_notes(self):
        engine = ConversationEngine()
        mock_session = AsyncMock()

        with patch(
            "app.core.conversation_engine.KnowledgeNoteRepository.list_all",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await engine._get_knowledge_context(mock_session, keywords={"slack"})

        assert result == ""


# ── T4: Learning Records Frequency Weighting ───────────────────


class TestLearningContextAssembly:
    @pytest.mark.asyncio
    async def test_high_frequency_first(self):
        """High-frequency Slack records should rank above low-frequency generic records."""
        records = [
            _make_learning("Generic: always validate JSON output", None, 1),
            _make_learning(
                "Slack: use resource=message not webclient",
                "n8n-nodes-base.slack",
                10,
            ),
            _make_learning("Generic: check node connections", None, 2),
        ]

        engine = ConversationEngine()
        mock_session = AsyncMock()

        with patch(
            "app.core.conversation_engine.LearningRepository.get_relevant",
            new_callable=AsyncMock,
            return_value=records,
        ):
            result = await engine._get_learning_context(
                mock_session,
                keywords={"slack", "n8n-nodes-base.slack"},
            )

        # Slack record should appear before generic ones
        slack_pos = result.find("Slack: use resource=message")
        generic_pos = result.find("Generic: always validate")
        assert slack_pos != -1
        assert generic_pos != -1
        assert slack_pos < generic_pos

    @pytest.mark.asyncio
    async def test_empty_records(self):
        engine = ConversationEngine()
        mock_session = AsyncMock()

        with patch(
            "app.core.conversation_engine.LearningRepository.get_relevant",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await engine._get_learning_context(mock_session, keywords={"slack"})

        assert result == ""


# ── T5: Token Budget Enforcement ────────────────────────────────


class TestTokenBudgetEnforcement:
    @pytest.mark.asyncio
    async def test_knowledge_context_within_budget(self):
        """Even with many notes, output should stay under TOKEN_BUDGET_KNOWLEDGE."""
        # Create 50 long notes (~100 tokens each = ~5000 total)
        notes = [
            _make_note(f"Note {i}: " + "word " * 80)
            for i in range(50)
        ]

        engine = ConversationEngine()
        mock_session = AsyncMock()

        with patch(
            "app.core.conversation_engine.KnowledgeNoteRepository.list_all",
            new_callable=AsyncMock,
            return_value=notes,
        ):
            result = await engine._get_knowledge_context(mock_session, keywords=set())

        tokens = estimate_tokens(result)
        assert tokens <= engine.TOKEN_BUDGET_KNOWLEDGE, (
            f"Knowledge context ({tokens} tokens) exceeds budget ({engine.TOKEN_BUDGET_KNOWLEDGE})"
        )

    def test_rag_trim_to_budget(self):
        """_trim_to_budget should respect the token limit."""
        engine = ConversationEngine()
        long_text = "\n\n---\n\n".join([f"Paragraph {i}: " + "content " * 100 for i in range(20)])
        trimmed = engine._trim_to_budget(long_text, 500)
        assert estimate_tokens(trimmed) <= 500


# ── T6: RAG Context Retrieval ───────────────────────────────────


class TestRagContextRetrieval:
    def test_returns_search_results(self):
        engine = ConversationEngine()

        with patch(
            "app.core.conversation_engine.rag_search",
            return_value="## Webhook Pattern\nUse n8n-nodes-base.webhook for HTTP triggers...",
        ):
            result = engine._get_rag_context("webhook slack integration")

        assert result != ""
        assert "Webhook" in result

    def test_handles_search_failure(self):
        engine = ConversationEngine()

        with patch(
            "app.core.conversation_engine.rag_search",
            side_effect=Exception("ChromaDB unavailable"),
        ):
            result = engine._get_rag_context("anything")

        assert result == ""

    def test_handles_empty_results(self):
        engine = ConversationEngine()

        with patch(
            "app.core.conversation_engine.rag_search",
            return_value="",
        ):
            result = engine._get_rag_context("obscure query")

        assert result == ""


# ── T7: Template Context Retrieval ──────────────────────────────


class TestTemplateContextRetrieval:
    def test_returns_with_header(self):
        engine = ConversationEngine()

        with patch(
            "app.core.conversation_engine.rag_search",
            return_value="## Template: Webhook → Slack\nNodes: Webhook, Slack...",
        ):
            result = engine._get_template_context(
                "webhook sends slack message",
                keywords={"slack", "webhook"},
            )

        assert "Reference Templates" in result
        assert "Webhook" in result

    def test_handles_no_templates(self):
        engine = ConversationEngine()

        with patch(
            "app.core.conversation_engine.rag_search",
            return_value="",
        ):
            result = engine._get_template_context("something", keywords=set())

        assert result == ""

    def test_handles_search_failure(self):
        engine = ConversationEngine()

        with patch(
            "app.core.conversation_engine.rag_search",
            side_effect=Exception("ChromaDB down"),
        ):
            result = engine._get_template_context("anything", keywords=set())

        assert result == ""

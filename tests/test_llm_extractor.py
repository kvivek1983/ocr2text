import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.llm.extractor import LLMExtractor


@pytest.mark.asyncio
async def test_extract_rc_book_anthropic():
    """LLM extractor returns structured fields from OCR text."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"registration_number": "MH47BL1775", "owner_name": "SHIVA SAI"}')]
    mock_response.usage.input_tokens = 500
    mock_response.usage.output_tokens = 100

    with patch("app.llm.extractor.anthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        extractor = LLMExtractor(provider="anthropic")
        result = await extractor.extract(
            ocr_text_front="Registration No: MH47BL1775\nOwner: SHIVA SAI",
            ocr_text_back=None,
            document_type="rc_book",
            side="front",
        )

        assert result.status == "success"
        assert result.extracted_fields["registration_number"] == "MH47BL1775"
        assert result.token_input == 500
        assert result.token_output == 100


@pytest.mark.asyncio
async def test_extract_returns_failed_on_api_error():
    with patch("app.llm.extractor.anthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API down"))
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        extractor = LLMExtractor(provider="anthropic")
        result = await extractor.extract(
            ocr_text_front="some text",
            ocr_text_back=None,
            document_type="rc_book",
            side="front",
        )

        assert result.status == "failed"
        assert "API down" in result.error_message

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.govt.client import GovtAPIClient
from app.govt.schemas import GovtVerificationResult


@pytest.mark.asyncio
async def test_client_calls_primary_reseller():
    mock_session = MagicMock()
    reseller = MagicMock()
    reseller.provider_code = "gridlines"
    reseller.circuit_state = "closed"
    reseller.id = "r1"

    fake_result = GovtVerificationResult(
        status="success",
        reseller_code="gridlines",
        normalized_fields={"owner_name": "TEST"},
        raw_response={"data": {}},
        response_time_ms=120,
    )

    with patch.object(GovtAPIClient, "_call_reseller", new_callable=AsyncMock, return_value=fake_result), \
         patch("app.storage.repository.GovtResellerRepository.record_success") as mock_record:
        client = GovtAPIClient(session=mock_session)
        client._resellers = [reseller]

        result = await client.verify("MH47BL1775", "rc_book")
        assert result.status == "success"
        assert result.normalized_fields["owner_name"] == "TEST"
        mock_record.assert_called_once_with("r1", 120)


@pytest.mark.asyncio
async def test_client_skips_open_circuit():
    mock_session = MagicMock()
    reseller = MagicMock()
    reseller.circuit_state = "open"
    reseller.last_failure_at = None
    reseller.provider_code = "gridlines"

    client = GovtAPIClient(session=mock_session)
    client._resellers = [reseller]

    result = await client.verify("MH47BL1775", "rc_book")
    assert result.status == "failed"
    assert "all resellers" in result.error_message.lower()


@pytest.mark.asyncio
async def test_client_records_failure_through_repository():
    mock_session = MagicMock()
    reseller = MagicMock()
    reseller.provider_code = "gridlines"
    reseller.circuit_state = "closed"
    reseller.id = "r1"

    with patch.object(GovtAPIClient, "_call_reseller", new_callable=AsyncMock, side_effect=Exception("timeout")), \
         patch("app.storage.repository.GovtResellerRepository.record_failure") as mock_failure:
        client = GovtAPIClient(session=mock_session)
        client._resellers = [reseller]

        result = await client.verify("MH47BL1775", "rc_book")
        assert result.status == "failed"
        mock_failure.assert_called_once_with("r1", "timeout")

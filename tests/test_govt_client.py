import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.govt.client import GovtAPIClient


@pytest.mark.asyncio
async def test_client_calls_primary_reseller():
    mock_session = MagicMock()
    reseller = MagicMock()
    reseller.provider_code = "gridlines"
    reseller.endpoints_by_doc_type = {"rc_book": "https://api.gridlines.io/rc"}
    reseller.response_mappers_by_doc_type = {"rc_book": "gridlines"}
    reseller.auth_config = {"env_var": "GRIDLINES_API_KEY"}
    reseller.timeout_ms = 10000
    reseller.circuit_state = "closed"
    reseller.id = "r1"

    with patch("app.govt.client.httpx.AsyncClient") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {"rc_data": {"owner_data": {"name": "TEST"}, "vehicle_data": {}, "status": "ACTIVE"}}
        }
        mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_httpx.return_value)
        mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.return_value.post = AsyncMock(return_value=mock_resp)

        client = GovtAPIClient(session=mock_session)
        client._resellers = [reseller]

        result = await client.verify("MH47BL1775", "rc_book")
        assert result.status == "success"
        assert result.normalized_fields["owner_name"] == "TEST"


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

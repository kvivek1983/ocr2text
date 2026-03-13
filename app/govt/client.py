import os
import time
from typing import List, Optional

import httpx

from app.govt.mappers import GOVT_MAPPER_REGISTRY
from app.govt.schemas import GovtVerificationResult


class GovtAPIClient:
    def __init__(self, session):
        self.session = session
        self._resellers = None

    def _load_resellers(self, doc_type: str):
        from app.storage.repository import GovtResellerRepository
        repo = GovtResellerRepository(self.session)
        self._resellers = repo.get_active_ordered(doc_type)

    async def verify(self, document_number: str, doc_type: str) -> GovtVerificationResult:
        if self._resellers is None:
            self._load_resellers(doc_type)

        from datetime import datetime, timedelta

        for reseller in self._resellers:
            if reseller.circuit_state == "open":
                if reseller.last_failure_at and \
                   datetime.utcnow() - reseller.last_failure_at > timedelta(minutes=5):
                    reseller.circuit_state = "half_open"
                else:
                    continue

            try:
                result = await self._call_reseller(reseller, document_number, doc_type)
                if result.status == "success":
                    from app.storage.repository import GovtResellerRepository
                    repo = GovtResellerRepository(self.session)
                    repo.record_success(reseller.id, result.response_time_ms)
                    return result
            except Exception as e:
                from app.storage.repository import GovtResellerRepository
                repo = GovtResellerRepository(self.session)
                repo.record_failure(reseller.id, str(e))
                continue

        return GovtVerificationResult(
            status="failed",
            reseller_code="none",
            normalized_fields={},
            raw_response={},
            error_message="All resellers exhausted or circuit open",
        )

    async def _call_reseller(self, reseller, document_number, doc_type):
        endpoint = reseller.endpoints_by_doc_type.get(doc_type)
        mapper_name = reseller.response_mappers_by_doc_type.get(doc_type)
        auth_env = reseller.auth_config.get("env_var", "")
        api_key = os.environ.get(auth_env, "")
        timeout = reseller.timeout_ms / 1000

        start = time.time()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                endpoint,
                json={"id_number": document_number},
                headers={"Authorization": api_key, "Content-Type": "application/json"},
                timeout=timeout,
            )
        elapsed_ms = int((time.time() - start) * 1000)

        if resp.status_code != 200:
            raise Exception(f"API returned {resp.status_code}")

        raw = resp.json()
        mapper = GOVT_MAPPER_REGISTRY[mapper_name]
        normalized = mapper.normalize(raw, doc_type)

        return GovtVerificationResult(
            status="success",
            reseller_code=reseller.provider_code,
            normalized_fields=normalized,
            raw_response=raw,
            response_time_ms=elapsed_ms,
        )

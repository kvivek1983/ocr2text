from dataclasses import dataclass
from datetime import datetime, date

from app.config import settings


@dataclass
class ApprovalDecision:
    method: str  # "auto_approved", "auto_rejected", "manual_review"
    reason: str


def _parse_date(date_str: str) -> date:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {date_str!r}")


class AutoApprovalEngine:
    def __init__(self):
        self.quality_threshold = settings.AUTO_APPROVAL_QUALITY_THRESHOLD
        self.match_threshold = settings.AUTO_APPROVAL_MATCH_THRESHOLD

    def _quality_ok(self, front_quality: float, back_quality: float) -> bool:
        return (
            front_quality >= self.quality_threshold
            and back_quality >= self.quality_threshold
        )

    def evaluate_rc(
        self,
        front_quality: float,
        back_quality: float,
        llm_status: str,
        govt_status: str,
        govt_match_score: float,
        govt_rc_status: str,
        govt_fitness_upto: str,
        govt_insurance_upto: str,
        critical_fields_match: bool,
    ) -> ApprovalDecision:
        today = date.today()

        # Auto-reject checks
        if govt_rc_status != "ACTIVE":
            return ApprovalDecision(
                method="auto_rejected",
                reason=f"RC status is not ACTIVE: {govt_rc_status}",
            )

        fitness_date = _parse_date(govt_fitness_upto)
        if fitness_date < today:
            return ApprovalDecision(
                method="auto_rejected",
                reason=f"RC fitness expired on {govt_fitness_upto}",
            )

        insurance_date = _parse_date(govt_insurance_upto)
        if insurance_date < today:
            return ApprovalDecision(
                method="auto_rejected",
                reason=f"RC insurance expired on {govt_insurance_upto}",
            )

        # Auto-approve check
        if (
            self._quality_ok(front_quality, back_quality)
            and govt_match_score >= self.match_threshold
            and critical_fields_match
            and llm_status == "success"
            and govt_status == "success"
        ):
            return ApprovalDecision(method="auto_approved", reason="All checks passed")

        return ApprovalDecision(
            method="manual_review",
            reason="One or more soft checks failed; requires human review",
        )

    def evaluate_dl(
        self,
        front_quality: float,
        back_quality: float,
        llm_status: str,
        govt_status: str,
        govt_match_score: float,
        govt_dl_status: str,
        govt_validity_tr: str,
        cov_covers_vehicle: bool,
        critical_fields_match: bool,
    ) -> ApprovalDecision:
        today = date.today()

        # Auto-reject checks
        validity_date = _parse_date(govt_validity_tr)
        if validity_date < today:
            return ApprovalDecision(
                method="auto_rejected",
                reason=f"DL expired on {govt_validity_tr}",
            )

        if govt_dl_status != "ACTIVE":
            return ApprovalDecision(
                method="auto_rejected",
                reason=f"DL status is not ACTIVE: {govt_dl_status}",
            )

        # Auto-approve check
        if (
            self._quality_ok(front_quality, back_quality)
            and govt_match_score >= self.match_threshold
            and critical_fields_match
            and cov_covers_vehicle
            and llm_status == "success"
            and govt_status == "success"
        ):
            return ApprovalDecision(method="auto_approved", reason="All checks passed")

        return ApprovalDecision(
            method="manual_review",
            reason="One or more soft checks failed; requires human review",
        )

    def evaluate_aadhaar(
        self,
        front_quality: float,
        back_quality: float,
        llm_status: str,
        govt_status: str,
        govt_match_score: float,
        govt_aadhaar_status: str,
        critical_fields_match: bool,
    ) -> ApprovalDecision:
        # Auto-reject checks
        if govt_aadhaar_status != "VALID":
            return ApprovalDecision(
                method="auto_rejected",
                reason=f"Aadhaar status is not VALID: {govt_aadhaar_status}",
            )

        # Auto-approve check
        if (
            self._quality_ok(front_quality, back_quality)
            and govt_match_score >= self.match_threshold
            and critical_fields_match
            and llm_status == "success"
            and govt_status == "success"
        ):
            return ApprovalDecision(method="auto_approved", reason="All checks passed")

        return ApprovalDecision(
            method="manual_review",
            reason="One or more soft checks failed; requires human review",
        )

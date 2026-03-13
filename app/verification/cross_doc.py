from thefuzz import fuzz
from app.config import settings


class CrossDocValidator:
    """Validates consistency of fields across DL, Aadhaar, and RC documents."""

    def validate(
        self,
        dl_name: str | None,
        aadhaar_name: str | None,
        dl_dob: str | None,
        aadhaar_dob: str | None,
        dl_cov: list | None,
        rc_vehicle_class: str | None,
    ) -> dict:
        """
        Compare fields across DL, Aadhaar, and RC documents.

        Returns a dict with keys:
          passed, name_match, dob_match, cov_match, name_similarity, details
        """
        # Name match via fuzzy token sort ratio
        name_similarity = 0.0
        name_match = False
        if dl_name is not None and aadhaar_name is not None:
            raw_score = fuzz.token_sort_ratio(dl_name.upper(), aadhaar_name.upper())
            name_similarity = raw_score / 100.0
            name_match = name_similarity >= settings.FUZZY_NAME_MATCH_THRESHOLD

        # DOB match — exact string comparison
        dob_match = False
        if dl_dob is not None and aadhaar_dob is not None:
            dob_match = dl_dob.strip() == aadhaar_dob.strip()

        # CoV match — rc_vehicle_class must be in dl_cov (case-insensitive)
        cov_match = False
        if dl_cov is not None and rc_vehicle_class is not None:
            cov_upper = [c.upper() for c in dl_cov]
            cov_match = rc_vehicle_class.upper() in cov_upper

        passed = name_match and dob_match and cov_match

        details_parts = []
        if not name_match:
            details_parts.append(f"name mismatch (similarity={name_similarity:.2f})")
        if not dob_match:
            details_parts.append("DOB mismatch")
        if not cov_match:
            details_parts.append("vehicle class not covered by DL")
        details = "; ".join(details_parts) if details_parts else "all checks passed"

        return {
            "passed": passed,
            "name_match": name_match,
            "dob_match": dob_match,
            "cov_match": cov_match,
            "name_similarity": name_similarity,
            "details": details,
        }

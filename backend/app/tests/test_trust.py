from app.services.trust_checker import analyze


def test_fee_negation_does_not_claim_verified_employer():
    result = analyze({"description": "No registration fee. No guaranteed benefit stated."})
    assert result["risk_score"] == 0
    assert result["verification_status"] == "UNKNOWN"

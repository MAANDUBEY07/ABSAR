from app.utils.file_handler import claims


def test_claim_offsets_and_negation():
    text = "No Python experience. I use SQL."
    result = claims(text)
    assert len(result) == 1
    assert text[result[0]["start"] : result[0]["end"]] == result[0]["quote"] == "SQL"
    assert result[0]["source"] == "RESUME_CLAIM"

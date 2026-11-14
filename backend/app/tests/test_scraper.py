import pytest
from app.services.safe_fetch import destination


def test_discovery_fetch_rejects_metadata_destination():
    with pytest.raises(ValueError):
        destination("http://169.254.169.254/latest/meta-data/")

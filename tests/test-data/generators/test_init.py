"""End-to-end anonymization tests."""

from fastapi.testclient import TestClient
import pytest

from main import app

client = TestClient(app)


@pytest.mark.slow
def test_anonymize_markdown_end_to_end():
    text = (
        "Patient John Doe was seen on January 15, 2024. "
        "Email: john.doe@example.com. Phone: 555-123-4567."
    )
    response = client.post(
        "/anonymization/anonymize-markdown",
        json={"markdown_text": text},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["anonymized_text"] != text
    assert sum(payload.get("statistics", {}).values()) > 0
    assert payload.get("vault_data")


@pytest.mark.slow
def test_anonymize_azure_di_end_to_end():
    azure_di_json = {
        "content": "John Doe lives at 123 Main St. Email john.doe@example.com.",
        "pages": [
            {
                "pageNumber": 1,
                "content": "Contact Jane Doe on 2024-01-15.",
            }
        ],
    }
    response = client.post(
        "/anonymization/anonymize-azure-di",
        json={"azure_di_json": azure_di_json},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["anonymized_json"]["content"] != azure_di_json["content"]
    assert sum(payload.get("statistics", {}).values()) > 0
    assert payload.get("vault_data")

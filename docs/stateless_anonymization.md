# Stateless Anonymization

The anonymization endpoints now support stateless operation by allowing clients to pass vault data between requests. This enables consistent anonymization across multiple API calls without requiring server-side session management.

## How It Works

1. **Initial Request**: When you first anonymize content, the API returns a `vault_data` field containing all the anonymization mappings.

2. **Subsequent Requests**: Pass the `vault_data` from previous responses to maintain consistent replacements across related documents.

3. **Vault Data Format**: The vault data is a JSON array of arrays, where each inner array contains:
   - Index 0: The replacement value (e.g., "Jane Doe")
   - Index 1: The original value (e.g., "John Smith")

## API Changes

### Request Models

Both anonymization endpoints now accept an optional `vault_data` field:

```json
{
  "markdown_text": "...",
  "config": {...},
  "vault_data": [
    ["Jane Doe", "John Smith"],
    ["555-987-6543", "555-123-4567"]
  ]
}
```

### Response Models

All anonymization responses now include the `vault_data` field:

```json
{
  "anonymized_text": "...",
  "statistics": {...},
  "vault_data": [
    ["Jane Doe", "John Smith"],
    ["555-987-6543", "555-123-4567"]
  ]
}
```

## Example Usage

```python
import requests

# First request - no vault data
response1 = requests.post("/anonymization/anonymize-markdown", json={
    "markdown_text": "John Smith's email is john@example.com",
    "config": {"entity_types": ["PERSON", "EMAIL_ADDRESS"]}
})

vault_data = response1.json()["vault_data"]

# Second request - use vault data for consistency
response2 = requests.post("/anonymization/anonymize-markdown", json={
    "markdown_text": "Contact John Smith for more details",
    "config": {"entity_types": ["PERSON", "EMAIL_ADDRESS"]},
    "vault_data": vault_data  # Pass vault from first response
})
```

## Storage Options

### 1. JSON File

```python
import json

# Save vault data
with open('vault.json', 'w') as f:
    json.dump(vault_data, f)

# Load vault data
with open('vault.json', 'r') as f:
    vault_data = json.load(f)
```

### 2. Database (PostgreSQL)

```sql
CREATE TABLE anonymization_vaults (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id VARCHAR(255),
    vault_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Store vault
INSERT INTO anonymization_vaults (document_id, vault_data)
VALUES ('doc_123', $1::jsonb);
```

### 3. Redis Cache

```python
import redis
import json

r = redis.Redis()

# Store with TTL
r.setex('vault:session:123', 3600, json.dumps(vault_data))

# Retrieve
vault_json = r.get('vault:session:123')
if vault_json:
    vault_data = json.loads(vault_json)
```

## Current Limitations

**Important**: Due to LLM-Guard's current implementation, when `use_faker=True` is enabled (which is the default), the library generates new fake values on each scan even if the original value already exists in the vault. The vault tracks all mappings but doesn't enforce consistency for faker replacements.

This means:

- The vault data will contain all mappings from all requests
- But the actual replacement values may differ between requests
- This is a limitation of the LLM-Guard library, not our implementation

For applications requiring strict consistency, consider:

1. Post-processing the results to enforce consistency
2. Using a custom anonymization solution
3. Contributing improvements to the LLM-Guard project

## Benefits

1. **No Server State**: The server doesn't need to maintain session state
2. **Scalability**: Works seamlessly with load-balanced deployments
3. **Flexibility**: Clients control when to reuse or reset anonymization mappings
4. **Persistence**: Vault data can be stored alongside anonymized content
5. **Debugging**: Easy to inspect and understand anonymization mappings

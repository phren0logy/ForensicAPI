# FastAPI Reusable Prototyping App

## Getting Started

### Prerequisites
- Python 3.8+
- Install dependencies using [uv](https://github.com/astral-sh/uv):
  ```sh
  uv pip install -r requirements.txt
  ```

### Running the Server

To start only the FastAPI backend:
```sh
uv run run.py
```

To start both the FastAPI backend and the MonsterUI test page:
```sh
uv run run.py -- --with-frontend
```
- The `--with-frontend` flag launches a UI test page at a separate port for interactive testing.

## API Endpoints

### `/compose-prompt` (POST)
- **Description:** Compose a prompt from multiple text fields and/or files, each wrapped in a specified XML tag.
- **Request:**
  - `multipart/form-data` with a `mapping` field (JSON: `{tag: value}`), where each key is an XML tag and the value is either:
    - A string (content), or
    - The name of an uploaded file field
  - Optionally, upload files with field names matching the mapping values.
- **Special Case:**
  - If a tag is named `instructions`, its section is wrapped in `<instructions>` and appears at both the top and bottom of the result.
- **Response:**
  - Plain text: The composed prompt with each section wrapped in its XML tag.
- **Example (text only):**
  ```json
  {
    "document": "Some document text",
    "transcript": "Transcript goes here",
    "manual": "Manual text",
    "instructions": "Do not share."
  }
  ```

### `/pdf-to-markdown` (POST)
- **Description:** Converts an uploaded PDF to Markdown using Azure Document Intelligence.
- **Request:**
  - `multipart/form-data` with a single file field named `file` (PDF file).
- **Response:**
  - Plain text: Extracted Markdown content.

## Testing
- For a simple UI to test `/compose-prompt`, start with `--with-frontend` and open the MonsterUI test page.
- You can also use tools like Postman or curl to test endpoints directly.

---
For questions or issues, please contact the project maintainer.

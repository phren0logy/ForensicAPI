# FastAPI Reusable Prototyping App

## Test the Endpoints with Built-in HTML Pages

This project includes simple HTML forms for testing endpoints.

### How to Use:

1. **Start the FastAPI server:**

   ```
   uv run run.py
   ```

   or

   ```
   uvicorn main:app --reload
   ```

2. **Visit the test pages in your browser:**

   - [PDF to Markdown Test](http://127.0.0.1:8000/pdf-test)
   - [Prompt Composer Test](http://127.0.0.1:8000/prompt-test)

3. **PDF to Markdown Test**

   - Upload a PDF file and download the converted markdown.

4. **Prompt Composer Test**
   - Fill in the fields and submit to see the composed prompt result.

---

## Getting Started

### Prerequisites

- Python 3.8+
- Install dependencies using [uv](https://github.com/astral-sh/uv):
  ```sh
  uv sync
  ```

### Running the Server

To start the FastAPI server:

```sh
uv run run.py
```

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

---

For questions or issues, please contact the project maintainer.

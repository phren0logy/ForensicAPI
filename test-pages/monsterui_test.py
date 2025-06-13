from fasthtml.common import *
from monsterui.all import *
import httpx
import json

hdrs = Theme.blue.headers()
app, rt = fast_app(hdrs=hdrs)

@rt
async def index(document: str = '', transcript: str = '', manual: str = '', result: str = '', submit: str = None):
    combined_result = result
    if submit:
        # On form submit, call backend and get combined result
        mapping = {'document': document, 'transcript': transcript, 'manual': manual}
        async with httpx.AsyncClient() as client:
            data = {'mapping': json.dumps(mapping)}
            resp = await client.post('http://127.0.0.1:8000/compose-prompt', data=data)
            combined_result = resp.text
    return Titled("Compose Prompt Test (MonsterUI)",
        Card(
            H1("Test /compose-prompt (text only)"),
            Form(
                Div(
                    Label("Document:"),
                    Input(name="document", value=document, type="text"),
                ),
                Div(
                    Label("Transcript:"),
                    Input(name="transcript", value=transcript, type="text"),
                ),
                Div(
                    Label("Manual:"),
                    Input(name="manual", value=manual, type="text"),
                ),
                Button("Submit", type="submit", name="submit", value="1"),
            ),
            Div(
                H2("Combined Result:"),
                Pre(combined_result or "(Result will appear here)")
            )
        )
    )

if __name__ == "__main__":
    serve()

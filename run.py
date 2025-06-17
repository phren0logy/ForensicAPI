import uvicorn

if __name__ == "__main__":
    # Use 2 workers to allow internal HTTP requests (e.g., httpx calls to self) to succeed.
    # Reload is set to False becuase that's required if you specify workers
    # For most local development, 2-4 workers is safe. Increase if you have a powerful machine or heavy concurrent load.
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False, workers=4)

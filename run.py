import uvicorn
import argparse
import subprocess
import sys

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run FastAPI backend and optionally MonsterUI frontend.")
    parser.add_argument("--with-frontend", action="store_true", help="Start MonsterUI frontend as well.")
    args = parser.parse_args()

    frontend_proc = None
    try:
        if args.with_frontend:
            frontend_proc = subprocess.Popen([
                sys.executable, "test-pages/monsterui_test.py"
            ])
        uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
    finally:
        if frontend_proc:
            frontend_proc.terminate()

"""Run a local service with .env loaded as data, never as shell code."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", choices=("api", "web", "mcp"))
    parser.add_argument("--production", action="store_true", help="Use the built Next.js app (web only).")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env", override=False)
    os.environ.setdefault("BACKEND_URL", "http://127.0.0.1:8000")
    os.environ.setdefault("FRONTEND_ORIGIN", "http://127.0.0.1:3000")
    os.chdir(root)
    if args.service == "api":
        command = [sys.executable, "-m", "uvicorn", "app.main:app", "--host",
                   os.getenv("API_HOST", "127.0.0.1"), "--port", os.getenv("API_PORT", "8000"),
                   "--no-access-log"]
    elif args.service == "mcp":
        command = [sys.executable, "-m", "prompt_enhance_mcp.server"]
    else:
        npm = shutil.which("npm")
        if npm is None:
            parser.error("npm was not found. Install Node.js 22+ and run npm ci in frontend/.")
        os.chdir(root / "frontend")
        command = [npm, "run", "start" if args.production else "dev", "--", "--hostname", "127.0.0.1", "--port", "3000"]
    os.execv(command[0], command)


if __name__ == "__main__":
    main()

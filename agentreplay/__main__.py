"""python -m agentreplay — start the AgentReplay dashboard server."""
import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentReplay time-travel debugger")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7474)
    parser.add_argument("--db", default=".agentreplay.db", help="Path to SQLite DB")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    import agentreplay.sqlite_store as _ss
    _ss._default_store = _ss.SQLiteStore(db_path=args.db)

    if not args.no_browser:
        import threading
        import time
        import webbrowser
        def _open() -> None:
            time.sleep(1.2)
            webbrowser.open(f"http://{args.host}:{args.port}")
        threading.Thread(target=_open, daemon=True).start()

    print(f"AgentReplay dashboard → http://{args.host}:{args.port}")
    print(f"Watching DB: {args.db}")
    print("Press Ctrl+C to stop.\n")

    import uvicorn
    from agentreplay.server import app
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()

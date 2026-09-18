"""Dev-server launcher that works regardless of the caller's cwd."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import uvicorn  # noqa: E402

if __name__ == "__main__":
    # reload=True so editing anything under app/ restarts the server. Without
    # it a long-running window silently serves whatever code it started with,
    # and a newly added route just 404s — which looks exactly like a bug in
    # the feature rather than a stale process.
    #
    # reload_dirs is pinned to app/ on purpose: the default watches the whole
    # working directory, which here would include .venv (thousands of files
    # that never change). data/ sits outside backend/ and is not watched, so
    # a scrape writing snapshots or SQLite WAL churn cannot trigger a restart.
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8001,
        reload=True,
        reload_dirs=[os.path.join(HERE, "app")],
    )

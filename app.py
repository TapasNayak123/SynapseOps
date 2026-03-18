"""SynapseOps — Single entry point.

Runs the unified FastAPI application with uvicorn.
"""
import uvicorn

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level="info")

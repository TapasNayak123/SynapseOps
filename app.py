"""SynapseOps — Single entry point.

Runs the unified FastAPI application with uvicorn.
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=5000, log_level="info")

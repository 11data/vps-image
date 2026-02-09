#!/usr/bin/env python3
"""
Mission Control API Server

FastAPI server for task management (Kanban board) and activity tracking.
Runs as a Docker service with PostgreSQL backend.
"""

import os
import asyncio
import json
import uuid
from datetime import datetime
from typing import Optional, List, Any

from fastapi import FastAPI, HTTPException, Query, Header
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
import asyncpg
from aiohttp import ClientSession, ClientError

# Configuration
PORT = int(os.getenv("MISSION_CONTROL_PORT", "18790"))
HOST = os.getenv("MISSION_CONTROL_HOST", "0.0.0.0")
DB_URL = os.getenv("MISSION_CONTROL_DB_URL")
TOKEN = os.getenv("MISSION_CONTROL_TOKEN", "")
OPENCLAW_INSTANCE_ID = os.getenv("OPENCLAW_INSTANCE_ID", "vps")
OPENCLAW_GATEWAY_URL = os.getenv("OPENCLAW_GATEWAY_URL", "http://openclaw:18789")

# Database connection pool
pool: asyncpg.Pool = None


async def get_db():
    """Get database connection from pool"""
    async with pool.acquire() as conn:
        yield conn


# FastAPI app
app = FastAPI(
    title="Mission Control API",
    description="Task management and activity tracking for RunYourAgent",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


# Pydantic models
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    status: str = Field(default="backlog", pattern="^(backlog|todo|in_progress|done|cancelled)$")
    priority: int = Field(default=0, ge=0, le=10)
    agent_id: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    agent_id: Optional[str] = None
    completed_at: Optional[str] = None


class Task(BaseModel):
    id: str
    title: str
    description: Optional[str]
    status: str
    priority: int
    agent_id: Optional[str]
    created_at: str
    updated_at: str
    completed_at: Optional[str]


class ActivityEvent(BaseModel):
    id: str
    event_type: str
    source: Optional[str]
    data: Optional[dict]
    created_at: str


class AgentProfile(BaseModel):
    agent_id: str
    name: str
    description: Optional[str]
    config: Optional[dict]
    created_at: str
    updated_at: str


# Startup/Shutdown events
@app.on_event("startup")
async def startup():
    """Initialize database connection pool"""
    global pool
    if not DB_URL:
        raise RuntimeError("MISSION_CONTROL_DB_URL environment variable not set")

    pool = await asyncpg.create_pool(
        DB_URL,
        min_size=2,
        max_size=10,
        command_timeout=60
    )
    print(f"Mission Control API: Connected to database")


@app.on_event("shutdown")
async def shutdown():
    """Close database connection pool"""
    global pool
    if pool:
        await pool.close()
        print("Mission Control API: Database connection closed")


# Auth middleware
async def verify_token(authorization: Optional[str] = Header(None)):
    """Verify request token"""
    if not TOKEN:
        return  # No token configured, skip auth

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization scheme")

    if token != TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")


# Health check
@app.get("/health")
async def health():
    """Health check endpoint"""
    db_ok = pool is not None
    try:
        if pool:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
    except Exception as e:
        db_ok = False

    return JSONResponse({
        "status": "healthy" if db_ok else "unhealthy",
        "database": "connected" if db_ok else "disconnected",
        "instance_id": OPENCLAW_INSTANCE_ID
    })


# Kanban endpoints
@app.get("/kanban")
async def get_kanban_tasks(
    status: Optional[str] = None,
    agent_id: Optional[str] = None,
    _: None = Depends(verify_token)
):
    """Get all tasks, optionally filtered by status or agent"""
    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                "SELECT * FROM tasks WHERE status = $1 ORDER BY priority DESC, created_at DESC",
                status
            )
        elif agent_id:
            rows = await conn.fetch(
                "SELECT * FROM tasks WHERE agent_id = $1 ORDER BY priority DESC, created_at DESC",
                agent_id
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM tasks ORDER BY priority DESC, created_at DESC"
            )

        return [
            {
                "id": str(row["id"]),
                "title": row["title"],
                "description": row["description"],
                "status": row["status"],
                "priority": row["priority"],
                "agent_id": row["agent_id"],
                "created_at": row["created_at"].isoformat(),
                "updated_at": row["updated_at"].isoformat(),
                "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
            }
            for row in rows
        ]


@app.post("/kanban/tasks")
async def create_task(
    task: TaskCreate,
    _: None = Depends(verify_token)
):
    """Create a new task"""
    async with pool.acquire() as conn:
        task_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO tasks (id, title, description, status, priority, agent_id)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            task_id, task.title, task.description, task.status, task.priority, task.agent_id
        )

        row = await conn.fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)

        return {
            "id": str(row["id"]),
            "title": row["title"],
            "description": row["description"],
            "status": row["status"],
            "priority": row["priority"],
            "agent_id": row["agent_id"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
            "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
        }


@app.get("/kanban/tasks/{task_id}")
async def get_task(
    task_id: str,
    _: None = Depends(verify_token)
):
    """Get a specific task"""
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow("SELECT * FROM tasks WHERE id = $1", uuid.UUID(task_id))
        except (asyncpg.DataError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid task ID")

        if not row:
            raise HTTPException(status_code=404, detail="Task not found")

        return {
            "id": str(row["id"]),
            "title": row["title"],
            "description": row["description"],
            "status": row["status"],
            "priority": row["priority"],
            "agent_id": row["agent_id"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
            "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
        }


@app.put("/kanban/tasks/{task_id}")
async def update_task(
    task_id: str,
    task: TaskUpdate,
    _: None = Depends(verify_token)
):
    """Update a task"""
    updates = {}
    if task.title is not None:
        updates["title"] = task.title
    if task.description is not None:
        updates["description"] = task.description
    if task.status is not None:
        updates["status"] = task.status
        if task.status == "done" and not task.completed_at:
            updates["completed_at"] = datetime.now()
    if task.priority is not None:
        updates["priority"] = task.priority
    if task.agent_id is not None:
        updates["agent_id"] = task.agent_id

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates["updated_at"] = datetime.now()

    # Build dynamic SQL
    set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates.keys()))
    values = list(updates.values())

    async with pool.acquire() as conn:
        try:
            await conn.execute(
                f"UPDATE tasks SET {set_clause} WHERE id = $1",
                uuid.UUID(task_id), *values
            )
        except (asyncpg.DataError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid task ID")

        row = await conn.fetchrow("SELECT * FROM tasks WHERE id = $1", uuid.UUID(task_id))

        if not row:
            raise HTTPException(status_code=404, detail="Task not found")

        return {
            "id": str(row["id"]),
            "title": row["title"],
            "description": row["description"],
            "status": row["status"],
            "priority": row["priority"],
            "agent_id": row["agent_id"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
            "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
        }


@app.delete("/kanban/tasks/{task_id}")
async def delete_task(
    task_id: str,
    _: None = Depends(verify_token)
):
    """Delete a task"""
    async with pool.acquire() as conn:
        try:
            result = await conn.execute(
                "DELETE FROM tasks WHERE id = $1",
                uuid.UUID(task_id)
            )
        except (asyncpg.DataError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid task ID")

        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Task not found")

        return {"success": True, "id": task_id}


# Activity endpoints
@app.get("/activity")
async def get_activity(
    limit: int = Query(100, ge=1, le=1000),
    event_type: Optional[str] = None,
    _: None = Depends(verify_token)
):
    """Get activity events"""
    async with pool.acquire() as conn:
        if event_type:
            rows = await conn.fetch(
                "SELECT * FROM activity_events WHERE event_type = $1 ORDER BY created_at DESC LIMIT $2",
                event_type, limit
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM activity_events ORDER BY created_at DESC LIMIT $1",
                limit
            )

        return [
            {
                "id": str(row["id"]),
                "event_type": row["event_type"],
                "source": row["source"],
                "data": row["data"],
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ]


@app.post("/activity")
async def log_activity(
    event_type: str,
    data: Optional[dict] = None,
    source: Optional[str] = None,
    _: None = Depends(verify_token)
):
    """Log an activity event"""
    async with pool.acquire() as conn:
        event_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO activity_events (id, event_type, source, data)
            VALUES ($1, $2, $3, $4)
            """,
            event_id, event_type, source, json.dumps(data) if data else None
        )

        return {
            "success": True,
            "id": str(event_id)
        }


# SSE streaming endpoints
async def task_event_generator():
    """Stream task updates via SSE"""
    try:
        while True:
            async with pool.acquire() as conn:
                # Get recent tasks
                rows = await conn.fetch(
                    "SELECT * FROM tasks ORDER BY updated_at DESC LIMIT 100"
                )

                tasks = [
                    {
                        "id": str(row["id"]),
                        "title": row["title"],
                        "description": row["description"],
                        "status": row["status"],
                        "priority": row["priority"],
                        "agent_id": row["agent_id"],
                        "updated_at": row["updated_at"].isoformat(),
                    }
                    for row in rows
                ]

                yield f"event: update\ndata: {json.dumps(tasks)}\n\n"

            await asyncio.sleep(2)
    except asyncio.CancelledError:
        pass


async def activity_event_generator():
    """Stream activity events via SSE"""
    try:
        last_event_id = None

        while True:
            async with pool.acquire() as conn:
                query = "SELECT * FROM activity_events ORDER BY created_at DESC LIMIT 100"
                if last_event_id:
                    query = f"SELECT * FROM activity_events WHERE created_at > '{last_event_id}' ORDER BY created_at DESC"

                rows = await conn.fetch(query)

                events = []
                for row in rows:
                    event_id = str(row["id"])
                    events.append({
                        "id": event_id,
                        "event_type": row["event_type"],
                        "source": row["source"],
                        "data": row["data"],
                        "created_at": row["created_at"].isoformat(),
                    })
                    if not last_event_id:
                        last_event_id = row["created_at"].isoformat()

                for event in reversed(events):
                    yield f"event: activity\ndata: {json.dumps(event)}\n\n"

            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass


@app.get("/kanban/stream")
async def stream_kanban(
    _: None = Depends(verify_token)
):
    """SSE stream for task updates"""
    return StreamingResponse(
        task_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/activity/stream")
async def stream_activity(
    _: None = Depends(verify_token)
):
    """SSE stream for activity events"""
    return StreamingResponse(
        activity_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# Agent profiles
@app.get("/agent-profiles")
async def get_agent_profiles(
    _: None = Depends(verify_token)
):
    """Get all agent profiles"""
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM agent_profiles ORDER BY name")

        return [
            {
                "agent_id": row["agent_id"],
                "name": row["name"],
                "description": row["description"],
                "config": row["config"],
                "created_at": row["created_at"].isoformat(),
                "updated_at": row["updated_at"].isoformat(),
            }
            for row in rows
        ]


@app.get("/agent-profiles/{agent_id}")
async def get_agent_profile(
    agent_id: str,
    _: None = Depends(verify_token)
):
    """Get a specific agent profile"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM agent_profiles WHERE agent_id = $1",
            agent_id
        )

        if not row:
            raise HTTPException(status_code=404, detail="Agent profile not found")

        return {
            "agent_id": row["agent_id"],
            "name": row["name"],
            "description": row["description"],
            "config": row["config"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
        }


if __name__ == "__main__":
    import uvicorn

    print(f"Starting Mission Control API on {HOST}:{PORT}")
    print(f"Instance ID: {OPENCLAW_INSTANCE_ID}")
    print(f"Token configured: {bool(TOKEN)}")

    uvicorn.run(app, host=HOST, port=PORT)

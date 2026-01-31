from fastapi import Request
import uuid
import os
import json
from starlette.responses import StreamingResponse
from starlette.templating import Jinja2Templates
from core.schema.default import Query
from settings import template_dir
from texttosql import stream_sql_query

template=Jinja2Templates(directory=str(template_dir))

async def default(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())

    response = template.TemplateResponse("default.html", {"request": request})
    response.set_cookie(
        key="session_id",
        value=session_id,
        max_age=3600
    )
    return response

async def query(request: Request, query: Query):
    q = query.question
    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())

    async def generate():
        result = stream_sql_query(q, session_id)
        async for chunk in result:
            yield json.dumps({'content': chunk}) + '\n'

    return StreamingResponse(generate(), media_type="text/event-stream")
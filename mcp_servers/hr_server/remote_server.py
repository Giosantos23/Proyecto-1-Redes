import asyncio
import json
import logging
import uuid
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from server import (
    DATABASE,
    HANDLERS,
    PROTOCOL_VERSION,
    SERVER_NAME,
    SERVER_VERSION,
    RPCError,
    dispatch,
    error_response,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(f"{SERVER_NAME}-remote")

app = FastAPI(title=f"{SERVER_NAME} Remote")

sessions: dict[str, asyncio.Queue] = {}


class JSONRPCMessage(BaseModel):
    jsonrpc: str
    id: Any = None
    method: str | None = None
    params: dict[str, Any] | None = None
    result: Any = None
    error: Any = None


@app.get("/sse")
async def sse_endpoint(request: Request):
    session_id = str(uuid.uuid4())
    queue = asyncio.Queue()
    sessions[session_id] = queue

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            endpoint_url = f"/messages?sessionId={session_id}"
            yield f"event: endpoint\ndata: {endpoint_url}\n\n"
            
            logger.info(f"Nueva sesión MCP inciada: {session_id}")

            while True:
                message = await queue.get()
                yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            logger.info(f"Sesión MCP cerrada: {session_id}")
        finally:
            if session_id in sessions:
                del sessions[session_id]

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/messages")
async def messages_endpoint(
    request: Request, 
    sessionId: str, 
    background_tasks: BackgroundTasks
):
    if sessionId not in sessions:
        return Response(content="Sesión no encontrada", status_code=404)

    try:
        body = await request.json()
        logger.info(f"Mensaje recibido para la sesión {sessionId}: {body}")
        
        try:
            result = dispatch(body, DATABASE)
        except RPCError as exc:
            result = error_response(body.get("id"), exc)
        except Exception as exc:
            logger.exception("Error interno del servidor")
            result = error_response(body.get("id"), RPCError(-32603, "Error interno"))

        if result is not None:
            await sessions[sessionId].put(result)
            
        return Response(status_code=202)
    except json.JSONDecodeError:
        return Response(content="JSON inválido", status_code=400)
    except Exception as exc:
        logger.error(f"Error procesando mensaje: {exc}")
        return Response(content="Error interno", status_code=500)


@app.on_event("startup")
async def startup_event():
    DATABASE.initialize()
    logger.info("DB remota inicializada")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

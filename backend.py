from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import asyncio
import uvicorn
from datetime import datetime

# Imports locales
from config import settings
from session_manager import session_manager
from models import (
    QueryRequest, NewSessionResponse, QueryResponse, 
    ConversationHistoryResponse, AvailableToolsResponse,
    SessionListResponse, ErrorResponse, HealthResponse,
    ConversationMessage, ToolCall, ToolResult, ToolInfo
)

# Configurar logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format=settings.log_format,
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Maneja el ciclo de vida de la aplicación FastAPI"""
    logger.info("Starting FastAPI application...")
    
    try:
        # Iniciar tarea de limpieza de sesiones
        await session_manager.start_cleanup_task()
        logger.info("Application startup completed")
        yield
        
    except Exception as e:
        logger.error(f"Error during application startup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Application startup failed: {str(e)}"
        )
        
    finally:
        # Cleanup al cerrar la aplicación
        logger.info("Shutting down application...")
        try:
            await session_manager.stop_cleanup_task()
            await session_manager.cleanup_all_sessions()
            logger.info("Application shutdown completed")
        except Exception as e:
            logger.error(f"Error during application shutdown: {e}")

# Crear aplicación FastAPI
app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# ENDPOINTS

@app.get("/", tags=["Health"])
async def root():
    """Endpoint raíz con información básica"""
    return {
        "message": "MCP Client API is running",
        "version": settings.api_version,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Endpoint de health check"""
    active_sessions = session_manager.get_session_count()
    
    # Verificar si hay al menos una sesión conectada para probar conectividad MCP
    mcp_connected = False
    if active_sessions > 0:
        # Tomar una sesión cualquiera para verificar conectividad
        session_ids = session_manager.list_sessions()
        if session_ids:
            client = session_manager.get_session(session_ids[0])
            if client:
                mcp_connected = client.is_connected
    
    return HealthResponse(
        status="healthy",
        mcp_server_connected=mcp_connected,
        active_sessions=active_sessions
    )

@app.post("/session/new", response_model=NewSessionResponse, tags=["Sessions"])
async def create_new_session():
    """Crea una nueva sesión de conversación"""
    try:
        session_id = await session_manager.create_session()
        logger.info(f"New session created: {session_id}")
        
        return NewSessionResponse(
            session_id=session_id,
            message="Session created successfully"
        )
        
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}"
        )

@app.get("/sessions", response_model=SessionListResponse, tags=["Sessions"])
async def list_sessions():
    """Lista todas las sesiones activas"""
    try:
        sessions = session_manager.list_sessions()
        return SessionListResponse(
            sessions=sessions,
            total_sessions=len(sessions)
        )
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sessions: {str(e)}"
        )

@app.delete("/session/{session_id}", tags=["Sessions"])
async def delete_session(session_id: str):
    """Elimina una sesión específica"""
    try:
        deleted = await session_manager.delete_session(session_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )
        
        return {"message": f"Session {session_id} deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session: {str(e)}"
        )

@app.post("/session/{session_id}/query", response_model=QueryResponse, tags=["Queries"])
async def process_query(session_id: str, request: QueryRequest):
    """Procesa una query en una sesión específica manteniendo el contexto"""
    try:
        # Obtener cliente de la sesión
        client = session_manager.get_session(session_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found or expired"
            )
        
        # Incrementar contador de queries
        session_manager.increment_query_count(session_id)
        
        # Procesar query
        logger.info(f"Processing query for session {session_id}: {request.query}")
        result = await client.process_query(request.query)
        
        # Convertir resultado al formato de respuesta
        tools_called = [
            ToolCall(name=tool["name"], args=tool["args"]) 
            for tool in result.get("tools_called", [])
        ]
        
        tools_results = [
            ToolResult(
                tool=tool_result.get("tool", ""),
                result=tool_result.get("result"),
                error=tool_result.get("error")
            )
            for tool_result in result.get("tools_results", [])
        ]
        
        response = QueryResponse(
            session_id=session_id,
            query=result["query"],
            llm_text=result.get("llm_text", []),
            tools_called=tools_called,
            tools_results=tools_results
        )
        
        logger.info(f"Query processed successfully for session {session_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing query for session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {str(e)}"
        )

@app.get("/session/{session_id}/history", response_model=ConversationHistoryResponse, tags=["Conversations"])
async def get_conversation_history(session_id: str):
    """Obtiene el historial completo de conversación de una sesión"""
    try:
        client = session_manager.get_session(session_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found or expired"
            )
        
        # Obtener historial
        history_raw = client.get_conversation_history()
        
        # Convertir al formato de respuesta
        history = [
            ConversationMessage(
                role=msg["role"],
                content=msg["content"],
                timestamp=msg["timestamp"],
                tool_name=msg.get("tool_name"),
                tool_args=msg.get("tool_args")
            )
            for msg in history_raw
        ]
        
        return ConversationHistoryResponse(
            session_id=session_id,
            history=history,
            total_messages=len(history)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation history for session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get conversation history: {str(e)}"
        )

@app.delete("/session/{session_id}/history", tags=["Conversations"])
async def clear_conversation_history(session_id: str):
    """Limpia el historial de conversación de una sesión"""
    try:
        client = session_manager.get_session(session_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found or expired"
            )
        
        client.clear_conversation_history()
        logger.info(f"Conversation history cleared for session {session_id}")
        
        return {"message": f"Conversation history cleared for session {session_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing conversation history for session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear conversation history: {str(e)}"
        )

@app.post("/session/{session_id}/save", tags=["Conversations"])
async def save_conversation(session_id: str):
    """Guarda la conversación actual en un archivo JSON"""
    try:
        client = session_manager.get_session(session_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found or expired"
            )
        
        filepath = client.save_conversation_to_file()
        if not filepath:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No conversation history to save or error saving file"
            )
        
        return {
            "message": "Conversation saved successfully",
            "filepath": filepath
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving conversation for session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save conversation: {str(e)}"
        )


# Exception handlers
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handler general para excepciones no capturadas"""
    logger.error(f"Unhandled exception: {exc}")
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error"
    )

if __name__ == "__main__":
    logger.info(f"Starting FastAPI server on {settings.api_host}:{settings.api_port}")
    uvicorn.run(
        "backend:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level=settings.log_level.lower()
    )
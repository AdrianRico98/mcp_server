from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class QueryRequest(BaseModel):
    query: str = Field(..., description="La consulta del usuario")

class NewSessionResponse(BaseModel):
    session_id: str = Field(..., description="ID único de la sesión creada")
    message: str = Field(..., description="Mensaje de confirmación")

class ToolCall(BaseModel):
    name: str = Field(..., description="Nombre de la herramienta")
    args: Dict[str, Any] = Field(..., description="Argumentos de la herramienta")

class ToolResult(BaseModel):
    tool: str = Field(..., description="Nombre de la herramienta ejecutada")
    result: Optional[Any] = Field(None, description="Resultado de la herramienta")
    error: Optional[str] = Field(None, description="Error si ocurrió alguno")

class QueryResponse(BaseModel):
    session_id: str = Field(..., description="ID de la sesión")
    query: str = Field(..., description="Consulta procesada")
    llm_text: List[str] = Field(default=[], description="Respuesta de texto del LLM")
    tools_called: List[ToolCall] = Field(default=[], description="Herramientas llamadas")
    tools_results: List[ToolResult] = Field(default=[], description="Resultados de las herramientas")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Timestamp de la respuesta")

class ConversationMessage(BaseModel):
    role: str = Field(..., description="Rol del mensaje (user, assistant, tool, error)")
    content: Any = Field(..., description="Contenido del mensaje")
    timestamp: str = Field(..., description="Timestamp del mensaje")
    tool_name: Optional[str] = Field(None, description="Nombre de la herramienta si es un mensaje de tool")
    tool_args: Optional[Dict[str, Any]] = Field(None, description="Argumentos de la herramienta si es un mensaje de tool")

class ConversationHistoryResponse(BaseModel):
    session_id: str = Field(..., description="ID de la sesión")
    history: List[ConversationMessage] = Field(..., description="Historial de la conversación")
    total_messages: int = Field(..., description="Número total de mensajes")

class ToolInfo(BaseModel):
    name: str = Field(..., description="Nombre de la herramienta")
    description: str = Field(..., description="Descripción de la herramienta")
    input_schema: Dict[str, Any] = Field(..., description="Schema de entrada de la herramienta")

class AvailableToolsResponse(BaseModel):
    tools: List[ToolInfo] = Field(..., description="Lista de herramientas disponibles")
    total_tools: int = Field(..., description="Número total de herramientas")

class SessionListResponse(BaseModel):
    sessions: List[str] = Field(..., description="Lista de IDs de sesiones activas")
    total_sessions: int = Field(..., description="Número total de sesiones")

class ErrorResponse(BaseModel):
    error: str = Field(..., description="Mensaje de error")
    detail: Optional[str] = Field(None, description="Detalles adicionales del error")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Timestamp del error")

class HealthResponse(BaseModel):
    status: str = Field(..., description="Estado del servicio")
    mcp_server_connected: bool = Field(..., description="Estado de conexión al servidor MCP")
    active_sessions: int = Field(..., description="Número de sesiones activas")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Timestamp del health check")
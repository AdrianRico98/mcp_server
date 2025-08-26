from mcp import ClientSession, types
from mcp.client.streamable_http import streamablehttp_client
import asyncio
import mcp.types as types
from mcp.shared.session import RequestResponder
import logging
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch
from google.genai import types as types_google
from google import genai
from dotenv import load_dotenv
import os
from typing import List, Dict, Any, Optional
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('mcp_client')

load_dotenv()

class LoggingCollector:
    def __init__(self):
        self.log_messages: list[types.LoggingMessageNotificationParams] = []
    
    async def __call__(self, params: types.LoggingMessageNotificationParams) -> None:
        self.log_messages.append(params)
        logger.info("MCP Log: %s - %s", params.level, params.data)

class MCPClient:
    def __init__(self, port: int = 8000, model_id: str = "gemini-2.5-flash"):
        self.port = port
        self.model_id = model_id
        self.session: Optional[ClientSession] = None
        self.logging_collector = LoggingCollector()
        self.tools = []
        self.functions = []
        self.conversation_history = []
        self.is_connected = False
        # Context managers para manejo correcto del ciclo de vida
        self._stream_context = None
        self._session_context = None
        
    async def connect(self):
        """Conecta al servidor MCP usando la misma estructura que tu código original"""
        try:
            logger.info("Starting client...")
            
            self._stream_context = streamablehttp_client(f"http://localhost:{self.port}/mcp")
            stream_manager = await self._stream_context.__aenter__()
            read_stream, write_stream, session_callback = stream_manager
            
            self._session_context = ClientSession(
                read_stream,
                write_stream,
                logging_callback=self.logging_collector,
                message_handler=self._message_handler, #necesario para manejar los mensajes streaming de ctx del server
            )
            
            self.session = await self._session_context.__aenter__()
            
            id_before = session_callback()
            logger.info("Session ID before init: %s", id_before)
            await self.session.initialize()
            id_after = session_callback()
            logger.info("Session ID after init: %s", id_after)
            logger.info("Session initialized, ready to call tools.")
            
            # Cargar herramientas
            await self._load_tools()
            
            self.is_connected = True
            logger.info("Successfully connected to MCP server")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to MCP server: {e}")
            self.is_connected = False
            await self._cleanup_connections()
            raise

    async def disconnect(self):
        """Desconecta del servidor MCP"""
        try:
            await self._cleanup_connections()
            self.is_connected = False
            logger.info("Disconnected from MCP server")
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")

    async def _cleanup_connections(self):
        """Limpia las conexiones y context managers"""
        try:
            if self._session_context:
                await self._session_context.__aexit__(None, None, None)
                self._session_context = None
                self.session = None
            
            if self._stream_context:
                await self._stream_context.__aexit__(None, None, None)
                self._stream_context = None
        except Exception as e:
            logger.error(f"Error cleaning up connections: {e}")

    async def _message_handler(self, message) -> None:
        """Maneja mensajes del servidor MCP"""
        logger.info("Received message: %s", message)
        if isinstance(message, Exception):
            logger.error("Exception received!")
            raise message
        elif isinstance(message, types.ServerNotification):
            logger.info("NOTIFICATION: %s", message)
        elif isinstance(message, RequestResponder):
            logger.info("REQUEST_RESPONDER: %s", message)
        else:
            logger.info("SERVER_MESSAGE: %s", message)

    async def _load_tools(self):
        """Carga las herramientas disponibles del servidor MCP"""
        if not self.session:
            raise Exception("Session not initialized")
            
        tools_response = await self.session.list_tools()
        self.tools = tools_response.tools
        self.functions = []
        
        for tool in self.tools:
            function = self._convert_to_llm_tool(tool)
            self.functions.append(function)
        
        logger.info(f"Loaded {len(self.tools)} tools: {[tool.name for tool in self.tools]}")

    def _convert_to_llm_tool(self, tool):
        """Convierte una herramienta MCP al formato del sdk Google Gemini
        https://ai.google.dev/gemini-api/docs/function-calling?hl=es-419&example=meeting#function_calling_mode 
        """
        return Tool(
            function_declarations=[
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.inputSchema["properties"],
                        "required": list(tool.inputSchema.get("required", []))
                    }
                }
            ]
        )

    def _build_conversation_context(self, new_query: str) -> str:
        """Construye el contexto completo de conversación para el LLM"""
        context_parts = []
        
        # Agregar historial previo si existe
        if self.conversation_history:
            context_parts.append("Previous conversation context:")
            for msg in self.conversation_history[-10:]:  # Últimos 10 mensajes para evitar contexto muy largo
                if msg['role'] == 'user':
                    context_parts.append(f"User: {msg['content']}")
                elif msg['role'] == 'assistant':
                    context_parts.append(f"Assistant: {msg['content']}")
                elif msg['role'] == 'tool':
                    tool_name = msg.get('tool_name', 'unknown_tool')
                    context_parts.append(f"Tool {tool_name} response: {msg['content']}")
     
            context_parts.append("\n---\n")
        
        # Agregar nueva query
        context_parts.append(f"Current user query: {new_query}")
        return "\n".join(context_parts)

    def _call_llm(self, prompt: str) -> Dict[str, Any]:
        """Llama al modelo LLM y obtiene respuesta"""
        client = genai.Client(api_key=os.environ["GEMINI_TOKEN"])
        
        # Construir contexto completo de conversación
        full_context = self._build_conversation_context(prompt)
        
        config = types_google.GenerateContentConfig(
            system_instruction="""You are a helpful assistant that can use tools to help users manage their files and directories. Always provide clear and helpful responses. If you use tools, explain what you found to the user in a friendly way.""", 
            temperature=0.1, 
            tools=self.functions
        )
        
        logger.debug(f"Sending to LLM: {full_context}")
        
        response = client.models.generate_content(
            model=self.model_id,
            contents=full_context,
            config=config
        )
        # logger.info(f"prompt completo pasado al llm: {full_context}")
        # Procesar respuesta
        text_responses = []
        functions_to_call = []
        
        if hasattr(response, 'candidates') and response.candidates:
            for candidate in response.candidates:
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            text_responses.append(part.text)
                        
                        if hasattr(part, 'function_call') and part.function_call is not None:
                            name = part.function_call.name
                            args = dict(part.function_call.args)
                            functions_to_call.append({"name": name, "args": args})

        logger.debug(f"LLM Response - Text: {text_responses}, Functions: {functions_to_call}")
        
        return {
            "text": text_responses,
            "functions": functions_to_call
        }

    async def process_query(self, query: str) -> Dict[str, Any]:
        """Procesa una query manteniendo el contexto de la conversación"""
        if not self.is_connected:
            raise Exception("Client not connected to MCP server")
        
        logger.info(f"Processing query: {query}")
        
        # Agregar query al historial
        self.conversation_history.append({
            "role": "user", 
            "content": query,
            "timestamp": datetime.now().isoformat()
        })
        
        try:
            # Llamar al LLM
            llm_response = self._call_llm(query)
            
            response_data = {
                "query": query,
                "llm_text": llm_response["text"],
                "tools_called": [],
                "tools_results": []
            }
            
            # Ejecutar herramientas si el LLM las sugirió
            if llm_response["functions"]:
                logger.info(f"LLM suggested {len(llm_response['functions'])} tools to call")
                
                for func_call in llm_response["functions"]:
                    logger.info(f"Calling tool: {func_call['name']} with args: {func_call['args']}")
                    
                    # Agregar la herramienta a la lista de llamadas ANTES de ejecutarla
                    response_data["tools_called"].append(func_call)
                    
                    try:
                        # Llamar herramienta del MCP server
                        result = await self.session.call_tool(
                            func_call["name"], 
                            arguments=func_call["args"]
                        )
                        
                        response_data["tools_results"].append({
                            "tool": func_call["name"],
                            "result": result.content
                        })
                        
                        # Agregar resultado de herramienta al historial
                        self.conversation_history.append({
                            "role": "tool",
                            "tool_name": func_call["name"],
                            "tool_args": func_call["args"],
                            "content": result.content,
                            "timestamp": datetime.now().isoformat()
                        })
                        
                        logger.info(f"Tool {func_call['name']} executed successfully")
                        
                    except Exception as e:
                        logger.error(f"Error calling tool {func_call['name']}: {e}")
                        logger.error(f"Exception details: {type(e).__name__}: {str(e)}")
                        
                        error_msg = f"Error executing tool {func_call['name']}: {str(e)}"
                        response_data["tools_results"].append({
                            "tool": func_call["name"],
                            "error": error_msg
                        })
                        
                        # Agregar error al historial
                        self.conversation_history.append({
                            "role": "error",
                            "content": error_msg,
                            "timestamp": datetime.now().isoformat()
                        })
                
                # Después de ejecutar herramientas, generar respuesta final si no había texto inicial
                if not llm_response["text"] and response_data["tools_results"]:
                    logger.info("No initial text response, generating final response based on tool results")
                    
                    # Construir un prompt para generar respuesta final basada en resultados
                    tools_summary = []
                    for tool_result in response_data["tools_results"]:
                        if "error" not in tool_result:
                            result = tool_result["result"]
                            if isinstance(result, list):
                                tools_summary.append(f"Found {len(result)} items using {tool_result['tool']}")
                            else:
                                tools_summary.append(f"Tool {tool_result['tool']} returned: {str(result)[:100]}")
                    
                    final_prompt = f"Based on the tool results: {'; '.join(tools_summary)}. Please provide a helpful summary for the user about what was found."
                    final_response = self._call_llm(final_prompt)
                    
                    if final_response["text"]:
                        response_data["llm_text"] = final_response["text"]
            
            # Agregar respuesta de texto al historial si existe
            if response_data["llm_text"]:
                self.conversation_history.append({
                    "role": "assistant",
                    "content": " ".join(response_data["llm_text"]),
                    "timestamp": datetime.now().isoformat()
                })
            
            logger.info("Query processed successfully")
            return response_data
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            error_response = {
                "query": query,
                "error": str(e),
                "llm_text": [],
                "tools_called": [],
                "tools_results": []
            }
            
            # Agregar error al historial
            self.conversation_history.append({
                "role": "error",
                "content": str(e),
                "timestamp": datetime.now().isoformat()
            })
            
            return error_response

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Retorna el historial completo de la conversación"""
        return self.conversation_history.copy()

    def clear_conversation_history(self):
        """Limpia el historial de conversación"""
        self.conversation_history = []
        logger.info("Conversation history cleared")

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Retorna lista de herramientas disponibles"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            }
            for tool in self.tools
        ]

    def save_conversation_to_file(self) -> str:
        """Guarda la conversación actual en un archivo JSON"""
        if not self.conversation_history:
            return None
            
        os.makedirs("conversations", exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath = os.path.join("conversations", f"conversation_{timestamp}.json")
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.conversation_history, f, indent=2, ensure_ascii=False)
            logger.info(f"Conversation saved to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error saving conversation: {e}")
            return None
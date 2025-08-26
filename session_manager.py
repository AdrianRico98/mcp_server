import uuid
import asyncio
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from mcp_client import MCPClient
from config import settings

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Dict] = {}
        self.cleanup_task: Optional[asyncio.Task] = None
        
    async def start_cleanup_task(self):
        """Inicia la tarea de limpieza de sesiones expiradas"""
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())
            logger.info("Session cleanup task started")
    
    async def stop_cleanup_task(self):
        """Detiene la tarea de limpieza"""
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Session cleanup task stopped")
    
    async def create_session(self) -> str:
        """Crea una nueva sesión con un cliente MCP"""
        if len(self.sessions) >= settings.max_sessions:
            # Limpiar sesiones expiradas antes de crear una nueva
            await self._cleanup_expired_sessions_sync()
            if len(self.sessions) >= settings.max_sessions:
                raise Exception(f"Maximum number of sessions ({settings.max_sessions}) reached")
        
        session_id = str(uuid.uuid4())
        
        # Crear y conectar cliente MCP
        client = MCPClient(
            port=settings.mcp_server_port,
            model_id=settings.model_id
        )
        
        try:
            await client.connect()
            
            session_data = {
                "client": client,
                "created_at": datetime.now(),
                "last_activity": datetime.now(),
                "query_count": 0
            }
            
            self.sessions[session_id] = session_data
            logger.info(f"Session {session_id} created successfully")
            return session_id
            
        except Exception as e:
            logger.error(f"Error creating session {session_id}: {e}")
            try:
                await client.disconnect()
            except:
                pass
            raise Exception(f"Failed to create session: {str(e)}")
    
    def get_session(self, session_id: str) -> Optional[MCPClient]:
        """Obtiene el cliente MCP de una sesión"""
        if session_id not in self.sessions:
            return None
            
        session = self.sessions[session_id]
        
        # Verificar si la sesión ha expirado
        if self._is_session_expired(session):
            asyncio.create_task(self._cleanup_session(session_id))
            return None
            
        # Actualizar última actividad
        session["last_activity"] = datetime.now()
        return session["client"]
    
    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """Obtiene información de una sesión"""
        if session_id not in self.sessions:
            return None
            
        session = self.sessions[session_id]
        if self._is_session_expired(session):
            return None
            
        return {
            "session_id": session_id,
            "created_at": session["created_at"].isoformat(),
            "last_activity": session["last_activity"].isoformat(),
            "query_count": session["query_count"],
            "is_connected": session["client"].is_connected
        }
    
    def increment_query_count(self, session_id: str):
        """Incrementa el contador de queries de una sesión"""
        if session_id in self.sessions:
            self.sessions[session_id]["query_count"] += 1
    
    async def delete_session(self, session_id: str) -> bool:
        """Elimina una sesión específica"""
        if session_id not in self.sessions:
            return False
            
        await self._cleanup_session(session_id)
        return True
    
    def list_sessions(self) -> List[str]:
        """Lista todas las sesiones activas (no expiradas)"""
        active_sessions = []
        for session_id, session in self.sessions.items():
            if not self._is_session_expired(session):
                active_sessions.append(session_id)
        return active_sessions
    
    def get_session_count(self) -> int:
        """Retorna el número de sesiones activas"""
        return len([s for s in self.sessions.values() if not self._is_session_expired(s)])
    
    async def cleanup_all_sessions(self):
        """Limpia todas las sesiones"""
        session_ids = list(self.sessions.keys())
        for session_id in session_ids:
            await self._cleanup_session(session_id)
        logger.info("All sessions cleaned up")
    
    def _is_session_expired(self, session: Dict) -> bool:
        """Verifica si una sesión ha expirado"""
        expiry_time = session["last_activity"] + timedelta(minutes=settings.session_timeout_minutes)
        return datetime.now() > expiry_time
    
    async def _cleanup_session(self, session_id: str):
        """Limpia una sesión específica"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            try:
                if session["client"].is_connected:
                    await session["client"].disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting client for session {session_id}: {e}")
            
            del self.sessions[session_id]
            logger.info(f"Session {session_id} cleaned up")
    
    async def _cleanup_expired_sessions_sync(self):
        """Limpia sesiones expiradas de forma síncrona"""
        expired_sessions = []
        for session_id, session in self.sessions.items():
            if self._is_session_expired(session):
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            await self._cleanup_session(session_id)
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
    
    async def _cleanup_expired_sessions(self):
        """Tarea periódica de limpieza de sesiones expiradas"""
        while True:
            try:
                await asyncio.sleep(3600)  # Ejecutar cada hora
                await self._cleanup_expired_sessions_sync()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in session cleanup task: {e}")

session_manager = SessionManager()
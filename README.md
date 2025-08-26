# MCP Client API - Template Educativo

Un proyecto template para aprender a crear e integrar servidores y clientes MCP (Model Context Protocol) siguiendo buenas prácticas y el SDK oficial de Python.

## Propósito Educativo

Este proyecto sirve como **template de aprendizaje** para entender cómo:
- Crear un servidor MCP con herramientas usando FastMCP y Pydantic.
- Implementar un cliente MCP que se conecte via HTTP streamable.
- Adaptar herramientas MCP al formato requerido por SDKs de modelos de lenguaje (Gemini).
- Gestionar sesiones y mantener contexto conversacional.
- Estructurar una API backend que orquesta todo el flujo.

> [!IMPORTANT]
> Este es un **toy example** con fines educativos. No está diseñado para producción sin mejoras adicionales en seguridad, autenticación y gestión de estado.

## Arquitectura del Template

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI       │    │   MCP Client    │    │   MCP Server    │
│   Backend       │◄───┤   (Cliente)     │◄───┤  (FastMCP)      │
│   (Orchestador) │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
    ┌─────────┐              ┌─────────┐              ┌─────────┐
    │ Session │              │ Gemini  │              │ File    │
    │ Manager │              │ 2.5     │              │ Tools   │
    │(In-Mem) │              │ Flash   │              │(Pydantic)│
    └─────────┘              └─────────┘              └─────────┘
```

## Qué Aprenderás

### 1. Servidor MCP con FastMCP
- Uso del transport `streamable-http` siguiendo el [SDK oficial](https://github.com/modelcontextprotocol/python-sdk).
- Definición de herramientas con schemas Pydantic.
- Manejo de contexto con logging y mensajes informativos.
- Simulación de procesos "lentos" con `asyncio.sleep()`.

### 2. Cliente MCP Completo  
- Inicialización correcta con context managers.
- Gestión del ciclo de vida de conexiones (connect/disconnect).
- Adaptación de herramientas MCP al formato Google Gemini SDK.
- Mantenimiento de historial conversacional con contexto.

### 3. Integración con Modelos de Lenguaje
- Conversión de schemas MCP a formato `Tool` de Gemini.
- Construcción de contexto conversacional para el LLM.
- Manejo de respuestas mixtas (texto + function calls).
- Ejecución de herramientas y procesamiento de resultados.

## Instalación Rápida

> [!NOTE]
> Requiere Python 3.8+ y un token de Gemini API

```bash
# 1. Crear y activar entorno
python -m venv venv
venv\Scripts\activate  # Windows

# 2. Instalar dependencias
pip install "mcp[cli]" google-genai fastapi uvicorn python-dotenv pydantic-settings

# 3. Configurar token
echo "GEMINI_TOKEN=tu_token_aqui" > .env
```

> [!TIP]
> Obtén tu token de Gemini en [Google AI Studio](https://makersuite.google.com/app/apikey)

## Uso del Template

### Ejecutar los Componentes

**Terminal 1 - Servidor MCP:**
```bash
python server.py
```

**Terminal 2 - API Backend:**  
```bash
python backend.py
```

### Probar la Integración

```bash
# Crear sesión
curl -X POST "http://localhost:8080/session/new"

# Hacer consulta (usa el session_id devuelto)
curl -X POST "http://localhost:8080/session/{session_id}/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "¿Qué directorios principales tiene el usuario adrian.rico?"}'
```

## Componentes del Template

### Servidor MCP (`server.py`)
Implementa dos herramientas de ejemplo siguiendo FastMCP

### Cliente MCP (`mcp_client.py`) 
Demuestra la inicialización correcta siguiendo el SDK oficial

### Backend API (`backend.py`)
Template de orchestación con:
- Gestión de sesiones en memoria.
- Endpoints RESTful completos.
- Manejo de errores y logging.
- CORS configurado (muy permisivo para desarrollo).

## Herramientas de Ejemplo

### `recuperar_directorios_principales`
- **Input**: `usuario: str`  
- **Output**: `List[Directorio]`.
- **Demuestra**: Schemas tipados, logging contextual, simulación de latencia.

### `recuperar_archivos_directorio`
- **Input**: Múltiples parámetros con filtros.
- **Output**: `List[Archivo]`.
- **Demuestra**: Herramienta compleja, manejo de errores, logging progresivo.

## Limitaciones Conocidas

> [!CAUTION]
> Este template tiene limitaciones intencionadas para simplicidad educativa

### Gestión de Estado
- **Sesiones en memoria**: Se pierden al reiniciar.
- **Sin persistencia**: Historial no se guarda automáticamente.  
- **Limpieza básica**: Solo por timeout, sin métricas avanzadas.

### Seguridad
- **CORS amplio**: Permite cualquier origen (`*`)
- **Sin autenticación**: Endpoints públicos sin protección
- **Sin rate limiting**: Vulnerable a abuso de recursos
- **Logs verbosos**: Pueden filtrar información sensible
- **Sin seguridad del server**: Algunas herramientas pueden suponer una seguridad adicional a implementar en el server así como límites de calls.

### Escalabilidad  
- **Single-threaded**: Una instancia por servidor MCP
- **Sin load balancing**: No distribuye carga


## Mejoras Sugeridas

> [!TIP]
> Áreas de mejora para convertir en aplicación de producción

### Seguridad
- Implementar autenticación JWT.
- Rate limiting con Redis.
- CORS restrictivo por dominio.
- Sanitización de inputs.

### Persistencia
- Base de datos para sesiones (Redis/PostgreSQL).
- Almacenamiento de conversaciones.
- Backup y recuperación de estado.

### Monitoreo
- Métricas.
- Health checks avanzados.
- Tracing distribuido.
- Alertas automáticas.

### Escalabilidad  
- Load balancer para múltiples instancias.
- Queue system para herramientas pesadas.
- Caching inteligente.

## Estructura de Archivos

```
mcp-template/
├── server.py           # Servidor MCP con FastMCP
├── mcp_client.py       # Cliente MCP completo  
├── backend.py          # API FastAPI orchestador
├── session_manager.py  # Gestión de sesiones
├── models.py          # Schemas Pydantic
├── config.py          # Configuración centralizada
├── .env               # Variables de entorno
└── README.md          # Esta documentación
```

## Referencias y Recursos

- [MCP Python SDK Oficial](https://github.com/modelcontextprotocol/python-sdk)
- [Documentación FastMCP](https://github.com/modelcontextprotocol/python-sdk/tree/main/src/mcp/server/fastmcp)
- [Google Gemini API](https://ai.google.dev/gemini-api/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

## Contribuir al Template

Este template mejora con la comunidad:

1. Fork del repositorio
2. Experimenta con mejoras  
3. Documenta tus hallazgos
4. Comparte via Pull Request

> [!IMPORTANT]
> Mantén el enfoque educativo - prioriza claridad sobre eficiencia


**Un template educativo para dominar MCP Protocol con Python**

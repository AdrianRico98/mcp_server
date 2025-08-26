from mcp.server.fastmcp import FastMCP, Context
from mcp.types import (
    TextContent
)
import asyncio
import os
import shutil
from pathlib import Path
import fnmatch
from typing import List
from pydantic import BaseModel, Field

mcp = FastMCP("Gestión de archivos")

# Clases de pydantic para el output
class Directorio(BaseModel):
    nombre: str = Field(description="Nombre del directorio")
    ruta: str = Field(description="Path completo del directorio")
    
class Archivo(BaseModel):
    nombre: str = Field(description="Nombre del archivo")
    ruta: str = Field(description="Ruta completa del archivo")
    extension: str = Field(description="Extensión del archivo")

# Herramientas del servidor
@mcp.tool(description="Herramienta que permite recuperar los directorios principales de un usuario")
async def recuperar_directorios_principales(usuario: str, ctx: Context) -> List[Directorio]:
    await ctx.info(f"Obteniendo los directorios principales para el usuario {usuario}")
    home_dir = Path(f"/home/{usuario}") if os.name == 'posix' else Path(f"C:/Users/{usuario}")

    directorios_principales = {
        'home': str(home_dir),
        'documentos': str(home_dir / 'Documents'),
        'descargas': str(home_dir / 'Downloads'),
        'musica': str(home_dir / 'Music'),
        'videos': str(home_dir / 'Videos')
    }
    
    await ctx.info("Filtrando solo para los directorios existentes")
    await asyncio.sleep(2)  # Simulando un proceso "lento" 
    
    # Filtrar solo los directorios que existen y convertir a objetos Directorio
    directorios_existentes = []
    for nombre, ruta in directorios_principales.items():
        if Path(ruta).exists():
            directorio_obj = Directorio(nombre=nombre, ruta=ruta)
            directorios_existentes.append(directorio_obj)
    
    await ctx.info(f"Se encontraron {len(directorios_existentes)} directorios existentes")
    return directorios_existentes


@mcp.tool(description="Herramienta que permite recuperar los distintos archivos de un directorio dado")
async def recuperar_archivos_directorio(
    directorio: str, 
    incluir_subdirectorios: bool, 
    patron_busqueda: str, 
    filtro_nombre: str, 
    extension: str, 
    ctx: Context
) -> List[Archivo]:
    """
    directorio (str): Ruta del directorio a explorar
    incluir_subdirectorios (bool): Si incluir archivos de subdirectorios
    patron_busqueda (str): Patrón para buscar archivos (ej: "*.txt", "documento*", "*2024*")
    filtro_nombre (str): Texto que debe contener el nombre del archivo (búsqueda tipo LIKE)
    extension (str): Extensión específica a buscar (ej: ".pdf", ".jpg")
    """
    
    await ctx.info(f"Iniciando búsqueda de archivos en el directorio: {directorio}")
    
    archivos_resultado = []
    directorio_path = Path(directorio)
    
    if not directorio_path.exists():
        await ctx.error(f"El directorio '{directorio}' no existe")
        raise ValueError(f"El directorio '{directorio}' no existe.")
    
    if not directorio_path.is_dir():
        await ctx.error(f"'{directorio}' no es un directorio válido")
        raise ValueError(f"'{directorio}' no es un directorio.")
    
    try:
        await ctx.info(f"Configurando búsqueda - Subdirectorios: {incluir_subdirectorios}, Patrón: {patron_busqueda or 'todos'}, Filtro nombre: {filtro_nombre or 'ninguno'}, Extensión: {extension or 'cualquiera'}")
        
        # Determinar qué archivos buscar
        if patron_busqueda:
            await ctx.info(f"Aplicando patrón de búsqueda: {patron_busqueda}")
            # Usar patrón específico con glob
            if incluir_subdirectorios:
                archivos_encontrados = directorio_path.rglob(patron_busqueda)
            else:
                archivos_encontrados = directorio_path.glob(patron_busqueda)
        else:
            await ctx.info("Buscando todos los archivos")
            # Buscar todos los archivos
            if incluir_subdirectorios:
                archivos_encontrados = directorio_path.rglob('*')
            else:
                archivos_encontrados = directorio_path.iterdir()
        
        # Filtrar y procesar archivos
        archivos_procesados = 0
        for archivo in archivos_encontrados:
            if archivo.is_file():
                archivos_procesados += 1
                if archivos_procesados % 50 == 0:  # Log cada 50 archivos procesados
                    await ctx.info(f"Procesados {archivos_procesados} archivos...")
                
                # Aplicar filtros adicionales
                incluir_archivo = True
                
                # Filtro por nombre (tipo LIKE - case insensitive)
                if filtro_nombre:
                    if filtro_nombre.lower() not in archivo.name.lower():
                        incluir_archivo = False
                
                # Filtro por extensión
                if extension and incluir_archivo:
                    # Normalizar extensión (añadir punto si no lo tiene)
                    ext_normalizada = extension if extension.startswith('.') else f'.{extension}'
                    if archivo.suffix.lower() != ext_normalizada.lower():
                        incluir_archivo = False
                
                if incluir_archivo:
                    archivo_obj = Archivo(
                        nombre=archivo.name,
                        ruta=str(archivo),
                        extension=archivo.suffix
                    )
                    archivos_resultado.append(archivo_obj)
        
        await ctx.info(f"Búsqueda completada. Se encontraron {len(archivos_resultado)} archivos que coinciden con los criterios")
        
    except PermissionError as e:
        await ctx.error(f"Error de permisos al acceder al directorio: {e}")
        raise ValueError(f"Sin permisos para acceder al directorio: {directorio}")
    except Exception as e:
        await ctx.error(f"Error inesperado durante la búsqueda: {e}")
        raise ValueError(f"Error al buscar archivos: {e}")
    
    # Ordenar por nombre de archivo
    archivos_resultado.sort(key=lambda x: x.nombre.lower())
    return archivos_resultado

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
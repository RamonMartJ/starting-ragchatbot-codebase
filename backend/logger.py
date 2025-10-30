"""
Sistema de logging centralizado para el sistema RAG.

Este módulo proporciona una configuración centralizada de logging que:
- Configura formato consistente con timestamp, nivel, módulo y mensaje
- Envía logs a consola (stdout) y archivo debug.log
- Permite configurar nivel de logging vía variable de entorno LOG_LEVEL
- Proporciona función get_logger() para obtener loggers por módulo
"""

import logging
import sys
from pathlib import Path
from typing import Optional
import os


# Formato del log: [2025-10-30 14:23:45] [INFO] [module_name] mensaje
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Nivel de logging por defecto (puede ser sobreescrito por variable de entorno)
DEFAULT_LOG_LEVEL = logging.INFO

# Archivo de logs
LOG_FILE = Path(__file__).parent / "debug.log"


def get_log_level_from_env() -> int:
    """
    Obtiene el nivel de logging desde la variable de entorno LOG_LEVEL.

    Niveles válidos: DEBUG, INFO, WARNING, ERROR, CRITICAL
    Si no está definida o es inválida, retorna DEFAULT_LOG_LEVEL.

    Returns:
        int: Nivel de logging (constante de logging.*)
    """
    level_name = os.getenv("LOG_LEVEL", "").upper()
    level_mapping = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return level_mapping.get(level_name, DEFAULT_LOG_LEVEL)


def setup_logging(level: Optional[int] = None) -> None:
    """
    Configura el sistema de logging con handlers para consola y archivo.

    Workflow:
    1. Determina nivel de logging (parámetro, variable de entorno, o default)
    2. Obtiene el root logger y limpia handlers existentes
    3. Crea formatter con formato consistente
    4. Añade StreamHandler para consola (stdout)
    5. Añade FileHandler para archivo debug.log
    6. Configura nivel de logging para ambos handlers

    Args:
        level: Nivel de logging opcional. Si no se proporciona, usa variable
               de entorno LOG_LEVEL o DEFAULT_LOG_LEVEL.
    """
    # Determinar nivel de logging
    if level is None:
        level = get_log_level_from_env()

    # Obtener root logger y limpiar handlers existentes
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Limpiar handlers existentes para evitar duplicados
    root_logger.handlers.clear()

    # Crear formatter
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    # Handler para consola (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Handler para archivo
    try:
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        # Si falla la creación del archivo, solo usar consola
        root_logger.warning(f"No se pudo crear archivo de log {LOG_FILE}: {e}")

    # Log inicial indicando configuración
    root_logger.info(f"Logging configurado - nivel={logging.getLevelName(level)}, archivo={LOG_FILE}")


def get_logger(name: str) -> logging.Logger:
    """
    Obtiene un logger para un módulo específico.

    El logger hereda la configuración del root logger establecida por setup_logging().
    El nombre del módulo aparecerá en los logs para facilitar el debugging.

    Args:
        name: Nombre del módulo (típicamente __name__)

    Returns:
        logging.Logger: Logger configurado para el módulo

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Mensaje de ejemplo")
        [2025-10-30 14:23:45] [INFO] [mi_modulo] Mensaje de ejemplo
    """
    return logging.getLogger(name)


# Configurar logging automáticamente al importar el módulo
# Esto asegura que el logging esté disponible desde el inicio
setup_logging()

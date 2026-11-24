"""
===============================================================================
Module: etl/db.py
Phase: Phase 1 - Project Setup & Infrastructure
Purpose: Centralized MySQL database connection and execution helper.
Inputs: Environment variables from .env (DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME).
Outputs: SQLAlchemy Engine, PyMySQL connection, and SQL execution helpers.
Dependencies: sqlalchemy, pymysql, python-dotenv
===============================================================================
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
import pymysql

# Automatically locate the project root directory and load .env
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()


def get_db_config() -> Dict[str, Any]:
    """
    Retrieve and validate database configuration parameters from environment.
    
    Returns:
        Dict[str, Any]: Database connection settings.
        
    Raises:
        ValueError: If required configuration is missing or DB_PASSWORD is not set.
    """
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "3306"))
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    default_schema = os.getenv("DB_NAME", "staging")

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "default_schema": default_schema,
    }


def get_connection_url(schema: Optional[str] = None) -> str:
    """
    Build a SQLAlchemy connection URL using pymysql.
    
    Args:
        schema (Optional[str]): Database schema to connect to. Defaults to None.
        
    Returns:
        str: SQLAlchemy connection string.
    """
    cfg = get_db_config()
    db_part = f"/{schema}" if schema else ""
    # Safe URL construction (pymysql driver)
    return f"mysql+pymysql://{cfg['user']}:{cfg['password']}@{cfg['host']}:{cfg['port']}{db_part}?charset=utf8mb4"


def get_engine(schema: Optional[str] = None) -> Engine:
    """
    Create a SQLAlchemy Engine with connection pooling.
    
    Args:
        schema (Optional[str]): Database schema to connect to.
        
    Returns:
        Engine: SQLAlchemy Engine instance.
    """
    url = get_connection_url(schema)
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False
    )


def get_raw_connection(schema: Optional[str] = None) -> pymysql.connections.Connection:
    """
    Create a raw PyMySQL connection for bulk operations or fast DDL execution.
    
    Args:
        schema (Optional[str]): Database schema to connect to.
        
    Returns:
        pymysql.Connection: Active database connection.
    """
    cfg = get_db_config()
    return pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=schema,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )


def test_connection() -> Dict[str, Any]:
    """
    Test database connectivity and return MySQL server details.
    
    Returns:
        Dict[str, Any]: Status flag, message, and server version.
    """
    cfg = get_db_config()
    if not cfg["password"] and cfg["password"] != "":
        # Prompt if empty
        pass
    
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT VERSION() AS version, CURRENT_USER() AS db_user, @@hostname AS host_name;"))
            row = result.mappings().fetchone()
            return {
                "success": True,
                "version": row["version"],
                "current_user": row["db_user"],
                "hostname": row["host_name"],
                "message": "Successfully connected to MySQL database."
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to connect to MySQL. Please check .env credentials."
        }


def execute_sql_file(file_path: Path, schema: Optional[str] = None) -> bool:
    """
    Execute multiple SQL statements from a file using PyMySQL.
    
    Args:
        file_path (Path): Path to the .sql file.
        schema (Optional[str]): Target schema if applicable.
        
    Returns:
        bool: True if execution succeeded.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"SQL file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Split by semicolon while ignoring comments
    statements = []
    current_stmt = []
    
    for line in content.splitlines():
        trimmed = line.strip()
        if trimmed.startswith("--") or not trimmed:
            continue
        current_stmt.append(line)
        if trimmed.endswith(";"):
            stmt_text = "\n".join(current_stmt).strip()
            if stmt_text:
                statements.append(stmt_text)
            current_stmt = []

    conn = get_raw_connection(schema=schema)
    try:
        with conn.cursor() as cursor:
            for stmt in statements:
                if stmt:
                    cursor.execute(stmt)
        return True
    finally:
        conn.close()


if __name__ == "__main__":
    res = test_connection()
    if res["success"]:
        print(f"[SUCCESS] {res['message']}")
        print(f"Server Version: {res['version']}")
        print(f"Logged in as:   {res['current_user']}")
    else:
        print(f"[ERROR] {res['message']}")
        print(f"Details: {res.get('error')}")

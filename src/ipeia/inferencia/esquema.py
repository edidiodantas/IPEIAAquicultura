"""Converte modelos Pydantic no esquema JSON enviado ao motor de linguagem."""

from typing import Any

from pydantic import BaseModel


def esquema_json(modelo: type[BaseModel]) -> dict[str, Any]:
    """Esquema para decodificação guiada. O `title` identifica a tarefa."""
    return modelo.model_json_schema()

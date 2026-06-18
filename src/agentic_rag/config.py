"""Central configuration loaded from environment / .env.

All tunables live here so the rest of the codebase never reads ``os.environ``
directly. Values come from a ``.env`` file (see ``.env.example``) or the process
environment. A single provider (OpenAI) powers both the agent LLM and the dense
embeddings, so only one API key is required.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_project_root() -> Path:
    """Locate the project root by walking up to the nearest ``pyproject.toml``.

    Works whether the package is imported from the source tree (editable
    install / ``PYTHONPATH=src``) or copied into ``site-packages`` (regular
    install); in the latter case there is no ``pyproject.toml`` above the
    package, so we fall back to the current working directory — where the user
    runs the CLI and keeps their ``.env``.
    """
    here = Path(__file__).resolve()
    for parent in (here.parent, *here.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


_PROJECT_ROOT = _find_project_root()


class Settings(BaseSettings):
    """Typed application settings.

    Attributes are populated from environment variables (case-insensitive) or a
    ``.env`` file at the project root.
    """

    model_config = SettingsConfigDict(
        env_file=_PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM + Embeddings (OpenAI) ---
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")

    # --- Retrieval tuning ---
    retrieval_top_k: int = Field(default=8, alias="RETRIEVAL_TOP_K")
    rrf_k: int = Field(default=60, alias="RRF_K")

    # --- Memory ---
    memory_path: Path = Field(default=_PROJECT_ROOT / "data" / "memory.jsonl", alias="MEMORY_PATH")

    def require_openai(self) -> str:
        """Return the OpenAI key or raise a clear, actionable error."""
        if not self.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and add your "
                "key (https://platform.openai.com/api-keys)."
            )
        return self.openai_api_key


@cache
def get_settings() -> Settings:
    """Return a process-wide cached :class:`Settings` instance."""
    return Settings()

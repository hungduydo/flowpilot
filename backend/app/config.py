from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    app_name: str = "LLM Workflow Builder"
    app_env: str = "development"
    log_level: str = "debug"

    # Database
    database_url: str = "postgresql+asyncpg://llmworkflow:llmworkflow123@localhost:5433/llm_workflow"

    # Redis
    redis_url: str = "redis://localhost:6380/0"

    # LLM Provider: "openai" | "anthropic" | "ollama"
    llm_provider: str = "ollama"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"

    # Anthropic Claude
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # Ollama (Local LLM)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"

    # n8n
    n8n_base_url: str = "http://localhost:5678"
    n8n_public_url: str = "http://localhost:5678"  # URL for browser access
    n8n_api_key: str = ""

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8100

    # LLM Settings
    max_retries: int = 3
    max_context_tokens: int = 100000
    max_output_tokens: int = 4096

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()

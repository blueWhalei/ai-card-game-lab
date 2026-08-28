"""Application configuration via Pydantic Settings.

Loads values from environment variables and .env file.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    app_name: str = "AI Card Game Lab"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    ollama_base_url: str = "http://localhost:11434"

    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    # deepseek-v4-flash：默认（成本/延迟友好）；需要更强推理可用 deepseek-v4-pro
    deepseek_model: str = "deepseek-v4-flash"

    kimi_api_key: str = ""
    kimi_base_url: str = "https://api.moonshot.cn/v1"

    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimax.chat/v1/text/chatcompletion_v2"

    zhipu_api_key: str = ""
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"

    yi_api_key: str = ""
    yi_base_url: str = "https://api.lingyiwanwu.com/v1"

    baichuan_api_key: str = ""
    baichuan_base_url: str = "https://api.baichuan-ai.com/v1"

    data_dir: str = str(_PROJECT_ROOT / "data")
    sqlite_path: str = str(_PROJECT_ROOT / "data" / "db" / "app.db")
    models_dir: str = str(_PROJECT_ROOT / "models")

    # Default True so fresh installs work without torch; set False after
    # `poetry install --with training` to enable real PEFT LoRA.
    training_use_mock: bool = True

    config_dir: str = str(_PROJECT_ROOT / "config")

    prompt_version: str = "v1"
    prompt_ab_test_enabled: bool = False
    prompt_ab_test_ratio: float = 0.5

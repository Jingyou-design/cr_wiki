"""Service and DeepSeek configuration loaded from environment variables."""

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()


class Settings(BaseSettings):
    """Environment-backed company Wiki service settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    deepseek_api_key: str = Field(
        default="",
        validation_alias="DEEPSEEK_API_KEY",
        description="DeepSeek API 密钥",
        repr=False,
    )
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com/v1",
        validation_alias="DEEPSEEK_BASE_URL",
        description="DeepSeek API 地址",
    )
    deepseek_model: str = Field(
        default="deepseek-v4-flash",
        validation_alias="DEEPSEEK_MODEL",
        description="DeepSeek 模型名称",
    )
    deepseek_temperature: float = Field(
        default=0.0,
        validation_alias="DEEPSEEK_TEMPERATURE",
        description="DeepSeek 生成温度",
    )
    mineru_api_token: str = Field(
        default="",
        validation_alias="MINERU_API_TOKEN",
        description="MinerU 精准解析 API Token",
        repr=False,
    )
    mineru_base_url: str = Field(
        default="https://mineru.net",
        validation_alias="MINERU_BASE_URL",
        description="MinerU API 地址",
    )
    mineru_model_version: str = Field(
        default="vlm",
        validation_alias="MINERU_MODEL_VERSION",
        description="MinerU 解析模型版本",
    )
    mineru_language: str = Field(
        default="ch",
        validation_alias="MINERU_LANGUAGE",
        description="MinerU 文档语言",
    )
    mineru_enable_table: bool = Field(
        default=True,
        validation_alias="MINERU_ENABLE_TABLE",
        description="是否识别表格",
    )
    mineru_enable_formula: bool = Field(
        default=False,
        validation_alias="MINERU_ENABLE_FORMULA",
        description="是否识别公式",
    )
    mineru_is_ocr: bool = Field(
        default=True,
        validation_alias="MINERU_IS_OCR",
        description="是否为 PDF 启用 OCR",
    )
    mineru_request_timeout_seconds: float = Field(
        default=120.0,
        gt=0,
        validation_alias="MINERU_REQUEST_TIMEOUT_SECONDS",
        description="MinerU 单次 HTTP 请求超时秒数",
    )
    mineru_poll_interval_seconds: float = Field(
        default=3.0,
        gt=0,
        validation_alias="MINERU_POLL_INTERVAL_SECONDS",
        description="MinerU 状态轮询间隔秒数",
    )
    mineru_poll_timeout_seconds: float = Field(
        default=1800.0,
        gt=0,
        validation_alias="MINERU_POLL_TIMEOUT_SECONDS",
        description="MinerU 整批解析等待上限秒数",
    )
    wiki_project_root: Path = Field(
        default_factory=Path.cwd,
        validation_alias="WIKI_PROJECT_ROOT",
        description="公司 Wiki 项目根目录",
    )
    access_control_file: Path = Field(
        default=Path("data/access-control.json"),
        validation_alias="ACCESS_CONTROL_FILE",
        description="用户、部门和访问路径 JSON 配置",
    )
    auth_cookie_name: str = Field(
        default="cr_wiki_session",
        validation_alias="AUTH_COOKIE_NAME",
        description="登录会话 Cookie 名称",
    )
    auth_session_ttl_seconds: int = Field(
        default=28800,
        ge=300,
        le=604800,
        validation_alias="AUTH_SESSION_TTL_SECONDS",
        description="登录会话有效期（秒）",
    )
    auth_cookie_secure: bool = Field(
        default=False,
        validation_alias="AUTH_COOKIE_SECURE",
        description="是否仅通过 HTTPS 发送登录 Cookie",
    )


settings = Settings()

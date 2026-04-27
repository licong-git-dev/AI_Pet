"""
PetPal - AI宠物社交服务平台
配置模块

使用pydantic-settings从环境变量和.env文件加载配置
敏感配置项必须通过环境变量配置，不允许使用默认值
"""
import sys
import warnings
from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator, model_validator
from urllib.parse import urlparse
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类

    配置优先级: 环境变量 > .env文件 > 默认值
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # 环境变量名不区分大小写
        extra="ignore",  # 忽略额外的环境变量
    )

    # ==================== 应用配置 ====================
    app_name: str = "PetPal"
    app_env: str = "development"  # development / staging / production
    debug: bool = True
    secret_key: str = "change-this-in-production"
    app_base_url: str = "http://localhost:8000"

    # ==================== 数据库配置 ====================
    database_url: str = "sqlite:///./petpal.db"
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # ==================== Redis配置 ====================
    redis_url: str = "redis://localhost:6379/0"

    # ==================== JWT配置 ====================
    jwt_secret_key: Optional[str] = None  # 必须配置
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30  # Access Token有效期30分钟
    jwt_refresh_token_expire_days: int = 30  # Refresh Token有效期30天

    # ==================== AI服务配置 ====================
    # OpenAI配置 (可选)
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # Google Gemini 配置 (可选)
    gemini_api_key: Optional[str] = None
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_model: str = "gemini-flash-latest"

    # 阿里云通义千问配置 (AI诊断功能必须)
    dashscope_api_key: Optional[str] = None  # 必须配置
    dashscope_vl_model: str = "qwen-vl-max"
    dashscope_chat_model: str = "qwen-max"

    # ==================== 通用 LLM 网关配置（记忆抽取 / 周摘要 / 画像构建） ====================
    # 主提供商，可选: gemini / openai / dashscope
    llm_primary_provider: str = "gemini"
    # 失败时自动切换的次级提供商
    llm_fallback_provider: Optional[str] = "openai"
    # 单次请求超时
    llm_timeout_seconds: float = 20.0
    # 创意度（0-1），低值用于结构化抽取，高值用于摘要
    llm_default_temperature: float = 0.2
    llm_summarize_temperature: float = 0.5
    # 单次最大输出 tokens
    llm_max_output_tokens: int = 1024

    # ==================== 阿里云短信配置 ====================
    aliyun_sms_access_key_id: Optional[str] = None
    aliyun_sms_access_key_secret: Optional[str] = None
    aliyun_sms_sign_name: str = "PetPal"
    aliyun_sms_template_code: Optional[str] = None

    # ==================== 文件存储配置 ====================
    upload_dir: str = "./uploads"
    max_upload_size: int = 10485760  # 10MB

    # 阿里云OSS配置 (可选)
    oss_access_key_id: Optional[str] = None
    oss_access_key_secret: Optional[str] = None
    oss_bucket_name: Optional[str] = None
    oss_endpoint: str = "oss-cn-hangzhou.aliyuncs.com"
    oss_domain: Optional[str] = None

    # ==================== CORS配置 ====================
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173"]

    # ==================== 宠物数字分身配置 ====================
    dashscope_wanx_model: str = "wanx-v1"
    pet_chat_temperature: float = 0.85
    sticker_daily_limit: int = 10
    personality_daily_limit: int = 5

    # ==================== Celery配置 ====================
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ==================== MQTT（桌宠 / 全息设备 fan-out） ====================
    mqtt_enabled: bool = False
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    mqtt_client_id_prefix: str = "petpal-backend"
    mqtt_keepalive: int = 60

    # ==================== 日志配置 ====================
    log_level: str = "INFO"
    log_file: Optional[str] = None

    # ==================== 监控配置 ====================
    sentry_dsn: Optional[str] = None

    # ==================== 支付配置 ====================
    # 支付宝
    alipay_app_id: Optional[str] = None
    alipay_private_key: Optional[str] = None
    alipay_public_key: Optional[str] = None

    # 微信支付
    wechat_app_id: Optional[str] = None
    wechat_mch_id: Optional[str] = None
    wechat_api_key: Optional[str] = None
    wechat_cert_path: Optional[str] = None

    # ==================== 第三方登录配置 ====================
    wechat_login_app_id: Optional[str] = None
    wechat_login_app_secret: Optional[str] = None

    apple_client_id: Optional[str] = None
    apple_team_id: Optional[str] = None
    apple_key_id: Optional[str] = None
    apple_private_key: Optional[str] = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """解析CORS origins配置"""
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("app_base_url", mode="before")
    @classmethod
    def normalize_app_base_url(cls, v):
        """规范化应用基础地址"""
        if not isinstance(v, str):
            raise ValueError("APP_BASE_URL 必须是字符串")

        base_url = v.strip().rstrip("/")
        parsed = urlparse(base_url)
        if not base_url or parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("APP_BASE_URL 必须是有效的 http(s) URL")

        return base_url

    @model_validator(mode="after")
    def validate_required_settings(self):
        """验证必需的配置项"""
        missing_configs = []
        warnings_list = []

        # 生产环境必须配置的项
        if self.app_env == "production":
            if not self.jwt_secret_key:
                missing_configs.append("JWT_SECRET_KEY")
            if self.secret_key == "change-this-in-production":
                missing_configs.append("SECRET_KEY")
            if not self.dashscope_api_key:
                warnings_list.append("DASHSCOPE_API_KEY (AI诊断功能将不可用)")

        # 开发环境的警告
        if self.app_env == "development":
            if not self.jwt_secret_key:
                warnings_list.append("JWT_SECRET_KEY 未配置，使用默认值")
                # 开发环境使用默认值
                object.__setattr__(self, 'jwt_secret_key', 'dev-jwt-secret-key-not-for-production')
            if not self.dashscope_api_key:
                warnings_list.append("DASHSCOPE_API_KEY 未配置，AI诊断功能将不可用")

        # 输出警告
        for warning in warnings_list:
            warnings.warn(f"[Config Warning] {warning}", UserWarning)

        # 生产环境缺少必要配置时退出
        if missing_configs and self.app_env == "production":
            error_msg = f"生产环境缺少必要配置: {', '.join(missing_configs)}"
            print(f"[FATAL ERROR] {error_msg}", file=sys.stderr)
            sys.exit(1)

        return self

    @property
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.app_env == "development"

    @property
    def sms_enabled(self) -> bool:
        """短信服务是否可用"""
        return all([
            self.aliyun_sms_access_key_id,
            self.aliyun_sms_access_key_secret,
            self.aliyun_sms_template_code
        ])

    @property
    def oss_enabled(self) -> bool:
        """OSS存储是否可用"""
        return all([
            self.oss_access_key_id,
            self.oss_access_key_secret,
            self.oss_bucket_name
        ])

    @property
    def ai_diagnosis_enabled(self) -> bool:
        """AI诊断功能是否可用"""
        return bool(self.dashscope_api_key)

    @property
    def llm_enabled(self) -> bool:
        """通用 LLM 网关是否可用（任一提供商有 key 即视为可用）"""
        return bool(self.gemini_api_key or self.openai_api_key or self.dashscope_api_key)


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例

    使用lru_cache确保整个应用生命周期内只创建一个配置实例
    """
    return Settings()


# 全局配置实例
settings = get_settings()


def print_config_status():
    """打印配置状态（用于启动时检查）"""
    print("=" * 50)
    print(f"PetPal 配置状态")
    print("=" * 50)
    print(f"环境: {settings.app_env}")
    print(f"调试模式: {settings.debug}")
    print(f"数据库: {settings.database_url.split('@')[-1] if '@' in settings.database_url else settings.database_url}")
    print(f"Redis: {settings.redis_url}")
    print(f"JWT配置: {'已配置' if settings.jwt_secret_key else '未配置'}")
    print(f"AI诊断: {'已启用' if settings.ai_diagnosis_enabled else '未启用'}")
    print(f"短信服务: {'已启用' if settings.sms_enabled else '未启用'}")
    print(f"OSS存储: {'已启用' if settings.oss_enabled else '未启用'}")
    print("=" * 50)

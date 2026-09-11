from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "quanlykeyveo3-api"
    API_V1_STR: str = "/api/v1"
    
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Supabase / DB
    DATABASE_URL: str
    
    # License Keys
    JWT_PRIVATE_KEY: str
    JWT_PUBLIC_KEY: str
    
    # System Config
    MIN_VERSION: str = "1.0.0"
    MAINTENANCE_MODE: bool = False

    # Security & Admin Config
    ADMIN_DEFAULT_EMAIL: str = "vubinhan094@gmail.com"
    ADMIN_DEFAULT_PASSWORD: str = "Vubinhan336!@#"
    ADMIN_SECURITY_PIN: str = "336999"  # Mã khóa cấp 2 bảo mật tối cao (Master PIN)
    SEPAY_API_KEY: Optional[str] = None
    ALLOWED_ORIGINS: str = "*"
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 5
    RATE_LIMIT_VERIFY_PER_MINUTE: int = 30
    RATE_LIMIT_HEARTBEAT_PER_MINUTE: int = 60

    # 2FA & Telegram Security Alert
    ENABLE_2FA_TELEGRAM: bool = True
    TELEGRAM_BOT_TOKEN: str = "8957341354:AAHA6bLk-Z3_WH6RaRRszijmymQQYoGbxvM"
    TELEGRAM_ADMIN_CHAT_ID: int = 7956637890
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()

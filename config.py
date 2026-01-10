"""
配置文件
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# LLM 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
LLM_MAX_TOKENS = os.getenv("LLM_MAX_TOKENS", "20000")
DEEPSEEK_API_BASE = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))

# 文档处理配置
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
TOP_K_RESULTS = int(os.getenv("TOP_K_RESULTS", "5"))
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))

# 支持的文件扩展名
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc"}

# 向量数据库配置
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "paper_reader")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# API 配置
_cors_raw = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
if _cors_raw:
    CORS_ALLOW_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()]
else:
    # 本地开发默认值（避免 allow_credentials=True 与 "*" 组合导致浏览器拒绝）
    CORS_ALLOW_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]

# 数据库配置
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "sqlite:///./paper_reader.db"
)

# JWT 配置
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")

# 生产环境安全检查
if os.getenv("ENVIRONMENT", "development") == "production":
    if SECRET_KEY == "dev-secret-key-change-me":
        raise ValueError("CRITICAL: 生产环境必须设置强 SECRET_KEY，不能使用默认值！")

ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# 📚 DeepinReader — 论文阅读多智能体系统

基于 **LangChain + LangGraph** 构建的智能论文分析与问答系统。上传论文 PDF / Word，AI 自动分析结构、生成摘要、智能问答、全文翻译、思维导图、代码生成、多文档对比。

## ✨ 核心功能

| 功能 | 说明 |
|------|------|
| 📄 **文档解析** | 支持 PDF / Word 格式，智能提取文档内容与结构 |
| 📊 **智能分析** | 自动生成结构化分析报告（方法、结果、创新点），支持流式输出 |
| 💬 **智能问答** | 基于 RAG + Plan-and-Solve 策略精准回答问题，支持流式对话 |
| 🌐 **全文翻译** | 逐段翻译保持学术风格，支持划词翻译与原文对照 |
| 🧠 **思维导图** | 自动生成论文结构思维导图（Mermaid 格式） |
| 💻 **代码生成** | 根据论文内容生成指定框架（PyTorch 等）的代码实现 |
| 🔍 **智能搜索** | 基于 DuckDuckGo 的联网搜索，查找相关研究 |
| 📑 **多文档对比** | 支持 2-3 篇论文的深度对比分析 |
| 📥 **导出报告** | 一键导出 Word 格式分析报告（含封面与格式排版） |
| 📚 **历史记录** | 持久化分析记录与聊天记录，随时回顾 |
| 📂 **多文档管理** | 同时管理多个文档，自由切换 |

## 🏗️ 技术架构

```
┌─────────────────┐      ┌───────────────────────────────────────┐
│  Vue 3 前端       │─────▶│       FastAPI 后端 (api.py)             │
│  Vite + Tailwind │◀─────│                                       │
│                  │  WS  │  ┌───────────────────────────────┐    │
│  9 个功能页面      │◀────▶│  │  LangGraph Coordinator         │    │
└─────────────────┘      │  │  ┌──────────┐ ┌────────────┐  │    │
                         │  │  │  Parser   │ │ Summarizer │  │    │
                         │  │  │  Agent    │ │   Agent    │  │    │
                         │  │  └──────────┘ └────────────┘  │    │
                         │  │  ┌──────────┐                 │    │
                         │  │  │  QA      │                 │    │
                         │  │  │  Agent   │                 │    │
                         │  │  └──────────┘                 │    │
                         │  └───────────────────────────────┘    │
                         │                                       │
                         │  ChromaDB + BM25（混合检索）             │
                         │  DeepSeek API (LLM)                   │
                         │  Sentence-Transformers (Embedding)    │
                         └───────────────────────────────────────┘
```

**通信方式**：
- **REST API**：文档上传、历史管理、文档切换等
- **SSE (Server-Sent Events)**：流式分析、流式翻译、流式对比
- **WebSocket**：统一多路复用端点，支持流式分析 / 问答 / 翻译 / 代码生成 / 对比，可随时取消任务

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-username/PaperReader.git
cd PaperReader
```

### 2. 安装后端依赖

```bash
# 推荐使用 Python 3.10+
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `env.example` 为 `.env` 并填入你的 DeepSeek API Key：

```bash
cp env.example .env
```

```ini
# .env
DEEPSEEK_API_KEY=your-actual-api-key-here
```

> 💡 获取 API Key：https://platform.deepseek.com/

### 4. 安装前端依赖

```bash
cd frontend
npm install
```

### 5. 启动项目

**方式一：使用启动脚本（Windows）**
```bash
start.bat
```

**方式二：手动启动**

```bash
# 终端 1：启动后端
python -m uvicorn api:app --host 0.0.0.0 --port 8001

# 终端 2：启动前端
cd frontend
npm run dev
```

**方式三：Docker 部署**

```bash
docker build -t paper-reader .
docker run -d -p 8001:8001 --env-file .env paper-reader
```

### 6. 打开浏览器

访问 http://localhost:3000 即可使用。

## 📂 项目结构

```
PaperReader/
├── api.py                  # FastAPI 主入口（28+ API 端点 + WebSocket）
├── config.py               # 配置文件（API Key、模型参数等）
├── requirements.txt        # Python 依赖
├── env.example             # 环境变量模板
├── Dockerfile              # Docker 容器化部署
├── start.bat               # Windows 一键启动脚本
│
├── agents/                 # 多智能体模块
│   ├── coordinator.py      # LangGraph 工作流协调器（含流式分析、代码生成）
│   ├── parser_agent.py     # 文档解析 Agent
│   ├── summarizer_agent.py # 摘要生成 Agent
│   └── qa_agent.py         # 智能问答 Agent（RAG + Plan-and-Solve）
│
├── services/               # 后端服务
│   ├── llm_service.py      # DeepSeek LLM 封装（同步 / 流式）
│   ├── vector_store.py     # ChromaDB 向量存储 + BM25 混合检索
│   ├── chroma_client.py    # ChromaDB 客户端单例管理
│   ├── document_parser.py  # PDF / Word 文档解析（PyMuPDF + python-docx）
│   ├── history_store.py    # 分析历史 & 聊天记录持久化
│   ├── text_utils.py       # 文本处理工具
│   └── tools.py            # 联网搜索工具（DuckDuckGo）
│
├── prompts/                # Prompt 模板
│   └── templates.py        # 结构分析、摘要、问答、代码生成等 Prompt
│
└── frontend/               # Vue 3 前端
    ├── package.json        # 前端依赖（v2.0.0）
    ├── vite.config.js      # Vite 构建配置
    ├── tailwind.config.js  # Tailwind CSS 配置
    └── src/
        ├── App.vue         # 主布局 & 路由
        ├── main.js         # 应用入口
        ├── store.js        # 状态管理（localStorage 持久化）
        ├── style.css       # 全局样式
        ├── api/index.js    # API 客户端（axios）
        ├── utils/
        │   ├── markdown.js # Markdown 渲染工具
        │   └── websocket.js# WebSocket 客户端封装
        └── views/          # 页面组件
            ├── Home.vue    # 首页（文档上传 & 管理）
            ├── Analyze.vue # 分析页（流式分析 + 报告导出）
            ├── Chat.vue    # 智能问答
            ├── Translate.vue # 全文翻译
            ├── MindMap.vue # 思维导图
            ├── CodeGen.vue # 代码生成
            ├── Search.vue  # 智能搜索
            ├── Compare.vue # 多文档对比
            └── History.vue # 历史记录
```

## ⚙️ 配置说明

| 环境变量 | 必填 | 默认值 | 说明 |
|----------|:---:|--------|------|
| `DEEPSEEK_API_KEY` | ✅ | — | DeepSeek API 密钥 |
| `DEEPSEEK_API_BASE` | ❌ | `https://api.deepseek.com` | API 基础地址（可切换兼容端点） |
| `DEEPSEEK_MODEL` | ❌ | `deepseek-chat` | 使用的模型名称 |
| `LLM_MAX_TOKENS` | ❌ | `20000` | LLM 最大输出 Token 数 |
| `LLM_TEMPERATURE` | ❌ | `0.7` | LLM 温度参数 |
| `CHUNK_SIZE` | ❌ | `500` | 文档分块大小 |
| `CHUNK_OVERLAP` | ❌ | `50` | 文档分块重叠 |
| `TOP_K_RESULTS` | ❌ | `5` | 检索返回的 Top-K 数量 |
| `MAX_FILE_SIZE_MB` | ❌ | `50` | 最大上传文件大小 (MB) |
| `CHROMA_PERSIST_DIR` | ❌ | `./chroma_db` | 向量数据库存储路径 |
| `COLLECTION_NAME` | ❌ | `paper_reader` | ChromaDB 集合名称 |
| `EMBEDDING_MODEL` | ❌ | `all-MiniLM-L6-v2` | Sentence-Transformers 嵌入模型 |
| `CORS_ALLOW_ORIGINS` | ❌ | `localhost:3000,3001` | 前端允许的域名（逗号分隔） |

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | Vue 3 + Vite + Tailwind CSS + Vue Router |
| **组件库** | Lucide Icons, Mermaid, Highlight.js, Marked, vue-pdf-embed |
| **后端** | FastAPI + Uvicorn |
| **AI 框架** | LangChain + LangGraph |
| **LLM** | DeepSeek API (OpenAI 兼容) |
| **向量数据库** | ChromaDB + Sentence-Transformers |
| **检索策略** | 向量检索 + BM25 混合检索 |
| **文档解析** | PyMuPDF (PDF) + python-docx (Word) |
| **搜索引擎** | DuckDuckGo |
| **部署** | Docker |

## 📄 许可证

[木兰宽松许可证，第2版 (Mulan PSL v2)](LICENSE)

"""
论文阅读多智能体系统 - FastAPI 后端 API
"""
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import shutil
import uuid
import sys
import json
import asyncio
from datetime import datetime, timedelta
import logging

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.coordinator import PaperReaderCoordinator
from services.history_store import HistoryStoreService
from config import SUPPORTED_EXTENSIONS, MAX_FILE_SIZE_MB, CORS_ALLOW_ORIGINS, ACCESS_TOKEN_EXPIRE_MINUTES
from services.database import get_db, User
from services.auth_service import AuthService
from services.session_service import session_store
from services.quota_service import QuotaService

logger = logging.getLogger(__name__)

app = FastAPI(
    title="论文阅读助手 API",
    description="基于 LangChain + LangGraph 构建的智能论文分析与问答系统",
    version="2.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 确保上传目录存在
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 挂载静态文件目录，用于访问上传的 PDF
app.mount("/api/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# 初始化认证服务
auth_service = AuthService()

# OAuth2 Scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

# 会话状态 (纯数据)
class SessionState:
    def __init__(self, session_id: str, data: Dict[str, Any]):
        self.session_id = session_id
        self.data = data
        
    @property
    def current_document_id(self) -> Optional[str]:
        return self.data.get("current_document_id")
        
    @current_document_id.setter
    def current_document_id(self, value: Optional[str]):
        self.data["current_document_id"] = value
        
    @property
    def is_document_loaded(self) -> bool:
        return self.data.get("is_document_loaded", False)
        
    @is_document_loaded.setter
    def is_document_loaded(self, value: bool):
        self.data["is_document_loaded"] = value
        
    @property
    def current_summary(self) -> str:
        return self.data.get("current_summary", "")
        
    @current_summary.setter
    def current_summary(self, value: str):
        self.data["current_summary"] = value
        
    @property
    def current_structure(self) -> str:
        return self.data.get("current_structure", "")
        
    @current_structure.setter
    def current_structure(self, value: str):
        self.data["current_structure"] = value
        
    @property
    def document_info(self) -> dict:
        return self.data.get("document_info", {})
        
    @document_info.setter
    def document_info(self, value: dict):
        self.data["document_info"] = value
        
    @property
    def current_history_id(self) -> Optional[str]:
        return self.data.get("current_history_id")
        
    @current_history_id.setter
    def current_history_id(self, value: Optional[str]):
        self.data["current_history_id"] = value
        
    def save(self):
        """保存状态到 Store"""
        session_store.save(self.session_id, self.data)

# 依赖注入：获取当前会话状态
async def get_session_state(x_session_id: Optional[str] = Header(None)) -> SessionState:
    session_id = x_session_id or "default"
    data = session_store.load(session_id)
    return SessionState(session_id, data)

# 依赖注入：获取 Coordinator (按需初始化)
async def get_coordinator(state: SessionState = Depends(get_session_state)) -> PaperReaderCoordinator:
    coordinator = PaperReaderCoordinator()
    
    # 如果会话中有文档，恢复上下文
    if state.current_document_id:
        try:
            # 加载向量存储
            loaded = coordinator.vector_store.load_collection(state.current_document_id)
            if loaded:
                # 恢复 QA Agent 上下文
                doc_info = state.document_info
                coordinator.qa_agent.set_document_context(
                    doc_id=state.current_document_id,
                    paper_title=doc_info.get("title", ""),
                    paper_summary=state.current_summary[:500]
                )
        except Exception as e:
            logger.warning(f"恢复 Coordinator 上下文失败: {e}")
            
    return coordinator

# 请求/响应模型
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    success: bool
    answer: str
    source_chunks: List[str] = []

class AnalysisResponse(BaseModel):
    success: bool
    status: str
    document_info: dict = {}
    structure: str = ""
    summary: str = ""
    error: str = ""

class DocumentInfoResponse(BaseModel):
    is_loaded: bool
    info: dict = {}
    structure: str = ""
    summary: str = ""

class HistoryItem(BaseModel):
    id: str
    filename: str
    title: str = ""
    file_type: str = ""
    page_count: int = 0
    word_count: int = 0
    processing_time: float = 0
    analyzed_at: str = ""

class HistoryListResponse(BaseModel):
    history: List[HistoryItem] = []
    current_id: Optional[str] = None

class ChatHistoryItem(BaseModel):
    id: str
    role: str
    content: str
    timestamp: str = ""
    source_chunks: List[str] = []

# 用户相关模型
class RegisterRequest(BaseModel):
    phone: str
    password: str
    nickname: str
    avatar: Optional[str] = None
    age: Optional[int] = None
    profession: Optional[str] = None

class LoginRequest(BaseModel):
    phone: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class UserProfileUpdateRequest(BaseModel):
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    age: Optional[int] = None
    profession: Optional[str] = None

def get_current_user(token: str = Depends(oauth2_scheme)):
    """获取当前用户"""
    payload = auth_service.decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload

@app.get("/")
async def root():
    return {"message": "论文阅读助手 API", "version": "2.0.0"}

@app.get("/api/status")
async def get_status(state: SessionState = Depends(get_session_state)):
    """获取系统状态"""
    return {
        "is_document_loaded": state.is_document_loaded,
        "has_coordinator": True # Coordinator 是无状态按需加载的
    }

@app.get("/api/document", response_model=DocumentInfoResponse)
async def get_document_info(state: SessionState = Depends(get_session_state)):
    """获取当前文档信息"""
    return DocumentInfoResponse(
        is_loaded=state.is_document_loaded,
        info=state.document_info,
        structure=state.current_structure,
        summary=state.current_summary
    )

@app.post("/api/upload", response_model=AnalysisResponse)
async def upload_and_analyze(
    file: UploadFile = File(...), 
    state: SessionState = Depends(get_session_state),
    coordinator: PaperReaderCoordinator = Depends(get_coordinator),
    current_user: dict = Depends(get_current_user), # 强制登录
    db = Depends(get_db)
):
    """上传并分析论文"""
    
    try:
        # 0. 检查配额
        user_id = int(current_user["sub"])
        QuotaService.check_and_increment_quota(db, user_id)
        
        # 检查文件类型
        filename = file.filename
        _, ext = os.path.splitext(filename)
        
        if ext.lower() not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件格式: {ext}，请上传 PDF 或 Word 文档"
            )
        
        # 1. 读取文件内容到内存用于分析
        file_bytes = await file.read()

        # 简单的大小限制
        max_bytes = int(MAX_FILE_SIZE_MB * 1024 * 1024)
        if len(file_bytes) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"文件过大：{len(file_bytes) / (1024 * 1024):.2f}MB，最大支持 {MAX_FILE_SIZE_MB}MB"
            )
            
        # 2. 保存文件到磁盘 (用于前端预览)
        file_id = str(uuid.uuid4())
        save_filename = f"{file_id}{ext}"
        save_path = os.path.join(UPLOAD_DIR, save_filename)
        
        with open(save_path, "wb") as f:
            f.write(file_bytes)
            
        # 生成访问 URL
        file_url = f"/api/uploads/{save_filename}"
        
        # 3. 处理文档
        result = coordinator.process_document(
            file_bytes=file_bytes,
            filename=filename
        )
        
        if result.success:
            state.is_document_loaded = True
            state.current_summary = result.summary
            state.current_structure = result.structure_info
            
            # 获取文档信息
            doc_info = coordinator.get_current_document_info()
            if doc_info:
                state.document_info = {
                    "filename": doc_info['filename'],
                    "title": doc_info['title'],
                    "file_type": doc_info['file_type'].upper(),
                    "page_count": doc_info['page_count'],
                    "word_count": doc_info['word_count'],
                    "document_id": doc_info['document_id'],
                    "processing_time": result.total_time,
                    "file_url": file_url
                }
                state.current_document_id = doc_info['document_id']
            
            # 保存到历史记录（持久化到 ChromaDB）
            try:
                history_store = HistoryStoreService()
                history_id = history_store.add_analysis_history(
                    document_id=state.current_document_id,
                    filename=state.document_info.get("filename", "未知文件"),
                    title=state.document_info.get("title", ""),
                    file_type=state.document_info.get("file_type", ""),
                    page_count=state.document_info.get("page_count", 0),
                    word_count=state.document_info.get("word_count", 0),
                    processing_time=state.document_info.get("processing_time", 0),
                    structure=result.structure_info,
                    summary=result.summary
                )
                state.current_history_id = history_id
            except Exception as e:
                logger.error(f"保存历史记录失败: {e}")
            
            # 保存 Session 状态
            state.save()
            
            return AnalysisResponse(
                success=True,
                status=f"文档解析完成！标题: {result.paper_title}",
                document_info=state.document_info,
                structure=result.structure_info,
                summary=result.summary
            )
        else:
            state.is_document_loaded = False
            state.save()
            return AnalysisResponse(
                success=False,
                status="处理失败",
                error=result.error_message
            )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}\n{traceback.format_exc()}"
        logger.error("文档分析失败: %s", error_detail)
        return AnalysisResponse(
            success=False,
            status="处理失败",
            error=str(e)
        )

@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest, 
    state: SessionState = Depends(get_session_state),
    coordinator: PaperReaderCoordinator = Depends(get_coordinator)
):
    """聊天问答"""
    
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")
    
    if not state.is_document_loaded:
        raise HTTPException(status_code=400, detail="请先上传并解析论文文档")
    
    # 保存用户消息到历史
    try:
        if state.current_document_id:
            HistoryStoreService().add_chat_message(
                document_id=state.current_document_id,
                role="user",
                content=request.message
            )
    except Exception as e:
        logger.error(f"保存消息失败: {e}")
    
    # 获取回答
    result = coordinator.ask_question(request.message)
    
    if result.success:
        # 保存助手回复到历史
        try:
            if state.current_document_id:
                HistoryStoreService().add_chat_message(
                    document_id=state.current_document_id,
                    role="assistant",
                    content=result.answer,
                    source_chunks=result.source_chunks[:3] if result.source_chunks else []
                )
        except Exception as e:
            logger.error(f"保存回复失败: {e}")
        
        return ChatResponse(
            success=True,
            answer=result.answer,
            source_chunks=result.source_chunks[:3] if result.source_chunks else []
        )
    else:
        return ChatResponse(
            success=False,
            answer=f"回答失败: {result.error_message}",
            source_chunks=[]
        )

@app.post("/api/chat/stream")
async def chat_stream(
    request: ChatRequest, 
    state: SessionState = Depends(get_session_state),
    coordinator: PaperReaderCoordinator = Depends(get_coordinator)
):
    """流式聊天问答"""
    
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")
    
    if not state.is_document_loaded:
        raise HTTPException(status_code=400, detail="请先上传并解析论文文档")
    
    # 保存用户消息
    try:
        if state.current_document_id:
            HistoryStoreService().add_chat_message(
                document_id=state.current_document_id,
                role="user",
                content=request.message
            )
    except Exception as e:
        logger.error(f"保存消息失败: {e}")
    
    async def generate():
        full_response = ""
        try:
            for chunk in coordinator.ask_question_stream(request.message):
                full_response += chunk
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.01)
            
            # 保存助手回复
            try:
                if state.current_document_id:
                    HistoryStoreService().add_chat_message(
                        document_id=state.current_document_id,
                        role="assistant",
                        content=full_response
                    )
            except Exception as e:
                logger.error(f"保存回复失败: {e}")
            
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

@app.get("/api/suggestions")
async def get_suggestions(
    state: SessionState = Depends(get_session_state),
    coordinator: PaperReaderCoordinator = Depends(get_coordinator)
):
    """获取建议问题"""
    if not state.is_document_loaded:
        return {"questions": []}
    
    questions = coordinator.get_suggested_questions()
    return {"questions": questions}

@app.post("/api/translate/stream")
async def translate_stream(
    state: SessionState = Depends(get_session_state),
    coordinator: PaperReaderCoordinator = Depends(get_coordinator)
):
    """流式翻译论文全文"""
    
    if not state.is_document_loaded:
        raise HTTPException(status_code=400, detail="请先上传并解析论文文档")
    
    async def generate():
        try:
            for chunk in coordinator.translate_stream():
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.01)
            
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

@app.post("/api/clear")
async def clear_chat(
    state: SessionState = Depends(get_session_state),
    coordinator: PaperReaderCoordinator = Depends(get_coordinator)
):
    """清除聊天历史"""
    coordinator.clear_chat_history()
    
    # 同时清除持久化的对话记录
    if state.current_document_id:
        try:
            HistoryStoreService().clear_chat_history(state.current_document_id)
        except Exception as e:
            logger.error(f"清除历史记录失败: {e}")
            
    return {"success": True}

@app.delete("/api/document")
async def clear_document(
    state: SessionState = Depends(get_session_state),
    coordinator: PaperReaderCoordinator = Depends(get_coordinator)
):
    """清除当前文档"""
    state.is_document_loaded = False
    state.current_summary = ""
    state.current_structure = ""
    state.document_info = {}
    state.current_history_id = None
    state.current_document_id = None
    
    coordinator.clear_chat_history()
    state.save()
    
    return {"success": True}

@app.get("/api/history", response_model=HistoryListResponse)
async def get_analysis_history(state: SessionState = Depends(get_session_state)):
    """获取分析历史记录列表"""
    try:
        history_store = HistoryStoreService()
        history_list = history_store.get_analysis_history_list()
        history_items = [
            HistoryItem(
                id=h["id"],
                filename=h["filename"],
                title=h.get("title", ""),
                file_type=h.get("file_type", ""),
                page_count=h.get("page_count", 0),
                word_count=h.get("word_count", 0),
                processing_time=h.get("processing_time", 0),
                analyzed_at=h.get("analyzed_at", "")
            )
            for h in history_list
        ]
        return HistoryListResponse(
            history=history_items,
            current_id=state.current_history_id
        )
    except Exception as e:
        logger.error("获取历史记录失败: %s", e)
        return HistoryListResponse(history=[], current_id=None)

@app.get("/api/history/{history_id}")
async def get_history_detail(history_id: str):
    """获取指定历史记录详情"""
    try:
        history_store = HistoryStoreService()
        item = history_store.get_analysis_history_detail(history_id)
        if not item:
            raise HTTPException(status_code=404, detail="历史记录不存在")
        return item
    except Exception as e:
        logger.error(f"获取详情失败: {e}")
        raise HTTPException(status_code=500, detail="服务错误")

@app.post("/api/history/{history_id}/load")
async def load_history_item(
    history_id: str, 
    state: SessionState = Depends(get_session_state),
    coordinator: PaperReaderCoordinator = Depends(get_coordinator)
):
    """加载历史记录到当前状态"""
    try:
        history_store = HistoryStoreService()
        item = history_store.get_analysis_history_detail(history_id)
        if not item:
            raise HTTPException(status_code=404, detail="历史记录不存在")
        
        # 更新当前状态
        state.current_summary = item.get("summary", "")
        state.current_structure = item.get("structure", "")
        state.is_document_loaded = True
        state.current_history_id = history_id
        state.current_document_id = item.get("document_id", "")
        state.document_info = {
            "filename": item["filename"],
            "title": item.get("title", ""),
            "file_type": item.get("file_type", ""),
            "page_count": item.get("page_count", 0),
            "word_count": item.get("word_count", 0),
            "processing_time": item.get("processing_time", 0),
            "document_id": item.get("document_id", "")
        }
        
        # 保存状态到 Session Store
        state.save()
        
        # 尝试加载向量存储
        if state.current_document_id:
            coordinator.vector_store.load_collection(state.current_document_id)
            coordinator.qa_agent.set_document_context(
                doc_id=state.current_document_id,
                paper_title=item.get("title", ""),
                paper_summary=state.current_summary[:500]
            )
        
        # 获取该文档的对话历史
        chat_history = history_store.get_chat_history(state.current_document_id)
        
        return {
            "success": True,
            "document_info": state.document_info,
            "structure": state.current_structure,
            "summary": state.current_summary,
            "chat_history": chat_history
        }
    except Exception as e:
        logger.error(f"加载历史记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/history/{history_id}")
async def delete_history_item(
    history_id: str, 
    state: SessionState = Depends(get_session_state),
    coordinator: PaperReaderCoordinator = Depends(get_coordinator)
):
    """删除指定历史记录"""
    try:
        history_store = HistoryStoreService()
        item = history_store.get_analysis_history_detail(history_id)
        if not item:
            raise HTTPException(status_code=404, detail="历史记录不存在")
        
        # 删除历史记录
        success = history_store.delete_analysis_history(history_id)
        if not success:
            raise HTTPException(status_code=500, detail="删除失败")
        
        # 尝试删除向量集合
        if item.get("document_id"):
            try:
                coordinator.vector_store.delete_collection(item["document_id"])
            except Exception as e:
                logger.warning(f"删除向量集合失败: {e}")
        
        # 如果删除的是当前记录，清除当前状态
        if state.current_history_id == history_id:
            state.current_history_id = None
            state.current_document_id = None
            state.is_document_loaded = False
            state.current_summary = ""
            state.current_structure = ""
            state.document_info = {}
            state.save()
        
        return {"success": True}
    except Exception as e:
        logger.error(f"删除失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history/{history_id}/chat")
async def get_history_chat(history_id: str):
    """获取指定历史记录的对话历史"""
    try:
        history_store = HistoryStoreService()
        item = history_store.get_analysis_history_detail(history_id)
        if not item:
            raise HTTPException(status_code=404, detail="历史记录不存在")
        
        document_id = item.get("document_id", "")
        chat_history = history_store.get_chat_history(document_id)
        
        return {"chat_history": chat_history}
    except Exception as e:
        logger.error(f"获取对话历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 用户认证相关接口 (保持不变)
@app.post("/api/register", response_model=TokenResponse)
async def register(request: RegisterRequest, db=Depends(get_db)):
    """用户注册"""
    existing_user = db.query(User).filter(User.phone == request.phone).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="手机号已被注册")
    
    user = auth_service.register_user(
        db=db,
        phone=request.phone,
        password=request.password,
        nickname=request.nickname,
        avatar=request.avatar,
        age=request.age,
        profession=request.profession
    )
    
    if not user:
        raise HTTPException(status_code=400, detail="注册失败")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={"sub": str(user.id), "phone": user.phone},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/login", response_model=TokenResponse)
async def login(request: LoginRequest, db=Depends(get_db)):
    """用户登录"""
    # 1. 查找用户
    user = db.query(User).filter(User.phone == request.phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="该账号不存在，请先注册")
    
    # 2. 验证密码
    if not auth_service.verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="密码错误，请重试")
        
    # 3. 生成令牌
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={"sub": str(user.id), "phone": user.phone},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/user/profile")
async def get_user_profile(current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    """获取用户资料"""
    user_id = current_user.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return {
        "id": user.id,
        "phone": user.phone,
        "nickname": user.nickname,
        "avatar": user.avatar,
        "age": user.age,
        "profession": user.profession,
        "is_verified": user.is_verified == 1
    }

@app.put("/api/user/profile")
async def update_user_profile(
    request: UserProfileUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """更新用户资料"""
    user_id = current_user.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    if request.nickname is not None:
        user.nickname = request.nickname
    if request.avatar is not None:
        user.avatar = request.avatar
    if request.age is not None:
        user.age = request.age
    if request.profession is not None:
        user.profession = request.profession
    
    db.commit()
    db.refresh(user)
    
    return {"success": True, "message": "资料更新成功"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
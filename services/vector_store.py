"""
向量存储服务 - ChromaDB 集成 (支持混合检索 Hybrid Search)
"""
import os
import logging
from typing import List, Optional, Dict, Any, Union
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun

from config import (
    CHROMA_PERSIST_DIR,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    TOP_K_RESULTS
)
from services.chroma_client import get_chroma_client
from services.text_utils import split_text

logger = logging.getLogger(__name__)

# 自定义简单的 EnsembleRetriever，解决版本兼容问题
class SimpleEnsembleRetriever(BaseRetriever):
    """
    一个简单的混合检索器，结合 Vector 和 BM25。
    使用 Reciprocal Rank Fusion (RRF) 算法合并结果。
    """
    retrievers: List[BaseRetriever]
    weights: List[float]
    
    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None
    ) -> List[Document]:
        
        # 1. 获取检索结果 (使用 get_relevant_documents 避免 invoke 的参数冲突)
        all_results = []
        for retriever in self.retrievers:
            try:
                # 直接调用底层方法，避免 invoke 的 run_manager 参数问题
                if hasattr(retriever, 'get_relevant_documents'):
                    results = retriever.get_relevant_documents(query)
                else:
                    results = retriever.invoke(query)
                all_results.append(results)
            except Exception as e:
                # 单个检索器失败不影响整体
                logger.warning(f"Retriever failed: {e}")
                all_results.append([])
        
        # 2. RRF 融合
        rrf_score: Dict[str, float] = {}
        doc_map: Dict[str, Document] = {}
        
        for retriever_idx, results in enumerate(all_results):
            weight = self.weights[retriever_idx]
            for rank, doc in enumerate(results):
                # 使用 page_content 作为唯一标识（简化版）
                doc_id = doc.page_content
                doc_map[doc_id] = doc
                
                # RRF 公式: score = weight * (1 / (rank + 60))
                score = weight * (1 / (rank + 60))
                rrf_score[doc_id] = rrf_score.get(doc_id, 0.0) + score
        
        # 3. 排序
        sorted_doc_ids = sorted(rrf_score.keys(), key=lambda x: rrf_score[x], reverse=True)
        
        # 4. 返回 Top K (假设 K=5，这里取前 len(results) 个)
        # 实际上 invoke 会根据各自 retriever 的 k 返回，这里简单合并
        return [doc_map[doc_id] for doc_id in sorted_doc_ids]

class VectorStoreService:
    """向量存储服务 - 基于 ChromaDB + BM25 混合检索"""
    
    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: Optional[str] = None,
        embedding_model: Optional[str] = None
    ):
        self.persist_directory = persist_directory or CHROMA_PERSIST_DIR
        self.collection_name = collection_name or COLLECTION_NAME
        self.embedding_model_name = embedding_model or EMBEDDING_MODEL
        
        # 确保持久化目录存在
        os.makedirs(self.persist_directory, exist_ok=True)
        
        # 初始化 Embedding 模型
        self.embeddings = self._create_embeddings()
        
        # 初始化向量存储
        self.vector_store: Optional[Any] = None
        self.bm25_retriever: Optional[BM25Retriever] = None
        self._current_collection_id: Optional[str] = None
        
        # 缓存当前文档的所有 chunk，用于构建 BM25 索引
        self._document_chunks_cache: List[Document] = []
    
    def _create_embeddings(self) -> HuggingFaceEmbeddings:
        """创建 Embedding 模型"""
        return HuggingFaceEmbeddings(
            model_name=self.embedding_model_name,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )

    def _get_chroma_class(self):
        """
        获取 Chroma VectorStore 实现。
        """
        try:
            from langchain_chroma import Chroma  # type: ignore
            return Chroma
        except Exception as e:  # pragma: no cover
            raise ImportError(
                "未找到 Chroma VectorStore 实现。请运行 `pip install -U langchain-chroma`。"
            ) from e

    def _split_text(self, text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """将文本分割为固定大小的块（委托给共享工具函数）"""
        return split_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    
    def create_collection(self, collection_id: str) -> None:
        """
        创建新的向量集合
        """
        collection_name = f"{self.collection_name}_{collection_id}"

        Chroma = self._get_chroma_class()
        client = get_chroma_client(self.persist_directory)
        self.vector_store = Chroma(
            client=client,
            collection_name=collection_name,
            embedding_function=self.embeddings,
        )
        self._current_collection_id = collection_id
        # 重置缓存
        self._document_chunks_cache = []
        self.bm25_retriever = None

    def load_collection(self, collection_id: str) -> bool:
        """
        切换到已存在的向量集合（多文档支持）
        """
        if self._current_collection_id == collection_id:
            return True  # 已经是当前集合
        
        try:
            collection_name = f"{self.collection_name}_{collection_id}"
            Chroma = self._get_chroma_class()
            client = get_chroma_client(self.persist_directory)
            self.vector_store = Chroma(
                client=client,
                collection_name=collection_name,
                embedding_function=self.embeddings,
            )
            self._current_collection_id = collection_id
            self._document_chunks_cache = []
            self.bm25_retriever = None
            return True
        except Exception as e:
            logger.error(f"加载集合失败: {e}")
            return False
    
    def add_documents(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        collection_id: Optional[str] = None
    ) -> None:
        """
        添加文档到向量存储，并更新 BM25 索引
        """
        if collection_id and collection_id != self._current_collection_id:
            self.create_collection(collection_id)
        
        if self.vector_store is None:
            raise ValueError("请先创建集合（调用 create_collection）")
        
        # 创建 Document 对象
        documents = []
        for i, text in enumerate(texts):
            metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
            metadata["chunk_index"] = i
            documents.append(Document(page_content=text, metadata=metadata))
        
        # 1. 添加到 Chroma 向量存储
        self.vector_store.add_documents(documents)
        
        # 2. 更新内存缓存并重建 BM25 索引
        # 注意：BM25Retriever 是纯内存的，每次服务重启或切换文档需要重建。
        # 生产环境中，对于超大文档，BM25 索引构建可能会慢，可以考虑使用 Elasticsearch。
        self._document_chunks_cache.extend(documents)
        self._rebuild_bm25_index()
        
    def _rebuild_bm25_index(self):
        """重建 BM25 索引"""
        if self._document_chunks_cache:
            # 使用默认参数初始化，避免访问不存在的字段 k1/b
            self.bm25_retriever = BM25Retriever.from_documents(
                self._document_chunks_cache,
                k=TOP_K_RESULTS # 设置默认检索数量
            )
            # 移除直接设置 k1, b 的代码，防止 AttributeError
            # self.bm25_retriever.k1 = 1.5 
            # self.bm25_retriever.b = 0.75
    
    def add_document_with_splitting(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        collection_id: Optional[str] = None,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP
    ) -> int:
        """添加长文档（自动分块）"""
        if collection_id and collection_id != self._current_collection_id:
            self.create_collection(collection_id)
        
        if self.vector_store is None:
            raise ValueError("请先创建集合")

        chunks = self._split_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        
        metadatas = []
        base_metadata = metadata or {}
        for i, chunk in enumerate(chunks):
            chunk_metadata = base_metadata.copy()
            chunk_metadata["chunk_index"] = i
            chunk_metadata["total_chunks"] = len(chunks)
            metadatas.append(chunk_metadata)
        
        self.add_documents(chunks, metadatas)
        return len(chunks)
    
    def load_collection(self, collection_id: str) -> bool:
        """
        加载已存在的集合（带短路缓存：如果集合已加载则跳过）
        """
        # 短路：目标集合已加载，无需重复拉取 + 重建 BM25 索引
        if self._current_collection_id == collection_id and self.vector_store is not None:
            return True

        collection_name = f"{self.collection_name}_{collection_id}"
        
        try:
            Chroma = self._get_chroma_class()
            client = get_chroma_client(self.persist_directory)
            self.vector_store = Chroma(
                client=client,
                collection_name=collection_name,
                embedding_function=self.embeddings,
            )
            self._current_collection_id = collection_id
            
            # 从 Chroma 中拉取所有文档来重建 BM25 索引
            results = self.vector_store.get()
            
            self._document_chunks_cache = []
            if results and results['documents']:
                for i, text in enumerate(results['documents']):
                    meta = results['metadatas'][i] if results['metadatas'] else {}
                    self._document_chunks_cache.append(Document(page_content=text, metadata=meta))
                
                self._rebuild_bm25_index()
                
            return True
        except Exception:
            return False
            
    def get_retriever(self, k: int = TOP_K_RESULTS):
        """
        获取混合检索器 (Hybrid Retriever)
        
        Returns:
            EnsembleRetriever: 结合了 Vector 和 BM25 的检索器
        """
        if self.vector_store is None:
            raise ValueError("向量存储未初始化")
        
        # 1. 向量检索器
        vector_retriever = self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": k}
        )
        
        # 2. 如果 BM25 索引存在，返回混合检索器
        if self.bm25_retriever:
            self.bm25_retriever.k = k
            
            # 权重分配：向量检索 0.7，关键词检索 0.3
            # 这意味着系统更偏重语义理解，但也会考虑关键词匹配
            ensemble_retriever = SimpleEnsembleRetriever(
                retrievers=[vector_retriever, self.bm25_retriever],
                weights=[0.7, 0.3]
            )
            return ensemble_retriever
        
        # 降级方案：仅返回向量检索器
        return vector_retriever

    # 兼容旧接口（如果外部直接调用 similarity_search）
    def similarity_search(self, query: str, k: int = TOP_K_RESULTS, collection_id: Optional[str] = None) -> List[Document]:
        if collection_id and collection_id != self._current_collection_id:
            self.load_collection(collection_id)
        
        # 如果有混合检索器，优先使用 invoke（新版 API）
        # 这里为了简单，如果已经初始化了 EnsembleRetriever，我们可以手动合并结果，或者直接回退到向量搜索
        # 通常外部是通过 get_retriever 获取后调用 invoke 的，所以这里保留原生的向量搜索即可
        if self.vector_store is None:
            raise ValueError("向量存储未初始化")
            
        return self.vector_store.similarity_search(query, k=k)
    
    def get_all_chunks(self) -> List[Document]:
        """
        获取当前文档的所有分块内容（用于全文翻译等场景）
        
        Returns:
            按 chunk_index 排序的文档列表
        """
        if not self._document_chunks_cache:
            # 尝试从向量存储加载
            if self.vector_store:
                try:
                    results = self.vector_store.get()
                    if results and results['documents']:
                        for i, text in enumerate(results['documents']):
                            meta = results['metadatas'][i] if results['metadatas'] else {}
                            self._document_chunks_cache.append(
                                Document(page_content=text, metadata=meta)
                            )
                except Exception as e:
                    logger.warning(f"加载文档分块失败: {e}")
        
        # 按 chunk_index 排序
        sorted_chunks = sorted(
            self._document_chunks_cache,
            key=lambda x: x.metadata.get("chunk_index", 0)
        )
        return sorted_chunks
    
    def search(self, query: str, top_k: int = TOP_K_RESULTS) -> List[Document]:
        """
        语义搜索（兼容旧接口，委托给 similarity_search）
        
        Args:
            query: 搜索查询
            top_k: 返回的最相关结果数量
            
        Returns:
            List[Document]: 相关文档列表
        """
        return self.similarity_search(query, k=top_k)

    def delete_collection(self, collection_id: str) -> bool:
        """
        删除向量集合
        
        Args:
            collection_id: 集合ID
            
        Returns:
            bool: 是否成功删除
        """
        collection_name = f"{self.collection_name}_{collection_id}"
        try:
            client = get_chroma_client(self.persist_directory)
            client.delete_collection(name=collection_name)
            # 如果删除的是当前集合，重置内部状态
            if self._current_collection_id == collection_id:
                self.vector_store = None
                self._current_collection_id = None
                self._document_chunks_cache = []
                self.bm25_retriever = None
            return True
        except Exception as e:
            logger.warning(f"删除集合失败: {e}")
            return False

    def get_full_text(self) -> str:
        """
        获取完整文档文本（按顺序拼接所有分块）
        
        Returns:
            完整文档文本
        """
        chunks = self.get_all_chunks()
        return "\n\n".join([chunk.page_content for chunk in chunks])

"""
文本处理工具 - 提供统一的文本分块等功能
"""
from typing import List


def split_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    separators: List[str] = None
) -> List[str]:
    """
    将文本分割为固定大小的块（在语义边界处分割）

    Args:
        text: 原始文本
        chunk_size: 每个块的最大字符数
        chunk_overlap: 相邻块之间的重叠字符数
        separators: 分割符列表（按优先级排序）

    Returns:
        List[str]: 文本块列表
    """
    if not text:
        return []

    if separators is None:
        separators = ["\n\n", "\n", "。", ".", "！", "!", "？", "?", "；", ";", " "]

    chunks: List[str] = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size

        if end >= text_length:
            last = text[start:].strip()
            if last:
                chunks.append(last)
            break

        # 在边界附近寻找最佳分割点
        search_start = max(start + chunk_size - 100, start)
        best_split = end

        for sep in separators:
            pos = text.rfind(sep, search_start, min(end + 50, text_length))
            if pos != -1 and pos > search_start:
                best_split = pos + len(sep)
                break

        chunk = text[start:best_split].strip()
        if chunk:
            chunks.append(chunk)

        # 计算下一块的起始位置（带重叠）
        next_start = best_split - chunk_overlap
        if next_start <= start:
            # 防止无限循环：确保至少前进 1 个字符
            next_start = start + max(chunk_size // 2, 1)
        start = next_start

    return chunks

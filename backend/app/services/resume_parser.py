# -*- coding: utf-8 -*-
"""
简历文档解析：从上传的 PDF / Word / TXT 提取纯文本。
- .txt/.md：直接解码（utf-8，失败回退 gbk）
- .docx：本质是 zip，用标准库 zipfile 读取 word/document.xml，正则提取 <w:t> 文本（无需 python-docx）
- .pdf：优先 pypdf；未安装或解析失败返回空串，由上层降级为"粘贴文本"
"""
from __future__ import annotations

import io
import logging
import re
import zipfile

logger = logging.getLogger(__name__)


def parse_resume(filename: str, content: bytes) -> tuple[str, str]:
    """返回 (file_type, text)。text 为空表示解析失败。"""
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return "pdf", _parse_pdf(content)
    if name.endswith(".docx"):
        return "docx", _parse_docx(content)
    if name.endswith(".doc"):
        # 旧版 .doc 为二进制格式，标准库无法解析；提示转 docx/txt
        return "doc", ""
    # txt / md / 其它纯文本
    return "txt", _parse_txt(content)


def _parse_txt(content: bytes) -> str:
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return content.decode(enc).strip()
        except Exception:
            continue
    return ""


def _parse_docx(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            raw = z.read("word/document.xml").decode("utf-8", errors="ignore")
    except Exception as e:
        logger.warning("[resume] docx 解析失败: %s", e)
        return ""
    # 按段落 </w:p> 切分，逐段提取 <w:t> 文本
    paragraphs = []
    for seg in raw.split("</w:p>"):
        ts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", seg, flags=re.S)
        line = "".join(ts).strip()
        if line:
            paragraphs.append(_unescape(line))
    return "\n".join(paragraphs).strip()


def _parse_pdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except Exception:
        logger.warning("[resume] pypdf 未安装，无法解析 PDF")
        return ""
    try:
        reader = PdfReader(io.BytesIO(content))
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(parts).strip()
    except Exception as e:
        logger.warning("[resume] pdf 解析失败: %s", e)
        return ""


def _unescape(s: str) -> str:
    return (s.replace("&amp;", "&").replace("&lt;", "<")
             .replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'"))

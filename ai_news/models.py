"""数据模型"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RawItem:
    """爬取到的原始条目"""

    source: str          # 源配置里的 name
    source_type: str     # tme / googlenews / rss / rsshub_twitter / twitter_x
    source_id: str       # 源内唯一 id（如消息 id / 状态 id）
    url: str
    author: str = ""
    title: str = ""
    text: str = ""
    published_at: str = ""   # ISO 8601
    media_urls: list[str] = field(default_factory=list)
    lang: str = ""


@dataclass
class Draft:
    """LLM 加工后的发布草稿"""

    item_id: int
    title: str = ""
    body: str = ""
    hashtags: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)  # 本地图片路径
    relevant: bool = True
    sensitive: bool = False
    reason: str = ""

"""科大讯飞 语音听写（流式 IAT）WebSocket 桥接服务

协议: https://www.xfyun.cn/doc/asr/voicedictation/API.html
- 鉴权: HMAC-SHA256 签名挂 URL（host/date/request-line）
- 音频: PCM 16k 16bit 单声道，1280B/帧（40ms）
- 单会话上限 60s，超时前由客户端续接新会话
- dwa=wpgs 动态修正: pgs=apd 追加 / pgs=rpl 按 rg 区间替换
"""
import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable
from urllib.parse import urlencode

import websockets

from app.core.config import settings

log = logging.getLogger(__name__)

IAT_URL = "wss://iat-api.xfyun.cn/v2/iat"
IAT_HOST = "iat-api.xfyun.cn"
IAT_PATH = "/v2/iat"

AUDIO_FMT = "audio/L16;rate=16000"


def is_configured() -> bool:
    return bool(settings.IFLY_APP_ID and settings.IFLY_API_KEY and settings.IFLY_API_SECRET)


def _signed_url() -> str:
    """生成带鉴权参数的讯飞 WebSocket 握手 URL"""
    date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    signature_origin = f"host: {IAT_HOST}\ndate: {date}\nGET {IAT_PATH} HTTP/1.1"
    signature_sha = hmac.new(
        settings.IFLY_API_SECRET.encode("utf-8"),
        signature_origin.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature = base64.b64encode(signature_sha).decode()
    authorization_origin = (
        f'api_key="{settings.IFLY_API_KEY}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode()
    query = urlencode({"host": IAT_HOST, "date": date, "authorization": authorization})
    return f"{IAT_URL}?{query}"


class IflyIatSession:
    """一个讯飞 IAT 会话（≤60s），负责发送音频帧 + 解析流式识别结果"""

    def __init__(self):
        self.ws = None
        self.results: dict[int, str] = {}   # sn -> 文本（支持 wpgs 动态修正）
        self.full_text = ""
        self.closed = False
        self._started = False

    async def start(self):
        url = _signed_url()
        self.ws = await websockets.connect(url, max_size=2 ** 22, open_timeout=10)

    async def send_audio(self, pcm: bytes, end: bool = False):
        """发送一帧 PCM 音频；end=True 时发送结束标识"""
        if self.closed or self.ws is None:
            return
        if not self._started:
            # 首帧携带 common/business + 第一段音频
            frame = {
                "common": {"app_id": settings.IFLY_APP_ID},
                "business": {
                    "language": "zh_cn",
                    "domain": "iat",
                    "accent": "mandarin",
                    "vad_eos": 10000,   # 10s 静默判定结束
                    "dwa": "wpgs",      # 动态修正（流式）
                    "ptt": 1,           # 加标点
                },
                "data": {
                    "status": 2 if end else 0,
                    "format": AUDIO_FMT,
                    "encoding": "raw",
                    "audio": base64.b64encode(pcm).decode() if pcm else "",
                },
            }
            self._started = True
        else:
            frame = {
                "data": {
                    "status": 2 if end else 1,
                    "format": AUDIO_FMT,
                    "encoding": "raw",
                    "audio": base64.b64encode(pcm).decode() if pcm else "",
                }
            }
        await self.ws.send(json.dumps(frame, ensure_ascii=False))

    def _apply_result(self, result: dict):
        """应用一条识别结果。

        dwa=wpgs 动态修正协议：
        - pgs=apd：该 sn 为新增片段，直接记录
        - pgs=rpl：该结果替换 rg=[lo, hi] 区间（按 sn 序号，非列表下标）内的所有旧结果
        最终文本 = 按 sn 升序拼接所有片段。
        """
        text = "".join(
            "".join(cw.get("w", "") for cw in ws_item.get("cw", []))
            for ws_item in result.get("ws", [])
        )
        try:
            sn = int(result.get("sn", 0))
        except (TypeError, ValueError):
            sn = 0
        pgs = result.get("pgs")
        if pgs == "rpl":
            rg = result.get("rg") or [sn, sn]
            try:
                lo, hi = int(rg[0]), int(rg[1])
            except (TypeError, ValueError, IndexError):
                lo, hi = sn, sn
            # 删除被替换 sn 区间内的旧片段
            self.results = {k: v for k, v in self.results.items() if not (lo <= k <= hi)}
        if text:
            self.results[sn] = text
        self.full_text = "".join(self.results[k] for k in sorted(self.results))

    async def recv_loop(
        self,
        on_partial: Callable[[str], Awaitable[None]],
        on_final: Callable[[str], Awaitable[None]],
        on_error: Callable[[str], Awaitable[None]],
    ):
        """循环接收识别结果，直到 data.status==2（全部返回）或连接关闭"""
        try:
            async for raw in self.ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                code = msg.get("code", 0)
                if code != 0:
                    await on_error(f"讯飞错误 {code}: {msg.get('message', '未知错误')}")
                    return
                data = msg.get("data") or {}
                result = data.get("result")
                if result:
                    self._apply_result(result)
                    if data.get("status") == 2:
                        self.closed = True
                        await on_final(self.full_text)
                        return
                    await on_partial(self.full_text)
        except websockets.ConnectionClosed as e:
            if not self.closed:
                log.warning("讯飞连接提前关闭: %s", e)
                await on_error("讯飞连接中断，请重新开始作答")
        except Exception as e:  # noqa: BLE001
            log.exception("讯飞接收循环异常")
            await on_error(f"转写服务异常: {e}")
        finally:
            self.closed = True

    async def close(self):
        self.closed = True
        if self.ws is not None:
            try:
                await self.ws.close()
            except Exception:  # noqa: BLE001
                pass

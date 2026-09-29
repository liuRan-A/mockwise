"""实时语音转写 WebSocket 端点

浏览器(PCM 16k 16bit mono) --binary frames--> 本端点 --转发--> 讯飞 IAT
讯飞识别结果 --partial/final JSON--> 浏览器

客户端消息:
- JSON {"type":"start"} 开始一个讯飞会话（60s 内自动续接由客户端负责）
- JSON {"type":"stop"}  结束当前会话（发送结束标识，等服务端返回最终结果）
- binary               一帧 PCM 音频

服务端消息:
- {"type":"ready"}               会话已就绪
- {"type":"partial","text":...}  中间结果（该会话内累计全文）
- {"type":"final","text":...}    会话最终结果
- {"type":"error",...}           错误（not_configured / connect / ifly）
"""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import decode_token
from app.services.ifly_asr import IflyIatSession, is_configured

router = APIRouter()
log = logging.getLogger(__name__)


@router.websocket("/ws/asr")
async def ws_asr(ws: WebSocket, token: str = ""):
    # 鉴权（浏览器端通过 query 传 token）
    user_id = decode_token(token)
    if not user_id:
        try:
            await ws.close(code=4401)
        except Exception:  # noqa: BLE001
            pass
        return

    await ws.accept()

    # 未配置讯飞密钥 → 明确告知前端走演示模式
    if not is_configured():
        await ws.send_json({
            "type": "error",
            "code": "not_configured",
            "message": "讯飞语音服务未配置，请在 backend/.env 填写 IFLY_APP_ID / IFLY_API_KEY / IFLY_API_SECRET",
        })
        await ws.close()
        return

    session: IflyIatSession | None = None
    recv_task: asyncio.Task | None = None

    async def on_partial(text: str):
        try:
            await ws.send_json({"type": "partial", "text": text})
        except Exception:  # noqa: BLE001
            pass

    async def on_final(text: str):
        try:
            await ws.send_json({"type": "final", "text": text})
        except Exception:  # noqa: BLE001
            pass

    async def on_error(msg: str):
        try:
            await ws.send_json({"type": "error", "code": "ifly", "message": msg})
        except Exception:  # noqa: BLE001
            pass

    async def start_session():
        nonlocal session, recv_task
        # 清理上一会话
        if recv_task is not None:
            recv_task.cancel()
            recv_task = None
        if session is not None:
            await session.close()
        session = IflyIatSession()
        try:
            await session.start()
        except Exception as e:  # noqa: BLE001
            log.exception("连接讯飞失败")
            session = None
            await ws.send_json({"type": "error", "code": "connect", "message": f"连接讯飞失败: {e}"})
            return
        recv_task = asyncio.create_task(session.recv_loop(on_partial, on_final, on_error))
        await ws.send_json({"type": "ready"})

    try:
        while True:
            raw = await ws.receive()
            if raw.get("type") == "websocket.disconnect":
                break
            data_bytes = raw.get("bytes")
            if data_bytes:
                if session is not None and not session.closed:
                    try:
                        await session.send_audio(data_bytes)
                    except Exception:  # noqa: BLE001
                        log.exception("转发音频帧失败")
                continue
            text = raw.get("text")
            if not text:
                continue
            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                continue
            mtype = msg.get("type")
            if mtype == "start":
                await start_session()
            elif mtype == "stop":
                if session is not None and not session.closed:
                    try:
                        await session.send_audio(b"", end=True)
                    except Exception:  # noqa: BLE001
                        log.exception("发送结束帧失败")
    except WebSocketDisconnect:
        pass
    finally:
        if recv_task is not None:
            recv_task.cancel()
        if session is not None:
            await session.close()

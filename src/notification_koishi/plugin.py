from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.utils.websocket import ws_client_manager

if TYPE_CHECKING:
    from app.plugins import PluginContext

from .schema import Config


SUMMARY_LIMIT = 1200


class KoishiChannel:
    def __init__(self, ctx: "PluginContext", config: Config) -> None:
        self.ctx = ctx
        self.config = config
        self._owns_client = False

    async def start(self) -> None:
        if not self.config.enabled:
            return
        if not self.config.server_address:
            self.ctx.logger.warning("Koishi 服务地址为空，跳过连接")
            return

        if ws_client_manager.has_client(self.config.client_name):
            await ws_client_manager.connect_client(self.config.client_name)
            if self.config.token:
                await ws_client_manager.send_auth(self.config.client_name, self.config.token, auth_type="auth")
            self.ctx.logger.info(f"复用已有 Koishi 客户端: {self.config.client_name}")
            return

        url = ws_client_manager.http_to_ws_url(self.config.server_address)
        await ws_client_manager.create_client(
            name=self.config.client_name,
            url=url,
            ping_interval=15.0,
            ping_timeout=30.0,
            reconnect_interval=self.config.reconnect_interval,
            max_reconnect_attempts=-1,
        )
        self._owns_client = True
        await ws_client_manager.connect_client(self.config.client_name)
        if self.config.token:
            await ws_client_manager.send_auth(self.config.client_name, self.config.token, auth_type="auth")
        self.ctx.logger.info(f"Koishi 客户端已启动: {self.config.client_name}")

    async def stop(self) -> None:
        if self._owns_client:
            await ws_client_manager.remove_client(self.config.client_name)
            self._owns_client = False

    async def send(self, payload: dict[str, Any]) -> bool:
        if not self.config.enabled:
            return False

        client_name = str(payload.get("client_name") or self.config.client_name or "Koishi")
        message = self._append_extra_summary(str(payload.get("koishi_message") or payload.get("text") or ""), payload)
        msgtype = str(payload.get("msgtype") or "text")

        client = ws_client_manager.get_client(client_name)
        if not client or not client.is_connected:
            self.ctx.logger.warning(f"WebSocket 客户端未连接: {client_name}")
            return False

        notify_message = {
            "id": "Client",
            "type": "notify",
            "data": {
                "msgtype": msgtype,
                "message": message,
            },
        }
        success = await client.send(notify_message)
        if success:
            self.ctx.logger.info("Koishi 通知已发送")
        return bool(success)

    def _append_extra_summary(self, message: str, payload: dict[str, Any]) -> str:
        summary = self._render_extra_summary(payload)
        if not summary:
            return message
        return f"{message}\n\n--- Extra ---\n{summary}"

    def _render_extra_summary(self, payload: dict[str, Any]) -> str:
        extra = payload.get("extra")
        if not isinstance(extra, dict):
            return ""

        parts: list[str] = []
        for index, item in enumerate(extra.get("logs") or [], start=1):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or f"log-{index}.txt")
            content = str(item.get("content") or "")
            parts.append(f"日志: {name}\n{content}")

        for key, label in (("images", "图片"), ("attachments", "附件")):
            for index, item in enumerate(extra.get(key) or [], start=1):
                if not isinstance(item, dict):
                    continue
                name = str(item.get("caption") or item.get("name") or item.get("path") or f"{key}-{index}")
                path = str(item.get("path") or item.get("url") or "")
                parts.append(f"{label}: {name}" + (f"\n{path}" if path else ""))

        summary = "\n\n".join(parts).strip()
        if len(summary) > SUMMARY_LIMIT:
            return summary[: SUMMARY_LIMIT - 3] + "..."
        return summary


class Plugin:
    needs = "notify"

    def __init__(self, ctx: "PluginContext") -> None:
        self.ctx = ctx
        self.channel: KoishiChannel | None = None

    async def on_start(self) -> None:
        raw_config = self.ctx.config.to_dict() if hasattr(self.ctx.config, "to_dict") else dict(self.ctx.config)
        self.channel = KoishiChannel(self.ctx, Config.model_validate(raw_config))
        await self.channel.start()
        self.ctx.get("notify").register_channel("koishi", self.channel)
        self.ctx.logger.info("通道已启动")

    async def on_stop(self, reason: str) -> None:
        notify = self.ctx.get("notify")
        if notify is not None:
            notify.unregister_channel("koishi")
        if self.channel is not None:
            await self.channel.stop()
        self.ctx.logger.info(f"插件停止, reason={reason}")

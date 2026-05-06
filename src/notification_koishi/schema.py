from app.plugins.fields import PluginField
from pydantic import BaseModel, ConfigDict


class Config(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = PluginField(default=True, description="启用 Koishi 通知")
    server_address: str = PluginField(default="", description="Koishi 服务器地址")
    token: str = PluginField(
        default="",
        description="认证 Token",
        format="password",
    )
    client_name: str = PluginField(default="Koishi", description="WebSocket 客户端名称")
    reconnect_interval: float = PluginField(default=5.0, ge=0.5, description="重连间隔秒数")

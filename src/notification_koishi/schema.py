from pydantic import BaseModel, ConfigDict, Field


class Config(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = Field(default=True, description="启用 Koishi 通知")
    server_address: str = Field(default="", description="Koishi 服务器地址")
    token: str = Field(
        default="",
        description="认证 Token",
        json_schema_extra={"format": "password"},
    )
    client_name: str = Field(default="Koishi", description="WebSocket 客户端名称")
    reconnect_interval: float = Field(default=5.0, ge=0.5, description="重连间隔秒数")

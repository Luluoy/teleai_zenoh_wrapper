from dataclasses import dataclass, field
from typing import List, Optional
import json


@dataclass
class QueueSize:
    """Zenoh 传输队列大小配置"""
    control: int = 2
    real_time: int = 4
    interactive_high: int = 4
    interactive_low: int = 4
    data_high: int = 8
    data: int = 8
    data_low: int = 4
    background: int = 2

    def to_dict(self) -> dict:
        return {
            "control": self.control,
            "real_time": self.real_time,
            "interactive_high": self.interactive_high,
            "interactive_low": self.interactive_low,
            "data_high": self.data_high,
            "data": self.data,
            "data_low": self.data_low,
            "background": self.background,
        }


@dataclass
class SharedMemory:
    """Zenoh 共享内存配置"""
    enabled: bool = True
    mode: str = "lazy"
    transport_optimization_enabled: bool = True
    pool_size: int = 16777216          # 16 MB
    message_size_threshold: int = 3072

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "transport_optimization": {
                "enabled": self.transport_optimization_enabled,
                "pool_size": self.pool_size,
                "message_size_threshold": self.message_size_threshold,
            },
        }


@dataclass
class Timestamping:
    """Zenoh 时间戳配置"""
    enabled: bool = True
    drop_future_timestamp: bool = False

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "drop_future_timestamp": self.drop_future_timestamp,
        }


@dataclass
class ZenohConfFactory:
    """
    Zenoh 配置工厂，通过链式调用灵活构建 pub / sub 配置。

    用法示例
    --------
    >>> conf_str = (
    ...     ZenohConfFactory.create_pub()
    ...     .set_listen_endpoints(["tcp/0.0.0.0:65500"])
    ...     .set_shared_memory(enabled=True, pool_size=33554432)
    ...     .set_queue_size(real_time=8, data_high=16)
    ...     .to_str()
    ... )
    """

    mode: str = "peer"
    listen_endpoints: List[str] = field(default_factory=list)
    connect_endpoints: List[str] = field(default_factory=list)
    timestamping: Timestamping = field(default_factory=Timestamping)
    queue_size: QueueSize = field(default_factory=QueueSize)
    shared_memory: SharedMemory = field(default_factory=SharedMemory)

    # ────────────────── 工厂方法 ──────────────────

    @classmethod
    def create_pub(
        cls,
        listen_endpoints: Optional[List[str]] = None,
        mode: str = "peer",
    ) -> "ZenohConfFactory":
        """创建发布者配置（默认 listen tcp/0.0.0.0:65500）"""
        return cls(
            mode=mode,
            listen_endpoints=listen_endpoints or ["tcp/0.0.0.0:65500"],
        )

    @classmethod
    def create_sub(
        cls,
        connect_endpoints: Optional[List[str]] = None,
        mode: str = "peer",
    ) -> "ZenohConfFactory":
        """创建订阅者配置（默认 connect tcp/127.0.0.1:7447）"""
        return cls(
            mode=mode,
            connect_endpoints=connect_endpoints or ["tcp/127.0.0.1:7447"],
        )

    # ────────────────── 链式 setter ──────────────────

    def set_mode(self, mode: str) -> "ZenohConfFactory":
        self.mode = mode
        return self

    def set_listen_endpoints(self, endpoints: List[str]) -> "ZenohConfFactory":
        self.listen_endpoints = endpoints
        return self

    def set_connect_endpoints(self, endpoints: List[str]) -> "ZenohConfFactory":
        self.connect_endpoints = endpoints
        return self

    def set_timestamping(
        self,
        enabled: Optional[bool] = None,
        drop_future_timestamp: Optional[bool] = None,
    ) -> "ZenohConfFactory":
        if enabled is not None:
            self.timestamping.enabled = enabled
        if drop_future_timestamp is not None:
            self.timestamping.drop_future_timestamp = drop_future_timestamp
        return self

    def set_queue_size(self, **kwargs: int) -> "ZenohConfFactory":
        """
        按需修改队列大小，仅传入想改的字段。

        >>> .set_queue_size(real_time=8, data_high=16)
        """
        for k, v in kwargs.items():
            if not hasattr(self.queue_size, k):
                raise ValueError(f"QueueSize 没有字段 '{k}'，"
                                 f"可选: {list(self.queue_size.__dataclass_fields__)}")
            setattr(self.queue_size, k, v)
        return self

    def set_shared_memory(
        self,
        enabled: Optional[bool] = None,
        mode: Optional[str] = None,
        transport_optimization_enabled: Optional[bool] = None,
        pool_size: Optional[int] = None,
        message_size_threshold: Optional[int] = None,
    ) -> "ZenohConfFactory":
        sm = self.shared_memory
        if enabled is not None:
            sm.enabled = enabled
        if mode is not None:
            sm.mode = mode
        if transport_optimization_enabled is not None:
            sm.transport_optimization_enabled = transport_optimization_enabled
        if pool_size is not None:
            sm.pool_size = pool_size
        if message_size_threshold is not None:
            sm.message_size_threshold = message_size_threshold
        return self

    # ────────────────── 序列化 ──────────────────

    def to_dict(self) -> dict:
        conf: dict = {"mode": self.mode}

        if self.listen_endpoints:
            conf["listen"] = {"endpoints": self.listen_endpoints}
        if self.connect_endpoints:
            conf["connect"] = {"endpoints": self.connect_endpoints}

        conf["timestamping"] = self.timestamping.to_dict()

        conf["transport"] = {
            "link": {
                "tx": {
                    "queue": {
                        "size": self.queue_size.to_dict(),
                    }
                }
            },
            "shared_memory": self.shared_memory.to_dict(),
        }

        return conf

    def to_str(self, indent: int = 2) -> str:
        """输出 JSON 字符串，可直接传给 zenoh.Config.from_json5()"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ────────────────── 测试 ──────────────────

if __name__ == "__main__":

    # ---------- 1. 使用默认值快速创建 ----------
    pub_conf = ZenohConfFactory.create_pub()
    print("===== 默认 PUB 配置 =====")
    print(pub_conf.to_str())

    print()

    sub_conf = ZenohConfFactory.create_sub()
    print("===== 默认 SUB 配置 =====")
    print(sub_conf.to_str())

    print()

    # ---------- 2. 链式调用自定义配置 ----------
    custom = (
        ZenohConfFactory.create_pub(listen_endpoints=["tcp/0.0.0.0:9999"])
        .set_mode("client")
        .set_timestamping(enabled=False)
        .set_queue_size(real_time=16, data_high=32)
        .set_shared_memory(pool_size=33554432, message_size_threshold=4096)
    )
    print("===== 自定义配置（链式调用） =====")
    print(custom.to_str(indent=4))
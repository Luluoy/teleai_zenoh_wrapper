import zenoh
from threading import Thread, Lock
from teleai_zenoh_wrapper.infoclasses.base import InfoPacket, TimestampedBufPacket
from teleai_zenoh_wrapper.pubsub.conf import ZenohConfFactory
from typing import Type
import time
from collections import deque


class ZenohPub():
    def __init__(self, data_cls: Type[TimestampedBufPacket], conf: str | None = None, key: str | None = None) -> None:
        assert key is not None, "必须提供必要的key以供连接。"
        if conf is None:
            conf = ZenohConfFactory.create_pub().to_str()
        self._conf = zenoh.Config.from_json5(conf)
        self._key = key
        self._data_cls = data_cls

        self._session = zenoh.open(self._conf)
        self._pub = self._session.declare_publisher(
            self._key,
            priority=zenoh.Priority.REAL_TIME,
            congestion_control=zenoh.CongestionControl.DROP,
            express=True,
        )

    def write(self, payload: TimestampedBufPacket|bytes):
        if isinstance(payload, TimestampedBufPacket):
            self._pub.put(payload.to_bytes())
        else:
            self._pub.put(payload)

    def close(self):
        try:
            self._pub.undeclare()
        except Exception:
            pass
        try:
            self._session.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class ZenohSub():
    def __init__(self, data_cls: Type[TimestampedBufPacket], conf: str | None = None,
                 key: str | None = None) -> None:
        assert key is not None, "必须提供必要的key以供连接。"
        if conf is None:
            conf = ZenohConfFactory.create_sub() \
            .set_shared_memory(pool_size=33554432) \
            .to_str()
        
        self._conf = zenoh.Config.from_json5(conf)
        self._key = key
        self._data_cls = data_cls
        self._lock = Lock()

        self._info = None

        self._session = zenoh.open(self._conf)
        self._sub = self._session.declare_subscriber(
            self._key,
            self._listen
        )

    def _listen(self, sample: zenoh.Sample) -> None:
        with self._lock:
            raw: bytes = bytes(sample.payload)          # ZBytes -> bytes
            pkt = self._data_cls.from_bytes(raw)
            self._info = pkt

    def read(self):
        with self._lock:
            return self._info

    def wait_for_connection(self):
        while self._info is None:
            time.sleep(0.1)

    def close(self):
        try:
            self._sub.undeclare()
        except Exception:
            pass
        try:
            self._session.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

class ZenohQueueSub():
    def __init__(self, data_cls: Type[TimestampedBufPacket], conf: str | None = None,
                 key: str | None = None) -> None:
        assert key is not None, "必须提供必要的key以供连接。"
        if conf is None:
            conf = ZenohConfFactory.create_sub() \
            .set_shared_memory(pool_size=33554432) \
            .to_str()
        
        self._conf = zenoh.Config.from_json5(conf)
        self._key = key
        self._data_cls = data_cls
        self._lock = Lock()

        self._q = deque(maxlen=1)

        self._session = zenoh.open(self._conf)
        self._sub = self._session.declare_subscriber(
            self._key,
            self._listen
        )

    def _listen(self, sample: zenoh.Sample) -> None:
        with self._lock:
            raw: bytes = bytes(sample.payload)          # ZBytes -> bytes
            pkt = self._data_cls.from_bytes(raw)
            self._q.append(pkt)

    def read(self):
        with self._lock:
            if self._q:
                return self._q.popleft()
            return None

    def wait_for_connection(self):
        while not self._q:
            time.sleep(0.1)

    def close(self):
        try:
            self._sub.undeclare()
        except Exception:
            pass
        try:
            self._session.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

class ZenohWildCardSub():
    def __init__(self, data_cls: Type[TimestampedBufPacket], conf: str | None = None,
                 key: str | None = None) -> None:
        assert key is not None, "必须提供必要的key以供连接。"
        if conf is None:
            conf = ZenohConfFactory.create_sub() \
            .set_shared_memory(pool_size=33554432) \
            .to_str()
        
        self._conf = zenoh.Config.from_json5(conf)
        self._key = key
        self._data_cls = data_cls
        self._lock = Lock()

        self._info = None

        self._session = zenoh.open(self._conf)
        self._sub = self._session.declare_subscriber(
            self._key,
            self._listen
        )

    def _listen(self, sample: zenoh.Sample) -> None:
        with self._lock:
            key_expr = str(sample.key_expr)
            raw: bytes = bytes(sample.payload)          # ZBytes -> bytes
            pkt = self._data_cls.from_bytes(raw)
            if not self._info:
                self._info = {}
            self._info[key_expr.split("/")[-1]] = pkt

    def read(self):
        with self._lock:
            return self._info

    def wait_for_connection(self):
        while self._info is None:
            time.sleep(0.1)

    def close(self):
        try:
            self._sub.undeclare()
        except Exception:
            pass
        try:
            self._session.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def main():
    from teleai_zenoh_wrapper.infoclasses import ImagePacket640_480_3
    import numpy as np
    from teleai_zenoh_wrapper.utils import get_nano

    test_key = "test/zenoh/pubsub"

    print("=== Zenoh PubSub 测试 ===\n")

    # 1. 创建订阅者（先启动，以便不遗漏消息）
    print("[1] 正在创建 ZenohSub ...")
    sub = ZenohSub(data_cls=ImagePacket640_480_3, key=test_key)
    print("    ZenohSub 创建成功，等待连接...\n")

    # 2. 创建发布者
    print("[2] 正在创建 ZenohPub ...")
    pub = ZenohPub(key=test_key)
    print("    ZenohPub 创建成功\n")

    # 给 pub/sub 一点时间完成底层连接发现
    time.sleep(1.0)

    # 3. 构造测试数据并发布
    num_messages = 5
    print(f"[3] 开始发布 {num_messages} 条测试消息 ...\n")

    for i in range(num_messages):
        test_data = np.zeros((640, 480, 3), dtype=np.uint8).tobytes()
        pkt = ImagePacket640_480_3(
            timestamp_ns=np.uint64(get_nano()),
            img_buf=test_data,
        )
        pub.write(pkt)
        # print(f"    -> 已发布消息 #{i}: {test_data}")
        time.sleep(0.2)

    # 4. 等待订阅者收到消息
    print("\n[4] 等待订阅者接收消息 ...")
    timeout = 3.0
    start = time.time()
    while sub.read() is None and (time.time() - start) < timeout:
        time.sleep(0.1)

    # 5. 验证结果
    print("\n[5] 验证结果:")
    last_pkt = sub.read()
    if last_pkt is not None:
        print(f"    ✅ 订阅者成功接收到消息!")
        print(f"    最后一条消息时间戳 (ns): {sub.last_recv_ns}")
        # print(f"    最后一条消息内容: {last_pkt.img_buf}")
    else:
        print("    ❌ 订阅者未收到任何消息（超时）")

    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    main()
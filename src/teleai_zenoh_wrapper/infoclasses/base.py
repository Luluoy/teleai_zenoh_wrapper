import struct
import numpy as np
from typing import ClassVar
from typing_extensions import Self
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


class InfoPacket(ABC):
    @abstractmethod
    def to_bytes(self) -> bytes:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_bytes(cls, data: bytes) -> "InfoPacket":
        raise NotImplementedError


_HEADER_FMT = "!Q"
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)

# Header: timestamp_ns (uint64, 8 bytes) + str_len (uint32, 4 bytes)
_STR_LEN_FMT = "!I"
_STR_LEN_SIZE = struct.calcsize(_STR_LEN_FMT)


@dataclass
class TimestampedStrPacket(InfoPacket):
    """带 timestamp_ns 头 + 不定长 UTF-8 字符串 payload 的 Zenoh 传输包。

    Wire format:
        [ timestamp_ns : uint64 (8 bytes, big-endian) ]
        [ str_len      : uint32 (4 bytes, big-endian) ]
        [ utf-8 bytes  : str_len bytes                ]

    Example:
        >>> pkt = TimestampedStrPacket(timestamp_ns=np.uint64(123456789), text="hello")
        >>> raw = pkt.to_bytes()
        >>> restored = TimestampedStrPacket.from_bytes(raw)
        >>> assert restored.text == "hello"
    """

    timestamp_ns: np.uint64 = field(default_factory=lambda: np.uint64(0))
    text: str = ""

    def to_bytes(self) -> bytes:
        encoded = self.text.encode("utf-8")
        header = struct.pack(_HEADER_FMT, self.timestamp_ns)
        length = struct.pack(_STR_LEN_FMT, len(encoded))
        return header + length + encoded

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        min_size = _HEADER_SIZE + _STR_LEN_SIZE
        if len(data) < min_size:
            raise ValueError(f"payload too small: {len(data)} < {min_size}")

        timestamp_ns = np.frombuffer(data[:_HEADER_SIZE], dtype=np.uint64, count=1)[0]
        (str_len,) = struct.unpack_from(_STR_LEN_FMT, data, _HEADER_SIZE)

        payload_start = _HEADER_SIZE + _STR_LEN_SIZE
        payload_end = payload_start + str_len
        if len(data) < payload_end:
            raise ValueError(
                f"payload truncated: expected {payload_end} bytes, got {len(data)}"
            )

        text = data[payload_start:payload_end].decode("utf-8")
        return cls(timestamp_ns=timestamp_ns, text=text)


@dataclass
class TimestampedBufPacket(InfoPacket):
    """带 timestamp_ns 头 + 固定大小 payload 的通用基类。

    子类只需定义：
      - INFOSIZE: ClassVar[int]          payload 字节数
      - _BUF_FIELD: ClassVar[str]        payload 字段名 (默认 "buf")
    """
    INFOSIZE: ClassVar[int]
    _BUF_FIELD: ClassVar[str] = "buf"

    timestamp_ns: np.uint64 = np.uint64(0)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if not isinstance(getattr(cls, "INFOSIZE", None), int):
            raise TypeError(
                f"{cls.__name__} must define INFOSIZE: ClassVar[int] "
                f"with a concrete int value"
            )

        buf_field = getattr(cls, "_BUF_FIELD", None)
        if not isinstance(buf_field, str):
            raise TypeError(
                f"{cls.__name__} must define _BUF_FIELD: ClassVar[str]"
            )

        all_annotations: dict[str, object] = {}
        for klass in reversed(cls.__mro__):
            all_annotations.update(getattr(klass, "__annotations__", {}))
        if buf_field not in all_annotations:
            raise TypeError(
                f"{cls.__name__}._BUF_FIELD = {buf_field!r}, "
                f"but no field '{buf_field}' found in annotations"
            )

    def _get_buf(self) -> bytes:
        return getattr(self, self._BUF_FIELD)

    def to_bytes(self) -> bytes:
        raw = bytes(self._get_buf())
        if len(raw) != self.INFOSIZE:
            raise ValueError(
                f"{self._BUF_FIELD} size must be {self.INFOSIZE}, got {len(raw)}"
            )
        return struct.pack(_HEADER_FMT, self.timestamp_ns) + raw

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        expected = _HEADER_SIZE + cls.INFOSIZE
        if len(data) < expected:
            raise ValueError(f"payload too small: {len(data)} < {expected}")
        timestamp_ns = np.frombuffer(data[:_HEADER_SIZE], dtype=np.uint64, count=1)[0]
        buf = data[_HEADER_SIZE : _HEADER_SIZE + cls.INFOSIZE]
        return cls(timestamp_ns=timestamp_ns, **{cls._BUF_FIELD: buf})


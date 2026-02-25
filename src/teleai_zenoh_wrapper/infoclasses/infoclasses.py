from typing import overload
from typing_extensions import override
from .base import InfoPacket, TimestampedBufPacket
from typing import ClassVar

from dataclasses import dataclass, field
import struct
import numpy as np

def _make_image_packet(h: int, w: int, c: int):
    """
    Factory function to generate ImagePacket dataclass for specified resolution.

    Args:
        h: height
        w: width
        c: channels

    Returns:
        ImagePacket dataclass(TimestampedBufPacket)
    """
    size = h * w * c

    @dataclass
    class _Cls(TimestampedBufPacket):
        INFOSIZE: ClassVar[int] = size
        _BUF_FIELD: ClassVar[str] = "img_buf"
        img_buf: bytes = field(
            default_factory=lambda: np.zeros((h, w, c), dtype=np.uint8).tobytes()
        )

    _Cls.__name__ = _Cls.__qualname__ = f"ImagePacket{h}_{w}_{c}"
    _Cls.__doc__ = f"{h}x{w}x{c} 图像 + 时间戳(ns)消息。"
    return _Cls

def _make_infrence_result_packet(cs: int, dim: int):
    """
    Factory function to generate Inference result dataclass for specified resolution.

    Args:
        cs : chunk size
        dim: robotic arm dofs


    Returns:
        Inference result dataclass(TimestampedBufPacket)
    """
    size = cs * dim * 4

    @dataclass
    class _Cls(TimestampedBufPacket):
        INFOSIZE: ClassVar[int] = size + 12
        _BUF_FIELD: ClassVar[str] = "inference_result_buf"

        inference_start_nanosec: int = 0
        fps: int = 0
        inference_result_buf: bytes = field(
            default_factory=lambda: np.zeros((cs, dim), dtype=np.float32).tobytes()
        )
        
        def to_bytes(self) -> bytes:
            payload = struct.pack("!qi", self.inference_start_nanosec, self.fps) + self.inference_result_buf
            if len(payload) != self.INFOSIZE:
                raise ValueError(f"Payload size mismatch: {len(payload)} != {self.INFOSIZE}")
            return struct.pack("!Q", self.timestamp_ns) + payload

        @classmethod
        def from_bytes(cls, data: bytes):
            expected = 8 + cls.INFOSIZE
            if len(data) < expected:
                raise ValueError(f"payload too small: {len(data)} < {expected}")
            timestamp_ns = np.frombuffer(data[:8], dtype=np.uint64, count=1)[0]
            inference_start_nanosec, fps = struct.unpack("!qi", data[8:20])
            buf = data[20 : expected]
            return cls(timestamp_ns=timestamp_ns, inference_start_nanosec=inference_start_nanosec, fps=fps, inference_result_buf=buf)

    _Cls.__name__ = _Cls.__qualname__ = f"InferenceResultPacket{cs}_{dim}"
    _Cls.__doc__ = f"{cs}x{dim} 推理结果 + 时间戳(ns)消息。"
    return _Cls

ImagePacket640_480_3  = _make_image_packet(640, 480, 3)
ImagePacket960_540_3  = _make_image_packet(960, 540, 3)
ImagePacket224_224_3  = _make_image_packet(224, 224, 3)

InferenceResultPacket20_8 = _make_infrence_result_packet(cs=20, dim=8)
InferenceResultPacket50_8 = _make_infrence_result_packet(cs=50, dim=8)

@dataclass
class U8Packet(TimestampedBufPacket):
    INFOSIZE: ClassVar[int] = 1
    _BUF_FIELD: ClassVar[str] = "state_buf"
    state_buf: bytes = field(
        default_factory=lambda: np.zeros(1, dtype=np.uint8).tobytes()
    )

@dataclass
class ControlPacket(TimestampedBufPacket):
    INFOSIZE: ClassVar[int] = 10
    _BUF_FIELD: ClassVar[str] = "control_buf"
    control_buf: bytes = field(
        default_factory=lambda: np.zeros(10, dtype=np.uint8).tobytes()
    )
    
    def to_dict(self) -> dict:
        return {
            "emergency_stop" : self.control_buf[0],
            "step_forward"   : self.control_buf[1],
            "stop"           : self.control_buf[2],
            "refresh"        : self.control_buf[3],
            "start"          : self.control_buf[4],
            "capture"        : self.control_buf[5]
        }

@dataclass
class RoboticArmPacket(TimestampedBufPacket):
    INFOSIZE: ClassVar[int] = 32
    _BUF_FIELD: ClassVar[str] = "RoboticArm_buf"
    RoboticArm_buf: bytes = field(
        default_factory=lambda: np.zeros(8, dtype=np.float32).tobytes()
    )
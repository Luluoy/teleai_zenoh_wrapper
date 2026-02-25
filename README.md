<p align="center">
  <h1>TeleAI Zenoh Python Wrapper</h1>
</p>

本项目是 **TeleAI（中国电信人工智能研究院）** 在具身智能（Embodied Intelligence）研发实践过程中开发并内部使用的一套 **基于 Zenoh 的高性能通信 Python 封装**。

相较于早期的 `teleai_dds_wrapper`（DDS + Iceoryx 方案），本项目基于 **Eclipse Zenoh** 实现统一的 **Pub/Sub + Query/RPC** 能力，更适合在多进程、多节点、异构设备上的具身智能系统中快速搭建通信骨干。

> ✅ 推荐使用本仓库作为新项目的通信基础设施。  
> ⚠️ 旧项目 `teleai_dds_wrapper` 已进入维护模式，仅用于兼容历史工程。

---

## 项目简介

本项目主要面向 **高带宽感知数据**（例如多路相机图像、大尺寸张量）以及 **控制 / 推理 / 规划 之间的解耦通信** 场景，基于：

- **通信内核**：Eclipse Zenoh (`eclipse-zenoh==1.7.2`)
- **数据模型**：基于 key-expression 的 Pub/Sub 与 Query（RPC）模式
- **Python 接口**：本项目提供的一组轻量级 wrapper 与数据结构

核心设计目标：

- **高性能**：绕开 Python GIL，适合多进程与跨节点通信
- **低耦合**：通过 topic / key-expression 解耦模块，实现弹性伸缩
- **工程友好**：统一的数据包定义与简单易用的 API

---

## 核心能力一览

- **Pub/Sub**
  - `ZenohPub`：发布端封装，支持直接写入 `TimestampedBufPacket` 或原始 `bytes`
  - `ZenohSub`：普通订阅者，持有最新一帧数据
  - `ZenohQueueSub`：队列订阅者，按顺序弹出消息，适合消费型任务
  - `ZenohWildCardSub`：通配符订阅者，可一次性订阅同一前缀下的多个 topic，并通过 key 进行区分

- **RPC / Query**
  - 基于 `session.declare_queryable` 与 `session.get` 实现
  - 支持简单的 JSON 请求 / 响应模式，便于与控制面、Web 服务等对接

- **数据包定义 (`infoclasses`)**
  - `ImagePacket640_480_3` / `ImagePacket960_540_3` / `ImagePacket224_224_3`
  - `InferenceResultPacket20_8` / `InferenceResultPacket50_8`
  - `ControlPacket` / `U8Packet` / `RoboticArmPacket` 等
  - 所有数据包均继承自 `TimestampedBufPacket`，包含纳秒级时间戳 `timestamp_ns`

---

## 环境与安装

**依赖环境：**

- 操作系统：推荐 Ubuntu 22.04+
- Python：`>= 3.10`
- 依赖（摘自 `pyproject.toml`）：
  - `numpy<=2.0`
  - `typing_extensions==4.15.0`
  - `eclipse-zenoh==1.7.2`

### 通过源码安装（推荐开发阶段）

在仓库根目录下：

```bash
pip install -e .
```

---

## 快速上手：Pub/Sub 示例

以下示例演示如何使用 `ZenohPub` 与 `ZenohSub` 在同一个二层网络中完成一对一的图像流传输：

```python
from teleai_zenoh_wrapper import ZenohPub, ZenohSub, ZenohConfFactory
from teleai_zenoh_wrapper import ImagePacket640_480_3
import numpy as np

topic = "camera/front/image"

# 发布端
def publisher():
    conf_str = ZenohConfFactory.create_pub().to_str()
    with ZenohPub(data_cls=ImagePacket640_480_3, conf=conf_str, key=topic) as pub:
        for _ in range(10):
            img = np.zeros((640, 480, 3), dtype=np.uint8).tobytes()
            pkt = ImagePacket640_480_3(img_buf=img)
            pub.write(pkt)   # 也可传入 pkt.to_bytes()

# 订阅端
def subscriber():
    conf_str = ZenohConfFactory.create_sub().to_str()
    with ZenohSub(data_cls=ImagePacket640_480_3, conf=conf_str, key=topic) as sub:
        sub.wait_for_connection()
        frame = sub.read()
        print("收到一帧图像，时间戳(ns):", frame.timestamp_ns)
```

> 实际工程中推荐将发布端与订阅端分别部署在不同进程 / 不同节点上。

---


内部实现中，`ZenohWildCardSub` 会从 `sample.key_expr` 中解析实际的 key，并将最后一段（如 `front` / `left` / `right`）作为字典键。

---

## 与 `teleai_dds_wrapper` 的关系

- `teleai_dds_wrapper`：基于 DDS + Iceoryx 的早期通信方案，已经 **进入维护 / 兼容阶段**，不再推荐作为新项目首选。
- `teleai_zenoh_wrapper`：基于 Zenoh 的新一代通信封装，提供更简洁的 API 与更灵活的部署方式，是 **面向具身智能项目的推荐通信库**。

迁移建议：

- 新项目：直接使用 `teleai_zenoh_wrapper`
- 旧项目：在不影响生产的前提下，逐步将 DDS 通信入口迁移到 Zenoh 封装上

---

## 当前状态与共建

- 本项目目前主要用于 TeleAI 内部具身智能 / 机器人项目，接口仍在持续演进中
- 目标是在保证 **简单、稳定、易读** 的前提下，支撑多种实验形态与部署拓扑

欢迎提交 Issue / PR，一起打磨更好用的具身智能通信基础设施。


import time

import cv2
import numpy as np

from teleai_zenoh_wrapper.infoclasses import ImagePacket224_224_3
from teleai_zenoh_wrapper.utils import get_nano
from teleai_zenoh_wrapper import ZenohPub
from teleai_zenoh_wrapper.pubsub import ZenohConfFactory

# 直接复用 teleai_vla_deploy 里的 RealSense 封装
from realsense import RealSenseCamera


def main():
    # ===== 1. Zenoh 连接配置（指向你的 zenohd） =====
    zenohd_endpoints = ["tcp/192.168.100.10:7447"]  # 按需改成你的 router 地址

    conf_str = (
        ZenohConfFactory.create_pub()
        .set_mode("client")
        .set_connect_endpoints(zenohd_endpoints)
        .to_str()
    )

    # 发布的 topic 与 testing_cameras.yaml 保持一致
    camera_topic = "cameras/realsense_L515"

    # ===== 2. L515 相机配置（与 testing_cameras.yaml 对齐） =====
    serial_number = "f1421862"          # L515 的 SN
    color_resolution = (960, 540)       # (w, h)
    depth_resolution = (640, 480)       # 这里可以保留，虽然本例不需要深度

    # 初始化 RealSense 相机
    camera = RealSenseCamera(
        serial_number=serial_number,
        color_resolution=color_resolution,
        depth_resolution=depth_resolution,
        fps=30,
        enable_color=True,
        enable_depth=False,             # 本例只需要彩色
    )
    camera.start()

    print("=== L515 → 224x224x3 → Zenoh Pub 测试 ===\n")

    # 初始化 Zenoh 发布端
    print("[1] 正在创建 ZenohPub ...")
    pub = ZenohPub(
        data_cls=ImagePacket224_224_3,
        conf=conf_str,
        key=camera_topic,
    )
    print(f"    ZenohPub 创建成功，topic = {camera_topic}\n")

    try:
        while True:
            # RealSenseCamera.get_latest_frames() 返回：
            # (latest_color_image, latest_depth_image, latest_color_ts, latest_depth_ts)
            color_image, depth_image, color_ts, depth_ts = camera.get_latest_frames()

            if color_image is None:
                # 还没有拿到一帧图像，稍微等一会
                time.sleep(0.001)
                continue

            # ===== 3. 压缩到 224x224x3 =====
            resized = cv2.resize(color_image, (224, 224))
            resized_u8 = resized.astype(np.uint8)
            img_bytes = resized_u8.flatten().tobytes()

            # ===== 4. 打包成 ImagePacket224_224_3 并发布 =====
            pkt = ImagePacket224_224_3(
                timestamp_ns=np.uint64(get_nano()),
                img_buf=img_bytes,
            )
            pub.write(pkt)

            # 控制发送节奏（可按需调整或去掉）
            # time.sleep(1.0 / 30.0)

    except KeyboardInterrupt:
        print("\n[Ctrl+C] 停止发布。")
    finally:
        pub.close()
        camera.stop()
        print("=== 测试完成，资源已清理 ===")


if __name__ == "__main__":
    main()
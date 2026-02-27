import time

import cv2
import numpy as np

from teleai_zenoh_wrapper.infoclasses import ImagePacket224_224_3
from teleai_zenoh_wrapper import ZenohSub
from teleai_zenoh_wrapper.pubsub import ZenohConfFactory

import zenoh

def main():
    # 与 pub 端保持一致的 router 地址和 topic
    zenohd_endpoints = ["tcp/192.168.100.10:7447"]  # 按需修改
    camera_topic = "cameras/realsense_L515"

    conf_str = (
        ZenohConfFactory.create_default()
        .set_mode("client")
        .set_connect_endpoints(zenohd_endpoints)
        .to_str()
    )

    print("=== Zenoh Sub 图像显示 ===")
    print(f"连接到 {zenohd_endpoints}, 订阅 topic = {camera_topic}")

    session = zenoh.open(zenoh.Config.from_json5(conf_str))
    sub = ZenohSub(
        data_cls=ImagePacket224_224_3,
        session=session,
        key=camera_topic,
    )
    print("ZenohSub 创建成功，等待第一帧数据 ...")
    sub.wait_for_connection()

    try:
        while True:
            pkt = sub.read()
            if pkt is None:
                time.sleep(0.01)
                continue

            # 将 bytes 还原成 224x224x3 的图像
            img = np.frombuffer(pkt.img_buf, dtype=np.uint8)
            if img.size != 224 * 224 * 3:
                # 尺寸异常时跳过
                time.sleep(0.01)
                continue
            img = img.reshape(224, 224, 3)

            cv2.imshow("L515 224x224 RGB", img)
            # 30ms 刷新一次，按 q / Esc 退出
            key = cv2.waitKey(30) & 0xFF
            if key in (27, ord("q")):
                break

    except KeyboardInterrupt:
        pass
    finally:
        sub.close()
        cv2.destroyAllWindows()
        print("=== 订阅结束 ===")


if __name__ == "__main__":
    main()


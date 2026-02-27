import pyrealsense2 as rs
import numpy as np
import threading
import time
import cv2

class RealSenseCamera:
    def __init__(self, 
                 serial_number=None, 
                 color_resolution=(640, 480), 
                 depth_resolution=(640, 480), 
                 fps=30, 
                 enable_color=True, 
                 enable_depth=True,
                 align_to=rs.stream.color,
                 advanced_settings=None):
        """
        初始化 RealSense 相机
        :param serial_number: 相机 SN 码
        :param color_resolution: 彩色分辨率 (w, h)
        :param depth_resolution: 深度分辨率 (w, h)
        :param fps: 帧率
        :param enable_color: 启用彩色
        :param enable_depth: 启用深度
        :param align_to: 对齐目标 (rs.stream.color 或 None)
        :param advanced_settings: 高级参数字典，格式如下:
               {
                   'color': { rs.option.enable_auto_exposure: 0, rs.option.exposure: 156.0 },
                   'depth': { rs.option.visual_preset: rs.rs400_visual_preset.high_accuracy }
               }
        """
        self.serial_number = serial_number
        self.color_res = color_resolution
        self.depth_res = depth_resolution
        self.fps = fps
        self.enable_color = enable_color
        self.enable_depth = enable_depth
        self.align_to = align_to
        self.advanced_settings = advanced_settings # 保存设置字典

        self.pipeline = None
        self.config = None
        self.profile = None
        self.align = None
        
        self.running = False
        self.thread = None
        self.lock = threading.Lock()

        self.latest_color_image = None
        self.latest_depth_image = None
        self.latest_color_ts = 0
        self.latest_depth_ts = 0

    def start(self):
        self.pipeline = rs.pipeline()
        self.config = rs.config()

        if self.serial_number:
            self.config.enable_device(self.serial_number)

        if self.enable_depth:
            w, h = self.depth_res
            self.config.enable_stream(rs.stream.depth, w, h, rs.format.z16, self.fps)
        
        if self.enable_color:
            w, h = self.color_res
            self.config.enable_stream(rs.stream.color, w, h, rs.format.bgr8, self.fps)

        try:
            self.profile = self.pipeline.start(self.config)
            print(f"RealSense (SN: {self.serial_number if self.serial_number else 'Auto'}) started.")

            # --- 应用高级设置 (核心修改) ---
            if self.advanced_settings:
                self._apply_camera_settings()
            
            # 初始化对齐对象 (只有当两个流都开启时)
            if self.align_to is not None and self.enable_color and self.enable_depth:
                self.align = rs.align(self.align_to)

        except RuntimeError as e:
            print(f"Failed to start camera: {e}")
            raise

        self.running = True
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()

    def _apply_camera_settings(self):
        """解析并应���传感器参数"""
        print("Applying advanced settings...")
        device = self.profile.get_device()
        sensors = device.query_sensors()

        # 查找特定的传感器对象
        depth_sensor = next((s for s in sensors if s.is_depth_sensor()), None)
        # 彩色传感器通常不支持 is_depth_sensor，且负责 color stream
        color_sensor = None
        for s in sensors:
            if not s.is_depth_sensor() and s.get_stream_profiles():
                # 简单判断：非深度且有流配置大概率是RGB (严谨做法是检查流类型)
                color_sensor = s
                break

        # 应用深度设置
        if depth_sensor and 'depth' in self.advanced_settings:
            print("  - Configuring Depth Sensor")
            for option, value in self.advanced_settings['depth'].items():
                try:
                    depth_sensor.set_option(option, value)
                    print(f"    Set {option} = {value}")
                except Exception as e:
                    print(f"    WARNING: Failed to set depth option {option}: {e}")

        # 应用彩色设置
        if color_sensor and 'color' in self.advanced_settings:
            print("  - Configuring Color Sensor")
            for option, value in self.advanced_settings['color'].items():
                try:
                    # 注意：如果要设置手动曝光，通常必须先将 enable_auto_exposure 设为 0
                    color_sensor.set_option(option, value)
                    print(f"    Set {option} = {value}")
                except Exception as e:
                    print(f"    WARNING: Failed to set color option {option}: {e}")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        if self.pipeline:
            self.pipeline.stop()
            print("Camera stopped.")

    def _update(self):
        while self.running:
            try:
                frames = self.pipeline.wait_for_frames(timeout_ms=2000)
            except RuntimeError:
                continue

            if self.align:
                frames = self.align.process(frames)

            color_frame = frames.get_color_frame() if self.enable_color else None
            depth_frame = frames.get_depth_frame() if self.enable_depth else None

            if (self.enable_color and not color_frame) or (self.enable_depth and not depth_frame):
                continue

            c_img = np.asanyarray(color_frame.get_data()) if color_frame else None
            d_img = np.asanyarray(depth_frame.get_data()) if depth_frame else None
            c_ts = color_frame.get_timestamp() if color_frame else 0
            d_ts = depth_frame.get_timestamp() if depth_frame else 0

            with self.lock:
                if c_img is not None:
                    self.latest_color_image = c_img.copy()
                    self.latest_color_ts = c_ts
                if d_img is not None:
                    self.latest_depth_image = d_img.copy()
                    self.latest_depth_ts = d_ts

    def get_latest_frames(self):
        with self.lock:
            return (self.latest_color_image, self.latest_depth_image, 
                    self.latest_color_ts, self.latest_depth_ts)


# --- 测试程序 ---
if __name__ == "__main__":
    
    # 1. 定义想要修改的参数
    # 注意：字典是有序的 (Python 3.7+)，这很重要。
    # 必须���关闭自动曝光，才能设置曝光值。
    custom_settings = {
        'color': {
            rs.option.enable_auto_exposure: 0.0, # 0.0 = 关闭自动曝光
            rs.option.exposure: 156.0,           # 设置固定曝光时间 (ms * 10 左右，具体看文档，D435是100微秒单位)
            rs.option.gain: 64.0,                # 设置增益
            rs.option.brightness: 0.0,
            rs.option.contrast: 50.0
        },
        'depth': {
            # rs.option.visual_preset 是枚举，用于加载预设配置 (High Density, High Accuracy 等)
            rs.option.visual_preset: float(rs.rs400_visual_preset.high_density),
            rs.option.laser_power: 150.0 # 激光发射器功率 (0-360)
        }
    }

    # 2. 也可以传入 None，这样相机就是全自动模式
    # custom_settings = None 

    cam = RealSenseCamera(
        color_resolution=(640, 480),
        depth_resolution=(640, 480),
        fps=30,
        enable_color=True,
        enable_depth=True,
        align_to=rs.stream.color,
        advanced_settings=custom_settings # <-- 传入配置
    )
    
    try:
        cam.start()
        
        # 简单查看 100 帧并检查参数效果
        for i in range(100):
            c_img, d_img, _, _ = cam.get_latest_frames()
            
            if c_img is not None:
                cv2.imshow("Color (Manual Exp)", c_img)
            
            # if d_img is not None:
                # 简单的深度可视化
                # d_map = cv2.applyColorMap(cv2.convertScaleAbs(d_img, alpha=0.03), cv2.COLORMAP_JET)
                # cv2.imshow("Depth", d_map)

            key = cv2.waitKey(30)
            if key == 27: break
            
    finally:
        cam.stop()
        cv2.destroyAllWindows()
import os
import time
import subprocess
from typing import Optional

import psutil

from teleai_zenoh_wrapper.utils import logger


def _get_running_zenohd_process() -> Optional[psutil.Process]:
    """
    查找正在运行的 zenohd 进程。

    返回:
        psutil.Process 或 None
    """
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = proc.info.get("name") or ""
            cmdline = " ".join(proc.info.get("cmdline") or [])
            if "zenohd" in name or "zenohd" in cmdline:
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return None


def _is_zenohd_config_match(proc: psutil.Process, config_path: str) -> bool:
    """
    检查 zenohd 是否使用了期望的配置文件。
    目前简单地判断 config_path 是否出现在进程的命令行参数中。
    """
    try:
        cmdline = proc.info.get("cmdline") or []
        if not cmdline:
            return False
        if config_path in cmdline:
            return True
        logger.info(
            f"[zenohd Monitor] Found process PID {proc.pid}, "
            f"but config doesn't match."
        )
        logger.info(f"[zenohd Monitor] Current cmdline: {cmdline}")
        return False
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def _start_zenohd(executable: str, config_path: str) -> None:
    """
    启动 zenohd 进程。
    """
    if not os.path.exists(config_path):
        logger.warning(
            f"[zenohd Monitor] Config file not found at {config_path}"
        )

    logger.info(
        f"[zenohd Monitor] Starting '{executable}' with config {config_path}..."
    )

    cmd = [executable, "--config", config_path]

    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )
        logger.info("[zenohd Monitor] Start command issued.")
        time.sleep(1)
    except FileNotFoundError:
        logger.error(
            f"[zenohd Monitor] Error: Executable '{executable}' not found in PATH."
        )
    except Exception as e:
        logger.error(f"[zenohd Monitor] Failed to start process: {e}")


def _check_and_start_zenohd(
    ZENOH_EXECUTABLE: str,
    EXPECTED_CONFIG_PATH: Optional[str],
) -> None:
    """
    检查并按需启动 zenohd。

    - 如果 EXPECTED_CONFIG_PATH 为空/None，则不做任何检查与启动。
    - 若已有 zenohd 进程在运行且配置不匹配，则尝试结束后用期望配置重启。
    - 若没有运行中的 zenohd，则直接用期望配置启动。
    """
    if not EXPECTED_CONFIG_PATH:
        logger.debug(
            "[zenohd Monitor] Empty config path provided, skip check and start."
        )
        return

    logger.debug("[zenohd Monitor] Checking zenohd status...")
    zenohd_proc = _get_running_zenohd_process()
    should_start = False

    if zenohd_proc:
        logger.debug(
            f"[zenohd Monitor] zenohd is running (PID: {zenohd_proc.info['pid']})."
        )
        if not _is_zenohd_config_match(zenohd_proc, EXPECTED_CONFIG_PATH):
            logger.warning(
                "[zenohd Monitor] Config mismatch detected, killing old process..."
            )
            try:
                zenohd_proc.terminate()
                zenohd_proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                logger.warning(
                    "[zenohd Monitor] Process stuck, forcing kill..."
                )
                zenohd_proc.kill()
            should_start = True
        else:
            logger.debug(
                "[zenohd Monitor] Existing zenohd matches expected config."
            )
    else:
        logger.warning("[zenohd Monitor] zenohd is NOT running.")
        should_start = True

    if should_start:
        _start_zenohd(ZENOH_EXECUTABLE, EXPECTED_CONFIG_PATH)

        time.sleep(1)
        if _get_running_zenohd_process():
            logger.info("[zenohd Monitor] Recovery successful. zenohd is up.")
        else:
            logger.error("[zenohd Monitor] Recovery failed.")


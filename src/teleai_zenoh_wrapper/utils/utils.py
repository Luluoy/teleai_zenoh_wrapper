import os
import time

import ctypes
import os

class Timespec(ctypes.Structure):
    _fields_ = [
        ("tv_sec", ctypes.c_long),
        ("tv_nsec", ctypes.c_long)
    ]

libc = ctypes.CDLL("libc.so.6")
nanosleep_func = libc.nanosleep

def nano_sleep(ns):
    req = Timespec(ns // 1_000_000_000, ns % 1_000_000_000)
    rem = Timespec(0, 0)
    nanosleep_func(ctypes.byref(req), ctypes.byref(rem))

def get_nano():
    return time.clock_gettime_ns(time.CLOCK_REALTIME)
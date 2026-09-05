"""Windows 进程守护: 通过 Job 对象使子进程随主程序一同终止

直接关闭主程序终端窗口或进程被强杀时, Python 层的清理逻辑不会执行, 子进程会成为
孤儿进程; 将子进程绑定至带 KILL_ON_JOB_CLOSE 标志的 Job 对象后, 内核会在主程序
进程终止时关闭 Job 句柄, 从而自动终止 Job 内的所有子进程。
"""
import ctypes
import os
from ctypes import wintypes

JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOBOBJECT_EXTENDED_LIMIT_INFORMATION = 9  # SetInformationJobObject 的信息类别


class _IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in (
        'ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
        'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]


class _BasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ('PerProcessUserTimeLimit', ctypes.c_longlong),
        ('PerJobUserTimeLimit', ctypes.c_longlong),
        ('LimitFlags', wintypes.DWORD),
        ('MinimumWorkingSetSize', ctypes.c_size_t),
        ('MaximumWorkingSetSize', ctypes.c_size_t),
        ('ActiveProcessLimit', wintypes.DWORD),
        ('Affinity', ctypes.c_size_t),
        ('PriorityClass', wintypes.DWORD),
        ('SchedulingClass', wintypes.DWORD),
    ]


class _ExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ('BasicLimitInformation', _BasicLimitInformation),
        ('IoInfo', _IoCounters),
        ('ProcessMemoryLimit', ctypes.c_size_t),
        ('JobMemoryLimit', ctypes.c_size_t),
        ('PeakProcessMemoryUsed', ctypes.c_size_t),
        ('PeakJobMemoryUsed', ctypes.c_size_t),
    ]


def bind_to_parent(process):  # 将子进程绑定至守护Job, 绑定成功返回True(非Windows平台或绑定失败返回False)
    if os.name != 'nt':
        return False
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return False
    limit = _ExtendedLimitInformation()
    limit.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(job, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
                                            ctypes.byref(limit), ctypes.sizeof(limit)):
        kernel32.CloseHandle(job)
        return False
    if not kernel32.AssignProcessToJobObject(job, int(process._handle)):
        kernel32.CloseHandle(job)
        return False
    return True  # job 句柄有意保持打开: 本程序进程终止时内核随之关闭句柄并终止Job内全部进程

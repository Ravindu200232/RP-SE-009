"""Own subprocess trees, including children whose Windows parent exits early."""
from __future__ import annotations

import os
import signal
import subprocess
import time


def spawn_owned(argv, **kwargs):
    if os.name != "nt":
        return subprocess.Popen(argv, start_new_session=True, **kwargs)
    import ctypes
    from ctypes import wintypes

    class BasicLimits(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]
    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in
                    ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                     "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]
    class ExtendedLimits(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BasicLimits), ("IoInfo", IoCounters),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateJobObjectW(None, None)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    limits = ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
    proc = None
    try:
        if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        # Assign before execution, so even a fast shell's children belong to
        # the job. NtResumeProcess resumes its suspended initial thread.
        proc = subprocess.Popen(argv, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 0x4 |
                                subprocess.CREATE_NO_WINDOW, **kwargs)
        if not kernel.AssignProcessToJobObject(handle, int(proc._handle)):
            raise ctypes.WinError(ctypes.get_last_error())
        resume = ctypes.WinDLL("ntdll").NtResumeProcess
        resume.argtypes, resume.restype = [wintypes.HANDLE], ctypes.c_long
        if resume(int(proc._handle)) != 0:
            raise OSError("Could not resume the owned process")
        proc._preview_job = handle
        return proc
    except BaseException:
        if proc is not None:
            proc.kill()
            proc.wait(timeout=5)
        kernel.CloseHandle(handle)
        raise


def stop_owned(proc):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        handle = getattr(proc, "_preview_job", None)
        if handle:
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
            class Accounting(ctypes.Structure):
                _fields_ = [(name, ctypes.c_longlong) for name in
                    ('user', 'kernel', 'period_user', 'period_kernel')] + [
                    (name, wintypes.DWORD) for name in ('faults', 'total', 'active', 'terminated')]
            try:
                if not kernel.TerminateJobObject(handle, 0):
                    raise ctypes.WinError(ctypes.get_last_error())
                # Wait for child process tree termination to prevent port bind collisions.
                deadline = time.monotonic() + 5
                accounting = Accounting()
                while time.monotonic() < deadline:
                    if not kernel.QueryInformationJobObject(handle, 1, ctypes.byref(accounting),
                                                            ctypes.sizeof(accounting), None):
                        raise ctypes.WinError(ctypes.get_last_error())
                    if not accounting.active:
                        break
                    time.sleep(.01)
            finally:
                kernel.CloseHandle(handle)
                proc._preview_job = None
        elif proc.poll() is None:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        # spawn_owned starts a new session whose process-group id is the
        # original pid. It still identifies children after the parent exits.
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=4)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            pass
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

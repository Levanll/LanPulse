"""后台任务执行器。

体检与修复都是阻塞型系统调用（PowerShell 每次 1-3 秒），必须离开 UI 线程，
否则窗口会白屏。这里用 QThreadPool + QRunnable 提供"一个任务、一个进度、一个结果"
的最小模型，不引入 asyncio（Qt 事件循环与 asyncio 混用会带来生命周期问题）。
"""
from __future__ import annotations

import inspect
import logging
import traceback
from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

log = logging.getLogger("netpulse.worker")


@dataclass
class TaskResult:
    ok: bool
    value: Any = None
    error: str = ""


class _Signals(QObject):
    progress = Signal(int, int, str)   # done, total, 说明
    finished = Signal(object)           # TaskResult
    failed = Signal(str)


class _Runnable(QRunnable):
    def __init__(self, fn: Callable[..., Any], kwargs: dict[str, Any]) -> None:
        super().__init__()
        self.fn = fn
        self.kwargs = kwargs
        self.signals = _Signals()
        self._cancelled = False
        self.setAutoDelete(True)

    def cancel(self) -> None:
        self._cancelled = True

    def report(self, done: int, total: int, text: str = "") -> None:
        self.signals.progress.emit(done, total, text)

    def is_cancelled(self) -> bool:
        return self._cancelled

    @Slot()
    def run(self) -> None:
        try:
            # 只有任务函数显式声明了 progress 形参时才注入进度回调，
            # 这样同一 runner 既能跑带进度的体检，也能跑无进度的简单操作。
            if "progress" in inspect.signature(self.fn).parameters:
                self.kwargs = {**self.kwargs, "progress": self.report}
            value = self.fn(**self.kwargs)
            self.signals.finished.emit(TaskResult(ok=True, value=value))
        except Exception as exc:  # noqa: BLE001 - 后台任务异常必须回到 UI 展示
            log.error("后台任务失败: %s\n%s", exc, traceback.format_exc())
            self.signals.finished.emit(TaskResult(ok=False, error=f"{type(exc).__name__}: {exc}"))


class TaskRunner(QObject):
    """UI 侧的任务发起器。同一 runner 串行化，避免体检与修复并发改状态。"""

    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int, str)
    started = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._current: _Runnable | None = None
        self.busy = False

    def run(self, fn: Callable[..., Any], **kwargs: Any) -> bool:
        if self.busy:
            return False
        r = _Runnable(fn, kwargs)
        r.signals.progress.connect(self.progress)
        r.signals.finished.connect(self._on_done)
        r.signals.failed.connect(self.failed)
        self._current = r
        self.busy = True
        self.started.emit()
        self._pool.start(r)
        return True

    def cancel(self) -> None:
        if self._current is not None:
            self._current.cancel()

    @Slot(object)
    def _on_done(self, res: TaskResult) -> None:
        self.busy = False
        self._current = None
        if res.ok:
            self.finished.emit(res.value)
        else:
            self.failed.emit(res.error)

    def wait(self, msec: int = 5000) -> bool:
        return self._pool.waitForDone(msec)


__all__ = ["TaskRunner", "TaskResult"]

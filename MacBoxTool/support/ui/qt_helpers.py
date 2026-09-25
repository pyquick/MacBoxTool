"""
qt_helpers.py: Small Qt helpers shared by the GUI pages.

Imports Qt only (no other project modules), so it is safe to import from any
page in any order.

The two helpers here replace patterns that had been copy-pasted across the
page modules: clearing a layout before rebuilding it, and shutting a page's
workers down on close.
"""


def clear_layout(layout, *, recursive: bool = False) -> None:
    """
    Remove every item from `layout`, deleting any widgets it held.

    Mirrors the loop that was duplicated across the pages exactly: items are
    detached via takeAt(), widgets are scheduled for deletion, and *sub-layouts
    are simply detached* — their child widgets are left alone. That last detail
    matters, because pages clear-then-rebuild and rely on the old sub-layout
    widgets still being alive while they do so.

    Pass `recursive=True` to also recurse into detached sub-layouts and delete
    their widgets (the asset-converter page needs this).
    """
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.deleteLater()
        elif recursive and item.layout():
            clear_layout(item.layout(), recursive=True)


class WorkerShutdownMixin:
    """
    Gives a page a `closeEvent` that shuts its workers down first.

    Subclasses supply `cleanup_workers(deadline=None)`; only the close handling
    is shared, because each page's actual shutdown differs (some stop QThreads,
    some join a threading.Thread, some also stop timers or unregister from the
    task manager).

    Place it first in the bases so `super().closeEvent(event)` still reaches the
    Qt widget:

        class MyPage(WorkerShutdownMixin, ScrollArea):
            def cleanup_workers(self, deadline=None):
                stop_qt_workers((self.worker,), deadline=deadline)
    """

    def closeEvent(self, event):
        self.cleanup_workers()
        super().closeEvent(event)

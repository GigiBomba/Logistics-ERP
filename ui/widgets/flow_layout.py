"""Flow layout that wraps child widgets to new rows when horizontal space runs out.

Extracted from ``ui.views.route_planner_view`` for reuse across the app.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QSizePolicy


class FlowLayout(QLayout):
    """Horizontal flow layout that wraps items to new rows when width is exhausted."""

    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing if spacing >= 0 else 4)
        self._items: list[QLayout] = []

    def __del__(self):
        while self._items:
            self._items.pop()

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect, test_only):
        x = rect.x() + self.contentsMargins().left()
        y = rect.y() + self.contentsMargins().top()
        line_height = 0
        spacing = self.spacing()

        for item in self._items:
            widget = item.widget()
            if widget is None:
                continue
            space_x = spacing
            space_y = spacing
            next_x = x + widget.sizeHint().width() + space_x
            if next_x - space_x > rect.right() + 1 and line_height > 0:
                x = rect.x() + self.contentsMargins().left()
                y += line_height + space_y
                next_x = x + widget.sizeHint().width() + space_x
                line_height = 0
            if not test_only:
                widget.setGeometry(QRect(QPoint(x, y), widget.sizeHint()))
            x = next_x
            line_height = max(line_height, widget.sizeHint().height())

        return y + line_height - rect.y() + self.contentsMargins().bottom()

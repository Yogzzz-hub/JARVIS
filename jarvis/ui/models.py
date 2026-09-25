"""QAbstractListModel implementations for Activity DAG, Tasks, Workflows, and Memory."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, Qt

from jarvis.ui.events import redact_sensitive_text


class ActivityListModel(QAbstractListModel):
    """Model for tasks in the Activity timeline."""

    IdRole = Qt.ItemDataRole.UserRole + 1
    RequestRole = Qt.ItemDataRole.UserRole + 2
    StateRole = Qt.ItemDataRole.UserRole + 3
    SourceRole = Qt.ItemDataRole.UserRole + 4
    RouteRole = Qt.ItemDataRole.UserRole + 5
    DurationRole = Qt.ItemDataRole.UserRole + 6
    MessageRole = Qt.ItemDataRole.UserRole + 7
    TimestampRole = Qt.ItemDataRole.UserRole + 8
    VerifiedRole = Qt.ItemDataRole.UserRole + 9

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[dict[str, Any]] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        item = self._items[index.row()]
        if role == self.IdRole:
            return item.get("request_id", "")
        if role == self.RequestRole:
            return item.get("text", "")
        if role == self.StateRole:
            return item.get("state", "UNKNOWN")
        if role == self.SourceRole:
            return item.get("source", "desktop")
        if role == self.RouteRole:
            return item.get("route", "SmartRouter")
        if role == self.DurationRole:
            return item.get("duration", "—")
        if role == self.MessageRole:
            return item.get("message", "")
        if role == self.TimestampRole:
            return item.get("timestamp", "")
        if role == self.VerifiedRole:
            return item.get("verified", True)
        return None

    def roleNames(self) -> dict[int, QByteArray]:
        return {
            self.IdRole: QByteArray(b"requestId"),
            self.RequestRole: QByteArray(b"requestText"),
            self.StateRole: QByteArray(b"taskState"),
            self.SourceRole: QByteArray(b"taskSource"),
            self.RouteRole: QByteArray(b"taskRoute"),
            self.DurationRole: QByteArray(b"taskDuration"),
            self.MessageRole: QByteArray(b"taskMessage"),
            self.TimestampRole: QByteArray(b"taskTimestamp"),
            self.VerifiedRole: QByteArray(b"taskVerified"),
        }

    def add_task(self, item: dict[str, Any]) -> None:
        clean = {k: redact_sensitive_text(v) if isinstance(v, str) else v for k, v in item.items()}
        self.beginInsertRows(QModelIndex(), 0, 0)
        self._items.insert(0, clean)
        if len(self._items) > 50:
            self._items.pop()
        self.endInsertRows()

    def clear(self) -> None:
        self.beginResetModel()
        self._items.clear()
        self.endResetModel()

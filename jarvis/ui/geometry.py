"""Procedural meshes for the 3D reactor (Qt Quick 3D).

Built in Python so the 3D HUD works on every Qt >= 6.5 (the built-in torus helper needs 6.9)
and each ring is a single draw call. Imported by ``jarvis.ui.app`` which registers the types
under the QML module ``Jarvis3D``.
"""
from __future__ import annotations

import math
import struct

from PySide6.QtCore import Property, Signal
from PySide6.QtGui import QVector3D
from PySide6.QtQml import QmlElement
from PySide6.QtQuick3D import QQuick3DGeometry

QML_IMPORT_NAME = "Jarvis3D"
QML_IMPORT_MAJOR_VERSION = 1

_STRIDE = 6 * 4  # position xyz + normal xyz, float32


def hud_ring_mesh(inner: float, outer: float, dashes: int, gap: float, steps: int) -> tuple[bytes, bytes, int]:
    """Flat (XY plane) annulus split into ``dashes`` arcs separated by ``gap`` (fraction of each slot)."""
    dashes = max(1, int(dashes))
    gap = min(0.9, max(0.0, float(gap))) if dashes > 1 else 0.0
    steps = max(1, int(steps))
    slot = 2 * math.pi / dashes
    arc = slot * (1.0 - gap)
    verts: list[float] = []
    idx: list[int] = []
    for d in range(dashes):
        start = d * slot
        base = len(verts) // 6
        for s in range(steps + 1):
            a = start + arc * s / steps
            c, si = math.cos(a), math.sin(a)
            verts += [inner * c, inner * si, 0.0, 0.0, 0.0, 1.0]
            verts += [outer * c, outer * si, 0.0, 0.0, 0.0, 1.0]
        for s in range(steps):
            i0 = base + 2 * s
            idx += [i0, i0 + 1, i0 + 2, i0 + 1, i0 + 3, i0 + 2]
    return struct.pack(f"<{len(verts)}f", *verts), struct.pack(f"<{len(idx)}I", *idx), len(idx)


def torus_mesh(radius: float, tube: float, rings: int, sides: int) -> tuple[bytes, bytes, int]:
    """Closed torus around the Z axis (lies in the XY plane)."""
    rings, sides = max(3, int(rings)), max(3, int(sides))
    verts: list[float] = []
    idx: list[int] = []
    for i in range(rings + 1):
        u = 2 * math.pi * i / rings
        cu, su = math.cos(u), math.sin(u)
        for j in range(sides + 1):
            v = 2 * math.pi * j / sides
            cv, sv = math.cos(v), math.sin(v)
            x, y, z = (radius + tube * cv) * cu, (radius + tube * cv) * su, tube * sv
            verts += [x, y, z, cv * cu, cv * su, sv]
    for i in range(rings):
        for j in range(sides):
            a = i * (sides + 1) + j
            b = a + sides + 1
            idx += [a, b, a + 1, b, b + 1, a + 1]
    return struct.pack(f"<{len(verts)}f", *verts), struct.pack(f"<{len(idx)}I", *idx), len(idx)


class _MeshBase(QQuick3DGeometry):
    def _upload(self, vertices: bytes, indices: bytes, extent_xy: float, extent_z: float) -> None:
        self.clear()
        self.setStride(_STRIDE)
        self.setVertexData(vertices)
        self.setIndexData(indices)
        self.setPrimitiveType(QQuick3DGeometry.PrimitiveType.Triangles)
        self.addAttribute(QQuick3DGeometry.Attribute.Semantic.PositionSemantic, 0,
                          QQuick3DGeometry.Attribute.ComponentType.F32Type)
        self.addAttribute(QQuick3DGeometry.Attribute.Semantic.NormalSemantic, 12,
                          QQuick3DGeometry.Attribute.ComponentType.F32Type)
        self.addAttribute(QQuick3DGeometry.Attribute.Semantic.IndexSemantic, 0,
                          QQuick3DGeometry.Attribute.ComponentType.U32Type)
        self.setBounds(QVector3D(-extent_xy, -extent_xy, -extent_z), QVector3D(extent_xy, extent_xy, extent_z))
        self.update()


@QmlElement
class HudRingGeometry(_MeshBase):
    """Dashed holographic ring (flat), e.g. ``HudRingGeometry { innerRadius: 90; outerRadius: 96; dashes: 48 }``."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._inner, self._outer, self._dashes, self._gap, self._steps = 90.0, 96.0, 1, 0.0, 96
        self._rebuild()

    def _rebuild(self) -> None:
        steps = self._steps if self._dashes == 1 else max(2, self._steps // self._dashes)
        v, i, _ = hud_ring_mesh(self._inner, self._outer, self._dashes, self._gap, steps)
        self._upload(v, i, self._outer, 0.01)

    def _set(self, name: str, value) -> None:
        if getattr(self, name) != value:
            setattr(self, name, value)
            self._rebuild()
            self.changed.emit()

    innerRadius = Property(float, lambda s: s._inner, lambda s, v: s._set("_inner", float(v)), notify=changed)
    outerRadius = Property(float, lambda s: s._outer, lambda s, v: s._set("_outer", float(v)), notify=changed)
    dashes = Property(int, lambda s: s._dashes, lambda s, v: s._set("_dashes", max(1, int(v))), notify=changed)
    gap = Property(float, lambda s: s._gap, lambda s, v: s._set("_gap", float(v)), notify=changed)
    steps = Property(int, lambda s: s._steps, lambda s, v: s._set("_steps", max(8, int(v))), notify=changed)


@QmlElement
class TubeRingGeometry(_MeshBase):
    """Solid torus ring, e.g. ``TubeRingGeometry { radius: 110; tube: 1.6 }``."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._radius, self._tube, self._rings, self._sides = 110.0, 1.5, 128, 12
        self._rebuild()

    def _rebuild(self) -> None:
        v, i, _ = torus_mesh(self._radius, self._tube, self._rings, self._sides)
        self._upload(v, i, self._radius + self._tube, self._tube)

    def _set(self, name: str, value) -> None:
        if getattr(self, name) != value:
            setattr(self, name, value)
            self._rebuild()
            self.changed.emit()

    radius = Property(float, lambda s: s._radius, lambda s, v: s._set("_radius", float(v)), notify=changed)
    tube = Property(float, lambda s: s._tube, lambda s, v: s._set("_tube", float(v)), notify=changed)
    segments = Property(int, lambda s: s._rings, lambda s, v: s._set("_rings", max(3, int(v))), notify=changed)
    sides = Property(int, lambda s: s._sides, lambda s, v: s._set("_sides", max(3, int(v))), notify=changed)

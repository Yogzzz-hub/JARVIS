import QtQuick
import QtQuick.Shapes
import "palette.js" as Palette

// Lightweight 2D reactor (GPU-rendered vector shapes). Used for small orbs, overlays and as
// the fallback when Qt Quick 3D is unavailable or low-resource mode is on.
Item {
    id: root
    property string assistantState: "IDLE"
    property bool lowResourceMode: false
    property real orbSize: 120
    property real level: 0.0

    width: orbSize
    height: orbSize

    readonly property color orbColor: Palette.stateColor(assistantState)
    readonly property bool busy: Palette.isBusy(assistantState)
    readonly property bool detailed: orbSize >= 64
    property real phase: 0.0
    property real energy: 0.0

    FrameAnimation {
        running: !root.lowResourceMode && root.visible
        onTriggered: {
            var dt = Math.min(frameTime, 0.05)
            root.phase += dt * Palette.speed(root.assistantState)
            var speaking = root.assistantState === "SPEAKING" ? 0.3 + 0.3 * Math.abs(Math.sin(root.phase * 7.0)) : 0.0
            var target = Math.max(Math.min(1.0, root.level * 1.4), speaking)
            root.energy += (target - root.energy) * (target > root.energy ? 0.4 : 0.08)
        }
    }

    // Soft halo
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        opacity: root.assistantState === "OFFLINE" ? 0.25 : 0.55 + root.energy * 0.45
        ShapePath {
            strokeWidth: 0
            strokeColor: "transparent"
            fillGradient: RadialGradient {
                centerX: root.width / 2; centerY: root.height / 2
                focalX: centerX; focalY: centerY
                centerRadius: root.width / 2
                focalRadius: 0
                GradientStop { position: 0.0; color: Qt.rgba(root.orbColor.r, root.orbColor.g, root.orbColor.b, 0.55) }
                GradientStop { position: 0.35; color: Qt.rgba(root.orbColor.r, root.orbColor.g, root.orbColor.b, 0.18) }
                GradientStop { position: 1.0; color: "transparent" }
            }
            PathAngleArc { centerX: root.width / 2; centerY: root.height / 2; radiusX: root.width / 2; radiusY: root.height / 2; startAngle: 0; sweepAngle: 360 }
        }
    }

    // Outer dashed ring
    Shape {
        anchors.fill: parent
        visible: root.detailed
        preferredRendererType: Shape.CurveRenderer
        rotation: root.phase * 10
        ShapePath {
            strokeColor: Qt.rgba(root.orbColor.r, root.orbColor.g, root.orbColor.b, 0.7)
            strokeWidth: Math.max(1, root.width * 0.012)
            fillColor: "transparent"
            strokeStyle: ShapePath.DashLine
            dashPattern: [1.2, 2.2]
            PathAngleArc { centerX: root.width / 2; centerY: root.height / 2; radiusX: root.width * 0.46; radiusY: root.height * 0.46; startAngle: 0; sweepAngle: 360 }
        }
    }

    // Three bold arcs (spin fast while thinking)
    Repeater {
        model: 3
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            rotation: -root.phase * (root.busy ? 70 : 24) + index * 120
            ShapePath {
                strokeColor: root.orbColor
                strokeWidth: Math.max(1.5, root.width * 0.035)
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                PathAngleArc { centerX: root.width / 2; centerY: root.height / 2; radiusX: root.width * 0.39; radiusY: root.height * 0.39; startAngle: 0; sweepAngle: 78 }
            }
        }
    }

    // Voice ring
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        scale: 1.0 + root.energy * 0.25
        opacity: 0.25 + root.energy * 0.75
        ShapePath {
            strokeColor: root.orbColor
            strokeWidth: Math.max(1, root.width * 0.015)
            fillColor: "transparent"
            PathAngleArc { centerX: root.width / 2; centerY: root.height / 2; radiusX: root.width * 0.29; radiusY: root.height * 0.29; startAngle: 0; sweepAngle: 360 }
        }
    }

    // Core
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        scale: 1.0 + root.energy * 0.18
        ShapePath {
            strokeWidth: 0
            strokeColor: "transparent"
            fillGradient: RadialGradient {
                centerX: root.width / 2; centerY: root.height / 2
                focalX: centerX; focalY: centerY
                centerRadius: root.width * 0.2
                focalRadius: 0
                GradientStop { position: 0.0; color: "white" }
                GradientStop { position: 0.45; color: Qt.lighter(root.orbColor, 1.3) }
                GradientStop { position: 1.0; color: Qt.rgba(root.orbColor.r, root.orbColor.g, root.orbColor.b, 0.0) }
            }
            PathAngleArc { centerX: root.width / 2; centerY: root.height / 2; radiusX: root.width * 0.2; radiusY: root.height * 0.2; startAngle: 0; sweepAngle: 360 }
        }
    }
}

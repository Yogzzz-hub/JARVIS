import QtQuick

// Frosted-glass card: layered gradient, inner highlight, animated glow border, and a subtle noise texture.
Rectangle {
    id: root
    property color glowColor: "#00E5FF"
    property real blurRadius: 10
    property bool activeBorder: false

    radius: 16
    border.width: 1
    border.color: activeBorder ? glowColor : Qt.rgba(0.55, 0.75, 1.0, 0.10)
    gradient: Gradient {
        GradientStop { position: 0.0; color: Qt.rgba(0.11, 0.15, 0.22, 0.85) }
        GradientStop { position: 0.5; color: Qt.rgba(0.07, 0.10, 0.16, 0.88) }
        GradientStop { position: 1.0; color: Qt.rgba(0.05, 0.07, 0.11, 0.92) }
    }
    Behavior on border.color { ColorAnimation { duration: 220 } }

    // top-edge sheen — subtle specular highlight
    Rectangle {
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 1 }
        height: Math.min(parent.height / 2, 50)
        radius: root.radius
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0.06) }
            GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.02) }
            GradientStop { position: 1.0; color: Qt.rgba(1, 1, 1, 0.0) }
        }
    }

    // left-edge accent line (tinted)
    Rectangle {
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
        anchors.topMargin: root.radius
        anchors.bottomMargin: root.radius
        width: 1
        gradient: Gradient {
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 0.5; color: Qt.rgba(root.glowColor.r, root.glowColor.g, root.glowColor.b, 0.08) }
            GradientStop { position: 1.0; color: "transparent" }
        }
    }

    // outer glow when active — dual-layer for softer bloom
    Rectangle {
        anchors.fill: parent
        anchors.margins: -2
        radius: root.radius + 2
        color: "transparent"
        border.width: 2
        border.color: Qt.rgba(root.glowColor.r, root.glowColor.g, root.glowColor.b,
                              root.activeBorder ? 0.3 : 0.0)
        visible: root.activeBorder
        z: -1
        Behavior on border.color { ColorAnimation { duration: 250 } }
    }
    Rectangle {
        anchors.fill: parent
        anchors.margins: -5
        radius: root.radius + 5
        color: "transparent"
        border.width: 4
        border.color: Qt.rgba(root.glowColor.r, root.glowColor.g, root.glowColor.b,
                              root.activeBorder ? 0.10 : 0.0)
        visible: root.activeBorder
        z: -2
        Behavior on border.color { ColorAnimation { duration: 300 } }
    }
}

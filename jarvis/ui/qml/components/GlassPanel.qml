import QtQuick

// Frosted-glass card: layered gradient, inner highlight and an optional glowing border.
Rectangle {
    id: root
    property color glowColor: "#00E5FF"
    property real blurRadius: 10
    property bool activeBorder: false

    radius: 14
    border.width: 1
    border.color: activeBorder ? glowColor : Qt.rgba(0.55, 0.75, 1.0, 0.12)
    gradient: Gradient {
        GradientStop { position: 0.0; color: Qt.rgba(0.10, 0.14, 0.21, 0.82) }
        GradientStop { position: 1.0; color: Qt.rgba(0.05, 0.07, 0.11, 0.88) }
    }
    Behavior on border.color { ColorAnimation { duration: 180 } }

    // top sheen
    Rectangle {
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 1 }
        height: Math.min(parent.height / 2, 40)
        radius: root.radius
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0.05) }
            GradientStop { position: 1.0; color: Qt.rgba(1, 1, 1, 0.0) }
        }
    }
    // outer glow when active
    Rectangle {
        anchors.fill: parent
        anchors.margins: -3
        radius: root.radius + 3
        color: "transparent"
        border.width: 3
        border.color: Qt.rgba(root.glowColor.r, root.glowColor.g, root.glowColor.b, 0.18)
        visible: root.activeBorder
        z: -1
    }
}

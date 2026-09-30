import QtQuick

// Holographic glass panel: translucent blue glass, a thin cyan edge, a bright top rim, HUD corner brackets and a
// faint scanline texture. Every card on every page is one of these, so the whole app shares one look.
Rectangle {
    id: root
    property color glowColor: "#00E5FF"
    property real blurRadius: 10          // kept for compatibility
    property bool activeBorder: false
    property bool brackets: true
    property bool hovered: hoverWatch.containsMouse

    radius: 14
    border.width: 1
    border.color: activeBorder ? Qt.rgba(glowColor.r, glowColor.g, glowColor.b, 0.85)
                               : Qt.rgba(0.35, 0.8, 1.0, hovered ? 0.30 : 0.16)
    gradient: Gradient {
        GradientStop { position: 0.0; color: Qt.rgba(0.06, 0.15, 0.27, 0.80) }
        GradientStop { position: 0.55; color: Qt.rgba(0.04, 0.09, 0.17, 0.84) }
        GradientStop { position: 1.0; color: Qt.rgba(0.03, 0.06, 0.12, 0.88) }
    }
    Behavior on border.color { ColorAnimation { duration: 220 } }

    MouseArea { id: hoverWatch; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton; z: -10 }

    // scanlines
    Canvas {
        anchors.fill: parent
        anchors.margins: 1
        opacity: 0.05
        onPaint: {
            var ctx = getContext("2d");
            ctx.clearRect(0, 0, width, height);
            ctx.fillStyle = "#9FE8FF";
            for (var y = 0; y < height; y += 3) ctx.fillRect(0, y, width, 1);
        }
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
    }

    // top rim light
    Rectangle {
        anchors { left: parent.left; right: parent.right; top: parent.top; leftMargin: root.radius; rightMargin: root.radius }
        height: 1
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 0.5; color: Qt.rgba(root.glowColor.r, root.glowColor.g, root.glowColor.b, root.activeBorder || root.hovered ? 0.9 : 0.55) }
            GradientStop { position: 1.0; color: "transparent" }
        }
    }
    // inner sheen
    Rectangle {
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 1 }
        height: Math.min(parent.height / 2, 46)
        radius: root.radius
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(0.6, 0.9, 1.0, 0.06) }
            GradientStop { position: 1.0; color: "transparent" }
        }
    }

    // HUD corner brackets
    Repeater {
        model: root.brackets && root.width > 90 && root.height > 50 ? 4 : 0
        Item {
            width: 14; height: 14
            x: index % 2 === 0 ? -1 : root.width - width + 1
            y: index < 2 ? -1 : root.height - height + 1
            opacity: root.activeBorder || root.hovered ? 1.0 : 0.7
            Behavior on opacity { NumberAnimation { duration: 200 } }
            Rectangle { width: 14; height: 2; color: root.glowColor; y: index < 2 ? 0 : 12 }
            Rectangle { width: 2; height: 14; color: root.glowColor; x: index % 2 === 0 ? 0 : 12 }
        }
    }

    // outer glow when active
    Rectangle {
        anchors.fill: parent
        anchors.margins: -4
        radius: root.radius + 4
        color: "transparent"
        border.width: 3
        border.color: Qt.rgba(root.glowColor.r, root.glowColor.g, root.glowColor.b, root.activeBorder ? 0.22 : (root.hovered ? 0.08 : 0.0))
        z: -1
        Behavior on border.color { ColorAnimation { duration: 250 } }
    }
}

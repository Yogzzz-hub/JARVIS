import QtQuick

Item {
    id: root
    property string assistantState: "IDLE"
    property bool lowResourceMode: false
    property real orbSize: 120

    width: orbSize
    height: orbSize

    // Color computation
    readonly property color orbColor: {
        switch (assistantState) {
            case "LISTENING": return "#00E676"  // Green
            case "TRANSCRIBING": return "#00E5FF" // Cyan
            case "PLANNING":
            case "ROUTING":
            case "EXECUTING": return "#00A3FF"  // Electric Blue
            case "VERIFYING": return "#00B4D8"  // Teal
            case "SPEAKING": return "#7C4DFF"   // Violet/Indigo
            case "WAITING_CONFIRMATION": return "#FFB300" // Amber
            case "ERROR": return "#FF5252"      // Red
            case "OFFLINE": return "#757575"    // Gray
            default: return "#00E5FF"           // Cyan Idle
        }
    }

    // Outer Aura Ring
    Rectangle {
        id: outerRing
        anchors.centerIn: parent
        width: parent.width * 0.95
        height: parent.height * 0.95
        radius: width / 2
        color: "transparent"
        border.color: root.orbColor
        border.width: assistantState === "LISTENING" ? 2 : 1
        opacity: assistantState === "OFFLINE" ? 0.2 : 0.4

        SequentialAnimation on scale {
            running: !root.lowResourceMode && (assistantState === "IDLE" || assistantState === "LISTENING")
            loops: Animation.Infinite
            NumberAnimation { to: assistantState === "LISTENING" ? 1.15 : 1.05; duration: assistantState === "LISTENING" ? 600 : 2400; easing.type: Easing.InOutQuad }
            NumberAnimation { to: 1.0; duration: assistantState === "LISTENING" ? 600 : 2400; easing.type: Easing.InOutQuad }
        }
    }

    // Segmented Thinking / Scanning Ring
    Rectangle {
        id: segmentRing
        anchors.centerIn: parent
        width: parent.width * 0.78
        height: parent.height * 0.78
        radius: width / 2
        color: "transparent"
        border.color: root.orbColor
        border.width: 1.5
        opacity: 0.6
        visible: assistantState === "PLANNING" || assistantState === "ROUTING" || assistantState === "EXECUTING" || assistantState === "VERIFYING"

        RotationAnimation on rotation {
            running: segmentRing.visible && !root.lowResourceMode
            loops: Animation.Infinite
            from: 0
            to: 360
            duration: assistantState === "VERIFYING" ? 1000 : 2000
        }
    }

    // Middle Ring
    Rectangle {
        id: middleRing
        anchors.centerIn: parent
        width: parent.width * 0.62
        height: parent.height * 0.62
        radius: width / 2
        color: "transparent"
        border.color: root.orbColor
        border.width: 1
        opacity: 0.7
    }

    // Inner Glowing Core
    Rectangle {
        id: core
        anchors.centerIn: parent
        width: parent.width * 0.40
        height: parent.height * 0.40
        radius: width / 2
        color: root.orbColor
        opacity: assistantState === "OFFLINE" ? 0.3 : 0.85

        SequentialAnimation on scale {
            running: !root.lowResourceMode && assistantState === "SPEAKING"
            loops: Animation.Infinite
            NumberAnimation { to: 1.18; duration: 250; easing.type: Easing.InOutQuad }
            NumberAnimation { to: 0.95; duration: 250; easing.type: Easing.InOutQuad }
        }
    }
}

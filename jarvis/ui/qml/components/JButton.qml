import QtQuick

// One button for every page: clear hover / press / disabled / busy states, so a click always visibly lands.
// variant: "primary" (cyan), "success", "warning", "danger", "ghost"
Rectangle {
    id: btn
    property string text: ""
    property string variant: "primary"
    property bool busy: false
    property bool small: false
    property bool enabledButton: true
    signal clicked()

    readonly property color tone: variant === "success" ? "#00E676" : variant === "warning" ? "#FFB300"
                                 : variant === "danger" ? "#FF5252" : variant === "ghost" ? "#94A3B8" : "#00E5FF"
    readonly property bool live: enabledButton && !busy

    implicitWidth: Math.max(small ? 64 : 86, label.implicitWidth + (busy ? 44 : 30))
    implicitHeight: small ? 26 : 34
    width: implicitWidth
    height: implicitHeight
    radius: small ? 7 : 9
    color: !live ? Qt.rgba(tone.r, tone.g, tone.b, 0.05)
           : mouse.pressed ? Qt.rgba(tone.r, tone.g, tone.b, 0.32)
           : mouse.containsMouse ? Qt.rgba(tone.r, tone.g, tone.b, 0.20) : Qt.rgba(tone.r, tone.g, tone.b, 0.09)
    border.width: 1
    border.color: Qt.rgba(tone.r, tone.g, tone.b, live ? (mouse.containsMouse ? 0.95 : 0.55) : 0.25)
    opacity: enabledButton ? 1.0 : 0.45
    scale: mouse.pressed && live ? 0.97 : 1.0
    Behavior on color { ColorAnimation { duration: 120 } }
    Behavior on scale { NumberAnimation { duration: 90 } }

    Row {
        anchors.centerIn: parent
        spacing: 8
        Item {
            width: 12; height: 12; visible: btn.busy
            anchors.verticalCenter: parent.verticalCenter
            Rectangle {
                anchors.fill: parent; radius: 6; color: "transparent"
                border.width: 2; border.color: Qt.rgba(btn.tone.r, btn.tone.g, btn.tone.b, 0.25)
            }
            Rectangle {
                width: 4; height: 4; radius: 2; color: btn.tone; x: 4; y: 0
                transformOrigin: Item.Center
            }
            RotationAnimation on rotation { running: btn.busy; from: 0; to: 360; duration: 800; loops: Animation.Infinite }
        }
        Text {
            id: label
            text: btn.text
            color: btn.tone
            font.pixelSize: btn.small ? 11 : 12
            font.bold: true
            font.letterSpacing: 0.6
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: btn.live ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: if (btn.live) btn.clicked()
    }
}

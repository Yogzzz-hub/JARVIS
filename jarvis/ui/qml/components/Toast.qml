import QtQuick

Rectangle {
    id: root
    property string title: "Notification"
    property string message: ""
    property bool showing: false

    width: 320
    height: 70
    radius: 8
    color: "#161E2E"
    border.color: "#00E5FF"
    border.width: 1
    opacity: showing ? 1.0 : 0.0
    visible: opacity > 0.0

    Behavior on opacity {
        NumberAnimation { duration: 250 }
    }

    Timer {
        id: hideTimer
        interval: 3500
        running: root.showing
        onTriggered: root.showing = false
    }

    Column {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 4

        Text {
            text: root.title
            color: "#00E5FF"
            font.pixelSize: 12
            font.bold: true
        }

        Text {
            text: root.message
            color: "#F0F4F8"
            font.pixelSize: 12
            elide: Text.ElideRight
            width: parent.width
        }
    }
}

import QtQuick

Item {
    id: root
    property string status: "READY"
    property string text: status

    readonly property color statusColor: {
        switch (status) {
            case "ONLINE":
            case "ACTIVE":
            case "READY":
            case "CONNECTED":
            case "SUCCESS": return "#00E676"  // Green
            case "SLEEPING":
            case "WAITING":
            case "BUSY": return "#FFB300"     // Amber
            case "OFFLINE":
            case "DISCONNECTED":
            case "FAILED":
            case "ERROR": return "#FF5252"    // Red
            default: return "#94A3B8"         // Slate/Gray
        }
    }

    width: row.width + 18
    height: 26

    // background pill
    Rectangle {
        anchors.fill: parent
        radius: 13
        color: Qt.rgba(root.statusColor.r, root.statusColor.g, root.statusColor.b, 0.10)
        border.color: Qt.rgba(root.statusColor.r, root.statusColor.g, root.statusColor.b, 0.40)
        border.width: 1
        Behavior on color { ColorAnimation { duration: 200 } }
        Behavior on border.color { ColorAnimation { duration: 200 } }
    }

    // outer glow
    Rectangle {
        anchors.fill: parent
        anchors.margins: -2
        radius: 15
        color: "transparent"
        border.width: 2
        border.color: Qt.rgba(root.statusColor.r, root.statusColor.g, root.statusColor.b, 0.12)
        z: -1
    }

    Row {
        id: row
        anchors.centerIn: parent
        spacing: 6

        // animated dot
        Item {
            width: 8; height: 8
            anchors.verticalCenter: parent.verticalCenter
            Rectangle {
                anchors.centerIn: parent
                width: 6; height: 6; radius: 3
                color: root.statusColor
            }
            Rectangle {
                anchors.centerIn: parent
                width: 10; height: 10; radius: 5
                color: "transparent"
                border.width: 1.5
                border.color: root.statusColor
                visible: root.status === "ONLINE" || root.status === "CONNECTED" || root.status === "READY"
                SequentialAnimation on scale {
                    running: root.status === "ONLINE" || root.status === "CONNECTED"
                    loops: Animation.Infinite
                    NumberAnimation { to: 1.5; duration: 1000; easing.type: Easing.OutCubic }
                    PropertyAction { value: 1.0 }
                }
                SequentialAnimation on opacity {
                    running: root.status === "ONLINE" || root.status === "CONNECTED"
                    loops: Animation.Infinite
                    NumberAnimation { from: 0.7; to: 0; duration: 1000; easing.type: Easing.OutCubic }
                    PropertyAction { value: 0.7 }
                }
            }
        }

        Text {
            text: root.text
            color: root.statusColor
            font.pixelSize: 11
            font.bold: true
            font.letterSpacing: 0.8
            anchors.verticalCenter: parent.verticalCenter
        }
    }
}

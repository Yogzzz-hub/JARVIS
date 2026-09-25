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

    width: row.width + 12
    height: 22

    Rectangle {
        anchors.fill: parent
        radius: 11
        color: root.statusColor
        opacity: 0.12
        border.color: root.statusColor
        border.width: 1
    }

    Row {
        id: row
        anchors.centerIn: parent
        spacing: 5

        Rectangle {
            width: 6
            height: 6
            radius: 3
            color: root.statusColor
            anchors.verticalCenter: parent.verticalCenter
        }

        Text {
            text: root.text
            color: root.statusColor
            font.pixelSize: 11
            font.bold: true
            anchors.verticalCenter: parent.verticalCenter
        }
    }
}

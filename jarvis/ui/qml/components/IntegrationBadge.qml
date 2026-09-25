import QtQuick

GlassPanel {
    id: root
    property string integrationName: "Integration"
    property string status: "CONNECTED"
    property string desc: "Description"

    width: 260
    height: 85

    Column {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 6

        Row {
            width: parent.width
            Text {
                text: root.integrationName
                color: "#F0F4F8"
                font.pixelSize: 13
                font.bold: true
                width: parent.width - badge.width - 4
                elide: Text.ElideRight
            }
            StatusBadge {
                id: badge
                status: root.status
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        Text {
            text: root.desc
            color: "#94A3B8"
            font.pixelSize: 11
            elide: Text.ElideRight
            width: parent.width
        }
    }
}

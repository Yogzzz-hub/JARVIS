import QtQuick

GlassPanel {
    id: root
    property string modelName: "Model"
    property string status: "READY"
    property string details: "Description"

    width: 220
    height: 80

    Column {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 6

        Row {
            width: parent.width
            Text {
                text: root.modelName
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
            text: root.details
            color: "#64748B"
            font.pixelSize: 11
            elide: Text.ElideRight
            width: parent.width
        }
    }
}

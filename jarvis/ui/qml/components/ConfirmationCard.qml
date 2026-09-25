import QtQuick

GlassPanel {
    id: root
    property string ticketId: ""
    property string title: "CONFIRMATION REQUIRED"
    property string target: "Action Target"
    property string source: "System"
    property string risk: "EXTERNAL_EFFECT"
    property string details: "This operation will modify system state."
    signal confirmed(string id)
    signal rejected(string id)

    width: 440
    height: 220
    glowColor: "#FFB300"
    activeBorder: true

    Column {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 12

        Row {
            width: parent.width
            spacing: 8
            Text {
                text: "⚠ " + root.title
                color: "#FFB300"
                font.pixelSize: 14
                font.bold: true
            }
            Item { width: Math.max(0, parent.width - 320); height: 1 }
            Text {
                text: "ID: " + root.ticketId
                color: "#64748B"
                font.pixelSize: 11
            }
        }

        Rectangle {
            width: parent.width
            height: 1
            color: "#222D3E"
        }

        Text {
            text: root.target
            color: "#F0F4F8"
            font.pixelSize: 16
            font.bold: true
        }

        Text {
            text: root.details
            color: "#94A3B8"
            font.pixelSize: 12
            wrapMode: Text.Wrap
            width: parent.width
        }

        Item { height: 8 }

        Row {
            spacing: 16
            anchors.right: parent.right

            // Reject Button
            Rectangle {
                width: 100
                height: 34
                radius: 6
                color: "#1E293B"
                border.color: "#334155"
                border.width: 1

                Text {
                    anchors.centerIn: parent
                    text: "REJECT"
                    color: "#F0F4F8"
                    font.pixelSize: 12
                    font.bold: true
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.rejected(root.ticketId)
                }
            }

            // Confirm Button
            Rectangle {
                width: 110
                height: 34
                radius: 6
                color: "#00E676"

                Text {
                    anchors.centerIn: parent
                    text: "APPROVE"
                    color: "#0A0D12"
                    font.pixelSize: 12
                    font.bold: true
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.confirmed(root.ticketId)
                }
            }
        }
    }
}

import QtQuick
import "../components"

Item {
    id: root
    property var controller

    Column {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 16

        Row {
            width: parent.width
            Text {
                text: "APPROVED MEMORY & PREFERENCES"
                color: "#F0F4F8"
                font.pixelSize: 18
                font.bold: true
            }
            Item { width: Math.max(0, parent.width - 500); height: 1 }

            Rectangle {
                width: 90
                height: 28
                radius: 4
                color: "#1A2230"
                border.color: "#00E5FF"
                border.width: 1
                anchors.verticalCenter: parent.verticalCenter

                Text {
                    anchors.centerIn: parent
                    text: "REFRESH"
                    color: "#00E5FF"
                    font.pixelSize: 11
                    font.bold: true
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (controller) controller.sendCommand("memory status");
                    }
                }
            }
        }

        Rectangle {
            width: parent.width
            height: 1
            color: "#222D3E"
        }

        // Memory List
        ListView {
            id: memList
            width: parent.width
            height: parent.height - 60
            clip: true
            spacing: 10

            model: [
                {"category": "PREFERENCE", "key": "Default Browser", "val": "Google Chrome", "time": "Permanent"},
                {"category": "PREFERENCE", "key": "Preferred Code Editor", "val": "Visual Studio Code", "time": "Permanent"},
                {"category": "PROJECT", "key": "Current Working Directory", "val": "C:\\Projects\\JarvisEdge", "time": "Active Session"},
                {"category": "PROJECT", "key": "Active Language Stack", "val": "Python 3.12, PySide6, Qt Quick", "time": "Active Session"},
                {"category": "CONTEXT", "key": "Last Known Location", "val": "Desktop Workstation (Windows 11)", "time": "Recent"},
            ]

            delegate: GlassPanel {
                width: memList.width
                height: 60

                Row {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 16

                    StatusBadge {
                        status: modelData.category === "PREFERENCE" ? "ONLINE" : "ACTIVE"
                        text: modelData.category
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Column {
                        width: parent.width - 240
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 2
                        Text {
                            text: modelData.key
                            color: "#94A3B8"
                            font.pixelSize: 11
                        }
                        Text {
                            text: modelData.val
                            color: "#F0F4F8"
                            font.pixelSize: 13
                            font.bold: true
                        }
                    }

                    Text {
                        text: modelData.time
                        color: "#64748B"
                        font.pixelSize: 11
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
            }
        }
    }
}

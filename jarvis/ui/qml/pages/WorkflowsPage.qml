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
                text: "APPROVED WORKFLOWS & ROUTINES"
                color: "#F0F4F8"
                font.pixelSize: 18
                font.bold: true
            }
            Item { width: Math.max(0, parent.width - 500); height: 1 }
            Text {
                text: "Security Policy Governed"
                color: "#94A3B8"
                font.pixelSize: 11
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        Rectangle {
            width: parent.width
            height: 1
            color: "#222D3E"
        }

        ListView {
            id: flowList
            width: parent.width
            height: parent.height - 60
            clip: true
            spacing: 10

            model: [
                {"name": "Morning Briefing", "runs": "Live", "avg": "1.8s", "desc": "Live real-time weather, hardware telemetry, battery, and top world news.", "command": "morning briefing"},
                {"name": "Development Setup", "runs": "Live", "avg": "0.5s", "desc": "Launch Visual Studio Code development environment.", "command": "open vscode"},
                {"name": "Meeting Focus Mode", "runs": "Live", "avg": "0.2s", "desc": "Set system audio volume to 20% for meetings.", "command": "set volume to 20 percent"},
                {"name": "System Health Check", "runs": "Live", "avg": "0.2s", "desc": "Query CPU, RAM, GPU telemetry, and hardware info.", "command": "system info"},
            ]

            delegate: GlassPanel {
                width: flowList.width
                height: 72

                Row {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 16

                    Column {
                        width: parent.width - 150
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 4

                        Row {
                            spacing: 10
                            Text {
                                text: modelData.name
                                color: "#F0F4F8"
                                font.pixelSize: 14
                                font.bold: true
                            }
                            Text {
                                text: "• " + modelData.runs + " (" + modelData.avg + ")"
                                color: "#00E5FF"
                                font.pixelSize: 11
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        Text {
                            text: modelData.desc
                            color: "#94A3B8"
                            font.pixelSize: 11
                            elide: Text.ElideRight
                            width: parent.width
                        }
                    }

                    // Run Button
                    Rectangle {
                        width: 70
                        height: 30
                        radius: 4
                        color: "#1A2230"
                        border.color: "#00E5FF"
                        border.width: 1
                        anchors.verticalCenter: parent.verticalCenter

                        Text {
                            anchors.centerIn: parent
                            text: "RUN"
                            color: "#00E5FF"
                            font.pixelSize: 11
                            font.bold: true
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (controller) controller.sendCommand(modelData.command);
                            }
                        }
                    }
                }
            }
        }
    }
}

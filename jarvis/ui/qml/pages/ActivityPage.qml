import QtQuick
import "../components"

Item {
    id: root
    property var activityModel
    property var controller

    Column {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 16

        // Page Header
        Row {
            width: parent.width
            Text {
                text: "ACTIVITY & RECENT TASKS"
                color: "#F0F4F8"
                font.pixelSize: 18
                font.bold: true
            }
            Item { width: Math.max(0, parent.width - 380); height: 1 }
            Text {
                text: "Bounded history (Max 50)"
                color: "#64748B"
                font.pixelSize: 12
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        Rectangle {
            width: parent.width
            height: 1
            color: "#222D3E"
        }

        // Tasks ListView
        ListView {
            id: taskList
            width: parent.width
            height: parent.height - 60
            clip: true
            spacing: 8
            model: root.activityModel

            delegate: GlassPanel {
                width: taskList.width
                height: 72

                Column {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 4

                    Row {
                        width: parent.width
                        spacing: 10

                        Text {
                            text: model.requestText || "Command"
                            color: "#F0F4F8"
                            font.pixelSize: 13
                            font.bold: true
                            elide: Text.ElideRight
                            width: parent.width - statusBadge.width - 90
                        }

                        StatusBadge {
                            id: statusBadge
                            status: model.taskState || "SUCCESS"
                        }

                        Text {
                            text: model.taskTimestamp || "00:00:00"
                            color: "#64748B"
                            font.pixelSize: 11
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    Row {
                        spacing: 12
                        Text {
                            text: "Source: " + (model.taskSource || "desktop")
                            color: "#94A3B8"
                            font.pixelSize: 11
                        }
                        Text {
                            text: "•  Route: " + (model.taskRoute || "SmartRouter")
                            color: "#94A3B8"
                            font.pixelSize: 11
                        }
                        Text {
                            text: "•  Result: " + (model.taskMessage || "Completed")
                            color: "#64748B"
                            font.pixelSize: 11
                            elide: Text.ElideRight
                            width: parent.width - 240
                        }
                    }
                }
            }

            // Empty state placeholder
            Text {
                anchors.centerIn: parent
                text: "No recent tasks executed yet."
                color: "#64748B"
                font.pixelSize: 13
                visible: taskList.count === 0
            }
        }
    }
}

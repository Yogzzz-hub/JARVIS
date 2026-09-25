import QtQuick
import "../components"

Item {
    id: root
    property var stateModel
    property var controller

    Column {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 16

        Row {
            width: parent.width
            Text {
                text: "CONNECTED HARDWARE & PERIPHERALS"
                color: "#F0F4F8"
                font.pixelSize: 18
                font.bold: true
            }
            Item { width: Math.max(0, parent.width - 520); height: 1 }
            Text {
                text: "Zero Polling Overhead"
                color: "#64748B"
                font.pixelSize: 11
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        Rectangle {
            width: parent.width
            height: 1
            color: "#222D3E"
        }

        Flow {
            width: parent.width
            spacing: 14

            Repeater {
                model: stateModel ? stateModel.devices : []
                delegate: GlassPanel {
                    width: 250
                    height: 75

                    Column {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 6

                        Row {
                            width: parent.width
                            Text {
                                text: modelData.name || "Device"
                                color: "#F0F4F8"
                                font.pixelSize: 13
                                font.bold: true
                                width: parent.width - devBadge.width - 4
                                elide: Text.ElideRight
                            }
                            StatusBadge {
                                id: devBadge
                                status: modelData.status || "OFFLINE"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        Text {
                            text: "Type: " + (modelData.type || "peripheral")
                            color: "#64748B"
                            font.pixelSize: 11
                        }
                    }
                }
            }
        }
    }
}

import QtQuick
import "../components"

Item {
    id: root
    property var controller

    Component.onCompleted: {
        if (controller) {
            toggleBox.checked = Boolean(controller.getSetting("low_resource_mode"));
            trayToggle.checked = Boolean(controller.getSetting("close_to_tray"));
        }
    }

    Flickable {
        anchors.fill: parent
        anchors.margins: 20
        contentHeight: settingsCol.height + 40
        clip: true

        Column {
            id: settingsCol
            width: Math.min(parent.width, 600)
            spacing: 20

            Text {
                text: "USER INTERFACE & PREFERENCES"
                color: "#F0F4F8"
                font.pixelSize: 18
                font.bold: true
            }

            Rectangle {
                width: parent.width
                height: 1
                color: "#222D3E"
            }

            // Low Resource Mode Toggle
            GlassPanel {
                width: parent.width
                height: 60

                Row {
                    anchors.fill: parent
                    anchors.margins: 14

                    Column {
                        width: parent.width - 70
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 2
                        Text {
                            text: "Low Resource Mode"
                            color: "#F0F4F8"
                            font.pixelSize: 13
                            font.bold: true
                        }
                        Text {
                            text: "Disables idle orb animations and slows hardware sampling to 0.5 Hz"
                            color: "#94A3B8"
                            font.pixelSize: 11
                        }
                    }

                    Rectangle {
                        id: toggleBox
                        width: 44
                        height: 24
                        radius: 12
                        property bool checked: false
                        color: checked ? "#00E5FF" : "#222D3E"
                        anchors.verticalCenter: parent.verticalCenter

                        Rectangle {
                            width: 18
                            height: 18
                            radius: 9
                            color: "#F0F4F8"
                            anchors.verticalCenter: parent.verticalCenter
                            x: toggleBox.checked ? parent.width - width - 3 : 3
                            Behavior on x { NumberAnimation { duration: 150 } }
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                toggleBox.checked = !toggleBox.checked;
                                if (controller) controller.updateSetting("low_resource_mode", toggleBox.checked);
                            }
                        }
                    }
                }
            }

            // Close to Tray Toggle
            GlassPanel {
                width: parent.width
                height: 60

                Row {
                    anchors.fill: parent
                    anchors.margins: 14

                    Column {
                        width: parent.width - 70
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 2
                        Text {
                            text: "Close to Tray"
                            color: "#F0F4F8"
                            font.pixelSize: 13
                            font.bold: true
                        }
                        Text {
                            text: "Closing the dashboard leaves JARVIS running quietly in the system tray"
                            color: "#94A3B8"
                            font.pixelSize: 11
                        }
                    }

                    Rectangle {
                        id: trayToggle
                        width: 44
                        height: 24
                        radius: 12
                        property bool checked: true
                        color: checked ? "#00E5FF" : "#222D3E"
                        anchors.verticalCenter: parent.verticalCenter

                        Rectangle {
                            width: 18
                            height: 18
                            radius: 9
                            color: "#F0F4F8"
                            anchors.verticalCenter: parent.verticalCenter
                            x: trayToggle.checked ? parent.width - width - 3 : 3
                            Behavior on x { NumberAnimation { duration: 150 } }
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                trayToggle.checked = !trayToggle.checked;
                                if (controller) controller.updateSetting("close_to_tray", trayToggle.checked);
                            }
                        }
                    }
                }
            }

            // Overlay Location
            GlassPanel {
                width: parent.width
                height: 60

                Row {
                    anchors.fill: parent
                    anchors.margins: 14

                    Column {
                        width: parent.width - 150
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 2
                        Text {
                            text: "Mini Voice Overlay Location"
                            color: "#F0F4F8"
                            font.pixelSize: 13
                            font.bold: true
                        }
                        Text {
                            text: "Default: Bottom-Center on active display"
                            color: "#94A3B8"
                            font.pixelSize: 11
                        }
                    }

                    Text {
                        text: "Bottom Center"
                        color: "#00E5FF"
                        font.pixelSize: 12
                        font.bold: true
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
            }
        }
    }
}

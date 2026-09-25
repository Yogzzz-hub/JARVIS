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
                text: "SYSTEM DIAGNOSTICS & SUBSYSTEM AUDIT"
                color: "#F0F4F8"
                font.pixelSize: 18
                font.bold: true
            }
            Item { width: Math.max(0, parent.width - 560); height: 1 }
            Rectangle {
                width: 130
                height: 28
                radius: 4
                color: "#1A2230"
                border.color: "#00E5FF"
                border.width: 1

                Text {
                    anchors.centerIn: parent
                    text: "RUN DIAGNOSTICS"
                    color: "#00E5FF"
                    font.pixelSize: 10
                    font.bold: true
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (controller) controller.sendCommand("diagnostics")
                }
            }
        }

        Rectangle {
            width: parent.width
            height: 1
            color: "#222D3E"
        }

        ListView {
            id: diagList
            width: parent.width
            height: parent.height - 70
            clip: true
            spacing: 8

            model: [
                {"name": "FastAPI Gateway Service", "status": "ONLINE", "desc": "Port 8765 HTTP/REST API endpoints"},
                {"name": "WebSocket Realtime Stream", "status": "ONLINE", "desc": "Persistent bi-directional command socket"},
                {"name": "SmartRouter Subsystem", "status": "READY", "desc": "Sub-millisecond intent classification"},
                {"name": "SQLite Persistence Store", "status": "READY", "desc": "Zero-drop background event journaling"},
                {"name": "Speech-to-Text Pipeline", "status": "READY", "desc": "Faster-Whisper on-demand worker"},
                {"name": "Voice Audio Hub", "status": "READY", "desc": "16kHz canonical audio buffer with Silero VAD"},
                {"name": "Piper Neural TTS Engine", "status": "READY", "desc": "Natural speech generation engine"},
                {"name": "Security & Policy Ledger", "status": "READY", "desc": "Phase-5 confirmation and hash idempotency"},
            ]

            delegate: GlassPanel {
                width: diagList.width
                height: 54

                Row {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 14

                    StatusBadge {
                        status: modelData.status
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    Column {
                        width: parent.width - 200
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 2

                        Text {
                            text: modelData.name
                            color: "#F0F4F8"
                            font.pixelSize: 13
                            font.bold: true
                        }
                        Text {
                            text: modelData.desc
                            color: "#94A3B8"
                            font.pixelSize: 11
                        }
                    }
                }
            }
        }
    }
}

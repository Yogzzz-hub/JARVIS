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
                text: "EXTERNAL SERVICE INTEGRATIONS"
                color: "#F0F4F8"
                font.pixelSize: 18
                font.bold: true
            }
            Item { width: Math.max(0, parent.width - 520); height: 1 }
            Text {
                text: "Tokens & Secrets Redacted"
                color: "#00E676"
                font.pixelSize: 11
                font.bold: true
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        Rectangle {
            width: parent.width
            height: 1
            color: "#222D3E"
        }

        // WhatsApp Omnichannel Dedicated Management Panel
        GlassPanel {
            width: parent.width
            height: 140

            Column {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 10

                Row {
                    width: parent.width
                    Text {
                        text: "WHATSAPP OMNICHANNEL (BAILEYS TRANSPORT)"
                        color: "#25D366"
                        font.pixelSize: 14
                        font.bold: true
                    }
                    Item { width: Math.max(0, parent.width - 480); height: 1 }
                    StatusBadge {
                        status: stateModel ? stateModel.whatsappStatus : "DISCONNECTED"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                Row {
                    spacing: 24
                    Column {
                        spacing: 4
                        Text { text: "Account / Pairing:"; color: "#64748B"; font.pixelSize: 11 }
                        Text { text: stateModel ? stateModel.whatsappAccount : "Configured"; color: "#F0F4F8"; font.pixelSize: 12; font.bold: true }
                    }
                    Column {
                        spacing: 4
                        Text { text: "Auto-Reply Mode:"; color: "#64748B"; font.pixelSize: 11 }
                        Text { text: stateModel ? stateModel.whatsappMode : "DRAFT_ONLY"; color: "#00E5FF"; font.pixelSize: 12; font.bold: true }
                    }
                    Column {
                        spacing: 4
                        Text { text: "Voice Reply:"; color: "#64748B"; font.pixelSize: 11 }
                        Text { text: (stateModel && stateModel.whatsappVoiceReply) ? "ENABLED (Piper)" : "TEXT ONLY"; color: (stateModel && stateModel.whatsappVoiceReply) ? "#00E676" : "#94A3B8"; font.pixelSize: 12; font.bold: true }
                    }
                    Column {
                        spacing: 4
                        Text { text: "Last Message:"; color: "#64748B"; font.pixelSize: 11 }
                        Text { text: stateModel ? stateModel.whatsappLastMessage : "None"; color: "#CBD5E1"; font.pixelSize: 12 }
                    }
                }

                Row {
                    spacing: 10
                    Rectangle {
                        width: 90
                        height: 28
                        radius: 4
                        color: "#1E293B"
                        border.color: "#334155"
                        Text {
                            anchors.centerIn: parent
                            text: (stateModel && stateModel.whatsappStatus === "CONNECTED") ? "Disconnect" : "Connect"
                            color: "#F0F4F8"
                            font.pixelSize: 11
                            font.bold: true
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (controller) {
                                    if (stateModel && stateModel.whatsappStatus === "CONNECTED") {
                                        controller.disconnectWhatsapp();
                                    } else {
                                        controller.connectWhatsapp();
                                    }
                                }
                            }
                        }
                    }

                    Rectangle {
                        width: 80
                        height: 28
                        radius: 4
                        color: "#1E293B"
                        border.color: "#334155"
                        Text {
                            anchors.centerIn: parent
                            text: "Re-pair"
                            color: "#F0F4F8"
                            font.pixelSize: 11
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (controller) controller.repairWhatsapp();
                            }
                        }
                    }

                    Rectangle {
                        width: 120
                        height: 28
                        radius: 4
                        color: "#1E293B"
                        border.color: "#334155"
                        Text {
                            anchors.centerIn: parent
                            text: (stateModel && stateModel.whatsappMode === "DRAFT_ONLY") ? "Mode: Draft-Only" : "Mode: Auto-Reply"
                            color: "#00E5FF"
                            font.pixelSize: 11
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (stateModel) {
                                    var m = stateModel.whatsappMode === "DRAFT_ONLY" ? "ALLOWLIST_AUTO_REPLY" : "DRAFT_ONLY"
                                    stateModel.setWhatsappMode(m)
                                }
                            }
                        }
                    }

                    Rectangle {
                        width: 130
                        height: 28
                        radius: 4
                        color: "#1E293B"
                        border.color: "#334155"
                        Text {
                            anchors.centerIn: parent
                            text: (stateModel && stateModel.whatsappVoiceReply) ? "Voice Reply: ON" : "Voice Reply: OFF"
                            color: (stateModel && stateModel.whatsappVoiceReply) ? "#00E676" : "#94A3B8"
                            font.pixelSize: 11
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (stateModel) stateModel.toggleWhatsappVoiceReply()
                            }
                        }
                    }
                }
            }
        }

        Text {
            text: "ACTIVE CONNECTORS"
            color: "#64748B"
            font.pixelSize: 12
            font.bold: true
        }

        Flow {
            width: parent.width
            spacing: 14

            Repeater {
                model: stateModel ? stateModel.integrations : []
                delegate: IntegrationBadge {
                    integrationName: modelData.name || "Integration"
                    status: modelData.status || "DISCONNECTED"
                    desc: modelData.desc || ""
                }
            }
        }
    }
}

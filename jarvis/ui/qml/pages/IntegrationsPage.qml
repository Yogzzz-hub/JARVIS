import QtQuick
import "../components"

Item {
    id: root
    property var stateModel
    property var controller
    signal navigate(int index)
    readonly property bool waConnected: stateModel && stateModel.whatsappStatus === "CONNECTED"

    PageScroll {
        anchors.fill: parent

        PageHeader {
            width: parent.width
            icon: "integrations"
            title: "Integrations"
            subtitle: "Services JARVIS talks to. Tokens and secrets are never shown here."
        }

        // WhatsApp
        Card {
            width: parent.width
            spacing: 14
            CardTitle { width: parent.width; title: "WhatsApp"; titleColor: "#25D366"
                status: root.stateModel ? root.stateModel.whatsappStatus : "DISCONNECTED" }
            Flow {
                width: parent.width
                spacing: 28
                Repeater {
                    model: [
                        { k: "Account", v: root.stateModel ? root.stateModel.whatsappAccount : "Not paired" },
                        { k: "Replies", v: root.stateModel && root.stateModel.whatsappMode === "ALLOWLIST_AUTO_REPLY" ? "Auto (allow-list)" : "Drafts only" },
                        { k: "Voice replies", v: root.stateModel && root.stateModel.whatsappVoiceReply ? "On" : "Text only" },
                        { k: "Last message", v: root.stateModel && root.stateModel.whatsappLastMessage ? root.stateModel.whatsappLastMessage : "None yet" }
                    ]
                    delegate: Column {
                        spacing: 4
                        Text { text: modelData.k; color: "#64748B"; font.pixelSize: 13 }
                        Text { text: modelData.v; color: "#E2E8F0"; font.pixelSize: 15; font.bold: true }
                    }
                }
            }
            Flow {
                width: parent.width
                spacing: 10
                JButton { text: root.waConnected ? "DISCONNECT" : "CONNECT"; variant: root.waConnected ? "danger" : "success"
                    onClicked: if (root.controller) { if (root.waConnected) root.controller.disconnectWhatsapp(); else root.controller.connectWhatsapp() } }
                JButton { text: "NEW PAIRING CODE"; variant: "ghost"; onClicked: if (root.controller) root.controller.repairWhatsapp() }
                JButton { text: "SUMMARIZE MESSAGES"; onClicked: if (root.controller) root.controller.sendCommand("summarize my whatsapp") }
                JButton { text: "AUTO-REPLY & CONTACTS →"; onClicked: root.navigate(9) }
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                color: "#64748B"
                font.pixelSize: 13
                text: "Auto-replies are time-boxed and set per contact on the WhatsApp page, or by voice: \"auto reply to everyone "
                      + "for 30 minutes saying I'm in a meeting\". Group chats are never auto-replied."
            }
        }

        SectionLabel { text: "CONNECTORS" }
        CardGrid {
            id: grid
            width: parent.width
            minCardWidth: 250
            Repeater {
                model: root.stateModel ? root.stateModel.integrations : []
                delegate: IntegrationBadge {
                    width: grid.cellWidth
                    integrationName: modelData.name || "Integration"
                    status: modelData.status || "DISCONNECTED"
                    desc: modelData.desc || ""
                }
            }
        }
    }
}

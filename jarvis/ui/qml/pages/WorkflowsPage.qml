import QtQuick
import "../components"

Item {
    id: root
    property var controller
    property string lastRun: ""

    PageScroll {
        anchors.fill: parent

        PageHeader {
            width: parent.width
            title: "Workflows"
            subtitle: "One-click routines. Each runs through the same safety checks as a spoken command."
        }
        NoticeBar {
            width: parent.width
            text: root.lastRun
            onClosed: root.lastRun = ""
        }

        CardGrid {
            id: grid
            width: parent.width
            minCardWidth: 320
            maxColumns: 3
            Repeater {
                model: [
                    { name: "Morning briefing", desc: "Weather, calendar, unread messages, battery and top news.", command: "morning briefing" },
                    { name: "WhatsApp catch-up", desc: "Who wrote to you and what they said, questions first.", command: "summarize my whatsapp" },
                    { name: "Focus mode", desc: "Turns the volume down to 20% for calls and meetings.", command: "set volume to 20 percent" },
                    { name: "Development setup", desc: "Open Visual Studio Code.", command: "open vscode" },
                    { name: "System health check", desc: "CPU, memory, GPU and disk at a glance.", command: "system info" },
                    { name: "Today's reminders", desc: "Everything JARVIS will remind you about.", command: "show my reminders" }
                ]
                delegate: Card {
                    width: grid.cellWidth
                    spacing: 8
                    Text { text: modelData.name; color: "#F0F4F8"; font.pixelSize: 15; font.bold: true; width: parent.width; elide: Text.ElideRight }
                    Text { text: modelData.desc; color: "#8193AB"; font.pixelSize: 12; wrapMode: Text.WordWrap; width: parent.width; height: 34 }
                    Item {
                        width: parent.width
                        height: 34
                        Text { text: "“" + modelData.command + "”"; color: "#56708F"; font.pixelSize: 11; font.italic: true
                               anchors.verticalCenter: parent.verticalCenter; width: parent.width - runBtn.width - 12; elide: Text.ElideRight }
                        JButton { id: runBtn; text: "RUN"; anchors.right: parent.right
                            onClicked: if (root.controller) { root.controller.sendCommand(modelData.command); root.lastRun = "Running “" + modelData.name + "” - the answer appears on Home and in Activity." } }
                    }
                }
            }
        }
    }
}

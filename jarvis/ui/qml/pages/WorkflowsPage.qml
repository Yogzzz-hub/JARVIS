import QtQuick
import "../components"

Item {
    id: root
    property var controller
    property var stateModel
    property string lastRun: ""
    readonly property string st: stateModel ? stateModel.assistantState : "IDLE"
    function up(v, good) { return v === good ? "READY" : (v === "ERROR" || v === "OFFLINE" || v === "DISCONNECTED" ? "ERROR" : "WAITING") }

    PageScroll {
        anchors.fill: parent

        PageHeader {
            width: parent.width
            icon: "workflows"
            title: "Workflows"
            subtitle: "One-click routines. Each runs through the same safety checks as a spoken command."
        }
        SectionLabel { text: "HOW JARVIS WORKS"; hint: "every request, live" }
        Card {
            width: parent.width
            WorkflowPipeline { width: parent.width; assistantState: root.st }
        }
        CardGrid {
            id: layers
            width: parent.width
            minCardWidth: 250
            maxColumns: 3
            Repeater {
                model: [
                    { t: "Voice", s: root.up(root.stateModel ? root.stateModel.voiceStatus : "", "READY"),
                      d: "Wake word \u201CHey Jarvis\u201D, Whisper speech-to-text (English + Thanglish), Piper voice." },
                    { t: "Understanding", s: root.up(root.stateModel ? root.stateModel.connectionStatus : "", "ONLINE"),
                      d: "Smart router: exact commands in milliseconds, typo and Thanglish tolerant; local decision engine for the rest." },
                    { t: "Local AI models", s: root.up(root.stateModel ? root.stateModel.llmStatus : "", "ONLINE"),
                      d: "Ollama on this PC: fast, planner, chat and vision models. Nothing leaves your machine." },
                    { t: "Actions", s: root.up(root.stateModel ? root.stateModel.connectionStatus : "", "ONLINE"),
                      d: "Apps, files, system, browser, phone (ADB), Google, WhatsApp - 150+ tools." },
                    { t: "Safety", s: "READY",
                      d: "Risky actions ask first; group chats and passwords are never automated; incoming messages can never run tools." },
                    { t: "Memory", s: "READY",
                      d: "Facts you asked it to remember, chat history search (RAG) and what it did, so follow-ups make sense." }
                ]
                delegate: Card {
                    width: layers.cellWidth
                    spacing: 8
                    CardTitle { width: parent.width; title: modelData.t; status: modelData.s
                                statusText: modelData.s === "READY" ? "READY" : (modelData.s === "ERROR" ? "OFFLINE" : "STARTING") }
                    Text { text: modelData.d; color: "#8FB4D6"; font.pixelSize: 14; wrapMode: Text.WordWrap; width: parent.width }
                }
            }
        }
        SectionLabel { text: "ONE-CLICK ROUTINES" }
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
                    Text { text: modelData.name; color: "#F0F4F8"; font.pixelSize: 17; font.bold: true; width: parent.width; elide: Text.ElideRight }
                    Text { text: modelData.desc; color: "#8193AB"; font.pixelSize: 14; wrapMode: Text.WordWrap; width: parent.width; height: 34 }
                    Item {
                        width: parent.width
                        height: 34
                        Text { text: "“" + modelData.command + "”"; color: "#56708F"; font.pixelSize: 13; font.italic: true
                               anchors.verticalCenter: parent.verticalCenter; width: parent.width - runBtn.width - 12; elide: Text.ElideRight }
                        JButton { id: runBtn; text: "RUN"; anchors.right: parent.right
                            onClicked: if (root.controller) { root.controller.sendCommand(modelData.command); root.lastRun = "Running “" + modelData.name + "” - the answer appears on Home and in Activity." } }
                    }
                }
            }
        }
    }
}

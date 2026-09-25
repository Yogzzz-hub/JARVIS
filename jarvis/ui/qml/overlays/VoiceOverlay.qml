import QtQuick
import QtQuick.Window
import "../components"

Window {
    id: root
    property var stateModel
    property var controller

    width: 440
    height: 120
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    color: "transparent"
    visible: false

    // Auto-hide timer: hides 3s after execution completes
    Timer {
        id: autoHideTimer
        interval: 3000
        onTriggered: root.visible = false
    }

    Connections {
        target: stateModel
        function onAssistantStateChanged(newState) {
            if (newState === "LISTENING") {
                autoHideTimer.stop();
                root.visible = true;
            } else if (newState === "SUCCESS" || newState === "ERROR" || newState === "IDLE") {
                autoHideTimer.restart();
            }
        }
    }

    // Borderless glass card container
    Rectangle {
        anchors.fill: parent
        anchors.margins: 4
        radius: 12
        color: "#0F141E"
        border.color: stateModel && stateModel.assistantState === "LISTENING" ? "#00E5FF" : "#222D3E"
        border.width: 1.5

        Column {
            anchors.fill: parent
            anchors.margins: 14
            spacing: 8

            // Header line: Orb + State title
            Row {
                width: parent.width
                spacing: 10

                JarvisOrb {
                    orbSize: 24
                    assistantState: stateModel ? stateModel.assistantState : "IDLE"
                    anchors.verticalCenter: parent.verticalCenter
                }

                Text {
                    text: {
                        if (!stateModel) return "Ready";
                        if (stateModel.isListening) return "Listening...";
                        if (stateModel.isSpeaking) return "Speaking...";
                        if (stateModel.assistantState === "TRANSCRIBING") return "Transcribing...";
                        if (stateModel.assistantState === "SUCCESS") return "Done";
                        if (stateModel.assistantState === "ERROR") return "Failed";
                        if (stateModel.assistantState === "IDLE") return "Ready";
                        return stateModel.statusMessage ? stateModel.statusMessage : "Ready";
                    }
                    color: "#00E5FF"
                    font.pixelSize: 12
                    font.bold: true
                    anchors.verticalCenter: parent.verticalCenter
                }

                Item { width: Math.max(0, parent.width - 200); height: 1 }

                Text {
                    text: "ESC to close"
                    color: "#64748B"
                    font.pixelSize: 10
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            // Waveform (visible when listening)
            VoiceWaveform {
                anchors.horizontalCenter: parent.horizontalCenter
                levels: stateModel ? stateModel.audioLevels : []
                active: stateModel ? stateModel.isListening : false
                visible: stateModel ? stateModel.isListening : false
                height: 20
                width: 200
            }

            // Live transcript or final response
            Text {
                width: parent.width
                text: {
                    if (!stateModel) return "...";
                    if (stateModel.isListening) {
                        return stateModel.transcriptPartial ? stateModel.transcriptPartial : "Listening...";
                    }
                    if (stateModel.response) return stateModel.response;
                    if (stateModel.transcriptFinal) return stateModel.transcriptFinal;
                    return "...";
                }
                color: "#F0F4F8"
                font.pixelSize: 13
                font.bold: true
                elide: Text.ElideRight
                wrapMode: Text.Wrap
                maximumLineCount: 2
            }
        }
    }

    Shortcut {
        sequence: "Escape"
        onActivated: root.visible = false
    }
}

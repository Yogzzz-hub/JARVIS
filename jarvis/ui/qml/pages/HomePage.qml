import QtQuick
import "../components"

Item {
    id: root
    property var stateModel
    property var controller

    Column {
        anchors.centerIn: parent
        spacing: 24
        width: Math.min(parent.width - 40, 600)

        // Center Orb
        JarvisOrb {
            anchors.horizontalCenter: parent.horizontalCenter
            orbSize: 130
            assistantState: stateModel ? stateModel.assistantState : "IDLE"
            lowResourceMode: stateModel ? stateModel.lowResourceMode : false
        }

        // Assistant State Text
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: stateModel ? stateModel.statusMessage : "Ready"
            color: "#00E5FF"
            font.pixelSize: 15
            font.bold: true
            font.capitalization: Font.AllUppercase
        }

        // Waveform Visualizer
        VoiceWaveform {
            anchors.horizontalCenter: parent.horizontalCenter
            levels: stateModel ? stateModel.audioLevels : []
            active: stateModel ? stateModel.isListening : false
            barColor: "#00E5FF"
        }

        // Transcript / Response Card
        GlassPanel {
            anchors.horizontalCenter: parent.horizontalCenter
            width: parent.width
            height: 110

            Column {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 8

                // User Transcript
                Row {
                    spacing: 8
                    width: parent.width
                    Text {
                        text: "YOU:"
                        color: "#94A3B8"
                        font.pixelSize: 11
                        font.bold: true
                    }
                    Text {
                        text: (stateModel && stateModel.transcriptFinal) ? stateModel.transcriptFinal : ((stateModel && stateModel.transcriptPartial) ? stateModel.transcriptPartial : "Say 'Hey Jarvis' or press Ctrl+Shift+J...")
                        color: (stateModel && stateModel.transcriptFinal) ? "#F0F4F8" : "#64748B"
                        font.pixelSize: 13
                        elide: Text.ElideRight
                        width: parent.width - 60
                    }
                }

                Rectangle {
                    width: parent.width
                    height: 1
                    color: "#222D3E"
                }

                // Jarvis Response
                Row {
                    spacing: 8
                    width: parent.width
                    Text {
                        text: "JARVIS:"
                        color: "#00E5FF"
                        font.pixelSize: 11
                        font.bold: true
                    }
                    Text {
                        text: (stateModel && stateModel.response) ? stateModel.response : "Awaiting command..."
                        color: (stateModel && stateModel.response) ? "#F0F4F8" : "#64748B"
                        font.pixelSize: 13
                        elide: Text.ElideRight
                        width: parent.width - 70
                    }
                }
            }
        }

        // Search / Direct Text Input Bar
        GlassPanel {
            anchors.horizontalCenter: parent.horizontalCenter
            width: parent.width
            height: 44
            activeBorder: cmdInput.activeFocus

            Row {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 10
                spacing: 10

                Text {
                    text: "⌨"
                    color: "#94A3B8"
                    font.pixelSize: 15
                    anchors.verticalCenter: parent.verticalCenter
                }

                TextInput {
                    id: cmdInput
                    width: parent.width - 90
                    anchors.verticalCenter: parent.verticalCenter
                    color: "#F0F4F8"
                    font.pixelSize: 13
                    clip: true
                    selectByMouse: true

                    Text {
                        text: "Ask Jarvis... (e.g. 'Open Chrome', 'What time is it?')"
                        color: "#64748B"
                        font.pixelSize: 13
                        visible: !cmdInput.text && !cmdInput.activeFocus
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    onAccepted: {
                        if (cmdInput.text.trim().length > 0 && controller) {
                            controller.sendCommand(cmdInput.text);
                            cmdInput.text = "";
                        }
                    }
                }

                Rectangle {
                    width: 50
                    height: 28
                    radius: 4
                    color: "#1A2230"
                    border.color: "#00E5FF"
                    border.width: 1
                    anchors.verticalCenter: parent.verticalCenter

                    Text {
                        anchors.centerIn: parent
                        text: "SEND"
                        color: "#00E5FF"
                        font.pixelSize: 10
                        font.bold: true
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (cmdInput.text.trim().length > 0 && controller) {
                                controller.sendCommand(cmdInput.text);
                                cmdInput.text = "";
                            }
                        }
                    }
                }
            }
        }

        // Quick Controls
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 12

            Rectangle {
                id: talkBtn
                width: 100
                height: 32
                radius: 6
                color: (stateModel && stateModel.isListening) ? "#FF1744" : (talkMouse.containsMouse ? "#33EBFF" : "#00E5FF")
                scale: talkMouse.pressed ? 0.94 : (talkMouse.containsMouse ? 1.03 : 1.0)
                Behavior on scale { NumberAnimation { duration: 100 } }
                Behavior on color { ColorAnimation { duration: 150 } }

                Text {
                    anchors.centerIn: parent
                    text: (stateModel && stateModel.isListening) ? "LISTENING..." : "TALK"
                    color: (stateModel && stateModel.isListening) ? "#FFFFFF" : "#0A0D12"
                    font.pixelSize: 12
                    font.bold: true
                }
                MouseArea {
                    id: talkMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (!controller) return;
                        if (stateModel && stateModel.isListening) {
                            controller.stopPTT();
                        } else {
                            controller.startPTT();
                        }
                    }
                }
            }

            Rectangle {
                id: stopBtn
                width: 110
                height: 32
                radius: 6
                color: stopMouse.containsMouse ? "#2A3649" : "#1A2230"
                border.color: stopMouse.containsMouse ? "#64748B" : "#334155"
                border.width: 1
                scale: stopMouse.pressed ? 0.94 : (stopMouse.containsMouse ? 1.03 : 1.0)
                Behavior on scale { NumberAnimation { duration: 100 } }
                Behavior on color { ColorAnimation { duration: 150 } }

                Text {
                    anchors.centerIn: parent
                    text: "STOP TALKING"
                    color: "#F0F4F8"
                    font.pixelSize: 11
                    font.bold: true
                }
                MouseArea {
                    id: stopMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (controller) controller.stopSpeaking()
                }
            }

            Rectangle {
                id: cancelBtn
                width: 110
                height: 32
                radius: 6
                color: cancelMouse.containsMouse ? "#3A1A22" : "#1A2230"
                border.color: cancelMouse.containsMouse ? "#FF1744" : "#FF5252"
                border.width: 1
                scale: cancelMouse.pressed ? 0.94 : (cancelMouse.containsMouse ? 1.03 : 1.0)
                Behavior on scale { NumberAnimation { duration: 100 } }
                Behavior on color { ColorAnimation { duration: 150 } }

                Text {
                    anchors.centerIn: parent
                    text: "CANCEL TASK"
                    color: "#FF5252"
                    font.pixelSize: 11
                    font.bold: true
                }
                MouseArea {
                    id: cancelMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (controller) controller.cancelTask()
                }
            }
        }
    }
}

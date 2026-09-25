import QtQuick
import QtQuick.Layouts
import "../components"
import "../components/palette.js" as Palette

Item {
    id: root
    property var stateModel
    property var controller

    readonly property string st: stateModel ? stateModel.assistantState : "IDLE"
    readonly property color tint: Palette.stateColor(st)
    readonly property bool listening: stateModel ? stateModel.isListening : false
    readonly property bool lowRes: stateModel ? stateModel.lowResourceMode : false

    function send(text) {
        var t = (text || "").trim()
        if (t.length > 0 && controller) controller.sendCommand(t)
    }

    // Shortcuts: Ctrl+K type, Ctrl+Space talk, Esc stop talking
    Shortcut { sequence: "Ctrl+K"; onActivated: cmdInput.forceActiveFocus() }
    Shortcut { sequence: "Ctrl+Space"; onActivated: if (controller) controller.toggleTalk() }
    Shortcut { sequence: "Esc"; onActivated: { if (controller) controller.stopSpeaking(); cmdInput.focus = false } }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 18

        // ------------------------------------------------------------------ reactor column
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12

            Item {
                id: stage
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 220

                ReactorView {
                    id: reactor
                    anchors.centerIn: parent
                    width: Math.min(parent.width, parent.height)
                    height: width
                    assistantState: root.st
                    level: stateModel ? stateModel.audioLevel : 0
                    lowResourceMode: root.lowRes
                    prefer3D: stateModel ? stateModel.ui3d : true
                    onActivated: if (controller) controller.toggleTalk()
                }

                // HUD corner brackets
                Repeater {
                    model: 4
                    Item {
                        width: 26; height: 26
                        x: (index % 2 === 0) ? 0 : stage.width - width
                        y: (index < 2) ? 0 : stage.height - height
                        opacity: 0.45
                        Rectangle { width: 26; height: 2; color: root.tint; y: index < 2 ? 0 : 24 }
                        Rectangle { width: 2; height: 26; color: root.tint; x: index % 2 === 0 ? 0 : 24 }
                    }
                }

                // state chip
                Rectangle {
                    x: 14; y: 12
                    height: 30
                    width: chipRow.implicitWidth + 24
                    radius: 15
                    color: Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.12)
                    border.color: Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.5)
                    Behavior on color { ColorAnimation { duration: 200 } }
                    Row {
                        id: chipRow
                        anchors.centerIn: parent
                        spacing: 8
                        Rectangle {
                            width: 8; height: 8; radius: 4
                            color: root.tint
                            anchors.verticalCenter: parent.verticalCenter
                            SequentialAnimation on opacity {
                                running: !root.lowRes
                                loops: Animation.Infinite
                                NumberAnimation { to: 0.25; duration: 700 }
                                NumberAnimation { to: 1.0; duration: 700 }
                            }
                        }
                        Text {
                            text: Palette.label(root.st).toUpperCase()
                            color: "#E6F7FF"
                            font.pixelSize: 11
                            font.bold: true
                            font.letterSpacing: 1.6
                        }
                    }
                }

                Text {
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    text: reactor.showing3D ? "3D" : "2D"
                    color: "#4B6584"
                    font.pixelSize: 10
                    font.bold: true
                    font.letterSpacing: 2
                }

            }


            // live caption: what you're saying, then what JARVIS answers
            Column {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: Math.min(stage.width - 40, 680)
                spacing: 4
                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    text: stateModel ? (root.listening ? (stateModel.transcriptPartial || "Listening...") : (stateModel.transcriptFinal || "")) : ""
                    color: root.listening ? "#E6F7FF" : "#7F93AD"
                    font.pixelSize: root.listening ? 18 : 13
                    font.italic: root.listening
                    elide: Text.ElideLeft
                    Behavior on font.pixelSize { NumberAnimation { duration: 150 } }
                }
                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    visible: !root.listening && text.length > 0
                    text: stateModel && stateModel.response ? stateModel.response
                          : (stateModel && stateModel.transcriptFinal ? "" : "Say “Hey Jarvis”, click the reactor, or press Ctrl+Space")
                    color: stateModel && stateModel.response ? "#F0F4F8" : "#56708F"
                    font.pixelSize: 15
                    wrapMode: Text.WordWrap
                    maximumLineCount: 3
                    elide: Text.ElideRight
                }
            }
            VoiceWaveform {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 300
                Layout.preferredHeight: 34
                levels: stateModel ? stateModel.audioLevels : []
                active: root.listening
                barColor: root.tint
            }

            // quick actions
            Flow {
                Layout.fillWidth: true
                spacing: 8
                Repeater {
                    model: [
                        { label: "Screenshot", icon: "▣", cmd: "take a screenshot" },
                        { label: "Weather", icon: "☁", cmd: "what's the weather today" },
                        { label: "WhatsApp summary", icon: "✉", cmd: "summarize my whatsapp" },
                        { label: "Reminders", icon: "⏰", cmd: "show my reminders" },
                        { label: "Phone status", icon: "☎", cmd: "is my phone connected" },
                        { label: "Open Chrome", icon: "◎", cmd: "open chrome" },
                        { label: "System", icon: "⚙", cmd: "how is my system doing" }
                    ]
                    delegate: Rectangle {
                        height: 30
                        width: chipText.implicitWidth + 30
                        radius: 15
                        color: chipMouse.containsMouse ? Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.18) : Qt.rgba(1, 1, 1, 0.04)
                        border.color: chipMouse.containsMouse ? root.tint : Qt.rgba(1, 1, 1, 0.10)
                        scale: chipMouse.pressed ? 0.95 : 1.0
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Behavior on scale { NumberAnimation { duration: 80 } }
                        Text {
                            id: chipText
                            anchors.centerIn: parent
                            text: modelData.icon + "  " + modelData.label
                            color: "#CFE3F7"
                            font.pixelSize: 12
                        }
                        MouseArea {
                            id: chipMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.send(modelData.cmd)
                        }
                    }
                }
            }

            // command bar
            GlassPanel {
                Layout.fillWidth: true
                Layout.preferredHeight: 54
                activeBorder: cmdInput.activeFocus
                glowColor: root.tint

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    spacing: 10

                    // mic button
                    Rectangle {
                        Layout.preferredWidth: 38
                        Layout.preferredHeight: 38
                        radius: 19
                        color: root.listening ? "#00E676" : (micMouse.containsMouse ? Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.25) : Qt.rgba(1, 1, 1, 0.06))
                        border.color: root.listening ? "#00E676" : Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.6)
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Text {
                            anchors.centerIn: parent
                            text: root.listening ? "■" : "🎙"
                            color: root.listening ? "#04120A" : "#E6F7FF"
                            font.pixelSize: root.listening ? 12 : 16
                        }
                        SequentialAnimation on scale {
                            running: root.listening && !root.lowRes
                            loops: Animation.Infinite
                            NumberAnimation { to: 1.08; duration: 450; easing.type: Easing.InOutQuad }
                            NumberAnimation { to: 1.0; duration: 450; easing.type: Easing.InOutQuad }
                        }
                        MouseArea {
                            id: micMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (controller) controller.toggleTalk()
                        }
                    }

                    TextInput {
                        id: cmdInput
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter
                        color: "#F0F4F8"
                        font.pixelSize: 14
                        clip: true
                        selectByMouse: true
                        selectionColor: root.tint
                        Text {
                            text: "Ask or tell JARVIS anything...   (Ctrl+K)"
                            color: "#56708F"
                            font.pixelSize: 14
                            visible: !cmdInput.text && !cmdInput.activeFocus
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Keys.onUpPressed: if (history.length) { historyIndex = Math.max(0, historyIndex - 1); text = history[historyIndex] }
                        Keys.onDownPressed: if (history.length) { historyIndex = Math.min(history.length, historyIndex + 1); text = historyIndex < history.length ? history[historyIndex] : "" }
                        property var history: []
                        property int historyIndex: 0
                        onAccepted: {
                            var t = text.trim()
                            if (!t.length) return
                            history = history.concat([t]).slice(-30)
                            historyIndex = history.length
                            root.send(t)
                            text = ""
                        }
                    }

                    // stop speaking
                    Rectangle {
                        Layout.preferredWidth: 34
                        Layout.preferredHeight: 34
                        radius: 8
                        visible: stateModel ? stateModel.isSpeaking || stateModel.isTaskRunning : false
                        color: stopMouse.containsMouse ? "#3A1A22" : Qt.rgba(1, 1, 1, 0.04)
                        border.color: "#FF5252"
                        Text { anchors.centerIn: parent; text: "✕"; color: "#FF8A80"; font.pixelSize: 13 }
                        MouseArea {
                            id: stopMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (!controller) return
                                if (stateModel && stateModel.isSpeaking) controller.stopSpeaking()
                                else controller.cancelTask()
                            }
                        }
                    }

                    // send
                    Rectangle {
                        Layout.preferredWidth: 72
                        Layout.preferredHeight: 36
                        radius: 10
                        opacity: cmdInput.text.trim().length ? 1.0 : 0.55
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: Qt.lighter(root.tint, 1.15) }
                            GradientStop { position: 1.0; color: Qt.darker(root.tint, 1.25) }
                        }
                        scale: sendMouse.pressed ? 0.95 : 1.0
                        Behavior on scale { NumberAnimation { duration: 80 } }
                        Text { anchors.centerIn: parent; text: "SEND"; color: "#05101A"; font.pixelSize: 12; font.bold: true; font.letterSpacing: 1.5 }
                        MouseArea {
                            id: sendMouse
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: cmdInput.accepted()
                        }
                    }
                }
            }
        }

        // ------------------------------------------------------------------ conversation
        GlassPanel {
            Layout.preferredWidth: Math.max(280, Math.min(380, root.width * 0.32))
            Layout.fillHeight: true
            visible: root.width > 760

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    Text { text: "CONVERSATION"; color: "#8FB3D9"; font.pixelSize: 11; font.bold: true; font.letterSpacing: 2; Layout.fillWidth: true }
                    Text {
                        text: "Clear"
                        color: clearMouse.containsMouse ? "#E6F7FF" : "#56708F"
                        font.pixelSize: 11
                        MouseArea { id: clearMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: if (stateModel) stateModel.clearConversation() }
                    }
                }

                ListView {
                    id: chat
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 10
                    model: stateModel ? stateModel.conversation : []
                    onCountChanged: Qt.callLater(chat.positionViewAtEnd)
                    onContentHeightChanged: if (atYEnd || chat.count < 3) Qt.callLater(chat.positionViewAtEnd)
                    boundsBehavior: Flickable.StopAtBounds

                    delegate: Item {
                        readonly property bool mine: modelData.role === "user"
                        width: chat.width
                        height: bubble.height + 16

                        Text {
                            anchors.top: parent.top
                            anchors.left: mine ? undefined : parent.left
                            anchors.right: mine ? parent.right : undefined
                            text: (mine ? "You" : "JARVIS") + "  ·  " + modelData.time
                            color: "#4B6584"
                            font.pixelSize: 9
                            font.bold: true
                        }
                        Rectangle {
                            id: bubble
                            y: 14
                            anchors.left: mine ? undefined : parent.left
                            anchors.right: mine ? parent.right : undefined
                            width: Math.min(chat.width * 0.88, msg.implicitWidth + 24)
                            height: msg.implicitHeight + 18
                            radius: 12
                            color: mine ? Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.16)
                                        : (modelData.state && modelData.state !== "SUCCESS" && modelData.state !== "WAITING_CONFIRMATION"
                                           ? Qt.rgba(1, 0.32, 0.32, 0.10) : Qt.rgba(1, 1, 1, 0.05))
                            border.color: mine ? Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.35) : Qt.rgba(1, 1, 1, 0.08)
                            Text {
                                id: msg
                                x: 12; y: 9
                                width: Math.min(implicitWidth, chat.width * 0.88 - 24)
                                text: modelData.text + (modelData.streaming ? " ▍" : "")
                                color: "#E8F1FA"
                                font.pixelSize: 13
                                wrapMode: Text.Wrap
                                textFormat: Text.PlainText
                            }
                        }
                    }

                    Text {
                        anchors.centerIn: parent
                        visible: chat.count === 0
                        width: parent.width - 20
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        text: "Your conversation with JARVIS appears here.\nTry “explain black holes simply” or “remind me to stretch in 20 minutes”."
                        color: "#4B6584"
                        font.pixelSize: 12
                        lineHeight: 1.3
                    }
                }
            }
        }
    }
}

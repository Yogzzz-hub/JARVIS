import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes
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

    // Incremental copy of the conversation: appended messages animate in, streamed text updates in place.
    ListModel { id: convModel }
    function syncConversation() {
        var src = stateModel ? stateModel.conversation : []
        if (src.length < convModel.count || (src.length > 0 && convModel.count > 0 && src.length === convModel.count
                && src[0].time + src[0].text !== convModel.get(0).time + convModel.get(0).text && src.length >= 50)) {
            // cleared, or the oldest message scrolled out of the history window
            convModel.clear()
        }
        for (var i = 0; i < src.length; i++) {
            var m = src[i]
            var row = { role: m.role, text: m.text, time: m.time, streaming: !!m.streaming, state: m.state || "" }
            if (i < convModel.count) {
                var cur = convModel.get(i)
                if (cur.text !== row.text || cur.streaming !== row.streaming || cur.state !== row.state)
                    convModel.set(i, row)
            } else {
                convModel.append(row)
            }
        }
    }
    Connections {
        target: stateModel
        function onConversationChanged() { root.syncConversation() }
    }
    Component.onCompleted: syncConversation()

    readonly property bool thinking: (st === "EXECUTING" || st === "ROUTING" || st === "PLANNING" || st === "UNDERSTANDING"
                                      || st === "TRANSCRIBING") && convModel.count > 0 && convModel.get(convModel.count - 1).role === "user"

    onStChanged: if (st === "LISTENING" && !lowRes) wakeRipple.restart()

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

                    // boot: the reactor powers up when the dashboard opens
                    scale: 1.0
                    Component.onCompleted: if (!root.lowRes) bootAnim.start()
                    SequentialAnimation {
                        id: bootAnim
                        PropertyAction { target: reactor; property: "opacity"; value: 0 }
                        PropertyAction { target: reactor; property: "scale"; value: 0.55 }
                        PauseAnimation { duration: 120 }
                        ParallelAnimation {
                            NumberAnimation { target: reactor; property: "opacity"; to: 1; duration: 700; easing.type: Easing.OutCubic }
                            NumberAnimation { target: reactor; property: "scale"; to: 1; duration: 1100; easing.type: Easing.OutBack; easing.overshoot: 1.4 }
                        }
                    }
                }

                // radar sweep behind the reactor while JARVIS is working
                Shape {
                    id: radar
                    anchors.centerIn: reactor
                    width: reactor.width * 0.98
                    height: width
                    z: -1
                    visible: opacity > 0.01
                    opacity: Palette.isBusy(root.st) && !root.lowRes ? 0.55 : 0.0
                    Behavior on opacity { NumberAnimation { duration: 400 } }
                    preferredRendererType: Shape.CurveRenderer
                    ShapePath {
                        strokeWidth: 0
                        strokeColor: "transparent"
                        fillGradient: ConicalGradient {
                            centerX: radar.width / 2; centerY: radar.height / 2
                            angle: sweepAngle.value
                            GradientStop { position: 0.0; color: Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.35) }
                            GradientStop { position: 0.12; color: Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.0) }
                            GradientStop { position: 1.0; color: Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.0) }
                        }
                        PathAngleArc { centerX: radar.width / 2; centerY: radar.height / 2; radiusX: radar.width / 2; radiusY: radar.height / 2; startAngle: 0; sweepAngle: 360 }
                    }
                    QtObject { id: sweepAngle; property real value: 0 }
                    NumberAnimation {
                        target: sweepAngle; property: "value"; from: 360; to: 0; duration: 1800
                        loops: Animation.Infinite; running: radar.visible
                    }
                }

                // wake ripple: three shockwaves when JARVIS starts listening
                Item {
                    id: rippleHost
                    anchors.centerIn: reactor
                    width: reactor.width * 0.42
                    height: width
                    component Ring: Rectangle {
                        anchors.centerIn: parent
                        width: parent.width; height: width; radius: width / 2
                        color: "transparent"
                        border.width: 2
                        border.color: root.tint
                        opacity: 0
                    }
                    Ring { id: ring1 }
                    Ring { id: ring2 }
                    Ring { id: ring3 }
                    component Wave: SequentialAnimation {
                        property Item ring
                        property int delay: 0
                        property real peak: 0.9
                        property real reach: 2.6
                        PauseAnimation { duration: delay }
                        PropertyAction { target: ring; property: "opacity"; value: peak }
                        ParallelAnimation {
                            NumberAnimation { target: ring; property: "scale"; from: 1; to: reach; duration: 950; easing.type: Easing.OutCubic }
                            NumberAnimation { target: ring; property: "opacity"; to: 0; duration: 950; easing.type: Easing.InQuad }
                        }
                    }
                    ParallelAnimation {
                        id: wakeRipple
                        Wave { ring: ring1 }
                        Wave { ring: ring2; delay: 160; peak: 0.7; reach: 2.3 }
                        Wave { ring: ring3; delay: 320; peak: 0.5; reach: 2.0 }
                    }
                }

                // "systems online" boot caption
                Text {
                    id: bootText
                    anchors.horizontalCenter: reactor.horizontalCenter
                    anchors.top: reactor.bottom
                    anchors.topMargin: -reactor.height * 0.12
                    text: "SYSTEMS ONLINE"
                    color: root.tint
                    font.pixelSize: 12
                    font.bold: true
                    font.letterSpacing: 6
                    opacity: 0
                    SequentialAnimation on opacity {
                        running: !root.lowRes
                        PauseAnimation { duration: 700 }
                        NumberAnimation { to: 0.9; duration: 400 }
                        PauseAnimation { duration: 1400 }
                        NumberAnimation { to: 0; duration: 700 }
                    }
                    SequentialAnimation on font.letterSpacing {
                        running: !root.lowRes
                        PauseAnimation { duration: 700 }
                        NumberAnimation { from: 14; to: 6; duration: 900; easing.type: Easing.OutCubic }
                    }
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
                Layout.alignment: Qt.AlignHCenter
                spacing: 10
                Repeater {
                    model: [
                        { label: "Screenshot",       iconKey: "screenshot", cmd: "take a screenshot" },
                        { label: "Weather",           iconKey: "weather",    cmd: "what's the weather today" },
                        { label: "WhatsApp summary",  iconKey: "whatsapp",   cmd: "summarize my whatsapp" },
                        { label: "Reminders",         iconKey: "reminders",  cmd: "show my reminders" },
                        { label: "Phone status",      iconKey: "phone",      cmd: "is my phone connected" },
                        { label: "Open Chrome",       iconKey: "chrome",     cmd: "open chrome" },
                        { label: "System",            iconKey: "cog",        cmd: "how is my system doing" }
                    ]
                    delegate: Rectangle {
                        height: 34
                        width: chipRow2.implicitWidth + 38
                        radius: 17
                        color: chipMouse.containsMouse
                               ? Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.16)
                               : Qt.rgba(1, 1, 1, 0.035)
                        border.color: chipMouse.containsMouse
                                      ? Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.55)
                                      : Qt.rgba(1, 1, 1, 0.09)
                        border.width: 1
                        scale: chipMouse.pressed ? 0.94 : 1.0
                        Behavior on color { ColorAnimation { duration: 150 } }
                        Behavior on border.color { ColorAnimation { duration: 150 } }
                        Behavior on scale { NumberAnimation { duration: 80 } }

                        Row {
                            id: chipRow2
                            anchors.centerIn: parent
                            spacing: 8

                            IconCanvas {
                                width: 14; height: 14
                                icon: modelData.iconKey
                                iconColor: chipMouse.containsMouse ? root.tint : "#8FB3D9"
                                iconStroke: 1.3
                                anchors.verticalCenter: parent.verticalCenter
                                Behavior on iconColor { ColorAnimation { duration: 150 } }
                            }

                            Text {
                                text: modelData.label
                                color: chipMouse.containsMouse ? "#F0F4F8" : "#CFE3F7"
                                font.pixelSize: 12
                                font.family: "Segoe UI"
                                anchors.verticalCenter: parent.verticalCenter
                                Behavior on color { ColorAnimation { duration: 150 } }
                            }
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
                        Layout.preferredWidth: 76
                        Layout.preferredHeight: 38
                        radius: 12
                        opacity: cmdInput.text.trim().length ? 1.0 : 0.45
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: Qt.lighter(root.tint, 1.2) }
                            GradientStop { position: 1.0; color: Qt.darker(root.tint, 1.15) }
                        }
                        scale: sendMouse.pressed ? 0.93 : (sendMouse.containsMouse ? 1.03 : 1.0)
                        Behavior on scale { NumberAnimation { duration: 100; easing.type: Easing.OutCubic } }
                        Behavior on opacity { NumberAnimation { duration: 150 } }

                        Row {
                            anchors.centerIn: parent
                            spacing: 6
                            Text {
                                text: "SEND"
                                color: "#05101A"
                                font.pixelSize: 12
                                font.bold: true
                                font.letterSpacing: 1.5
                                font.family: "Segoe UI"
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            Text {
                                text: "→"
                                color: "#05101A"
                                font.pixelSize: 14
                                font.bold: true
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }

                        // hover glow
                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: -3
                            radius: parent.radius + 3
                            color: "transparent"
                            border.width: 2
                            border.color: Qt.rgba(root.tint.r, root.tint.g, root.tint.b,
                                                  sendMouse.containsMouse ? 0.3 : 0)
                            z: -1
                            Behavior on border.color { ColorAnimation { duration: 180 } }
                        }

                        MouseArea {
                            id: sendMouse
                            anchors.fill: parent
                            hoverEnabled: true
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

                // conversation header
                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 32

                    RowLayout {
                        anchors.fill: parent
                        spacing: 8

                        // chat icon
                        IconCanvas {
                            Layout.preferredWidth: 16; Layout.preferredHeight: 16
                            icon: "whatsapp"
                            iconColor: root.tint
                            iconStroke: 1.4
                        }

                        Text {
                            text: "CONVERSATION"
                            color: "#8FB3D9"
                            font.pixelSize: 11
                            font.bold: true
                            font.letterSpacing: 2.5
                            Layout.fillWidth: true
                        }

                        // clear button
                        Rectangle {
                            Layout.preferredWidth: 52; Layout.preferredHeight: 24
                            radius: 12
                            color: clearMouse.containsMouse ? Qt.rgba(1, 0.32, 0.32, 0.12) : "transparent"
                            border.color: clearMouse.containsMouse ? "#FF5252" : Qt.rgba(1, 1, 1, 0.08)
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Behavior on border.color { ColorAnimation { duration: 120 } }
                            Text {
                                anchors.centerIn: parent
                                text: "Clear"
                                color: clearMouse.containsMouse ? "#FF8A80" : "#56708F"
                                font.pixelSize: 10
                                font.bold: true
                                Behavior on color { ColorAnimation { duration: 120 } }
                            }
                            MouseArea {
                                id: clearMouse; anchors.fill: parent; hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (stateModel) stateModel.clearConversation()
                            }
                        }
                    }

                    // gradient underline
                    Rectangle {
                        anchors.bottom: parent.bottom
                        anchors.left: parent.left; anchors.right: parent.right
                        height: 1
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.3) }
                            GradientStop { position: 0.5; color: Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.08) }
                            GradientStop { position: 1.0; color: "transparent" }
                        }
                    }
                }

                ListView {
                    id: chat
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 10
                    model: convModel
                    onCountChanged: Qt.callLater(chat.positionViewAtEnd)
                    onContentHeightChanged: if (atYEnd || chat.count < 3) Qt.callLater(chat.positionViewAtEnd)
                    boundsBehavior: Flickable.StopAtBounds

                    // new messages glide in; nothing else re-animates
                    add: Transition {
                        enabled: !root.lowRes
                        ParallelAnimation {
                            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 260; easing.type: Easing.OutCubic }
                            NumberAnimation { property: "scale"; from: 0.92; to: 1; duration: 320; easing.type: Easing.OutBack }
                        }
                    }
                    addDisplaced: Transition { NumberAnimation { properties: "y"; duration: 200; easing.type: Easing.OutCubic } }

                    footer: Item {
                        width: chat.width
                        height: root.thinking ? 44 : 0
                        visible: root.thinking
                        Rectangle {
                            y: 8
                            width: 64; height: 30; radius: 12
                            color: Qt.rgba(1, 1, 1, 0.05)
                            border.color: Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.35)
                            Row {
                                anchors.centerIn: parent
                                spacing: 6
                                Repeater {
                                    model: 3
                                    Rectangle {
                                        width: 7; height: 7; radius: 4
                                        color: root.tint
                                        SequentialAnimation on opacity {
                                            running: root.thinking && !root.lowRes
                                            loops: Animation.Infinite
                                            PauseAnimation { duration: index * 150 }
                                            NumberAnimation { to: 0.2; duration: 300 }
                                            NumberAnimation { to: 1.0; duration: 300 }
                                            PauseAnimation { duration: (2 - index) * 150 }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    delegate: Item {
                        readonly property bool mine: model.role === "user"
                        width: chat.width
                        height: bubble.height + 16
                        transformOrigin: mine ? Item.Right : Item.Left

                        Text {
                            anchors.top: parent.top
                            anchors.left: mine ? undefined : parent.left
                            anchors.right: mine ? parent.right : undefined
                            text: (mine ? "You" : "JARVIS") + "  \u00B7  " + model.time
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
                                        : (model.state && model.state !== "SUCCESS" && model.state !== "WAITING_CONFIRMATION"
                                           ? Qt.rgba(1, 0.32, 0.32, 0.10) : Qt.rgba(1, 1, 1, 0.05))
                            border.color: mine ? Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.35) : Qt.rgba(1, 1, 1, 0.08)
                            Behavior on height { enabled: !root.lowRes; NumberAnimation { duration: 120 } }
                            Text {
                                id: msg
                                x: 12; y: 9
                                width: Math.min(implicitWidth, chat.width * 0.88 - 24)
                                text: model.text + (model.streaming ? " \u258D" : "")
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

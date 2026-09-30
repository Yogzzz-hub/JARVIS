import QtQuick
import "palette.js" as Palette

// How JARVIS handles every request, lit live from the assistant state:
// LISTEN -> UNDERSTAND -> PLAN -> ACT -> SPEAK. The current stage glows, finished ones stay lit, and a pulse runs
// along the link while JARVIS is working.
Item {
    id: root
    property string assistantState: "IDLE"
    property bool animate: true
    readonly property var stages: [
        { k: "LISTEN",     d: "wake word / mic",   states: ["LISTENING", "TRANSCRIBING"] },
        { k: "UNDERSTAND", d: "router + local AI", states: ["UNDERSTANDING", "ROUTING"] },
        { k: "PLAN",       d: "steps + safety",    states: ["PLANNING", "WAITING_CONFIRMATION"] },
        { k: "ACT",        d: "PC, phone, web",    states: ["EXECUTING", "VERIFYING"] },
        { k: "SPEAK",      d: "voice + text",      states: ["SPEAKING", "SUCCESS"] }
    ]
    readonly property int current: {
        for (var i = 0; i < stages.length; i++) if (stages[i].states.indexOf(assistantState) >= 0) return i;
        return -1;
    }
    readonly property color tint: Palette.stateColor(assistantState)
    readonly property real edge: 62
    readonly property real step: (width - 2 * edge) / (stages.length - 1)

    implicitHeight: 74

    // links
    Repeater {
        model: root.stages.length - 1
        Item {
            x: root.edge + index * root.step + 16
            y: 21
            width: root.step - 32
            height: 2
            Rectangle { anchors.fill: parent; radius: 1; color: index < root.current ? Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.7) : Qt.rgba(0.4, 0.8, 1, 0.18) }
            Rectangle {
                width: 18; height: 4; radius: 2; y: -1
                color: root.tint
                visible: root.animate && index === root.current - 1
                NumberAnimation on x { from: 0; to: parent.width - 18; duration: 700; loops: Animation.Infinite; running: parent.visible }
            }
        }
    }
    // nodes
    Repeater {
        model: root.stages
        Item {
            readonly property bool active: index === root.current
            readonly property bool done: root.current >= 0 && index < root.current
            x: root.edge + index * root.step - width / 2
            width: 110
            height: root.height
            Rectangle {
                id: node
                width: 22; height: 22; rotation: 45
                anchors.horizontalCenter: parent.horizontalCenter
                y: 11
                color: active ? Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.35) : (done ? Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.15) : Qt.rgba(0.02, 0.07, 0.14, 0.9))
                border.width: 1.5
                border.color: active || done ? root.tint : Qt.rgba(0.4, 0.8, 1, 0.35)
                Rectangle { anchors.centerIn: parent; width: 6; height: 6; color: active || done ? root.tint : Qt.rgba(0.5, 0.8, 1, 0.4) }
                Behavior on color { ColorAnimation { duration: 200 } }
            }
            Rectangle {
                anchors.centerIn: node
                width: 40; height: 40; radius: 20
                color: "transparent"
                border.width: 1.5
                border.color: root.tint
                visible: active && root.animate
                SequentialAnimation on scale { running: parent.visible; loops: Animation.Infinite
                    NumberAnimation { from: 0.6; to: 1.4; duration: 900 } }
                SequentialAnimation on opacity { running: parent.visible; loops: Animation.Infinite
                    NumberAnimation { from: 0.8; to: 0; duration: 900 } }
            }
            Column {
                anchors.horizontalCenter: parent.horizontalCenter
                y: 42
                spacing: 1
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.k; font.family: "Orbitron"; font.pixelSize: 10
                       font.letterSpacing: 2; font.weight: Font.DemiBold
                       color: active ? "#FFFFFF" : (done ? "#BFEFFF" : "#6F8AA8") }
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.d; font.pixelSize: 12
                       color: active ? root.tint : "#4F6A88" }
            }
        }
    }
}

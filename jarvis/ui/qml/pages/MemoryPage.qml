import QtQuick
import "../components"

// What JARVIS remembers about you (only what you told it to remember), your to-do list and saved shortcuts.
Item {
    id: root
    property var controller
    property var client: (typeof uiDashboard !== "undefined") ? uiDashboard : null
    readonly property var mem: client ? client.memory : ({ facts: [], todos: [], shortcuts: [] })

    function when(ts) { return ts ? Qt.formatDate(new Date(ts * 1000), "d MMM yyyy") : "" }
    onVisibleChanged: if (visible && client) client.refreshMemory()
    Component.onCompleted: if (client) client.refreshMemory()

    PageScroll {
        anchors.fill: parent

        PageHeader {
            width: parent.width
            icon: "memory"
            title: "Memory"
            subtitle: "Only what you asked JARVIS to remember. Delete anything, any time."
            JButton { text: "REFRESH"; variant: "ghost"; busy: root.client ? root.client.busy : false; onClicked: if (root.client) root.client.refreshMemory() }
        }
        NoticeBar { width: parent.width; text: root.client && root.client.noticePage === "memory" ? root.client.notice : ""; error: root.client ? root.client.noticeError : false
                    onClosed: if (root.client) root.client.clearNotice() }

        // add a fact
        Card {
            width: parent.width
            Text { text: "Teach JARVIS something"; color: "#F0F4F8"; font.pixelSize: 16; font.bold: true }
            Item {
                width: parent.width
                height: 34
                JInput { id: factInput; anchors.left: parent.left; anchors.right: addBtn.left; anchors.rightMargin: 10
                         placeholder: "e.g. my car is parked on level 2"
                         onAccepted: addBtn.clicked() }
                JButton { id: addBtn; text: "REMEMBER"; anchors.right: parent.right; enabledButton: factInput.text.trim().length > 0
                          onClicked: if (root.client) { root.client.addFact(factInput.text); factInput.text = "" } }
            }
        }

        SectionLabel { text: "REMEMBERED FACTS"; hint: root.mem.facts.length + " saved" }
        Column {
            width: parent.width
            spacing: 10
            Repeater {
                model: root.mem.facts
                delegate: Card {
                    width: parent.width
                    padding: 14
                    Item {
                        width: parent.width
                        height: Math.max(factText.implicitHeight, 26)
                        Text { id: factText; text: modelData.fact; color: "#E2E8F0"; font.pixelSize: 15; wrapMode: Text.WordWrap
                               anchors.left: parent.left; anchors.right: dateText.left; anchors.rightMargin: 14; anchors.verticalCenter: parent.verticalCenter }
                        Text { id: dateText; text: root.when(modelData.created_at); color: "#64748B"; font.pixelSize: 13
                               anchors.right: forget.left; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter }
                        JButton { id: forget; text: "FORGET"; variant: "danger"; small: true; anchors.right: parent.right
                                  anchors.verticalCenter: parent.verticalCenter; onClicked: root.client.forgetFact(modelData.id) }
                    }
                }
            }
            EmptyState { width: parent.width; visible: root.mem.facts.length === 0; title: "Nothing remembered yet"
                         hint: "Say \"remember that my wifi password is on the fridge\" or type it above." }
        }

        SectionLabel { text: "TO-DO LIST"; hint: root.mem.todos.length + " items" }
        Card {
            width: parent.width
            visible: root.mem.todos.length > 0
            Repeater {
                model: root.mem.todos
                delegate: Row {
                    spacing: 10
                    Rectangle { width: 16; height: 16; radius: 4; color: modelData.done ? "#00E676" : "transparent"
                                border.width: 1; border.color: modelData.done ? "#00E676" : "#4A5B73"; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: modelData.text; color: modelData.done ? "#64748B" : "#E2E8F0"; font.pixelSize: 15
                           font.strikeout: modelData.done }
                }
            }
        }
        EmptyState { width: parent.width; visible: root.mem.todos.length === 0; title: "No to-dos"
                     hint: "Say \"add buy milk to my to-do list\"." }

        SectionLabel { text: "SHORTCUTS"; hint: "one phrase runs several steps" }
        Column {
            width: parent.width
            spacing: 10
            Repeater {
                model: root.mem.shortcuts
                delegate: Card {
                    width: parent.width
                    padding: 14
                    Item {
                        width: parent.width
                        height: Math.max(scCol.implicitHeight, 26)
                        Column {
                            id: scCol
                            anchors.left: parent.left; anchors.right: del.left; anchors.rightMargin: 14
                            spacing: 3
                            Text { text: "“" + modelData.phrase + "”"; color: "#F0F4F8"; font.pixelSize: 15; font.bold: true }
                            Text { text: (modelData.steps || []).join("  →  "); color: "#8193AB"; font.pixelSize: 14; wrapMode: Text.WordWrap; width: parent.width }
                        }
                        JButton { id: del; text: "DELETE"; variant: "danger"; small: true; anchors.right: parent.right
                                  anchors.verticalCenter: parent.verticalCenter; onClicked: root.client.deleteShortcut(modelData.phrase) }
                    }
                }
            }
            EmptyState { width: parent.width; visible: root.mem.shortcuts.length === 0; title: "No shortcuts yet"
                         hint: "Say \"when I say study mode, open notes and set volume to 20\"." }
        }
    }
}

import QtQuick
import "../components"

Item {
    id: root
    property var activityModel
    property var controller
    property var stateModel
    readonly property var tasks: stateModel && stateModel.recentTasks ? stateModel.recentTasks : []
    function countState(list) { var n = 0; for (var i = 0; i < tasks.length; i++) if (list.indexOf(tasks[i].state) >= 0) n++; return n }

    Item {
        anchors.fill: parent
        anchors.leftMargin: root.width < 900 ? 20 : 28
        anchors.rightMargin: root.width < 900 ? 20 : 28
        anchors.topMargin: 24
        anchors.bottomMargin: 16

        PageHeader {
            id: head
            width: parent.width
            icon: "activity"
            title: "Activity"
            subtitle: "Everything you asked JARVIS to do, newest first (last 50)."
            JButton { text: "WHAT DID YOU DO?"; variant: "ghost"; onClicked: if (root.controller) root.controller.sendCommand("what did you do just now") }
        }

        PageHero {
            id: hero
            anchors.top: head.bottom
            anchors.topMargin: 18
            width: parent.width
            icon: "activity"
            caption: "MISSION LOG"
            HoloGauge { width: 132; height: 156; label: "Success"; tint: "#00E676"
                        value: root.tasks.length ? 100 * root.countState(["SUCCESS"]) / root.tasks.length : 0
                        text: root.tasks.length ? Math.round(100 * root.countState(["SUCCESS"]) / root.tasks.length) + "" : "--" }
            HoloStat { value: root.tasks.length + ""; label: "Commands"; hint: "this session" }
            HoloStat { value: root.countState(["ERROR", "FAILED", "TIMEOUT"]) + ""; label: "Failed"; tint: "#FF5252"; hint: "open one to see why" }
            HoloStat { value: root.countState(["WAITING_CONFIRMATION"]) + ""; label: "Waiting"; tint: "#FFB300"; hint: "need your OK" }
            HoloStat { value: root.tasks.length ? root.tasks[0].duration : "--"; label: "Last run"; tint: "#B388FF"
                       hint: root.tasks.length ? root.tasks[0].text : "" }
        }

        ListView {
            id: taskList
            anchors.top: hero.bottom
            anchors.topMargin: 18
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            clip: true
            spacing: 10
            model: root.activityModel
            boundsBehavior: Flickable.StopAtBounds

            delegate: Card {
                width: taskList.width
                padding: 16
                spacing: 6
                Item {
                    width: parent.width
                    height: Math.max(req.implicitHeight, badge.height)
                    Text {
                        id: req
                        text: model.requestText || "Command"
                        color: "#F0F4F8"
                        font.pixelSize: 16
                        font.bold: true
                        elide: Text.ElideRight
                        width: parent.width - badge.width - time.implicitWidth - 28
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        id: time
                        text: model.taskTimestamp || ""
                        color: "#64748B"
                        font.pixelSize: 13
                        anchors.right: badge.left
                        anchors.rightMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    StatusBadge { id: badge; status: model.taskState || "SUCCESS"; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter }
                }
                Text {
                    width: parent.width
                    text: (model.taskMessage || "Completed")
                    color: "#B8C6D8"
                    font.pixelSize: 14
                    wrapMode: Text.WordWrap
                    maximumLineCount: 3
                    elide: Text.ElideRight
                }
                Text {
                    text: "From " + (model.taskSource || "desktop") + "  ·  " + (model.taskRoute || "router")
                    color: "#64748B"
                    font.pixelSize: 13
                }
            }

            EmptyState {
                anchors.centerIn: parent
                visible: taskList.count === 0
                title: "Nothing yet"
                hint: "Say \"Hey Jarvis\" or type a command on Home - it appears here with its result."
            }
        }
    }
}

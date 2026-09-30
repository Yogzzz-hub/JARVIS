import QtQuick
import "../components"

// Real checks (python -m jarvis.diagnostics): Python, packages, models, Ollama, FFmpeg, database, gateway.
Item {
    id: root
    property var stateModel
    property var controller
    property var client: (typeof uiDashboard !== "undefined") ? uiDashboard : null
    property string filter: "ALL"
    readonly property var checks: client ? client.diagnostics : []
    function count(s) { var n = 0; for (var i = 0; i < checks.length; i++) if (checks[i].status === s) n++; return n }

    PageScroll {
        anchors.fill: parent

        PageHeader {
            width: parent.width
            icon: "diagnostics"
            title: "Diagnostics"
            subtitle: "Checks every part JARVIS needs and says how to fix what is missing."
            JButton { text: root.checks.length ? "RUN AGAIN" : "RUN DIAGNOSTICS"; busy: root.client ? root.client.busy : false
                      onClicked: if (root.client) root.client.runDiagnostics() }
        }
        NoticeBar { width: parent.width; text: root.client && root.client.noticePage === "diagnostics" ? root.client.notice : ""; error: root.client ? root.client.noticeError : false
                    onClosed: if (root.client) root.client.clearNotice() }

        Row {
            spacing: 10
            visible: root.checks.length > 0
            Repeater {
                model: [["ALL", root.checks.length, "#94A3B8"], ["FAIL", root.count("FAIL"), "#FF5252"],
                        ["WARN", root.count("WARN"), "#FFB300"], ["PASS", root.count("PASS"), "#00E676"]]
                delegate: Rectangle {
                    width: chip.implicitWidth + 26; height: 30; radius: 15
                    color: root.filter === modelData[0] ? Qt.rgba(0, 0.9, 1, 0.14) : "transparent"
                    border.width: 1; border.color: root.filter === modelData[0] ? "#00E5FF" : "#2A3A52"
                    Text { id: chip; anchors.centerIn: parent; text: modelData[0] + "  " + modelData[1]; color: modelData[2]
                           font.pixelSize: 13; font.bold: true }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.filter = modelData[0] }
                }
            }
        }

        Column {
            width: parent.width
            spacing: 8
            Repeater {
                model: root.checks
                delegate: Card {
                    width: parent.width
                    visible: root.filter === "ALL" || modelData.status === root.filter
                    height: visible ? implicitHeight : 0
                    padding: 14
                    spacing: 4
                    Item {
                        width: parent.width
                        height: Math.max(nameText.implicitHeight, badge.height)
                        StatusBadge { id: badge; status: modelData.status === "PASS" ? "READY" : (modelData.status === "WARN" ? "WAITING" : "ERROR")
                                      text: modelData.status; anchors.verticalCenter: parent.verticalCenter }
                        Text { id: nameText; text: modelData.name; color: "#F0F4F8"; font.pixelSize: 15; font.bold: true
                               anchors.left: badge.right; anchors.leftMargin: 14; anchors.right: parent.right; elide: Text.ElideRight
                               anchors.verticalCenter: parent.verticalCenter }
                    }
                    Text { text: modelData.detail; visible: text.length > 0; color: "#8193AB"; font.pixelSize: 14
                           wrapMode: Text.WrapAnywhere; maximumLineCount: 3; elide: Text.ElideRight; width: parent.width
                           leftPadding: badge.width + 14 }
                }
            }
        }
        EmptyState {
            width: parent.width
            visible: root.checks.length === 0
            title: "No results yet"
            hint: "Press Run diagnostics. It takes a few seconds and changes nothing on your PC."
        }
    }
}

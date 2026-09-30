import QtQuick
import "../components"

Item {
    id: root
    property var controller
    property string saved: ""

    function setting(key, fallback) {
        if (!controller) return fallback;
        var v = controller.getSetting(key);
        return v === undefined || v === null ? fallback : v;
    }

    component SettingRow: Card {
        id: row
        property string title: ""
        property string desc: ""
        property string key: ""
        property bool fallback: false
        width: parent ? parent.width : 400
        padding: 16
        Item {
            width: parent.width
            height: Math.max(textCol.implicitHeight, 26)
            Column {
                id: textCol
                anchors.left: parent.left
                anchors.right: toggle.left
                anchors.rightMargin: 20
                anchors.verticalCenter: parent.verticalCenter
                spacing: 3
                Text { text: row.title; color: "#F0F4F8"; font.pixelSize: 14; font.bold: true }
                Text { text: row.desc; color: "#8193AB"; font.pixelSize: 12; wrapMode: Text.WordWrap; width: parent.width }
            }
            Toggle {
                id: toggle
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                Component.onCompleted: checked = Boolean(root.setting(row.key, row.fallback))
                onToggled: function(on) {
                    if (root.controller) root.controller.updateSetting(row.key, on);
                    root.saved = row.title + (on ? " is on." : " is off.");
                }
            }
        }
    }

    PageScroll {
        anchors.fill: parent

        PageHeader {
            width: parent.width
            title: "Settings"
            subtitle: "How the dashboard looks and behaves. Changes apply immediately."
        }
        NoticeBar { width: parent.width; text: root.saved; onClosed: root.saved = "" }

        Column {
            width: Math.min(parent.width, 760)
            spacing: 12
            SectionLabel { text: "APPEARANCE" }
            SettingRow { title: "3D reactor"; key: "ui_3d"; fallback: true
                         desc: "Real-time 3D core with glow and particles (uses the GPU). Off = the lighter 2D reactor." }
            SettingRow { title: "Low resource mode"; key: "low_resource_mode"; fallback: false
                         desc: "Pauses idle animations and samples hardware every 2 seconds instead of every second." }
            SettingRow { title: "Floating orb"; key: "floating_orb_enabled"; fallback: false
                         desc: "A small always-on-top orb you can click to talk, even when the dashboard is closed." }
            Item { width: 1; height: 6 }
            SectionLabel { text: "WINDOW" }
            SettingRow { title: "Close to tray"; key: "close_to_tray"; fallback: true
                         desc: "Closing the dashboard keeps JARVIS listening in the system tray." }
            Card {
                width: parent.width
                padding: 16
                Text { text: "Keyboard shortcuts"; color: "#F0F4F8"; font.pixelSize: 14; font.bold: true }
                Grid {
                    columns: 2
                    columnSpacing: 24
                    rowSpacing: 6
                    Repeater {
                        model: ["Talk (anywhere)", "Ctrl + Shift + J", "Open the dashboard", "Ctrl + Shift + D", "Talk (dashboard open)", "Ctrl + Space", "Type a command", "Ctrl + K", "Wake word", "“Hey Jarvis”"]
                        delegate: Text { text: modelData; color: index % 2 ? "#00E5FF" : "#B8C6D8"; font.pixelSize: 12; font.bold: index % 2 === 1 }
                    }
                }
            }
        }
    }
}

import QtQuick
import "../components"

Item {
    id: root
    readonly property var devs: stateModel && stateModel.devices ? stateModel.devices : []
    function online() { var n = 0; for (var i = 0; i < devs.length; i++) if (["ONLINE", "READY", "CONNECTED"].indexOf(devs[i].status) >= 0) n++; return n }
    function phoneStatus() { for (var i = 0; i < devs.length; i++) if ((devs[i].type || "") === "mobile") return ["ONLINE", "READY", "CONNECTED"].indexOf(devs[i].status) >= 0 ? "LINKED" : "OFFLINE"; return "NONE" }
    property var stateModel
    property var controller

    PageScroll {
        anchors.fill: parent

        PageHeader {
            width: parent.width
            icon: "devices"
            title: "Devices"
            subtitle: "Your phone and the hardware JARVIS can use."
            JButton { text: "PHONE STATUS"; variant: "ghost"; onClicked: if (root.controller) root.controller.sendCommand("phone status") }
            JButton { text: "CONNECT PHONE"; variant: "ghost"; onClicked: if (root.controller) root.controller.sendCommand("connect my phone") }
            JButton { text: "MIRROR SCREEN"; onClicked: if (root.controller) root.controller.sendCommand("mirror my phone screen") }
        }

        PageHero {
            width: parent.width
            icon: "devices"
            caption: "HARDWARE LINK"
            HoloGauge { width: 132; height: 156; label: "Online"; unit: ""; max: Math.max(1, root.devs.length)
                        value: root.online(); text: root.online() + "/" + root.devs.length }
            HoloStat { value: root.phoneStatus(); label: "Phone"; tint: root.phoneStatus() === "LINKED" ? "#00E676" : "#FF5252"
                       hint: root.phoneStatus() === "LINKED" ? "USB / Wi-Fi debugging connected" : "Say \u201Cconnect my phone\u201D" }
        }

        CardGrid {
            id: grid
            width: parent.width
            minCardWidth: 250
            Repeater {
                model: root.stateModel ? root.stateModel.devices : []
                delegate: Card {
                    width: grid.cellWidth
                    padding: 16
                    CardTitle { width: parent.width; title: modelData.name || "Device"; status: modelData.status || "OFFLINE" }
                    Text { text: "Type: " + (modelData.type || "peripheral"); color: "#8193AB"; font.pixelSize: 14 }
                }
            }
        }
        EmptyState {
            width: parent.width
            visible: !root.stateModel || !root.stateModel.devices || root.stateModel.devices.length === 0
            title: "No devices reported yet"
            hint: "Connect your phone with USB debugging (or say \"connect my phone\") and it shows up here."
        }
    }
}

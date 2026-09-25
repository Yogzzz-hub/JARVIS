import QtQuick
import "../components"

Item {
    id: root
    property var stateModel
    property var controller

    Flickable {
        anchors.fill: parent
        anchors.margins: 20
        contentHeight: contentCol.height + 40
        clip: true

        Column {
            id: contentCol
            width: parent.width
            spacing: 20

            // Header
            Row {
                width: parent.width
                Text {
                    text: "SYSTEM HARDWARE & MODEL RESIDENCY"
                    color: "#F0F4F8"
                    font.pixelSize: 18
                    font.bold: true
                }
                Item { width: Math.max(0, parent.width - 480); height: 1 }
                StatusBadge {
                    status: stateModel ? stateModel.connectionStatus : "OFFLINE"
                }
            }

            Rectangle {
                width: parent.width
                height: 1
                color: "#222D3E"
            }

            // Metric Cards Grid
            Text {
                text: "HARDWARE TELEMETRY (1 HZ SAMPLING)"
                color: "#94A3B8"
                font.pixelSize: 12
                font.bold: true
            }

            Flow {
                width: parent.width
                spacing: 16

                MetricCard {
                    title: "CPU Load"
                    value: stateModel ? stateModel.cpuPercent.toFixed(1) : "0"
                    unit: "%"
                    accentColor: "#00E5FF"
                    history: stateModel ? stateModel.getCpuHistory() : []
                }

                MetricCard {
                    title: "System RAM"
                    value: stateModel ? stateModel.ramPercent.toFixed(1) : "0"
                    unit: "%"
                    accentColor: "#00B4D8"
                    history: stateModel ? stateModel.getRamHistory() : []
                }

                MetricCard {
                    title: "GPU Load"
                    value: stateModel ? stateModel.gpuPercent.toFixed(1) : "0"
                    unit: "%"
                    accentColor: "#7C4DFF"
                    history: stateModel ? stateModel.getGpuHistory() : []
                }

                MetricCard {
                    title: "VRAM Used"
                    value: stateModel ? stateModel.vramMb.toFixed(0) : "0"
                    unit: "MB"
                    accentColor: "#FFB300"
                }

                MetricCard {
                    title: "Gateway Ping"
                    value: stateModel ? stateModel.pingMs.toString() : "0"
                    unit: "ms"
                    accentColor: "#00E676"
                }
            }

            // Model Residency Section
            Text {
                text: "MODEL RESIDENCY (RESOURCE GOVERNOR)"
                color: "#94A3B8"
                font.pixelSize: 12
                font.bold: true
            }

            Flow {
                width: parent.width
                spacing: 12

                Repeater {
                    model: stateModel ? stateModel.models : []
                    delegate: ModelStatus {
                        modelName: modelData.name || "Model"
                        status: modelData.status || "READY"
                        details: modelData.details || ""
                    }
                }
            }
        }
    }
}

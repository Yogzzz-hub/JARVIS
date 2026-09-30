import QtQuick
import "../components"

Item {
    id: root
    property var stateModel
    property var controller

    PageScroll {
        anchors.fill: parent

        PageHeader {
            width: parent.width
            icon: "system"
            title: "System"
            subtitle: "Live hardware load and which AI models are loaded right now."
            StatusBadge { status: root.stateModel ? root.stateModel.connectionStatus : "OFFLINE" }
            JButton { text: "SYSTEM REPORT"; variant: "ghost"; onClicked: if (root.controller) root.controller.sendCommand("system info") }
        }

        SectionLabel { text: "HARDWARE"; hint: "sampled every second" }
        CardGrid {
            id: metrics
            width: parent.width
            minCardWidth: 190
            MetricCard { width: metrics.cellWidth; title: "CPU load"; unit: "%"; accentColor: "#00E5FF"
                value: root.stateModel ? root.stateModel.cpuPercent.toFixed(0) : "0"
                history: root.stateModel ? root.stateModel.getCpuHistory() : [] }
            MetricCard { width: metrics.cellWidth; title: "Memory (RAM)"; unit: "%"; accentColor: "#00B4D8"
                value: root.stateModel ? root.stateModel.ramPercent.toFixed(0) : "0"
                history: root.stateModel ? root.stateModel.getRamHistory() : [] }
            MetricCard { width: metrics.cellWidth; title: "GPU load"; unit: "%"; accentColor: "#B388FF"
                value: root.stateModel ? root.stateModel.gpuPercent.toFixed(0) : "0"
                history: root.stateModel ? root.stateModel.getGpuHistory() : [] }
            MetricCard { width: metrics.cellWidth; title: "GPU memory"; unit: "MB"; accentColor: "#FFB300"
                value: root.stateModel ? root.stateModel.vramMb.toFixed(0) : "0" }
            MetricCard { width: metrics.cellWidth; title: "Gateway ping"; unit: "ms"; accentColor: "#00E676"
                value: root.stateModel ? root.stateModel.pingMs.toString() : "0" }
        }

        SectionLabel { text: "AI MODELS"; hint: "loaded on demand, unloaded when idle" }
        CardGrid {
            id: modelsGrid
            width: parent.width
            minCardWidth: 240
            Repeater {
                model: root.stateModel ? root.stateModel.models : []
                delegate: ModelStatus {
                    width: modelsGrid.cellWidth
                    modelName: modelData.name || "Model"
                    status: modelData.status || "READY"
                    details: modelData.details || ""
                }
            }
        }
    }
}

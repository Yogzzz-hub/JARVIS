import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import "components"
import "pages"
import "overlays"

Window {
    id: mainWindow
    width: 960
    height: 620
    minimumWidth: 800
    minimumHeight: 520
    title: "JARVIS EDGE v1.0"
    color: "#0A0D12"
    visible: true

    // Connections to global controller events
    Connections {
        target: uiController
        function onShowVoiceOverlayRequested() {
            voiceOverlay.visible = true;
            voiceOverlay.requestActivate();
        }
        function onHideVoiceOverlayRequested() {
            voiceOverlay.visible = false;
        }
        function onShowDashboardRequested() {
            mainWindow.visible = true;
            mainWindow.visibility = Window.Windowed;
            mainWindow.raise();
            mainWindow.requestActivate();
        }
        function onHideDashboardRequested() {
            mainWindow.visible = false;
        }
        function onShowToastRequested(title, message) {
            toast.title = title;
            toast.message = message;
            toast.showing = true;
        }
    }

    // Windows TitleBar & System Header
    Rectangle {
        id: header
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 46
        color: "#0F141E"
        border.color: "#1E293B"
        border.width: 1

        Row {
            anchors.left: parent.left
            anchors.leftMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            spacing: 10

            JarvisOrb {
                orbSize: 20
                assistantState: uiState ? uiState.assistantState : "IDLE"
                lowResourceMode: uiState ? uiState.lowResourceMode : false
                anchors.verticalCenter: parent.verticalCenter
            }

            Text {
                text: "JARVIS EDGE"
                color: "#F0F4F8"
                font.pixelSize: 13
                font.bold: true
                anchors.verticalCenter: parent.verticalCenter
            }

            Text {
                text: "v1.0"
                color: "#00E5FF"
                font.pixelSize: 10
                font.bold: true
                anchors.verticalCenter: parent.verticalCenter
            }
        }

        Row {
            anchors.right: parent.right
            anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            spacing: 12

            StatusBadge {
                status: uiState ? uiState.connectionStatus : "OFFLINE"
                anchors.verticalCenter: parent.verticalCenter
            }

            Text {
                id: clockText
                text: Qt.formatTime(new Date(), "hh:mm")
                color: "#94A3B8"
                font.pixelSize: 12
                font.bold: true
                anchors.verticalCenter: parent.verticalCenter

                Timer {
                    interval: 1000
                    running: true
                    repeat: true
                    onTriggered: clockText.text = Qt.formatTime(new Date(), "hh:mm")
                }
            }
        }
    }

    // Body: Sidebar + Pages Stack
    Row {
        anchors.top: header.bottom
        anchors.bottom: footer.top
        anchors.left: parent.left
        anchors.right: parent.right

        // Sidebar Navigation
        Rectangle {
            id: sidebar
            width: 180
            height: parent.height
            color: "#0D111A"
            border.color: "#1E293B"
            border.width: 1

            Column {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 4

                SidebarButton {
                    text: "Home"
                    iconSymbol: "◉"
                    selected: pageStack.currentIndex === 0
                    onClicked: pageStack.currentIndex = 0
                }
                SidebarButton {
                    text: "Activity"
                    iconSymbol: "☰"
                    selected: pageStack.currentIndex === 1
                    onClicked: pageStack.currentIndex = 1
                }
                SidebarButton {
                    text: "System"
                    iconSymbol: "⚙"
                    selected: pageStack.currentIndex === 2
                    onClicked: pageStack.currentIndex = 2
                }
                SidebarButton {
                    text: "Memory"
                    iconSymbol: "🧠"
                    selected: pageStack.currentIndex === 3
                    onClicked: pageStack.currentIndex = 3
                }
                SidebarButton {
                    text: "Workflows"
                    iconSymbol: "⚡"
                    selected: pageStack.currentIndex === 4
                    onClicked: pageStack.currentIndex = 4
                }
                SidebarButton {
                    text: "Devices"
                    iconSymbol: "💻"
                    selected: pageStack.currentIndex === 5
                    onClicked: pageStack.currentIndex = 5
                }
                SidebarButton {
                    text: "Integrations"
                    iconSymbol: "🔌"
                    selected: pageStack.currentIndex === 6
                    onClicked: pageStack.currentIndex = 6
                }
                SidebarButton {
                    text: "Settings"
                    iconSymbol: "🔧"
                    selected: pageStack.currentIndex === 7
                    onClicked: pageStack.currentIndex = 7
                }
                SidebarButton {
                    text: "Diagnostics"
                    iconSymbol: "🛡"
                    selected: pageStack.currentIndex === 8
                    onClicked: pageStack.currentIndex = 8
                }
            }
        }

        // Pages Container
        StackLayout {
            id: pageStack
            width: parent.width - sidebar.width
            height: parent.height
            currentIndex: 0

            HomePage {
                stateModel: uiState
                controller: uiController
            }
            ActivityPage {
                activityModel: uiActivityModel
                controller: uiController
            }
            SystemPage {
                stateModel: uiState
                controller: uiController
            }
            MemoryPage {
                controller: uiController
            }
            WorkflowsPage {
                controller: uiController
            }
            DevicesPage {
                stateModel: uiState
                controller: uiController
            }
            IntegrationsPage {
                stateModel: uiState
                controller: uiController
            }
            SettingsPage {
                controller: uiController
            }
            DiagnosticsPage {
                stateModel: uiState
                controller: uiController
            }
        }
    }

    // Bottom Telemetry Bar
    Rectangle {
        id: footer
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        height: 32
        color: "#0B0E14"
        border.color: "#1E293B"
        border.width: 1

        Row {
            anchors.left: parent.left
            anchors.leftMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            spacing: 16

            Text {
                text: "CPU " + (uiState ? uiState.cpuPercent.toFixed(0) : "0") + "%"
                color: "#94A3B8"
                font.pixelSize: 11
            }
            Text {
                text: "RAM " + (uiState ? uiState.ramPercent.toFixed(0) : "0") + "%"
                color: "#94A3B8"
                font.pixelSize: 11
            }
            Text {
                text: "GPU " + (uiState ? uiState.gpuPercent.toFixed(0) : "0") + "%"
                color: "#94A3B8"
                font.pixelSize: 11
            }
            Text {
                text: "Ping " + (uiState ? uiState.pingMs : 0) + "ms"
                color: "#00E5FF"
                font.pixelSize: 11
            }
        }

        Row {
            anchors.right: parent.right
            anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            spacing: 12

            Text {
                text: "● MIC"
                color: "#00E676"
                font.pixelSize: 10
                font.bold: true
            }
            Text {
                text: "● STT"
                color: "#00E676"
                font.pixelSize: 10
                font.bold: true
            }
            Text {
                text: "● OLLAMA"
                color: "#00E676"
                font.pixelSize: 10
                font.bold: true
            }
            Text {
                text: "○ GOOGLE"
                color: "#64748B"
                font.pixelSize: 10
                font.bold: true
            }
        }
    }

    // Overlays
    VoiceOverlay {
        id: voiceOverlay
        stateModel: uiState
        controller: uiController
        x: (Screen.width - width) / 2
        y: Screen.height - height - 80
    }

    ConfirmationOverlay {
        id: confirmOverlay
        stateModel: uiState
        controller: uiController
        x: (Screen.width - width) / 2
        y: (Screen.height - height) / 2
    }

    FloatingOrb {
        id: floatingOrb
        stateModel: uiState
        controller: uiController
        visible: uiSettings ? uiSettings.get("floating_orb_enabled") : false
        x: Screen.width - 80
        y: 120
    }

    Toast {
        id: toast
        anchors.bottom: footer.top
        anchors.right: parent.right
        anchors.margins: 16
    }
}

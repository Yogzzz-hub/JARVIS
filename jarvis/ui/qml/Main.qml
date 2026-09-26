import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import "components"
import "pages"
import "overlays"
import "components/palette.js" as Palette

Window {
    id: mainWindow
    width: 1240
    height: 760
    minimumWidth: 820
    minimumHeight: 560
    title: "JARVIS EDGE"
    color: "#070B13"
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

    // ------------------------------------------------------------------ backdrop
    readonly property string st: uiState ? uiState.assistantState : "IDLE"
    readonly property color tint: Palette.stateColor(st)

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#0B1220" }
            GradientStop { position: 0.55; color: "#070B13" }
            GradientStop { position: 1.0; color: "#05070C" }
        }
    }
    // faint grid
    Canvas {
        anchors.fill: parent
        opacity: 0.05
        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            ctx.strokeStyle = "#7FDBFF"
            ctx.lineWidth = 1
            for (var x = 0; x < width; x += 40) { ctx.beginPath(); ctx.moveTo(x + 0.5, 0); ctx.lineTo(x + 0.5, height); ctx.stroke() }
            for (var y = 0; y < height; y += 40) { ctx.beginPath(); ctx.moveTo(0, y + 0.5); ctx.lineTo(width, y + 0.5); ctx.stroke() }
        }
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
    }

    // ------------------------------------------------------------------ header
    Item {
        id: header
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 54

        Rectangle {
            anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
            height: 1
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: Qt.rgba(mainWindow.tint.r, mainWindow.tint.g, mainWindow.tint.b, 0.55) }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }

        Row {
            anchors.left: parent.left
            anchors.leftMargin: 18
            anchors.verticalCenter: parent.verticalCenter
            spacing: 12

            JarvisOrb {
                orbSize: 30
                assistantState: mainWindow.st
                lowResourceMode: uiState ? uiState.lowResourceMode : false
                level: uiState ? uiState.audioLevel : 0
                anchors.verticalCenter: parent.verticalCenter
            }
            Column {
                anchors.verticalCenter: parent.verticalCenter
                Text { text: "J.A.R.V.I.S"; color: "#F0F4F8"; font.pixelSize: 15; font.bold: true; font.letterSpacing: 4 }
                Text { text: "EDGE  \u00B7  LOCAL AI"; color: mainWindow.tint; font.pixelSize: 9; font.bold: true; font.letterSpacing: 2.5 }
            }
        }

        Row {
            anchors.right: parent.right
            anchors.rightMargin: 18
            anchors.verticalCenter: parent.verticalCenter
            spacing: 14

            StatusBadge {
                status: uiState ? uiState.connectionStatus : "OFFLINE"
                anchors.verticalCenter: parent.verticalCenter
            }
            Column {
                anchors.verticalCenter: parent.verticalCenter
                Text { id: clockText; text: Qt.formatTime(new Date(), "hh:mm"); color: "#E6F7FF"; font.pixelSize: 16; font.bold: true; anchors.right: parent.right }
                Text { id: dateText; text: Qt.formatDate(new Date(), "ddd, d MMM"); color: "#56708F"; font.pixelSize: 10; anchors.right: parent.right }
                Timer {
                    interval: 1000; running: true; repeat: true
                    onTriggered: { clockText.text = Qt.formatTime(new Date(), "hh:mm"); dateText.text = Qt.formatDate(new Date(), "ddd, d MMM") }
                }
            }
        }
    }

    // ------------------------------------------------------------------ body
    Item {
        anchors.top: header.bottom
        anchors.bottom: footer.top
        anchors.left: parent.left
        anchors.right: parent.right

        Item {
            id: sidebar
            readonly property bool compact: mainWindow.width < 1040
            width: compact ? 64 : 190
            height: parent.height
            Behavior on width { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

            Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Qt.rgba(1, 1, 1, 0.06) }

            Column {
                anchors.fill: parent
                anchors.margins: 10
                anchors.topMargin: 14
                spacing: 4
                Repeater {
                    model: [
                        { t: "Home", i: "\u25C9" }, { t: "Activity", i: "\u2630" }, { t: "System", i: "\u2699" },
                        { t: "Memory", i: "\u25C8" }, { t: "Workflows", i: "\u26A1" }, { t: "Devices", i: "\u25A3" },
                        { t: "Integrations", i: "\u2B21" }, { t: "Settings", i: "\u2692" }, { t: "Diagnostics", i: "\u2695" },
                        { t: "WhatsApp", i: "\u260E" }
                    ]
                    delegate: SidebarButton {
                        text: modelData.t
                        iconSymbol: modelData.i
                        compact: sidebar.compact
                        accent: mainWindow.tint
                        selected: pageStack.currentIndex === index
                        onClicked: pageStack.currentIndex = index
                    }
                }
            }
        }

        StackLayout {
            id: pageStack
            objectName: "pageStack"
            anchors.left: sidebar.right
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            currentIndex: 0
            onCurrentIndexChanged: pageFade.restart()

            NumberAnimation { id: pageFade; target: pageStack; property: "opacity"; from: 0.0; to: 1.0; duration: 160; easing.type: Easing.OutQuad }

            HomePage { stateModel: uiState; controller: uiController }
            ActivityPage { activityModel: uiActivityModel; controller: uiController }
            SystemPage { stateModel: uiState; controller: uiController }
            MemoryPage { controller: uiController }
            WorkflowsPage { controller: uiController }
            DevicesPage { stateModel: uiState; controller: uiController }
            IntegrationsPage { stateModel: uiState; controller: uiController }
            SettingsPage { controller: uiController }
            DiagnosticsPage { stateModel: uiState; controller: uiController }
            WhatsAppContactsPage { }
        }
    }

    // ------------------------------------------------------------------ footer (live status)
    Item {
        id: footer
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        height: 30

        Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: Qt.rgba(1, 1, 1, 0.06) }

        Row {
            anchors.left: parent.left
            anchors.leftMargin: 18
            anchors.verticalCenter: parent.verticalCenter
            spacing: 18
            Repeater {
                model: [
                    { k: "CPU", v: uiState ? uiState.cpuPercent.toFixed(0) + "%" : "-" },
                    { k: "RAM", v: uiState ? uiState.ramPercent.toFixed(0) + "%" : "-" },
                    { k: "GPU", v: uiState ? uiState.gpuPercent.toFixed(0) + "%" : "-" },
                    { k: "PING", v: uiState ? uiState.pingMs + " ms" : "-" }
                ]
                delegate: Row {
                    spacing: 5
                    Text { text: modelData.k; color: "#4B6584"; font.pixelSize: 10; font.bold: true; font.letterSpacing: 1 }
                    Text { text: modelData.v; color: "#A9BCD3"; font.pixelSize: 10; font.bold: true }
                }
            }
        }

        Row {
            anchors.right: parent.right
            anchors.rightMargin: 18
            anchors.verticalCenter: parent.verticalCenter
            spacing: 16
            Repeater {
                model: [
                    { k: "CORE", s: uiState ? (uiState.connectionStatus === "ONLINE" ? 1 : 0) : 0 },
                    { k: "VOICE", s: uiState ? (uiState.voiceStatus === "READY" ? 1 : (uiState.voiceStatus === "ERROR" ? 0 : 2)) : 2 },
                    { k: "AI", s: uiState ? (uiState.llmStatus === "ONLINE" ? 1 : (uiState.llmStatus === "OFFLINE" ? 0 : 2)) : 2 },
                    { k: "WHATSAPP", s: uiState ? (uiState.whatsappStatus === "CONNECTED" ? 1 : 2) : 2 }
                ]
                delegate: Row {
                    spacing: 6
                    readonly property color c: modelData.s === 1 ? "#00E676" : (modelData.s === 0 ? "#FF5252" : "#56708F")
                    Rectangle { width: 7; height: 7; radius: 4; color: c; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: modelData.k; color: c; font.pixelSize: 10; font.bold: true; font.letterSpacing: 1 }
                }
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
        visible: uiController ? uiController.getSetting("floating_orb_enabled") === true : false
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

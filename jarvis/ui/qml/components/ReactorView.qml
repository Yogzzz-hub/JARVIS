import QtQuick

// Shows the 3D reactor when the GPU path is available, otherwise the vector (2D) reactor.
// Qt Quick 3D is loaded lazily so a missing module or a software renderer never breaks the UI.
Item {
    id: root
    property string assistantState: "IDLE"
    property real level: 0.0
    property bool lowResourceMode: false
    property bool prefer3D: true
    property bool failed3D: false
    signal activated()

    readonly property bool gpu: GraphicsInfo.api !== GraphicsInfo.Software && GraphicsInfo.api !== GraphicsInfo.Unknown
    readonly property bool use3D: prefer3D && !lowResourceMode && !failed3D && (gpu || GraphicsInfo.api === GraphicsInfo.Unknown)
    readonly property bool showing3D: use3D && loader3d.status === Loader.Ready

    Loader {
        id: loader3d
        anchors.fill: parent
        active: root.use3D
        asynchronous: true
        source: "Reactor3D.qml"
        onStatusChanged: {
            if (status === Loader.Error) {
                console.warn("3D reactor unavailable, using the 2D reactor")
                root.failed3D = true
            }
        }
        onLoaded: {
            item.assistantState = Qt.binding(function() { return root.assistantState })
            item.level = Qt.binding(function() { return root.level })
            item.animate = Qt.binding(function() { return !root.lowResourceMode && root.visible })
            item.activated.connect(root.activated)
        }
    }

    JarvisOrb {
        anchors.centerIn: parent
        visible: !root.showing3D
        orbSize: Math.min(root.width, root.height) * 0.8
        assistantState: root.assistantState
        lowResourceMode: root.lowResourceMode
        level: root.level

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: root.activated()
        }
    }
}

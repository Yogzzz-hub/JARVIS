import QtQuick

// Pop-up notice in the corner (pairing code, task errors). Holographic like the rest of the app.
GlassPanel {
    id: root
    property string title: "Notification"
    property string message: ""
    property bool showing: false

    width: 360
    height: col.implicitHeight + 28
    activeBorder: true
    opacity: showing ? 1.0 : 0.0
    visible: opacity > 0.0
    y: showing ? 0 : 12
    Behavior on opacity { NumberAnimation { duration: 250 } }

    Timer { interval: 4500; running: root.showing; onTriggered: root.showing = false }

    Column {
        id: col
        x: 18; y: 14
        width: parent.width - 36
        spacing: 4
        Text { text: root.title; color: "#7FEFFF"; font.family: "Orbitron"; font.pixelSize: 11; font.letterSpacing: 2.2
               font.capitalization: Font.AllUppercase }
        Text { text: root.message; color: "#EAF8FF"; font.pixelSize: 16; wrapMode: Text.WordWrap; width: parent.width; maximumLineCount: 3; elide: Text.ElideRight }
    }
    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.showing = false }
}

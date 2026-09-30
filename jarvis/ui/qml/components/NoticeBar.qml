import QtQuick

// Result of the last action ("Replies to Naveen are off.", "Backend not running"). Stays until closed or replaced;
// success notices fade after a while.
Rectangle {
    id: root
    property string text: ""
    property bool error: false
    signal closed()

    readonly property color tone: error ? "#FF5252" : "#00E5FF"
    visible: text.length > 0
    implicitHeight: visible ? Math.max(40, msg.implicitHeight + 20) : 0
    radius: 10
    color: Qt.rgba(tone.r, tone.g, tone.b, 0.09)
    border.width: 1
    border.color: Qt.rgba(tone.r, tone.g, tone.b, 0.45)

    onTextChanged: if (text.length && !error) fade.restart()
    Timer { id: fade; interval: 9000; onTriggered: root.closed() }

    Rectangle { width: 3; radius: 2; color: root.tone; anchors { left: parent.left; top: parent.top; bottom: parent.bottom; margins: 8 } }
    Text {
        id: msg
        anchors { left: parent.left; right: closeBtn.left; verticalCenter: parent.verticalCenter; leftMargin: 20; rightMargin: 10 }
        text: root.text
        color: root.error ? "#FFB4B4" : "#DDF8FF"
        font.pixelSize: 12
        wrapMode: Text.WordWrap
    }
    Text {
        id: closeBtn
        anchors { right: parent.right; verticalCenter: parent.verticalCenter; rightMargin: 14 }
        text: "✕"
        color: closeMouse.containsMouse ? "#F0F4F8" : "#7C8DA5"
        font.pixelSize: 13
        MouseArea { id: closeMouse; anchors.fill: parent; anchors.margins: -8; hoverEnabled: true
            cursorShape: Qt.PointingHandCursor; onClicked: root.closed() }
    }
}

import QtQuick

// Single-line text field with a placeholder; Enter emits accepted().
Rectangle {
    id: root
    property alias text: input.text
    property string placeholder: ""
    property bool numeric: false
    signal accepted()

    implicitWidth: 180
    implicitHeight: 36
    radius: 9
    color: Qt.rgba(0.02, 0.06, 0.12, 0.75)
    border.width: 1
    border.color: input.activeFocus ? "#00E5FF" : (hover.containsMouse ? "#33475F" : "#243044")
    Behavior on border.color { ColorAnimation { duration: 120 } }

    TextInput {
        id: input
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        verticalAlignment: TextInput.AlignVCenter
        color: "#F0F4F8"
        font.pixelSize: 16
        font.weight: Font.Medium
        clip: true
        selectByMouse: true
        selectionColor: "#0091A8"
        inputMethodHints: root.numeric ? Qt.ImhFormattedNumbersOnly : Qt.ImhNone
        validator: root.numeric ? numberValidator : null
        onAccepted: root.accepted()
    }
    DoubleValidator { id: numberValidator; bottom: 0; top: 100000; decimals: 1 }
    Text {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        verticalAlignment: Text.AlignVCenter
        text: root.placeholder
        color: "#58708E"
        font.pixelSize: 15
        elide: Text.ElideRight
        visible: input.text.length === 0 && !input.activeFocus
    }
    MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton; cursorShape: Qt.IBeamCursor }
}

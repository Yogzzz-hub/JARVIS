import QtQuick

// Single-line text field with a placeholder; Enter emits accepted().
Rectangle {
    id: root
    property alias text: input.text
    property string placeholder: ""
    property bool numeric: false
    signal accepted()

    implicitWidth: 180
    implicitHeight: 34
    radius: 9
    color: "#0C121C"
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
        font.pixelSize: 13
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
        color: "#546178"
        font.pixelSize: 13
        elide: Text.ElideRight
        visible: input.text.length === 0 && !input.activeFocus
    }
    MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton; cursorShape: Qt.IBeamCursor }
}

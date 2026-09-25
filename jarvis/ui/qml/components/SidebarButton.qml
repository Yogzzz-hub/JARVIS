import QtQuick

Item {
    id: root
    property string text: "Button"
    property string iconSymbol: "●"
    property bool selected: false
    property bool compact: false
    property color accent: "#00E5FF"
    signal clicked()

    width: parent ? parent.width : 180
    height: 40

    Rectangle {
        anchors.fill: parent
        radius: 10
        color: root.selected ? Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.12)
                             : (mouseArea.containsMouse ? Qt.rgba(1, 1, 1, 0.05) : "transparent")
        Behavior on color { ColorAnimation { duration: 150 } }
    }
    // selection indicator
    Rectangle {
        width: 3
        height: root.selected ? 20 : 0
        radius: 2
        color: root.accent
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        Behavior on height { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
    }

    Row {
        anchors.fill: parent
        anchors.leftMargin: root.compact ? 0 : 14
        spacing: 12
        Text {
            width: root.compact ? root.width : 20
            horizontalAlignment: Text.AlignHCenter
            text: root.iconSymbol
            color: root.selected ? root.accent : "#7F93AD"
            font.pixelSize: 15
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            visible: !root.compact
            text: root.text
            color: root.selected ? "#F0F4F8" : (mouseArea.containsMouse ? "#E2E8F0" : "#8FA3BC")
            font.pixelSize: 13
            font.bold: root.selected
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}

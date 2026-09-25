import QtQuick

Rectangle {
    id: root
    property string text: "Button"
    property string iconSymbol: "●"
    property bool selected: false
    signal clicked()

    width: parent ? parent.width : 180
    height: 38
    radius: 6

    color: selected ? "#1A2230" : (mouseArea.containsMouse ? "#141A24" : "transparent")
    border.color: selected ? "#00E5FF" : "transparent"
    border.width: 1

    Row {
        anchors.fill: parent
        anchors.leftMargin: 12
        spacing: 12

        Text {
            text: root.iconSymbol
            color: root.selected ? "#00E5FF" : "#94A3B8"
            font.pixelSize: 14
            anchors.verticalCenter: parent.verticalCenter
        }

        Text {
            text: root.text
            color: root.selected ? "#F0F4F8" : (mouseArea.containsMouse ? "#E2E8F0" : "#94A3B8")
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

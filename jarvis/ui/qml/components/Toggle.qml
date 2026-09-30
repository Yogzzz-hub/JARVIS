import QtQuick

Rectangle {
    id: t
    property bool checked: false
    signal toggled(bool checked)
    width: 46; height: 26; radius: 13
    color: checked ? "#00BCD4" : "#1E293B"
    border.width: 1
    border.color: checked ? "#00E5FF" : "#33475F"
    Behavior on color { ColorAnimation { duration: 150 } }
    Rectangle {
        width: 20; height: 20; radius: 10; color: "#F0F4F8"
        anchors.verticalCenter: parent.verticalCenter
        x: t.checked ? parent.width - width - 3 : 3
        Behavior on x { NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }
    }
    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { t.checked = !t.checked; t.toggled(t.checked) } }
}

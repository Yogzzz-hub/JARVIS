import QtQuick

Item {
    id: root
    property var levels: []
    property color barColor: "#00E5FF"
    property bool active: true

    width: 240
    height: 36

    Row {
        anchors.centerIn: parent
        spacing: 3

        Repeater {
            model: 24
            delegate: Rectangle {
                id: bar
                width: 4
                property real targetHeight: {
                    if (!root.active || !root.levels || root.levels.length <= index) return 4;
                    var val = root.levels[index] || 0.0;
                    return Math.max(4, val * root.height);
                }
                height: targetHeight
                radius: 2
                color: root.barColor
                anchors.verticalCenter: parent.verticalCenter
                opacity: root.active ? 0.9 : 0.3

                Behavior on height {
                    NumberAnimation { duration: 60; easing.type: Easing.OutQuad }
                }
            }
        }
    }
}

import QtQuick
import QtQuick.Window
import "../components"

Window {
    id: root
    property var stateModel
    property var controller

    width: 48
    height: 48
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    color: "transparent"
    visible: false

    JarvisOrb {
        anchors.fill: parent
        orbSize: 46
        assistantState: stateModel ? stateModel.assistantState : "IDLE"
        lowResourceMode: stateModel ? stateModel.lowResourceMode : false
    }

    MouseArea {
        id: dragArea
        anchors.fill: parent
        cursorShape: Qt.SizeAllCursor
        drag.target: root
        acceptedButtons: Qt.LeftButton | Qt.RightButton

        property point clickPos: "0,0"

        onPressed: function(mouse) {
            clickPos = Qt.point(mouse.x, mouse.y);
        }

        onPositionChanged: function(mouse) {
            if (pressedButtons & Qt.LeftButton) {
                var delta = Qt.point(mouse.x - clickPos.x, mouse.y - clickPos.y);
                root.x += delta.x;
                root.y += delta.y;
            }
        }

        onDoubleClicked: {
            if (controller) controller.requestDashboard();
        }

        onClicked: function(mouse) {
            if (mouse.button === Qt.LeftButton) {
                if (controller) controller.startPTT();
            }
        }
    }
}

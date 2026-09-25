import QtQuick

Item {
    id: root
    property string text: "Button"
    property string iconSymbol: "●"      // kept for compat (ignored now)
    property string iconName: ""          // new: drives IconCanvas
    property bool selected: false
    property bool compact: false
    property color accent: "#00E5FF"
    signal clicked()

    width: parent ? parent.width : 180
    height: 44

    // ─── background ───
    Rectangle {
        anchors.fill: parent
        radius: 12
        color: root.selected
               ? Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.14)
               : (mouseArea.containsMouse ? Qt.rgba(1, 1, 1, 0.06) : "transparent")
        Behavior on color { ColorAnimation { duration: 180 } }
    }

    // ─── selection indicator (vertical pill) ───
    Rectangle {
        width: 3
        height: root.selected ? 22 : 0
        radius: 2
        color: root.accent
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        Behavior on height { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
        // glow
        Rectangle {
            anchors.centerIn: parent
            width: 7; height: parent.height + 4; radius: 4
            color: root.accent; opacity: 0.25
            visible: root.selected
        }
    }

    Row {
        anchors.fill: parent
        anchors.leftMargin: root.compact ? 0 : 16
        spacing: root.compact ? 0 : 14

        // ─── Icon (Canvas-drawn vector) ───
        Item {
            width: root.compact ? root.width : 22
            height: 22
            anchors.verticalCenter: parent.verticalCenter

            IconCanvas {
                anchors.centerIn: parent
                width: 18; height: 18
                icon: root.iconName
                iconColor: root.selected ? root.accent
                         : (mouseArea.containsMouse ? "#C8D6E5" : "#7F93AD")
                iconStroke: root.selected ? 1.9 : 1.5
                Behavior on iconColor { ColorAnimation { duration: 150 } }
            }

            // glow behind icon when selected
            Rectangle {
                anchors.centerIn: parent
                width: 28; height: 28; radius: 14
                color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.12)
                visible: root.selected
                z: -1
            }
        }

        // ─── Label ───
        Text {
            visible: !root.compact
            text: root.text
            color: root.selected ? "#F0F4F8"
                 : (mouseArea.containsMouse ? "#E2E8F0" : "#8FA3BC")
            font.pixelSize: 13
            font.bold: root.selected
            font.family: "Segoe UI"
            anchors.verticalCenter: parent.verticalCenter
            Behavior on color { ColorAnimation { duration: 150 } }
        }
    }

    // ─── Tooltip on hover (compact mode) ───
    Rectangle {
        id: tooltip
        visible: root.compact && mouseArea.containsMouse
        x: root.width + 8
        anchors.verticalCenter: parent.verticalCenter
        width: ttText.implicitWidth + 16
        height: 28
        radius: 8
        color: "#1A2332"
        border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.3)
        z: 100

        Text {
            id: ttText
            anchors.centerIn: parent
            text: root.text
            color: "#E2E8F0"
            font.pixelSize: 11
            font.bold: true
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

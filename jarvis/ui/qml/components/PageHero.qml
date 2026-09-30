import QtQuick

// The hologram band at the top of each page: live numbers / gauges on the left, a rotating holographic emblem with
// the page icon on the right. Children go into the stats Flow.
GlassPanel {
    id: hero
    property string icon: ""
    property string caption: ""
    property bool animate: true
    default property alias stats: statsFlow.data
    readonly property bool showEmblem: width > 720
    implicitHeight: Math.max(statsFlow.implicitHeight + 40, showEmblem ? 170 : 0)
    radius: 16

    // soft light from the emblem side
    Rectangle {
        anchors.fill: parent
        radius: parent.radius
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 0.75; color: Qt.rgba(0, 0.6, 1, 0.05) }
            GradientStop { position: 1.0; color: Qt.rgba(0, 0.7, 1, 0.14) }
        }
    }

    Flow {
        id: statsFlow
        x: 26
        y: 20
        width: hero.width - 52 - (hero.showEmblem ? 190 : 0)
        spacing: 34
    }

    // emblem
    Item {
        visible: hero.showEmblem
        width: 150; height: 150
        anchors.right: parent.right
        anchors.rightMargin: 26
        anchors.verticalCenter: parent.verticalCenter
        Rectangle { anchors.centerIn: parent; width: 150; height: 150; radius: 75; color: "transparent"
                    border.width: 1; border.color: Qt.rgba(0, 0.9, 1, 0.25) }
        Rectangle {
            anchors.centerIn: parent; width: 124; height: 124; radius: 62; color: "transparent"
            border.width: 2; border.color: Qt.rgba(0, 0.9, 1, 0.55)
            Rectangle { width: 10; height: 10; radius: 5; color: "#E6FDFF"; x: parent.width / 2 - 5; y: -5 }
            RotationAnimation on rotation { running: hero.animate && hero.visible; from: 0; to: 360; duration: 9000; loops: Animation.Infinite }
        }
        Repeater {   // dashed inner ring
            model: 24
            Rectangle {
                width: 2; height: 6; color: Qt.rgba(0, 0.9, 1, 0.6)
                x: 75 - 1; y: 20
                transform: Rotation { origin.x: 1; origin.y: 55; angle: index * 15 }
            }
        }
        Rectangle {
            anchors.centerIn: parent; width: 70; height: 70; radius: 35
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(0, 0.75, 1, 0.35) }
                GradientStop { position: 1.0; color: Qt.rgba(0, 0.3, 0.7, 0.20) }
            }
            border.width: 1; border.color: "#7FEFFF"
            IconCanvas { anchors.centerIn: parent; width: 30; height: 30; icon: hero.icon; iconColor: "#E6FDFF"; iconStroke: 1.8 }
            SequentialAnimation on scale { running: hero.animate && hero.visible; loops: Animation.Infinite
                NumberAnimation { to: 1.06; duration: 1400; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1.0; duration: 1400; easing.type: Easing.InOutSine } }
        }
        Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.bottom; anchors.topMargin: -4
               text: hero.caption; color: "#7FEFFF"; font.family: "Orbitron"; font.pixelSize: 9; font.letterSpacing: 2.5 }
    }
}

import QtQuick

// Every dashboard page: the same 28 px side / 24 px top padding, vertical scrolling when the window is short,
// and a slim scrollbar that shows only while there is more to see.
Flickable {
    id: flick
    property int sidePadding: width < 900 ? 20 : 28
    property alias spacing: body.spacing
    default property alias content: body.data
    readonly property int contentW: width - sidePadding * 2

    contentWidth: width
    contentHeight: body.implicitHeight + 24 + 36
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    flickableDirection: Flickable.VerticalFlick

    Column {
        id: body
        x: flick.sidePadding
        y: 24
        width: flick.contentW
        spacing: 20
    }

    Rectangle {
        id: bar
        visible: flick.contentHeight > flick.height + 2
        parent: flick
        anchors.right: parent.right
        anchors.rightMargin: 6
        width: 4
        radius: 2
        color: Qt.rgba(0.5, 0.85, 1.0, barMouse.containsMouse || flick.moving ? 0.45 : 0.18)
        height: Math.max(40, flick.height * flick.height / Math.max(1, flick.contentHeight))
        y: (flick.height - height) * (flick.contentY / Math.max(1, flick.contentHeight - flick.height))
        MouseArea {
            id: barMouse
            anchors.fill: parent
            anchors.margins: -6
            hoverEnabled: true
            drag.target: parent
            drag.axis: Drag.YAxis
            drag.minimumY: 0
            drag.maximumY: flick.height - bar.height
            onPositionChanged: if (drag.active) flick.contentY = bar.y / Math.max(1, flick.height - bar.height) * (flick.contentHeight - flick.height)
        }
    }
}

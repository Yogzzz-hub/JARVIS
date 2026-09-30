import QtQuick

// Page title + subtitle on the left, actions / badges on the right. When the window is too narrow for both on one
// line, the actions move under the title instead of overlapping it.
Item {
    id: root
    property string title: ""
    property string subtitle: ""
    property string icon: ""               // IconCanvas name shown in a glowing ring before the title
    default property alias actions: actionRow.data
    readonly property real iconW: icon.length ? 50 : 0
    readonly property bool stacked: iconW + titleText.implicitWidth + actionRow.implicitWidth + 40 > width
    readonly property real textWidth: (stacked ? width : width - actionRow.implicitWidth - 40) - iconW

    implicitHeight: (stacked ? titleCol.height + 14 + actionRow.implicitHeight : Math.max(titleCol.height, actionRow.implicitHeight)) + 18

    Item {
        visible: root.icon.length > 0
        width: 38; height: 38
        y: 0
        Rectangle { anchors.fill: parent; radius: 19; color: Qt.rgba(0, 0.9, 1, 0.08); border.width: 1; border.color: Qt.rgba(0, 0.9, 1, 0.55) }
        Rectangle { anchors.fill: parent; anchors.margins: -4; radius: 23; color: "transparent"; border.width: 1; border.color: Qt.rgba(0, 0.9, 1, 0.15) }
        IconCanvas { anchors.centerIn: parent; width: 18; height: 18; icon: root.icon; iconColor: "#7FEFFF"; iconStroke: 1.5 }
    }
    Column {
        id: titleCol
        x: root.iconW
        y: 0
        width: root.textWidth
        spacing: 5
        Text {
            id: titleText
            text: root.title
            color: "#EAF8FF"
            font.family: "Orbitron"
            font.pixelSize: 21
            font.weight: Font.DemiBold
            font.letterSpacing: 4
            font.capitalization: Font.AllUppercase
            style: Text.Raised
            styleColor: Qt.rgba(0, 0.9, 1, 0.25)
            elide: Text.ElideRight
            width: parent.width
        }
        Text {
            text: root.subtitle
            visible: text.length > 0
            color: "#8FB4D6"
            font.pixelSize: 15
            font.letterSpacing: 0.3
            wrapMode: Text.WordWrap
            width: parent.width
        }
    }
    Row {
        id: actionRow
        spacing: 10
        x: root.stacked ? root.iconW : root.width - implicitWidth
        y: root.stacked ? titleCol.height + 14 : Math.max(0, (titleText.implicitHeight - implicitHeight) / 2)
    }
    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "#2A3A52" }
            GradientStop { position: 0.7; color: "#1A2433" }
            GradientStop { position: 1.0; color: "transparent" }
        }
    }
}

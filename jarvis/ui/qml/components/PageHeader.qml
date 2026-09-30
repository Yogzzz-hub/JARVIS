import QtQuick

// Page title + subtitle on the left, actions / badges on the right. When the window is too narrow for both on one
// line, the actions move under the title instead of overlapping it.
Item {
    id: root
    property string title: ""
    property string subtitle: ""
    default property alias actions: actionRow.data
    readonly property bool stacked: titleText.implicitWidth + actionRow.implicitWidth + 40 > width
    readonly property real textWidth: stacked ? width : width - actionRow.implicitWidth - 40

    implicitHeight: (stacked ? titleCol.height + 14 + actionRow.implicitHeight : Math.max(titleCol.height, actionRow.implicitHeight)) + 18

    Column {
        id: titleCol
        x: 0
        y: 0
        width: root.textWidth
        spacing: 5
        Text {
            id: titleText
            text: root.title
            color: "#F0F4F8"
            font.pixelSize: 22
            font.bold: true
            font.letterSpacing: 0.4
            elide: Text.ElideRight
            width: parent.width
        }
        Text {
            text: root.subtitle
            visible: text.length > 0
            color: "#8193AB"
            font.pixelSize: 13
            wrapMode: Text.WordWrap
            width: parent.width
        }
    }
    Row {
        id: actionRow
        spacing: 10
        x: root.stacked ? 0 : root.width - implicitWidth
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

import QtQuick
import QtQuick.Layouts

// Card heading: the title takes the room it needs and elides only when the card is really narrow; the badge never
// overlaps it (it moves under the title instead).
Item {
    id: root
    property string title: ""
    property string status: ""
    property string statusText: status
    property color titleColor: "#F0F4F8"
    readonly property bool stacked: status.length > 0 && width < titleText.implicitWidth + badge.width + 14

    implicitHeight: stacked ? titleText.implicitHeight + 8 + badge.height : Math.max(titleText.implicitHeight, status.length ? badge.height : 0)

    Text {
        id: titleText
        text: root.title
        color: root.titleColor
        font.pixelSize: 14
        font.bold: true
        elide: Text.ElideRight
        width: root.stacked || !root.status.length ? root.width : root.width - badge.width - 14
        y: root.stacked ? 0 : (root.implicitHeight - implicitHeight) / 2
    }
    StatusBadge {
        id: badge
        visible: root.status.length > 0
        status: root.status
        text: root.statusText
        x: root.stacked ? 0 : root.width - width
        y: root.stacked ? titleText.implicitHeight + 8 : (root.implicitHeight - height) / 2
    }
}

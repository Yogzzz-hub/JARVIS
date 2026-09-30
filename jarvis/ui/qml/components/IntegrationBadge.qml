import QtQuick

Card {
    id: root
    property string integrationName: "Integration"
    property string status: "CONNECTED"
    property string desc: ""
    padding: 16
    spacing: 8
    CardTitle { width: parent.width; title: root.integrationName; status: root.status }
    Text { text: root.desc; visible: text.length > 0; color: "#8193AB"; font.pixelSize: 12; wrapMode: Text.WordWrap; width: parent.width }
}

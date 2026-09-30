import QtQuick

Card {
    id: root
    property string modelName: "Model"
    property string status: "READY"
    property string details: ""
    padding: 16
    spacing: 8
    CardTitle { width: parent.width; title: root.modelName; status: root.status }
    Text { text: root.details; visible: text.length > 0; color: "#8193AB"; font.pixelSize: 14; wrapMode: Text.WordWrap; width: parent.width }
}

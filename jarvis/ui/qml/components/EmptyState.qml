import QtQuick

Column {
    property string title: ""
    property string hint: ""
    spacing: 6
    Text { text: parent.title; color: "#94A3B8"; font.pixelSize: 14; font.bold: true; anchors.horizontalCenter: parent.horizontalCenter }
    Text { text: parent.hint; visible: text.length > 0; color: "#64748B"; font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter
           wrapMode: Text.WordWrap; width: Math.min(implicitWidth, 420); anchors.horizontalCenter: parent.horizontalCenter }
}

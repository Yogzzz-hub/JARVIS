import QtQuick

Row {
    property string text: ""
    property string hint: ""
    spacing: 10
    Rectangle { width: 3; height: 14; radius: 2; color: "#00E5FF"; anchors.verticalCenter: parent.verticalCenter }
    Text { text: parent.text; color: "#C9D6E6"; font.pixelSize: 12; font.bold: true; font.letterSpacing: 1.4
           anchors.verticalCenter: parent.verticalCenter }
    Text { text: parent.hint; visible: text.length > 0; color: "#64748B"; font.pixelSize: 11
           anchors.verticalCenter: parent.verticalCenter }
}

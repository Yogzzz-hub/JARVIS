import QtQuick

// A big glowing number with a label - used in the hologram header of each page.
Column {
    id: s
    property string value: "0"
    property string label: ""
    property string hint: ""
    property color tint: "#00E5FF"
    spacing: 2
    Text { text: s.value; color: "#EAF8FF"; font.family: "Rajdhani"; font.pixelSize: 40; font.weight: Font.Bold
           style: Text.Outline; styleColor: Qt.rgba(s.tint.r, s.tint.g, s.tint.b, 0.35) }
    Row {
        spacing: 7
        Rectangle { width: 6; height: 6; radius: 3; color: s.tint; anchors.verticalCenter: parent.verticalCenter }
        Text { text: s.label; color: "#BFEFFF"; font.family: "Orbitron"; font.pixelSize: 10; font.letterSpacing: 2.2
               font.capitalization: Font.AllUppercase }
    }
    Text { text: s.hint; visible: text.length > 0; color: "#6F8AA8"; font.pixelSize: 14; width: Math.min(implicitWidth, 260); elide: Text.ElideRight }
}

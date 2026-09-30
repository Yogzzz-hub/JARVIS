import QtQuick

Row {
    property string text: ""
    property string hint: ""
    spacing: 10
    Rectangle { width: 8; height: 8; rotation: 45; color: "transparent"; border.width: 1.5; border.color: "#00E5FF"
                anchors.verticalCenter: parent.verticalCenter }
    Text { text: parent.text; color: "#BFEFFF"; font.family: "Orbitron"; font.pixelSize: 11; font.weight: Font.DemiBold
           font.letterSpacing: 3; anchors.verticalCenter: parent.verticalCenter }
    Rectangle { width: 40; height: 1; anchors.verticalCenter: parent.verticalCenter
                gradient: Gradient { orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: "#5000E5FF" } GradientStop { position: 1; color: "transparent" } } }
    Text { text: parent.hint; visible: text.length > 0; color: "#6F8AA8"; font.pixelSize: 14
           anchors.verticalCenter: parent.verticalCenter }
}

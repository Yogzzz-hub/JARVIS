import QtQuick

Rectangle {
    id: root
    property color glowColor: "#00E5FF"
    property real blurRadius: 10
    property bool activeBorder: false

    color: "#121721"
    border.color: activeBorder ? glowColor : "#222D3E"
    border.width: 1
    radius: 8
    smooth: true
}

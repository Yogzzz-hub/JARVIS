import QtQuick

Card {
    id: root
    property string title: "METRIC"
    property string value: "0"
    property string unit: "%"
    property color accentColor: "#00E5FF"
    property var history: []
    padding: 16
    spacing: 6

    Text { text: root.title; color: "#8193AB"; font.pixelSize: 11; font.bold: true; font.letterSpacing: 1.1
           font.capitalization: Font.AllUppercase; elide: Text.ElideRight; width: parent.width }
    Row {
        spacing: 4
        Text { text: root.value; color: "#F0F4F8"; font.pixelSize: 26; font.bold: true }
        Text { text: root.unit; color: root.accentColor; font.pixelSize: 13; font.bold: true
               anchors.baseline: parent.children[0].baseline }
    }
    Item {
        width: parent.width
        height: 26
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Qt.rgba(1, 1, 1, 0.06) }
        Canvas {
            id: sparkline
            anchors.fill: parent
            visible: root.history && root.history.length > 1
            onPaint: {
                var ctx = getContext("2d");
                ctx.clearRect(0, 0, width, height);
                if (!root.history || root.history.length < 2) return;
                var step = width / (root.history.length - 1);
                ctx.beginPath();
                for (var i = 0; i < root.history.length; i++) {
                    var y = height - 2 - (Math.min(100, root.history[i] || 0) / 100.0) * (height - 4);
                    if (i === 0) ctx.moveTo(0, y); else ctx.lineTo(i * step, y);
                }
                ctx.strokeStyle = root.accentColor;
                ctx.lineWidth = 1.6;
                ctx.stroke();
                ctx.lineTo(width, height); ctx.lineTo(0, height); ctx.closePath();
                ctx.fillStyle = Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.10);
                ctx.fill();
            }
            Connections { target: root; function onHistoryChanged() { sparkline.requestPaint() } }
        }
    }
}

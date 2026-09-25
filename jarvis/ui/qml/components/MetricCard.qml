import QtQuick

GlassPanel {
    id: root
    property string title: "METRIC"
    property string value: "0"
    property string unit: "%"
    property color accentColor: "#00E5FF"
    property var history: []

    width: 160
    height: 90

    Column {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 4

        Text {
            text: root.title
            color: "#94A3B8"
            font.pixelSize: 11
            font.bold: true
            font.capitalization: Font.AllUppercase
        }

        Row {
            spacing: 2
            Text {
                text: root.value
                color: "#F0F4F8"
                font.pixelSize: 22
                font.bold: true
            }
            Text {
                text: root.unit
                color: root.accentColor
                font.pixelSize: 13
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 3
            }
        }

        // Mini sparkline using Canvas
        Canvas {
            id: sparkline
            width: parent.width
            height: 18
            visible: root.history && root.history.length > 1

            onPaint: {
                var ctx = getContext("2d");
                ctx.clearRect(0, 0, width, height);
                if (!root.history || root.history.length < 2) return;

                ctx.beginPath();
                ctx.strokeStyle = root.accentColor;
                ctx.lineWidth = 1.5;

                var step = width / (root.history.length - 1);
                for (var i = 0; i < root.history.length; i++) {
                    var val = root.history[i] || 0;
                    var y = height - (val / 100.0) * height;
                    if (i === 0) ctx.moveTo(0, y);
                    else ctx.lineTo(i * step, y);
                }
                ctx.stroke();
            }

            Connections {
                target: root
                function onHistoryChanged() { sparkline.requestPaint(); }
            }
        }
    }
}

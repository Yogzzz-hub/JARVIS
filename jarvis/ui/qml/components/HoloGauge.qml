import QtQuick
import QtQuick.Shapes

// Circular holographic gauge: tick ring, glowing value arc, big number in the middle, label under it.
Item {
    id: g
    property real value: 0            // 0..max
    property real max: 100
    property string text: Math.round(value) + ""
    property string unit: "%"
    property string label: ""
    property color tint: "#00E5FF"
    property bool animate: true
    readonly property real frac: Math.max(0, Math.min(1, max > 0 ? value / max : 0))
    property real shown: frac
    Behavior on shown { enabled: g.animate; NumberAnimation { duration: 600; easing.type: Easing.OutCubic } }
    onFracChanged: shown = frac

    implicitWidth: 132
    implicitHeight: 132 + 24

    readonly property real d: Math.min(width, height - 24)
    readonly property real r: d / 2 - 8

    Item {
        id: dial
        width: g.d; height: g.d
        anchors.horizontalCenter: parent.horizontalCenter

        // ticks
        Canvas {
            id: ticks
            anchors.fill: parent
            property real lit: g.shown
            onLitChanged: requestPaint()
            onPaint: {
                var ctx = getContext("2d");
                ctx.clearRect(0, 0, width, height);
                var c = width / 2, n = 40;
                for (var i = 0; i <= n; i++) {
                    var a = (135 + 270 * i / n) * Math.PI / 180;
                    var major = i % 5 === 0;
                    var r1 = c - 2, r2 = c - (major ? 9 : 6);
                    ctx.strokeStyle = i / n <= lit + 0.001 ? "rgba(127,239,255,0.9)" : "rgba(127,200,255,0.2)";
                    ctx.lineWidth = major ? 2 : 1;
                    ctx.beginPath();
                    ctx.moveTo(c + Math.cos(a) * r1, c + Math.sin(a) * r1);
                    ctx.lineTo(c + Math.cos(a) * r2, c + Math.sin(a) * r2);
                    ctx.stroke();
                }
            }
        }
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {   // track
                strokeColor: Qt.rgba(0.4, 0.8, 1, 0.14); strokeWidth: 6; fillColor: "transparent"; capStyle: ShapePath.RoundCap
                PathAngleArc { centerX: dial.width / 2; centerY: dial.height / 2; radiusX: g.r - 8; radiusY: g.r - 8; startAngle: 135; sweepAngle: 270 }
            }
            ShapePath {   // glow
                strokeColor: Qt.rgba(g.tint.r, g.tint.g, g.tint.b, 0.22); strokeWidth: 12; fillColor: "transparent"; capStyle: ShapePath.RoundCap
                PathAngleArc { centerX: dial.width / 2; centerY: dial.height / 2; radiusX: g.r - 8; radiusY: g.r - 8; startAngle: 135; sweepAngle: Math.max(0.1, 270 * g.shown) }
            }
            ShapePath {   // value
                strokeColor: g.tint; strokeWidth: 5; fillColor: "transparent"; capStyle: ShapePath.RoundCap
                PathAngleArc { centerX: dial.width / 2; centerY: dial.height / 2; radiusX: g.r - 8; radiusY: g.r - 8; startAngle: 135; sweepAngle: Math.max(0.1, 270 * g.shown) }
            }
        }
        Column {
            anchors.centerIn: parent
            spacing: -2
            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 2
                Text { text: g.text; color: "#EAF8FF"; font.family: "Rajdhani"; font.pixelSize: Math.max(18, g.d * 0.28); font.weight: Font.Bold }
                Text { text: g.unit; color: g.tint; font.pixelSize: Math.max(11, g.d * 0.1); font.bold: true; anchors.baseline: parent.children[0].baseline }
            }
        }
    }
    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        text: g.label
        color: "#9FC4E4"
        font.family: "Orbitron"
        font.pixelSize: 10
        font.letterSpacing: 2.2
        font.capitalization: Font.AllUppercase
    }
}

import QtQuick
import QtQuick.Shapes

// The scene behind every page: deep-blue night sky, a light beam from above, a glowing city skyline on the horizon,
// a reflective floor with a light ring, and slow drifting particles. Painted once per resize (cheap); only the
// particles and the beam shimmer animate, and not at all in low-resource mode.
Item {
    id: root
    property color tint: "#00E5FF"
    property bool animate: true
    clip: true

    // sky
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.00; color: "#040913" }
            GradientStop { position: 0.45; color: "#071427" }
            GradientStop { position: 0.72; color: "#0A1E38" }
            GradientStop { position: 0.80; color: "#06101F" }
            GradientStop { position: 1.00; color: "#03060C" }
        }
    }

    // central glow (the core light behind everything)
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeWidth: 0
            strokeColor: "transparent"
            fillGradient: RadialGradient {
                centerX: root.width / 2; centerY: root.height * 0.32
                focalX: centerX; focalY: centerY
                centerRadius: Math.max(root.width, root.height) * 0.55
                focalRadius: 0
                GradientStop { position: 0.0; color: Qt.rgba(0.0, 0.55, 1.0, 0.20) }
                GradientStop { position: 0.45; color: Qt.rgba(0.0, 0.40, 0.9, 0.07) }
                GradientStop { position: 1.0; color: "transparent" }
            }
            PathRectangle { x: 0; y: 0; width: root.width; height: root.height }
        }
    }

    // skyline + stars + floor, painted once per size
    Canvas {
        id: city
        anchors.fill: parent
        renderStrategy: Canvas.Cooperative
        property real horizon: height * 0.78
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            var ctx = getContext("2d");
            ctx.clearRect(0, 0, width, height);
            var seed = 7;
            function rnd() { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; }

            // stars
            for (var s = 0; s < 90; s++) {
                ctx.fillStyle = "rgba(170,210,255," + (0.15 + rnd() * 0.45) + ")";
                ctx.fillRect(rnd() * width, rnd() * horizon * 0.7, 1, 1);
            }

            // far skyline (hazy)
            var x = 0;
            ctx.fillStyle = "rgba(20,55,95,0.55)";
            while (x < width) {
                var w = 14 + rnd() * 34, h = 18 + rnd() * height * 0.10;
                ctx.fillRect(x, horizon - h, w, h);
                x += w + rnd() * 6;
            }
            // near skyline with spires and lit windows
            x = -10;
            while (x < width) {
                var bw = 18 + rnd() * 46;
                var tall = rnd() > 0.82;
                var bh = (tall ? 0.16 + rnd() * 0.16 : 0.05 + rnd() * 0.09) * height;
                var g = ctx.createLinearGradient(0, horizon - bh, 0, horizon);
                g.addColorStop(0, "rgba(14,32,58,0.95)");
                g.addColorStop(1, "rgba(6,14,28,0.98)");
                ctx.fillStyle = g;
                ctx.fillRect(x, horizon - bh, bw, bh);
                if (tall) {  // spire
                    ctx.beginPath();
                    ctx.moveTo(x + bw * 0.35, horizon - bh);
                    ctx.lineTo(x + bw * 0.5, horizon - bh - 22 - rnd() * 40);
                    ctx.lineTo(x + bw * 0.65, horizon - bh);
                    ctx.closePath();
                    ctx.fill();
                    ctx.fillStyle = "rgba(255,90,90,0.8)";
                    ctx.fillRect(x + bw * 0.5 - 1, horizon - bh - 24, 2, 2);
                }
                // windows
                for (var wy = horizon - bh + 6; wy < horizon - 4; wy += 6) {
                    for (var wx = x + 4; wx < x + bw - 4; wx += 5) {
                        if (rnd() > 0.72) {
                            var warm = rnd() > 0.8;
                            ctx.fillStyle = warm ? "rgba(255,200,120," + (0.35 + rnd() * 0.5) + ")"
                                                 : "rgba(120,200,255," + (0.3 + rnd() * 0.55) + ")";
                            ctx.fillRect(wx, wy, 2, 2);
                        }
                    }
                }
                x += bw + rnd() * 10;
            }
            // horizon haze
            var hz = ctx.createLinearGradient(0, horizon - 40, 0, horizon + 6);
            hz.addColorStop(0, "rgba(0,160,255,0)");
            hz.addColorStop(1, "rgba(0,170,255,0.20)");
            ctx.fillStyle = hz;
            ctx.fillRect(0, horizon - 40, width, 46);

            // floor
            var fl = ctx.createLinearGradient(0, horizon, 0, height);
            fl.addColorStop(0, "rgba(10,30,58,0.95)");
            fl.addColorStop(1, "rgba(3,7,14,1)");
            ctx.fillStyle = fl;
            ctx.fillRect(0, horizon, width, height - horizon);
            // floor light lines (perspective)
            ctx.strokeStyle = "rgba(0,200,255,0.10)";
            ctx.lineWidth = 1;
            for (var i = -12; i <= 12; i++) {
                ctx.beginPath();
                ctx.moveTo(width / 2 + i * 20, horizon);
                ctx.lineTo(width / 2 + i * 160, height);
                ctx.stroke();
            }
            ctx.strokeStyle = "rgba(0,229,255,0.55)";
            ctx.beginPath(); ctx.moveTo(0, horizon + 0.5); ctx.lineTo(width, horizon + 0.5); ctx.stroke();
        }
    }

    // light beam from above
    Rectangle {
        id: beam
        width: Math.max(90, root.width * 0.09)
        height: root.height * 0.8
        x: (root.width - width) / 2
        y: 0
        opacity: 0.55
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 0.5; color: Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.10) }
            GradientStop { position: 1.0; color: "transparent" }
        }
        SequentialAnimation on opacity {
            running: root.animate
            loops: Animation.Infinite
            NumberAnimation { to: 0.8; duration: 2600; easing.type: Easing.InOutSine }
            NumberAnimation { to: 0.45; duration: 2600; easing.type: Easing.InOutSine }
        }
    }

    // drifting particles
    Repeater {
        model: root.animate ? 26 : 0
        Rectangle {
            id: p
            readonly property real seedX: (index * 137.508) % 1
            width: index % 5 === 0 ? 3 : 2
            height: width
            radius: width / 2
            color: Qt.rgba(0.55, 0.9, 1.0, 0.6)
            x: root.width * (0.1 + 0.8 * seedX)
            y: root.height
            opacity: 0
            SequentialAnimation {
                running: root.animate
                loops: Animation.Infinite
                PauseAnimation { duration: (index * 733) % 9000 }
                ParallelAnimation {
                    NumberAnimation { target: p; property: "y"; from: root.height * 0.9; to: root.height * 0.15; duration: 14000 + (index * 911) % 9000 }
                    SequentialAnimation {
                        NumberAnimation { target: p; property: "opacity"; to: 0.7; duration: 2500 }
                        PauseAnimation { duration: 8000 }
                        NumberAnimation { target: p; property: "opacity"; to: 0; duration: 3500 }
                    }
                }
            }
        }
    }

    // faint HUD grid
    Canvas {
        anchors.fill: parent
        opacity: 0.035
        onPaint: {
            var ctx = getContext("2d");
            ctx.clearRect(0, 0, width, height);
            ctx.strokeStyle = "#7FDBFF";
            for (var x = 0; x < width; x += 48) { ctx.beginPath(); ctx.moveTo(x + 0.5, 0); ctx.lineTo(x + 0.5, height); ctx.stroke() }
            for (var y = 0; y < height; y += 48) { ctx.beginPath(); ctx.moveTo(0, y + 0.5); ctx.lineTo(width, y + 0.5); ctx.stroke() }
        }
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
    }

    // vignette
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: Qt.rgba(0, 0, 0, 0.55) }
            GradientStop { position: 0.18; color: "transparent" }
            GradientStop { position: 0.82; color: "transparent" }
            GradientStop { position: 1.0; color: Qt.rgba(0, 0, 0, 0.55) }
        }
    }
}

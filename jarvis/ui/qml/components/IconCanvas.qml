import QtQuick

// Draws crisp vector icons using Canvas 2D — replaces inconsistent Unicode glyphs.
Canvas {
    id: root
    property string icon: "home"
    property color iconColor: "#7F93AD"
    property real iconStroke: 1.6

    width: 20; height: 20
    antialiasing: true
    renderStrategy: Canvas.Cooperative

    onPaint: {
        var ctx = getContext("2d")
        ctx.clearRect(0, 0, width, height)
        ctx.strokeStyle = iconColor
        ctx.fillStyle = iconColor
        ctx.lineWidth = iconStroke
        ctx.lineCap = "round"
        ctx.lineJoin = "round"

        var w = width, h = height
        var cx = w / 2, cy = h / 2

        switch (icon) {

        case "home":
            ctx.beginPath()
            ctx.moveTo(w * 0.15, h * 0.45)
            ctx.lineTo(cx, h * 0.12)
            ctx.lineTo(w * 0.85, h * 0.45)
            ctx.stroke()
            ctx.beginPath()
            ctx.moveTo(w * 0.25, h * 0.42)
            ctx.lineTo(w * 0.25, h * 0.85)
            ctx.lineTo(w * 0.75, h * 0.85)
            ctx.lineTo(w * 0.75, h * 0.42)
            ctx.stroke()
            // door
            ctx.beginPath()
            ctx.moveTo(w * 0.42, h * 0.85)
            ctx.lineTo(w * 0.42, h * 0.62)
            ctx.lineTo(w * 0.58, h * 0.62)
            ctx.lineTo(w * 0.58, h * 0.85)
            ctx.stroke()
            break

        case "activity":
            ctx.beginPath()
            ctx.moveTo(w * 0.08, cy)
            ctx.lineTo(w * 0.22, cy)
            ctx.lineTo(w * 0.32, h * 0.2)
            ctx.lineTo(w * 0.45, h * 0.8)
            ctx.lineTo(w * 0.55, h * 0.35)
            ctx.lineTo(w * 0.68, h * 0.65)
            ctx.lineTo(w * 0.78, cy)
            ctx.lineTo(w * 0.92, cy)
            ctx.stroke()
            break

        case "system":
            // gear
            var r1 = w * 0.22, r2 = w * 0.32, teeth = 6
            ctx.beginPath()
            for (var i = 0; i < teeth; i++) {
                var a1 = (Math.PI * 2 / teeth) * i - Math.PI / 2
                var a2 = a1 + Math.PI * 2 / teeth * 0.35
                var a3 = a1 + Math.PI * 2 / teeth * 0.5
                var a4 = a1 + Math.PI * 2 / teeth * 0.85
                if (i === 0) ctx.moveTo(cx + r2 * Math.cos(a1), cy + r2 * Math.sin(a1))
                ctx.lineTo(cx + r2 * Math.cos(a2), cy + r2 * Math.sin(a2))
                ctx.lineTo(cx + r1 * Math.cos(a3), cy + r1 * Math.sin(a3))
                ctx.lineTo(cx + r1 * Math.cos(a4), cy + r1 * Math.sin(a4))
                var nextA = (Math.PI * 2 / teeth) * (i + 1) - Math.PI / 2
                ctx.lineTo(cx + r2 * Math.cos(nextA), cy + r2 * Math.sin(nextA))
            }
            ctx.closePath()
            ctx.stroke()
            ctx.beginPath()
            ctx.arc(cx, cy, w * 0.1, 0, Math.PI * 2)
            ctx.stroke()
            break

        case "memory":
            // brain / chip
            ctx.strokeRect(w * 0.22, h * 0.22, w * 0.56, h * 0.56)
            ctx.beginPath()
            ctx.arc(cx, cy, w * 0.14, 0, Math.PI * 2)
            ctx.stroke()
            // pins
            var pins = [0.35, 0.5, 0.65]
            for (var p = 0; p < pins.length; p++) {
                var pp = pins[p]
                ctx.beginPath(); ctx.moveTo(w * pp, h * 0.22); ctx.lineTo(w * pp, h * 0.08); ctx.stroke()
                ctx.beginPath(); ctx.moveTo(w * pp, h * 0.78); ctx.lineTo(w * pp, h * 0.92); ctx.stroke()
                ctx.beginPath(); ctx.moveTo(w * 0.22, h * pp); ctx.lineTo(w * 0.08, h * pp); ctx.stroke()
                ctx.beginPath(); ctx.moveTo(w * 0.78, h * pp); ctx.lineTo(w * 0.92, h * pp); ctx.stroke()
            }
            break

        case "workflows":
            // lightning bolt
            ctx.beginPath()
            ctx.moveTo(w * 0.55, h * 0.08)
            ctx.lineTo(w * 0.25, h * 0.52)
            ctx.lineTo(w * 0.48, h * 0.52)
            ctx.lineTo(w * 0.42, h * 0.92)
            ctx.lineTo(w * 0.75, h * 0.42)
            ctx.lineTo(w * 0.52, h * 0.42)
            ctx.closePath()
            ctx.stroke()
            break

        case "devices":
            // laptop
            ctx.strokeRect(w * 0.18, h * 0.2, w * 0.64, h * 0.45)
            ctx.beginPath()
            ctx.moveTo(w * 0.1, h * 0.75)
            ctx.lineTo(w * 0.18, h * 0.65)
            ctx.lineTo(w * 0.82, h * 0.65)
            ctx.lineTo(w * 0.9, h * 0.75)
            ctx.closePath()
            ctx.stroke()
            break

        case "integrations":
            // puzzle piece / link
            ctx.beginPath()
            ctx.arc(w * 0.35, cy, w * 0.18, Math.PI * 0.5, -Math.PI * 0.5)
            ctx.stroke()
            ctx.beginPath()
            ctx.arc(w * 0.65, cy, w * 0.18, -Math.PI * 0.5, Math.PI * 0.5)
            ctx.stroke()
            ctx.beginPath()
            ctx.moveTo(w * 0.35, h * 0.32)
            ctx.lineTo(w * 0.65, h * 0.32)
            ctx.stroke()
            ctx.beginPath()
            ctx.moveTo(w * 0.35, h * 0.68)
            ctx.lineTo(w * 0.65, h * 0.68)
            ctx.stroke()
            break

        case "settings":
            // sliders
            var rows = [0.28, 0.5, 0.72]
            var knobs = [0.62, 0.38, 0.55]
            for (var s = 0; s < 3; s++) {
                var ry = h * rows[s]
                ctx.beginPath(); ctx.moveTo(w * 0.15, ry); ctx.lineTo(w * 0.85, ry); ctx.stroke()
                ctx.beginPath(); ctx.arc(w * knobs[s], ry, w * 0.06, 0, Math.PI * 2); ctx.fill()
            }
            break

        case "diagnostics":
            // heartbeat/pulse in a shield
            ctx.beginPath()
            ctx.moveTo(cx, h * 0.1)
            ctx.bezierCurveTo(w * 0.82, h * 0.1, w * 0.85, h * 0.45, cx, h * 0.9)
            ctx.bezierCurveTo(w * 0.15, h * 0.45, w * 0.18, h * 0.1, cx, h * 0.1)
            ctx.closePath()
            ctx.stroke()
            // heartbeat inside
            ctx.beginPath()
            ctx.moveTo(w * 0.28, cy)
            ctx.lineTo(w * 0.38, cy)
            ctx.lineTo(w * 0.44, h * 0.32)
            ctx.lineTo(w * 0.54, h * 0.68)
            ctx.lineTo(w * 0.6, cy)
            ctx.lineTo(w * 0.72, cy)
            ctx.stroke()
            break

        // Quick-action chip icons
        case "screenshot":
            ctx.strokeRect(w * 0.15, h * 0.15, w * 0.7, h * 0.7)
            // viewfinder cross
            ctx.beginPath(); ctx.moveTo(cx, h * 0.3); ctx.lineTo(cx, h * 0.7); ctx.stroke()
            ctx.beginPath(); ctx.moveTo(w * 0.3, cy); ctx.lineTo(w * 0.7, cy); ctx.stroke()
            ctx.beginPath(); ctx.arc(cx, cy, w * 0.12, 0, Math.PI * 2); ctx.stroke()
            break

        case "weather":
            // sun with cloud
            ctx.beginPath(); ctx.arc(w * 0.38, h * 0.35, w * 0.16, 0, Math.PI * 2); ctx.stroke()
            // rays
            for (var ri = 0; ri < 8; ri++) {
                var ra = (Math.PI * 2 / 8) * ri
                ctx.beginPath()
                ctx.moveTo(w * 0.38 + w * 0.22 * Math.cos(ra), h * 0.35 + w * 0.22 * Math.sin(ra))
                ctx.lineTo(w * 0.38 + w * 0.28 * Math.cos(ra), h * 0.35 + w * 0.28 * Math.sin(ra))
                ctx.stroke()
            }
            // cloud
            ctx.beginPath()
            ctx.arc(w * 0.52, h * 0.62, w * 0.13, Math.PI, 0)
            ctx.arc(w * 0.68, h * 0.62, w * 0.1, Math.PI * 1.2, Math.PI * 0.1)
            ctx.lineTo(w * 0.38, h * 0.72)
            ctx.arc(w * 0.42, h * 0.62, w * 0.1, Math.PI * 0.8, Math.PI * 1.5)
            ctx.stroke()
            break

        case "whatsapp":
            // chat bubble
            ctx.beginPath()
            ctx.arc(cx, h * 0.42, w * 0.32, 0, Math.PI * 2)
            ctx.stroke()
            ctx.beginPath()
            ctx.moveTo(w * 0.3, h * 0.68)
            ctx.lineTo(w * 0.22, h * 0.88)
            ctx.lineTo(w * 0.46, h * 0.72)
            ctx.stroke()
            break

        case "reminders":
            // bell
            ctx.beginPath()
            ctx.moveTo(w * 0.25, h * 0.62)
            ctx.bezierCurveTo(w * 0.25, h * 0.25, w * 0.75, h * 0.25, w * 0.75, h * 0.62)
            ctx.lineTo(w * 0.82, h * 0.72)
            ctx.lineTo(w * 0.18, h * 0.72)
            ctx.closePath()
            ctx.stroke()
            // clapper
            ctx.beginPath(); ctx.arc(cx, h * 0.8, w * 0.08, 0, Math.PI); ctx.stroke()
            // top
            ctx.beginPath(); ctx.moveTo(cx, h * 0.12); ctx.lineTo(cx, h * 0.22); ctx.stroke()
            break

        case "phone":
            ctx.strokeRect(w * 0.3, h * 0.1, w * 0.4, h * 0.8)
            ctx.beginPath(); ctx.moveTo(w * 0.3, h * 0.22); ctx.lineTo(w * 0.7, h * 0.22); ctx.stroke()
            ctx.beginPath(); ctx.moveTo(w * 0.3, h * 0.75); ctx.lineTo(w * 0.7, h * 0.75); ctx.stroke()
            ctx.beginPath(); ctx.arc(cx, h * 0.84, w * 0.04, 0, Math.PI * 2); ctx.fill()
            break

        case "chrome":
            ctx.beginPath(); ctx.arc(cx, cy, w * 0.36, 0, Math.PI * 2); ctx.stroke()
            ctx.beginPath(); ctx.arc(cx, cy, w * 0.14, 0, Math.PI * 2); ctx.stroke()
            // spokes
            ctx.beginPath(); ctx.moveTo(cx + w * 0.14, cy); ctx.lineTo(w * 0.86, cy); ctx.stroke()
            ctx.beginPath()
            ctx.moveTo(cx - w * 0.07, cy - w * 0.12)
            ctx.lineTo(cx - w * 0.18, cy - w * 0.31)
            ctx.stroke()
            ctx.beginPath()
            ctx.moveTo(cx - w * 0.07, cy + w * 0.12)
            ctx.lineTo(cx - w * 0.18, cy + w * 0.31)
            ctx.stroke()
            break

        case "cog":
            // simple gear for "System" chip
            var gr = w * 0.18, gr2 = w * 0.3, gt = 8
            ctx.beginPath()
            for (var gi = 0; gi < gt; gi++) {
                var ga1 = (Math.PI * 2 / gt) * gi - Math.PI / 2
                var ga2 = ga1 + Math.PI * 2 / gt * 0.3
                var ga3 = ga1 + Math.PI * 2 / gt * 0.5
                var ga4 = ga1 + Math.PI * 2 / gt * 0.8
                if (gi === 0) ctx.moveTo(cx + gr2 * Math.cos(ga1), cy + gr2 * Math.sin(ga1))
                ctx.lineTo(cx + gr2 * Math.cos(ga2), cy + gr2 * Math.sin(ga2))
                ctx.lineTo(cx + gr * Math.cos(ga3), cy + gr * Math.sin(ga3))
                ctx.lineTo(cx + gr * Math.cos(ga4), cy + gr * Math.sin(ga4))
                var gna = (Math.PI * 2 / gt) * (gi + 1) - Math.PI / 2
                ctx.lineTo(cx + gr2 * Math.cos(gna), cy + gr2 * Math.sin(gna))
            }
            ctx.closePath()
            ctx.stroke()
            ctx.beginPath(); ctx.arc(cx, cy, w * 0.08, 0, Math.PI * 2); ctx.stroke()
            break

        default:
            ctx.beginPath()
            ctx.arc(cx, cy, w * 0.3, 0, Math.PI * 2)
            ctx.stroke()
            break
        }
    }

    onIconColorChanged: requestPaint()
    onIconChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
}

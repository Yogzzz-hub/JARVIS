import QtQuick
import "palette.js" as Palette

// The holographic "model" around the reactor: tilted orbit rings with travelling lights, a light column and a
// glowing pedestal with the JARVIS wordmark - like a hologram standing on its platform. Purely decorative and
// drawn behind / around whatever reactor sits in the middle (3D or 2D).
Item {
    id: root
    property string assistantState: "IDLE"
    property bool animate: true
    property real core: Math.min(width, height * 0.78)       // reactor diameter this stage is built around
    readonly property color tint: Palette.stateColor(assistantState)
    readonly property real speed: Palette.isBusy(assistantState) ? 2.6 : (assistantState === "SPEAKING" ? 1.8 : 1.0)
    property real phase: 0

    FrameAnimation {
        running: root.animate && root.visible
        onTriggered: root.phase += Math.min(frameTime, 0.05) * root.speed
    }

    readonly property real cx: width / 2
    readonly property real cy: core / 2 + (height - core) * 0.18

    // pedestal
    Item {
        id: pedestal
        width: root.core * 0.95
        height: root.core * 0.26
        x: root.cx - width / 2
        y: root.cy + root.core * 0.40
        Repeater {
            model: 3
            Rectangle {
                readonly property real f: 1 - index * 0.16
                width: pedestal.width * f
                height: pedestal.height * 0.62 * f
                radius: height / 2
                x: (pedestal.width - width) / 2
                y: index * pedestal.height * 0.10
                color: index === 0 ? Qt.rgba(0.02, 0.07, 0.14, 0.85) : "transparent"
                border.width: index === 1 ? 2 : 1
                border.color: Qt.rgba(root.tint.r, root.tint.g, root.tint.b, index === 1 ? 0.85 : 0.45)
            }
        }
        // front face
        Rectangle {
            width: pedestal.width * 0.74
            height: pedestal.height * 0.42
            x: (pedestal.width - width) / 2
            y: pedestal.height * 0.36
            radius: 8
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(0.08, 0.16, 0.28, 0.95) }
                GradientStop { position: 1.0; color: Qt.rgba(0.02, 0.05, 0.10, 0.98) }
            }
            border.width: 1
            border.color: Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.35)
            Column {
                anchors.centerIn: parent
                spacing: 2
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: "JARVIS"; color: "#EAF8FF"; font.family: "Orbitron"
                       font.pixelSize: Math.max(12, root.core * 0.055); font.letterSpacing: root.core * 0.022; font.weight: Font.Medium }
                Text { anchors.horizontalCenter: parent.horizontalCenter; text: "YOUR LOCAL AI COMPANION"; color: root.tint
                       font.pixelSize: Math.max(9, root.core * 0.022); font.letterSpacing: 2.4; font.weight: Font.DemiBold; opacity: 0.85 }
            }
            // light strip
            Rectangle { anchors.bottom: parent.bottom; anchors.horizontalCenter: parent.horizontalCenter; width: parent.width * 0.6; height: 2
                        gradient: Gradient { orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: "transparent" }
                            GradientStop { position: 0.5; color: root.tint }
                            GradientStop { position: 1; color: "transparent" } } }
        }
    }

    // light column from the pedestal up into the core
    Rectangle {
        width: root.core * 0.10
        height: root.core * 0.42
        x: root.cx - width / 2
        y: root.cy + root.core * 0.02
        opacity: 0.65
        gradient: Gradient {
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 1.0; color: Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.35) }
        }
    }

    // orbit rings (tilted ellipses) with travelling lights
    Repeater {
        model: [ { r: 0.62, tilt: -16, squash: 0.30, dir: 1.0, w: 1.6 },
                 { r: 0.56, tilt: 22,  squash: 0.22, dir: -1.3, w: 1.2 },
                 { r: 0.68, tilt: 4,   squash: 0.12, dir: 0.7, w: 1.0 } ]
        Item {
            id: orbit
            readonly property real rad: root.core * modelData.r
            width: rad * 2
            height: rad * 2
            x: root.cx - rad
            y: root.cy - rad
            transform: [ Scale { origin.x: orbit.rad; origin.y: orbit.rad; yScale: modelData.squash },
                         Rotation { origin.x: orbit.rad; origin.y: orbit.rad; angle: modelData.tilt } ]
            Rectangle {
                anchors.fill: parent
                radius: width / 2
                color: "transparent"
                border.width: modelData.w / modelData.squash * 0.5
                border.color: Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.45)
            }
        }
    }

    // lights riding the orbits (computed in window space so they stay round)
    Repeater {
        model: [ { r: 0.62, tilt: -16, squash: 0.30, dir: 1.0 }, { r: 0.56, tilt: 22, squash: 0.22, dir: -1.3 },
                 { r: 0.68, tilt: 4, squash: 0.12, dir: 0.7 } ]
        Rectangle {
            readonly property real a: root.phase * modelData.dir + index * 2.1
            readonly property real orbitR: root.core * modelData.r
            readonly property real lx: Math.cos(a) * orbitR
            readonly property real ly: Math.sin(a) * orbitR * modelData.squash
            readonly property real t: modelData.tilt * Math.PI / 180
            width: 9; height: 9; radius: 4.5
            x: root.cx + lx * Math.cos(t) - ly * Math.sin(t) - width / 2
            y: root.cy + lx * Math.sin(t) + ly * Math.cos(t) - height / 2
            color: "#E6FDFF"
            Rectangle { anchors.centerIn: parent; width: 26; height: 26; radius: 13; color: Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.22) }
        }
    }
}

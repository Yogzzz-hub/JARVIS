import QtQuick

pragma Singleton

QtObject {
    id: root

    // Palette: Deep graphite / near-black + cyan / electric blue + teal
    readonly property color background: "#0A0D12"
    readonly property color surface: "#121721"
    readonly property color surfaceLight: "#1A2230"
    readonly property color border: "#222D3E"
    readonly property color borderGlow: "#304058"

    readonly property color primary: "#00E5FF"        // Electric Cyan
    readonly property color primaryHover: "#33EBFF"
    readonly property color primaryDim: "#00E5FF33"
    readonly property color accent: "#00A3FF"         // Electric Blue
    readonly property color teal: "#00B4D8"           // Subtle Teal

    readonly property color textPrimary: "#F0F4F8"
    readonly property color textSecondary: "#94A3B8"
    readonly property color textMuted: "#64748B"

    readonly property color success: "#00E676"        // Soft Green
    readonly property color warning: "#FFB300"        // Amber
    readonly property color error: "#FF5252"          // Soft Red

    // Typography
    readonly property string fontFamily: "Segoe UI, Inter, Roboto, sans-serif"
    readonly property int fontSizeSmall: 11
    readonly property int fontSizeNormal: 13
    readonly property int fontSizeMedium: 15
    readonly property int fontSizeLarge: 18
    readonly property int fontSizeTitle: 22

    // Geometry
    readonly property int radiusSmall: 4
    readonly property int radiusMedium: 8
    readonly property int radiusLarge: 12
    readonly property int radiusOrb: 999
}

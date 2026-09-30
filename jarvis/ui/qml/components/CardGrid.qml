import QtQuick

// Responsive grid: as many columns of at least ``minCardWidth`` as fit, all the same width (no ragged gaps).
Flow {
    id: grid
    property int minCardWidth: 260
    property int maxColumns: 6
    spacing: 14
    readonly property int columns: Math.max(1, Math.min(maxColumns, Math.floor((width + spacing) / (minCardWidth + spacing))))
    readonly property real cellWidth: Math.floor((width - (columns - 1) * spacing) / columns)
}

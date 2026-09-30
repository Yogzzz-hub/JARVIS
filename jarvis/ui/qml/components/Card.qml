import QtQuick

// GlassPanel with consistent inner padding; children go in a Column that sizes the card.
GlassPanel {
    id: card
    property int padding: 18
    property alias spacing: body.spacing
    default property alias content: body.data
    implicitHeight: body.implicitHeight + padding * 2
    radius: 14
    Column {
        id: body
        x: card.padding
        y: card.padding
        width: card.width - card.padding * 2
        spacing: 10
    }
}

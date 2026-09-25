import QtQuick
import QtQuick.Window
import "../components"

Window {
    id: root
    property var stateModel
    property var controller

    width: 460
    height: 240
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Dialog
    color: "transparent"
    visible: stateModel && stateModel.confirmationTicket && Object.keys(stateModel.confirmationTicket).length > 0

    ConfirmationCard {
        anchors.centerIn: parent
        ticketId: (stateModel && stateModel.confirmationTicket) ? (stateModel.confirmationTicket.ticket_id || "TKT-100") : ""
        title: (stateModel && stateModel.confirmationTicket) ? (stateModel.confirmationTicket.title || "SECURITY CONFIRMATION") : "SECURITY CONFIRMATION"
        target: (stateModel && stateModel.confirmationTicket) ? (stateModel.confirmationTicket.target || "Execute Tool") : "Execute Tool"
        details: (stateModel && stateModel.confirmationTicket) ? (stateModel.confirmationTicket.details || "Confirm system state change.") : "Confirm system state change."

        onConfirmed: function(id) {
            if (controller) controller.confirmTicket(id);
            root.visible = false;
        }

        onRejected: function(id) {
            if (controller) controller.rejectTicket(id);
            root.visible = false;
        }
    }
}

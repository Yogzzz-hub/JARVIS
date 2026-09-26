import QtQuick
import QtQuick.Dialogs
import "../components"

// Dashboard -> WhatsApp -> Contacts: per-contact style profiles and time-boxed auto-reply.
// Group chats never appear here and can never be auto-replied.
Item {
    id: root
    property var client: (typeof uiWhatsApp !== "undefined") ? uiWhatsApp : null
    property string selectedId: ""
    property var detail: client ? client.selected : ({})
    property var contact: detail && detail.contact ? detail.contact : null
    property var summary: detail && detail.summary ? detail.summary : null
    property var profile: detail && detail.profile ? detail.profile : null

    readonly property color fg: "#F0F4F8"
    readonly property color dim: "#94A3B8"
    readonly property color accent: "#00E5FF"
    readonly property color danger: "#FF5252"
    readonly property color ok: "#00E676"

    function timeText(ts) {
        if (!ts) return "-";
        var d = new Date(ts * 1000);
        return d.toLocaleTimeString(Qt.locale(), "hh:mm AP");
    }
    function selectContact(cid) {
        selectedId = cid;
        if (client) client.select(cid);
    }

    Component.onCompleted: if (client) client.refresh()
    Timer { interval: 15000; repeat: true; running: root.visible && root.client !== null; onTriggered: root.client.refresh() }

    component JButton: Rectangle {
        id: btn
        property string label: ""
        property color tone: "#00E5FF"
        property bool enabledButton: true
        signal clicked()
        width: Math.max(74, lbl.implicitWidth + 22)
        height: 28
        radius: 6
        color: hover.containsMouse && enabledButton ? Qt.rgba(tone.r, tone.g, tone.b, 0.22) : Qt.rgba(tone.r, tone.g, tone.b, 0.10)
        border.color: tone
        border.width: 1
        opacity: enabledButton ? 1.0 : 0.4
        Text { id: lbl; anchors.centerIn: parent; text: btn.label; color: btn.tone; font.pixelSize: 11; font.bold: true }
        MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
            onClicked: if (btn.enabledButton) btn.clicked() }
    }

    component JInput: Rectangle {
        property alias text: input.text
        property string placeholder: ""
        width: 160; height: 28; radius: 6
        color: "#0F1623"; border.color: input.activeFocus ? "#00E5FF" : "#243044"; border.width: 1
        TextInput { id: input; anchors.fill: parent; anchors.margins: 7; color: "#F0F4F8"; font.pixelSize: 12; clip: true
            selectByMouse: true }
        Text { anchors.fill: parent; anchors.margins: 7; text: parent.placeholder; color: "#546178"; font.pixelSize: 12
            visible: input.text.length === 0 && !input.activeFocus }
    }

    FileDialog {
        id: exportDialog
        title: "Choose a WhatsApp chat export (.txt)"
        nameFilters: ["WhatsApp export (*.txt)", "All files (*)"]
        onAccepted: if (root.client && root.selectedId) root.client.importChatFile(root.selectedId, selectedFile.toString(),
                                                                                   contact ? contact.display_name : "", ownerName.text)
    }

    Column {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 12

        // ------------------------------------------------------------ header
        Row {
            width: parent.width
            spacing: 10
            Text { text: "WHATSAPP · CONTACTS"; color: root.fg; font.pixelSize: 18; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
            StatusBadge { status: "BUSY"; text: "GROUPS: BLOCKED"; anchors.verticalCenter: parent.verticalCenter }
            StatusBadge { status: root.client && root.client.encryption === "keyring" ? "READY" : "WAITING"
                text: root.client && root.client.encryption === "keyring" ? "ENCRYPTED" : "NOT ENCRYPTED"; anchors.verticalCenter: parent.verticalCenter }
            Item { width: 12; height: 1 }
            JInput { id: newContact; width: 150; placeholder: "number or name" }
            JButton { label: "ADD CONTACT"; onClicked: if (root.client && newContact.text) { root.client.addContact(newContact.text, ""); newContact.text = "" } }
            JInput { id: everyoneMinutes; width: 56; text: "60" }
            JButton { label: "EVERYONE (MIN)"; tone: "#FFB300"
                onClicked: if (root.client) root.client.enableEveryone(parseFloat(everyoneMinutes.text) || 60) }
            JButton { label: "STOP ALL AUTO-REPLY"; tone: root.danger; onClicked: if (root.client) root.client.stopAll() }
        }
        Text { width: parent.width; text: root.client ? root.client.status : "Backend not connected"; color: root.dim; font.pixelSize: 12; elide: Text.ElideRight }
        Rectangle { width: parent.width; height: 1; color: "#222D3E" }

        Row {
            width: parent.width
            height: parent.height - 220
            spacing: 14

            // -------------------------------------------------------- contact list
            ListView {
                id: list
                width: parent.width * 0.36
                height: parent.height
                clip: true
                spacing: 8
                model: root.client ? root.client.contacts : []
                delegate: GlassPanel {
                    width: list.width
                    height: 74
                    activeBorder: modelData.contact_id === root.selectedId
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.selectContact(modelData.contact_id) }
                    Column {
                        anchors.fill: parent; anchors.margins: 10; spacing: 4
                        Row {
                            spacing: 6
                            Text { text: modelData.display_name; color: root.fg; font.pixelSize: 14; font.bold: true }
                            StatusBadge { status: modelData.auto_reply === "ON" ? "ACTIVE" : (modelData.reply_mode === "OFF" ? "OFFLINE" : "WAITING")
                                text: modelData.auto_reply === "ON" ? "AUTO until " + root.timeText(modelData.auto_reply_expiry) : modelData.reply_mode }
                        }
                        Text { text: modelData.profile_status + " · " + modelData.samples + " samples · " + modelData.language_style
                               color: root.dim; font.pixelSize: 11; elide: Text.ElideRight; width: parent.width }
                        Text { text: modelData.last_incoming ? ("Last: " + modelData.last_incoming) : "No messages yet"
                               color: "#64748B"; font.pixelSize: 11; elide: Text.ElideRight; width: parent.width }
                    }
                }
            }

            // -------------------------------------------------------- contact detail
            Flickable {
                width: parent.width * 0.64 - 14
                height: parent.height
                contentHeight: detailCol.implicitHeight
                clip: true
                visible: root.contact !== null

                Column {
                    id: detailCol
                    width: parent.width
                    spacing: 10

                    GlassPanel {
                        width: parent.width
                        height: 138
                        Column {
                            anchors.fill: parent; anchors.margins: 12; spacing: 4
                            Text { text: root.contact ? root.contact.display_name : ""; color: root.fg; font.pixelSize: 16; font.bold: true }
                            Text { text: "WhatsApp ID: " + (root.contact ? root.contact.contact_id : ""); color: root.dim; font.pixelSize: 11 }
                            Text { text: "Profile confidence: " + (root.contact ? root.contact.confidence : 0) + " · messages analyzed: "
                                         + (root.summary ? root.summary.messages_analyzed : 0) + " · version " + (root.contact ? root.contact.profile_version : 0)
                                         + " · updated " + (root.profile ? root.timeText(root.profile.updated_at) : "-")
                                   color: root.dim; font.pixelSize: 11 }
                            Text { text: root.summary ? ("Language: " + root.summary.language + " · Tone: " + root.summary.tone
                                                         + " · Length: " + root.summary.typical_length + " · Emoji: " + root.summary.emoji)
                                                      : "No style profile yet - import a chat export or build from WhatsApp history."
                                   color: root.fg; font.pixelSize: 12; wrapMode: Text.WordWrap; width: parent.width }
                            Rectangle {  // language distribution bar
                                width: parent.width; height: 6; radius: 3; color: "#1E293B"; visible: root.profile !== null
                                Rectangle { width: parent.width * (root.profile ? root.profile.tanglish_ratio : 0); height: parent.height; radius: 3; color: "#B388FF" }
                            }
                            Text { text: "AUTO REPLY: " + (root.contact ? root.contact.auto_reply : "OFF") + " · MODE: " + (root.contact ? root.contact.reply_mode : "OFF")
                                         + (root.contact && root.contact.auto_reply_expiry ? " · EXPIRES: " + root.timeText(root.contact.auto_reply_expiry) : "")
                                         + " · GROUP: N/A - groups blocked"
                                   color: root.contact && root.contact.auto_reply === "ON" ? root.ok : root.dim; font.pixelSize: 12; font.bold: true }
                        }
                    }

                    // modes
                    Row {
                        spacing: 8
                        JButton { label: "OFF"; tone: root.danger; onClicked: root.client.setMode(root.selectedId, "OFF", 0) }
                        JButton { label: "SUGGEST"; onClicked: root.client.setMode(root.selectedId, "SUGGEST_ONLY", 0) }
                        JButton { label: "ASK"; onClicked: root.client.setMode(root.selectedId, "ASK_BEFORE_SEND", 0) }
                        JInput { id: autoMinutes; width: 56; text: "45" }
                        JButton { label: "AUTO FOR (MIN)"; tone: root.ok
                            onClicked: root.client.setMode(root.selectedId, "AUTO_REPLY_UNTIL", parseFloat(autoMinutes.text) || 45) }
                        JButton { label: "STOP"; tone: root.danger; onClicked: root.client.stop(root.selectedId) }
                    }

                    // profile actions
                    Row {
                        spacing: 8
                        JInput { id: ownerName; width: 130; placeholder: "your name in export" }
                        JButton { label: "IMPORT CHAT"; onClicked: exportDialog.open() }
                        JButton { label: "FROM WHATSAPP HISTORY"; onClicked: root.client.importFromHistory(root.selectedId, root.contact.display_name) }
                        JButton { label: "REFRESH PROFILE"; onClicked: root.client.rebuild(root.selectedId) }
                        JButton { label: "DELETE PROFILE"; tone: root.danger; onClicked: root.client.clearProfile(root.selectedId) }
                    }

                    // preview + feedback
                    GlassPanel {
                        width: parent.width
                        height: previewCol.implicitHeight + 24
                        Column {
                            id: previewCol
                            anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 12
                            spacing: 6
                            Row {
                                spacing: 8
                                Text { text: "STYLE PREVIEW"; color: root.accent; font.pixelSize: 12; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                                JButton { label: "PREVIEW STYLE"; onClicked: root.client.previewStyle(root.selectedId) }
                            }
                            Text { visible: !!(root.client && root.client.preview.summary); width: parent.width; wrapMode: Text.WordWrap
                                   color: root.fg; font.pixelSize: 12
                                   text: root.client && root.client.preview.summary
                                         ? ("They: " + root.client.preview.sample_incoming + "\nYou (preview): " + (root.client.preview.example_reply || "(model offline)"))
                                         : "" }
                            Flow {
                                width: parent.width; spacing: 6
                                visible: !!(root.client && root.client.preview.summary)
                                Repeater {
                                    model: [["Looks right", "looks_right"], ["Too formal", "too_formal"], ["Too casual", "too_casual"],
                                            ["More English", "more_english"], ["More Tanglish", "more_tanglish"], ["Shorter", "shorter"], ["Longer", "longer"]]
                                    delegate: JButton { label: modelData[0]; tone: "#B388FF"; onClicked: root.client.feedback(root.selectedId, modelData[1]) }
                                }
                            }
                        }
                    }

                    // test reply (never sends)
                    GlassPanel {
                        width: parent.width
                        height: testCol.implicitHeight + 24
                        Column {
                            id: testCol
                            anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 12
                            spacing: 6
                            Row {
                                spacing: 8
                                Text { text: "TEST REPLY (NOT SENT)"; color: root.accent; font.pixelSize: 12; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                                JInput { id: testInput; width: 260; placeholder: "dei tomorrow varuviya?" }
                                JButton { label: "TEST"; onClicked: root.client.testReply(root.selectedId, testInput.text || "dei tomorrow varuviya?") }
                            }
                            Text { width: parent.width; wrapMode: Text.WordWrap; color: root.fg; font.pixelSize: 12
                                   visible: !!(root.client && root.client.testResult.incoming)
                                   text: root.client && root.client.testResult.incoming
                                         ? ("Reply: " + (root.client.testResult.reply || "(model offline)") + "\nLanguage: " + root.client.testResult.target_language
                                            + " · Would auto-send: " + (root.client.testResult.would_auto_send ? "yes" : "no - needs review")
                                            + (root.client.testResult.quality && root.client.testResult.quality.reasons.length
                                               ? "\nWhy: " + root.client.testResult.quality.reasons.join("; ") : ""))
                                         : "" }
                        }
                    }

                    // history
                    Row {
                        spacing: 8
                        Text { text: "HISTORY"; color: root.accent; font.pixelSize: 12; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                        JButton { label: "VIEW HISTORY"; onClicked: root.client.loadHistory(root.selectedId) }
                    }
                    Repeater {
                        model: root.client ? root.client.history : []
                        delegate: GlassPanel {
                            width: detailCol.width
                            height: 64
                            Column {
                                anchors.fill: parent; anchors.margins: 8; spacing: 2
                                Text { text: root.timeText(modelData.created_at) + " · " + modelData.status + (modelData.reason ? " · " + modelData.reason : "")
                                       color: modelData.status === "VERIFIED" ? root.ok : (modelData.status === "UNCERTAIN" || modelData.status === "FAILED" ? root.danger : root.dim)
                                       font.pixelSize: 11; elide: Text.ElideRight; width: parent.width }
                                Text { text: "They: " + modelData.incoming; color: root.dim; font.pixelSize: 11; elide: Text.ElideRight; width: parent.width }
                                Row {
                                    spacing: 6
                                    Text { text: "You: " + (modelData.text || "-"); color: root.fg; font.pixelSize: 11; elide: Text.ElideRight; width: Math.max(80, detailCol.width - 380) }
                                    JButton { label: "SEND"; tone: root.ok; height: 20
                                        visible: ["SUGGESTED", "AWAITING_APPROVAL", "NEEDS_USER_REVIEW"].indexOf(modelData.status) >= 0
                                        onClicked: root.client.approve(modelData.id, "", false) }
                                    JButton { label: "GOOD EXAMPLE + SEND"; tone: "#B388FF"; height: 20
                                        visible: ["SUGGESTED", "AWAITING_APPROVAL", "NEEDS_USER_REVIEW"].indexOf(modelData.status) >= 0
                                        onClicked: root.client.approve(modelData.id, "", true) }
                                    JButton { label: "DISCARD"; tone: root.danger; height: 20
                                        visible: ["SUGGESTED", "AWAITING_APPROVAL", "NEEDS_USER_REVIEW"].indexOf(modelData.status) >= 0
                                        onClicked: root.client.reject(modelData.id) }
                                }
                            }
                        }
                    }
                }
            }
            Text { visible: root.contact === null; text: "Select a contact, or add one by number."; color: root.dim; font.pixelSize: 13 }
        }

        // ------------------------------------------------------------ live activity
        Text { text: "LIVE ACTIVITY"; color: root.accent; font.pixelSize: 12; font.bold: true }
        ListView {
            width: parent.width
            height: 120
            clip: true
            model: root.client ? root.client.activity : []
            delegate: Text {
                text: root.timeText(modelData.ts) + "  " + modelData.stage + " — " + modelData.display_name + (modelData.detail ? "  (" + modelData.detail + ")" : "")
                color: modelData.stage === "NOT SENT" || modelData.stage === "UNCERTAIN" ? root.danger
                       : (modelData.stage === "Verified" ? root.ok : root.dim)
                font.pixelSize: 11
            }
        }
    }
}

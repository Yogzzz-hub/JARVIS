import QtQuick
import QtQuick.Dialogs
import "../components"

// Dashboard -> WhatsApp: time-boxed auto-reply (everyone or one person, optionally with your own away message),
// per-contact style profiles, drafts waiting for your OK, and what the agent is doing right now.
// Group chats never appear here and can never be auto-replied.
Item {
    id: root
    property var client: (typeof uiWhatsApp !== "undefined") ? uiWhatsApp : null
    property string selectedId: ""
    property var detail: client ? client.selected : ({})
    property var contact: detail && detail.contact ? detail.contact : null
    property var summary: detail && detail.summary ? detail.summary : null
    property var profile: detail && detail.profile ? detail.profile : null
    readonly property bool busy: client ? client.busy : false
    readonly property bool wide: width >= 1080

    readonly property color fg: "#F0F4F8"
    readonly property color dim: "#8193AB"
    readonly property color faint: "#64748B"
    readonly property color accent: "#00E5FF"
    readonly property color danger: "#FF5252"
    readonly property color ok: "#00E676"

    function timeText(ts) {
        if (!ts) return "-";
        return new Date(ts * 1000).toLocaleTimeString(Qt.locale(), "h:mm AP");
    }
    function selectContact(cid) {
        selectedId = cid;
        if (client) { client.select(cid); client.loadHistory(cid) }
    }
    function modeLabel(m) {
        return m === "SUGGEST_ONLY" ? "SUGGEST" : m === "ASK_BEFORE_SEND" ? "ASK FIRST" : m === "AUTO_REPLY_UNTIL" ? "AUTO" : "OFF"
    }

    Component.onCompleted: if (client) client.refresh()
    onVisibleChanged: if (visible && client) client.refresh()
    Timer { interval: 15000; repeat: true; running: root.visible && root.client !== null; onTriggered: root.client.refresh() }

    FileDialog {
        id: exportDialog
        title: "Choose a WhatsApp chat export (.txt)"
        nameFilters: ["WhatsApp export (*.txt)", "All files (*)"]
        onAccepted: if (root.client && root.selectedId) root.client.importChatFile(root.selectedId, selectedFile.toString(),
                                                                                   root.contact ? root.contact.display_name : "", ownerName.text)
    }

    component ModeButton: Rectangle {
        id: mb
        property string text: ""
        property bool active: false
        property color tone: "#00E5FF"
        signal clicked()
        width: Math.max(88, t.implicitWidth + 28); height: 34; radius: 9
        color: active ? Qt.rgba(tone.r, tone.g, tone.b, 0.22) : (m.containsMouse ? Qt.rgba(1, 1, 1, 0.06) : "transparent")
        border.width: 1
        border.color: active ? tone : "#2A3A52"
        Text { id: t; anchors.centerIn: parent; text: mb.text; color: mb.active ? mb.tone : "#B8C6D8"; font.pixelSize: 14; font.bold: true }
        MouseArea { id: m; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: mb.clicked() }
    }

    PageScroll {
        id: page
        anchors.fill: parent
        spacing: 16

        PageHeader {
            width: parent.width
            icon: "whatsapp"
            title: "WhatsApp"
            subtitle: root.client ? (root.client.status || "Loading...") : "JARVIS backend not connected"
            StatusBadge { status: "BUSY"; text: "GROUPS BLOCKED" }
            StatusBadge { status: root.client && root.client.encryption === "keyring" ? "READY" : "WAITING"
                          text: root.client && root.client.encryption === "keyring" ? "ENCRYPTED" : "NOT ENCRYPTED" }
        }

        NoticeBar {
            width: parent.width
            text: root.client ? root.client.notice : ""
            error: root.client ? root.client.noticeError : false
            onClosed: if (root.client) root.client.clearNotice()
        }

        // ---------------------------------------------------------------- auto-reply for everyone
        Card {
            width: parent.width
            spacing: 12
            Text { text: "Auto-reply to everyone"; color: root.fg; font.pixelSize: 17; font.bold: true }
            Text {
                width: parent.width; wrapMode: Text.WordWrap; color: root.dim; font.pixelSize: 14
                text: "Direct chats only, for a set time. Type what to tell people (sent once to each person), or leave it "
                      + "empty and JARVIS drafts replies in your style."
            }
            Flow {
                width: parent.width
                spacing: 10
                JInput { id: everyoneMinutes; width: 90; text: "60"; numeric: true; placeholder: "minutes" }
                Text { text: "minutes"; color: root.dim; font.pixelSize: 14; height: 34; verticalAlignment: Text.AlignVCenter }
                JInput { id: everyoneNote; width: Math.min(360, page.contentW - 460); placeholder: "Message (optional): I'm in a meeting" }
                JButton { text: "TURN ON"; variant: "warning"; busy: root.busy
                          onClicked: if (root.client) root.client.enableEveryoneWithNote(parseFloat(everyoneMinutes.text) || 60, everyoneNote.text) }
                JButton { text: "STOP ALL"; variant: "danger"; onClicked: if (root.client) root.client.stopAll() }
            }
        }

        // ---------------------------------------------------------------- contacts + detail
        Item {
            id: split
            width: parent.width
            height: root.wide ? Math.max(listCol.implicitHeight, detailCol.implicitHeight) : listCol.implicitHeight + 16 + detailCol.implicitHeight
            readonly property real listW: root.wide ? Math.round(width * 0.34) : width

            Column {
                id: listCol
                width: split.listW
                spacing: 10

                SectionLabel { text: "CONTACTS"; hint: root.client ? root.client.contacts.length + " people" : "" }
                Item {
                    width: parent.width
                    height: 34
                    JInput { id: newContact; anchors.left: parent.left; anchors.right: addBtn.left; anchors.rightMargin: 8
                             placeholder: "Add by number or name"; onAccepted: addBtn.clicked() }
                    JButton { id: addBtn; text: "ADD"; anchors.right: parent.right; enabledButton: newContact.text.trim().length > 0
                              onClicked: if (root.client) { root.client.addContact(newContact.text, ""); newContact.text = "" } }
                }
                Repeater {
                    model: root.client ? root.client.contacts : []
                    delegate: GlassPanel {
                        width: listCol.width
                        height: cCol.implicitHeight + 26
                        radius: 12
                        activeBorder: modelData.contact_id === root.selectedId
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.selectContact(modelData.contact_id) }
                        Column {
                            id: cCol
                            x: 14; y: 13
                            width: parent.width - 28
                            spacing: 5
                            CardTitle {
                                width: parent.width
                                title: modelData.display_name
                                status: modelData.auto_reply === "ON" ? "ACTIVE" : (modelData.reply_mode === "OFF" ? "OFFLINE" : "WAITING")
                                statusText: modelData.auto_reply === "ON" ? "AUTO · " + root.timeText(modelData.auto_reply_expiry)
                                                                          : root.modeLabel(modelData.reply_mode)
                            }
                            Text { text: (modelData.profile_status === "NO PROFILE" ? "Style not learned yet" : modelData.profile_status + " · "
                                          + modelData.samples + " messages · " + modelData.language_style)
                                   color: root.dim; font.pixelSize: 13; elide: Text.ElideRight; width: parent.width }
                            Text { text: modelData.last_incoming ? "“" + modelData.last_incoming + "”" : "No messages yet"
                                   color: root.faint; font.pixelSize: 13; elide: Text.ElideRight; width: parent.width }
                        }
                    }
                }
                EmptyState { width: parent.width; visible: !root.client || root.client.contacts.length === 0
                             title: "No contacts yet"; hint: "People who message you appear here, or add one above." }
            }

            Column {
                id: detailCol
                x: root.wide ? split.listW + 18 : 0
                y: root.wide ? 0 : listCol.implicitHeight + 16
                width: root.wide ? split.width - split.listW - 18 : split.width
                spacing: 14

                EmptyState {
                    width: parent.width
                    visible: root.contact === null
                    topPadding: 60
                    title: "Select a contact"
                    hint: "Choose how JARVIS answers them, teach it your style, and approve drafts."
                }

                // profile
                Card {
                    width: parent.width
                    visible: root.contact !== null
                    spacing: 8
                    CardTitle {
                        width: parent.width
                        title: root.contact ? root.contact.display_name : ""
                        status: root.contact && root.contact.auto_reply === "ON" ? "ACTIVE" : "OFFLINE"
                        statusText: root.contact && root.contact.auto_reply === "ON" ? "AUTO-REPLY UNTIL " + root.timeText(root.contact.auto_reply_expiry)
                                                                                    : "AUTO-REPLY OFF"
                    }
                    Text { text: root.contact ? "+" + root.contact.contact_id.split("@")[0] : ""; color: root.faint; font.pixelSize: 14 }
                    Text {
                        width: parent.width; wrapMode: Text.WordWrap; color: root.fg; font.pixelSize: 15
                        text: root.summary ? (root.summary.language + "  ·  " + root.summary.tone + " tone  ·  "
                                              + root.summary.typical_length + "  ·  emoji " + root.summary.emoji.toLowerCase())
                                           : "Style not learned yet. Import a chat below, or JARVIS learns as you chat."
                    }
                    Rectangle {
                        width: parent.width; height: 6; radius: 3; color: "#1E293B"; visible: root.profile !== null
                        Rectangle { width: parent.width * (root.profile ? root.profile.tanglish_ratio : 0); height: parent.height; radius: 3; color: "#B388FF" }
                    }
                    Text { visible: root.summary !== null; color: root.faint; font.pixelSize: 13
                           text: root.summary ? root.summary.messages_analyzed + " of your messages analysed · profile v"
                                                + ((root.contact && root.contact.profile_version) || 0) + " · updated "
                                                + (root.profile ? root.timeText(root.profile.updated_at) : "-") : "" }
                }

                // reply mode
                Card {
                    width: parent.width
                    visible: root.contact !== null
                    spacing: 12
                    Text { text: "How JARVIS answers them"; color: root.fg; font.pixelSize: 16; font.bold: true }
                    Flow {
                        width: parent.width
                        spacing: 8
                        ModeButton { text: "OFF"; tone: root.danger; active: root.contact && root.contact.reply_mode === "OFF" && root.contact.auto_reply !== "ON"
                                     onClicked: root.client.setMode(root.selectedId, "OFF", 0) }
                        ModeButton { text: "SUGGEST"; active: root.contact && root.contact.reply_mode === "SUGGEST_ONLY"
                                     onClicked: root.client.setMode(root.selectedId, "SUGGEST_ONLY", 0) }
                        ModeButton { text: "ASK FIRST"; active: root.contact && root.contact.reply_mode === "ASK_BEFORE_SEND"
                                     onClicked: root.client.setMode(root.selectedId, "ASK_BEFORE_SEND", 0) }
                    }
                    Text {
                        width: parent.width; wrapMode: Text.WordWrap; color: root.dim; font.pixelSize: 14
                        text: root.contact && root.contact.reply_mode === "SUGGEST_ONLY" ? "Drafts show up in History below; nothing is sent."
                              : root.contact && root.contact.reply_mode === "ASK_BEFORE_SEND" ? "Each draft waits in History for your Send."
                              : "No drafts. Turn on auto-reply below for a set time, or choose Suggest / Ask first."
                    }
                    Rectangle { width: parent.width; height: 1; color: "#1E2A3B" }
                    Flow {
                        width: parent.width
                        spacing: 10
                        Text { text: "Auto-reply for"; color: root.fg; font.pixelSize: 15; height: 34; verticalAlignment: Text.AlignVCenter }
                        JInput { id: autoMinutes; width: 76; text: "45"; numeric: true }
                        Text { text: "min"; color: root.dim; font.pixelSize: 14; height: 34; verticalAlignment: Text.AlignVCenter }
                        JInput { id: autoNote; width: Math.max(200, Math.min(320, detailCol.width - 420)); placeholder: "Message (optional)" }
                        JButton { text: "START"; variant: "success"; busy: root.busy
                                  onClicked: root.client.setModeWithNote(root.selectedId, "AUTO_REPLY_UNTIL", parseFloat(autoMinutes.text) || 45, autoNote.text) }
                        JButton { text: "STOP"; variant: "danger"; enabledButton: root.contact && root.contact.auto_reply === "ON"
                                  onClicked: root.client.stop(root.selectedId) }
                    }
                }

                // learn style
                Card {
                    width: parent.width
                    visible: root.contact !== null
                    spacing: 12
                    Text { text: "Teach JARVIS how you write to them"; color: root.fg; font.pixelSize: 16; font.bold: true }
                    Text { width: parent.width; wrapMode: Text.WordWrap; color: root.dim; font.pixelSize: 14
                           text: "Import a WhatsApp chat export (Chat → More → Export chat → Without media), or learn from the messages JARVIS already has. Only your own messages teach it." }
                    Flow {
                        width: parent.width
                        spacing: 10
                        JInput { id: ownerName; width: 210; placeholder: "Your name in the export" }
                        JButton { text: "IMPORT CHAT FILE"; onClicked: exportDialog.open() }
                        JButton { text: "LEARN FROM HISTORY"; variant: "ghost"; busy: root.busy
                                  onClicked: root.client.importFromHistory(root.selectedId, root.contact.display_name) }
                        JButton { text: "REFRESH"; variant: "ghost"; onClicked: root.client.rebuild(root.selectedId) }
                        JButton { text: "DELETE PROFILE"; variant: "danger"; enabledButton: root.profile !== null
                                  onClicked: root.client.clearProfile(root.selectedId) }
                    }
                }

                // preview + test (never sends)
                Card {
                    width: parent.width
                    visible: root.contact !== null
                    spacing: 12
                    Text { text: "Try it (nothing is sent)"; color: root.fg; font.pixelSize: 16; font.bold: true }
                    Item {
                        width: parent.width
                        height: 34
                        JInput { id: testInput; anchors.left: parent.left; anchors.right: testBtns.left; anchors.rightMargin: 10
                                 placeholder: "What they might send, e.g. dei tomorrow varuviya?"; onAccepted: testBtn.clicked() }
                        Row {
                            id: testBtns
                            anchors.right: parent.right
                            spacing: 8
                            JButton { id: testBtn; text: "DRAFT A REPLY"; busy: root.busy
                                      onClicked: root.client.testReply(root.selectedId, testInput.text || "dei tomorrow varuviya?") }
                            JButton { text: "PREVIEW STYLE"; variant: "ghost"; onClicked: root.client.previewStyle(root.selectedId) }
                        }
                    }
                    Rectangle {
                        width: parent.width
                        height: resultText.implicitHeight + 24
                        radius: 10
                        color: "#0C121C"
                        border.width: 1
                        border.color: "#1E2A3B"
                        visible: resultText.text.length > 0
                        Text {
                            id: resultText
                            x: 14; y: 12; width: parent.width - 28
                            wrapMode: Text.WordWrap; color: root.fg; font.pixelSize: 14; lineHeight: 1.25
                            text: {
                                var c = root.client;
                                if (!c) return "";
                                if (c.testResult && c.testResult.incoming) {
                                    var r = c.testResult;
                                    return "They: " + r.incoming + "\nYou: " + (r.reply || "(no draft - the AI model is offline)")
                                           + "\n\nLanguage " + r.target_language + " · "
                                           + (r.would_auto_send ? "would be sent automatically" : "would wait for your review")
                                           + (r.quality && r.quality.reasons && r.quality.reasons.length ? " (" + r.quality.reasons.join("; ") + ")" : "");
                                }
                                if (c.preview && c.preview.summary)
                                    return "They: " + c.preview.sample_incoming + "\nYou: " + (c.preview.example_reply || "(no draft - the AI model is offline)")
                                           + (c.preview.has_profile ? "" : "\n\nNo style learned yet, so this uses your general style.");
                                return "";
                            }
                        }
                    }
                    Flow {
                        width: parent.width; spacing: 6
                        visible: !!(root.client && root.client.preview && root.client.preview.has_profile)
                        Text { text: "Tune:"; color: root.dim; font.pixelSize: 14; height: 26; verticalAlignment: Text.AlignVCenter }
                        Repeater {
                            model: [["Looks right", "looks_right"], ["Too formal", "too_formal"], ["Too casual", "too_casual"],
                                    ["More English", "more_english"], ["More Tanglish", "more_tanglish"], ["Shorter", "shorter"], ["Longer", "longer"]]
                            delegate: JButton { text: modelData[0]; small: true; variant: "ghost"; onClicked: root.client.feedback(root.selectedId, modelData[1]) }
                        }
                    }
                }

                // history + drafts waiting
                Card {
                    width: parent.width
                    visible: root.contact !== null
                    spacing: 10
                    Item {
                        width: parent.width
                        height: 34
                        Text { text: "Replies and drafts"; color: root.fg; font.pixelSize: 16; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                        JButton { text: "RELOAD"; variant: "ghost"; small: true; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                                  onClicked: root.client.loadHistory(root.selectedId) }
                    }
                    Text { visible: !root.client || root.client.history.length === 0; color: root.faint; font.pixelSize: 14
                           text: "Nothing yet. Drafts that need your OK and every reply JARVIS sends show up here." }
                    Repeater {
                        model: root.client ? root.client.history : []
                        delegate: Rectangle {
                            readonly property bool pending: ["SUGGESTED", "AWAITING_APPROVAL", "NEEDS_USER_REVIEW"].indexOf(modelData.status) >= 0
                            width: parent.width
                            height: hCol.implicitHeight + 22
                            radius: 10
                            color: pending ? Qt.rgba(1, 0.7, 0, 0.05) : "#0C121C"
                            border.width: 1
                            border.color: pending ? Qt.rgba(1, 0.7, 0, 0.35) : "#1E2A3B"
                            Column {
                                id: hCol
                                x: 14; y: 11; width: parent.width - 28
                                spacing: 5
                                Text { text: root.timeText(modelData.created_at) + "  ·  " + modelData.status.replace(/_/g, " ").toLowerCase()
                                             + (modelData.reason ? "  ·  " + modelData.reason : "")
                                       color: modelData.status === "VERIFIED" ? root.ok : (modelData.status === "UNCERTAIN" || modelData.status === "FAILED" ? root.danger : root.dim)
                                       font.pixelSize: 13; elide: Text.ElideRight; width: parent.width }
                                Text { text: "They: " + modelData.incoming; color: root.dim; font.pixelSize: 14; wrapMode: Text.WordWrap; width: parent.width }
                                Text { text: "You: " + (modelData.text || "-"); color: root.fg; font.pixelSize: 14; wrapMode: Text.WordWrap; width: parent.width }
                                Flow {
                                    width: parent.width; spacing: 8; visible: pending
                                    JButton { text: "SEND"; variant: "success"; small: true; onClicked: root.client.approve(modelData.id, "", false) }
                                    JButton { text: "SEND + LEARN FROM IT"; small: true; onClicked: root.client.approve(modelData.id, "", true) }
                                    JButton { text: "DISCARD"; variant: "danger"; small: true; onClicked: root.client.reject(modelData.id) }
                                }
                            }
                        }
                    }
                }
            }
        }

        // ---------------------------------------------------------------- live activity
        Card {
            width: parent.width
            spacing: 6
            SectionLabel { text: "LIVE ACTIVITY" }
            Text { visible: !root.client || root.client.activity.length === 0; color: root.faint; font.pixelSize: 14
                   text: "Quiet. When a message arrives you will see JARVIS read it, draft, and send or hold the reply." }
            Repeater {
                model: root.client ? root.client.activity.slice(0, 12) : []
                delegate: Row {
                    spacing: 12
                    Text { text: root.timeText(modelData.ts); color: root.faint; font.pixelSize: 13; width: 64 }
                    Text { text: modelData.stage; font.pixelSize: 13; font.bold: true; width: 120; elide: Text.ElideRight
                           color: modelData.stage === "NOT SENT" || modelData.stage === "UNCERTAIN" ? root.danger
                                  : (modelData.stage === "Verified" ? root.ok : "#B8C6D8") }
                    Text { text: modelData.display_name + (modelData.detail ? "  ·  " + modelData.detail : ""); color: root.dim
                           font.pixelSize: 13; elide: Text.ElideRight; width: page.contentW - 240 }
                }
            }
        }
    }
}

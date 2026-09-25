.pragma library

// One colour language for every orb, badge and glow in the UI.
function stateColor(state) {
    switch (state) {
    case "LISTENING": return "#00E676";
    case "TRANSCRIBING": return "#18FFFF";
    case "UNDERSTANDING":
    case "PLANNING":
    case "ROUTING":
    case "EXECUTING": return "#2979FF";
    case "VERIFYING": return "#00B8D4";
    case "SPEAKING": return "#B388FF";
    case "WAITING_CONFIRMATION": return "#FFB300";
    case "SUCCESS": return "#00E5FF";
    case "ERROR": return "#FF5252";
    case "OFFLINE": return "#607D8B";
    default: return "#00E5FF";
    }
}

function isBusy(state) {
    return state === "UNDERSTANDING" || state === "PLANNING" || state === "ROUTING"
        || state === "EXECUTING" || state === "VERIFYING" || state === "TRANSCRIBING";
}

function label(state) {
    switch (state) {
    case "LISTENING": return "Listening";
    case "TRANSCRIBING": return "Transcribing";
    case "UNDERSTANDING":
    case "ROUTING": return "Understanding";
    case "PLANNING": return "Planning";
    case "EXECUTING": return "Working";
    case "VERIFYING": return "Verifying";
    case "SPEAKING": return "Speaking";
    case "WAITING_CONFIRMATION": return "Needs your OK";
    case "SUCCESS": return "Done";
    case "ERROR": return "Something went wrong";
    case "OFFLINE": return "Offline";
    default: return "Online";
    }
}

function speed(state) {
    if (isBusy(state)) return 2.6;
    if (state === "LISTENING") return 1.7;
    if (state === "SPEAKING") return 1.35;
    if (state === "OFFLINE") return 0.25;
    return 1.0;
}


var DOC_VERSIONS = {};
var DOC_SORTED_VERSIONS = [];
var DOC_LATEST_VERSION = null;

function versionSplit(v) {
    var parts = v.split(".", 4);
    
    if (parts.length < 3) {
        throw new Error("Invalid version: " + v);
    }
    
    var nparts = [];
    for (var i = 0; i < 3; i++) {
        nparts.push(parseInt(parts[i]));
    }
    
    var version = parts.slice(0, 3).join(".");
    
    var suffix;
    
    if (parts.length == 3) {
        suffix = "";
    }
    else {
        suffix = parts[3];
    }

    return {version: version, nparts: nparts, suffix: suffix, raw: v};
}

function compareVN(v1, v2) {
    for (var i = 0; i < 3; i++) {
        var d = v1.nparts[i] - v2.nparts[i];
        if (d != 0) {
            return -d;
        }
    }
    return 0;
}

function compareV(v1, v2) {
    var nd = compareVN(v1, v2);
    if (nd != 0) {
        return nd;
    }
    else {
        return -v1.suffix.localeCompare(v2.suffix);
    }
}

function compareSV(sv1, sv2) {
    return compareV(versionSplit(sv1), versionSplit(sv2));
}

function initVersions() {
    /* We need to sort them, coalesce 0.1.0* to 0.1.0 and make sure 0.1.0 
    points to the latest in the set of 0.1.0'es. We also set DOC_LATEST_VERSION.
    The order is numeric for the numeric parts and lexicographic for the 
    trailing part. */
    var vs = {};
    
    for (var i = 0; i < DOC_VERSIONS_RAW.length; i++) {
        var v = versionSplit(DOC_VERSIONS_RAW[i]);
        console.log(v);
        if (!(v.version in vs)) {
            vs[v.version] = {all: []};
        }
        console.log(vs);
        vs[v.version].all.push(v);
    }
    
    for (var key in vs) {
        vs[key].all.sort(compareV);
        vs[key].latest = vs[key].all[0];
        DOC_SORTED_VERSIONS.push(vs[key].latest);
    }
    
    DOC_SORTED_VERSIONS.sort(compareVN);
    DOC_LATEST_VERSION = DOC_SORTED_VERSIONS[0].version;
    DOC_VERSIONS = vs;
}

function getLatestVersion() {
    return DOC_LATEST_VERSION;
}

function getSortedVersionLabels() {
    return DOC_SORTED_VERSIONS.map(v => v.version);
}

function splitLocation() {
    var url = window.location.href;
    
    var ix1 = url.indexOf("/docs/v/");
    if (ix1 >= 0) {
        var rest = url.substring(ix1 + "/docs/v/".length);
        var ix2 = rest.indexOf("/");
        if (ix2 >= 0) {
            return [url.substring(0, ix1) + "/docs/v", rest.substring(0, ix2), rest.substring(ix2 + 1)];
        }
        else {
            return [url.substring(0, ix1) + "/docs/v", rest, ""];
        }
    }
    else {
        return [url, "", ""];
    }
}

function setVersion() {    
    var s = splitLocation();
    
    window.location = s[0] + "/" + DOC_VERSIONS[this.version].latest.raw + "/" + s[2];
}

function getCurrentVersion() {
    v = splitLocation()[1];
    if (v == "") {
        return v;
    }
    else {
        return versionSplit(v).version;
    }
}

initVersions();
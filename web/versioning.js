
var DOC_VERSIONS = {};
var DOC_SORTED_VERSIONS = [];
var DOC_LATEST_VERSION = null;

/**
 * Takes a string of the form <code>x.y.z[.suffix]</code> and returns a version
 * object with the following fields:
 * - <code>version</code>: a string containing the <code>x.y.z</code> part
 * - <code>nparts</code>: an array with x, y, and z in numeric form
 * - <code>suffix</code>: the <code>suffix</code> part or an empty string
 * - <code>raw</code>: the original string passed to this function
 *
 * @param  {String} v   A string in the form <code>x.y.z[.suffix]</code>
 * @return {Object}     A version object with information about the input
 *                      version
 */
function versionSplit(v) {
    var parts = v.split(".", 4);
    
    if (parts.length < 3) {
        return {version: v, nparts: [v], suffix: "", raw: v};
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

/**
 * Compares the numeric parts of two version objects. Specifically,
 * it successively compares <code>v1.nparts[i]</code> with
 * <code>v2.nparts[i]</code> until one is larger than the other.
 * Sorting a list of version objects using this comparator results
 * in the latest version being the first.
 *
 * @param  {Object} v1   The first version object to compare
 * @param  {Object} v2   The second version object to compare
 * @return {Number}      A negative number if v2 represents a version
 *                       smaller than v1 (ignoring the suffix), 0 if
 *                       equal (again, ignoring the suffix), and a
 *                       positive number otherwise.
 */
function compareVN(v1, v2) {
    if (v1.nparts.length < 3) {
        return -1;
    }
    if (v2.nparts.length < 3) {
        return 1;
    }
    for (var i = 0; i < 3; i++) {
        var d = v1.nparts[i] - v2.nparts[i];
        if (d != 0) {
            return -d;
        }
    }
    return 0;
}

/**
 * Compares two version objects. First, their numeric parts are compared
 * and the result returned if the numeric parts are not equal. If the
 * numeric parts are equal, their suffixes are compared.
 *
 * @param  {Object} v1   The first version object to compare.
 * @param  {Object} v2   The second version object to compare.
 * @return {Number}      A negative number if v2 < v1, zero if
 *                       v2 == v1, and a positive number otherwise.
 */
function compareV(v1, v2) {
    var n = compareVN(v1, v2);
    if (n != 0) {
        return n;
    }
    else {
        return -v1.suffix.localeCompare(v2.suffix);
    }
}


/**
 * Compares two version strings. It first parses them into version
 * objects then uses <code>compareV()</code>.
 *
 * @param  {String} sv1   The first version string to compare
 * @param  {String} sv2   The second version string to compare
 * @return {Number}       A negative number if v2 < v1, zero if
 *                        v2 == v1, or a positive number if v2 > v1.
 */
function compareSV(sv1, sv2) {
    return compareV(versionSplit(sv1), versionSplit(sv2));
}


/**
 * Initializes various version related global variables.
 * The build process produces a <code>versions.js</code> file
 * which contains a list of raw version strings. These versions
 * are then parsed and the versions with the same numbers (but different
 * suffixes) are coalesced into a single object with a pointer to the
 * version with the latest suffix. The idea is that we only present the
 * numeric version to the users, but always point to the latest version
 * with that numeric prefix. For example, the latest of "0.1.0",
 * "0.1.0.post1", and "0.1.0.post2" is "0.1.0.post2", but the user only
 * sees "0.1.0".
 *
 * This function also selects the latest version which is to be displayed
 * by default.
 *
 */
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
    if (DOC_SORTED_VERSIONS.length == 1 || DOC_SORTED_VERSIONS[0].nparts.length != 1) {
        DOC_LATEST_VERSION = DOC_SORTED_VERSIONS[0].version;
    }
    else {
        DOC_LATEST_VERSION = DOC_SORTED_VERSIONS[1].version;
    }
    DOC_VERSIONS = vs;
}

/**
 * Returns the numeric part of the latest version that can be selected.
 * For example, if all versions are "0.1.0", "0.1.0.post1", "0.9.0", and,
 * "0.9.0.post1", this function will return "0.9.0" since it is the numeric
 * part of the latest version, which is "0.9.0.post1".
 *
 * @return {String}    A string representing the latest version that can
 *                     be selected by a user.
 */
function getLatestVersion() {
    return DOC_LATEST_VERSION;
}

/**
 * Returns a list with the numeric parts of all versions, with the most recent
 * version occupying the first position in the list. For example, if all
 * versions are "0.1.0", "0.1.0.post1", "0.9.0", and, "0.9.0.post1" then this
 * function will return <code>["0.9.0", "0.1.0"]</code>.
 *
 * @return {Array}     A list of version numbers.
 */
function getSortedVersionLabels() {
    return DOC_SORTED_VERSIONS.map(v => v.version);
}

/**
 * Splits the current URL around the documentation version. It returns
 * an array with three elements, the first being the part before the version,
 * the second being the version, and the third being the part after the
 * version. For example, the url  will be
 * split into <code>["abc.com/docs/v", "0.1.0", "path"]</code>.
 *
 * @return {Array}     A list of URL parts as described above.
 */
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

/**
 * Replaces the current version in the URL with the version selected in the
 * version selector (<code>this.version</code>). For example, if the current
 * URL is <code>"abc.com/docs/v/0.1.0/path"</code> and
 * <code>this.version == "0.9.0"</code>, then this function will redirect
 * the browser to <code>"abc.com/docs/v/0.9.0/path"</code>.
 */
function setVersion() {    
    var s = splitLocation();
    
    window.location = s[0] + "/" + DOC_VERSIONS[this.version].latest.raw + "/" + s[2];
}

/**
 * Returns the numeric part of the current version being displayed.
 * For example, if the current URL is "abc.com/docs/v/0.1.0.post2/path",
 * this method will return "0.1.0".
 *
 * @return {String}    A string representing the numeric part of the
 *                     currently displayed documentation version.
 */
function getCurrentVersion() {
    var v = splitLocation()[1];
    if (v == "") {
        return v;
    }
    else {
        return versionSplit(v).version;
    }
}

/**
 * Returns the main documentation page for the current version by removing
 * everything after <code>"../docs/v/x.y.z/"</code> from the current URL.
 */
function getMainDocsPage() {
    var s = splitLocation();

    return s[0] + "/" + s[1] + "/";
}

/**
 * Returns true if the current URL points to a versioned documentation
 * page.
 */
function isDocsPage() {
    return window.location.href.includes("/docs/v/");
}

initVersions();
docsHashChange = function(path, hash) {
    if (!path.startsWith("/docs/")) {
        throw new Exception("Something is wrong with the docs path " +
        "(should start) with '/docs/'" + path);
    }
    if (hash.startsWith("#")) {
        hash = hash.substr(1);
    }
    path = path.substr("/docs/".length);
    window.scrollTo(window.scrollX, window.scrollY - 56);
    window.location.hash = buildPath({tab: "docs", doc: path, dochash: hash});
}

docsLoaded = function(path, hash) {
    docsHashChange(path, hash);
    resizeDocsFrame();
    if (hash) {
        var anchor = window.docs.document.getElementById(hash.substr(1));
        if (anchor) {
            anchor.scrollIntoView();
            window.scrollTo(window.scrollX, window.scrollY - 56);
        }
    }

    var html = document.getElementsByTagName("html")[0];
    var body = document.getElementsByTagName("body")[0];
    var ibody = window.docs.document.getElementsByTagName("body")[0];

    ibody.scrollcb = function(y) {
        html.scrollTop = y;
        body.scrollTop = y;
    }

    ibody.scrollpos = function() {
        return html.scrollTop;
    }
}

function resizeDocsFrame() {
    if (crtpath.tab == "docs") {
        if (window.docs && window.docs.document && window.docs.document.body) {
            var fdoc = window.docs.document;

            if (fdoc.body.offsetHeight == 0) {
                window.setTimeout(function() {resizeDocsFrame(false)}, 100);
                return;
            }
            $("#docs-frame").css("height", (fdoc.body.offsetHeight + 180) + 'px');

            $(fdoc).find("a.reference.external").each(function() {
                $(this).attr("target", "_parent");
            });
        }
    }
};

function buildPath(crtpath) {
    if (!crtpath.tab) {
        return "";
    }
    if (!crtpath.doc || crtpath.tab != "docs") {
        return "#" + crtpath.tab;
    }
    if (!crtpath.dochash) {
        return "#" + crtpath.tab + "/" + crtpath.doc;
    }
    return "#" + crtpath.tab + "/" + crtpath.doc + "/#" + crtpath.dochash;
}

function buildDocsPath(crtpath) {
    if (crtpath.tab != "docs") {
        return "";
    }
    if (!crtpath.doc) {
        return "/docs/index.html";
    }
    if (!crtpath.dochash) {
        return "/docs/" + crtpath.doc;
    }
    else {
        return "/docs/" + crtpath.doc + "#" + crtpath.dochash;
    }
}

function getPathFromHash(hash) {
    if (hash == "") {
        return {tab: "index", doc: null, dochash: null};
    }
    var els = hash.split("/");
    var tab = els[0].substr(1);
    var doc = null;
    var dochash = null;
    if (els.length == 2) {
        doc = els[1];
    }
    if (els.length > 2) {
        var last = els[els.length - 1];
        if (last && last.startsWith("#")) {
            dochash = last.substr(1);
            doc = els.slice(1, -1).join("/");
        }
        else {
            doc = els.slice(1).join("/");
            dochash = null;
        }
    }
    return {tab: tab, doc: doc, dochash: dochash};
}

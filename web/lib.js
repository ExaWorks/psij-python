function getTabFromHash(hash) {
    if (hash) {
        return hash.substr(1);
    }
    else {
        return "index";
    }
}

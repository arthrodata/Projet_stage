(function initBioExplorerConfig(window) {
    const host = window.location.hostname;
    const isLocalHost = host === "localhost" || host === "127.0.0.1" || host === "::1";
    const isLocalFile = window.location.protocol === "file:";

    window.BioExplorerConfig = {
        apiUrl: isLocalHost || isLocalFile ? "http://127.0.0.1:8000" : "/api",
        assetVersion: String(Date.now()),
    };
    window.API_URL = window.BioExplorerConfig.apiUrl;
})(window);

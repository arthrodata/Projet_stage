(function applyAssetCacheBusting(window, document) {
    const config = window.BioExplorerConfig || {};
    const version = encodeURIComponent(config.assetVersion || String(Date.now()));
    const localStylesheetSelector = 'link[rel="stylesheet"][href]:not([href^="http://"]):not([href^="https://"])';

    function withVersion(url) {
        const [path, hash = ""] = url.split("#");
        const [base, query = ""] = path.split("?");
        const params = new URLSearchParams(query);
        params.set("v", version);
        const nextUrl = `${base}?${params.toString()}`;
        return hash ? `${nextUrl}#${hash}` : nextUrl;
    }

    function refreshStylesheets() {
        document.querySelectorAll(localStylesheetSelector).forEach((asset) => {
            const current = asset.getAttribute("href");
            if (!current || current.startsWith("data:") || current.startsWith("blob:")) return;
            asset.setAttribute("href", withVersion(current));
        });
    }

    function loadScript(src) {
        return new Promise((resolve, reject) => {
            const script = document.createElement("script");
            script.src = withVersion(src);
            script.onload = resolve;
            script.onerror = () => reject(new Error(`Unable to load ${src}`));
            document.body.appendChild(script);
        });
    }

    function loadAppScripts() {
        const scripts = Array.from(document.querySelectorAll("script[data-src]"));
        return scripts.reduce(
            (chain, script) => chain.then(() => {
                const current = script.getAttribute("data-src");
                if (!current || current.startsWith("data:") || current.startsWith("blob:")) return null;
                return loadScript(current);
            }),
            Promise.resolve()
        );
    }

    function boot() {
        refreshStylesheets();
        loadAppScripts().catch((error) => {
            console.error(error);
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot, { once: true });
    } else {
        boot();
    }
})(window, document);

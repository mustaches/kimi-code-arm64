(() => {
    if (window.__kimiCdpBridgeInstalled) return;
    window.__kimiCdpBridgeInstalled = true;
    const desktop = window.kimiDesktop || {};
    const pending = new Map();
    let nextId = 0;

    window.__kimiResolve = (id, result) => {
        const resolve = pending.get(id);
        if (!resolve) return;
        pending.delete(id);
        resolve(result);
    };

    const call = (payload) => new Promise((resolve) => {
        const id = ++nextId;
        pending.set(id, resolve);
        window.__kimiNativeBridge(JSON.stringify({id, payload}));
    });

    const decodePng = (result) => {
        if (!result || result.status !== "ok") return {status: result ? result.status : "error"};
        const binary = atob(result.png);
        const bytes = new Uint8Array(binary.length);
        for (let index = 0; index < binary.length; index++) {
            bytes[index] = binary.charCodeAt(index);
        }
        return {status: "ok", captureId: String(result.captureId || Date.now()), pngBytes: bytes, comment: ""};
    };

    desktop.isFullscreen = () => Promise.resolve(false);
    desktop.onFullscreenChanged = () => () => {};
    desktop.onQuitConfirm = () => () => {};
    desktop.onQuitConfirmCancel = () => () => {};
    desktop.isScreenshotSupported = () => true;
    desktop.captureScreenshot = () => call({action: "captureScreenshot"}).then(decodePng);
    desktop.openExternal = (url) => call({action: "openExternal", url})
        .then((result) => result === true);
    desktop.showOpenDialog = (options) => call({action: "showOpenDialog", options})
        .then((result) => result || {canceled: true, filePaths: []});
    window.kimiDesktop = desktop;

    const markNoTranslate = () => {
        const meta = document.createElement("meta");
        meta.name = "google";
        meta.content = "notranslate";
        (document.head || document.documentElement)?.appendChild(meta);
        if (document.documentElement) document.documentElement.lang = "zh-CN";
    };
    if (document.head || document.documentElement) {
        markNoTranslate();
    } else {
        document.addEventListener("DOMContentLoaded", markNoTranslate, {once: true});
    }

    window.__kimiSetTitle = (title) => {
        if (window.__kimiTitleTimer) clearInterval(window.__kimiTitleTimer);
        const apply = () => {
            if (document.title !== title) document.title = title;
        };
        apply();
        window.__kimiTitleTimer = setInterval(apply, 1000);
    };
})();

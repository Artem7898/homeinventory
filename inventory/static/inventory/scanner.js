/* QR decoding stays in this browser. Only existing links on this site may open. */
(() => {
    "use strict";

    const uuidPattern = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";
    const labelPath = new RegExp(`^/labels/(item|container)/${uuidPattern}/$`, "i");
    const itemPath = /^\/item\/[1-9]\d*\/$/;
    const containerPath = /^\/containers\/[1-9]\d*\/$/;
    const plainUuid = new RegExp(`^${uuidPattern}$`, "i");

    function safeDestination(raw, kind = "item") {
        const value = String(raw || "").trim();
        if (!value) return null;
        let candidate = value;
        if (plainUuid.test(value)) {
            if (!["item", "container"].includes(kind)) return null;
            candidate = `/labels/${kind}/${value.toLowerCase()}/`;
        }
        try {
            const url = new URL(candidate, window.location.origin);
            if (!["http:", "https:"].includes(url.protocol) ||
                url.origin !== window.location.origin || url.username || url.password) return null;
            const path = url.pathname;
            if (labelPath.test(path)) return path.toLowerCase();
            return (itemPath.test(path) || containerPath.test(path)) ? path : null;
        } catch (_) {
            return null;
        }
    }

    // A small public seam also lets the browser smoke test verify URL validation.
    window.HomeInventoryScanner = Object.freeze({safeDestination});

    const readerElement = document.getElementById("qr-reader");
    const startButton = document.getElementById("scanner-start");
    const stopButton = document.getElementById("scanner-stop");
    const status = document.getElementById("scanner-status");
    const fileInput = document.getElementById("scanner-file");
    const codeForm = document.getElementById("scanner-code");
    if (!readerElement || !startButton || !stopButton || !status) return;

    let scanner;
    let running = false;
    let starting = false;
    let navigating = false;
    let lastRejected = null;

    function announce(message, isError = false) {
        status.textContent = message;
        status.dataset.error = isError ? "true" : "false";
    }

    function controls() {
        startButton.disabled = running || starting || navigating;
        stopButton.disabled = !running || navigating;
        if (fileInput) fileInput.disabled = starting || navigating;
        readerElement.setAttribute("aria-busy", starting ? "true" : "false");
    }

    function getScanner() {
        if (!window.Html5Qrcode) throw new Error("scanner-unavailable");
        if (!scanner) scanner = new window.Html5Qrcode("qr-reader");
        return scanner;
    }

    async function stopCamera() {
        if (scanner && running) {
            try { await scanner.stop(); } catch (_) { /* Stream may have ended already. */ }
        }
        running = false;
        controls();
    }

    async function openCode(decoded, kind) {
        if (navigating) return;
        const path = safeDestination(decoded, kind);
        if (!path) {
            if (lastRejected !== decoded) {
                announce("Этот код не является этикеткой с этого сайта. Проверьте адрес или введите код этикетки вручную.", true);
                lastRejected = decoded;
            }
            return;
        }
        navigating = true;
        controls();
        announce("Код распознан. Открываем карточку…");
        await stopCamera();
        window.location.assign(path);
    }

    startButton.addEventListener("click", async () => {
        if (running || starting || navigating) return;
        if (!window.isSecureContext) {
            announce("Для камеры нужен защищённый адрес HTTPS. Можно загрузить снимок кода или ввести его вручную.", true);
            return;
        }
        starting = true;
        controls();
        announce("Разрешите доступ к камере, затем наведите её на этикетку.");
        try {
            await getScanner().start(
                {facingMode: "environment"},
                {fps: 10, qrbox: {width: 220, height: 220}},
                (decoded) => { void openCode(decoded); },
                () => { /* Unreadable video frames are expected while aiming. */ }
            );
            running = true;
            announce("Камера работает. Наведите её на QR-код.");
        } catch (_) {
            announce("Не удалось включить камеру. Проверьте разрешение браузера или загрузите снимок QR-кода.", true);
        } finally {
            starting = false;
            controls();
            if (navigating) await stopCamera();
        }
    });

    stopButton.addEventListener("click", async () => {
        await stopCamera();
        announce("Камера выключена.");
    });

    if (fileInput) fileInput.addEventListener("change", async () => {
        const file = fileInput.files && fileInput.files[0];
        if (!file || navigating) return;
        if (file.size > 10 * 1024 * 1024) {
            announce("Выберите изображение размером не более 10 МБ.", true);
            fileInput.value = "";
            return;
        }
        await stopCamera();
        announce("Читаем код на изображении…");
        try {
            const decoded = await getScanner().scanFile(file, true);
            await openCode(decoded);
        } catch (_) {
            announce("Не удалось прочитать QR-код. Попробуйте более чёткий снимок или введите код вручную.", true);
        } finally {
            fileInput.value = "";
            controls();
        }
    });

    if (codeForm) codeForm.addEventListener("submit", (event) => {
        const data = new FormData(codeForm);
        const code = String(data.get("code") || "").trim();
        // Short printed codes are resolved by the authorized, workspace-scoped server.
        if (/^[0-9a-f]{8}$/i.test(code)) return;
        event.preventDefault();
        void openCode(code, data.get("kind") || "item");
    });

    window.addEventListener("pagehide", () => { void stopCamera(); });
    controls();
})();

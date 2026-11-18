
document.addEventListener("DOMContentLoaded", () => {
    const fileInput = document.getElementById("reviews_file");
    const dropzone = document.getElementById("dropzone");
    const fileName = document.getElementById("file-name");
    const fileError = document.getElementById("file-error");
    const csvForm = document.getElementById("csv-form");
    const urlForm = document.getElementById("analyze-product");
    const urlInput = document.getElementById("product_url");
    const urlError = document.getElementById("url-error");

    function showError(element, message) {
        if (!element) return;
        element.textContent = message;
        element.hidden = !message;
    }

    function displayFile(file) {
        if (!fileName) return;
        fileName.textContent = file
            ? `Selected: ${file.name}`
            : "No file selected.";
    }

    if (fileInput) {
        fileInput.addEventListener("change", () => {
            const file = fileInput.files[0];
            showError(fileError, "");

            if (!file) {
                displayFile(null);
                return;
            }

            const maxMB = Number(dropzone?.dataset.maxMb || 100);
            if (!file.name.toLowerCase().endsWith(".csv")) {
                fileInput.value = "";
                displayFile(null);
                showError(fileError, "Please select a CSV file.");
                return;
            }

            if (file.size > maxMB * 1024 * 1024) {
                fileInput.value = "";
                displayFile(null);
                showError(fileError, `File must be smaller than ${maxMB} MB.`);
                return;
            }

            displayFile(file);
        });
    }

    if (dropzone && fileInput) {
        ["dragenter", "dragover"].forEach((eventName) => {
            dropzone.addEventListener(eventName, (event) => {
                event.preventDefault();
                dropzone.classList.add("is-dragging");
            });
        });

        ["dragleave", "drop"].forEach((eventName) => {
            dropzone.addEventListener(eventName, (event) => {
                event.preventDefault();
                dropzone.classList.remove("is-dragging");
            });
        });

        dropzone.addEventListener("drop", (event) => {
            const file = event.dataTransfer?.files?.[0];
            if (!file) return;

            try {
                const transfer = new DataTransfer();
                transfer.items.add(file);
                fileInput.files = transfer.files;
                fileInput.dispatchEvent(new Event("change"));
            } catch {
                showError(
                    fileError,
                    "Please use the browse option to select your CSV."
                );
            }
        });
    }

    if (csvForm) {
        csvForm.addEventListener("submit", (event) => {
            showError(fileError, "");

            if (!fileInput || !fileInput.files.length) {
                event.preventDefault();
                showError(fileError, "Please select a CSV file first.");
                return;
            }

            const button = csvForm.querySelector('button[type="submit"]');
            if (button) {
                button.disabled = true;
                const label = button.querySelector(".btn-label");
                if (label) label.textContent = "Analyzing reviews...";
            }
        });
    }

    if (urlForm) {
        urlForm.addEventListener("submit", (event) => {
            showError(urlError, "");
            const value = urlInput?.value.trim() || "";

            if (!value) {
                event.preventDefault();
                showError(urlError, "Please paste a product URL.");
                urlInput?.focus();
                return;
            }

            try {
                const parsed = new URL(value);
                if (!["http:", "https:"].includes(parsed.protocol)) {
                    throw new Error("Invalid protocol");
                }
            } catch {
                event.preventDefault();
                showError(urlError, "Enter a valid URL starting with https:// or http://.");
                urlInput?.focus();
                return;
            }

            const button = urlForm.querySelector('button[type="submit"]');
            if (button) {
                button.disabled = true;
                const label = button.querySelector(".btn-label");
                if (label) label.textContent = "Analyzing product...";
            }
        });
    }
});

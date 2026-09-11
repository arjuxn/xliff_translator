const form =
    document.getElementById(
        "translation-form"
    );

const fileInput =
    document.getElementById(
        "file"
    );

const dropZone =
    document.getElementById(
        "drop-zone"
    );

const selectedFile =
    document.getElementById(
        "selected-file"
    );

const dntTerms =
    document.getElementById(
        "dnt-terms"
    );

const termCount =
    document.getElementById(
        "term-count"
    );

const dntFileInput =
    document.getElementById(
        "dnt-file"
    );

const selectedDntFile =
    document.getElementById(
        "selected-dnt-file"
    );

const selectedDntName =
    document.getElementById(
        "selected-dnt-name"
    );

const removeDntFile =
    document.getElementById(
        "remove-dnt-file"
    );

const translateButton =
    document.getElementById(
        "translate-button"
    );

const status =
    document.getElementById(
        "status"
    );

const statusTitle =
    document.getElementById(
        "status-title"
    );

const statusMessage =
    document.getElementById(
        "status-message"
    );

const results =
    document.getElementById(
        "results"
    );

const resultSummary =
    document.getElementById(
        "result-summary"
    );

const downloadList =
    document.getElementById(
        "download-list"
    );

const errorBox =
    document.getElementById(
        "error"
    );


// ============================================================
// XLIFF FILE
// ============================================================

fileInput.addEventListener(
    "change",
    () => {

        const file =
            fileInput.files[0];

        if (!file) {

            selectedFile.textContent =
                "";

            return;
        }

        selectedFile.textContent =
            `Selected: ${file.name}`;

        hideError();
    }
);


// ============================================================
// XLIFF DRAG AND DROP
// ============================================================

dropZone.addEventListener(
    "dragover",
    event => {

        event.preventDefault();

        dropZone.classList.add(
            "dragging"
        );
    }
);


dropZone.addEventListener(
    "dragleave",
    () => {

        dropZone.classList.remove(
            "dragging"
        );
    }
);


dropZone.addEventListener(
    "drop",
    event => {

        event.preventDefault();

        dropZone.classList.remove(
            "dragging"
        );

        const files =
            event.dataTransfer.files;

        if (!files.length) {
            return;
        }

        const file =
            files[0];

        const name =
            file.name.toLowerCase();

        if (
            !name.endsWith(".xlf") &&
            !name.endsWith(".xliff")
        ) {

            showError(
                "Please select an XLF or XLIFF file."
            );

            return;
        }

        fileInput.files =
            files;

        selectedFile.textContent =
            `Selected: ${file.name}`;

        hideError();
    }
);


// ============================================================
// DNT FILE
// ============================================================

dntFileInput.addEventListener(
    "change",
    () => {

        const file =
            dntFileInput.files[0];

        if (!file) {

            hideDntFile();

            return;
        }

        if (
            !file.name
                .toLowerCase()
                .endsWith(".txt")
        ) {

            showError(
                "Protected terms file must be a .txt file."
            );

            dntFileInput.value =
                "";

            hideDntFile();

            return;
        }

        selectedDntName.textContent =
            file.name;

        selectedDntFile.classList.remove(
            "hidden"
        );

        removeDntFile.classList.remove(
            "hidden"
        );

        hideError();
    }
);


removeDntFile.addEventListener(
    "click",
    () => {

        dntFileInput.value =
            "";

        hideDntFile();
    }
);


function hideDntFile() {

    selectedDntFile.classList.add(
        "hidden"
    );

    removeDntFile.classList.add(
        "hidden"
    );

    selectedDntName.textContent =
        "";
}


// ============================================================
// TERM COUNT
// ============================================================

dntTerms.addEventListener(
    "input",
    updateTermCount
);


function getTypedTerms() {

    const lines =
        dntTerms.value
            .split(/\r?\n/)
            .map(
                line => line.trim()
            )
            .filter(
                line => line.length > 0
            );

    return [
        ...new Set(lines)
    ];
}


function updateTermCount() {

    const count =
        getTypedTerms().length;

    termCount.textContent =
        count === 1
            ? "1 protected term"
            : `${count} protected terms`;
}


updateTermCount();


// ============================================================
// TRANSLATION
// ============================================================

form.addEventListener(
    "submit",
    async event => {

        event.preventDefault();

        hideError();
        hideResults();

        const file =
            fileInput.files[0];

        if (!file) {

            showError(
                "Please select an XLIFF file."
            );

            return;
        }


        const selectedLanguages =
            document.querySelectorAll(
                'input[name="language"]:checked'
            );

        if (!selectedLanguages.length) {

            showError(
                "Please select at least one target language."
            );

            return;
        }


        const languages =
            Array.from(
                selectedLanguages
            )
                .map(
                    input => input.value
                )
                .join(",");


        const model =
            document.getElementById(
                "model"
            ).value;


        const formData =
            new FormData();


        formData.append(
            "file",
            file
        );

        formData.append(
            "languages",
            languages
        );

        formData.append(
            "model",
            model
        );

        formData.append(
            "dnt_terms",
            dntTerms.value
        );


        const dntFile =
            dntFileInput.files[0];

        if (dntFile) {

            formData.append(
                "dnt_file",
                dntFile
            );
        }


        // ----------------------------------------------------
        // START LOADING
        // ----------------------------------------------------

        setLoading(true);

        statusTitle.textContent =
            "Translating...";

        statusMessage.textContent =
            "This may take a few minutes.";


        try {

            const response =
                await fetch(
                    "/api/translate",
                    {
                        method: "POST",
                        body: formData
                    }
                );


            let data;

            try {

                data =
                    await response.json();

            }
            catch {

                throw new Error(
                    "The server returned an invalid response."
                );
            }


            if (!response.ok) {

                throw new Error(
                    data.detail ||
                    "Translation failed."
                );
            }


            // ------------------------------------------------
            // SUCCESS
            // ------------------------------------------------

            showResults(
                data
            );

            // The translation is finished, so remove the
            // loading status/spinner immediately.
            hideStatus();

        }
        catch (error) {

            hideStatus();

            showError(
                error.message ||
                "Translation failed."
            );

        }
        finally {

            translateButton.disabled =
                false;

        }

    }
);


// ============================================================
// LOADING STATE
// ============================================================

function setLoading(
    loading
) {

    translateButton.disabled =
        loading;

    if (loading) {

        status.classList.remove(
            "hidden"
        );

    }
    else {

        status.classList.add(
            "hidden"
        );

    }
}


function hideStatus() {

    status.classList.add(
        "hidden"
    );
}


// ============================================================
// RESULTS
// ============================================================

function showResults(
    data
) {

    downloadList.innerHTML =
        "";

    const files =
        data.files || [];


    if (!files.length) {

        showError(
            "Translation completed but no output files were generated."
        );

        return;
    }


    if (
        data.dnt_terms_enabled &&
        data.dnt_terms_count
    ) {

        resultSummary.textContent =
            `${data.dnt_terms_count} protected term(s) were preserved.`;

    }
    else {

        resultSummary.textContent =
            "Your translated files are ready.";

    }


    files.forEach(
        file => {

            const link =
                document.createElement(
                    "a"
                );

            link.className =
                "download-link";

            link.href =
                file.url;

            link.download =
                file.name;

            link.textContent =
                `Download ${file.name}`;

            downloadList.appendChild(
                link
            );
        }
    );


    results.classList.remove(
        "hidden"
    );
}


function hideResults() {

    results.classList.add(
        "hidden"
    );

    downloadList.innerHTML =
        "";

    resultSummary.textContent =
        "";
}


// ============================================================
// ERROR
// ============================================================

function showError(
    message
) {

    errorBox.textContent =
        message;

    errorBox.classList.remove(
        "hidden"
    );
}


function hideError() {

    errorBox.textContent =
        "";

    errorBox.classList.add(
        "hidden"
    );
}
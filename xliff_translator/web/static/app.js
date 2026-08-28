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

const downloadList =
    document.getElementById(
        "download-list"
    );

const errorBox =
    document.getElementById(
        "error"
    );


fileInput.addEventListener(
    "change",
    () => {
        showSelectedFile(
            fileInput.files[0]
        );
    }
);


function showSelectedFile(file) {

    if (!file) {
        selectedFile.textContent = "";
        return;
    }

    selectedFile.textContent =
        `Selected: ${file.name}`;

}


[
    "dragenter",
    "dragover"
].forEach(
    eventName => {

        dropZone.addEventListener(
            eventName,
            event => {

                event.preventDefault();

                dropZone.classList.add(
                    "dragging"
                );

            }
        );

    }
);


[
    "dragleave",
    "drop"
].forEach(
    eventName => {

        dropZone.addEventListener(
            eventName,
            event => {

                event.preventDefault();

                dropZone.classList.remove(
                    "dragging"
                );

            }
        );

    }
);


dropZone.addEventListener(
    "drop",
    event => {

        const files =
            event.dataTransfer.files;

        if (!files.length) {
            return;
        }

        fileInput.files = files;

        showSelectedFile(
            files[0]
        );

    }
);


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


        const languageInputs =
            document.querySelectorAll(
                'input[name="language"]:checked'
            );


        if (!languageInputs.length) {

            showError(
                "Please select at least one target language."
            );

            return;
        }


        const languages =
            Array.from(
                languageInputs
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


        setLoading(true);

        statusTitle.textContent =
            "Translating...";

        statusMessage.textContent =
            "The XLIFF file is being translated. This may take a few minutes.";


        try {

            const response =
                await fetch(
                    "/api/translate",
                    {
                        method: "POST",
                        body: formData
                    }
                );


            const data =
                await response.json();


            if (!response.ok) {

                throw new Error(
                    data.detail ||
                    "Translation failed."
                );

            }


            showResults(
                data.files
            );


            statusTitle.textContent =
                "Translation complete.";

            statusMessage.textContent =
                "Your translated files are ready.";

        }
        catch (error) {

            hideStatus();

            showError(
                error.message
            );

        }
        finally {

            setLoading(false);

        }

    }
);


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


function showResults(
    files
) {

    downloadList.innerHTML = "";

    for (
        const file of files
    ) {

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

    results.classList.remove(
        "hidden"
    );

}


function hideResults() {

    results.classList.add(
        "hidden"
    );

}


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

    errorBox.classList.add(
        "hidden"
    );

    errorBox.textContent =
        "";

}
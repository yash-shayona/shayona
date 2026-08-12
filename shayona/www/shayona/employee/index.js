// This state mirrors the server response so the UI always reflects the real backend day log.
const state = {
    boot: null,
    currentWorkTimer: null,
    pageClockTimer: null,
    taskLoadRequestId: 0,
    cachedLocation: null,
    cachedLocationAt: 0,
    attendanceActionInProgress: false
};

const PORTAL_API_BASE = "shayona.api.employee_portal.";

const PORTAL_METHODS = {
    get_boot_data: `${PORTAL_API_BASE}employee_portal_get_boot_data`,
    search_link: "frappe.desk.search.search_link",
    start_day: `${PORTAL_API_BASE}employee_portal_start_day`,
    start_work: `${PORTAL_API_BASE}employee_portal_start_work`,
    create_task: `${PORTAL_API_BASE}employee_portal_create_task`,
    start_break: `${PORTAL_API_BASE}employee_portal_start_break`,
    end_break: `${PORTAL_API_BASE}employee_portal_end_break`,
    switch_task: `${PORTAL_API_BASE}employee_portal_switch_task`,
    end_day: `${PORTAL_API_BASE}employee_portal_end_day`
};

const LOCATION_CACHE_MS = 60000;

let projectAutocomplete = null;
let taskAutocomplete = null;
let activityTypeAutocomplete = null;
let createTaskProjectAutocomplete = null;
let createTaskTypeAutocomplete = null;

/* ---------------------------------------------------------
   Basic Helpers
--------------------------------------------------------- */

function getEl(id) {
    return document.getElementById(id);
}

function pad(value) {
    return String(value).padStart(2, "0");
}

function getDurationParts(totalSeconds) {
    const safeSeconds = Math.max(
        Math.floor(Number(totalSeconds) || 0),
        0
    );

    return frappe.utils.seconds_to_duration(
        safeSeconds,
        { hide_days: 1 }
    );
}

function getElapsedSeconds(startValue) {
    if (!startValue) {
        return 0;
    }

    const startTime =
        frappe.datetime.convert_to_user_tz(
            startValue,
            false
        );

    if (!startTime.isValid()) {
        return 0;
    }

    return Math.max(
        moment().diff(startTime, "seconds"),
        0
    );
}

function formatSecondsToClock(totalSeconds) {
    const { hours, minutes, seconds } =
        getDurationParts(totalSeconds);

    return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
}

function formatSecondsToHourMinute(totalSeconds) {
    const { hours, minutes } =
        getDurationParts(totalSeconds);

    return `${pad(hours)}:${pad(minutes)}`;
}

function formatHoursToClock(hours) {
    const totalSeconds = Math.max(
        Math.round((Number(hours) || 0) * 60 * 60),
        0
    );

    return formatSecondsToClock(totalSeconds);
}

function formatTime(value) {
    if (!value) {
        return "--:--:--";
    }

    const userTime =
        frappe.datetime.convert_to_user_tz(
            value,
            false
        );

    if (!userTime.isValid()) {
        return "--:--:--";
    }

    return userTime.format("hh:mm:ss A");
}


/* ---------------------------------------------------------
   Header Clock
--------------------------------------------------------- */

function updatePageClock() {
    const now = frappe.datetime.now_datetime(true);

    const dateElement = getEl("today-date");
    const timeElement = getEl("current-time");

    if (dateElement) {
        dateElement.textContent =
            now.toLocaleDateString("en-IN", {
                day: "2-digit",
                month: "short",
                year: "numeric",
                weekday: "long"
            });
    }

    if (timeElement) {
        timeElement.textContent =
            now.toLocaleTimeString("en-IN", {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit"
            });
    }

    renderGreeting(now);
}

function getGreetingLabel(now) {
    const hour = now.getHours();

    if (hour < 12) {
        return "Good Morning";
    }

    if (hour < 17) {
        return "Good Afternoon";
    }

    if (hour < 20) {
        return "Good Evening";
    }

    return "Good Night";
}

function renderGreeting(
    now = frappe.datetime.now_datetime(true)
) {
    const title = getEl("greeting-title");

    if (!title) {
        return;
    }

    const employeeName =
        state.boot?.user?.employee_name || "";

    const greeting = getGreetingLabel(now);

    title.textContent = employeeName
        ? `${greeting}, ${employeeName}`
        : greeting;
}


/* ---------------------------------------------------------
   Messages
--------------------------------------------------------- */

function showInlineAlert(message, type = "info") {
    const alert = getEl("portal-alert");

    if (!alert) {
        return;
    }

    alert.textContent = message;
    alert.className = `swp-alert swp-alert-${type}`;
}

function hideInlineAlert() {
    const alert = getEl("portal-alert");

    if (!alert) {
        return;
    }

    alert.textContent = "";
    alert.className = "swp-alert hidden";
}

function getErrorMessage(
    error,
    fallback = __("Something went wrong.")
) {
    const serverMessages =
        error?._server_messages
        || error?.responseJSON?._server_messages;

    if (serverMessages) {
        try {
            const parsed = JSON.parse(serverMessages);

            const firstMessage = parsed?.[0]
                ? JSON.parse(parsed[0])
                : null;

            if (typeof firstMessage === "string") {
                return firstMessage;
            }

            if (firstMessage?.message) {
                return firstMessage.message;
            }
        } catch (parseError) {
            // Use normal fallback.
        }
    }

    return error?.message || fallback;
}

function hasServerMessages(error) {
    return Boolean(
        error?._server_messages
        || error?.responseJSON?._server_messages
    );
}


/* ---------------------------------------------------------
   API
--------------------------------------------------------- */

async function callPortal(method, args = {}) {
    const apiMethod = PORTAL_METHODS[method];

    if (!apiMethod) {
        throw new Error(
            `Portal method is not configured: ${method}`
        );
    }

    const response = await frappe.call({
        method: apiMethod,
        args
    });

    return response.message;
}


/* ---------------------------------------------------------
   Location
--------------------------------------------------------- */

function getCurrentLocation() {
    const now = Date.now();

    if (
        state.cachedLocation
        && now - state.cachedLocationAt
        < LOCATION_CACHE_MS
    ) {
        return Promise.resolve(
            state.cachedLocation
        );
    }

    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject(
                new Error(
                    "Your browser does not support location access."
                )
            );
            return;
        }

        navigator.geolocation.getCurrentPosition(
            (position) => {
                state.cachedLocation = {
                    latitude:
                        position.coords.latitude,
                    longitude:
                        position.coords.longitude
                };

                state.cachedLocationAt = Date.now();

                resolve(state.cachedLocation);
            },
            (error) => {
                let message =
                    "Unable to get your current location.";

                if (
                    error.code
                    === error.PERMISSION_DENIED
                ) {
                    message =
                        "Please allow location permission to record attendance.";
                } else if (
                    error.code
                    === error.POSITION_UNAVAILABLE
                ) {
                    message =
                        "Your current location is unavailable.";
                } else if (
                    error.code
                    === error.TIMEOUT
                ) {
                    message =
                        "Location request timed out. Please try again.";
                }

                reject(new Error(message));
            },
            {
                enableHighAccuracy: false,
                timeout: 7000,
                maximumAge: LOCATION_CACHE_MS
            }
        );
    });
}


/* ---------------------------------------------------------
   Attendance Actions
--------------------------------------------------------- */

async function runAttendanceAction(
    method,
    successMessage,
    button
) {
    // Ignore extra rapid clicks.
    if (state.attendanceActionInProgress) {
        return;
    }

    state.attendanceActionInProgress = true;

    // Disable every attendance button immediately.
    refreshButtons();

    const textElement =
        button?.querySelector("span:last-child");

    const originalText =
        textElement?.textContent || "";

    if (textElement) {
        textElement.textContent = "Processing...";
    }

    try {
        const isLocationRequired =
            Number(
                state.boot
                    ?.allow_geolocation_tracking
                || 0
            ) === 1;

        let attendanceArgs = {};

        if (isLocationRequired) {
            attendanceArgs =
                await getCurrentLocation();
        }

        // Save Entry / Break Start / Break End / Exit.
        await callPortal(
            method,
            attendanceArgs
        );

        // Reload the real backend state.
        const boot =
            await callPortal("get_boot_data");

        setBootState(boot);

        frappe.show_alert({
            message: successMessage,
            indicator: "green"
        });
    } catch (error) {
        if (!hasServerMessages(error)) {
            frappe.msgprint(
                getErrorMessage(
                    error,
                    "Unable to complete attendance action."
                )
            );
        }
    } finally {
        if (textElement && originalText) {
            textElement.textContent =
                originalText;
        }

        state.attendanceActionInProgress =
            false;

        // Enable only the button valid for latest status.
        refreshButtons();
    }
}


/* ---------------------------------------------------------
   Master Dropdowns
--------------------------------------------------------- */

function getFormValues() {
    return {
        project: getEl("project")?.value || "",
        task: getEl("task")?.value || "",
        activity_type:
            getEl("activity-type")?.value || "",
        description:
            getEl("work-description")
                ?.value.trim() || ""
    };
}

/* Deprecated copy retained only until the next portal asset cleanup. */
/*
function legacyQsoCreateAutocomplete({
    inputId,
    resultsId,
    doctype,
    referenceDoctype,
    linkFieldname,
    getQuery,
    getFilters,
    onSelect,
}) {
    const input = qsoGet(inputId);
    const results = qsoGet(resultsId);
    let requestId = 0;
    let selectedValue = "";

    function close() {
        results.hidden = true;
        input.setAttribute("aria-expanded", "false");
    }

    function render(options) {
        results.replaceChildren();

        if (!options.length) {
            const empty = document.createElement("div");
            empty.className = "qso-results-message";
            empty.textContent = __("No results found");
            results.appendChild(empty);
        } else {
            options.forEach((option) => {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "qso-result-option";
                button.setAttribute("role", "option");

                const title = document.createElement("strong");
                title.textContent = option.label || option.value;
                button.appendChild(title);

                const detailText = [
                    option.value !== (option.label || option.value) ? option.value : "",
                    option.description || "",
                ].filter(Boolean).join(" · ");

                if (detailText) {
                    const detail = document.createElement("small");
                    detail.textContent = detailText;
                    button.appendChild(detail);
                }

                button.addEventListener("mousedown", (event) => {
                    event.preventDefault();
                    selectedValue = option.value;
                    input.value = option.value;
                    close();
                    onSelect(option);
                });
                results.appendChild(button);
            });
        }

        results.hidden = false;
        input.setAttribute("aria-expanded", "true");
    }

    async function search() {
        const currentRequest = ++requestId;
        results.replaceChildren();
        const loading = document.createElement("div");
        loading.className = "qso-results-message";
        loading.textContent = __("Searching...");
        results.appendChild(loading);
        results.hidden = false;
        input.setAttribute("aria-expanded", "true");

        try {
            const options = await qsoCall(QSO_METHODS.search, {
                doctype,
                txt: input.value.trim(),
                query: getQuery?.() || "",
                filters: getFilters?.() || {},
                page_length: 10,
                reference_doctype: referenceDoctype,
                link_fieldname: linkFieldname,
            });

            if (currentRequest === requestId) {
                render(options || []);
            }
        } catch (error) {
            if (currentRequest === requestId) {
                close();
                qsoSetAlert(qsoErrorMessage(error, __("Unable to search.")), "error");
            }
        }
    }

    const debouncedSearch = qsoDebounce(search);
    input.addEventListener("focus", search);
    input.addEventListener("input", () => {
        if (input.value.trim() !== selectedValue) {
            selectedValue = "";
            onSelect(null);
        }
        debouncedSearch();
    });
    input.addEventListener("blur", () => window.setTimeout(close, 120));
    input.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            close();
        }
    });

    return {
        clear() {
            selectedValue = "";
            input.value = "";
            close();
        },
        setValue(value) {
            selectedValue = value || "";
            input.value = value || "";
            close();
        },
    };
}
*/

function createSearchLinkAutocomplete({
    inputId,
    valueInputId,
    resultsId,
    doctype,
    referenceDoctype,
    linkFieldname,
    getFilters = () => ({}),
    canSearch = () => true,
    getDisplayLabel = (option) => option.label || option.value,
    onSelect = () => {},
    onClear = () => {},
}) {
    const input = getEl(inputId);
    const valueInput = getEl(valueInputId);
    const results = getEl(resultsId);
    let requestId = 0;
    let selectedValue = "";
    let debounceTimer = null;

    if (!input || !valueInput || !results) {
        console.error(`Autocomplete elements missing for ${inputId}.`);
        return {
            clear() {},
            setValue() {},
            setDisabled() {},
        };
    }

    const close = () => {
        results.hidden = true;
        input.setAttribute("aria-expanded", "false");
    };

    const renderMessage = (message) => {
        results.replaceChildren();
        const element = document.createElement("div");
        element.className = "swp-link-message";
        element.textContent = message;
        results.appendChild(element);
        results.hidden = false;
        input.setAttribute("aria-expanded", "true");
    };

    const renderResults = (options) => {
        results.replaceChildren();

        if (!options.length) {
            renderMessage("No results found");
            return;
        }

        options.forEach((option) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "swp-link-option";
            button.setAttribute("role", "option");

            const label = document.createElement("strong");
            label.textContent = getDisplayLabel(option);
            button.appendChild(label);

            const description = option.description || option.value;
            if (description && description !== getDisplayLabel(option)) {
                const detail = document.createElement("small");
                detail.textContent = description;
                button.appendChild(detail);
            }

            button.addEventListener("mousedown", (event) => {
                event.preventDefault();
                selectedValue = option.value || "";
                valueInput.value = selectedValue;
                input.value = getDisplayLabel(option);
                close();
                onSelect(option);
            });

            results.appendChild(button);
        });

        results.hidden = false;
        input.setAttribute("aria-expanded", "true");
    };

    const search = async () => {
        if (!canSearch()) {
            close();
            return;
        }

        const currentRequestId = ++requestId;
        renderMessage("Searching...");

        try {
            const response = await frappe.call({
                method: PORTAL_METHODS.search_link,
                args: {
                    doctype,
                    txt: input.value.trim(),
                    filters: getFilters() || {},
                    page_length: 10,
                    reference_doctype: referenceDoctype,
                    link_fieldname: linkFieldname,
                },
            });

            if (currentRequestId === requestId) {
                renderResults(response.message || []);
            }
        } catch (error) {
            if (currentRequestId !== requestId) {
                return;
            }

            close();
            frappe.msgprint(getErrorMessage(error, "Unable to search."));
        }
    };

    const scheduleSearch = () => {
        window.clearTimeout(debounceTimer);
        debounceTimer = window.setTimeout(search, 250);
    };

    input.addEventListener("focus", search);
    input.addEventListener("input", () => {
        if (input.value.trim() !== selectedValue) {
            selectedValue = "";
            valueInput.value = "";
            onClear();
        }

        scheduleSearch();
    });
    input.addEventListener("blur", () => window.setTimeout(close, 150));
    input.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            close();
        }
    });

    return {
        clear({ notify = true } = {}) {
            selectedValue = "";
            valueInput.value = "";
            input.value = "";
            close();
            if (notify) {
                onClear();
            }
        },
        setValue(value, label = value) {
            selectedValue = value || "";
            valueInput.value = selectedValue;
            input.value = label || selectedValue;
            close();
        },
        setDisabled(disabled) {
            input.disabled = Boolean(disabled);
            input.setAttribute("aria-disabled", String(Boolean(disabled)));
            if (disabled) {
                close();
            }
        },
    };
}

function initializeAutocompleteFields() {
    projectAutocomplete = createSearchLinkAutocomplete({
        inputId: "project-search",
        valueInputId: "project",
        resultsId: "project-results",
        doctype: "Project",
        referenceDoctype: "Timesheet Detail",
        linkFieldname: "project",
        getFilters: () => ({ status: "Open" }),
        onSelect: () => {
            taskAutocomplete.clear({ notify: false });
            taskAutocomplete.setDisabled(!getEl("project").value);
        },
        onClear: () => {
            taskAutocomplete.clear({ notify: false });
            taskAutocomplete.setDisabled(true);
        },
    });

    taskAutocomplete = createSearchLinkAutocomplete({
        inputId: "task-search",
        valueInputId: "task",
        resultsId: "task-results",
        doctype: "Task",
        referenceDoctype: "Timesheet Detail",
        linkFieldname: "task",
        canSearch: () => Boolean(getEl("project")?.value),
        getFilters: () => ({
            project: getEl("project")?.value || "",
            status: ["not in", ["Cancelled", "Completed"]],
            is_group: 0,
        }),
    });

    activityTypeAutocomplete = createSearchLinkAutocomplete({
        inputId: "activity-type-search",
        valueInputId: "activity-type",
        resultsId: "activity-type-results",
        doctype: "Activity Type",
        referenceDoctype: "Timesheet Detail",
        linkFieldname: "activity_type",
    });

    createTaskProjectAutocomplete = createSearchLinkAutocomplete({
        inputId: "create-task-project-search",
        valueInputId: "create-task-project",
        resultsId: "create-task-project-results",
        doctype: "Project",
        referenceDoctype: "Task",
        linkFieldname: "project",
        getFilters: () => ({ status: "Open" }),
    });

    createTaskTypeAutocomplete = createSearchLinkAutocomplete({
        inputId: "create-task-type-search",
        valueInputId: "create-task-type",
        resultsId: "create-task-type-results",
        doctype: "Task Type",
        referenceDoctype: "Task",
        linkFieldname: "type",
    });

    taskAutocomplete.setDisabled(true);
}

function syncAutocompleteValues() {
    const selected = state.boot?.selected_values || {};
    const current = state.boot?.current_work_session || {};

    projectAutocomplete?.setValue(
        selected.project || "",
        current.project_label || selected.project || ""
    );
    taskAutocomplete?.setValue(
        selected.task || "",
        current.task_label || selected.task || ""
    );
    activityTypeAutocomplete?.setValue(
        selected.activity_type || "",
        selected.activity_type || ""
    );
    taskAutocomplete?.setDisabled(!selected.project);
}

/* ---------------------------------------------------------
   Create Task Modal
--------------------------------------------------------- */

function resetCreateTaskModal() {
    const selectedProject =
        state.boot?.selected_values?.project
        || getEl("project")?.value
        || "";

    getEl("create-task-title").value = "";
    createTaskProjectAutocomplete?.setValue(
        selectedProject,
        selectedProject
    );
    createTaskTypeAutocomplete?.clear({ notify: false });
}

function openCreateTaskDialog() {
    resetCreateTaskModal();

    const modal =
        getEl("create-task-modal");

    if (!modal) {
        return;
    }

    modal.classList.remove("hidden");
    modal.setAttribute(
        "aria-hidden",
        "false"
    );

    getEl("create-task-title")?.focus();
}

function closeCreateTaskDialog() {
    const modal =
        getEl("create-task-modal");

    if (!modal) {
        return;
    }

    modal.classList.add("hidden");
    modal.setAttribute(
        "aria-hidden",
        "true"
    );
}

async function submitCreateTask() {
    const title =
        getEl("create-task-title")
            ?.value.trim() || "";

    const project =
        getEl("create-task-project")
            ?.value || "";

    const taskType =
        getEl("create-task-type")
            ?.value || "";

    const submitButton =
        getEl("btn-submit-create-task");

    if (!title) {
        frappe.msgprint(
            "Please enter Task Title."
        );
        return;
    }

    const currentValues = getFormValues();

    const originalText =
        submitButton.textContent;

    submitButton.disabled = true;
    submitButton.textContent =
        "Creating & Starting...";

    let createdTask = "";

    try {
        /*
         * Step 1:
         * Create the new Task.
         */
        const result = await callPortal(
            "create_task",
            {
                subject: title,
                project,
                task_type: taskType
            }
        );

        createdTask = result.task;

        /*
         * Step 2:
         * Immediately start work on the newly created Task.
         */
        await callPortal(
            "start_work",
            {
                project,
                task: createdTask,
                activity_type:
                    currentValues.activity_type,
                description:
                    currentValues.description
            }
        );

        /*
         * Step 3:
         * Reload actual backend state.
         *
         * Backend status should now become "Working"
         * and current_work_session should contain
         * the newly created Task.
         */
        const boot = await callPortal(
            "get_boot_data"
        );

        closeCreateTaskDialog();
        setBootState(boot);

        frappe.show_alert({
            message:
                "Task created and work started successfully.",
            indicator: "green"
        });
    } catch (error) {
        /*
         * Task creation and Start Work are two separate
         * backend calls.
         *
         * Therefore, it is possible that Task was created
         * successfully but Start Work failed.
         */
        if (!hasServerMessages(error)) {
            const message = getErrorMessage(
                error,
                createdTask
                    ? "Task was created, but work could not be started."
                    : "Unable to create Task."
            );

            frappe.msgprint(message);
        }
    } finally {
        submitButton.disabled = false;
        submitButton.textContent =
            originalText;
    }
}


/* ---------------------------------------------------------
   Attendance Timer
--------------------------------------------------------- */

// function syncCurrentWorkTimer() {
//     if (state.currentWorkTimer) {
//         clearInterval(
//             state.currentWorkTimer
//         );

//         state.currentWorkTimer = null;
//     }

//     const tick = () => {
//         const status =
//             state.boot?.status
//             || "Not Started";

//         const completedWorkSeconds =
//             Number(
//                 state.boot
//                     ?.completed_work_seconds
//                 || 0
//             );

//         const completedBreakSeconds =
//             Number(
//                 state.boot
//                     ?.completed_break_seconds
//                 || 0
//             );

//         const activeWorkSeconds =
//             state.boot?.active_work_started_at
//             ? getElapsedSeconds(
//                 state.boot.active_work_started_at
//             )
//             : 0;

//         const activeBreakSeconds =
//             state.boot?.active_break_started_at
//             ? getElapsedSeconds(
//                 state.boot.active_break_started_at
//             )
//             : 0;

//         const totalWorkSeconds =
//             completedWorkSeconds
//             + activeWorkSeconds;

//         const totalBreakSeconds =
//             completedBreakSeconds
//             + activeBreakSeconds;

//         const workingTime =
//             getEl("current-working-time");

//         const workTotal =
//             getEl("total-work-time");

//         const breakTotal =
//             getEl("total-break-time");

//         const label =
//             getEl("current-working-label");

//         if (workingTime) {
//             workingTime.textContent =
//                 formatSecondsToClock(
//                     totalWorkSeconds
//                 );
//         }

//         if (workTotal) {
//             workTotal.textContent =
//                 formatSecondsToHourMinute(
//                     totalWorkSeconds
//                 );
//         }

//         if (breakTotal) {
//             breakTotal.textContent =
//                 formatSecondsToHourMinute(
//                     totalBreakSeconds
//                 );
//         }

//         if (!label) {
//             return;
//         }

//         if (status === "On Break") {
//             label.textContent =
//                 "Break in progress";

//             label.classList.remove(
//                 "hidden"
//             );
//         } else if (
//             status === "Day Started"
//             || status === "Working"
//         ) {
//             label.textContent = "";
//             label.classList.add(
//                 "hidden"
//             );
//         } else if (
//             status === "Day Ended"
//         ) {
//             label.textContent =
//                 "Day completed";

//             label.classList.remove(
//                 "hidden"
//             );
//         } else {
//             label.textContent =
//                 "No active session";

//             label.classList.remove(
//                 "hidden"
//             );
//         }
//     };

//     tick();

//     const shouldRunTimer =
//         Boolean(
//             state.boot?.active_work_started_at
//         )
//         || Boolean(
//             state.boot?.active_break_started_at
//         );

//     if (shouldRunTimer) {
//         state.currentWorkTimer =
//             setInterval(tick, 1000);
//     }
// }
function syncCurrentWorkTimer() {
    if (state.currentWorkTimer) {
        clearInterval(state.currentWorkTimer);
        state.currentWorkTimer = null;
    }

    const tick = () => {
        const status =
            state.boot?.status || "Not Started";

        const completedWorkSeconds = Number(
            state.boot?.completed_work_seconds || 0
        );

        const completedBreakSeconds = Number(
            state.boot?.completed_break_seconds || 0
        );

        const activeWorkSeconds =
            state.boot?.active_work_started_at
                ? getElapsedSeconds(
                    state.boot.active_work_started_at
                )
                : 0;

        const activeBreakSeconds =
            state.boot?.active_break_started_at
                ? getElapsedSeconds(
                    state.boot.active_break_started_at
                )
                : 0;

        const totalWorkSeconds =
            completedWorkSeconds
            + activeWorkSeconds;

        const totalBreakSeconds =
            completedBreakSeconds
            + activeBreakSeconds;


        // Elements
        const workingTime =
            getEl("current-working-time");

        const breakTime =
            getEl("current-break-time");

        const workTotal =
            getEl("total-work-time");

        const breakTotal =
            getEl("total-break-time");

        const workLabel =
            getEl("current-working-label");

        const breakLabel =
            getEl("current-break-label");

        const workDot =
            getEl("work-timer-dot");

        const breakDot =
            getEl("break-timer-dot");

        const workPanel =
            getEl("work-timer-panel");

        const breakPanel =
            getEl("break-timer-panel");


        // Timer Values
        if (workingTime) {
            workingTime.textContent =
                formatSecondsToClock(
                    totalWorkSeconds
                );
        }

        /*
         * Cumulative Break Timer:
         * completed breaks + currently running break.
         *
         * Break End par reset nahi hoga.
         */
        if (breakTime) {
            breakTime.textContent =
                formatSecondsToClock(
                    totalBreakSeconds
                );
        }

        if (workTotal) {
            workTotal.textContent =
                formatSecondsToHourMinute(
                    totalWorkSeconds
                );
        }

        if (breakTotal) {
            breakTotal.textContent =
                formatSecondsToHourMinute(
                    totalBreakSeconds
                );
        }


        // Active Timer States
        const isWorkActive =
            Boolean(
                state.boot?.active_work_started_at
            )
            && status !== "On Break"
            && status !== "Day Ended";

        const isBreakActive =
            Boolean(
                state.boot?.active_break_started_at
            )
            && status === "On Break";


        // Dot Animation
        workDot?.classList.toggle(
            "is-active",
            isWorkActive
        );

        breakDot?.classList.toggle(
            "is-active",
            isBreakActive
        );


        // Active Panel Highlight
        workPanel?.classList.toggle(
            "is-active",
            isWorkActive
        );

        breakPanel?.classList.toggle(
            "is-active",
            isBreakActive
        );


        // Work Label
        if (workLabel) {
            if (isWorkActive) {
                workLabel.textContent =
                    "Working now";
            } else if (
                status === "On Break"
            ) {
                workLabel.textContent =
                    "Work timer paused";
            } else if (
                status === "Day Ended"
            ) {
                workLabel.textContent =
                    "Day completed";
            } else {
                workLabel.textContent =
                    "No active session";
            }
        }


        // Break Label
        if (breakLabel) {
            if (isBreakActive) {
                breakLabel.textContent =
                    "Break in progress";
            } else if (
                totalBreakSeconds > 0
                && status !== "Day Ended"
            ) {
                breakLabel.textContent =
                    "Break timer paused";
            } else if (
                status === "Day Ended"
            ) {
                breakLabel.textContent =
                    "Day completed";
            } else {
                breakLabel.textContent =
                    "No break taken";
            }
        }
    };


    // Immediately render.
    tick();


    const shouldRunTimer =
        Boolean(
            state.boot?.active_work_started_at
        )
        || Boolean(
            state.boot?.active_break_started_at
        );

    if (shouldRunTimer) {
        state.currentWorkTimer =
            setInterval(tick, 1000);
    }
}

/* ---------------------------------------------------------
   Buttons
--------------------------------------------------------- */

function setButtonHidden(
    id,
    hidden,
    disabled = false
) {
    const button = getEl(id);

    if (!button) {
        console.error(
            `Button element not found: ${id}`
        );
        return;
    }

    button.classList.toggle(
        "hidden",
        hidden
    );

    button.disabled = Boolean(
        disabled
        || state.attendanceActionInProgress
    );
}

function refreshButtons() {
    const status =
        state.boot?.status
        || "Not Started";

    const setupComplete =
        Boolean(
            state.boot?.setup_complete
        );

    const actionRow =
        getEl("status-action-row");

    const allButtonIds = [
        "btn-entry",
        "btn-break-start",
        "btn-break-end",
        "btn-exit",
        "btn-create-task",
        "btn-start-task",
        "btn-switch-task"
    ];

    allButtonIds.forEach((id) => {
        setButtonHidden(
            id,
            true,
            !setupComplete
        );
    });

    actionRow?.classList.remove(
        "has-single"
    );

    if (!setupComplete) {
        return;
    }

    if (status === "Not Started") {
        setButtonHidden(
            "btn-entry",
            false
        );
    } else if (
        status === "Day Started"
    ) {
        setButtonHidden(
            "btn-break-start",
            false
        );

        setButtonHidden(
            "btn-exit",
            false
        );

        setButtonHidden(
            "btn-create-task",
            false
        );

        setButtonHidden(
            "btn-start-task",
            false
        );
    } else if (
        status === "Working"
    ) {
        setButtonHidden(
            "btn-break-start",
            false
        );

        setButtonHidden(
            "btn-exit",
            false
        );

        setButtonHidden(
            "btn-switch-task",
            false
        );
    } else if (
        status === "On Break"
    ) {
        setButtonHidden(
            "btn-break-end",
            false
        );
    }

    const visibleAttendanceButtons = [
        "btn-entry",
        "btn-break-start",
        "btn-break-end",
        "btn-exit"
    ].filter((id) => {
        const button = getEl(id);

        return button
            && !button.classList
                .contains("hidden");
    });

    if (
        actionRow
        && visibleAttendanceButtons.length <= 1
    ) {
        actionRow.classList.add(
            "has-single"
        );
    }
}


/* ---------------------------------------------------------
   Task Control Lock
--------------------------------------------------------- */

function syncTaskControlLock() {
    const status =
        state.boot?.status
        || "Not Started";

    const card =
        getEl("task-control-card");

    const lock =
        getEl("task-control-lock");

    const title =
        getEl("task-control-lock-title");

    const message =
        getEl("task-control-lock-message");

    if (
        !card
        || !lock
        || !title
        || !message
    ) {
        console.error(
            "Task Control lock elements are missing from HTML."
        );
        return;
    }

    const isWorking =
        status === "Working";

    const isOnBreak =
        status === "On Break";

    const shouldLock =
        isWorking || isOnBreak;

    card.classList.toggle(
        "is-locked",
        shouldLock
    );

    lock.classList.toggle(
        "hidden",
        !shouldLock
    );

    lock.setAttribute(
        "aria-hidden",
        shouldLock ? "false" : "true"
    );

    if (isOnBreak) {
        title.textContent =
            "Break in Progress";

        message.textContent =
            "End your break before starting another task.";

        return;
    }

    title.textContent =
        "Work in Progress";

    message.textContent =
        "Use Stop / Switch Task to finish the current work before selecting another task.";
}


/* ---------------------------------------------------------
   Current Task
--------------------------------------------------------- */

function renderCurrentTaskCard() {
    const currentSession =
        state.boot?.current_work_session
        || null;

    const stateElement =
        getEl("current-task-state");

    const projectElement =
        getEl("current-project");

    const taskElement =
        getEl("current-task");

    const activityElement =
        getEl("current-activity-type");

    const startedElement =
        getEl("current-task-started-at");

    const descriptionElement =
        getEl("current-description");

    if (stateElement) {
        stateElement.textContent =
            state.boot?.status
            || "Not Started";
    }

    if (projectElement) {
        projectElement.textContent =
            currentSession?.project_label
            || "Not Selected";
    }

    if (taskElement) {
        taskElement.textContent =
            currentSession?.task_label
            || "Not Selected";
    }

    if (activityElement) {
        activityElement.textContent =
            currentSession?.activity_type
            || "Not Selected";
    }

    if (startedElement) {
        startedElement.textContent =
            formatTime(
                currentSession?.from_time
            );
    }

    if (descriptionElement) {
        descriptionElement.textContent =
            currentSession?.description
            || "No active task description yet.";
    }
}


/* ---------------------------------------------------------
   Work Sessions
--------------------------------------------------------- */

function renderWorkSessions() {
    const container =
        getEl("work-session-list");

    if (!container) {
        return;
    }

    const sessions = [
        ...(state.boot?.work_sessions || [])
    ].reverse();

    if (!sessions.length) {
        container.innerHTML = `
            <div class="swp-empty-state">
                No work session started yet.
            </div>
        `;

        return;
    }

    container.innerHTML = sessions
        .map((session) => `
            <div class="swp-log-item">
                <div class="swp-log-top">
                    <h4>
                        ${frappe.utils.escape_html(
            session.task_label
            || session.activity_type
            || "Work Session"
        )}
                    </h4>

                    <span class="swp-log-duration">
                        ${formatHoursToClock(
            session.duration_hours || 0
        )}
                    </span>
                </div>

                <div class="swp-log-meta">
                    <span>
                        Project:
                        ${frappe.utils.escape_html(
            session.project_label
            || "-"
        )}
                    </span>

                    <span>
                        Activity:
                        ${frappe.utils.escape_html(
            session.activity_type
            || "-"
        )}
                    </span>

                    <span>
                        Time:
                        ${formatTime(
            session.from_time
        )}
                        -
                        ${session.to_time
                ? formatTime(
                    session.to_time
                )
                : "Running"
            }
                    </span>

                    <span>
                        Description:
                        ${frappe.utils.escape_html(
                session.description
                || "-"
            )}
                    </span>
                </div>
            </div>
        `)
        .join("");
}


/* ---------------------------------------------------------
   Break Logs
--------------------------------------------------------- */

function renderBreakLogs() {
    const container =
        getEl("break-log-list");

    if (!container) {
        return;
    }

    const breaks = [
        ...(state.boot?.break_logs || [])
    ].reverse();

    if (!breaks.length) {
        container.innerHTML = `
            <div class="swp-empty-state">
                No break taken yet.
            </div>
        `;

        return;
    }

    container.innerHTML = breaks
        .map((breakRow, index) => `
            <div class="swp-log-item">
                <div class="swp-log-top">
                    <h4>
                        Break ${breakRow.break_number
            || index + 1
            }
                    </h4>

                    <span class="swp-log-duration">
                        ${formatHoursToClock(
                breakRow.duration_hours
                || 0
            )}
                    </span>
                </div>

                <div class="swp-log-meta">
                    <span>
                        Start:
                        ${formatTime(
                breakRow.break_start
            )}
                    </span>

                    <span>
                        End:
                        ${breakRow.break_end
                ? formatTime(
                    breakRow.break_end
                )
                : "Running"
            }
                    </span>

                    <span>
                        Status:
                        ${frappe.utils.escape_html(
                breakRow.status
                || "Open"
            )}
                    </span>
                </div>
            </div>
        `)
        .join("");
}


/* ---------------------------------------------------------
   Summary
--------------------------------------------------------- */

function renderSetupState() {
    const setupCard =
        getEl("setup-card");

    if (!setupCard) {
        return;
    }

    if (!state.boot?.setup_complete) {
        setupCard.classList.remove(
            "hidden"
        );

        const setupMessage =
            getEl("setup-message");

        if (setupMessage) {
            setupMessage.textContent =
                `Missing setup: ${(
                    state.boot
                        ?.missing_setup
                    || []
                ).join(", ")
                }`;
        }

        showInlineAlert(
            "Please complete the missing setup items first.",
            "error"
        );

        return;
    }

    setupCard.classList.add("hidden");
    hideInlineAlert();
}

function renderSummary() {
    const statusElement =
        getEl("work-status");

    const entryTimeElement =
        getEl("entry-time");

    const exitTimeElement =
        getEl("exit-time");

    if (statusElement) {
        statusElement.textContent =
            state.boot?.status || "Not Started";
    }

    if (entryTimeElement) {
        entryTimeElement.textContent =
            formatTime(
                state.boot?.entry_time
            );
    }

    if (exitTimeElement) {
        exitTimeElement.textContent =
            formatTime(
                state.boot?.exit_time
            );
    }
}

function renderSelectedValues() {
    const selected =
        state.boot?.selected_values
        || {};

    const description =
        getEl("work-description");

    if (description) {
        description.value =
            selected.description || "";
    }
}


/* ---------------------------------------------------------
   Full Page Render
--------------------------------------------------------- */

function renderPage() {
    renderSetupState();
    renderSummary();
    renderGreeting();

    syncAutocompleteValues();
    renderSelectedValues();

    renderCurrentTaskCard();
    renderWorkSessions();
    renderBreakLogs();

    refreshButtons();
    syncTaskControlLock();
    syncCurrentWorkTimer();
}

function setBootState(boot) {
    state.boot = boot || {};
    renderPage();
}


/* ---------------------------------------------------------
   Normal Portal Actions
--------------------------------------------------------- */

async function withAction(
    action,
    successMessage
) {
    try {
        await action();

        // Do not send old Project after Switch.
        // Backend will return current running session,
        // otherwise a clean form.
        const boot =
            await callPortal("get_boot_data");

        setBootState(boot);

        if (successMessage) {
            frappe.show_alert({
                message: successMessage,
                indicator: "green"
            });
        }
    } catch (error) {
        if (!hasServerMessages(error)) {
            frappe.msgprint(
                getErrorMessage(error)
            );
        }
    }
}

function validateWorkForm(values = getFormValues()) {
    const hasWorkInformation = Boolean(
        values.project
        || values.task
        || values.activity_type
        || values.description
    );

    if (!hasWorkInformation) {
        frappe.msgprint(
            "Please select a Project, Task, Activity Type, or enter a Description."
        );

        return false;
    }

    return true;
}


/* ---------------------------------------------------------
   Boot
--------------------------------------------------------- */

async function loadBootData() {
    try {
        const boot =
            await callPortal("get_boot_data");

        setBootState(boot);
    } catch (error) {
        const message = getErrorMessage(
            error,
            __("Unable to load portal data.")
        );

        showInlineAlert(
            message,
            "error"
        );
    }
}


/* ---------------------------------------------------------
   Events
--------------------------------------------------------- */

function bindEvents() {
    getEl("btn-create-task")
        ?.addEventListener(
            "click",
            openCreateTaskDialog
        );

    getEl("btn-close-create-task-modal")
        ?.addEventListener(
            "click",
            closeCreateTaskDialog
        );

    getEl("btn-cancel-create-task")
        ?.addEventListener(
            "click",
            closeCreateTaskDialog
        );

    getEl("btn-submit-create-task")
        ?.addEventListener(
            "click",
            submitCreateTask
        );

    getEl("create-task-modal")
        ?.addEventListener(
            "click",
            (event) => {
                if (
                    event.target.dataset
                        .modalClose
                    === "true"
                ) {
                    closeCreateTaskDialog();
                }
            }
        );

    document.addEventListener(
        "keydown",
        (event) => {
            const modal =
                getEl("create-task-modal");

            if (
                event.key === "Escape"
                && modal
                && !modal.classList
                    .contains("hidden")
            ) {
                closeCreateTaskDialog();
            }
        }
    );

    getEl("btn-entry")
        ?.addEventListener(
            "click",
            (event) => {
                runAttendanceAction(
                    "start_day",
                    "Entry recorded successfully.",
                    event.currentTarget
                );
            }
        );

    getEl("btn-break-start")
        ?.addEventListener(
            "click",
            (event) => {
                runAttendanceAction(
                    "start_break",
                    "Break started successfully.",
                    event.currentTarget
                );
            }
        );

    getEl("btn-break-end")
        ?.addEventListener(
            "click",
            (event) => {
                runAttendanceAction(
                    "end_break",
                    "Break ended successfully.",
                    event.currentTarget
                );
            }
        );

    getEl("btn-exit")
        ?.addEventListener(
            "click",
            (event) => {
                runAttendanceAction(
                    "end_day",
                    "Day ended successfully.",
                    event.currentTarget
                );
            }
        );

    getEl("btn-start-task")
        ?.addEventListener(
            "click",
            async () => {
                const values =
                    getFormValues();

                if (!validateWorkForm(values)) {
                    return;
                }

                await withAction(
                    () => callPortal(
                        "start_work",
                        values
                    ),
                    "Work session started."
                );
            }
        );

    getEl("btn-switch-task")
        ?.addEventListener(
            "click",
            async () => {
                await withAction(
                    () => callPortal(
                        "switch_task"
                    ),
                    "Current work stopped. Select another task and click Start Work."
                );
            }
        );
}


/* ---------------------------------------------------------
   Start Portal
--------------------------------------------------------- */

document.addEventListener(
    "DOMContentLoaded",
    async () => {
        updatePageClock();

        state.pageClockTimer =
            setInterval(
                updatePageClock,
                1000
            );

        initializeAutocompleteFields();
        bindEvents();
        await loadBootData();
    }
);

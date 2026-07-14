const ATTENDANCE_HISTORY_METHOD =
    "employee_portal_get_attendance_history";

const attendanceHistoryState = {
    data: null,
    summary: null,

    loading: false,

    currentPage: 1,
    pageSize: 10
};


/* ---------------------------------------------------------
   Basic Helpers
--------------------------------------------------------- */

function attendanceGetEl(id) {
    return document.getElementById(id);
}

function attendancePad(value) {
    return String(value).padStart(2, "0");
}

function attendanceEscapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}


/* ---------------------------------------------------------
   Date Helpers
--------------------------------------------------------- */

function attendanceToInputDate(date) {
    return [
        date.getFullYear(),
        attendancePad(
            date.getMonth() + 1
        ),
        attendancePad(
            date.getDate()
        )
    ].join("-");
}

function attendanceGetToday() {
    return new Date();
}

function attendanceGetMonthStart() {
    const today =
        attendanceGetToday();

    return new Date(
        today.getFullYear(),
        today.getMonth(),
        1
    );
}

function attendanceParseDateOnly(value) {
    if (!value) {
        return null;
    }

    const parts = String(value)
        .split("-")
        .map(Number);

    if (parts.length !== 3) {
        return null;
    }

    const date = new Date(
        parts[0],
        parts[1] - 1,
        parts[2]
    );

    if (Number.isNaN(date.getTime())) {
        return null;
    }

    return date;
}

function attendanceGetDateDifference(
    fromDateValue,
    toDateValue
) {
    const fromDate =
        attendanceParseDateOnly(
            fromDateValue
        );

    const toDate =
        attendanceParseDateOnly(
            toDateValue
        );

    if (!fromDate || !toDate) {
        return null;
    }

    const difference =
        toDate.getTime()
        - fromDate.getTime();

    return Math.floor(
        difference
        / (1000 * 60 * 60 * 24)
    );
}

function attendanceFormatDate(value) {
    const date =
        attendanceParseDateOnly(value);

    if (!date) {
        return {
            date: "--",
            day: ""
        };
    }

    return {
        date: date.toLocaleDateString(
            "en-IN",
            {
                day: "2-digit",
                month: "short",
                year: "numeric"
            }
        ),

        day: date.toLocaleDateString(
            "en-IN",
            {
                weekday: "long"
            }
        )
    };
}


/* ---------------------------------------------------------
   Time Helpers
--------------------------------------------------------- */

function attendanceParseDateTime(value) {
    if (!value) {
        return null;
    }

    if (value instanceof Date) {
        return value;
    }

    let normalizedValue = String(value)
        .trim()
        .replace(" ", "T");

    /*
     * Frappe can return microseconds with
     * more than 3 digits.
     */
    normalizedValue =
        normalizedValue.replace(
            /(\.\d{3})\d+/,
            "$1"
        );

    const date =
        new Date(normalizedValue);

    if (Number.isNaN(date.getTime())) {
        return null;
    }

    return date;
}

function attendanceFormatTime(value) {
    const date =
        attendanceParseDateTime(value);

    if (!date) {
        return "--";
    }

    return date.toLocaleTimeString(
        "en-IN",
        {
            hour: "2-digit",
            minute: "2-digit",
            hour12: true
        }
    );
}

function attendanceFormatDuration(
    totalSeconds
) {
    const safeSeconds = Math.max(
        Math.floor(
            Number(totalSeconds) || 0
        ),
        0
    );

    const totalMinutes = Math.floor(
        safeSeconds / 60
    );

    const hours = Math.floor(
        totalMinutes / 60
    );

    const minutes =
        totalMinutes % 60;

    return (
        `${attendancePad(hours)}:`
        + `${attendancePad(minutes)}`
    );
}


/* ---------------------------------------------------------
   Error Helpers
--------------------------------------------------------- */

function attendanceGetErrorMessage(
    error,
    fallback =
        "Unable to load attendance history."
) {
    const serverMessages =
        error?._server_messages
        || error?.responseJSON
            ?._server_messages;

    if (serverMessages) {
        try {
            const parsedMessages =
                JSON.parse(serverMessages);

            if (parsedMessages?.length) {
                const firstMessage =
                    JSON.parse(
                        parsedMessages[0]
                    );

                if (
                    typeof firstMessage
                    === "string"
                ) {
                    return firstMessage;
                }

                if (
                    firstMessage?.message
                ) {
                    return (
                        firstMessage.message
                    );
                }
            }
        } catch (parseError) {
            // Use fallback below.
        }
    }

    return (
        error?.message
        || error?.responseJSON?.exception
        || fallback
    );
}

function attendanceShowAlert(
    message,
    type = "error"
) {
    const alert =
        attendanceGetEl(
            "history-alert"
        );

    if (!alert) {
        return;
    }

    alert.textContent = message;

    alert.className =
        `sah-alert sah-alert-${type}`;
}

function attendanceHideAlert() {
    const alert =
        attendanceGetEl(
            "history-alert"
        );

    if (!alert) {
        return;
    }

    alert.textContent = "";
    alert.className =
        "sah-alert hidden";
}


/* ---------------------------------------------------------
   Loading State
--------------------------------------------------------- */

function attendanceSetLoading(
    isLoading
) {
    attendanceHistoryState.loading =
        isLoading;

    const applyButton =
        attendanceGetEl(
            "btn-apply-filter"
        );

    const currentMonthButton =
        attendanceGetEl(
            "btn-current-month"
        );

    if (applyButton) {
        applyButton.disabled =
            isLoading;

        applyButton.textContent =
            isLoading
                ? "Loading..."
                : "Apply Filter";
    }

    if (currentMonthButton) {
        currentMonthButton.disabled =
            isLoading;
    }

    if (!isLoading) {
        return;
    }

    const tableBody =
        attendanceGetEl(
            "attendance-table-body"
        );

    if (tableBody) {
        tableBody.innerHTML = `
            <tr>
                <td
                    colspan="10"
                    class="sah-table-message"
                >
                    <div class="sah-loading">
                        <span
                            class="sah-spinner"
                        ></span>

                        Loading attendance history...
                    </div>
                </td>
            </tr>
        `;
    }
}


/* ---------------------------------------------------------
   Employee Card
--------------------------------------------------------- */

function attendanceRenderEmployee(
    employee
) {
    const employeeName =
        employee?.employee_name
        || "Employee";

    const initial = employeeName
        .trim()
        .charAt(0)
        .toUpperCase()
        || "E";

    const nameElement =
        attendanceGetEl(
            "employee-name"
        );

    const initialElement =
        attendanceGetEl(
            "employee-initial"
        );

    const idElement =
        attendanceGetEl(
            "employee-id"
        );

    const departmentElement =
        attendanceGetEl(
            "employee-department"
        );

    const companyElement =
        attendanceGetEl(
            "employee-company"
        );

    if (nameElement) {
        nameElement.textContent =
            employeeName;
    }

    if (initialElement) {
        initialElement.textContent =
            initial;
    }

    if (idElement) {
        idElement.textContent =
            employee?.name || "--";
    }

    if (departmentElement) {
        departmentElement.textContent =
            employee?.department
            || "No Department";
    }

    if (companyElement) {
        companyElement.textContent =
            employee?.company
            || "No Company";
    }
}


/* ---------------------------------------------------------
   Full Filter Summary
--------------------------------------------------------- */

function attendanceRenderSummary(
    summary
) {
    const daysInRange = Number(
        summary?.days_in_range || 0
    );

    const workedDays = Number(
        summary?.worked_days || 0
    );

    const totalWorkSeconds = Number(
        summary?.total_work_seconds || 0
    );

    const totalBreakSeconds = Number(
        summary?.total_break_seconds || 0
    );

    const averageWorkSeconds = Number(
        summary?.average_work_seconds || 0
    );

    const workedDaysElement =
        attendanceGetEl(
            "summary-active-days"
        );

    const rangeDaysElement =
        attendanceGetEl(
            "summary-range-days"
        );

    const workElement =
        attendanceGetEl(
            "summary-work-time"
        );

    const breakElement =
        attendanceGetEl(
            "summary-break-time"
        );

    const averageElement =
        attendanceGetEl(
            "summary-average-time"
        );

    if (workedDaysElement) {
        workedDaysElement.textContent =
            workedDays;
    }

    if (rangeDaysElement) {
        rangeDaysElement.textContent =
            `Across ${daysInRange}`
            + " selected days";
    }

    if (workElement) {
        workElement.textContent =
            attendanceFormatDuration(
                totalWorkSeconds
            );
    }

    if (breakElement) {
        breakElement.textContent =
            attendanceFormatDuration(
                totalBreakSeconds
            );
    }

    if (averageElement) {
        averageElement.textContent =
            attendanceFormatDuration(
                averageWorkSeconds
            );
    }
}


/* ---------------------------------------------------------
   Attendance Status Badge
--------------------------------------------------------- */

function attendanceGetAttendanceClass(
    status
) {
    const statusValue =
        String(status || "")
            .toLowerCase();

    if (statusValue === "present") {
        return "sah-badge-success";
    }

    if (statusValue === "absent") {
        return "sah-badge-danger";
    }

    if (
        statusValue === "half day"
    ) {
        return "sah-badge-warning";
    }

    if (
        statusValue === "on leave"
    ) {
        return "sah-badge-purple";
    }

    if (
        statusValue
        === "work from home"
    ) {
        return "sah-badge-primary";
    }

    return "sah-badge-neutral";
}

function attendanceGetPortalClass(
    status
) {
    const statusValue =
        String(status || "")
            .toLowerCase();

    if (
        statusValue === "day ended"
    ) {
        return "sah-badge-success";
    }

    if (
        statusValue === "working"
        || statusValue
        === "day started"
    ) {
        return "sah-badge-primary";
    }

    if (
        statusValue === "on break"
    ) {
        return "sah-badge-warning";
    }

    if (
        statusValue === "incomplete"
    ) {
        return "sah-badge-danger";
    }

    return "sah-badge-neutral";
}


/* ---------------------------------------------------------
   Remarks
--------------------------------------------------------- */

function attendanceRenderRemarks(row) {
    const remarks = [];

    if (
        Number(
            row?.late_entry || 0
        )
    ) {
        remarks.push(`
            <span
                class="
                    sah-flag
                    sah-flag-warning
                "
            >
                Late Entry
            </span>
        `);
    }

    if (
        Number(
            row?.early_exit || 0
        )
    ) {
        remarks.push(`
            <span
                class="
                    sah-flag
                    sah-flag-danger
                "
            >
                Early Exit
            </span>
        `);
    }

    if (
        Number(
            row?.is_incomplete || 0
        )
    ) {
        remarks.push(`
            <span
                class="
                    sah-flag
                    sah-flag-danger
                "
            >
                Incomplete
            </span>
        `);
    }

    if (!remarks.length) {
        return `
            <span class="sah-empty-value">
                -
            </span>
        `;
    }

    return `
        <div class="sah-flags">
            ${remarks.join("")}
        </div>
    `;
}


/* ---------------------------------------------------------
   Server-side Pagination
--------------------------------------------------------- */

function attendanceGetVisiblePages(
    currentPage,
    totalPages
) {
    const maximumVisiblePages = 5;

    let startPage = Math.max(
        currentPage - 2,
        1
    );

    let endPage = Math.min(
        startPage
        + maximumVisiblePages
        - 1,
        totalPages
    );

    if (
        endPage
        - startPage
        + 1
        < maximumVisiblePages
    ) {
        startPage = Math.max(
            endPage
            - maximumVisiblePages
            + 1,
            1
        );
    }

    const pages = [];

    for (
        let page = startPage;
        page <= endPage;
        page += 1
    ) {
        pages.push(page);
    }

    return pages;
}

function attendanceRenderPagination(
    paginationData
) {
    const pagination =
        attendanceGetEl(
            "attendance-pagination"
        );

    if (!pagination) {
        return;
    }

    const currentPage = Number(
        paginationData?.current_page
        || 1
    );

    const pageSize = Number(
        paginationData?.page_size
        || attendanceHistoryState
            .pageSize
        || 10
    );

    const totalPages = Number(
        paginationData?.total_pages
        || 1
    );

    const totalRecords = Number(
        paginationData?.total_records
        || 0
    );

    const fromRecord = Number(
        paginationData?.from_record
        || 0
    );

    const toRecord = Number(
        paginationData?.to_record
        || 0
    );

    attendanceHistoryState.currentPage =
        currentPage;

    attendanceHistoryState.pageSize =
        pageSize;

    if (
        totalPages <= 1
        || totalRecords <= pageSize
    ) {
        pagination.innerHTML = "";

        pagination.classList.add(
            "hidden"
        );

        return;
    }

    pagination.classList.remove(
        "hidden"
    );

    const visiblePages =
        attendanceGetVisiblePages(
            currentPage,
            totalPages
        );

    const pageButtons = visiblePages
        .map((page) => {
            const activeClass =
                page === currentPage
                    ? "is-active"
                    : "";

            const currentAttribute =
                page === currentPage
                    ? 'aria-current="page"'
                    : "";

            return `
                <button
                    type="button"
                    class="
                        sah-page-button
                        ${activeClass}
                    "
                    data-page="${page}"
                    ${currentAttribute}
                >
                    ${page}
                </button>
            `;
        })
        .join("");

    pagination.innerHTML = `
        <div
            class="sah-pagination-summary"
        >
            Showing

            <strong>
                ${fromRecord}-${toRecord}
            </strong>

            of

            <strong>
                ${totalRecords}
            </strong>

            records
        </div>

        <div
            class="sah-pagination-controls"
        >
            <button
                type="button"
                class="sah-page-navigation"
                data-page-action="previous"
                ${currentPage <= 1
            ? "disabled"
            : ""
        }
            >
                Previous
            </button>

            <div class="sah-page-numbers">
                ${pageButtons}
            </div>

            <button
                type="button"
                class="sah-page-navigation"
                data-page-action="next"
                ${currentPage >= totalPages
            ? "disabled"
            : ""
        }
            >
                Next
            </button>
        </div>
    `;
}

async function attendanceChangePage(
    page
) {
    if (
        attendanceHistoryState.loading
    ) {
        return;
    }

    const totalPages = Number(
        attendanceHistoryState
            .data
            ?.pagination
            ?.total_pages
        || 1
    );

    const requestedPage =
        Number(page);

    if (
        !requestedPage
        || requestedPage < 1
        || requestedPage > totalPages
    ) {
        return;
    }

    /*
     * Pagination does not request summary again.
     * Existing filter summary remains unchanged.
     */
    await attendanceLoadHistory(
        requestedPage,
        true,
        false
    );
}

function attendanceHandlePaginationClick(
    event
) {
    const button =
        event.target.closest(
            "button"
        );

    if (
        !button
        || button.disabled
    ) {
        return;
    }

    const directPage =
        button.dataset.page;

    if (directPage) {
        attendanceChangePage(
            Number(directPage)
        );

        return;
    }

    const action =
        button.dataset.pageAction;

    const currentPage =
        attendanceHistoryState
            .currentPage;

    if (action === "previous") {
        attendanceChangePage(
            currentPage - 1
        );

        return;
    }

    if (action === "next") {
        attendanceChangePage(
            currentPage + 1
        );
    }
}


/* ---------------------------------------------------------
   Table
--------------------------------------------------------- */

function attendanceRenderTable(
    rows,
    pagination
) {
    const tableBody =
        attendanceGetEl(
            "attendance-table-body"
        );

    const recordCount =
        attendanceGetEl(
            "record-count"
        );

    if (!tableBody) {
        return;
    }

    const safeRows =
        Array.isArray(rows)
            ? rows
            : [];

    const totalRecords = Number(
        pagination?.total_records
        || 0
    );

    const fromRecord = Number(
        pagination?.from_record
        || 0
    );

    const toRecord = Number(
        pagination?.to_record
        || 0
    );

    if (recordCount) {
        recordCount.textContent =
            totalRecords > 0
                ? `${fromRecord}-${toRecord}`
                + ` of ${totalRecords}`
                : "0 Records";
    }

    if (!safeRows.length) {
        tableBody.innerHTML = `
            <tr>
                <td
                    colspan="10"
                    class="sah-table-message"
                >
                    No attendance records found
                    for selected date range.
                </td>
            </tr>
        `;

        return;
    }

    tableBody.innerHTML = safeRows
        .map((row) => {
            const formattedDate =
                attendanceFormatDate(
                    row.date
                );

            const attendanceStatus =
                row.attendance_status
                || "Not Marked";

            const portalStatus =
                row.portal_status
                || "No Activity";

            const hasActivity =
                Number(
                    row.has_activity
                    || 0
                );

            const rowClass =
                hasActivity
                    ? ""
                    : "sah-row-no-activity";

            return `
                <tr class="${rowClass}">
                    <td>
                        <div
                            class="sah-date-cell"
                        >
                            <strong>
                                ${attendanceEscapeHtml(
                formattedDate
                    .date
            )}
                            </strong>

                            <span>
                                ${attendanceEscapeHtml(
                formattedDate
                    .day
            )}
                            </span>
                        </div>
                    </td>

                    <td>
                        <span
                            class="
                                sah-badge
                                ${attendanceGetAttendanceClass(
                attendanceStatus
            )}
                            "
                        >
                            ${attendanceEscapeHtml(
                attendanceStatus
            )}
                        </span>
                    </td>

                    <td>
                        <span
                            class="
                                sah-badge
                                ${attendanceGetPortalClass(
                portalStatus
            )}
                            "
                        >
                            ${attendanceEscapeHtml(
                portalStatus
            )}
                        </span>
                    </td>

                    <td
                        class="sah-time-value"
                    >
                        ${attendanceFormatTime(
                row.entry_time
            )}
                    </td>

                    <td
                        class="sah-time-value"
                    >
                        ${attendanceFormatTime(
                row.exit_time
            )}
                    </td>

                    <td>
                        <strong
                            class="sah-work-time"
                        >
                            ${attendanceFormatDuration(
                row.work_seconds
            )}
                        </strong>
                    </td>

                    <td>
                        <strong
                            class="sah-break-time"
                        >
                            ${attendanceFormatDuration(
                row.break_seconds
            )}
                        </strong>
                    </td>

                    <td
                        class="sah-number-value"
                    >
                        ${Number(
                row.break_count
                || 0
            )}
                    </td>

                    <td>
                        <span
                            class="sah-shift-value"
                        >
                            ${attendanceEscapeHtml(
                row.shift || "-"
            )}
                        </span>
                    </td>

                    <td>
                        ${attendanceRenderRemarks(
                row
            )}
                    </td>
                </tr>
            `;
        })
        .join("");
}


/* ---------------------------------------------------------
   Range Label
--------------------------------------------------------- */

function attendanceRenderRange(
    filters
) {
    const label =
        attendanceGetEl(
            "history-range-label"
        );

    if (!label) {
        return;
    }

    const fromDate =
        attendanceFormatDate(
            filters?.from_date
        ).date;

    const toDate =
        attendanceFormatDate(
            filters?.to_date
        ).date;

    label.textContent =
        `${fromDate} to ${toDate}`;
}


/* ---------------------------------------------------------
   Full Page Render
--------------------------------------------------------- */

function attendanceRenderPage(data) {
    attendanceHistoryState.data =
        data || {};

    attendanceHistoryState.currentPage =
        Number(
            data?.pagination
                ?.current_page
            || 1
        );

    attendanceHistoryState.pageSize =
        Number(
            data?.pagination?.page_size
            || attendanceHistoryState
                .pageSize
            || 10
        );


    attendanceRenderEmployee(
        data?.employee || {}
    );


    /*
     * API sends summary only when:
     * include_summary = 1
     *
     * Pagination response has summary = null.
     */
    if (data?.summary) {
        attendanceHistoryState.summary =
            data.summary;

        attendanceRenderSummary(
            data.summary
        );
    } else if (
        attendanceHistoryState.summary
    ) {
        attendanceRenderSummary(
            attendanceHistoryState.summary
        );
    }


    attendanceRenderTable(
        data?.rows || [],
        data?.pagination || {}
    );

    attendanceRenderPagination(
        data?.pagination || {}
    );

    attendanceRenderRange(
        data?.filters || {}
    );
}


/* ---------------------------------------------------------
   Filter Validation
--------------------------------------------------------- */

function attendanceValidateFilters() {
    const fromDate =
        attendanceGetEl("from-date")
            ?.value || "";

    const toDate =
        attendanceGetEl("to-date")
            ?.value || "";

    if (!fromDate || !toDate) {
        attendanceShowAlert(
            "Please select From Date and To Date."
        );

        return null;
    }

    const dateDifference =
        attendanceGetDateDifference(
            fromDate,
            toDate
        );

    if (dateDifference === null) {
        attendanceShowAlert(
            "Please select valid dates."
        );

        return null;
    }

    if (dateDifference < 0) {
        attendanceShowAlert(
            "From Date cannot be greater than To Date."
        );

        return null;
    }

    return {
        from_date: fromDate,
        to_date: toDate
    };
}


/* ---------------------------------------------------------
   API
--------------------------------------------------------- */

async function attendanceLoadHistory(
    page = 1,
    scrollToTable = false,
    includeSummary = false
) {
    if (
        attendanceHistoryState.loading
    ) {
        return;
    }

    attendanceHideAlert();

    const filters =
        attendanceValidateFilters();

    if (!filters) {
        return;
    }

    attendanceSetLoading(true);

    try {
        const response =
            await frappe.call({
                method:
                    ATTENDANCE_HISTORY_METHOD,

                args: {
                    ...filters,

                    page:
                        Number(page) || 1,

                    include_summary:
                        includeSummary
                            ? 1
                            : 0
                }
            });

        const responseData =
            response.message || {};

        attendanceRenderPage(
            responseData
        );

        if (scrollToTable) {
            document
                .querySelector(
                    ".sah-table-card"
                )
                ?.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });
        }
    } catch (error) {
        const message =
            attendanceGetErrorMessage(
                error
            );

        attendanceShowAlert(
            message,
            "error"
        );

        const tableBody =
            attendanceGetEl(
                "attendance-table-body"
            );

        if (tableBody) {
            tableBody.innerHTML = `
                <tr>
                    <td
                        colspan="10"
                        class="
                            sah-table-message
                            sah-table-error
                        "
                    >
                        ${attendanceEscapeHtml(
                message
            )}
                    </td>
                </tr>
            `;
        }
    } finally {
        attendanceSetLoading(false);
    }
}


/* ---------------------------------------------------------
   Filter Defaults
--------------------------------------------------------- */

function attendanceSetCurrentMonth() {
    const fromDate =
        attendanceGetEl(
            "from-date"
        );

    const toDate =
        attendanceGetEl(
            "to-date"
        );

    if (fromDate) {
        fromDate.value =
            attendanceToInputDate(
                attendanceGetMonthStart()
            );
    }

    if (toDate) {
        toDate.value =
            attendanceToInputDate(
                attendanceGetToday()
            );
    }
}


/* ---------------------------------------------------------
   Events
--------------------------------------------------------- */

function attendanceBindEvents() {
    attendanceGetEl(
        "btn-apply-filter"
    )?.addEventListener(
        "click",
        async () => {
            /*
             * New filter:
             * Page 1 + complete summary.
             */
            await attendanceLoadHistory(
                1,
                false,
                true
            );
        }
    );

    attendanceGetEl(
        "btn-current-month"
    )?.addEventListener(
        "click",
        async () => {
            attendanceSetCurrentMonth();

            /*
             * Current Month:
             * Page 1 + complete summary.
             */
            await attendanceLoadHistory(
                1,
                false,
                true
            );
        }
    );

    attendanceGetEl(
        "attendance-pagination"
    )?.addEventListener(
        "click",
        attendanceHandlePaginationClick
    );

    attendanceGetEl(
        "from-date"
    )?.addEventListener(
        "keydown",
        async (event) => {
            if (event.key === "Enter") {
                await attendanceLoadHistory(
                    1,
                    false,
                    true
                );
            }
        }
    );

    attendanceGetEl(
        "to-date"
    )?.addEventListener(
        "keydown",
        async (event) => {
            if (event.key === "Enter") {
                await attendanceLoadHistory(
                    1,
                    false,
                    true
                );
            }
        }
    );
}


/* ---------------------------------------------------------
   Initialize
--------------------------------------------------------- */

async function attendanceInitializePage() {
    attendanceSetCurrentMonth();
    attendanceBindEvents();

    /*
     * Initial load:
     * Page 1 + current month full summary.
     */
    await attendanceLoadHistory(
        1,
        false,
        true
    );
}

if (
    document.readyState
    === "loading"
) {
    document.addEventListener(
        "DOMContentLoaded",
        attendanceInitializePage
    );
} else {
    attendanceInitializePage();
}
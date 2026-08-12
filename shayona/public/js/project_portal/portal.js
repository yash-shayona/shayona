const projectPortalState = {
    initialized: false,
    dashboard: null,
    currentWorkTimer: null,
    projects: {
        loaded: false,
        loading: false,
        requestId: 0,
        searchTimer: null,
        filters: {
            search: "",
            status: "Open",
            sort: "recent"
        },
        page: 1,
        pageLength: 10,
        rows: [],
        pagination: {
            page: 1,
            page_length: 10,
            has_previous: false,
            has_more: false,
            total_records: 0,
            total_pages: 0
        }
    },
    // This state keeps My Tasks filters and the currently opened detail drawer independent.
    myTasks: {
        loading: false,
        requestId: 0,
        detailRequestId: 0,
        detail: null,
        editing: false,
        saving: false,
        workingTask: "",
        updating: false,
        searchTimer: null,
        filters: {
            search: "",
            status: "All",
            priority: "All",
            due: "All"
        },
        page: 1,
        pageLength: 10,
        rows: [],
        pagination: {
            page: 1,
            page_length: 10,
            has_previous: false,
            has_more: false,
            total_records: 0,
            total_pages: 0
        }
    },
    // This is a read-only view of the logged-in employee's standard ERPNext Timesheets.
    timesheets: {
        loading: false,
        requestId: 0,
        filters: {
            period: "This Week",
            status: "All"
        },
        page: 1,
        pageLength: 10,
        rows: [],
        summary: null,
        pagination: {
            page: 1,
            page_length: 10,
            has_previous: false,
            has_more: false,
            total_records: 0,
            total_pages: 0
        }
    },
    // The Task Board is a separate, non-paginated view of the current user's active Task statuses.
    taskBoard: {
        loading: false,
        requestId: 0,
        searchTimer: null,
        search: "",
        statuses: [],
        rows: [],
        isTruncated: false,
        boardLimit: 0,
        movingTask: "",
        workingTask: "",
        activeWork: null
    },
    // Portal alerts are intentionally separate from Frappe Desk's global notification list.
    notifications: {
        loading: false,
        requestId: 0,
        rows: [],
        unreadCount: 0
    },
    // This state keeps one selected Project workspace separate from the Projects list.
    workspace: {
        projectName: "",
        loading: false,
        requestId: 0,
        searchTimer: null,
        data: null,
        filters: {
            search: "",
            status: "All"
        },
        page: 1,
        pageLength: 10,
        pagination: {
            page: 1,
            page_length: 10,
            has_previous: false,
            has_more: false,
            total_records: 0,
            total_pages: 0
        }
    }
};

const PORTAL_API_BASE = "shayona.api.portal.project_portal.";

const PROJECT_PORTAL_METHODS = {
    get_dashboard: `${PORTAL_API_BASE}employee_project_portal_get_dashboard`,
    get_projects: `${PORTAL_API_BASE}employee_project_portal_get_projects`,
    get_project_workspace: `${PORTAL_API_BASE}employee_project_portal_get_project_workspace`,
    get_my_tasks: `${PORTAL_API_BASE}employee_project_portal_get_my_tasks`,
    get_my_timesheets: `${PORTAL_API_BASE}employee_project_portal_get_my_timesheets`,
    get_task_board: `${PORTAL_API_BASE}employee_project_portal_get_task_board`,
    get_task_details: `${PORTAL_API_BASE}employee_project_portal_get_task_details`,
    update_my_task: `${PORTAL_API_BASE}employee_project_portal_update_my_task`,
    start_my_task_work: `${PORTAL_API_BASE}employee_project_portal_start_my_task_work`,
    stop_my_task_work: `${PORTAL_API_BASE}employee_project_portal_stop_my_task_work`,
    add_task_update: `${PORTAL_API_BASE}employee_project_portal_add_task_update`,
    upload_task_attachment: `${PORTAL_API_BASE}employee_project_portal_upload_task_attachment`,
    get_notifications: `${PORTAL_API_BASE}employee_project_portal_get_notifications`,
    mark_notifications_read: `${PORTAL_API_BASE}employee_project_portal_mark_notifications_read`
};

function eppGetEl(id) {
    return document.getElementById(id);
}

// This reads which standalone website route rendered the shared portal shell.
function eppGetPortalPage() {
    return document.querySelector(".epp-layout")?.dataset.eppPage || "";
}

// This reads the Project name extracted by Frappe's dynamic website route.
function eppGetRouteProjectName() {
    return document.querySelector(".epp-layout")?.dataset.eppProjectName || "";
}

function eppPad(value) {
    return String(value).padStart(2, "0");
}

function eppEscapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function eppToDate(value) {
    if (!value) {
        return null;
    }

    if (value instanceof Date) {
        return value;
    }

    const stringValue = String(value).trim();
    const dateOnlyMatch = stringValue.match(
        /^(\d{4})-(\d{2})-(\d{2})$/
    );

    if (dateOnlyMatch) {
        return new Date(
            Number(dateOnlyMatch[1]),
            Number(dateOnlyMatch[2]) - 1,
            Number(dateOnlyMatch[3])
        );
    }

    const parsedDate = new Date(
        stringValue.replace(" ", "T")
    );

    if (Number.isNaN(parsedDate.getTime())) {
        return null;
    }

    return parsedDate;
}

function eppGetElapsedSeconds(startValue) {
    const startDate = eppToDate(startValue);

    if (!startDate) {
        return 0;
    }

    return Math.max(
        Math.floor(
            (Date.now() - startDate.getTime()) / 1000
        ),
        0
    );
}

function eppFormatSeconds(totalSeconds) {
    const safeSeconds = Math.max(
        Math.floor(Number(totalSeconds) || 0),
        0
    );

    const hours = Math.floor(safeSeconds / 3600);
    const minutes = Math.floor((safeSeconds % 3600) / 60);
    const seconds = safeSeconds % 60;

    return [
        eppPad(hours),
        eppPad(minutes),
        eppPad(seconds)
    ].join(":");
}

function eppFormatTime(value) {
    const date = eppToDate(value);

    if (!date) {
        return "--";
    }

    return date.toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: true
    }).toUpperCase();
}

function eppFormatDate(value) {
    const date = eppToDate(value);

    if (!date) {
        return "--";
    }

    return date.toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric"
    });
}

function eppFormatDateTime(value) {
    const date = eppToDate(value);

    if (!date) {
        return "--";
    }

    return `${date.toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric"
    })} · ${date.toLocaleTimeString("en-IN", {
        hour: "numeric",
        minute: "2-digit",
        hour12: true
    })}`;
}

function eppGetDeadlineParts(value) {
    const date = eppToDate(value);

    if (!date) {
        return {
            day: "--",
            month: "--"
        };
    }

    return {
        day: eppPad(date.getDate()),
        month: date.toLocaleDateString("en-IN", {
            month: "short"
        })
    };
}

function eppGetRelativeTime(value) {
    const date = eppToDate(value);

    if (!date) {
        return "";
    }

    const seconds = Math.floor(
        (Date.now() - date.getTime()) / 1000
    );

    if (seconds < 0) {
        return eppFormatDate(value);
    }

    if (seconds < 60) {
        return "Just now";
    }

    const minutes = Math.floor(seconds / 60);

    if (minutes < 60) {
        return `${minutes} min ago`;
    }

    const hours = Math.floor(minutes / 60);

    if (hours < 24) {
        return `${hours} hr ago`;
    }

    const days = Math.floor(hours / 24);

    if (days === 1) {
        return "Yesterday";
    }

    if (days < 7) {
        return `${days} days ago`;
    }

    return eppFormatDate(value);
}

function eppGetInitials(name) {
    const words = String(name || "")
        .trim()
        .split(/\s+/)
        .filter(Boolean);

    if (!words.length) {
        return "U";
    }

    if (words.length === 1) {
        return words[0].slice(0, 2).toUpperCase();
    }

    return (
        words[0][0]
        + words[words.length - 1][0]
    ).toUpperCase();
}

function eppClampPercentage(value) {
    return Math.min(
        Math.max(Number(value) || 0, 0),
        100
    );
}

function eppSetText(id, value) {
    const element = eppGetEl(id);

    if (element) {
        element.textContent = value;
    }
}

function eppGetPriorityClass(priority) {
    const value = String(priority || "").toLowerCase();

    if (value === "high") {
        return "is-high";
    }

    if (value === "medium") {
        return "is-medium";
    }

    return "";
}

function eppGetStatusClass(status) {
    return String(status || "").toLowerCase() === "completed"
        ? "is-completed"
        : "";
}

function eppGetProjectStatusClass(status) {
    const value = String(status || "").toLowerCase();

    if (value === "completed") {
        return "is-completed";
    }

    if (value === "cancelled") {
        return "is-cancelled";
    }

    return "";
}

function eppGetErrorMessage(
    error,
    fallback = "Something went wrong."
) {
    const serverMessages =
        error?._server_messages
        || error?.responseJSON?._server_messages;

    if (serverMessages) {
        try {
            const parsedMessages = JSON.parse(serverMessages);

            for (const rawMessage of parsedMessages) {
                let parsedMessage = rawMessage;

                try {
                    parsedMessage = JSON.parse(rawMessage);
                } catch (parseError) {
                    // Keep the original value.
                }

                if (typeof parsedMessage === "string") {
                    return parsedMessage;
                }

                if (parsedMessage?.message) {
                    return parsedMessage.message;
                }
            }
        } catch (parseError) {
            // Continue to normal fallback.
        }
    }

    return (
        error?.responseJSON?.message
        || error?.message
        || fallback
    );
}

function eppShowDashboardAlert(message, type = "info") {
    const alert = eppGetEl("dashboard-alert");

    if (!alert) {
        return;
    }

    alert.textContent = message;
    alert.className = `epp-alert epp-alert-${type}`;
}

function eppHideDashboardAlert() {
    const alert = eppGetEl("dashboard-alert");

    if (!alert) {
        return;
    }

    alert.textContent = "";
    alert.className = "epp-alert hidden";
}

function eppShowProjectsError(message) {
    const element = eppGetEl("projects-error");

    if (!element) {
        return;
    }

    element.textContent = message;
    element.classList.remove("hidden");
}

function eppHideProjectsError() {
    const element = eppGetEl("projects-error");

    if (!element) {
        return;
    }

    element.textContent = "";
    element.classList.add("hidden");
}

async function eppCallPortal(method, args = {}) {
    const apiMethod = PROJECT_PORTAL_METHODS[method];

    if (!apiMethod) {
        throw new Error(
            `Project Portal method is not configured: ${method}`
        );
    }

    const response = await frappe.call({
        method: apiMethod,
        args
    });

    return response.message;
}

function eppRenderHeader() {
    const user = projectPortalState.dashboard?.user || {};
    const employeeName = user.employee_name || "Employee";
    const initials = eppGetInitials(employeeName);

    eppSetText("sidebar-user-name", employeeName);
    eppSetText(
        "sidebar-user-department",
        user.department || user.company || "Employee"
    );
    eppSetText("sidebar-user-avatar", initials);
}

function eppSetNotificationDrawerOpen(isOpen) {
    const drawer = eppGetEl("project-portal-notification-drawer");
    const backdrop = eppGetEl("project-portal-notification-backdrop");
    const trigger = eppGetEl("btn-project-portal-notifications");

    if (isOpen) {
        eppCloseSidebar();
        eppCloseMyTaskDrawer();
    }

    drawer?.classList.toggle("is-open", isOpen);
    drawer?.setAttribute("aria-hidden", String(!isOpen));
    backdrop?.classList.toggle("hidden", !isOpen);
    trigger?.setAttribute("aria-expanded", String(isOpen));
    document.body.style.overflow = isOpen ? "hidden" : "";
}

function eppCloseNotificationDrawer() {
    eppSetNotificationDrawerOpen(false);
}

function eppRenderNotificationBadge() {
    const notifications = projectPortalState.notifications;
    const badge = eppGetEl("project-portal-notification-count");
    const button = eppGetEl("btn-project-portal-notifications");
    const unreadCount = Math.max(0, Number(notifications.unreadCount) || 0);

    if (badge) {
        badge.textContent = unreadCount > 99 ? "99+" : String(unreadCount);
        badge.classList.toggle("hidden", !unreadCount);
    }

    button?.setAttribute(
        "aria-label",
        unreadCount ? `Notifications, ${unreadCount} unread` : "Notifications"
    );
}

function eppRenderNotifications() {
    const notifications = projectPortalState.notifications;
    const container = eppGetEl("project-portal-notification-list");
    const markAllButton = eppGetEl("btn-mark-project-portal-notifications-read");

    eppRenderNotificationBadge();

    if (markAllButton) {
        markAllButton.disabled = notifications.loading || !notifications.unreadCount;
    }

    if (!container) {
        return;
    }

    if (notifications.loading && !notifications.rows.length) {
        container.innerHTML = `<div class="epp-loading-state">Loading notifications...</div>`;
        return;
    }

    if (!notifications.rows.length) {
        container.innerHTML = `
            <div class="epp-notification-empty">
                <strong>You're all caught up.</strong>
                <span>Due dates and blocker updates will appear here.</span>
            </div>
        `;
        return;
    }

    container.innerHTML = notifications.rows.map((notification) => {
        const taskReference = notification.document_type === "Task" && notification.document_name
            ? `<span>${eppEscapeHtml(notification.document_name)}</span>`
            : "";
        const taskLink = notification.link
            ? `<a href="${eppEscapeHtml(notification.link)}">Open Task</a>`
            : "";

        return `
            <article class="epp-notification-item${notification.read ? " is-read" : ""}">
                <div class="epp-notification-item-header">
                    <strong>${eppEscapeHtml(notification.title || "Project Portal update")}</strong>
                    ${notification.read ? "" : '<span class="epp-notification-unread">New</span>'}
                </div>
                <p>${eppEscapeHtml(notification.description || "No additional details.")}</p>
                <div class="epp-notification-item-meta">
                    ${taskReference}
                    <time>${eppEscapeHtml(eppFormatDateTime(notification.created_at))}</time>
                    ${taskLink}
                </div>
            </article>
        `;
    }).join("");
}

async function eppLoadNotifications() {
    const notifications = projectPortalState.notifications;
    const requestId = ++notifications.requestId;

    notifications.loading = true;
    eppRenderNotifications();

    try {
        const response = await eppCallPortal("get_notifications");

        if (requestId !== notifications.requestId) {
            return;
        }

        notifications.rows = response?.notifications || [];
        notifications.unreadCount = Number(response?.unread_count) || 0;
    } catch (error) {
        if (requestId !== notifications.requestId) {
            return;
        }

        console.error("Project Portal notification API Error:", error);
    } finally {
        if (requestId === notifications.requestId) {
            notifications.loading = false;
            eppRenderNotifications();
        }
    }
}

async function eppMarkProjectPortalNotificationsRead() {
    const notifications = projectPortalState.notifications;

    if (notifications.loading || !notifications.unreadCount) {
        return;
    }

    notifications.loading = true;
    eppRenderNotifications();

    try {
        const response = await eppCallPortal("mark_notifications_read");

        notifications.unreadCount = Number(response?.unread_count) || 0;
        notifications.rows = notifications.rows.map((notification) => ({
            ...notification,
            read: 1
        }));
    } catch (error) {
        frappe.show_alert({
            message: eppGetErrorMessage(error, "Unable to mark notifications as read."),
            indicator: "red"
        });
        console.error("Project Portal notification read API Error:", error);
    } finally {
        notifications.loading = false;
        eppRenderNotifications();
    }
}

function eppRenderSetupState() {
    const dashboard = projectPortalState.dashboard || {};
    const setupCard = eppGetEl("dashboard-setup-card");
    const setupMessage = eppGetEl("dashboard-setup-message");

    if (!setupCard) {
        return;
    }

    if (!dashboard.setup_complete) {
        setupCard.classList.remove("hidden");

        const missingSetup = dashboard.missing_setup || [];

        if (setupMessage) {
            setupMessage.textContent = missingSetup.length
                ? `Missing setup: ${missingSetup.join(", ")}`
                : "Required employee setup is missing.";
        }

        eppShowDashboardAlert(
            "Please complete the required employee setup before using this portal.",
            "error"
        );
        return;
    }

    setupCard.classList.add("hidden");
    eppHideDashboardAlert();
}

function eppRenderSummary() {
    const summary = projectPortalState.dashboard?.summary || {};

    eppSetText(
        "summary-active-projects",
        Number(summary.active_projects) || 0
    );
    eppSetText(
        "summary-my-tasks",
        Number(summary.my_tasks) || 0
    );
    eppSetText(
        "summary-overdue-tasks",
        Number(summary.overdue_tasks) || 0
    );
    eppSetText(
        "summary-completed-week",
        Number(summary.completed_this_week) || 0
    );
}

function eppStopCurrentWorkTimer() {
    if (projectPortalState.currentWorkTimer) {
        clearInterval(projectPortalState.currentWorkTimer);
        projectPortalState.currentWorkTimer = null;
    }
}

function eppRenderCurrentWorkTimer() {
    const currentWork = projectPortalState.dashboard?.current_work;
    const element = eppGetEl("current-work-duration");

    if (!currentWork || !element) {
        return;
    }

    element.textContent = eppFormatSeconds(
        eppGetElapsedSeconds(currentWork.from_time)
    );
}

function eppSyncCurrentWorkTimer() {
    eppStopCurrentWorkTimer();

    const currentWork = projectPortalState.dashboard?.current_work;

    if (!currentWork?.from_time) {
        return;
    }

    eppRenderCurrentWorkTimer();

    projectPortalState.currentWorkTimer = setInterval(
        eppRenderCurrentWorkTimer,
        1000
    );
}

function eppRenderCurrentWork() {
    const currentWork = projectPortalState.dashboard?.current_work || null;
    const emptyState = eppGetEl("current-work-empty");
    const content = eppGetEl("current-work-content");
    const status = eppGetEl("current-work-status");

    if (!currentWork) {
        emptyState?.classList.remove("hidden");
        content?.classList.add("hidden");

        if (status) {
            status.textContent = "Not Working";
            status.classList.remove("is-working");
        }

        eppStopCurrentWorkTimer();
        return;
    }

    emptyState?.classList.add("hidden");
    content?.classList.remove("hidden");

    if (status) {
        status.textContent = "Working";
        status.classList.add("is-working");
    }

    eppSetText(
        "current-work-task",
        currentWork.task_label
        || currentWork.task
        || "General Work"
    );
    eppSetText(
        "current-work-project",
        currentWork.project_label
        || currentWork.project
        || "No Project"
    );
    eppSetText(
        "current-work-activity",
        currentWork.activity_type || "-"
    );
    eppSetText(
        "current-work-started-at",
        eppFormatTime(currentWork.from_time)
    );
    eppSetText(
        "current-work-description",
        currentWork.description || "-"
    );

    eppSyncCurrentWorkTimer();
}

function eppRenderUpcomingDeadlines() {
    const container = eppGetEl("upcoming-deadline-list");
    const deadlines = projectPortalState.dashboard?.upcoming_deadlines || [];

    if (!container) {
        return;
    }

    if (!deadlines.length) {
        container.innerHTML = `
            <div class="epp-section-empty">
                No upcoming task deadlines found.
            </div>
        `;
        return;
    }

    container.innerHTML = deadlines
        .map((item) => {
            const dateParts = eppGetDeadlineParts(item.due_date);
            const projectLabel =
                item.project_label
                || item.project
                || "No Project";

            return `
                <div class="epp-list-item">
                    <div class="epp-list-date">
                        <strong>${eppEscapeHtml(dateParts.day)}</strong>
                        <span>${eppEscapeHtml(dateParts.month)}</span>
                    </div>

                    <div class="epp-list-content">
                        <strong>
                            ${eppEscapeHtml(
                item.subject
                || item.task
                || "Untitled Task"
            )}
                        </strong>

                        <p>${eppEscapeHtml(projectLabel)}</p>

                        <div class="epp-list-meta">
                            ${item.priority
                    ? `
                                        <span class="epp-mini-pill ${eppGetPriorityClass(item.priority)}">
                                            ${eppEscapeHtml(item.priority)}
                                        </span>
                                    `
                    : ""
                }

                            ${item.status
                    ? `
                                        <span class="epp-mini-pill ${eppGetStatusClass(item.status)}">
                                            ${eppEscapeHtml(item.status)}
                                        </span>
                                    `
                    : ""
                }

                            <span class="epp-mini-pill">
                                Due ${eppEscapeHtml(eppFormatDate(item.due_date))}
                            </span>
                        </div>
                    </div>
                </div>
            `;
        })
        .join("");
}

function eppRenderRecentActivity() {
    const container = eppGetEl("recent-activity-list");
    const activities = projectPortalState.dashboard?.recent_activity || [];

    if (!container) {
        return;
    }

    if (!activities.length) {
        container.innerHTML = `
            <div class="epp-section-empty">
                No recent task activity found.
            </div>
        `;
        return;
    }

    container.innerHTML = activities
        .map((activity) => {
            const projectLabel =
                activity.project_label
                || activity.project
                || "No Project";

            return `
                <div class="epp-activity-item">
                    <span class="epp-activity-dot"></span>

                    <div class="epp-activity-content">
                        <strong>
                            ${eppEscapeHtml(
                activity.title
                || activity.reference_name
                || "Task"
            )}
                        </strong>

                        <p>
                            ${eppEscapeHtml(activity.activity_type || "Task Updated")}
                            ${activity.status ? ` · ${eppEscapeHtml(activity.status)}` : ""}
                            · ${eppEscapeHtml(projectLabel)}
                        </p>

                        <time>
                            ${eppEscapeHtml(eppGetRelativeTime(activity.modified))}
                        </time>
                    </div>
                </div>
            `;
        })
        .join("");
}

function eppRenderProjectProgress() {
    const container = eppGetEl("project-progress-list");
    const projects = projectPortalState.dashboard?.project_progress || [];

    if (!container) {
        return;
    }

    if (!projects.length) {
        container.innerHTML = `
            <div class="epp-section-empty">
                No active projects found.
            </div>
        `;
        return;
    }

    container.innerHTML = projects
        .map((project) => {
            const percentage = eppClampPercentage(
                project.percent_complete
            );

            return `
                <article class="epp-project-progress-item">
                    <div class="epp-progress-item-top">
                        <div class="epp-progress-project-copy">
                            <strong>
                                ${eppEscapeHtml(
                project.project_name
                || project.project
                || "Untitled Project"
            )}
                            </strong>

                            <span>${eppEscapeHtml(project.status || "Open")}</span>
                        </div>

                        <span class="epp-progress-percentage">
                            ${percentage}%
                        </span>
                    </div>

                    <div class="epp-progress-track">
                        <div
                            class="epp-progress-bar"
                            style="width: ${percentage}%"
                        ></div>
                    </div>

                    <div class="epp-progress-dates">
                        <span>
                            Start: ${eppEscapeHtml(eppFormatDate(project.expected_start_date))}
                        </span>

                        <span>
                            Due: ${eppEscapeHtml(eppFormatDate(project.expected_end_date))}
                        </span>
                    </div>
                </article>
            `;
        })
        .join("");
}

function eppRenderDashboard() {
    eppRenderSetupState();
    eppRenderHeader();
    eppRenderSummary();
    eppRenderCurrentWork();
    eppRenderUpcomingDeadlines();
    eppRenderRecentActivity();
    eppRenderProjectProgress();
}

async function eppLoadDashboard() {
    try {
        projectPortalState.dashboard = await eppCallPortal(
            "get_dashboard"
        );

        eppRenderDashboard();
    } catch (error) {
        const message = eppGetErrorMessage(
            error,
            "Unable to load project dashboard."
        );

        eppShowDashboardAlert(message, "error");

        const errorHtml = `
            <div class="epp-section-empty">
                ${eppEscapeHtml(message)}
            </div>
        `;

        [
            "upcoming-deadline-list",
            "recent-activity-list",
            "project-progress-list"
        ].forEach((id) => {
            const element = eppGetEl(id);

            if (element) {
                element.innerHTML = errorHtml;
            }
        });

        console.error("Project Dashboard Error:", error);
    }
}

function eppSetProjectsLoading(isLoading) {
    projectPortalState.projects.loading = isLoading;

    eppGetEl("projects-loading")?.classList.toggle(
        "hidden",
        !isLoading
    );

    eppGetEl("projects-list")?.classList.toggle(
        "hidden",
        isLoading
    );

}

function eppReadProjectFilters() {
    return {
        search: eppGetEl("project-search")?.value.trim() || "",
        status: eppGetEl("project-status-filter")?.value || "Open",
        sort: eppGetEl("project-sort-filter")?.value || "recent"
    };
}

function eppSyncProjectFilterControls() {
    const filters = projectPortalState.projects.filters;
    const searchInput = eppGetEl("project-search");
    const statusSelect = eppGetEl("project-status-filter");
    const sortSelect = eppGetEl("project-sort-filter");

    if (searchInput) {
        searchInput.value = filters.search;
    }

    if (statusSelect) {
        statusSelect.value = filters.status;
    }

    if (sortSelect) {
        sortSelect.value = filters.sort;
    }
}

function eppGetVisiblePaginationPages(currentPage, totalPages) {
    if (totalPages <= 7) {
        return Array.from({ length: totalPages }, (_, index) => index + 1);
    }

    if (currentPage <= 4) {
        return [1, 2, 3, 4, 5, "ellipsis-right", totalPages];
    }

    if (currentPage >= totalPages - 3) {
        return [
            1,
            "ellipsis-left",
            totalPages - 4,
            totalPages - 3,
            totalPages - 2,
            totalPages - 1,
            totalPages
        ];
    }

    return [
        1,
        "ellipsis-left",
        currentPage - 1,
        currentPage,
        currentPage + 1,
        "ellipsis-right",
        totalPages
    ];
}

function eppRenderPaginationFooter({
    state,
    elementId,
    summaryId,
    pageNumbersId,
    singularLabel,
    pluralLabel
}) {
    const footer = eppGetEl(elementId);
    const pagination = state.pagination || {};
    const totalRecords = Math.max(Number(pagination.total_records) || 0, 0);
    const pageLength = Math.max(
        Number(pagination.page_length) || state.pageLength || 10,
        1
    );
    const totalPages = Math.max(Number(pagination.total_pages) || 0, 0);
    const currentPage = totalPages
        ? Math.min(Math.max(Number(pagination.page) || 1, 1), totalPages)
        : 1;
    const startRecord = totalRecords
        ? ((currentPage - 1) * pageLength) + 1
        : 0;
    const endRecord = totalRecords
        ? Math.min(currentPage * pageLength, totalRecords)
        : 0;
    const label = totalRecords === 1 ? singularLabel : pluralLabel;
    const isLoading = Boolean(state.loading);

    if (!footer) {
        return;
    }

    footer.classList.remove("hidden");
    eppSetText(
        summaryId,
        totalRecords
            ? `${startRecord}–${endRecord} of ${pagination.is_truncated ? "first " : ""}${totalRecords} ${label}`
            : `0 ${pluralLabel}`
    );

    footer.querySelectorAll("[data-pagination-page]").forEach((button) => {
        const target = button.dataset.paginationPage;
        const targetPage = target === "first"
            ? 1
            : target === "previous"
                ? currentPage - 1
                : target === "next"
                    ? currentPage + 1
                    : target === "last"
                        ? totalPages
                        : Number(target);

        button.disabled = (
            isLoading
            || !totalPages
            || targetPage < 1
            || targetPage > totalPages
            || targetPage === currentPage
        );
    });

    const pageNumbers = eppGetEl(pageNumbersId);

    if (pageNumbers) {
        pageNumbers.innerHTML = eppGetVisiblePaginationPages(currentPage, totalPages)
            .map((value) => {
                if (typeof value !== "number") {
                    return '<span class="epp-pagination-ellipsis" aria-hidden="true">…</span>';
                }

                const isActive = value === currentPage;

                return `
                    <button type="button" class="epp-pagination-page${isActive ? " is-active" : ""}" data-pagination-page="${value}"${isActive ? ' aria-current="page"' : ""}${isLoading || isActive ? " disabled" : ""}>${value}</button>
                `;
            })
            .join("");
    }
}

function eppBindPaginationControls(elementId, state, loadPage) {
    eppGetEl(elementId)?.addEventListener("click", (event) => {
        const button = event.target.closest("[data-pagination-page]");

        if (!button || state.loading) {
            return;
        }

        const pagination = state.pagination || {};
        const totalPages = Math.max(Number(pagination.total_pages) || 0, 0);
        const currentPage = Math.max(Number(pagination.page) || 1, 1);
        const target = button.dataset.paginationPage;
        const nextPage = target === "first"
            ? 1
            : target === "previous"
                ? currentPage - 1
                : target === "next"
                    ? currentPage + 1
                    : target === "last"
                        ? totalPages
                        : Number(target);

        if (
            !totalPages
            || !Number.isInteger(nextPage)
            || nextPage < 1
            || nextPage > totalPages
            || nextPage === currentPage
        ) {
            return;
        }

        state.page = nextPage;
        loadPage();
    });
}

function eppRenderProjectsPagination() {
    eppRenderPaginationFooter({
        state: projectPortalState.projects,
        elementId: "projects-pagination",
        summaryId: "projects-pagination-summary",
        pageNumbersId: "projects-page-numbers",
        singularLabel: "Project",
        pluralLabel: "Projects"
    });
}

function eppRenderProjectsList() {
    const container = eppGetEl("projects-list");
    const rows = projectPortalState.projects.rows || [];

    if (!container) {
        return;
    }

    if (!rows.length) {
        container.innerHTML = `
            <div class="epp-card epp-section-empty">
                No projects matched the selected filters.
            </div>
        `;

        eppRenderProjectsPagination();
        return;
    }

    container.innerHTML = rows
        .map((project) => {
            const percentage = eppClampPercentage(
                project.percent_complete
            );
            const taskSummary = project.task_summary || {};
            const statusClass = eppGetProjectStatusClass(
                project.status
            );

            return `
                <article class="epp-project-card">
                    <div class="epp-project-main">
                        <div class="epp-project-name-row">
                            <h3>
                                ${eppEscapeHtml(
                project.project_name
                || project.name
                || "Untitled Project"
            )}
                            </h3>

                            <span class="epp-project-status-pill ${statusClass}">
                                ${eppEscapeHtml(project.status || "Open")}
                            </span>

                            ${project.is_overdue
                    ? `
                                        <span class="epp-project-overdue-pill">
                                            Overdue
                                        </span>
                                    `
                    : ""
                }
                        </div>

                        <div class="epp-project-meta">
                            <span class="epp-project-code">
                                ${eppEscapeHtml(project.name || "")}
                            </span>

                            <span>
                                Customer: ${eppEscapeHtml(project.customer || "No Customer")}
                            </span>

                            <span>
                                Type: ${eppEscapeHtml(project.project_type || "General")}
                            </span>

                            <span>
                                Due: ${eppEscapeHtml(eppFormatDate(project.expected_end_date))}
                            </span>
                        </div>
                    </div>

                    <div class="epp-project-progress-column">
                        <span class="epp-project-column-label">
                            Progress
                        </span>

                        <div class="epp-project-progress-head">
                            <strong>Project Completion</strong>
                            <span>${percentage}%</span>
                        </div>

                        <div class="epp-progress-track">
                            <div
                                class="epp-progress-bar"
                                style="width: ${percentage}%"
                            ></div>
                        </div>
                    </div>

                    <div class="epp-project-task-column">
                        <span class="epp-project-column-label">
                            Visible Tasks
                        </span>

                        <div class="epp-project-task-stats">
                            <div class="epp-project-task-stat">
                                <strong>${Number(taskSummary.total) || 0}</strong>
                                <span>Total</span>
                            </div>

                            <div class="epp-project-task-stat">
                                <strong>${Number(taskSummary.open) || 0}</strong>
                                <span>Open</span>
                            </div>

                            <div class="epp-project-task-stat">
                                <strong>${Number(taskSummary.completed) || 0}</strong>
                                <span>Done</span>
                            </div>

                            <div class="epp-project-task-stat is-overdue">
                                <strong>${Number(taskSummary.overdue) || 0}</strong>
                                <span>Overdue</span>
                            </div>
                        </div>
                    </div>

                    <div class="epp-project-actions">
                        <button
                            type="button"
                            class="epp-project-open-button"
                            data-open-project="${eppEscapeHtml(project.name || "")}"
                        >
                            Open Project
                        </button>
                    </div>

                </article>
            `;
        })
        .join("");

    eppRenderProjectsPagination();
}

async function eppLoadProjects(
    {
        resetPage = false,
        scrollToTop = false
    } = {}
) {
    if (resetPage) {
        projectPortalState.projects.page = 1;
    }

    const requestId = ++projectPortalState.projects.requestId;
    const filters = projectPortalState.projects.filters;
    const page = projectPortalState.projects.page;

    eppHideProjectsError();
    eppSetProjectsLoading(true);

    try {
        const response = await eppCallPortal(
            "get_projects",
            {
                search: filters.search,
                status: filters.status,
                sort: filters.sort,
                page,
                page_length: projectPortalState.projects.pageLength
            }
        );

        if (requestId !== projectPortalState.projects.requestId) {
            return;
        }

        projectPortalState.projects.loaded = true;
        projectPortalState.projects.rows = response?.projects || [];
        projectPortalState.projects.pagination =
            response?.pagination
            || {
                page,
                page_length: projectPortalState.projects.pageLength,
                has_previous: page > 1,
                has_more: false
            };
        projectPortalState.projects.page =
            Number(response?.pagination?.page)
            || page;

        eppRenderProjectsList();

        if (scrollToTop) {
            eppGetEl("projects-view")?.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
        }
    } catch (error) {
        if (requestId !== projectPortalState.projects.requestId) {
            return;
        }

        const message = eppGetErrorMessage(
            error,
            "Unable to load Projects."
        );

        eppShowProjectsError(message);

        const container = eppGetEl("projects-list");

        if (container) {
            container.innerHTML = `
                <div class="epp-card epp-section-empty">
                    ${eppEscapeHtml(message)}
                </div>
            `;
        }

        console.error("Projects API Error:", error);
    } finally {
        if (requestId === projectPortalState.projects.requestId) {
            eppSetProjectsLoading(false);
            eppRenderProjectsPagination();
        }
    }
}

function eppGetMyTaskFilters() {
    return {
        search: eppGetEl("my-task-search")?.value.trim() || "",
        status: eppGetEl("my-task-status-filter")?.value || "All",
        priority: eppGetEl("my-task-priority-filter")?.value || "All",
        due: eppGetEl("my-task-due-filter")?.value || "All"
    };
}

function eppSyncMyTaskFilterControls() {
    const filters = projectPortalState.myTasks.filters;

    [
        ["my-task-search", filters.search],
        ["my-task-status-filter", filters.status],
        ["my-task-priority-filter", filters.priority],
        ["my-task-due-filter", filters.due]
    ].forEach(([id, value]) => {
        const element = eppGetEl(id);

        if (element) {
            element.value = value;
        }
    });
}

function eppSetMyTasksLoading(isLoading) {
    projectPortalState.myTasks.loading = isLoading;
    eppGetEl("my-tasks-loading")?.classList.toggle("hidden", !isLoading);
    eppGetEl("my-tasks-list")?.classList.toggle("hidden", isLoading);
}

function eppShowMyTasksError(message) {
    const element = eppGetEl("my-tasks-error");

    if (!element) {
        return;
    }

    element.textContent = message;
    element.classList.remove("hidden");
}

function eppHideMyTasksError() {
    const element = eppGetEl("my-tasks-error");

    if (!element) {
        return;
    }

    element.textContent = "";
    element.classList.add("hidden");
}

function eppGetMyTaskPriorityClass(priority) {
    const value = String(priority || "").toLowerCase();

    if (value === "urgent") {
        return "is-urgent";
    }

    if (value === "high") {
        return "is-high";
    }

    if (value === "medium") {
        return "is-medium";
    }

    return "";
}

function eppRenderMyTasksPagination() {
    eppRenderPaginationFooter({
        state: projectPortalState.myTasks,
        elementId: "my-tasks-pagination",
        summaryId: "my-tasks-pagination-summary",
        pageNumbersId: "my-tasks-page-numbers",
        singularLabel: "Task",
        pluralLabel: "Tasks"
    });
}

function eppRenderMyTasks() {
    const container = eppGetEl("my-tasks-list");
    const tasks = projectPortalState.myTasks.rows || [];

    if (!container) {
        return;
    }

    if (!tasks.length) {
        container.innerHTML = `
            <div class="epp-section-empty">
                No assigned tasks matched the selected filters.
            </div>
        `;
        eppRenderMyTasksPagination();
        return;
    }

    container.innerHTML = tasks
        .map((task) => {
            const percentage = eppClampPercentage(task.progress);
            const priority = task.priority || "No Priority";
            const dueLabel = eppFormatDate(task.due_date);

            return `
                <article class="epp-my-task-row">
                    <div class="epp-my-task-main">
                        <strong>${eppEscapeHtml(task.subject || task.name || "Untitled Task")}</strong>
                        <span>${eppEscapeHtml(task.project || "No Project")}</span>
                    </div>
                    <div><span class="epp-task-status-pill ${eppGetTaskStatusClass(task.status)}">${eppEscapeHtml(task.status || "Open")}</span></div>
                    <div class="epp-my-task-meta">
                        <span class="epp-task-priority ${eppGetMyTaskPriorityClass(task.priority)}">${eppEscapeHtml(priority)}</span>
                        <span>Due: ${eppEscapeHtml(dueLabel)}${task.is_overdue ? " · Overdue" : ""}</span>
                        <span>Time: ${eppEscapeHtml(eppFormatHours(task.actual_time))} / ${eppEscapeHtml(eppFormatHours(task.expected_time))}</span>
                    </div>
                    <div class="epp-my-task-progress">
                        <div class="epp-project-progress-head"><strong>Progress</strong><span>${percentage}%</span></div>
                        <div class="epp-progress-track"><div class="epp-progress-bar" style="width: ${percentage}%"></div></div>
                    </div>
                    <button type="button" class="epp-secondary-button epp-task-detail-button" data-open-task="${eppEscapeHtml(task.name || "")}">View Details</button>
                </article>
            `;
        })
        .join("");

    eppRenderMyTasksPagination();
}

async function eppLoadMyTasks({ resetPage = false, scrollToTop = false } = {}) {
    const myTasks = projectPortalState.myTasks;

    if (resetPage) {
        myTasks.page = 1;
    }

    const requestId = ++myTasks.requestId;
    eppHideMyTasksError();
    eppSetMyTasksLoading(true);

    try {
        const response = await eppCallPortal("get_my_tasks", {
            ...myTasks.filters,
            page: myTasks.page,
            page_length: myTasks.pageLength
        });

        if (requestId !== myTasks.requestId) {
            return;
        }

        myTasks.rows = response?.tasks || [];
        myTasks.pagination = response?.pagination || myTasks.pagination;
        myTasks.page = Number(response?.pagination?.page) || myTasks.page;
        eppRenderMyTasks();

        if (scrollToTop) {
            eppGetEl("my-tasks-view")?.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
        }
    } catch (error) {
        if (requestId !== myTasks.requestId) {
            return;
        }

        const message = eppGetErrorMessage(error, "Unable to load My Tasks.");
        eppShowMyTasksError(message);
        const container = eppGetEl("my-tasks-list");

        if (container) {
            container.innerHTML = `
                <div class="epp-section-empty">${eppEscapeHtml(message)}</div>
            `;
        }
        console.error("My Tasks API Error:", error);
    } finally {
        if (requestId === myTasks.requestId) {
            eppSetMyTasksLoading(false);
            eppRenderMyTasksPagination();
        }
    }
}

function eppScheduleMyTaskSearch() {
    const myTasks = projectPortalState.myTasks;

    if (myTasks.searchTimer) {
        clearTimeout(myTasks.searchTimer);
    }

    myTasks.searchTimer = setTimeout(() => {
        myTasks.filters = eppGetMyTaskFilters();
        eppLoadMyTasks({ resetPage: true });
    }, 350);
}

function eppResetMyTaskFilters() {
    projectPortalState.myTasks.filters = {
        search: "",
        status: "All",
        priority: "All",
        due: "All"
    };
    projectPortalState.myTasks.page = 1;
    eppSyncMyTaskFilterControls();
    eppLoadMyTasks({ resetPage: true });
}

function eppGetTimesheetFilters() {
    return {
        period: eppGetEl("timesheet-period-filter")?.value || "This Week",
        status: eppGetEl("timesheet-status-filter")?.value || "All"
    };
}

function eppSyncTimesheetFilterControls() {
    const filters = projectPortalState.timesheets.filters;

    [
        ["timesheet-period-filter", filters.period],
        ["timesheet-status-filter", filters.status]
    ].forEach(([id, value]) => {
        const element = eppGetEl(id);

        if (element) {
            element.value = value;
        }
    });
}

function eppSetTimesheetsLoading(isLoading) {
    projectPortalState.timesheets.loading = isLoading;
    eppGetEl("timesheets-loading")?.classList.toggle("hidden", !isLoading);
    eppGetEl("timesheet-summary-grid")?.classList.toggle("hidden", isLoading);
    eppGetEl("timesheets-list")?.closest(".epp-timesheet-list-card")?.classList.toggle("hidden", isLoading);
}

function eppShowTimesheetsError(message) {
    const element = eppGetEl("timesheets-error");

    if (!element) {
        return;
    }

    element.textContent = message;
    element.classList.remove("hidden");
}

function eppHideTimesheetsError() {
    const element = eppGetEl("timesheets-error");

    if (!element) {
        return;
    }

    element.textContent = "";
    element.classList.add("hidden");
}

function eppRenderTimesheetsSetup(setupComplete, missingSetup = []) {
    const setup = eppGetEl("timesheets-setup");
    const message = eppGetEl("timesheets-setup-message");

    if (!setup) {
        return;
    }

    setup.classList.toggle("hidden", setupComplete);

    if (!setupComplete && message) {
        message.textContent = missingSetup.length
            ? `Missing setup: ${missingSetup.join(", ")}`
            : "Required employee setup is missing.";
    }
}

function eppRenderTimesheetsPagination() {
    eppRenderPaginationFooter({
        state: projectPortalState.timesheets,
        elementId: "timesheets-pagination",
        summaryId: "timesheets-pagination-summary",
        pageNumbersId: "timesheets-page-numbers",
        singularLabel: "Timesheet",
        pluralLabel: "Timesheets"
    });
}

function eppRenderTimesheetBreakdown(id, rows, emptyMessage) {
    const container = eppGetEl(id);

    if (!container) {
        return;
    }

    if (!rows?.length) {
        container.innerHTML = `<div class="epp-section-empty">${eppEscapeHtml(emptyMessage)}</div>`;
        return;
    }

    const highestHours = Math.max(...rows.map((row) => Number(row.hours) || 0), 0);

    container.innerHTML = rows.map((row) => {
        const hours = Number(row.hours) || 0;
        const percentage = highestHours ? (hours / highestHours) * 100 : 0;

        return `
            <div class="epp-timesheet-breakdown-row">
                <div><strong>${eppEscapeHtml(row.label || row.name || "--")}</strong><span>${eppEscapeHtml(eppFormatHours(hours))}</span></div>
                <div class="epp-progress-track"><div class="epp-progress-bar" style="width: ${percentage}%"></div></div>
            </div>
        `;
    }).join("");
}

function eppRenderTimesheetSummary() {
    const summary = projectPortalState.timesheets.summary || {};
    const activeSession = summary.active_session;

    eppSetText("timesheet-today-hours", eppFormatHours(summary.today_hours));
    eppSetText("timesheet-period-hours", eppFormatHours(summary.period_hours));
    eppSetText("timesheet-period-label", projectPortalState.timesheets.filters.period || "Selected Period");
    eppSetText("timesheet-draft-count", Number(summary.draft_timesheets) || 0);
    eppSetText("timesheet-submitted-count", Number(summary.submitted_timesheets) || 0);

    const activeContainer = eppGetEl("timesheet-active-session");

    if (activeContainer) {
        activeContainer.innerHTML = activeSession ? `
            <div class="epp-timesheet-active-session">
                <span class="epp-status-pill is-working">Running</span>
                <strong>${eppEscapeHtml(activeSession.task_label || activeSession.project_label || "Work Session")}</strong>
                <span>${eppEscapeHtml(activeSession.project_label || "No Project")}</span>
                <span>Started ${eppEscapeHtml(eppFormatTime(activeSession.from_time))} · ${eppEscapeHtml(eppFormatHours(activeSession.hours))}</span>
            </div>
        ` : "No active Timesheet session.";
        activeContainer.classList.toggle("epp-section-empty", !activeSession);
    }

    eppRenderTimesheetBreakdown(
        "timesheet-project-hours",
        summary.project_hours,
        "No project time was recorded in this period."
    );
    eppRenderTimesheetBreakdown(
        "timesheet-task-hours",
        summary.task_hours,
        "No task time was recorded in this period."
    );
}

function eppRenderTimesheets() {
    const container = eppGetEl("timesheets-list");
    const rows = projectPortalState.timesheets.rows || [];

    if (!container) {
        return;
    }

    if (!rows.length) {
        container.innerHTML = `<div class="epp-section-empty">No Timesheets matched the selected filters.</div>`;
        eppRenderTimesheetsPagination();
        return;
    }

    container.innerHTML = rows.map((timesheet) => {
        const sessions = timesheet.time_logs || [];
        const sessionLabel = sessions.length === 1 ? "session" : "sessions";

        return `
            <details class="epp-timesheet-record">
                <summary>
                    <div class="epp-timesheet-record-main"><strong>${eppEscapeHtml(eppFormatDate(timesheet.start_date))}</strong><span>${eppEscapeHtml(timesheet.name || "Timesheet")}</span></div>
                    <span class="epp-timesheet-status ${timesheet.status === "Submitted" ? "is-submitted" : "is-draft"}">${eppEscapeHtml(timesheet.status || "Draft")}</span>
                    <span>${eppEscapeHtml(eppFormatHours(timesheet.total_hours))}</span>
                    <span>${sessions.length} ${sessionLabel}</span>
                </summary>
                <div class="epp-timesheet-session-list">
                    ${sessions.length ? sessions.map((session) => `
                        <article class="epp-timesheet-session">
                            <div><strong>${eppEscapeHtml(session.task_label || session.activity_type || "Work Session")}</strong><span>${eppEscapeHtml(session.project_label || "No Project")}</span></div>
                            <div><span>${eppEscapeHtml(session.activity_type || "No Activity Type")}</span><span>${eppEscapeHtml(eppFormatTime(session.from_time))} – ${session.is_running ? "Running" : eppEscapeHtml(eppFormatTime(session.to_time))}</span></div>
                            <strong>${eppEscapeHtml(eppFormatHours(session.hours))}</strong>
                        </article>
                    `).join("") : `<div class="epp-section-empty">No time-log rows were found.</div>`}
                </div>
            </details>
        `;
    }).join("");

    eppRenderTimesheetsPagination();
}

async function eppLoadTimesheets({ resetPage = false } = {}) {
    const timesheets = projectPortalState.timesheets;

    if (resetPage) {
        timesheets.page = 1;
    }

    const requestId = ++timesheets.requestId;
    eppHideTimesheetsError();
    eppSetTimesheetsLoading(true);

    try {
        const response = await eppCallPortal("get_my_timesheets", {
            ...timesheets.filters,
            page: timesheets.page,
            page_length: timesheets.pageLength
        });

        if (requestId !== timesheets.requestId) {
            return;
        }

        eppRenderTimesheetsSetup(
            Boolean(response?.setup_complete),
            response?.missing_setup || []
        );
        timesheets.rows = response?.timesheets || [];
        timesheets.summary = response?.summary || null;
        timesheets.pagination = response?.pagination || timesheets.pagination;
        timesheets.page = Number(response?.pagination?.page) || timesheets.page;
        eppRenderTimesheetSummary();
        eppRenderTimesheets();

        if (response?.summary?.is_truncated) {
            eppShowTimesheetsError("Only the first 500 Timesheets in this period are included in the summary.");
        }
    } catch (error) {
        if (requestId !== timesheets.requestId) {
            return;
        }

        const message = eppGetErrorMessage(error, "Unable to load Timesheets.");
        eppShowTimesheetsError(message);
        const container = eppGetEl("timesheets-list");

        if (container) {
            container.innerHTML = `<div class="epp-section-empty">${eppEscapeHtml(message)}</div>`;
        }
        console.error("Timesheets API Error:", error);
    } finally {
        if (requestId === timesheets.requestId) {
            eppSetTimesheetsLoading(false);
            eppRenderTimesheetsPagination();
        }
    }
}

function eppResetTimesheetFilters() {
    projectPortalState.timesheets.filters = {
        period: "This Week",
        status: "All"
    };
    eppSyncTimesheetFilterControls();
    eppLoadTimesheets({ resetPage: true });
}

function eppSetTaskBoardLoading(isLoading) {
    projectPortalState.taskBoard.loading = isLoading;
    eppGetEl("task-board-loading")?.classList.toggle("hidden", !isLoading);
    eppGetEl("task-board-lanes")?.classList.toggle("hidden", isLoading);
}

function eppShowTaskBoardError(message) {
    const element = eppGetEl("task-board-error");

    if (!element) {
        return;
    }

    element.textContent = message;
    element.classList.remove("hidden");
}

function eppHideTaskBoardError() {
    const element = eppGetEl("task-board-error");

    if (!element) {
        return;
    }

    element.textContent = "";
    element.classList.add("hidden");
}

function eppRenderTaskBoard() {
    const container = eppGetEl("task-board-lanes");
    const taskBoard = projectPortalState.taskBoard;
    const limitNotice = eppGetEl("task-board-limit-notice");

    if (!container) {
        return;
    }

    if (limitNotice) {
        limitNotice.textContent = taskBoard.isTruncated
            ? `Showing the first ${taskBoard.boardLimit} matched tasks. Refine the search to narrow this board.`
            : "";
        limitNotice.classList.toggle("hidden", !taskBoard.isTruncated);
    }

    const statuses = taskBoard.statuses || [];
    const tasks = taskBoard.rows || [];
    const activeWorkTask = taskBoard.activeWork?.task || "";

    if (!statuses.length) {
        container.innerHTML = `
            <div class="epp-card epp-section-empty">No Task statuses are available for this board.</div>
        `;
        return;
    }

    container.innerHTML = statuses.map((status) => {
        const laneTasks = tasks.filter((task) => task.status === status);

        return `
            <section class="epp-task-board-lane" data-task-board-status="${eppEscapeHtml(status)}">
                <header class="epp-task-board-lane-header">
                    <div>
                        <span class="epp-task-status-pill ${eppGetTaskStatusClass(status)}">${eppEscapeHtml(status)}</span>
                    </div>
                    <strong>${laneTasks.length}</strong>
                </header>
                <div class="epp-task-board-dropzone" data-task-board-status="${eppEscapeHtml(status)}">
                    ${laneTasks.length ? laneTasks.map((task) => {
                        const percentage = eppClampPercentage(task.progress);
                        const priority = task.priority || "No Priority";
                        const dueLabel = eppFormatDate(task.due_date);
                        const isMoving = taskBoard.movingTask === task.name;
                        const isWorking = activeWorkTask === task.name;
                        const hasAnotherActiveSession = Boolean(activeWorkTask && !isWorking);
                        const isClosed = ["completed", "cancelled"].includes(
                            String(task.status || "").toLowerCase()
                        );
                        const isWorkActionPending = taskBoard.workingTask === task.name;
                        const workAction = isClosed ? "" : `
                            <div class="epp-task-board-work-action">
                                <button type="button" class="${isWorking ? "epp-secondary-button" : "epp-primary-button"} epp-task-board-work-button" data-task-work-action="${isWorking ? "stop" : "start"}" data-task-work="${eppEscapeHtml(task.name || "")}"${hasAnotherActiveSession || isWorkActionPending ? " disabled" : ""}>
                                    ${isWorkActionPending ? "Saving..." : isWorking ? "Stop Work" : hasAnotherActiveSession ? "Another task running" : "Start Work"}
                                </button>
                            </div>
                        `;

                        return `
                            <article class="epp-task-board-card${isMoving ? " is-moving" : ""}" draggable="true" data-open-board-task="${eppEscapeHtml(task.name || "")}">
                                <div class="epp-task-board-card-topline">
                                    <span class="epp-task-priority ${eppGetMyTaskPriorityClass(task.priority)}">${eppEscapeHtml(priority)}</span>
                                    <span class="epp-task-board-due${task.is_overdue ? " is-overdue" : ""}">${task.is_overdue ? "Overdue · " : "Due · "}${eppEscapeHtml(dueLabel)}</span>
                                </div>
                                <button type="button" class="epp-task-board-open" data-open-board-task="${eppEscapeHtml(task.name || "")}" aria-label="Open ${eppEscapeHtml(task.subject || task.name || "Task")}">${eppEscapeHtml(task.subject || task.name || "Untitled Task")}</button>
                                <span class="epp-task-board-project">${eppEscapeHtml(task.project || "No Project")}</span>
                                <div class="epp-task-board-progress">
                                    <div class="epp-project-progress-head"><strong>Progress</strong><span>${percentage}%</span></div>
                                    <div class="epp-progress-track"><div class="epp-progress-bar" style="width: ${percentage}%"></div></div>
                                </div>
                                ${workAction}
                            </article>
                        `;
                    }).join("") : `
                        <div class="epp-task-board-empty">Drop a task here.</div>
                    `}
                </div>
            </section>
        `;
    }).join("");

}

async function eppLoadTaskBoard() {
    const taskBoard = projectPortalState.taskBoard;
    const requestId = ++taskBoard.requestId;

    eppHideTaskBoardError();
    eppSetTaskBoardLoading(true);

    try {
        const response = await eppCallPortal("get_task_board", {
            search: taskBoard.search
        });

        if (requestId !== taskBoard.requestId) {
            return;
        }

        taskBoard.statuses = response?.statuses || [];
        taskBoard.rows = response?.tasks || [];
        taskBoard.activeWork = response?.active_work || null;
        taskBoard.isTruncated = Boolean(response?.is_truncated);
        taskBoard.boardLimit = Number(response?.board_limit) || 0;
        taskBoard.movingTask = "";
        eppRenderTaskBoard();
    } catch (error) {
        if (requestId !== taskBoard.requestId) {
            return;
        }

        const message = eppGetErrorMessage(error, "Unable to load Task Board.");
        eppShowTaskBoardError(message);
        const container = eppGetEl("task-board-lanes");

        if (container) {
            container.innerHTML = `
                <div class="epp-card epp-section-empty">${eppEscapeHtml(message)}</div>
            `;
        }
        console.error("Task Board API Error:", error);
    } finally {
        if (requestId === taskBoard.requestId) {
            eppSetTaskBoardLoading(false);
        }
    }
}

function eppScheduleTaskBoardSearch() {
    const taskBoard = projectPortalState.taskBoard;

    if (taskBoard.searchTimer) {
        clearTimeout(taskBoard.searchTimer);
    }

    taskBoard.searchTimer = setTimeout(() => {
        taskBoard.search = eppGetEl("task-board-search")?.value.trim() || "";
        eppLoadTaskBoard();
    }, 350);
}

function eppResetTaskBoardFilters() {
    const taskBoard = projectPortalState.taskBoard;

    taskBoard.search = "";
    const searchElement = eppGetEl("task-board-search");

    if (searchElement) {
        searchElement.value = "";
    }

    eppLoadTaskBoard();
}

function eppClearTaskBoardDropTargets() {
    document.querySelectorAll(".epp-task-board-dropzone.is-drop-target").forEach((element) => {
        element.classList.remove("is-drop-target");
    });
}

async function eppMoveTaskOnBoard(taskName, status) {
    const taskBoard = projectPortalState.taskBoard;
    const task = taskBoard.rows.find((row) => row.name === taskName);

    if (!task || task.status === status || taskBoard.movingTask) {
        return;
    }

    taskBoard.movingTask = taskName;
    eppRenderTaskBoard();

    try {
        await eppCallPortal("update_my_task", { task: taskName, status });
        frappe.show_alert({ message: "Task status updated.", indicator: "green" });
        await eppLoadTaskBoard();
    } catch (error) {
        taskBoard.movingTask = "";
        eppRenderTaskBoard();
        eppShowTaskBoardError(
            eppGetErrorMessage(error, "Unable to update this task status.")
        );
        console.error("Task Board update API Error:", error);
    }
}

async function eppSetMyTaskWork(taskName, action) {
    const myTasks = projectPortalState.myTasks;
    const taskBoard = projectPortalState.taskBoard;

    if (!taskName || myTasks.workingTask) {
        return;
    }

    myTasks.workingTask = taskName;
    taskBoard.workingTask = taskName;

    if (eppGetPortalPage() === "task-board") {
        eppRenderTaskBoard();
    }

    try {
        await eppCallPortal(
            action === "stop" ? "stop_my_task_work" : "start_my_task_work",
            { task: taskName }
        );

        frappe.show_alert({
            message: action === "stop" ? "Work session stopped." : "Work session started.",
            indicator: "green"
        });

        const refreshes = [eppLoadDashboard(), eppLoadMyTasks()];

        if (eppGetPortalPage() === "task-board") {
            refreshes.push(eppLoadTaskBoard());
        }

        if (eppGetPortalPage() === "timesheets") {
            refreshes.push(eppLoadTimesheets());
        }

        await Promise.all(refreshes);

        if (myTasks.detail?.name === taskName) {
            await eppOpenMyTaskDetails(taskName);
        }
    } catch (error) {
        const message = eppGetErrorMessage(
            error,
            action === "stop" ? "Unable to stop this work session." : "Unable to start work for this task."
        );

        frappe.show_alert({ message, indicator: "red" });

        if (eppGetPortalPage() === "task-board") {
            eppShowTaskBoardError(message);
        }

        console.error("Task work session API Error:", error);
    } finally {
        myTasks.workingTask = "";
        taskBoard.workingTask = "";

        if (eppGetPortalPage() === "task-board") {
            eppRenderTaskBoard();
        }
    }
}

function eppSetMyTaskDrawerOpen(isOpen) {
    const drawer = eppGetEl("my-task-drawer");
    const backdrop = eppGetEl("my-task-drawer-backdrop");

    drawer?.classList.toggle("is-open", isOpen);
    drawer?.setAttribute("aria-hidden", String(!isOpen));
    backdrop?.classList.toggle("hidden", !isOpen);
    document.body.style.overflow = isOpen ? "hidden" : "";
}

function eppCloseMyTaskDrawer() {
    eppSetMyTaskDrawerOpen(false);
}

function eppCanEditMyTaskField(task, fieldname) {
    return (task.editable_fields || []).includes(fieldname);
}

function eppFormatDateTimeInput(value) {
    const date = eppToDate(value);

    if (!date) {
        return "";
    }

    return [
        date.getFullYear(),
        eppPad(date.getMonth() + 1),
        eppPad(date.getDate())
    ].join("-") + `T${eppPad(date.getHours())}:${eppPad(date.getMinutes())}`;
}

function eppRenderMyTaskSelectOptions(options, value, emptyLabel = "Select") {
    const optionRows = Array.isArray(options) ? options : [];
    const values = new Set(optionRows.map((option) => String(option?.value ?? option)));
    const currentValue = String(value || "");
    const currentOption = currentValue && !values.has(currentValue)
        ? `<option value="${eppEscapeHtml(currentValue)}">${eppEscapeHtml(currentValue)}</option>`
        : "";
    const emptyOption = emptyLabel
        ? `<option value="">${eppEscapeHtml(emptyLabel)}</option>`
        : "";

    return emptyOption + currentOption + optionRows.map((option) => {
        const optionValue = String(option?.value ?? option);
        const optionLabel = String(option?.label ?? option);
        const selected = optionValue === currentValue ? " selected" : "";

        return `<option value="${eppEscapeHtml(optionValue)}"${selected}>${eppEscapeHtml(optionLabel)}</option>`;
    }).join("");
}

function eppRenderMyTaskEditForm(task) {
    const container = eppGetEl("my-task-drawer-content");

    if (!container) {
        return;
    }

    const options = task.edit_options || {};
    const canEdit = (fieldname) => eppCanEditMyTaskField(task, fieldname);
    const managerFields = canEdit("subject") ? `
        <div class="epp-task-edit-field epp-task-edit-field-wide">
            <label for="my-task-edit-subject">Task Title</label>
            <input id="my-task-edit-subject" name="subject" type="text" maxlength="140" value="${eppEscapeHtml(task.subject || "")}" required>
        </div>
    ` : "";
    const priorityField = canEdit("priority") ? `
        <div class="epp-task-edit-field">
            <label for="my-task-edit-priority">Priority</label>
            <select id="my-task-edit-priority" name="priority">${eppRenderMyTaskSelectOptions(options.priorities, task.priority, "No Priority")}</select>
        </div>
    ` : "";
    const typeField = canEdit("type") ? `
        <div class="epp-task-edit-field">
            <label for="my-task-edit-type">Task Type</label>
            <input id="my-task-edit-type" name="type" type="text" list="my-task-type-options" value="${eppEscapeHtml(task.activity_type || "")}">
            <datalist id="my-task-type-options">${eppRenderMyTaskSelectOptions(options.task_types, task.activity_type, "")}</datalist>
        </div>
    ` : "";
    const scheduleFields = canEdit("exp_start_date") ? `
        <div class="epp-task-edit-field">
            <label for="my-task-edit-start-date">Start Date</label>
            <input id="my-task-edit-start-date" name="exp_start_date" type="datetime-local" value="${eppEscapeHtml(eppFormatDateTimeInput(task.start_date))}">
        </div>
        <div class="epp-task-edit-field">
            <label for="my-task-edit-due-date">Due Date</label>
            <input id="my-task-edit-due-date" name="exp_end_date" type="datetime-local" value="${eppEscapeHtml(eppFormatDateTimeInput(task.due_date))}">
        </div>
        <div class="epp-task-edit-field">
            <label for="my-task-edit-expected-time">Expected Time (hours)</label>
            <input id="my-task-edit-expected-time" name="expected_time" type="number" min="0" step="0.1" value="${eppEscapeHtml(task.expected_time || 0)}">
        </div>
    ` : "";

    eppSetText("my-task-detail-subject", `Edit ${task.subject || task.name || "Task"}`);
    container.innerHTML = `
        <form id="my-task-edit-form" class="epp-task-edit-form">
            <p class="epp-task-edit-note">Only this task's owner can update it. Changing Task Owner transfers this task to that employee.</p>
            <div class="epp-task-edit-grid">
                ${managerFields}
                <div class="epp-task-edit-field">
                    <label for="my-task-edit-status">Status</label>
                    <select id="my-task-edit-status" name="status" required>${eppRenderMyTaskSelectOptions(options.statuses, task.status, "")}</select>
                </div>
                ${priorityField}
                <div class="epp-task-edit-field">
                    <label for="my-task-edit-progress">Progress (%)</label>
                    <input id="my-task-edit-progress" name="progress" type="number" min="0" max="100" step="1" value="${eppEscapeHtml(task.progress || 0)}" required>
                </div>
                <div class="epp-task-edit-field epp-task-edit-field-wide">
                    <label for="my-task-edit-owner">Task Owner</label>
                    <select id="my-task-edit-owner" name="custom_task_owner" required>${eppRenderMyTaskSelectOptions(options.task_owners, task.task_owner, "")}</select>
                </div>
                ${typeField}
                ${scheduleFields}
                <div class="epp-task-edit-field epp-task-edit-field-wide">
                    <label for="my-task-edit-description">Task Description</label>
                    <textarea id="my-task-edit-description" name="description" rows="5" placeholder="Add the current task update or description...">${eppEscapeHtml(task.description || "")}</textarea>
                </div>
            </div>
            <div id="my-task-edit-error" class="epp-alert epp-alert-error hidden"></div>
            <div class="epp-task-edit-actions">
                <button type="button" class="epp-secondary-button" data-cancel-my-task-edit>Cancel</button>
                <button type="submit" class="epp-primary-button">Save Task</button>
            </div>
        </form>
    `;
}

function eppRenderTaskUpdateTimeline(task) {
    const updates = Array.isArray(task.updates) ? task.updates : [];
    const attachments = Array.isArray(task.attachments) ? task.attachments : [];
    const statusOptions = task.edit_options?.statuses || [];
    const isSaving = projectPortalState.myTasks.updating;
    const updateRows = updates.length ? updates.map((update) => `
        <article class="epp-task-update-entry">
            <div class="epp-task-update-entry-header">
                <strong>${eppEscapeHtml(update.author || "Employee")}</strong>
                <time>${eppEscapeHtml(eppFormatDateTime(update.created_at))}</time>
            </div>
            <p>${eppEscapeHtml(update.content || "")}</p>
        </article>
    `).join("") : `
        <div class="epp-task-update-empty">No task updates yet. Add the first progress update below.</div>
    `;
    const attachmentRows = attachments.length ? attachments.map((attachment) => `
        <a class="epp-task-attachment" href="${eppEscapeHtml(attachment.file_url || "#")}" target="_blank" rel="noopener">
            <span>${eppEscapeHtml(attachment.file_name || "Attachment")}</span>
            <small>${eppEscapeHtml(eppFormatDate(attachment.created_at))}</small>
        </a>
    `).join("") : `
        <span class="epp-task-attachments-empty">No attachments added.</span>
    `;

    return `
        <section class="epp-task-update-section">
            <div class="epp-task-update-section-header">
                <div><span class="epp-section-label">Progress Update</span><h3>Add Work Update</h3></div>
                <span>Saved to Task timeline</span>
            </div>
            <form id="my-task-update-form" class="epp-task-update-form">
                <div class="epp-task-edit-field epp-task-edit-field-wide">
                    <label for="my-task-update-work-completed">Work Completed</label>
                    <textarea id="my-task-update-work-completed" name="work_completed" rows="4" maxlength="3000" placeholder="What did you complete?" required${isSaving ? " disabled" : ""}></textarea>
                </div>
                <div class="epp-task-edit-grid">
                    <div class="epp-task-edit-field">
                        <label for="my-task-update-status">Status</label>
                        <select id="my-task-update-status" name="status"${isSaving ? " disabled" : ""}>${eppRenderMyTaskSelectOptions(statusOptions, task.status, "Keep current status")}</select>
                    </div>
                    <div class="epp-task-edit-field">
                        <label for="my-task-update-progress">Progress (%)</label>
                        <input id="my-task-update-progress" name="progress" type="number" min="0" max="100" step="1" value="${eppEscapeHtml(task.progress || 0)}"${isSaving ? " disabled" : ""}>
                    </div>
                </div>
                <div class="epp-task-edit-field epp-task-edit-field-wide">
                    <label for="my-task-update-blocker">Blocker (optional)</label>
                    <textarea id="my-task-update-blocker" name="blocker" rows="2" maxlength="1500" placeholder="What is blocking this task?"${isSaving ? " disabled" : ""}></textarea>
                </div>
                <div class="epp-task-edit-field epp-task-edit-field-wide">
                    <label for="my-task-update-next-step">Next Step (optional)</label>
                    <textarea id="my-task-update-next-step" name="next_step" rows="2" maxlength="1500" placeholder="What will happen next?"${isSaving ? " disabled" : ""}></textarea>
                </div>
                <div class="epp-task-edit-field epp-task-edit-field-wide">
                    <label for="my-task-update-attachments">Attachments (optional)</label>
                    <input id="my-task-update-attachments" name="attachments" type="file" multiple${isSaving ? " disabled" : ""}>
                    <small class="epp-task-update-file-help">Images, PDF, TXT, CSV, Microsoft Office, and supported video files are uploaded privately.</small>
                </div>
                <div id="my-task-update-error" class="epp-alert epp-alert-error hidden"></div>
                <div class="epp-task-edit-actions">
                    <button type="submit" class="epp-primary-button"${isSaving ? " disabled" : ""}>${isSaving ? "Saving Update..." : "Save Update"}</button>
                </div>
            </form>
        </section>
        <section class="epp-task-update-section">
            <div class="epp-task-update-section-header"><div><span class="epp-section-label">Activity</span><h3>Update Timeline</h3></div><span>${updates.length} update${updates.length === 1 ? "" : "s"}</span></div>
            <div class="epp-task-update-timeline">${updateRows}</div>
        </section>
        <section class="epp-task-update-section">
            <div class="epp-task-update-section-header"><div><span class="epp-section-label">Files</span><h3>Attachments</h3></div><span>${attachments.length} file${attachments.length === 1 ? "" : "s"}</span></div>
            <div class="epp-task-attachments">${attachmentRows}</div>
        </section>
    `;
}

function eppRenderMyTaskDetails(task) {
    const container = eppGetEl("my-task-drawer-content");

    if (!container) {
        return;
    }

    projectPortalState.myTasks.detail = task;
    projectPortalState.myTasks.editing = false;

    const percentage = eppClampPercentage(task.progress);
    const priority = task.priority || "No Priority";
    const hasEditableFields = Array.isArray(task.editable_fields) && task.editable_fields.length;
    const activeWorkTask = task.active_work?.task || "";
    const isWorking = activeWorkTask === task.name;
    const hasAnotherActiveSession = Boolean(activeWorkTask && !isWorking);
    const isClosed = ["completed", "cancelled"].includes(
        String(task.status || "").toLowerCase()
    );
    const isWorkActionPending = projectPortalState.myTasks.workingTask === task.name;
    const workAction = isClosed ? "" : `
        <div class="epp-task-detail-toolbar">
            <span>${isWorking ? "Work is running for this task." : hasAnotherActiveSession ? "Another task has a running work session." : "Start a work session for this task."}</span>
            <button type="button" class="${isWorking ? "epp-secondary-button" : "epp-primary-button"}" data-task-work-action="${isWorking ? "stop" : "start"}" data-task-work="${eppEscapeHtml(task.name || "")}"${hasAnotherActiveSession || isWorkActionPending ? " disabled" : ""}>
                ${isWorkActionPending ? "Saving..." : isWorking ? "Stop Work" : hasAnotherActiveSession ? "Another task running" : "Start Work"}
            </button>
        </div>
    `;
    const editAction = hasEditableFields ? `
        <div class="epp-task-detail-toolbar">
            <span>Task Owner can update this task.</span>
            <button type="button" class="epp-secondary-button" data-edit-my-task>Edit Task</button>
        </div>
    ` : "";

    eppSetText("my-task-detail-subject", task.subject || task.name || "Task");
    container.innerHTML = `
        ${workAction}
        ${editAction}
        <div class="epp-task-detail-pills">
            <span class="epp-task-status-pill ${eppGetTaskStatusClass(task.status)}">${eppEscapeHtml(task.status || "Open")}</span>
            <span class="epp-task-priority ${eppGetMyTaskPriorityClass(task.priority)}">${eppEscapeHtml(priority)}</span>
        </div>
        <p class="epp-task-detail-description">${eppEscapeHtml(task.description || "No task description was added.")}</p>
        <div class="epp-task-detail-grid">
            <div><span>Task ID</span><strong>${eppEscapeHtml(task.name || "--")}</strong></div>
            <div><span>Project</span><strong>${eppEscapeHtml(task.project_label || task.project || "--")}</strong></div>
            <div><span>Task Owner</span><strong>${eppEscapeHtml(task.task_owner || "--")}</strong></div>
            <div><span>Task Type</span><strong>${eppEscapeHtml(task.activity_type || "--")}</strong></div>
            <div><span>Start Date</span><strong>${eppEscapeHtml(eppFormatDate(task.start_date))}</strong></div>
            <div><span>Due Date</span><strong>${eppEscapeHtml(eppFormatDate(task.due_date))}</strong></div>
            <div><span>Expected Time</span><strong>${eppEscapeHtml(eppFormatHours(task.expected_time))}</strong></div>
            <div><span>Actual Time</span><strong>${eppEscapeHtml(eppFormatHours(task.actual_time))}</strong></div>
        </div>
        <div class="epp-workspace-progress-row">
            <div class="epp-project-progress-head"><strong>Progress</strong><span>${percentage}%</span></div>
            <div class="epp-progress-track"><div class="epp-progress-bar" style="width: ${percentage}%"></div></div>
        </div>
        ${eppRenderTaskUpdateTimeline(task)}
    `;
}

function eppShowMyTaskEditError(message) {
    const element = eppGetEl("my-task-edit-error");

    if (!element) {
        return;
    }

    element.textContent = message;
    element.classList.remove("hidden");
}

function eppShowMyTaskUpdateError(message) {
    const element = eppGetEl("my-task-update-error");

    if (!element) {
        return;
    }

    element.textContent = message;
    element.classList.remove("hidden");
}

async function eppUploadTaskAttachment(taskName, file) {
    const formData = new FormData();
    formData.append("task", taskName);
    formData.append("file", file, file.name);

    const response = await fetch(
        `/api/method/${PROJECT_PORTAL_METHODS.upload_task_attachment}`,
        {
            method: "POST",
            credentials: "same-origin",
            headers: {
                Accept: "application/json",
                "X-Frappe-CSRF-Token": frappe.csrf_token || ""
            },
            body: formData
        }
    );
    const responseData = await response.json().catch(() => ({}));

    if (!response.ok || responseData.exc) {
        const error = new Error(
            responseData.message || "Unable to upload this attachment."
        );

        error._server_messages = responseData._server_messages;
        error.responseJSON = responseData;
        throw error;
    }

    return responseData.message;
}

async function eppSaveMyTaskUpdate(form) {
    const myTasks = projectPortalState.myTasks;
    const task = myTasks.detail;

    if (!task || myTasks.saving || myTasks.updating) {
        return;
    }

    const formData = new FormData(form);
    const update = { task: task.name };
    const attachments = Array.from(
        form.querySelector("[name='attachments']")?.files || []
    );

    for (const [fieldname, value] of formData.entries()) {
        if (fieldname !== "attachments") {
            update[fieldname] = value;
        }
    }

    myTasks.updating = true;
    form.querySelectorAll("button, input, select, textarea").forEach((element) => {
        element.disabled = true;
    });

    try {
        const response = await eppCallPortal("add_task_update", update);
        const failedAttachments = [];

        for (const attachment of attachments) {
            try {
                await eppUploadTaskAttachment(task.name, attachment);
            } catch (error) {
                failedAttachments.push(
                    `${attachment.name}: ${eppGetErrorMessage(error, "Upload failed.")}`
                );
            }
        }

        myTasks.updating = false;
        await eppOpenMyTaskDetails(task.name);
        eppLoadDashboard();
        eppLoadMyTasks();

        if (eppGetPortalPage() === "task-board") {
            eppLoadTaskBoard();
        }

        if (failedAttachments.length) {
            frappe.show_alert({
                message: `Task update saved. ${failedAttachments.length} attachment${failedAttachments.length === 1 ? "" : "s"} could not be uploaded.`,
                indicator: "orange"
            });
            console.error("Task attachment upload errors:", failedAttachments);
            return;
        }

        frappe.show_alert({ message: "Task update saved.", indicator: "green" });
    } catch (error) {
        myTasks.updating = false;
        form.querySelectorAll("button, input, select, textarea").forEach((element) => {
            element.disabled = false;
        });
        eppShowMyTaskUpdateError(
            eppGetErrorMessage(error, "Unable to save this task update.")
        );
        console.error("Task update API Error:", error);
    }
}

function eppStartMyTaskEdit() {
    const myTasks = projectPortalState.myTasks;

    if (!myTasks.detail || myTasks.saving || myTasks.updating) {
        return;
    }

    myTasks.editing = true;
    eppRenderMyTaskEditForm(myTasks.detail);
}

function eppCancelMyTaskEdit() {
    const myTasks = projectPortalState.myTasks;

    if (!myTasks.detail || myTasks.saving || myTasks.updating) {
        return;
    }

    eppRenderMyTaskDetails(myTasks.detail);
}

async function eppSaveMyTask(form) {
    const myTasks = projectPortalState.myTasks;
    const task = myTasks.detail;

    if (!task || myTasks.saving) {
        return;
    }

    const formData = new FormData(form);
    const updates = { task: task.name };

    for (const [fieldname, value] of formData.entries()) {
        updates[fieldname] = value;
    }

    myTasks.saving = true;
    form.querySelectorAll("button, input, select, textarea").forEach((element) => {
        element.disabled = true;
    });

    try {
        const response = await eppCallPortal("update_my_task", updates);
        const updatedTask = response?.task || task;

        myTasks.saving = false;

        if (response?.ownership_transferred) {
            eppCloseMyTaskDrawer();
            myTasks.detail = null;
            frappe.show_alert({
                message: "Task Owner updated. The task now appears for the new owner.",
                indicator: "green"
            });
            eppLoadMyTasks();
            if (eppGetPortalPage() === "task-board") {
                eppLoadTaskBoard();
            }
            return;
        }

        eppRenderMyTaskDetails(updatedTask);
        frappe.show_alert({ message: "Task updated.", indicator: "green" });
        eppLoadMyTasks();
        if (eppGetPortalPage() === "task-board") {
            eppLoadTaskBoard();
        }
    } catch (error) {
        myTasks.saving = false;
        form.querySelectorAll("button, input, select, textarea").forEach((element) => {
            element.disabled = false;
        });
        eppShowMyTaskEditError(eppGetErrorMessage(error, "Unable to update this task."));
        console.error("Task update API Error:", error);
    }
}

async function eppOpenMyTaskDetails(taskName) {
    if (!taskName) {
        return;
    }

    const requestId = ++projectPortalState.myTasks.detailRequestId;
    const drawerContent = eppGetEl("my-task-drawer-content");

    projectPortalState.myTasks.detail = null;
    projectPortalState.myTasks.editing = false;
    eppSetText("my-task-detail-subject", "Loading Task");

    if (drawerContent) {
        drawerContent.innerHTML = `
            <div class="epp-loading-state">Loading task details...</div>
        `;
    }
    eppSetMyTaskDrawerOpen(true);

    try {
        const response = await eppCallPortal("get_task_details", { task: taskName });

        if (requestId !== projectPortalState.myTasks.detailRequestId) {
            return;
        }

        eppRenderMyTaskDetails(response?.task || {});
    } catch (error) {
        if (requestId !== projectPortalState.myTasks.detailRequestId) {
            return;
        }

        const message = eppGetErrorMessage(error, "Unable to load task details.");
        if (drawerContent) {
            drawerContent.innerHTML = `
                <div class="epp-section-empty">${eppEscapeHtml(message)}</div>
            `;
        }
        console.error("Task Detail API Error:", error);
    }
}

// This formats standard ERPNext hour fields for compact read-only task metadata.
function eppFormatHours(value) {
    const hours = Number(value) || 0;

    return `${hours.toLocaleString("en-IN", {
        maximumFractionDigits: 1
    })}h`;
}

function eppGetTaskStatusClass(status) {
    const normalizedStatus = String(status || "").toLowerCase();

    if (normalizedStatus === "completed") {
        return "is-completed";
    }

    if (normalizedStatus === "working") {
        return "is-working";
    }

    if (normalizedStatus === "pending review") {
        return "is-review";
    }

    if (normalizedStatus === "cancelled") {
        return "is-cancelled";
    }

    return "is-open";
}

function eppShowWorkspaceError(message) {
    const element = eppGetEl("workspace-error");

    if (!element) {
        return;
    }

    element.textContent = message;
    element.classList.remove("hidden");
}

function eppHideWorkspaceError() {
    const element = eppGetEl("workspace-error");

    if (!element) {
        return;
    }

    element.textContent = "";
    element.classList.add("hidden");
}

function eppSetWorkspaceLoading(isLoading) {
    projectPortalState.workspace.loading = isLoading;

    eppGetEl("workspace-loading")?.classList.toggle(
        "hidden",
        !isLoading
    );

    eppGetEl("workspace-content")?.classList.toggle(
        "hidden",
        isLoading
    );
}

function eppRenderWorkspaceMembers(members) {
    const container = eppGetEl("workspace-members");

    if (!container) {
        return;
    }

    if (!members.length) {
        container.innerHTML = `
            <span class="epp-member-empty">
                No project members configured.
            </span>
        `;
        return;
    }

    container.innerHTML = members
        .map((member) => {
            const name = member.full_name || member.user || "Member";

            return `
                <span class="epp-member-avatar" title="${eppEscapeHtml(name)}">
                    ${eppEscapeHtml(eppGetInitials(name))}
                </span>
            `;
        })
        .join("");
}

function eppRenderWorkspaceOverview() {
    const workspace = projectPortalState.workspace.data || {};
    const project = workspace.project || {};
    const summary = workspace.task_summary || {};
    const percentage = eppClampPercentage(project.percent_complete);
    const statusElement = eppGetEl("workspace-project-status");

    eppSetText(
        "workspace-project-name",
        project.project_name || project.name || "Project"
    );
    eppSetText("workspace-project-code", project.name || "--");
    eppSetText(
        "workspace-project-notes",
        project.notes || "No project description was added."
    );
    eppSetText("workspace-project-customer", project.customer || "--");
    eppSetText("workspace-project-type", project.project_type || "--");
    eppSetText(
        "workspace-project-start-date",
        eppFormatDate(project.expected_start_date)
    );
    eppSetText(
        "workspace-project-end-date",
        eppFormatDate(project.expected_end_date)
    );
    eppSetText("workspace-project-progress", `${percentage}%`);
    eppSetText("workspace-task-total", Number(summary.total) || 0);
    eppSetText("workspace-task-open", Number(summary.open) || 0);
    eppSetText("workspace-task-working", Number(summary.working) || 0);
    eppSetText("workspace-task-review", Number(summary.review) || 0);
    eppSetText("workspace-task-completed", Number(summary.completed) || 0);

    const progressBar = eppGetEl("workspace-project-progress-bar");

    if (progressBar) {
        progressBar.style.width = `${percentage}%`;
    }

    if (statusElement) {
        statusElement.textContent = project.status || "Open";
        statusElement.className = [
            "epp-project-status-pill",
            eppGetProjectStatusClass(project.status)
        ].filter(Boolean).join(" ");
    }

    eppRenderWorkspaceMembers(project.members || []);
}

function eppRenderWorkspaceTaskPagination() {
    eppRenderPaginationFooter({
        state: projectPortalState.workspace,
        elementId: "workspace-task-pagination",
        summaryId: "workspace-task-pagination-summary",
        pageNumbersId: "workspace-task-page-numbers",
        singularLabel: "Task",
        pluralLabel: "Tasks"
    });
}

function eppRenderWorkspaceTasks() {
    const workspace = projectPortalState.workspace;
    const container = eppGetEl("workspace-task-list");
    const tasks = workspace.data?.tasks || [];

    if (!container) {
        return;
    }

    if (!tasks.length) {
        container.innerHTML = `
            <div class="epp-section-empty">
                No permitted tasks matched the selected filters.
            </div>
        `;
        eppRenderWorkspaceTaskPagination();
        return;
    }

    container.innerHTML = tasks
        .map((task) => {
            const percentage = eppClampPercentage(task.progress);
            const owner = task.custom_task_owner || "Unassigned";

            return `
                <article class="epp-workspace-task-row">
                    <div class="epp-workspace-task-main">
                        <strong>${eppEscapeHtml(task.subject || task.name || "Untitled Task")}</strong>
                        <span>${eppEscapeHtml(task.name || "")}</span>
                    </div>

                    <div class="epp-workspace-task-status">
                        <span class="epp-task-status-pill ${eppGetTaskStatusClass(task.status)}">
                            ${eppEscapeHtml(task.status || "Open")}
                        </span>
                    </div>

                    <div class="epp-workspace-task-meta">
                        <span>Owner: ${eppEscapeHtml(owner)}</span>
                        <span>Due: ${eppEscapeHtml(eppFormatDate(task.exp_end_date))}</span>
                        <span>Time: ${eppEscapeHtml(eppFormatHours(task.actual_time))} / ${eppEscapeHtml(eppFormatHours(task.expected_time))}</span>
                    </div>

                    <div class="epp-workspace-task-progress">
                        <div class="epp-project-progress-head">
                            <strong>Progress</strong>
                            <span>${percentage}%</span>
                        </div>
                        <div class="epp-progress-track">
                            <div class="epp-progress-bar" style="width: ${percentage}%"></div>
                        </div>
                    </div>
                </article>
            `;
        })
        .join("");

    eppRenderWorkspaceTaskPagination();
}

function eppReadWorkspaceTaskFilters() {
    return {
        search: eppGetEl("workspace-task-search")?.value.trim() || "",
        status: eppGetEl("workspace-task-status-filter")?.value || "All"
    };
}

function eppSyncWorkspaceTaskFilters() {
    const filters = projectPortalState.workspace.filters;
    const searchInput = eppGetEl("workspace-task-search");
    const statusSelect = eppGetEl("workspace-task-status-filter");

    if (searchInput) {
        searchInput.value = filters.search;
    }

    if (statusSelect) {
        statusSelect.value = filters.status;
    }
}

// This loads the selected Project and its permission-filtered Task page from the server.
async function eppLoadWorkspace({ resetPage = false } = {}) {
    const workspace = projectPortalState.workspace;

    if (!workspace.projectName) {
        return;
    }

    if (resetPage) {
        workspace.page = 1;
    }

    const requestId = ++workspace.requestId;

    eppHideWorkspaceError();
    eppSetWorkspaceLoading(true);

    try {
        const response = await eppCallPortal(
            "get_project_workspace",
            {
                project: workspace.projectName,
                search: workspace.filters.search,
                status: workspace.filters.status,
                page: workspace.page,
                page_length: workspace.pageLength
            }
        );

        if (requestId !== workspace.requestId) {
            return;
        }

        workspace.data = response || {};
        workspace.pagination = response?.pagination || workspace.pagination;
        workspace.page = Number(response?.pagination?.page) || workspace.page;

        eppRenderWorkspaceOverview();
        eppRenderWorkspaceTasks();
    } catch (error) {
        if (requestId !== workspace.requestId) {
            return;
        }

        const message = eppGetErrorMessage(
            error,
            "Unable to load the Project workspace."
        );

        eppShowWorkspaceError(message);
        eppGetEl("workspace-task-list").innerHTML = `
            <div class="epp-section-empty">
                ${eppEscapeHtml(message)}
            </div>
        `;
        console.error("Project Workspace API Error:", error);
    } finally {
        if (requestId === workspace.requestId) {
            eppSetWorkspaceLoading(false);
            eppRenderWorkspaceTaskPagination();
        }
    }
}

function eppScheduleWorkspaceTaskSearch() {
    const workspace = projectPortalState.workspace;

    if (workspace.searchTimer) {
        clearTimeout(workspace.searchTimer);
    }

    workspace.searchTimer = setTimeout(
        () => {
            workspace.filters = eppReadWorkspaceTaskFilters();
            eppLoadWorkspace({ resetPage: true });
        },
        350
    );
}

function eppSetSidebarOpen(isOpen) {
    const sidebar = document.querySelector(".epp-sidebar");
    const backdrop = eppGetEl("epp-sidebar-backdrop");

    sidebar?.classList.toggle("is-open", isOpen);
    backdrop?.classList.toggle("hidden", !isOpen);
    document.body.style.overflow = isOpen ? "hidden" : "";
}

function eppCloseSidebar() {
    eppSetSidebarOpen(false);
}

function eppScheduleProjectSearch() {
    if (projectPortalState.projects.searchTimer) {
        clearTimeout(projectPortalState.projects.searchTimer);
    }

    projectPortalState.projects.searchTimer = setTimeout(
        () => {
            projectPortalState.projects.filters =
                eppReadProjectFilters();

            eppLoadProjects({
                resetPage: true
            });
        },
        350
    );
}

function eppResetProjectFilters() {
    projectPortalState.projects.filters = {
        search: "",
        status: "Open",
        sort: "recent"
    };
    projectPortalState.projects.page = 1;

    eppSyncProjectFilterControls();
    eppLoadProjects({
        resetPage: true
    });
}

function eppHandleProjectOpen(projectName) {
    if (!projectName) {
        return;
    }

    // This URL remains refresh-safe because Frappe resolves the Project name dynamically.
    window.location.assign(
        `/shayona/projects/${encodeURIComponent(projectName)}`
    );
}

function eppPrepareWorkspace(projectName) {
    if (!projectName) {
        return;
    }

    const workspace = projectPortalState.workspace;

    // Opening a Project starts its task filters and pagination from their defaults.
    workspace.projectName = projectName;
    workspace.data = null;
    workspace.filters = {
        search: "",
        status: "All"
    };
    workspace.page = 1;
    workspace.pagination = {
        page: 1,
        page_length: workspace.pageLength,
        has_previous: false,
        has_more: false
    };

    eppSyncWorkspaceTaskFilters();
}

function eppBindEvents() {
    eppGetEl("btn-toggle-sidebar")?.addEventListener(
        "click",
        () => {
            const sidebar = document.querySelector(".epp-sidebar");
            const isOpen = sidebar?.classList.contains("is-open");
            eppSetSidebarOpen(!isOpen);
        }
    );

    eppGetEl("epp-sidebar-backdrop")?.addEventListener(
        "click",
        eppCloseSidebar
    );

    eppGetEl("btn-project-portal-notifications")?.addEventListener(
        "click",
        () => {
            const isOpen = eppGetEl("project-portal-notification-drawer")
                ?.classList.contains("is-open");

            if (isOpen) {
                eppCloseNotificationDrawer();
                return;
            }

            eppSetNotificationDrawerOpen(true);
            eppLoadNotifications();
        }
    );

    eppGetEl("btn-close-project-portal-notifications")?.addEventListener(
        "click",
        eppCloseNotificationDrawer
    );

    eppGetEl("project-portal-notification-backdrop")?.addEventListener(
        "click",
        eppCloseNotificationDrawer
    );

    eppGetEl("btn-mark-project-portal-notifications-read")?.addEventListener(
        "click",
        eppMarkProjectPortalNotificationsRead
    );

    eppGetEl("project-search")?.addEventListener(
        "input",
        eppScheduleProjectSearch
    );

    eppGetEl("project-status-filter")?.addEventListener(
        "change",
        () => {
            projectPortalState.projects.filters =
                eppReadProjectFilters();

            eppLoadProjects({
                resetPage: true
            });
        }
    );

    eppGetEl("project-sort-filter")?.addEventListener(
        "change",
        () => {
            projectPortalState.projects.filters =
                eppReadProjectFilters();

            eppLoadProjects({
                resetPage: true
            });
        }
    );

    eppGetEl("btn-reset-project-filters")?.addEventListener(
        "click",
        eppResetProjectFilters
    );

    eppGetEl("my-task-search")?.addEventListener(
        "input",
        eppScheduleMyTaskSearch
    );

    [
        "my-task-status-filter",
        "my-task-priority-filter",
        "my-task-due-filter"
    ].forEach((id) => {
        eppGetEl(id)?.addEventListener("change", () => {
            projectPortalState.myTasks.filters = eppGetMyTaskFilters();
            eppLoadMyTasks({ resetPage: true });
        });
    });

    eppGetEl("btn-reset-my-task-filters")?.addEventListener(
        "click",
        eppResetMyTaskFilters
    );

    ["timesheet-period-filter", "timesheet-status-filter"].forEach((id) => {
        eppGetEl(id)?.addEventListener("change", () => {
            projectPortalState.timesheets.filters = eppGetTimesheetFilters();
            eppLoadTimesheets({ resetPage: true });
        });
    });

    eppGetEl("btn-reset-timesheet-filters")?.addEventListener(
        "click",
        eppResetTimesheetFilters
    );

    eppGetEl("task-board-search")?.addEventListener(
        "input",
        eppScheduleTaskBoardSearch
    );

    eppGetEl("btn-reset-task-board-filters")?.addEventListener(
        "click",
        eppResetTaskBoardFilters
    );

    eppGetEl("workspace-task-search")?.addEventListener(
        "input",
        eppScheduleWorkspaceTaskSearch
    );

    eppGetEl("workspace-task-status-filter")?.addEventListener(
        "change",
        () => {
            projectPortalState.workspace.filters =
                eppReadWorkspaceTaskFilters();

            eppLoadWorkspace({ resetPage: true });
        }
    );

    eppBindPaginationControls(
        "projects-pagination",
        projectPortalState.projects,
        () => eppLoadProjects({ scrollToTop: true })
    );
    eppBindPaginationControls(
        "my-tasks-pagination",
        projectPortalState.myTasks,
        () => eppLoadMyTasks({ scrollToTop: true })
    );
    eppBindPaginationControls(
        "timesheets-pagination",
        projectPortalState.timesheets,
        eppLoadTimesheets
    );
    eppBindPaginationControls(
        "workspace-task-pagination",
        projectPortalState.workspace,
        eppLoadWorkspace
    );

    eppGetEl("projects-list")?.addEventListener(
        "click",
        (event) => {
            const button = event.target.closest("[data-open-project]");

            if (!button?.dataset.openProject) {
                return;
            }

            eppHandleProjectOpen(button.dataset.openProject);
        }
    );

    eppGetEl("my-tasks-list")?.addEventListener(
        "click",
        (event) => {
            const button = event.target.closest("[data-open-task]");

            if (!button?.dataset.openTask) {
                return;
            }

            eppOpenMyTaskDetails(button.dataset.openTask);
        }
    );

    eppGetEl("task-board-lanes")?.addEventListener(
        "click",
        (event) => {
            const workButton = event.target.closest("[data-task-work-action]");

            if (workButton?.dataset.taskWork) {
                event.stopPropagation();
                eppSetMyTaskWork(
                    workButton.dataset.taskWork,
                    workButton.dataset.taskWorkAction
                );
                return;
            }

            const card = event.target.closest("[data-open-board-task]");

            if (!card?.dataset.openBoardTask) {
                return;
            }

            eppOpenMyTaskDetails(card.dataset.openBoardTask);
        }
    );

    eppGetEl("task-board-lanes")?.addEventListener(
        "keydown",
        (event) => {
            if (event.key !== "Enter" && event.key !== " ") {
                return;
            }

            if (event.target.closest("button")) {
                return;
            }

            const card = event.target.closest("[data-open-board-task]");

            if (!card?.dataset.openBoardTask) {
                return;
            }

            event.preventDefault();
            eppOpenMyTaskDetails(card.dataset.openBoardTask);
        }
    );

    eppGetEl("task-board-lanes")?.addEventListener(
        "dragstart",
        (event) => {
            const card = event.target.closest("[data-open-board-task]");

            if (!card?.dataset.openBoardTask || !event.dataTransfer) {
                return;
            }

            event.dataTransfer.effectAllowed = "move";
            event.dataTransfer.setData("text/plain", card.dataset.openBoardTask);
            card.classList.add("is-dragging");
        }
    );

    eppGetEl("task-board-lanes")?.addEventListener(
        "dragend",
        (event) => {
            event.target.closest("[data-open-board-task]")?.classList.remove("is-dragging");
            eppClearTaskBoardDropTargets();
        }
    );

    eppGetEl("task-board-lanes")?.addEventListener(
        "dragover",
        (event) => {
            const dropzone = event.target.closest(".epp-task-board-dropzone");

            if (!dropzone?.dataset.taskBoardStatus) {
                return;
            }

            event.preventDefault();
            if (event.dataTransfer) {
                event.dataTransfer.dropEffect = "move";
            }
            eppClearTaskBoardDropTargets();
            dropzone.classList.add("is-drop-target");
        }
    );

    eppGetEl("task-board-lanes")?.addEventListener(
        "dragleave",
        (event) => {
            const dropzone = event.target.closest(".epp-task-board-dropzone");

            if (dropzone && !dropzone.contains(event.relatedTarget)) {
                dropzone.classList.remove("is-drop-target");
            }
        }
    );

    eppGetEl("task-board-lanes")?.addEventListener(
        "drop",
        (event) => {
            const dropzone = event.target.closest(".epp-task-board-dropzone");

            if (!dropzone?.dataset.taskBoardStatus) {
                return;
            }

            event.preventDefault();
            const taskName = event.dataTransfer?.getData("text/plain") || "";
            eppClearTaskBoardDropTargets();
            eppMoveTaskOnBoard(taskName, dropzone.dataset.taskBoardStatus);
        }
    );

    eppGetEl("btn-close-my-task-drawer")?.addEventListener(
        "click",
        eppCloseMyTaskDrawer
    );

    eppGetEl("my-task-drawer-backdrop")?.addEventListener(
        "click",
        eppCloseMyTaskDrawer
    );

    eppGetEl("my-task-drawer-content")?.addEventListener(
        "click",
        (event) => {
            const workButton = event.target.closest("[data-task-work-action]");

            if (workButton?.dataset.taskWork) {
                eppSetMyTaskWork(
                    workButton.dataset.taskWork,
                    workButton.dataset.taskWorkAction
                );
                return;
            }

            if (event.target.closest("[data-edit-my-task]")) {
                eppStartMyTaskEdit();
                return;
            }

            if (event.target.closest("[data-cancel-my-task-edit]")) {
                eppCancelMyTaskEdit();
            }
        }
    );

    eppGetEl("my-task-drawer-content")?.addEventListener(
        "submit",
        (event) => {
            const updateForm = event.target.closest("#my-task-update-form");

            if (updateForm) {
                event.preventDefault();
                eppSaveMyTaskUpdate(updateForm);
                return;
            }

            const form = event.target.closest("#my-task-edit-form");

            if (!form) {
                return;
            }

            event.preventDefault();
            eppSaveMyTask(form);
        }
    );

    window.addEventListener(
        "resize",
        () => {
            if (window.innerWidth > 980) {
                eppCloseSidebar();
            }
        }
    );

    document.addEventListener(
        "keydown",
        (event) => {
            if (event.key === "Escape") {
                eppCloseSidebar();
                eppCloseMyTaskDrawer();
                eppCloseNotificationDrawer();
            }
        }
    );
}

async function eppInitializeProjectPortal() {
    if (projectPortalState.initialized) {
        return;
    }

    projectPortalState.initialized = true;

    eppBindEvents();
    eppRenderHeader();

    const portalPage = eppGetPortalPage();

    await Promise.all([eppLoadDashboard(), eppLoadNotifications()]);

    if (portalPage === "projects") {
        eppSyncProjectFilterControls();
        eppLoadProjects();
        return;
    }

    if (portalPage === "my-tasks") {
        eppSyncMyTaskFilterControls();
        eppLoadMyTasks();
        return;
    }

    if (portalPage === "timesheets") {
        eppSyncTimesheetFilterControls();
        eppLoadTimesheets();
        return;
    }

    if (portalPage === "task-board") {
        eppLoadTaskBoard();
        return;
    }

    if (portalPage === "workspace") {
        const projectName = eppGetRouteProjectName();

        if (!projectName) {
            eppShowWorkspaceError("The Project name is missing from this URL.");
            return;
        }

        eppPrepareWorkspace(projectName);
        eppLoadWorkspace({ resetPage: true });
    }

}

if (document.readyState === "loading") {
    document.addEventListener(
        "DOMContentLoaded",
        eppInitializeProjectPortal
    );
} else {
    eppInitializeProjectPortal();
}

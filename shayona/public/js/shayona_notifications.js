(function () {
    if (typeof frappe === "undefined" || frappe.session.user === "Guest") {
        return;
    }

    const REALTIME_EVENT = "shayona_alert_popup";
    const BADGE_CLASS = "shayona-notification-count";
    const STYLE_ID = "shayona-notification-style";
    const seenAlerts = new Set();

    function injectStyles() {
        if (document.getElementById(STYLE_ID)) {
            return;
        }

        const style = document.createElement("style");
        style.id = STYLE_ID;
        style.innerHTML = `
            .sidebar-notification .sidebar-item-icon {
                position: relative;
            }

            .${BADGE_CLASS} {
                position: absolute;
                top: -6px;
                right: -10px;
                min-width: 16px;
                height: 16px;
                padding: 0 4px;
                border-radius: 999px;
                background: var(--red-500, #ef4444);
                color: #fff;
                font-size: 10px;
                line-height: 16px;
                text-align: center;
                font-weight: 600;
                z-index: 3;
            }
        `;
        document.head.appendChild(style);
    }

    function getNotificationIcon() {
        return document.querySelector(".sidebar-notification .sidebar-item-icon");
    }

    function ensureBadgeNode() {
        const icon = getNotificationIcon();
        if (!icon) {
            return null;
        }

        let badge = icon.querySelector(`.${BADGE_CLASS}`);
        if (!badge) {
            badge = document.createElement("span");
            badge.className = `${BADGE_CLASS} hidden`;
            badge.textContent = "0";
            icon.appendChild(badge);
        }

        return badge;
    }

    function updateBadge(count) {
        const badge = ensureBadgeNode();
        if (!badge) {
            return;
        }

        const parsedCount = Number.parseInt(count, 10) || 0;
        if (parsedCount <= 0) {
            badge.classList.add("hidden");
            badge.textContent = "0";
            return;
        }

        badge.classList.remove("hidden");
        badge.textContent = parsedCount > 99 ? "99+" : `${parsedCount}`;
    }

    function refreshBadge() {
        return frappe
            .xcall("shayona.notifications.get_unread_notification_count")
            .then((count) => {
                updateBadge(count);
            })
            .catch(() => {});
    }

    function getPopupMessage(data) {
        const subject = frappe.utils.escape_html(data?.subject || __("You have a new alert"));
        const doctype = frappe.utils.escape_html(data?.document_type || "");
        const docname = frappe.utils.escape_html(data?.document_name || "");

        let meta = "";
        if (doctype && docname) {
            meta = `<div class="text-muted" style="margin-top: 8px;">${doctype}: ${docname}</div>`;
        }

        return `<div>${subject}</div>${meta}`;
    }

    function getPrimaryAction(data) {
        if (data?.document_type && data?.document_name) {
            return {
                label: __("Open"),
                action: function () {
                    frappe.set_route("Form", data.document_type, data.document_name);
                },
            };
        }

        if (data?.link) {
            return {
                label: __("Open"),
                action: function () {
                    window.location.href = data.link;
                },
            };
        }

        return null;
    }

    function showPopup(data) {
        if (!data?.name || seenAlerts.has(data.name)) {
            return;
        }

        seenAlerts.add(data.name);
        if (seenAlerts.size > 200) {
            seenAlerts.clear();
        }

        const config = {
            title: __("Reminder Alert"),
            message: getPopupMessage(data),
            indicator: "orange",
            wide: false,
        };

        const primaryAction = getPrimaryAction(data);
        if (primaryAction) {
            config.primary_action = primaryAction;
        }

        frappe.msgprint(config);
    }

    function setupRealtimeListeners() {
        if (!frappe.realtime || typeof frappe.realtime.on !== "function") {
            return;
        }

        frappe.realtime.on(REALTIME_EVENT, function (data) {
            showPopup(data || {});
            refreshBadge();
        });

        frappe.realtime.on("notification", function () {
            refreshBadge();
        });
    }

    function setupBadgeRefreshTriggers() {
        document.addEventListener("click", function (event) {
            const target = event.target;
            if (!target || typeof target.closest !== "function") return;

            const markOne = target.closest(".dropdown-notifications .mark-as-read");
            const markAll = target.closest(".dropdown-notifications .mark-all-read");

            if (markOne || markAll) {
                setTimeout(refreshBadge, 300);
            }
        });

        window.addEventListener("focus", refreshBadge);
        setInterval(refreshBadge, 60000);
    }

    function ensureBadgeWhenSidebarReady() {
        const maxWaitMs = 12000;
        const start = Date.now();
        const timer = setInterval(() => {
            if (getNotificationIcon()) {
                clearInterval(timer);
                ensureBadgeNode();
                refreshBadge();
                return;
            }

            if (Date.now() - start >= maxWaitMs) {
                clearInterval(timer);
            }
        }, 200);
    }

    function initialize() {
        if (window.__shayona_notifications_initialized) {
            return;
        }

        window.__shayona_notifications_initialized = true;
        injectStyles();
        setupRealtimeListeners();
        setupBadgeRefreshTriggers();
        ensureBadgeWhenSidebarReady();
        refreshBadge();
    }

    initialize();
})();

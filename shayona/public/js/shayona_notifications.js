(function () {
    if (typeof frappe === "undefined" || frappe.session.user === "Guest") {
        return;
    }

    const CONFIG = {
        realtimeEventName: "shayona_alert_popup",
        unreadCountMethod: "shayona.overrides.notifications.get_unread_notification_count",
        sidebarBadgeClass: "shayona-notification-count-inline",
        navbarBadgeClass: "shayona-notification-count-navbar",
        styleElementId: "shayona-notification-style",
        maxPopupMemory: 200,
        maxBadgeCount: 99,
        socketReadyWaitMs: 12000,
        socketReadyPollIntervalMs: 250,
        badgeIconWaitMs: 12000,
        badgeIconPollIntervalMs: 200,
        badgeRefreshIntervalMs: 60000,
        badgeRefreshAfterReadMs: 300,
    };

    const SELECTORS = {
        sidebarNotificationAnchor: ".sidebar-notification .item-anchor",
        sidebarLabel: ".sidebar-item-label",
        navbarBellIcon:
            "header .desktop-notification-icon, header .notifications-icon, .navbar .desktop-notification-icon, .navbar .notifications-icon",
        markAsReadButton: ".dropdown-notifications .mark-as-read",
        markAllAsReadButton: ".dropdown-notifications .mark-all-read",
    };

    const state = {
        initialized: false,
        listenersBound: false,
        seenNotificationNames: new Set(),
        reconnectHookBound: false,
    };

    const handlers = {
        onAlertRealtimeEvent: function (payload) {
            showPopupIfEligible(payload || {});
            refreshUnreadBadge();
        },

        onNotificationRealtimeEvent: function () {
            refreshUnreadBadge();
        },

        onSocketReconnect: function () {
            state.listenersBound = false;
            bindRealtimeListenersIfReady();
        },
    };

    function initialize() {
        if (state.initialized || window.__shayona_notifications_initialized) {
            return;
        }

        state.initialized = true;
        window.__shayona_notifications_initialized = true;

        injectBadgeStyles();
        setupRealtimeListenersWithRetry();
        setupBadgeRefreshTriggers();
        ensureBadgeNodeWhenSidebarIsReady();
        refreshUnreadBadge();

        // When desk route changes, sidebar and realtime state may re-initialize.
        $(document).on("page-change", function () {
            if (!state.listenersBound) {
                setupRealtimeListenersWithRetry();
            }
        });
    }

    function injectBadgeStyles() {
        if (document.getElementById(CONFIG.styleElementId)) {
            return;
        }

        const styleElement = document.createElement("style");
        styleElement.id = CONFIG.styleElementId;
        styleElement.innerHTML = `
            .sidebar-notification .item-anchor {
                display: flex;
                align-items: center;
            }

            .sidebar-notification .sidebar-item-icon {
                position: relative;
            }

            .${CONFIG.sidebarBadgeClass} {
                margin-left: auto;
                min-width: 20px;
                height: 20px;
                padding: 0 6px;
                border-radius: 999px;
                border: 1px solid transparent;
                background: var(--ink-gray-7, #3f3f46);
                color: var(--bg-color, #ffffff);
                font-size: 11px;
                line-height: 18px;
                text-align: center;
                font-weight: 600;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                flex-shrink: 0;
            }

            html[data-theme-mode="dark"] .${CONFIG.sidebarBadgeClass},
            html[data-theme="dark"] .${CONFIG.sidebarBadgeClass},
            body[data-theme-mode="dark"] .${CONFIG.sidebarBadgeClass},
            body[data-theme="dark"] .${CONFIG.sidebarBadgeClass} {
                background: var(--ink-gray-1, #e5e7eb);
                color: var(--ink-gray-8, #111827);
            }

            .${CONFIG.navbarBadgeClass} {
                position: absolute;
                top: -6px;
                right: -7px;
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

        document.head.appendChild(styleElement);
    }

    function getSidebarNotificationAnchor() {
        return document.querySelector(SELECTORS.sidebarNotificationAnchor);
    }

    function ensureSidebarBadgeNode() {
        const sidebarNotificationAnchor = getSidebarNotificationAnchor();
        if (!sidebarNotificationAnchor) {
            return null;
        }

        let badgeElement = sidebarNotificationAnchor.querySelector(`.${CONFIG.sidebarBadgeClass}`);
        if (!badgeElement) {
            badgeElement = document.createElement("span");
            badgeElement.className = `${CONFIG.sidebarBadgeClass} hidden`;
            badgeElement.textContent = "0";
            const sidebarLabel = sidebarNotificationAnchor.querySelector(SELECTORS.sidebarLabel);
            if (sidebarLabel && sidebarLabel.nextSibling) {
                sidebarNotificationAnchor.insertBefore(badgeElement, sidebarLabel.nextSibling);
            } else {
                sidebarNotificationAnchor.appendChild(badgeElement);
            }
        }

        return badgeElement;
    }

    function ensureNavbarBadgeNode() {
        const navbarBadgeContainer = findNavbarBellBadgeContainer();
        if (!navbarBadgeContainer) {
            return null;
        }

        let badgeElement = navbarBadgeContainer.querySelector(`.${CONFIG.navbarBadgeClass}`);
        if (!badgeElement) {
            badgeElement = document.createElement("span");
            badgeElement.className = `${CONFIG.navbarBadgeClass} hidden`;
            badgeElement.textContent = "0";

            // Navbar bell can be svg/icon wrapper, keep badge positioning local.
            const computedPosition = window.getComputedStyle(navbarBadgeContainer).position;
            if (computedPosition === "static") {
                navbarBadgeContainer.style.position = "relative";
            }
            navbarBadgeContainer.appendChild(badgeElement);
        }

        return badgeElement;
    }

    function findNavbarBellBadgeContainer() {
        const directMatch = document.querySelector(SELECTORS.navbarBellIcon);
        if (directMatch) {
            return directMatch;
        }

        // Fallback: find notification svg icon in header and attach to nearest clickable wrapper.
        const notificationIconUseElement = document.querySelector(
            "header use[href*='notifications'], header use[xlink\\:href*='notifications']"
        );
        if (!notificationIconUseElement) {
            return null;
        }

        return (
            notificationIconUseElement.closest(
                "button, a, .nav-link, .toolbar-icon, .navbar-icon, .icon, span, div"
            ) || notificationIconUseElement.parentElement
        );
    }

    function applyCountToBadgeNode(badgeElement, unreadCountText) {
        if (!badgeElement) {
            return;
        }

        const parsedUnreadCount = Number.parseInt(unreadCountText, 10) || 0;
        if (parsedUnreadCount <= 0) {
            badgeElement.classList.add("hidden");
            badgeElement.textContent = "0";
            return;
        }

        badgeElement.classList.remove("hidden");
        badgeElement.textContent =
            parsedUnreadCount > CONFIG.maxBadgeCount
                ? `${CONFIG.maxBadgeCount}+`
                : `${parsedUnreadCount}`;
    }

    function updateUnreadBadgeCount(unreadCount) {
        const sidebarBadgeNode = ensureSidebarBadgeNode();
        const navbarBadgeNode = ensureNavbarBadgeNode();
        const countText = `${unreadCount}`;

        applyCountToBadgeNode(sidebarBadgeNode, countText);
        applyCountToBadgeNode(navbarBadgeNode, countText);
    }

    function refreshUnreadBadge() {
        return frappe
            .xcall(CONFIG.unreadCountMethod)
            .then(function (unreadCount) {
                updateUnreadBadgeCount(unreadCount);
            })
            .catch(function () {
                // Badge refresh failures should not block desk usage.
            });
    }

    function showPopupIfEligible(payload) {
        if (!payload || !payload.name) {
            return;
        }

        if (hasPopupBeenShown(payload.name)) {
            return;
        }

        markPopupAsShown(payload.name);

        const popupConfig = {
            title: __("Reminder Alert"),
            message: buildPopupMessage(payload),
            indicator: "orange",
            wide: false,
        };

        const primaryAction = buildPrimaryAction(payload);
        if (primaryAction) {
            popupConfig.primary_action = primaryAction;
        }

        frappe.msgprint(popupConfig);
    }

    function hasPopupBeenShown(notificationName) {
        return state.seenNotificationNames.has(notificationName);
    }

    function markPopupAsShown(notificationName) {
        state.seenNotificationNames.add(notificationName);

        if (state.seenNotificationNames.size > CONFIG.maxPopupMemory) {
            state.seenNotificationNames.clear();
            state.seenNotificationNames.add(notificationName);
        }
    }

    function buildPopupMessage(payload) {
        const safeSubject = frappe.utils.escape_html(payload.subject || __("You have a new alert"));
        const safeDocumentType = frappe.utils.escape_html(payload.document_type || "");
        const safeDocumentName = frappe.utils.escape_html(payload.document_name || "");

        let metadataHtml = "";
        if (safeDocumentType && safeDocumentName) {
            metadataHtml = `<div class="text-muted" style="margin-top: 8px;">${safeDocumentType}: ${safeDocumentName}</div>`;
        }

        return `<div>${safeSubject}</div>${metadataHtml}`;
    }

    function buildPrimaryAction(payload) {
        if (payload.document_type && payload.document_name) {
            return {
                label: __("Open"),
                action: function () {
                    frappe.set_route("Form", payload.document_type, payload.document_name);
                },
            };
        }

        if (payload.link) {
            return {
                label: __("Open"),
                action: function () {
                    window.location.href = payload.link;
                },
            };
        }

        return null;
    }

    function setupRealtimeListenersWithRetry() {
        if (bindRealtimeListenersIfReady()) {
            return;
        }

        const startTime = Date.now();
        const timer = setInterval(function () {
            if (bindRealtimeListenersIfReady()) {
                clearInterval(timer);
                return;
            }

            if (Date.now() - startTime >= CONFIG.socketReadyWaitMs) {
                clearInterval(timer);
            }
        }, CONFIG.socketReadyPollIntervalMs);
    }

    function bindRealtimeListenersIfReady() {
        if (!isRealtimeSocketReady()) {
            return false;
        }

        frappe.realtime.off(CONFIG.realtimeEventName, handlers.onAlertRealtimeEvent);
        frappe.realtime.off("notification", handlers.onNotificationRealtimeEvent);

        frappe.realtime.on(CONFIG.realtimeEventName, handlers.onAlertRealtimeEvent);
        frappe.realtime.on("notification", handlers.onNotificationRealtimeEvent);

        bindSocketReconnectHook();

        state.listenersBound = true;
        return true;
    }

    function isRealtimeSocketReady() {
        if (!frappe.realtime) {
            return false;
        }

        if (typeof frappe.realtime.on !== "function" || typeof frappe.realtime.off !== "function") {
            return false;
        }

        if (!frappe.realtime.socket) {
            return false;
        }

        return true;
    }

    function bindSocketReconnectHook() {
        if (state.reconnectHookBound || !frappe.realtime || !frappe.realtime.socket) {
            return;
        }

        frappe.realtime.socket.on("connect", handlers.onSocketReconnect);
        state.reconnectHookBound = true;
    }

    function setupBadgeRefreshTriggers() {
        document.addEventListener("click", function (event) {
            const clickTarget = event.target;
            if (!clickTarget || typeof clickTarget.closest !== "function") {
                return;
            }

            const clickedMarkAsRead = clickTarget.closest(SELECTORS.markAsReadButton);
            const clickedMarkAllAsRead = clickTarget.closest(SELECTORS.markAllAsReadButton);

            if (!clickedMarkAsRead && !clickedMarkAllAsRead) {
                return;
            }

            setTimeout(refreshUnreadBadge, CONFIG.badgeRefreshAfterReadMs);
        });

        window.addEventListener("focus", refreshUnreadBadge);
        setInterval(refreshUnreadBadge, CONFIG.badgeRefreshIntervalMs);
    }

    function ensureBadgeNodeWhenSidebarIsReady() {
        const startTime = Date.now();
        const timer = setInterval(function () {
            const sidebarAnchorExists = Boolean(getSidebarNotificationAnchor());
            const navbarBellExists = Boolean(findNavbarBellBadgeContainer());
            if (sidebarAnchorExists || navbarBellExists) {
                clearInterval(timer);
                ensureSidebarBadgeNode();
                ensureNavbarBadgeNode();
                refreshUnreadBadge();
                return;
            }

            if (Date.now() - startTime >= CONFIG.badgeIconWaitMs) {
                clearInterval(timer);
            }
        }, CONFIG.badgeIconPollIntervalMs);
    }

    initialize();
})();

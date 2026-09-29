(function () {
    const adminButton = document.getElementById("adminButton");
    const pinOverlay = document.getElementById("pinOverlay");
    const pinForm = document.getElementById("pinForm");
    const pinInput = document.getElementById("pinInput");
    const pinError = document.getElementById("pinError");
    const pinCancel = document.getElementById("pinCancel");
    const pinPrompt = document.getElementById("pinPrompt");
    const resetData = document.getElementById("resetData");
    const adminOverlay = document.getElementById("adminOverlay");
    const adminClose = document.getElementById("adminClose");
    const wineRows = document.getElementById("wineRows");
    const wineCount = document.getElementById("wineCount");
    const wineFilter = document.getElementById("wineFilter");
    const saveStatus = document.getElementById("saveStatus");
    const infoList = document.getElementById("infoList");
    const addWine = document.getElementById("addWine");
    const saveAll = document.getElementById("saveAll");
    const adminTitle = document.getElementById("adminTitle");


    let token = "";
    let wines = [];
    let dirty = false;
    let pinMode = "admin";
    let demoAdmin = false;

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text == null ? "" : String(text);
        return div.innerHTML;
    }

    async function adminFetch(path, options) {
        const response = await fetch(path, {
            ...options,
            headers: {
                "Content-Type": "application/json",
                Authorization: "Bearer " + token,
                ...(options && options.headers),
            },
        });
        const data = await response.json().catch(() => ({}));
        if (response.status === 401) {
            closeAdmin(true);
            throw new Error(data.detail || "Enter the admin pin.");
        }
        if (!response.ok) {
            const detail = data.detail;
            throw new Error(typeof detail === "string" ? detail : "Request failed");
        }
        return data;
    }

    function openPin(mode) {
        pinMode = mode || "admin";
        pinPrompt.textContent = pinMode === "reset"
            ? "Enter the 6-digit pin to erase the information counts."
            : "Enter the 6-digit admin pin.";
        pinError.textContent = "";
        pinInput.value = "";
        pinOverlay.hidden = false;
        pinInput.focus();
    }

    function closePin() {
        pinOverlay.hidden = true;
        pinInput.value = "";
    }

    const OUTLET_SALES = [
        {
            id: "pool",
            name: "Pool",
            hours: "10:00–19:00",
            service: "By the glass, plus a few bottles",
            band: "Under $60",
            orders: 44,
            wines: [
                { label: "NV Nino Franco Rustico Prosecco", qty: 24, revenue: 480 },
                { label: "NV Raventós i Blanc de Nit Rosé", qty: 16, revenue: 480 },
                { label: "2023 Yalumba The Y Series Riesling", qty: 14, revenue: 210 },
                { label: "2021 Hugel Riesling Classic", qty: 9, revenue: 225 },
            ],
            missed: ["California Primitivo"],
        },
        {
            id: "in-room",
            name: "In-Room",
            hours: "24 hours",
            service: "Bottles sent to the room",
            band: "$40–$90",
            orders: 27,
            wines: [
                { label: "NV Veuve Clicquot Yellow Label", qty: 12, revenue: 660 },
                { label: "2021 Rombauer Chardonnay", qty: 9, revenue: 360 },
                { label: "2020 Caymus Cabernet Sauvignon", qty: 7, revenue: 630 },
                { label: "NV Bollinger Special Cuvée", qty: 5, revenue: 400 },
            ],
            missed: ["Harlan Estate"],
        },
        {
            id: "beach",
            name: "Beach",
            hours: "11:00–18:00",
            service: "By the glass and sparkling bottles",
            band: "Under $90",
            orders: 33,
            wines: [
                { label: "2021 Albet i Noya Xarel·lo", qty: 20, revenue: 400 },
                { label: "NV Juvé y Camps Gran Reserva", qty: 15, revenue: 450 },
                { label: "NV Billecart-Salmon Rosé", qty: 8, revenue: 720 },
                { label: "NV Ruinart Blanc de Blancs", qty: 6, revenue: 540 },
            ],
            missed: ["Australian Sangiovese"],
        },
        {
            id: "golf",
            name: "Golf Course",
            hours: "08:00–18:00",
            service: "By the glass on the turn, bottles in the clubhouse",
            band: "$25–$70",
            orders: 29,
            wines: [
                { label: "2021 Trimbach Riesling", qty: 18, revenue: 450 },
                { label: "2022 Henschke Julius Riesling", qty: 11, revenue: 385 },
                { label: "NV Taittinger Brut Réserve", qty: 10, revenue: 600 },
                { label: "NV Moët & Chandon Brut Impérial", qty: 7, revenue: 350 },
            ],
            missed: [],
        },
        {
            id: "steakhouse",
            name: "Steakhouse",
            hours: "17:00–23:00",
            service: "Bottles only",
            band: "$90 and up",
            orders: 24,
            wines: [
                { label: "2019 Shafer Hillside Select Cabernet Sauvignon", qty: 6, revenue: 2100 },
                { label: "2018 Dominus", qty: 5, revenue: 1500 },
                { label: "2019 Opus One", qty: 4, revenue: 1600 },
                { label: "2012 Vega Sicilia Único", qty: 2, revenue: 1000 },
                { label: "2018 Corison Cabernet Sauvignon", qty: 7, revenue: 840 },
                { label: "2019 Silver Oak Alexander Valley Cabernet Sauvignon", qty: 8, revenue: 800 },
            ],
            missed: ["Screaming Eagle"],
        },
    ];

    function money(amount) {
        return "$" + Number(amount).toLocaleString("en-US");
    }

    function outletRevenue(outlet) {
        return outlet.wines.reduce((sum, wine) => sum + wine.revenue, 0);
    }

    function showSalesOverview() {
        const detail = document.getElementById("salesDetail");
        const overview = document.getElementById("salesOverview");
        if (detail) detail.hidden = true;
        if (overview) overview.hidden = false;
    }

    function showOutletSales(id) {
        const outlet = OUTLET_SALES.find((item) => item.id === id);
        if (!outlet) return;
        document.getElementById("salesOverview").hidden = true;
        document.getElementById("salesDetail").hidden = false;
        document.getElementById("salesOutletName").textContent = outlet.name;
        document.getElementById("salesConfig").textContent = outlet.hours + " · " + outlet.service + " · " + outlet.band;
        document.getElementById("salesRevenue").textContent = money(outletRevenue(outlet));
        document.getElementById("salesOrders").textContent = String(outlet.orders);
        const qr = document.getElementById("salesQr");
        qr.src = "/api/outlets/" + outlet.id + "/qr.png";
        qr.alt = "QR code for " + outlet.name;
        document.getElementById("salesQrNote").textContent = "Sample QR for " + outlet.name + ". Guests who scan it open this outlet: " + location.host + "/?outlet=" + outlet.id;
        const wines = outlet.wines.map((wine) => `
            <li>
                <span class="report-label">${escapeHtml(wine.label)}</span>
                <span class="report-count">${escapeHtml(wine.qty)} · ${escapeHtml(money(wine.revenue))}</span>
            </li>
        `).join("");
        const missed = (outlet.missed || []).map((term) => ({ value: term, count: 1 }));
        document.getElementById("salesReport").innerHTML = `
            <article class="info-box">
                <h3>Wines</h3>
                <ol>${wines}</ol>
            </article>
            ${rankBox("Searched, not found", missed, "No searches missed")}
        `;
        document.getElementById("salesPanel").scrollTop = 0;
    }

    function renderOutletCards() {
        const grid = document.getElementById("outletGrid");
        if (!grid || grid.childElementCount) return;
        grid.innerHTML = OUTLET_SALES.map((outlet) => `
            <button type="button" class="outlet-card" data-outlet="${escapeHtml(outlet.id)}">
                <span>
                    <strong>${escapeHtml(outlet.name)}</strong>
                    <span class="outlet-meta">${escapeHtml(money(outletRevenue(outlet)))} · ${escapeHtml(outlet.orders)} orders</span>
                </span>
                <em>View</em>
            </button>
        `).join("");
        grid.querySelectorAll(".outlet-card").forEach((card) => {
            card.addEventListener("click", () => showOutletSales(card.dataset.outlet));
        });
    }

    function showTab(name) {
        document.getElementById("winesPanel").hidden = name !== "wines";
        document.getElementById("infoPanel").hidden = name !== "info";
        document.getElementById("salesPanel").hidden = name !== "sales";
        document.querySelectorAll(".tab-button").forEach((button) => {
            button.classList.toggle("on", button.dataset.tab === name);
        });
        if (name === "info") {
            loadInsights();
        }
        if (name === "sales") {
            renderOutletCards();
        }
    }

    function stockLabel(on) {
        return on ? "in stock" : "out of stock";
    }

    function rowHtml(wine) {
        const inventory = wine.inventory_count == null ? 1 : wine.inventory_count;
        return `
            <tr data-id="${escapeHtml(wine.id)}">
                <td class="col-producer"><input type="text" data-field="producer" value="${escapeHtml(wine.producer)}" aria-label="wine_producer"></td>
                <td class="col-label"><input type="text" data-field="label" value="${escapeHtml(wine.label)}" aria-label="wine_label"></td>
                <td><input type="text" data-field="vintage" value="${escapeHtml(wine.vintage)}" aria-label="vintage"></td>
                <td><input type="text" data-field="country" value="${escapeHtml(wine.country)}" aria-label="country"></td>
                <td><input type="text" data-field="region" value="${escapeHtml(wine.region)}" aria-label="region"></td>
                <td><input type="text" data-field="sub_region" value="${escapeHtml(wine.sub_region)}" aria-label="sub_region"></td>
                <td><input type="number" min="0" step="1" data-field="price" value="${escapeHtml(wine.price)}" aria-label="price"></td>
                <td class="edit-date">${escapeHtml(wine.last_edit_date || "")}</td>
                <td><input type="number" min="0" step="1" data-field="inventory_count" value="${escapeHtml(inventory)}" placeholder="—" aria-label="inventory_count"></td>
                <td>
                    <div class="stock-cell">
                        <button type="button" class="stock-toggle${wine.in_stock ? " on" : ""}" data-field="in_stock" aria-pressed="${wine.in_stock ? "true" : "false"}" aria-label="in_stock">
                            <i></i>
                        </button>
                        <span class="stock-word">${stockLabel(wine.in_stock)}</span>
                    </div>
                </td>
                <td><button type="button" class="same-btn" data-action="delete">Delete</button></td>
            </tr>
        `;
    }

    function renderRows() {
        const query = wineFilter.value.trim().toLowerCase();
        const visible = wines.filter((wine) => {
            if (!query) return true;
            return [wine.producer, wine.label, wine.region, wine.country, wine.vintage]
                .join(" ")
                .toLowerCase()
                .includes(query);
        });
        wineRows.innerHTML = visible.map(rowHtml).join("");
        wineCount.textContent = wines.length + (wines.length === 1 ? " wine" : " wines");
    }

    function findWine(id) {
        return wines.find((wine) => wine.id === id);
    }

    function markDirty() {
        dirty = true;
        saveStatus.textContent = "";
    }

    async function loadWines() {
        const data = await adminFetch("/api/admin/wines");
        wines = data.wines || [];
        dirty = false;
        renderRows();
    }

    function applyAdminChrome() {
        if (adminTitle) adminTitle.textContent = demoAdmin ? "Admin - Demo" : "Admin";
    }

    function emailBox(rows) {
        const items = rows && rows.length
            ? rows.map((row) => `
                <li>
                    <span>${escapeHtml((row.wines || []).join(" · "))}</span>
                </li>
            `).join("")
            : `<li class="empty">No emails yet</li>`;
        return `
            <article class="info-box">
                <h3>Emailed wines</h3>
                <ol class="stack">${items}</ol>
            </article>
        `;
    }

    function rankBox(title, rows, emptyText) {
        const items = rows && rows.length
            ? rows.map((row) => `
                <li>
                    <span class="report-label">${escapeHtml(row.value)}</span>
                    <span class="report-count">${escapeHtml(row.count)}</span>
                </li>
            `).join("")
            : `<li class="empty">${escapeHtml(emptyText)}</li>`;
        return `
            <article class="info-box">
                <h3>${escapeHtml(title)}</h3>
                <ol>${items}</ol>
            </article>
        `;
    }

    async function loadInsights() {
        infoList.innerHTML = "<p class='admin-note'>Loading…</p>";
        try {
            const data = await adminFetch("/api/admin/insights");
            infoList.innerHTML = [
                rankBox("Regions searched", data.regions, "No regions searched yet"),
                rankBox("Color", data.colors, "No colors searched yet"),
                rankBox("Searched, not on the list", data.descriptions, "No producers, grapes, or descriptions were missed"),
                rankBox("Price", data.prices, "No prices searched yet"),
                rankBox("Keywords", data.keywords, "No buttons selected yet"),
                emailBox(data.sends),
            ].join("");
        } catch (error) {
            infoList.innerHTML = `<p class="pin-error">${escapeHtml(error.message)}</p>`;
        }
    }

    async function openAdmin(newToken) {
        token = newToken;
        closePin();
        applyAdminChrome();
        adminOverlay.hidden = false;
        saveStatus.textContent = "";
        showTab("wines");
        try {
            await loadWines();
        } catch (error) {
            saveStatus.textContent = error.message;
        }
    }

    function closeAdmin(force) {
        if (!force && dirty && !window.confirm("Close without Update List? These edits will be dropped.")) {
            return;
        }
        const wasDemo = demoAdmin;
        const closing = token;
        token = "";
        dirty = false;
        demoAdmin = false;
        applyAdminChrome();
        showSalesOverview();
        adminOverlay.hidden = true;
        const locked = closing
            ? fetch("/api/admin/lock", {
                method: "POST",
                headers: { Authorization: "Bearer " + closing },
            }).catch(() => {})
            : Promise.resolve();
        if (wasDemo) {
            locked.finally(() => location.replace("/index.html"));
        }
    }

    async function enterDemoOffice() {
        const params = new URLSearchParams(location.search);
        if (params.get("office") !== "demo") return;
        try {
            const response = await fetch("/api/admin/demo", { method: "POST" });
            const data = await response.json().catch(() => ({}));
            if (!response.ok || !data.token) {
                document.documentElement.classList.remove("office-demo");
                return;
            }
            demoAdmin = true;
            await openAdmin(data.token);
        } catch (error) {
            document.documentElement.classList.remove("office-demo");
        }
    }

    adminButton.addEventListener("click", () => openPin("admin"));
    pinCancel.addEventListener("click", closePin);
    pinForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        pinError.textContent = "";
        const pin = pinInput.value.trim();
        if (!/^\d{6}$/.test(pin)) {
            pinError.textContent = "Enter 6 digits.";
            return;
        }
        try {
            const response = await fetch("/api/admin/unlock", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ pin: pin }),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                pinError.textContent = data.detail || "That pin is not right.";
                return;
            }
            pinInput.value = "";
            if (pinMode === "reset") {
                const cleared = await adminFetch("/api/admin/insights/reset", {
                    method: "POST",
                    body: JSON.stringify({ pin: pin }),
                });
                closePin();
                if (cleared && cleared.demo) {
                    saveStatus.textContent = "this is a demo";
                    return;
                }
                if (cleared && cleared.ok) {
                    await loadInsights();
                }
                return;
            }
            demoAdmin = Boolean(data.demo);
            await openAdmin(data.token);
        } catch (error) {
            pinError.textContent = error.message || "Could not reach the server.";
        }
    });

    document.querySelectorAll(".tab-button").forEach((button) => {
        button.addEventListener("click", () => showTab(button.dataset.tab));
    });
    adminClose.addEventListener("click", () => closeAdmin(false));
    document.getElementById("salesBack").addEventListener("click", showSalesOverview);

    wineFilter.addEventListener("input", renderRows);

    wineRows.addEventListener("input", (event) => {
        const input = event.target;
        const row = input.closest("tr");
        if (!row || !input.dataset.field) return;
        const wine = findWine(row.dataset.id);
        if (!wine) return;
        const field = input.dataset.field;
        if (field === "inventory_count") {
            wine.inventory_count = input.value === "" ? null : Number(input.value);
            if (wine.inventory_count === 0) {
                wine.in_stock = false;
                const toggle = row.querySelector("[data-field='in_stock']");
                const word = row.querySelector(".stock-word");
                if (toggle) {
                    toggle.classList.remove("on");
                    toggle.setAttribute("aria-pressed", "false");
                }
                if (word) word.textContent = stockLabel(false);
            }
        } else if (field === "price") {
            wine.price = input.value === "" ? "" : Number(input.value);
        } else {
            wine[field] = input.value;
        }
        markDirty();
    });

    wineRows.addEventListener("click", (event) => {
        const row = event.target.closest("tr");
        if (!row) return;
        const wine = findWine(row.dataset.id);
        if (!wine) return;
        if (event.target.closest("[data-action='delete']")) {
            wines = wines.filter((item) => item.id !== wine.id);
            markDirty();
            renderRows();
            return;
        }
        const toggle = event.target.closest("[data-field='in_stock']");
        if (toggle) {
            wine.in_stock = !wine.in_stock;
            toggle.classList.toggle("on", wine.in_stock);
            toggle.setAttribute("aria-pressed", wine.in_stock ? "true" : "false");
            const word = row.querySelector(".stock-word");
            if (word) word.textContent = stockLabel(wine.in_stock);
            markDirty();
        }
    });

    addWine.addEventListener("click", () => {
        wines.unshift({
            id: crypto.randomUUID().replace(/-/g, ""),
            producer: "",
            label: "",
            vintage: "",
            country: "",
            region: "",
            sub_region: "",
            major_region: "",
            price: "",
            grapes: "",
            wine_style: "",
            last_edit_date: "",
            inventory_count: 1,
            in_stock: true,
        });
        wineFilter.value = "";
        markDirty();
        renderRows();
        const first = wineRows.querySelector("input");
        if (first) first.focus();
    });

    saveAll.addEventListener("click", async () => {
        if (demoAdmin) {
            saveStatus.textContent = "this is a demo";
            return;
        }
        saveAll.disabled = true;
        saveStatus.textContent = "Saving…";
        try {
            const data = await adminFetch("/api/admin/wines", {
                method: "POST",
                body: JSON.stringify({ wines: wines }),
            });
            wines = data.wines || wines;
            dirty = false;
            renderRows();
            saveStatus.textContent = data.message || "Saved.";
        } catch (error) {
            saveStatus.textContent = error.message;
        } finally {
            saveAll.disabled = false;
        }
    });

    resetData.addEventListener("click", () => openPin("reset"));
    enterDemoOffice();
})();

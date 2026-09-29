(function () {
    const listButton = document.getElementById("listButton");
    const listPage = document.getElementById("listPage");
    const notePage = document.getElementById("notePage");
    const listBody = document.getElementById("listBody");
    const noteBody = document.getElementById("noteBody");
    const listBack = document.getElementById("listBack");
    const noteBack = document.getElementById("noteBack");
    const noteStartOver = document.getElementById("noteStartOver");

    let wines = null;
    let listScroll = 0;
    let resetOnReturn = false;

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text == null ? "" : String(text);
        return div.innerHTML;
    }

    function money(price) {
        if (price == null || price === "") return "";
        const number = Number(price);
        if (Number.isNaN(number)) return "";
        return "$" + (Number.isInteger(number) ? number : number.toFixed(2));
    }

    function bottleTitle(wine) {
        const parts = [wine.vintage, wine.producer];
        const label = (wine.label || "").trim();
        if (label && label.toLowerCase() !== (wine.producer || "").trim().toLowerCase()) {
            parts.push(label);
        }
        return parts.filter(Boolean).join(" ");
    }

    const STYLE_ORDER = ["red", "white", "rosé", "sparkling"];
    const STYLE_LABEL = {
        red: "Red",
        white: "White",
        "rosé": "Rosé",
        sparkling: "Sparkling",
        other: "Other",
    };

    function styleKey(wine) {
        const raw = (wine.wine_style || "").trim().toLowerCase();
        if (raw === "rose" || raw === "rosé") return "rosé";
        if (STYLE_ORDER.indexOf(raw) !== -1) return raw;
        return "other";
    }

    function placeLine(wine) {
        return [wine.sub_region, money(wine.price)].filter(Boolean).join(" · ");
    }

    function inStock(wine) {
        return wine.in_stock !== false && wine.in_stock !== 0 && wine.in_stock !== "out";
    }

    function orderedWines() {
        return (wines || []).filter(inStock).slice().sort((a, b) => {
            const style = STYLE_ORDER.concat("other").indexOf(styleKey(a))
                - STYLE_ORDER.concat("other").indexOf(styleKey(b));
            if (style) return style;
            const country = (a.country || "Unknown").localeCompare(b.country || "Unknown");
            if (country) return country;
            const region = (a.region || "Unknown").localeCompare(b.region || "Unknown");
            if (region) return region;
            return bottleTitle(a).localeCompare(bottleTitle(b));
        });
    }

    function renderList() {
        const rows = orderedWines();
        if (!rows.length) {
            listBody.innerHTML = "<p class='bottle-meta'>No wines on the list yet.</p>";
            return;
        }
        let html = "";
        let style = "";
        let country = "";
        let region = "";
        rows.forEach((wine) => {
            const nextStyle = styleKey(wine);
            const nextCountry = wine.country || "Unknown";
            const nextRegion = wine.region || "Unknown";
            if (nextStyle !== style) {
                style = nextStyle;
                country = "";
                region = "";
                html += `<h2 class="style-head">${escapeHtml(STYLE_LABEL[style] || "Other")}</h2>`;
            }
            if (nextCountry !== country) {
                country = nextCountry;
                region = "";
                html += `<h3 class="country-head">${escapeHtml(country)}</h3>`;
            }
            if (nextRegion !== region) {
                region = nextRegion;
                html += `<h3 class="region-head">${escapeHtml(region)}</h3>`;
            }
            const meta = placeLine(wine);
            html += `
                <button type="button" class="bottle-button" data-id="${escapeHtml(wine.id)}">
                    <div class="bottle-name">${escapeHtml(bottleTitle(wine))}</div>
                    ${meta ? `<div class="bottle-meta">${escapeHtml(meta)}</div>` : ""}
                </button>
            `;
        });
        listBody.innerHTML = html;
    }

    async function ensureWines(force) {
        if (wines && !force) return wines;
        listBody.innerHTML = "<p class='bottle-meta'>Loading the list…</p>";
        const response = await fetch("/api/wines");
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.detail || "Could not load the wine list.");
        }
        wines = data.wines || [];
        renderList();
        return wines;
    }

    function showListPage() {
        notePage.hidden = true;
        listPage.hidden = false;
        listBody.scrollTop = resetOnReturn ? 0 : listScroll;
        resetOnReturn = false;
    }

    function showHome() {
        listPage.hidden = true;
        notePage.hidden = true;
    }

    async function openList(force) {
        showListPage();
        try {
            await ensureWines(force);
        } catch (error) {
            listBody.innerHTML = `<p class="pin-error">${escapeHtml(error.message)}</p>`;
        }
        if (!history.state || history.state.view !== "list") {
            history.pushState({ view: "list" }, "");
        }
    }

    function paintNote(wine, noteText) {
        const wineId = wine.id || wine.wine_id || "";
        noteBody.innerHTML = `
            <h2 class="note-title">${escapeHtml(bottleTitle(wine))}</h2>
            <p class="note-meta">${escapeHtml(placeLine(wine))}</p>
            <p class="note-kicker">Tasting note</p>
            <p class="note-copy">${escapeHtml(noteText)}</p>
            <section class="email-box">
                <p class="email-title">Email selection</p>
                <button type="button" class="wine-pick" data-id="${escapeHtml(wineId)}" aria-pressed="false">${escapeHtml(bottleTitle(wine))}</button>
                <div class="email-row">
                    <input class="email-input" type="email" inputmode="email" placeholder="you@email.com" autocomplete="email" aria-label="Email address">
                    <button type="button" class="email-send">Send</button>
                </div>
                <div class="email-status"></div>
            </section>
        `;
        const pick = noteBody.querySelector(".wine-pick");
        pick.addEventListener("click", () => {
            pick.classList.toggle("selected");
            pick.setAttribute("aria-pressed", pick.classList.contains("selected") ? "true" : "false");
        });
        noteBody.querySelector(".email-send").addEventListener("click", () => sendNoteEmail());
    }

    async function sendNoteEmail() {
        const pick = noteBody.querySelector(".wine-pick");
        const input = noteBody.querySelector(".email-input");
        const status = noteBody.querySelector(".email-status");
        const email = (input.value || "").trim();
        if (!pick.classList.contains("selected") || !pick.dataset.id) {
            status.textContent = "Select the bottle first.";
            return;
        }
        if (!email) {
            status.textContent = "Enter an email.";
            return;
        }
        status.textContent = "Sending…";
        const restaurantId = new URLSearchParams(window.location.search).get("r")
            || new URLSearchParams(window.location.search).get("restaurant")
            || "demo";
        try {
            const response = await fetch("/api/email-wine", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    email,
                    restaurant_id: restaurantId,
                    wine_ids: [pick.dataset.id],
                    notes: [{
                        wine_id: pick.dataset.id,
                        tasting_note: (noteBody.querySelector(".note-copy") || {}).textContent || ""
                    }]
                })
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(data.detail || "Could not send.");
            status.textContent = data.message || "Sent.";
        } catch (error) {
            status.textContent = error.message || "Could not send just now.";
        }
    }

    async function openNote(id, push) {
        const wine = (wines || []).find((item) => item.id === id);
        if (!wine) return;
        if (push) listScroll = listBody.scrollTop;
        listPage.hidden = true;
        notePage.hidden = false;
        noteBody.scrollTop = 0;
        const savedNote = (wine.tasting_note || "").trim();
        if (savedNote.length > 40) {
            paintNote(wine, savedNote);
            if (push) history.pushState({ view: "note", id: id }, "");
            return;
        }
        paintNote(wine, "Writing the tasting note…");
        if (push) history.pushState({ view: "note", id: id }, "");
        try {
            const response = await fetch("/api/wines/" + encodeURIComponent(id) + "/note");
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(data.detail || "Could not write the tasting note.");
            }
            wine.tasting_note = data.tasting_note || "";
            if (history.state && history.state.view === "note" && history.state.id === id) {
                paintNote(data, data.tasting_note || "A note for this bottle is not available yet.");
            }
        } catch (error) {
            if (history.state && history.state.view === "note" && history.state.id === id) {
                paintNote(wine, error.message);
            }
        }
    }

    function returnToList(fromTop) {
        resetOnReturn = fromTop;
        if (fromTop) listScroll = 0;
        if (history.state && history.state.view === "note") {
            history.back();
            return;
        }
        showListPage();
    }

    listButton.addEventListener("click", () => {
        listScroll = 0;
        resetOnReturn = true;
        openList(true);
    });

    listBody.addEventListener("click", (event) => {
        const button = event.target.closest(".bottle-button");
        if (!button) return;
        openNote(button.dataset.id, true);
    });

    listBack.addEventListener("click", () => {
        if (history.state && history.state.view === "list") {
            history.back();
            return;
        }
        showHome();
    });

    noteBack.addEventListener("click", () => returnToList(false));
    noteStartOver.addEventListener("click", () => returnToList(true));

    window.addEventListener("popstate", (event) => {
        const view = event.state && event.state.view;
        if (view === "note" && event.state.id) {
            ensureWines().then(() => openNote(event.state.id, false)).catch(() => showHome());
            return;
        }
        if (view === "list") {
            showListPage();
            ensureWines().catch((error) => {
                listBody.innerHTML = `<p class="pin-error">${escapeHtml(error.message)}</p>`;
            });
            return;
        }
        showHome();
    });

    history.replaceState({ view: "home" }, "");
})();

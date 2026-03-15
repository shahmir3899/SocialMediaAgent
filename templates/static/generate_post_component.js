const DEFAULT_TOPIC_PRESETS = {
    educational: [
        "Productivity habits that actually work",
        "Simple AI workflow tips for busy teams",
        "Data privacy basics everyone should know",
        "How to improve decision quality at work"
    ],
    engagement: [
        "What skill helped your career most this year?",
        "Morning routine or night routine: which one wins?",
        "What is one mistake that taught you a lot?",
        "What tool do you wish you discovered earlier?"
    ],
    promotional: [
        "How our service saves teams weekly hours",
        "Top feature customers keep recommending",
        "Real client outcomes from using our workflow",
        "Limited offer for new customers this month"
    ],
    quote: [
        "A quote about consistency and growth",
        "A quote about creativity under constraints",
        "A quote about leadership and clarity",
        "A quote about long-term thinking"
    ],
    announcement: [
        "New feature launch that solves a major pain point",
        "Upcoming event with practical takeaways",
        "Community milestone announcement",
        "Partnership announcement for customer value"
    ]
};

function buildPresetChips(container, presets, onClick) {
    container.innerHTML = "";
    presets.forEach((text) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "topic-chip";
        chip.textContent = text;
        chip.addEventListener("click", () => onClick(text, chip));
        container.appendChild(chip);
    });
}

function renderGeneratedPost(resultContainer, data) {
    const content = data.content || "";
    const imageUrl = data.image_url || "";
    const proxiedImageUrl = data.id ? `/api/images/${data.id}` : imageUrl;
    const placeholderImageUrl = "https://picsum.photos/seed/socialmediaagent-preview/1080/1080";

    const safeContent = content
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");

    const imageHtml = imageUrl
        ? `<div class="generated-image-wrap"><img src="${proxiedImageUrl}" alt="Generated post image" class="generated-image" loading="lazy"><a href="${proxiedImageUrl}" target="_blank" rel="noopener noreferrer" class="text-sm">Open full image</a></div>`
        : '<p class="text-sm text-muted">No image URL returned for this post.</p>';

    resultContainer.innerHTML = `
        <div class="generated-preview">
            <h4>Generated Post</h4>
            <p class="text-sm text-muted">Post ID: ${data.id || "-"}</p>
            <div class="generated-caption">${safeContent.replaceAll("\n", "<br>")}</div>
            ${imageHtml}
        </div>
    `;

    if (imageUrl) {
        const imgEl = resultContainer.querySelector(".generated-image");
        const linkEl = resultContainer.querySelector(".generated-image-wrap a");
        if (imgEl) {
            let stage = 0;
            imgEl.addEventListener("error", () => {
                if (stage === 0 && imageUrl && imgEl.src !== imageUrl) {
                    stage = 1;
                    imgEl.src = imageUrl;
                    if (linkEl) linkEl.href = imageUrl;
                    return;
                }
                if (stage <= 1 && imgEl.src !== placeholderImageUrl) {
                    stage = 2;
                    imgEl.src = placeholderImageUrl;
                    if (linkEl) linkEl.href = placeholderImageUrl;
                }
            });
        }
    }

    resultContainer.style.display = "block";
}

function markSelectedChip(chipListContainer, activeChip) {
    chipListContainer.querySelectorAll(".topic-chip").forEach((chip) => {
        chip.classList.toggle("active", chip === activeChip);
    });
}

function getErrorMessage(result) {
    if (!result) return "Unknown error";
    if (typeof result.detail === "string") return result.detail;
    return "Unknown error";
}

function initGeneratePostComposer(rootId, options = {}) {
    const root = document.getElementById(rootId);
    if (!root) return;

    const postTypeEl = root.querySelector('[data-role="post-type"]');
    const platformEl = root.querySelector('[data-role="platform"]');
    const topicEl = root.querySelector('[data-role="topic"]');
    const keywordsEl = root.querySelector('[data-role="keywords"]');
    const presetListEl = root.querySelector('[data-role="preset-list"]');
    const generateBtn = root.querySelector('[data-role="generate-btn"]');
    const resultEl = root.querySelector('[data-role="result"]');

    const presets = options.topicPresets || DEFAULT_TOPIC_PRESETS;

    function renderPresets() {
        const selectedType = postTypeEl.value;
        const list = presets[selectedType] || [];
        buildPresetChips(presetListEl, list, (text, chip) => {
            topicEl.value = text;
            markSelectedChip(presetListEl, chip);
        });
    }

    postTypeEl.addEventListener("change", () => {
        renderPresets();
    });

    generateBtn.addEventListener("click", async () => {
        const payload = {
            post_type: postTypeEl.value,
            platform: platformEl.value,
            topic: topicEl.value.trim() || null,
            additional_keywords: keywordsEl.value.trim() || null
        };

        const label = generateBtn.querySelector(".btn-label");
        const spinner = generateBtn.querySelector(".btn-spinner");
        generateBtn.disabled = true;
        if (label) label.textContent = "Generating";
        if (spinner) spinner.style.display = "inline-block";
        showToast("Generating post...");

        try {
            const result = await apiCall("/api/posts/generate-and-save", "POST", payload);
            if (result && result.id) {
                showToast("Post generated successfully!");
                renderGeneratedPost(resultEl, result);
                if (typeof options.onGenerated === "function") {
                    options.onGenerated(result);
                }
            } else {
                showToast(`Generation failed: ${getErrorMessage(result)}`, "error");
            }
        } catch (err) {
            showToast(`Generation failed: ${err.message || "Network error"}`, "error");
        } finally {
            generateBtn.disabled = false;
            if (label) label.textContent = "Generate Post";
            if (spinner) spinner.style.display = "none";
        }
    });

    renderPresets();
}

window.initGeneratePostComposer = initGeneratePostComposer;

let currentMealId = null;
let currentItems = [];
let selectedFile = null;

function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    selectedFile = file;

    // Show preview immediately
    const reader = new FileReader();
    reader.onload = function (e) {
        document.getElementById('pre-upload-preview').src = e.target.result;
        document.getElementById('pre-upload-preview').style.display = 'block';
        document.getElementById('upload-placeholder').style.display = 'none';
    }
    reader.readAsDataURL(file);
}

async function calculateMeal() {
    const description = document.getElementById('image-description').value.trim();

    if (!selectedFile && !description) {
        alert("Please upload an image or enter a description.");
        return;
    }

    // Show loading state
    document.getElementById('loading-state').style.display = 'block';

    const formData = new FormData();
    if (selectedFile) formData.append('image', selectedFile);
    formData.append('description', description);

    try {
        const response = await fetch('/analyze_meal', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (data.error) {
            if (data.error.includes("429") || data.error.toLowerCase().includes("quota")) {
                showNotification(
                    "Quota Limit Reached",
                    "I've updated the models to a higher-capacity version. Please:\n1. Stop your python server (Ctrl+C)\n2. Restart it: python app.py\n3. Refresh this page",
                    "warning"
                );
            } else if (data.error.toLowerCase().includes("no food") || data.error.toLowerCase().includes("not detected")) {
                showNotification(
                    "No Food Detected",
                    "Please upload a clear food image or provide a detailed meal description.\n\nTips:\n• Ensure good lighting\n• Focus on the food items\n• Avoid blurry or blank images",
                    "error"
                );
            } else {
                showNotification("Error", data.error, "error");
            }
            document.getElementById('loading-state').style.display = 'none';
            return;
        }

        displayResults(data);
        fetchDailySummary();

        if (data.items.length === 0) {
            showNotification(
                "No Items Detected",
                "Gemini couldn't identify specific food items. You can add them manually!",
                "warning"
            );
        }
    } catch (error) {
        console.error("Error analyzing meal:", error);
        showNotification("Connection Error", "Failed to analyze meal. Please try again.", "error");
        document.getElementById('loading-state').style.display = 'none';
    }
}

// Custom Notification Functions
function showNotification(title, message, type = "error") {
    const overlay = document.getElementById('custom-notification-overlay');
    const titleEl = document.getElementById('notification-title');
    const messageEl = document.getElementById('notification-message');
    const iconEl = document.getElementById('notification-icon');

    titleEl.textContent = title;
    messageEl.textContent = message;

    // Update icon and color based on type
    const icon = iconEl.querySelector('i');
    if (type === "error") {
        icon.className = "fas fa-exclamation-circle";
        iconEl.style.background = "linear-gradient(135deg, #ef4444, #dc2626)";
    } else if (type === "warning") {
        icon.className = "fas fa-exclamation-triangle";
        iconEl.style.background = "linear-gradient(135deg, #f59e0b, #d97706)";
    } else if (type === "success") {
        icon.className = "fas fa-check-circle";
        iconEl.style.background = "linear-gradient(135deg, #10b981, #059669)";
    }

    overlay.style.display = 'flex';
}

function closeNotification() {
    document.getElementById('custom-notification-overlay').style.display = 'none';
}

function displayResults(data) {
    currentMealId = data.meal_id;
    currentItems = data.items;

    document.getElementById('loading-state').style.display = 'none';
    document.getElementById('result-stage').style.display = 'block';

    const previewImg = document.getElementById('image-preview');
    if (data.image_url) {
        previewImg.src = data.image_url;
        previewImg.style.display = 'block';
    } else {
        previewImg.style.display = 'none';
        previewImg.src = '';
    }

    updateNutritionDisplay(data.totals);
    renderItemsList(data.items);
    renderSuggestions(data.suggestions);
}

function renderSuggestions(suggestions) {
    const grid = document.getElementById('suggestion-grid');
    const container = document.getElementById('suggestions-section'); // Usually contains the sub-header
    grid.innerHTML = '';

    if (!suggestions || suggestions.length === 0) {
        grid.innerHTML = `<p id="suggestion-text">No suggestions available at this time.</p>`;
        return;
    }

    if (typeof suggestions === 'string') {
        grid.innerHTML = `<p id="suggestion-text">${suggestions}</p>`;
        return;
    }

    suggestions.forEach((s, index) => {
        const card = document.createElement('div');
        card.className = 'suggestion-card';
        card.style.animationDelay = `${index * 0.1}s`; // Staggered entry

        // Show image and "Top Choice" badge only for the first suggestion
        let headerHtml = '';
        if (index === 0) {
            headerHtml = `
                <div class="top-choice-badge">
                    <i class="fas fa-crown"></i> Top Choice
                </div>
                <img src="${s.image_url}" alt="${s.title}" onerror="this.onerror=null;this.src='https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=320&h=240&fit=crop';">
            `;
        } else {
            // Add a small icon for text-only suggestions to fill the space
            headerHtml = `
                <div class="suggestion-icon-header">
                    <i class="fas ${index === 1 ? 'fa-leaf' : 'fa-mortar-pestle'}"></i>
                </div>
            `;
        }

        card.innerHTML = `
            ${headerHtml}
            <div class="suggestion-card-content">
                <h4>${s.title}</h4>
                <p>${s.description}</p>
            </div>
        `;
        grid.appendChild(card);
    });
}

function renderItemsList(items) {
    const list = document.getElementById('items-list');
    list.innerHTML = '';

    items.forEach((item, index) => {
        const row = document.createElement('div');
        row.className = 'food-item-row';
        row.innerHTML = `
            <input type="text" value="${item.food_name}" onchange="updateItem(${index}, 'food_name', this.value)" style="flex: 2;">
            <select onchange="updateItem(${index}, 'portion', this.value)" style="flex: 1;">
                <option value="small" ${item.portion === 'small' ? 'selected' : ''}>Small</option>
                <option value="medium" ${item.portion === 'medium' ? 'selected' : ''}>Medium</option>
                <option value="large" ${item.portion === 'large' ? 'selected' : ''}>Large</option>
            </select>
            <div style="color: var(--text-muted); font-size: 0.8rem; flex: 1; text-align: right;">
                ${Math.round(item.confidence * 100)}% Match
            </div>
        `;
        list.appendChild(row);
    });
}

function updateItem(index, field, value) {
    currentItems[index][field] = value;
}

async function recalculate() {
    const btn = event.target;
    const originalText = btn.innerText;
    btn.innerText = 'Updating...';
    btn.disabled = true;

    try {
        const response = await fetch('/recalculate_nutrition', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                meal_id: currentMealId,
                items: currentItems
            })
        });

        const data = await response.json();
        updateNutritionDisplay(data.totals);
        currentItems = data.items;
        renderItemsList(data.items);
        fetchDailySummary();
    } catch (error) {
        console.error("Error recalculating:", error);
        alert("Recalculation failed.");
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
}

function updateNutritionDisplay(totals) {
    document.getElementById('total-calories-range').innerText = `${totals.calorie_range} kcal`;
    document.getElementById('total-calories-exact').innerText = `Approx: ${totals.calories} kcal`;
    document.getElementById('total-carbs').innerText = `${totals.carbs}g`;
    document.getElementById('total-protein').innerText = `${totals.protein}g`;
    document.getElementById('total-fat').innerText = `${totals.fat}g`;
}

async function fetchDailySummary() {
    try {
        const response = await fetch('/daily_summary');
        const data = await response.json();
        console.log("Fetched Daily Summary:", data);

        document.getElementById('daily-calories').innerText = data.daily_totals.calories;
        document.getElementById('daily-protein').innerText = `${data.daily_totals.protein}g`;
        document.getElementById('daily-carbs').innerText = `${data.daily_totals.carbs}g`;
        document.getElementById('daily-fats').innerText = `${data.daily_totals.fat}g`;

        const historyBody = document.getElementById('meal-history-body');
        historyBody.innerHTML = '';
        data.meals.forEach(meal => {
            try {
                const row = document.createElement('tr');
                const calories = (meal.totals && meal.totals.calories) ? meal.totals.calories : 0;
                row.innerHTML = `
                    <td>${meal.meal_name || 'Unknown Meal'}</td>
                    <td>${new Date(meal.date_time).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}</td>
                    <td><strong>${calories} kcal</strong></td>
                `;
                historyBody.appendChild(row);
            } catch (e) {
                console.error("Error rendering meal row:", e, meal);
            }
        });
    } catch (error) {
        console.log("Error fetching summary:", error);
    }
}

function resetUI() {
    selectedFile = null;
    document.getElementById('upload-stage').style.display = 'flex';
    document.getElementById('upload-placeholder').style.display = 'block';
    document.getElementById('pre-upload-preview').style.display = 'none';
    document.getElementById('pre-upload-preview').src = '';

    document.getElementById('loading-state').style.display = 'none';
    document.getElementById('result-stage').style.display = 'none';
    document.getElementById('file-input').value = '';
    document.getElementById('image-description').value = '';
    currentMealId = null;
}

// Audio and Download Utilities
function speakResults() {
    const calories = document.getElementById('total-calories-exact').innerText;
    const itemsCount = currentItems.length;

    // Get text from the first suggestion if available
    const firstSuggestionBox = document.querySelector('.suggestion-card h4');
    const suggestionNote = document.querySelector('.suggestion-card p');
    const suggestionText = firstSuggestionBox ? `Suggested: ${firstSuggestionBox.innerText}. ${suggestionNote ? suggestionNote.innerText : ''}` : '';

    const textToSpeak = `Analysis complete. Detected ${itemsCount} items. ${calories}. ${suggestionText}`;

    const utterance = new SpeechSynthesisUtterance(textToSpeak);
    const currentLang = document.documentElement.lang || 'en';
    utterance.lang = currentLang;
    window.speechSynthesis.speak(utterance);
}

function speakSuggestion() {
    const cards = document.querySelectorAll('.suggestion-card');
    if (cards.length === 0) return;

    let fullText = "Here are some smart suggestions: ";
    cards.forEach((card, index) => {
        const title = card.querySelector('h4').innerText;
        const description = card.querySelector('p').innerText;
        fullText += `${index + 1}. ${title}, ${description}. `;
    });

    const utterance = new SpeechSynthesisUtterance(fullText);
    const currentLang = document.documentElement.lang || 'en';
    utterance.lang = currentLang;
    window.speechSynthesis.speak(utterance);
}

function downloadReport() {
    if (!currentMealId) {
        alert("Please analyze a meal first.");
        return;
    }
    // Direct location change is often more robust for simple downloads
    window.location.href = `/download_report/${currentMealId}`;
}

// Init
document.getElementById('today-date').innerText = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
fetchDailySummary();

// --- Voice Recognition Feature ---
let recognition = null;
let initialText = '';
let audioContext = null;
let analyser = null;
let dataArray = null;
let animationId = null;

if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = true; // Stay on until manual Stop
    recognition.interimResults = true; // Show results live
    recognition.lang = 'en-US';

    recognition.onstart = () => {
        const textarea = document.getElementById('image-description');
        initialText = textarea.value.trim();

        const status = document.getElementById('recording-status');
        status.innerText = "Listening... Speak now";
        status.classList.add('listening-active');

        document.getElementById('start-recording').style.display = 'none';
        document.getElementById('stop-recording').style.display = 'inline-block';
        document.getElementById('mic-visualizer-container').style.display = 'flex';
        document.getElementById('mic-tip').style.display = 'block';

        startMicVisualizer();
    };

    recognition.onresult = (event) => {
        let final_transcript = '';
        let interim_transcript = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                final_transcript += event.results[i][0].transcript;
            } else {
                interim_transcript += event.results[i][0].transcript;
            }
        }

        const textarea = document.getElementById('image-description');
        const combinedFinal = (initialText ? initialText + ' ' : '') + final_transcript;
        textarea.value = combinedFinal + interim_transcript;

        if (final_transcript) {
            initialText = combinedFinal.trim();
        }
    };

    recognition.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
        const status = document.getElementById('recording-status');
        let msg = "Error: " + event.error;
        if (event.error === 'not-allowed') msg = "Mic permission denied (Check browser settings)";
        if (event.error === 'no-speech') msg = "No speech detected. Try again.";
        status.innerText = msg;
        status.classList.remove('listening-active');

        stopVoiceRecognition(); // Clean up everything
    };

    recognition.onend = () => {
        const status = document.getElementById('recording-status');
        status.classList.remove('listening-active');
        if (!status.innerText.includes("Error") && !status.innerText.includes("denied")) {
            status.innerText = "Recording stopped.";
        }
        document.getElementById('start-recording').style.display = 'inline-block';
        document.getElementById('stop-recording').style.display = 'none';
        // Keep visualizer visible briefly then hide or just hide
        setTimeout(() => {
            if (document.getElementById('start-recording').style.display !== 'none') {
                document.getElementById('mic-visualizer-container').style.display = 'none';
                document.getElementById('mic-tip').style.display = 'none';
            }
        }, 1500);

        stopMicVisualizer();
    };
}

async function startMicVisualizer() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioContext.createAnalyser();
        const source = audioContext.createMediaStreamSource(stream);
        source.connect(analyser);
        analyser.fftSize = 32;
        dataArray = new Uint8Array(analyser.frequencyBinCount);

        const bars = document.querySelectorAll('.mic-visualizer .bar');

        function update() {
            if (!analyser) return; // safety check
            analyser.getByteFrequencyData(dataArray);
            bars.forEach((bar, i) => {
                const val = dataArray[i] / 1.5; // Sensitivity scaling
                bar.style.height = `${Math.max(4, Math.min(18, val))}px`;
            });
            animationId = requestAnimationFrame(update);
        }
        update();
    } catch (err) {
        console.error("Mic access denied for visualizer:", err);
    }
}

function stopMicVisualizer() {
    if (animationId) cancelAnimationFrame(animationId);
    if (audioContext) audioContext.close();
    audioContext = null;
    analyser = null;
}

function startVoiceRecognition() {
    if (!recognition) {
        alert("Speech recognition is not supported in this browser. Please use Chrome or Edge.");
        return;
    }
    recognition.start();
}

function stopVoiceRecognition() {
    if (recognition) {
        recognition.stop();
        stopMicVisualizer();
    }
}

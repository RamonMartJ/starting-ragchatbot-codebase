// API base URL - use relative path to work from any host
const API_URL = '/api';

// Global state
let currentSessionId = null;
let isLoading = false; // Track if a query is currently being processed
let originalButtonHTML = ''; // Store original button HTML with icon

// DOM elements
let chatMessages, chatInput, sendButton, totalArticles, articleTitles, newChatButton;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Get DOM elements after page loads
    chatMessages = document.getElementById('chatMessages');
    chatInput = document.getElementById('chatInput');
    sendButton = document.getElementById('sendButton');
    totalArticles = document.getElementById('totalArticles');
    articleTitles = document.getElementById('articleTitles');
    newChatButton = document.getElementById('newChatButton');

    // Capture original button HTML once (with SVG icon)
    originalButtonHTML = sendButton.innerHTML;

    setupEventListeners();
    createNewSession();
    loadArticleStats();
});

// Event Listeners
function setupEventListeners() {
    // Chat functionality
    sendButton.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !isLoading) {
            sendMessage();
        }
    });

    // New Chat button - clears conversation and starts fresh session
    newChatButton.addEventListener('click', () => {
        createNewSession();
    });

    // Suggested questions
    document.querySelectorAll('.suggested-item').forEach(button => {
        button.addEventListener('click', (e) => {
            const question = e.target.getAttribute('data-question');
            chatInput.value = question;
            sendMessage();
        });
    });
}


// Chat Functions
async function sendMessage() {
    const query = chatInput.value.trim();
    if (!query) return;

    // Prevent multiple simultaneous queries
    if (isLoading) {
        console.log('Ya hay una consulta en curso, ignorando nueva petición');
        return;
    }

    // Mark as loading and disable all inputs
    isLoading = true;
    chatInput.value = '';
    chatInput.disabled = true;
    sendButton.disabled = true;

    // Update button HTML to show loading state
    sendButton.innerHTML = 'Cargando...';

    // Disable suggested question buttons
    document.querySelectorAll('.suggested-item').forEach(button => {
        button.classList.add('disabled');
        button.style.pointerEvents = 'none';
        button.style.opacity = '0.5';
    });

    // Add user message
    addMessage(query, 'user');

    // Add loading message - create a unique container for it
    const loadingMessage = createLoadingMessage();
    chatMessages.appendChild(loadingMessage);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        const response = await fetch(`${API_URL}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: query,
                session_id: currentSessionId
            })
        });

        if (!response.ok) throw new Error('La consulta falló');

        const data = await response.json();

        // Update session ID if new
        if (!currentSessionId) {
            currentSessionId = data.session_id;
        }

        // Replace loading message with response
        loadingMessage.remove();
        addMessage(data.answer, 'assistant', data.sources);

    } catch (error) {
        // Replace loading message with error
        loadingMessage.remove();
        addMessage(`Error: ${error.message}`, 'assistant');
    } finally {
        // Re-enable all inputs
        isLoading = false;
        chatInput.disabled = false;
        sendButton.disabled = false;
        sendButton.innerHTML = originalButtonHTML;

        // Re-enable suggested question buttons
        document.querySelectorAll('.suggested-item').forEach(button => {
            button.classList.remove('disabled');
            button.style.pointerEvents = 'auto';
            button.style.opacity = '1';
        });

        chatInput.focus();
    }
}

function createLoadingMessage() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="loading">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    return messageDiv;
}

function addMessage(content, type, sources = null, isWelcome = false) {
    const messageId = Date.now();
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}${isWelcome ? ' welcome-message' : ''}`;
    messageDiv.id = `message-${messageId}`;

    // Convert markdown to HTML for assistant messages
    let displayContent = type === 'assistant' ? marked.parse(content) : escapeHtml(content);

    // Add citation links with tooltips for assistant messages
    if (type === 'assistant' && sources) {
        displayContent = addCitationLinks(displayContent, sources);
    }

    let html = `<div class="message-content">${displayContent}</div>`;

    // Render sources with clickable links if URLs are available
    if (sources && sources.length > 0) {
        // Remove duplicate sources by creating a Map with unique text as key
        const uniqueSourcesMap = new Map();
        sources.forEach(source => {
            let key;
            if (typeof source === 'object' && source.text) {
                key = source.text;
            } else {
                key = source;
            }
            // Only add if not already present (keeps first occurrence)
            if (!uniqueSourcesMap.has(key)) {
                uniqueSourcesMap.set(key, source);
            }
        });

        // Convert unique sources to HTML: modern badge-style links or plain text badges
        const sourceLinks = Array.from(uniqueSourcesMap.values()).map(source => {
            // Check if source is an object with text and url (new format)
            if (typeof source === 'object' && source.text) {
                if (source.url) {
                    // Render as clickable badge with icon (opens in new tab)
                    return `<a href="${source.url}" target="_blank" rel="noopener noreferrer" class="source-link">${escapeHtml(source.text)}</a>`;
                } else {
                    // No URL available, render as plain text badge
                    return `<span class="source-text">${escapeHtml(source.text)}</span>`;
                }
            }
            // Fallback for old string format (backward compatibility)
            return `<span class="source-text">${escapeHtml(source)}</span>`;
        }).join(''); // No separator - badges have their own margins

        html += `
            <details class="sources-collapsible">
                <summary class="sources-header">Fuentes</summary>
                <div class="sources-content">${sourceLinks}</div>
            </details>
        `;
    }
    
    messageDiv.innerHTML = html;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return messageId;
}

// Helper function to escape HTML for user messages
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Helper function to add citation links with tooltips
function addCitationLinks(htmlContent, sources) {
    if (!sources || sources.length === 0) {
        return htmlContent;
    }

    // Create a mapping of index to source text for tooltips
    const sourceMap = {};
    sources.forEach(source => {
        if (source.index) {
            sourceMap[source.index] = source.text;
        }
    });

    // Replace [1], [2], etc. with citation links
    // Use regex to find all [number] patterns
    return htmlContent.replace(/\[(\d+)\]/g, (match, number) => {
        const index = parseInt(number);
        const tooltipText = sourceMap[index];

        if (tooltipText) {
            // Create citation link with tooltip
            return `<span class="citation-link" data-tooltip="${escapeHtml(tooltipText)}">[${number}]</span>`;
        }

        // If no matching source, return original text
        return match;
    });
}

// Removed removeMessage function - no longer needed since we handle loading differently

async function createNewSession() {
    currentSessionId = null;
    chatMessages.innerHTML = '';
    addMessage('¡Bienvenido al Asistente de Noticias! Puedo ayudarte con preguntas sobre los artículos disponibles. ¿Qué te gustaría saber?', 'assistant', null, true);
}

// Load article statistics
async function loadArticleStats() {
    try {
        console.log('Cargando estadísticas de artículos...');
        const response = await fetch(`${API_URL}/articles`);
        if (!response.ok) throw new Error('Error al cargar estadísticas de artículos');
        
        const data = await response.json();
        console.log('Article data received:', data);

        // Update stats in UI
        if (totalArticles) {
            totalArticles.textContent = data.total_articles;
        }

        // Update article titles
        if (articleTitles) {
            if (data.article_titles && data.article_titles.length > 0) {
                articleTitles.innerHTML = data.article_titles
                    .map(title => `<div class="article-title-item">${title}</div>`)
                    .join('');
            } else {
                articleTitles.innerHTML = '<span class="no-articles">No hay noticias disponibles</span>';
            }
        }

    } catch (error) {
        console.error('Error al cargar estadísticas de artículos:', error);
        // Set default values on error
        if (totalArticles) {
            totalArticles.textContent = '0';
        }
        if (articleTitles) {
            articleTitles.innerHTML = '<span class="error">Error al cargar noticias</span>';
        }
    }
}
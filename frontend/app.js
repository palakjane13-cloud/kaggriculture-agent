// STATE MANAGEMENT
let todos = [];
let chatHistory = [];
let currentFilter = 'all';
let currentSearch = '';

// DOM ELEMENTS
const chatThread = document.getElementById('chat-thread');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatSubmitBtn = document.getElementById('chat-submit-btn');
const taskList = document.getElementById('task-list');
const boardSearch = document.getElementById('board-search');
const filterPills = document.querySelectorAll('.filter-pills .pill');

// STAT ELEMENTS
const statTotal = document.getElementById('stat-total');
const statPending = document.getElementById('stat-pending');
const statCompleted = document.getElementById('stat-completed');
const statProgressRing = document.getElementById('stat-progress-ring');
const statProgressPercent = document.getElementById('stat-progress-percent');

// MODAL ELEMENTS
const taskModal = document.getElementById('task-modal');
const taskForm = document.getElementById('task-form');
const modalTitle = document.getElementById('modal-title');
const btnOpenAddModal = document.getElementById('btn-open-add-modal');
const btnCloseModal = document.getElementById('btn-close-modal');
const btnCancelModal = document.getElementById('btn-cancel-modal');

// INITIALIZATION
document.addEventListener('DOMContentLoaded', () => {
    // Set up Marked Options
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            breaks: true,
            gfm: true
        });
    }

    // Load initial tasks
    fetchTodos();

    // Event Listeners
    chatForm.addEventListener('submit', handleChatSubmit);
    boardSearch.addEventListener('input', handleSearchInput);
    
    // Filter pills
    filterPills.forEach(pill => {
        pill.addEventListener('click', () => {
            filterPills.forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            currentFilter = pill.getAttribute('data-filter');
            renderTodos();
        });
    });

    // Modal triggers
    btnOpenAddModal.addEventListener('click', () => openModal());
    btnCloseModal.addEventListener('click', closeModal);
    btnCancelModal.addEventListener('click', closeModal);
    taskForm.addEventListener('submit', handleManualTaskSubmit);

    // Close modal on click outside
    window.addEventListener('click', (e) => {
        if (e.target === taskModal) {
            closeModal();
        }
    });
});

// API REQUESTS

// Fetch all todos from the backend
async function fetchTodos() {
    try {
        const response = await fetch('/api/todos');
        if (!response.ok) throw new Error('Failed to fetch tasks');
        todos = await response.json();
        renderTodos();
        renderStats();
    } catch (error) {
        console.error('Error fetching tasks:', error);
        taskList.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-triangle-exclamation" style="color: var(--priority-high);"></i>
                <p>Failed to load tasks from backend server.</p>
            </div>
        `;
    }
}

// Toggle status of a todo between pending and completed
async function toggleTodoStatus(id, currentStatus) {
    const newStatus = currentStatus === 'completed' ? 'pending' : 'completed';
    try {
        const response = await fetch(`/api/todos/${id}/status`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        if (!response.ok) throw new Error('Failed to update task status');
        
        // Update local state and re-render
        const updatedTodo = await response.json();
        todos = todos.map(t => t.id === id ? updatedTodo : t);
        renderTodos();
        renderStats();
    } catch (error) {
        console.error('Error updating task status:', error);
        alert('Could not update task status.');
    }
}

// Delete a todo from the list
async function deleteTodo(id) {
    if (!confirm('Are you sure you want to delete this task?')) return;
    try {
        const response = await fetch(`/api/todos/${id}`, {
            method: 'DELETE'
        });
        if (!response.ok) throw new Error('Failed to delete task');
        
        // Update local state
        todos = todos.filter(t => t.id !== id);
        renderTodos();
        renderStats();
    } catch (error) {
        console.error('Error deleting task:', error);
        alert('Could not delete task.');
    }
}

// CHAT FUNCTIONS

// Send user chat message to the agent
async function sendChatMessage(messageText) {
    if (!messageText.trim()) return;

    // 1. Render User Message
    addMessageToChat('user', messageText);
    
    // 2. Add typing indicator
    const typingIndicator = showTypingIndicator();
    chatSubmitBtn.disabled = true;

    try {
        // Prepare request payload
        const payload = {
            message: messageText,
            history: chatHistory
        };

        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error('Agent failed to respond');
        const data = await response.json();

        // 3. Remove typing indicator
        typingIndicator.remove();

        // 4. Render Agent Message
        addMessageToChat('model', data.response);

        // 5. Update local todos list and board if the backend returned updated tasks
        if (data.todos) {
            todos = data.todos;
            renderTodos();
            renderStats();
        }

        // Keep chat history clean (limit to last 20 messages to prevent heavy context)
        chatHistory.push({ role: 'user', content: messageText });
        chatHistory.push({ role: 'model', content: data.response });
        if (chatHistory.length > 20) {
            chatHistory = chatHistory.slice(-20);
        }
    } catch (error) {
        console.error('Chat error:', error);
        typingIndicator.remove();
        addMessageToChat('model', '⚠️ **Apologies, I encountered a communication problem with my engine.** Please verify that the server is running and your API key is correctly configured.');
    } finally {
        chatSubmitBtn.disabled = false;
    }
}

function handleChatSubmit(e) {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;
    
    chatInput.value = '';
    sendChatMessage(message);
}

// Allows suggestion buttons to trigger chat
function sendSuggestion(text) {
    sendChatMessage(text);
}

// Render message bubbles in chat thread
function addMessageToChat(role, content) {
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('message');
    msgDiv.classList.add(role === 'user' ? 'user-msg' : 'system-msg');

    const avatar = role === 'user' ? '<i class="fa-solid fa-user"></i>' : '<i class="fa-solid fa-robot"></i>';
    
    // Parse Markdown safely if Marked is loaded
    let htmlContent = content;
    if (typeof marked !== 'undefined') {
        htmlContent = marked.parse(content);
    } else {
        htmlContent = `<p>${content.replace(/\n/g, '<br>')}</p>`;
    }

    msgDiv.innerHTML = `
        <div class="msg-avatar">
            ${avatar}
        </div>
        <div class="msg-bubble">
            ${htmlContent}
        </div>
    `;

    chatThread.appendChild(msgDiv);
    chatThread.scrollTop = chatThread.scrollHeight;
}

function showTypingIndicator() {
    const indicatorDiv = document.createElement('div');
    indicatorDiv.classList.add('message', 'system-msg');
    indicatorDiv.innerHTML = `
        <div class="msg-avatar">
            <i class="fa-solid fa-robot"></i>
        </div>
        <div class="msg-bubble">
            <div class="typing-indicator">
                <span class="typing-dot-small"></span>
                <span class="typing-dot-small"></span>
                <span class="typing-dot-small"></span>
            </div>
        </div>
    `;
    chatThread.appendChild(indicatorDiv);
    chatThread.scrollTop = chatThread.scrollHeight;
    return indicatorDiv;
}

// BOARD RENDERING

// Render todos dynamically into the board list
function renderTodos() {
    taskList.innerHTML = '';

    // Filter tasks based on Search and Filter Pills
    const filteredTodos = todos.filter(todo => {
        // Status filter
        if (currentFilter === 'pending' && todo.status !== 'pending') return false;
        if (currentFilter === 'completed' && todo.status !== 'completed') return false;

        // Search text filter
        if (currentSearch) {
            const term = currentSearch.toLowerCase();
            return (
                todo.title.toLowerCase().includes(term) ||
                (todo.description && todo.description.toLowerCase().includes(term)) ||
                (todo.category && todo.category.toLowerCase().includes(term))
            );
        }
        return true;
    });

    if (filteredTodos.length === 0) {
        taskList.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-clipboard-list"></i>
                <p>No tasks found. ${currentSearch ? 'Try a different search term.' : 'Use the AI Copilot to add some!'}</p>
            </div>
        `;
        return;
    }

    filteredTodos.forEach(todo => {
        const isCompleted = todo.status === 'completed';
        const card = document.createElement('div');
        card.classList.add('task-card');
        if (isCompleted) card.classList.add('completed');

        // Format priority class name
        const priorityClass = `priority-${todo.priority.toLowerCase()}`;
        
        // Build badges
        const dueBadge = todo.due_date ? `
            <span class="badge badge-due ${isOverdue(todo.due_date) && !isCompleted ? 'overdue' : ''}">
                <i class="fa-regular fa-calendar"></i> ${formatDate(todo.due_date)}
            </span>
        ` : '';

        const categoryBadge = todo.category ? `
            <span class="badge badge-category">
                <i class="fa-solid fa-tag"></i> ${todo.category}
            </span>
        ` : '';

        card.innerHTML = `
            <div class="task-checkbox-container">
                <div class="custom-checkbox" onclick="toggleTodoStatus(${todo.id}, '${todo.status}')">
                    <i class="fa-solid fa-check"></i>
                </div>
            </div>
            <div class="task-details">
                <div class="task-card-header">
                    <div class="task-title">${escapeHTML(todo.title)}</div>
                    <div class="task-actions">
                        <button class="btn-icon edit" onclick="openModal(${todo.id})" title="Edit Task">
                            <i class="fa-solid fa-pen"></i>
                        </button>
                        <button class="btn-icon delete" onclick="deleteTodo(${todo.id})" title="Delete Task">
                            <i class="fa-solid fa-trash-can"></i>
                        </button>
                    </div>
                </div>
                ${todo.description ? `<p class="task-desc">${escapeHTML(todo.description)}</p>` : ''}
                <div class="task-meta">
                    <span class="badge ${priorityClass}">
                        <i class="fa-solid fa-circle-exclamation"></i> ${todo.priority}
                    </span>
                    ${categoryBadge}
                    ${dueBadge}
                </div>
            </div>
        `;
        taskList.appendChild(card);
    });
}

// Render Header Stats Panel
function renderStats() {
    const total = todos.length;
    const completed = todos.filter(t => t.status === 'completed').length;
    const pending = total - completed;
    
    statTotal.textContent = total;
    statPending.textContent = pending;
    statCompleted.textContent = completed;
    
    // Circular progress calculation
    const percent = total > 0 ? Math.round((completed / total) * 100) : 0;
    statProgressPercent.textContent = `${percent}%`;
    
    // SVG dasharray configuration
    // r = 24 -> circumference = 2 * PI * r = ~150.79
    const radius = 24;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (percent / 100) * circumference;
    statProgressRing.style.strokeDashoffset = offset;
}

// SEARCH
function handleSearchInput(e) {
    currentSearch = e.target.value;
    renderTodos();
}

// DIALOG/MODAL MANAGEMENT
function openModal(todoId = null) {
    taskForm.reset();
    document.getElementById('task-id').value = '';
    
    if (todoId) {
        // Editing Mode
        modalTitle.textContent = 'Edit Task';
        const todo = todos.find(t => t.id === todoId);
        if (todo) {
            document.getElementById('task-id').value = todo.id;
            document.getElementById('task-title').value = todo.title;
            document.getElementById('task-desc').value = todo.description || '';
            document.getElementById('task-category').value = todo.category || 'General';
            document.getElementById('task-priority').value = todo.priority;
            document.getElementById('task-due').value = todo.due_date || '';
        }
    } else {
        // Creation Mode
        modalTitle.textContent = 'Create New Task';
        document.getElementById('task-category').value = 'General';
        document.getElementById('task-priority').value = 'Medium';
    }
    taskModal.classList.add('open');
}

function closeModal() {
    taskModal.classList.remove('open');
}

// Manual task creation or editing form submission handler
async function handleManualTaskSubmit(e) {
    e.preventDefault();
    
    const id = document.getElementById('task-id').value;
    const title = document.getElementById('task-title').value.trim();
    const description = document.getElementById('task-desc').value.trim();
    const category = document.getElementById('task-category').value.trim() || 'General';
    const priority = document.getElementById('task-priority').value;
    const due_date = document.getElementById('task-due').value;

    if (!title) {
        alert('Please enter a task title');
        return;
    }

    const payload = { title, description, category, priority, due_date };
    const method = id ? 'PUT' : 'POST';
    const url = id ? `/api/todos/${id}` : '/api/todos';

    try {
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error('Failed to save task');
        
        const savedTodo = await response.json();
        
        if (id) {
            // Update local state (Edit)
            todos = todos.map(t => t.id === parseInt(id) ? savedTodo : t);
        } else {
            // Append local state (Create)
            todos.unshift(savedTodo);
        }
        
        closeModal();
        renderTodos();
        renderStats();
    } catch (error) {
        console.error('Error saving task:', error);
        alert('Could not save task. Please check server connection.');
    }
}

// UTILITY FUNCTIONS

function escapeHTML(str) {
    if (!str) return '';
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    try {
        const options = { month: 'short', day: 'numeric' };
        // Parse date in local timezone to avoid off-by-one errors from UTC
        const parts = dateStr.split('-');
        if (parts.length === 3) {
            const date = new Date(parts[0], parts[1] - 1, parts[2]);
            return date.toLocaleDateString('en-US', options);
        }
        return dateStr;
    } catch (e) {
        return dateStr;
    }
}

function isOverdue(dateStr) {
    if (!dateStr) return false;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    const parts = dateStr.split('-');
    if (parts.length === 3) {
        const dueDate = new Date(parts[0], parts[1] - 1, parts[2]);
        dueDate.setHours(0, 0, 0, 0);
        return dueDate < today;
    }
    return false;
}

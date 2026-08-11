/** @odoo-module **/

import { Component, useState, useRef, onMounted, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

// ─────────────────────────────────────────────────────────────────
//  Unicore AI Chatbot — systray icon + slide-out panel
// ─────────────────────────────────────────────────────────────────
export class UnicoreAIChatbot extends Component {
    static template = "unicore_ai.ChatbotSystray";
    static props = [];

    setup() {
        this.state = useState({
            isOpen: false,
            isLoading: false,
            showHistory: false,
            messages: [],
            sessions: [],
            currentSessionId: null,
        });
        this.messagesRef = useRef("messagesContainer");
        this.inputRef = useRef("inputArea");
    }

    // ── helpers ──────────────────────────────────────────────────
    scrollToBottom() {
        const el = document.querySelector(".o_unicore_ai_messages");
        if (el) {
            requestAnimationFrame(() => {
                el.scrollTop = el.scrollHeight;
            });
        }
    }

    formatMessage(content) {
        if (!content) return "";
        let html = content
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/```([\s\S]*?)```/g, '<pre class="o_unicore_ai_code">$1</pre>')
            .replace(/`([^`]+)`/g, "<code>$1</code>")
            .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
            .replace(/\*(.+?)\*/g, "<em>$1</em>")
            .replace(/\n/g, "<br/>");
        return markup(html);
    }

    // ── panel visibility ────────────────────────────────────────
    togglePanel() {
        this.state.isOpen = !this.state.isOpen;
    }

    // ── session management ──────────────────────────────────────
    async newSession() {
        const res = await rpc("/unicore_ai/chat/new_session", {});
        this.state.currentSessionId = res.id;
        this.state.messages = [];
        this.state.showHistory = false;
    }

    async loadSessions() {
        this.state.sessions = await rpc("/unicore_ai/chat/sessions", {});
    }

    async loadSession(sessionId) {
        const messages = await rpc("/unicore_ai/chat/messages", {
            session_id: sessionId,
        });
        this.state.messages = messages;
        this.state.currentSessionId = sessionId;
        this.state.showHistory = false;
        this.scrollToBottom();
    }

    async deleteSession(sessionId) {
        await rpc("/unicore_ai/chat/delete_session", {
            session_id: sessionId,
        });
        if (this.state.currentSessionId === sessionId) {
            this.state.currentSessionId = null;
            this.state.messages = [];
        }
        await this.loadSessions();
    }

    async toggleHistory() {
        if (!this.state.showHistory) {
            await this.loadSessions();
        }
        this.state.showHistory = !this.state.showHistory;
    }

    // ── messaging ───────────────────────────────────────────────
    async sendSuggestion(text) {
        // Set the text and send
        this.state._pendingSuggestion = text;
        await this._doSend(text);
    }

    async sendMessage() {
        const inputEl = this.inputRef.el;
        const text = inputEl ? inputEl.value.trim() : "";
        if (!text) return;
        inputEl.value = "";
        await this._doSend(text);
    }

    async _doSend(text) {
        // Create session lazily
        if (!this.state.currentSessionId) {
            const res = await rpc("/unicore_ai/chat/new_session", {});
            this.state.currentSessionId = res.id;
        }

        // Optimistic user message
        this.state.messages = [...this.state.messages, { role: "user", content: text }];
        this.state.isLoading = true;
        this.scrollToBottom();

        try {
            const res = await rpc("/unicore_ai/chat/send", {
                session_id: this.state.currentSessionId,
                message: text,
            });
            if (res.error) {
                this.state.messages = [
                    ...this.state.messages,
                    { role: "assistant", content: `⚠️ ${res.error}` },
                ];
            } else {
                this.state.messages = [
                    ...this.state.messages,
                    { role: "assistant", content: res.reply },
                ];
            }
        } catch {
            this.state.messages = [
                ...this.state.messages,
                { role: "assistant", content: "⚠️ An unexpected error occurred. Please try again." },
            ];
        }
        this.state.isLoading = false;
        this.scrollToBottom();
    }

    onKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendMessage();
        }
    }
}

// Register the systray item
registry.category("systray").add(
    "unicore_ai.Chatbot",
    { Component: UnicoreAIChatbot },
    { sequence: 50 }
);

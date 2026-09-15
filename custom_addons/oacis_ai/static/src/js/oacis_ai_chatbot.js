/** @odoo-module **/

import { Component, useState, useRef, onMounted, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

// ─────────────────────────────────────────────────────────────────
//  Oacis AI Chatbot — systray icon + slide-out panel
//  Features: history, prompt templates, record grounding,
//  copy buttons, feedback, per-role suggestions.
// ─────────────────────────────────────────────────────────────────
export class OacisAIChatbot extends Component {
    static template = "oacis_ai.ChatbotSystray";
    static props = [];

    setup() {
        this.state = useState({
            isOpen: false,
            isLoading: false,
            showHistory: false,
            messages: [],
            sessions: [],
            prompts: [],
            currentSessionId: null,
            searchText: "",
        });
        this.messagesRef = useRef("messagesContainer");
        this.inputRef = useRef("inputArea");
        onMounted(() => this.loadPrompts());
    }

    get filteredSessions() {
        const q = (this.state.searchText || "").toLowerCase();
        if (!q) return this.state.sessions;
        return this.state.sessions.filter((s) =>
            (s.title || "").toLowerCase().includes(q)
        );
    }

    // ── helpers ──────────────────────────────────────────────────
    scrollToBottom() {
        const el = document.querySelector(".o_oacis_ai_messages");
        if (el) {
            requestAnimationFrame(() => {
                el.scrollTop = el.scrollHeight;
            });
        }
    }

    escapeHtml(s) {
        return (s || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
    }

    formatMessage(content) {
        if (!content) return "";
        // 1. Extract code blocks first (protect from other transforms)
        const codeBlocks = [];
        let html = this.escapeHtml(content);
        html = html.replace(/```([\s\S]*?)```/g, (m, code) => {
            codeBlocks.push(
                `<pre class="o_oacis_ai_code">${code.replace(/^\n+|\n+$/g, "")}</pre>`
            );
            return `\u0000CODE${codeBlocks.length - 1}\u0000`;
        });
        // 2. Inline code, bold, italic
        html = html
            .replace(/`([^`]+)`/g, "<code>$1</code>")
            .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
            .replace(/(^|\W)\*(.+?)\*/g, "$1<em>$2</em>");
        // 3. Headings (###, ##, #)
        html = html
            .replace(/^### (.+)$/gm, "<h5>$1</h5>")
            .replace(/^## (.+)$/gm, "<h4>$1</h4>")
            .replace(/^# (.+)$/gm, "<h4>$1</h4>");
        // 4. Lists: "- " / "* " / "1. "
        html = html.replace(
            /((?:^(?:- |\* |\d+\. ).+$\n?)+)/gm,
            (block) => {
                const items = block
                    .trim()
                    .split("\n")
                    .map((line) =>
                        `<li>${line.replace(/^(?:- |\* |\d+\. )/, "")}</li>`
                    )
                    .join("");
                return `<ul>${items}</ul>`;
            }
        );
        // 5. Line breaks
        html = html.replace(/\n/g, "<br/>");
        // 6. Restore code blocks
        html = html.replace(/\u0000CODE(\d+)\u0000/g, (m, i) => codeBlocks[+i]);
        return markup(html);
    }

    async copyText(text) {
        try {
            await navigator.clipboard.writeText(text || "");
        } catch {
            const ta = document.createElement("textarea");
            ta.value = text || "";
            document.body.appendChild(ta);
            ta.select();
            document.execCommand("copy");
            ta.remove();
        }
    }

    currentRecordContext() {
        // Best-effort: read current record from URL hash (#id=..&model=..&view_type=form).
        try {
            const hash = window.location.hash || "";
            const idMatch = hash.match(/[?&]id=(\d+)/);
            const modelMatch = hash.match(/[?&]model=([\w.]+)/);
            if (idMatch && modelMatch) {
                return {
                    res_model: decodeURIComponent(modelMatch[1]),
                    res_id: parseInt(idMatch[1], 10),
                };
            }
        } catch {
            // ignore — grounding is optional
        }
        return {};
    }

    // ── panel visibility ────────────────────────────────────────
    togglePanel() {
        this.state.isOpen = !this.state.isOpen;
        if (this.state.isOpen) {
            this.loadPrompts();
        }
    }

    // ── session management ──────────────────────────────────────
    async newSession() {
        const res = await rpc("/oacis_ai/chat/new_session", {});
        this.state.currentSessionId = res.id;
        this.state.messages = [];
        this.state.showHistory = false;
    }

    async loadSessions() {
        this.state.sessions = await rpc("/oacis_ai/chat/sessions", {});
    }

    async loadPrompts() {
        try {
            this.state.prompts = await rpc("/oacis_ai/chat/prompts", {});
        } catch {
            this.state.prompts = [];
        }
    }

    async loadSession(sessionId) {
        const messages = await rpc("/oacis_ai/chat/messages", {
            session_id: sessionId,
        });
        this.state.messages = messages;
        this.state.currentSessionId = sessionId;
        this.state.showHistory = false;
        this.scrollToBottom();
    }

    async deleteSession(sessionId) {
        await rpc("/oacis_ai/chat/delete_session", {
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

    async sendFeedback(msg, rating) {
        if (!msg.id) return;
        try {
            await rpc("/oacis_ai/chat/feedback", {
                message_id: msg.id,
                rating,
            });
            msg.rating = rating;
        } catch {
            // non-blocking
        }
    }

    // ── messaging ───────────────────────────────────────────────
    async sendSuggestion(text) {
        await this._doSend(text);
    }

    async askAboutRecord() {
        const ctx = this.currentRecordContext();
        if (!ctx.res_model) {
            await this._doSend("Summarize what you can help me with.");
            return;
        }
        await this._doSend(
            `Summarize this ${ctx.res_model} record (id ${ctx.res_id}) in 5 bullet points.`,
            ctx
        );
    }

    async sendMessage() {
        const inputEl = this.inputRef.el;
        const text = inputEl ? inputEl.value.trim() : "";
        if (!text) return;
        inputEl.value = "";
        await this._doSend(text);
    }

    async _doSend(text, recordCtx = null) {
        // Create session lazily
        if (!this.state.currentSessionId) {
            const res = await rpc("/oacis_ai/chat/new_session", {});
            this.state.currentSessionId = res.id;
        }

        // Optimistic user message
        this.state.messages = [...this.state.messages, { role: "user", content: text }];
        this.state.isLoading = true;
        this.scrollToBottom();

        try {
            const ctx = recordCtx || this.currentRecordContext();
            const res = await rpc("/oacis_ai/chat/send", {
                session_id: this.state.currentSessionId,
                message: text,
                res_model: ctx.res_model || null,
                res_id: ctx.res_id || null,
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
    "oacis_ai.Chatbot",
    { Component: OacisAIChatbot },
    { sequence: 50 }
);

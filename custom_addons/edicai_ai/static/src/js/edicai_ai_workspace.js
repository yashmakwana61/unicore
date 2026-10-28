/** @odoo-module **/

import { Component, markup, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

/**
 * Edicai AI — full-page conversational workspace (Claude-style UI).
 *
 * Presentation layer only: existing Phase 0-11 endpoints and provider/
 * audit/ACL behaviour are untouched.  Endpoints used:
 *
 *   - /edicai_ai/chat/provider_status  (safe, keyless header chip)
 *   - /edicai_ai/chat/sessions          (sidebar, optional ?query=)
 *   - /edicai_ai/chat/new_session
 *   - /edicai_ai/chat/messages
 *   - /edicai_ai/chat/send
 *   - /edicai_ai/chat/rename_session
 *   - /edicai_ai/chat/delete_session
 */
/** Welcome-screen starters (one tap → grounded prompt). */
const STARTERS = [
    { label: "Show my fee status", prompt: "Show my fee status" },
    { label: "Check my attendance", prompt: "Check my attendance" },
    { label: "Any timetable clashes?", prompt: "Are there any timetable clashes?" },
    { label: "List admission programs", prompt: "List admission programs" },
];

/** Pick the escaped-safe link renderer for markdown output. */
const LINK_RE = /\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\)/g;

export class EdicaiAIWorkspace extends Component {
    static template = "edicai_ai.Workspace";
    static props = { ...standardActionServiceProps };

    setup() {
        this.state = useState({
            sessions: [],
            messages: [],
            currentSessionId: null,
            isLoading: false,
            isLoadingSessions: false,
            search: "",
            input: "",
            editingId: null,
            editingTitle: "",
            menuId: null,
            sidebarCollapsed: false,
            copiedIndex: null,
            showJump: false,
            provider: { provider_label: "", model: "", available: false, test_mode: false },
        });
        this.threadRef = useRef("thread");
        this.inputRef = useRef("composerInput");
        this.notification = useService("notification");
        this.starters = STARTERS;
        this._copiedTimer = null;

        // display name for the sidebar footer card (plain import — no
        // RPC, no sensitive payload beyond the display name)
        const name = String(user.name || "").trim();
        this._userName = name || "";
        this._userInitials = this._initials(name);
        this._isMobile = () => window.innerWidth <= 900;

        // outside-click closes the row menu; code-block copy delegation
        this._onDocClick = (ev) => {
            const copyBtn = ev.target.closest(".o_edicai_ai_ws_precopy");
            if (copyBtn) {
                this._copyFromCodeBlock(copyBtn);
                return;
            }
            if (!this.state.menuId) {
                return;
            }
            if (ev.target.closest(".o_edicai_ai_ws_popmenu")) {
                return;
            }
            this.state.menuId = null;
        };
        onWillStart(async () => {
            if (window.innerWidth <= 900) {
                this.state.sidebarCollapsed = true;
            }
            document.addEventListener("click", this._onDocClick, true);
            await Promise.all([this.refreshProviderStatus(), this.loadSessions()]);
        });
        onWillUnmount(() => {
            document.removeEventListener("click", this._onDocClick, true);
            if (this._copiedTimer) {
                clearTimeout(this._copiedTimer);
            }
        });
    }

    // ── identity chips for the sidebar footer ────────────────────────
    _initials(name) {
        const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
        if (!parts.length) {
            return "AI";
        }
        return parts.slice(0, 2).map((p) => p[0].toUpperCase()).join("");
    }

    get userName() {
        return this._userName || "You";
    }

    get userInitials() {
        return this._userInitials;
    }

    // ── provider indicator (safe, keyless) ───────────────────────────
    async refreshProviderStatus() {
        try {
            this.state.provider = await rpc("/edicai_ai/chat/provider_status", {});
        } catch {
            // never break the workspace over an indicator
        }
    }

    // ── helpers ─────────────────────────────────────────────────────
    /**
     * Resolve the session a DOM event belongs to.
     *
     * The OWL compiler EVALUATES handler arguments at render time, so a
     * handler must never receive the session as an argument
     * (``t-on-click="deleteSession(session)"`` would call the method on
     * every render).  The session id travels in a data attribute
     * instead.
     */
    _sessionFromEvent(ev) {
        const id = parseInt(ev.currentTarget.dataset.sessionId, 10);
        return this.state.sessions.find((s) => s.id === id) || false;
    }

    _nearBottom() {
        const el = this.threadRef.el;
        if (!el) {
            return true;
        }
        return el.scrollHeight - el.scrollTop - el.clientHeight < 130;
    }

    scrollToBottom(force) {
        const el = this.threadRef.el;
        if (!el) {
            return;
        }
        if (!force && (this.state.showJump || !this._nearBottom())) {
            // the user scrolled away — never yank the thread; the pill
            // offers the jump instead
            return;
        }
        requestAnimationFrame(() => {
            el.scrollTop = el.scrollHeight;
        });
    }

    onThreadScroll() {
        const el = this.threadRef.el;
        if (!el) {
            return;
        }
        const far = el.scrollHeight - el.scrollTop - el.clientHeight > 130;
        if (far !== this.state.showJump) {
            this.state.showJump = far;
        }
    }

    jumpToLatest() {
        this.state.showJump = false;
        this.scrollToBottom(true);
        this.focusComposer();
    }

    async clearSearch() {
        this.state.search = "";
        const el = document.querySelector(".o_edicai_ai_ws_search_input");
        if (el) {
            el.focus();
        }
    }

    // ── markdown (escape-first, small closed feature set) ───────────
    /**
     * Render assistant content.  Everything is ESCAPED FIRST; only a
     * closed set of markdown marks is then applied:
     * fenced/inline code, headings, blockquote, hr, nested lists,
     * paragraphs, links (http/https only), **bold**, *italic*.
     */
    formatMessage(content) {
        if (!content) {
            return "";
        }
        const esc = (s) => String(s)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
        let text = esc(content);
        // fenced code blocks → placeholders before inline processing so
        // their contents are never markdown-mangled
        const blocks = this._codeSnippets();
        text = text.replace(/```([\w+-]*)\n?([\s\S]*?)```/g, (m, lang, code) => {
            const key = blocks.length;
            blocks.push({
                lang: lang || "",
                code: code.replace(/\n+$/, ""),
            });
            return `\x00CODE${key}\x00`;
        });
        // inline code spans → placeholders for the same reason
        const spans = [];
        text = text.replace(/`([^`\n]+)`/g, (m, c) => {
            spans.push(c);
            return `\x00SPAN${spans.length - 1}\x00`;
        });
        // links first so their label can still carry bold/italic later
        text = text.replace(LINK_RE,
            '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
        text = text.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
        text = text.replace(/(^|\s)\*([^*\n]+)\*/g, "$1<em>$2</em>");

        text = this._blockRender(text);

        // restore code spans then fenced blocks
        text = text.replace(/\x00SPAN(\d+)\x00/g,
            (m, i) => `<code>${spans[Number(i)]}</code>`);
        text = text.replace(/\x00CODE(\d+)\x00/g, (m, i) => {
            const b = blocks[Number(i)];
            const lang = b.lang ? `<span class="o_edicai_ai_ws_prelang">${b.lang}</span>`
                                : "<span class=\"o_edicai_ai_ws_prelang\">text</span>";
            return ('<div class="o_edicai_ai_ws_preblock">'
                + '<div class="o_edicai_ai_ws_prehead">' + lang
                + `<button type="button" class="o_edicai_ai_ws_precopy"`
                + ` title="Copy code" data-code-id="${Number(i)}">Copy</button>`
                + "</div>"
                + `<pre>${b.code}</pre></div>`);
        });
        return markup(text);
    }

    /**
     * Line-based block renderer: paragraphs, #-headings, nested lists,
     * blockquotes, horizontal rules.
     */
    _blockRender(text) {
        const lines = text.split("\n");
        const out = [];
        let para = [];
        const flushPara = () => {
            if (para.length) {
                out.push(`<p>${para.join("<br/>")}</p>`);
                para = [];
            }
        };
        let i = 0;
        while (i < lines.length) {
            const line = lines[i];
            const trimmed = line.trim();
            if (!trimmed) {
                flushPara();
                i += 1;
                continue;
            }
            // heading
            let m = /^(#{1,3})\s+(.*)$/.exec(trimmed);
            if (m) {
                flushPara();
                const level = m[1].length;
                out.push(`<h${level}>${m[2]}</h${level}>`);
                i += 1;
                continue;
            }
            // horizontal rule
            if (/^([-*_])\1{2,}$/.test(trimmed)) {
                flushPara();
                out.push("<hr/>");
                i += 1;
                continue;
            }
            // blockquote run
            if (/^&gt;\s?/.test(trimmed) || /^>\s?/.test(trimmed)) {
                flushPara();
                const quote = [];
                while (i < lines.length && /^&gt;\s?/.test(lines[i].trim())) {
                    quote.push(lines[i].trim().replace(/^&gt;\s?/, ""));
                    i += 1;
                }
                out.push(`<blockquote>${quote.join(" ")}</blockquote>`);
                continue;
            }
            // list run (nested by two-space indent)
            m = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/.exec(line);
            if (m) {
                flushPara();
                i = this._renderList(m, lines, i, out);
                continue;
            }
            para.push(trimmed);
            i += 1;
        }
        flushPara();
        return out.join("");
    }

    /** Render one list run starting at ``first``; returns the new index. */
    _renderList(first, lines, i, out) {
        const items = [];
        let m = first;
        while (m) {
            const rawIndent = m[1].replace(/\t/g, "    ").length;
            items.push({
                depth: Math.min(4, Math.floor(rawIndent / 2)),
                ordered: /\d/.test(m[2]),
                text: m[3],
            });
            i += 1;
            m = i < lines.length
                ? /^(\s*)([-*+]|\d+[.)])\s+(.*)$/.exec(lines[i])
                : null;
        }
        let idx = 0;
        const emit = (depth) => {
            let inner = "";
            const levelItems = [];
            while (idx < items.length) {
                const it = items[idx];
                if (it.depth < depth) {
                    break;
                }
                if (it.depth === depth) {
                    if (levelItems.length) {
                        inner += "</li>";
                    }
                    levelItems.push(it);
                    inner += `<li>${it.text}`;
                    idx += 1;
                } else {
                    // deeper level → nested list inside the open <li>
                    inner += emit(depth + 1);
                }
            }
            if (!levelItems.length) {
                return inner;
            }
            const tag = levelItems[0].ordered ? "ol" : "ul";
            return `<${tag}>${inner}</li></${tag}>`;
        };
        out.push(emit(0));
        return i;
    }

    /** Component-scoped code snippet store for copy delegation. */
    _codeSnippets() {
        if (!this.__codeSnippets) {
            this.__codeSnippets = [];
        }
        return this.__codeSnippets;
    }

    _copyFromCodeBlock(btn) {
        const id = Number(btn.dataset.codeId);
        const block = this._codeSnippets()[id];
        if (!block) {
            return;
        }
        this._copyText(btn, block.code, "Copy");
    }

    async copyMessage(ev) {
        const idx = parseInt(ev.currentTarget.dataset.msgIndex, 10);
        const message = this.state.messages[idx];
        if (!message) {
            return;
        }
        this.state.copiedIndex = idx;
        if (this._copiedTimer) {
            clearTimeout(this._copiedTimer);
        }
        const ok = await this._writeToClipboard(message.content || "");
        if (!ok) {
            this.state.copiedIndex = null;
            this.notification.add("The reply could not be copied.",
                { type: "warning" });
            return;
        }
        this._copiedTimer = setTimeout(() => {
            this.state.copiedIndex = null;
        }, 1600);
        // keep the focus ring on the button while copied state shows
        ev.currentTarget.blur();
    }

    async _copyText(_btn, raw, _label) {
        const ok = await this._writeToClipboard(raw);
        if (!ok) {
            this.notification.add("The code could not be copied.",
                { type: "warning" });
            return;
        }
        // code copy buttons live inside t-out markup (not OWL-managed),
        // so feedback is done directly on the DOM node
        const btn = _btn;
        const prev = btn.textContent;
        btn.textContent = "Copied ✓";
        setTimeout(() => {
            btn.textContent = prev;
        }, 1400);
    }

    async _writeToClipboard(rawText) {
        try {
            await navigator.clipboard.writeText(rawText);
            return true;
        } catch {
            try {
                const ta = document.createElement("textarea");
                ta.value = rawText;
                ta.style.position = "fixed";
                ta.style.opacity = "0";
                document.body.appendChild(ta);
                ta.select();
                const ok = document.execCommand("copy");
                ta.remove();
                return ok;
            } catch {
                return false;
            }
        }
    }

    // ── date groups ─────────────────────────────────────────────────
    get sessionGroups() {
        const query = (this.state.search || "").trim().toLowerCase();
        const now = new Date();
        const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const buckets = {
            today: [], yesterday: [], week: [], month: [], older: [],
        };
        for (const session of this.state.sessions) {
            if (query && !(session.title || "").toLowerCase().includes(query)) {
                continue;
            }
            const stamp = session.write_date || session.create_date;
            if (!stamp) {
                buckets.older.push(session);
                continue;
            }
            const date = new Date(stamp);
            if (Number.isNaN(date.getTime())) {
                buckets.older.push(session);
                continue;
            }
            const day = new Date(date.getFullYear(), date.getMonth(), date.getDate());
            const diffDays = Math.round((startOfToday - day) / 86400000);
            if (diffDays <= 0) {
                buckets.today.push(session);
            } else if (diffDays === 1) {
                buckets.yesterday.push(session);
            } else if (diffDays < 7) {
                buckets.week.push(session);
            } else if (diffDays < 30) {
                buckets.month.push(session);
            } else {
                buckets.older.push(session);
            }
        }
        const groups = [];
        if (buckets.today.length) {
            groups.push({ key: "today", label: "Today", items: buckets.today });
        }
        if (buckets.yesterday.length) {
            groups.push({ key: "yesterday", label: "Yesterday", items: buckets.yesterday });
        }
        if (buckets.week.length) {
            groups.push({ key: "week", label: "Previous 7 days", items: buckets.week });
        }
        if (buckets.month.length) {
            groups.push({ key: "month", label: "Previous 30 days", items: buckets.month });
        }
        if (buckets.older.length) {
            groups.push({ key: "older", label: "Older", items: buckets.older });
        }
        return groups;
    }

    get currentTitle() {
        const session = this.state.sessions.find((s) => s.id === this.state.currentSessionId);
        if (session && session.title) {
            return session.title;
        }
        return "New chat";
    }

    /** Relative-time tooltip for a sidebar row ("Last message 2h ago"). */
    sessionTooltip(session) {
        const stamp = session.write_date || session.create_date;
        if (!stamp) {
            return "";
        }
        const then = new Date(stamp);
        if (Number.isNaN(then.getTime())) {
            return "";
        }
        const secs = Math.max(0, (Date.now() - then.getTime()) / 1000);
        let label;
        if (secs < 60) {
            label = "just now";
        } else if (secs < 3600) {
            const mins = Math.round(secs / 60);
            label = `${mins} min ago`;
        } else if (secs < 86400) {
            const hrs = Math.round(secs / 3600);
            label = `${hrs}h ago`;
        } else if (secs < 86400 * 7) {
            const days = Math.round(secs / 86400);
            label = `${days}d ago`;
        } else {
            label = then.toLocaleDateString();
        }
        return `Last message ${label}`;
    }

    get timeGreeting() {
        const hour = new Date().getHours();
        const part = hour < 12 ? "Good morning"
            : hour < 18 ? "Good afternoon" : "Good evening";
        const first = (this._userName || "").split(/\s+/)[0] || "";
        return first ? `${part}, ${first}` : part;
    }

    get canSend() {
        return Boolean((this.state.input || "").trim()) && !this.state.isLoading;
    }

    // ── sessions ────────────────────────────────────────────────────
    async loadSessions() {
        this.state.isLoadingSessions = true;
        try {
            this.state.sessions = await rpc("/edicai_ai/chat/sessions", {});
        } catch {
            this.state.sessions = [];
        }
        this.state.isLoadingSessions = false;
    }

    async newSession() {
        this.state.menuId = null;
        try {
            const res = await rpc("/edicai_ai/chat/new_session", {});
            this.state.currentSessionId = res.id;
            this.state.messages = [];
            this.state.editingId = null;
            this.state.showJump = false;
            if (this._isMobile()) {
                this.state.sidebarCollapsed = true;
            }
            await this.loadSessions();
            this.focusComposer();
        } catch {
            this.notification.add(
                "The conversation could not be created — please try again.",
                { type: "warning" }
            );
        }
    }

    /** Keyboard activation for a sidebar row (Enter/Space). */
    onRowKeydown(ev) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.loadSession(ev);
        }
    }

    async loadSession(ev) {
        const session = this._sessionFromEvent(ev);
        if (!session) {
            return;
        }
        this.state.menuId = null;
        try {
            const messages = await rpc("/edicai_ai/chat/messages", {
                session_id: session.id,
            });
            this.state.messages = messages;
            this.state.currentSessionId = session.id;
            this.state.editingId = null;
            this.state.showJump = false;
            if (this._isMobile()) {
                this.state.sidebarCollapsed = true;
            }
            requestAnimationFrame(() => this.scrollToBottom(true));
        } catch {
            this.notification.add(
                "This conversation could not be loaded.", { type: "warning" }
            );
        }
    }

    async deleteSession(ev) {
        const session = this._sessionFromEvent(ev);
        if (!session) {
            return;
        }
        this.state.menuId = null;
        if (!window.confirm(`Delete the conversation “${session.title || "New chat"}”?`)) {
            return;
        }
        try {
            await rpc("/edicai_ai/chat/delete_session", { session_id: session.id });
            if (this.state.currentSessionId === session.id) {
                this.state.currentSessionId = null;
                this.state.messages = [];
                this.state.showJump = false;
            }
            this.state.editingId = null;
            if (this._isMobile()) {
                this.state.sidebarCollapsed = true;
            }
            await this.loadSessions();
            this.notification.add("Conversation deleted", { type: "success" });
        } catch {
            this.notification.add(
                "The conversation could not be deleted.", { type: "warning" }
            );
        }
    }

    // ── row menu (Claude-style ⋯) ───────────────────────────────────
    toggleMenu(ev) {
        const id = parseInt(ev.currentTarget.dataset.sessionId, 10);
        this.state.menuId = this.state.menuId === id ? null : id;
    }

    closeMenu() {
        this.state.menuId = null;
    }

    // ── rename (inline edit in the sidebar) ─────────────────────────
    startRename(ev) {
        const session = this._sessionFromEvent(ev);
        if (!session) {
            return;
        }
        this.state.menuId = null;
        this.state.editingId = session.id;
        this.state.editingTitle = session.title || "";
        // focus after the input mounts
        requestAnimationFrame(() => {
            const input = document.querySelector(
                `.o_edicai_ai_ws_rename_input[data-session-id="${session.id}"]`);
            if (input) {
                input.focus();
                input.select();
            }
        });
    }

    cancelRename() {
        this.state.editingId = null;
        this.state.editingTitle = "";
    }

    async saveRename(ev) {
        const session = this._sessionFromEvent(ev);
        if (!session) {
            this.cancelRename();
            return;
        }
        const title = (this.state.editingTitle || "").trim();
        if (!title) {
            this.cancelRename();
            return;
        }
        if (title === session.title) {
            this.cancelRename();
            return;
        }
        try {
            const res = await rpc("/edicai_ai/chat/rename_session", {
                session_id: session.id,
                title,
            });
            if (res && res.success) {
                const target = this.state.sessions.find((s) => s.id === session.id);
                if (target) {
                    target.title = res.title || title;
                }
                this.notification.add("Conversation renamed", { type: "success" });
            }
        } catch {
            this.notification.add(
                "The conversation could not be renamed.", { type: "warning" }
            );
        }
        this.cancelRename();
    }

    onRenameKeydown(ev) {
        const session = this._sessionFromEvent(ev);
        if (!session) {
            this.cancelRename();
            return;
        }
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.saveRename(ev);
        } else if (ev.key === "Escape") {
            ev.stopPropagation();
            this.cancelRename();
        }
    }

    // ── messaging ───────────────────────────────────────────────────
    focusComposer() {
        const el = this.inputRef.el;
        if (el) {
            el.focus();
        }
    }

    async sendMessage() {
        // The composer is bound with t-model, so the text always lives in
        // the component state (no DOM read, no fragile ref).
        const text = (this.state.input || "").trim();
        if (!text || this.state.isLoading) {
            return;
        }
        this.state.input = "";
        // OWL does not overwrite a focused input, so clear the visible
        // text explicitly and release the focus.
        const el = this.inputRef.el;
        if (el) {
            el.value = "";
            this._growComposerInput();
            el.blur();
        }
        await this.doSend(text);
    }

    sendStarter(ev) {
        const item = this.starters[
            parseInt(ev.currentTarget.dataset.starterIndex, 10)];
        if (item && !this.state.isLoading) {
            this.focusComposer();
            this.doSend(item.prompt);
        }
    }

    async doSend(text) {
        this.state.menuId = null;
        this.state.showJump = false;
        this.state.isLoading = true;
        this.scrollToBottom(true);
        try {
            if (!this.state.currentSessionId) {
                const res = await rpc("/edicai_ai/chat/new_session", {});
                this.state.currentSessionId = res.id;
            }
            // optimistic user message
            this.state.messages = [
                ...this.state.messages,
                { role: "user", content: text },
            ];
            this.scrollToBottom(true);
            const res = await rpc("/edicai_ai/chat/send", {
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
                    {
                        role: "assistant",
                        content: res.reply,
                        source: res.source || "",
                        diagnostics: res.diagnostics || null,
                    },
                ];
            }
        } catch {
            this.state.messages = [
                ...this.state.messages,
                {
                    role: "assistant",
                    content: "⚠️ An unexpected error occurred. Please try again.",
                },
            ];
        }
        this.state.isLoading = false;
        this.scrollToBottom(true);
        await this.loadSessions();
    }

    // ── composer ────────────────────────────────────────────────────
    onComposerInput() {
        this._growComposerInput();
    }

    _growComposerInput() {
        const el = this.inputRef.el;
        if (!el) {
            return;
        }
        el.style.height = "auto";
        el.style.height = `${Math.min(el.scrollHeight, 192)}px`;
    }

    onComposerKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendMessage();
        }
    }

    toggleSidebar() {
        this.state.sidebarCollapsed = !this.state.sidebarCollapsed;
        this.state.menuId = null;
    }

    onGlobalKeydown(ev) {
        if ((ev.ctrlKey || ev.metaKey) && ev.key === "k") {
            ev.preventDefault();
            this.newSession();
            return;
        }
        if ((ev.ctrlKey || ev.metaKey) && ev.key === "b") {
            ev.preventDefault();
            this.toggleSidebar();
            return;
        }
        if (ev.key === "Escape" && this.state.menuId) {
            // the rename input handles its own Escape (stopPropagation)
            this.closeMenu();
        }
    }

    // ── template helpers ───────────────────────────────────────────
    stopClick() {
        // used with t-on-click.stop: keeps the parent row handler away
        // from the inline rename input
    }

    diagnosticsText(message) {
        try {
            return JSON.stringify(message.diagnostics, null, 2);
        } catch {
            return "";
        }
    }
}

registry.category("actions").add("edicai_ai.Workspace", EdicaiAIWorkspace);

/* Oacis AI — portal chat page logic (loads on /my/ai-assistant). */
(function () {
    'use strict';
    function init() {
        const msgs = document.getElementById('oacisAiMsgs');
        const input = document.getElementById('oacisAiInput');
        const sendBtn = document.getElementById('oacisAiSend');
        if (!msgs || !input || !sendBtn || msgs.dataset.ready) return;
        msgs.dataset.ready = '1';
        let sessionId = null;

        function bubble(role, text) {
            const div = document.createElement('div');
            div.className = 'p-2 rounded ' + (role === 'user'
                ? 'bg-primary text-white align-self-end'
                : 'bg-light border align-self-start');
            div.style.maxWidth = '85%';
            div.style.whiteSpace = 'pre-wrap';
            div.textContent = text;
            msgs.appendChild(div);
            msgs.scrollTop = msgs.scrollHeight;
        }
        async function jsonRpc(url, params) {
            const r = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: params || {} }),
            });
            const data = await r.json();
            if (data.error) throw new Error(data.error.message || 'Request failed');
            return data.result;
        }
        async function ensureSession() {
            if (sessionId) return sessionId;
            const s = await jsonRpc('/oacis_ai/chat/new_session', {});
            sessionId = s.id;
            return sessionId;
        }
        async function send(text) {
            text = (text || '').trim();
            if (!text) return;
            input.value = '';
            bubble('user', text);
            bubble('assistant', '…');
            const typing = msgs.lastChild;
            try {
                const sid = await ensureSession();
                const res = await jsonRpc('/oacis_ai/chat/send', { session_id: sid, message: text });
                typing.remove();
                bubble('assistant', res.error ? ('\u26A0\uFE0F ' + res.error) : res.reply);
            } catch (e) {
                typing.remove();
                bubble('assistant', '\u26A0\uFE0F ' + (e.message || 'Something went wrong.'));
            }
        }
        sendBtn.addEventListener('click', () => send(input.value));
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input.value); }
        });
        msgs.parentElement.querySelectorAll('.oacis-ai-suggest').forEach((b) =>
            b.addEventListener('click', () => send(b.dataset.q)));
        bubble('assistant', "Hello! I'm Oacis AI. Try My fees, Study plan, or ask anything else.");
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

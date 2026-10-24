# Prompt Enhance frontend

Next.js App Router and React client. Production routes always call the backend; there is no demo mode. Source bodies render as text, never executable HTML.

```sh
npm install
cp .env.example .env.local
npm run dev -- --hostname 127.0.0.1 --port 3000
```

`BACKEND_URL` is server-only and defaults to `http://127.0.0.1:8000`. `/api/v1/*` proxies to the backend `/v1/*`. Provider credentials belong in backend environment only.

```sh
npm run typecheck
npm run lint
npm test
npm run build
npm start
```

The draft and appearance preference are intentional local application state. Request payloads are not logged by the frontend. Outcomes contain only explicit event metadata. Knowledge preview generation and transactional save follow the synchronous contract in `contracts/http.md`; failed generation/save preserves source inputs, and retries reuse the save idempotency key.

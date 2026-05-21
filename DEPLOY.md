# Deploying RefundRoute — step-by-step

## What you're setting up

Your project has two halves:

- **The website** — what visitors see and click. This goes on **Vercel**.
- **The engine** — the behind-the-scenes program that reads contracts and
  builds the letters. This goes on **Render**.

Vercel and Render are two separate hosting companies. You'll set up the
engine first, then the website, then introduce them to each other.
Total time: about 15 minutes.

Your code is already on GitHub, so there's nothing to upload — Render
and Vercel pull it from there themselves.

## Before you start, have these ready

- Your **Anthropic API key** — from https://console.anthropic.com
- Your **Gemini API key** — from https://aistudio.google.com/apikey
- A **beta access code** — make one up now. It's the password your
  testers type to use the site (e.g. `maple-harbor-72`). Write it down.
- A credit card — the engine costs about **$7/month** (see Part 1, step 5).

## Part 1 — The engine (Render)

1. Go to **https://render.com** and click **Get Started**. When it offers
   sign-up options, choose **GitHub** — this lets Render see your code.
2. You'll land on the dashboard (**https://dashboard.render.com**). Click
   the **New +** button (top right), then choose **Blueprint**.
3. Render asks which repository to use. Pick **CarServiceCancellation**
   (it may appear lower-case). If it isn't listed, click **Configure
   account** and give Render permission to that repository.
4. Render reads the setup file in your project and shows one service,
   **refundroute-api**, with a few boxes to fill in. Fill them:
   - **ANTHROPIC_API_KEY** — paste your Anthropic key
   - **GEMINI_API_KEY** — paste your Gemini key
   - **REFUNDS_ACCESS_CODE** — type the beta access code you made up
   - **REFUNDS_ALLOWED_ORIGIN** — type exactly `https://example.com`
     for now (a placeholder; you fix it in Part 3)
5. Click **Apply** (or **Create**). Render asks you to confirm the plan —
   the **Starter** plan, about **$7/month** — and add a payment card.
   This small paid plan is what lets the engine remember your customers'
   cases between visits.
6. Render builds the engine — 2-3 minutes, with text scrolling. Wait
   until the status says **Live**.
7. Near the top, find the engine's web address. It looks like
   `https://refundroute-api.onrender.com`. **Copy it and write it down**
   — call it your **Engine address**.
8. Quick check: open a new browser tab and visit your Engine address
   with **`/api/health`** on the end — e.g.
   `https://refundroute-api.onrender.com/api/health`. If you see
   `{"ok": true}`, the engine is running.

## Part 2 — The website (Vercel)

1. Go to **https://vercel.com** and sign up — again, choose **GitHub**.
2. Click **Add New...** -> **Project** (or go to https://vercel.com/new).
3. Find **CarServiceCancellation** in the list and click **Import**
   (grant access if asked).
4. You'll see a settings screen. **One change matters:** find **Root
   Directory**, click **Edit**, and set it to just the word **`web`**.
   This tells Vercel the website lives in the project's "web" folder.
5. On the same screen, open **Environment Variables** and add one:
   - **Name:** `VITE_API_URL`
   - **Value:** your **Engine address** from Part 1 (the
     `https://...onrender.com` address — no slash at the end)
6. Click **Deploy** and wait 1-2 minutes.
7. When it finishes, Vercel shows your website's address — something
   like `https://carservicecancellation.vercel.app`. **Copy it and write
   it down** — your **Website address**.

## Part 3 — Introduce them to each other

The engine needs to know the website is allowed to talk to it.

1. Go back to Render (**https://dashboard.render.com**) and click your
   **refundroute-api** service.
2. In the left-hand menu, click **Environment**.
3. Find **REFUNDS_ALLOWED_ORIGIN** (it currently says
   `https://example.com`). Edit it and replace it with your **Website
   address** from Part 2 (the `https://...vercel.app` address — no slash
   at the end).
4. Click **Save changes**. Render restarts itself — about a minute.

## Part 4 — Try it

1. Open your **Website address** in a browser. You should see the
   RefundRoute landing page.
2. Click **Start a claim**.
3. When it asks for an **access code**, type the beta code you chose.
4. Fill in the form and continue through the steps.

If the whole flow works, you're live.

## If something's wrong

- **The page loads, but "Start a claim" gives an error** — almost always
  Part 3. Re-check that **REFUNDS_ALLOWED_ORIGIN** on Render is *exactly*
  your Vercel address: starts with `https://`, with no slash or extra
  text on the end.
- **`/api/health` doesn't show `{"ok": true}`** — the engine didn't
  start. On Render, open your service and click **Logs** to see why.
- **"Invalid or missing access code"** — the code you typed doesn't match
  `REFUNDS_ACCESS_CODE` on Render. They must match exactly.

## Keeping it private during the beta

The access code already keeps strangers out — no code, no claim. For an
extra lock, in Vercel go to your project -> **Settings** -> **Deployment
Protection** and turn on password protection for the whole site.

## Making changes later

You don't need to redo any of this. When new code is pushed, **Render
and Vercel both rebuild themselves automatically** — a new version just
goes live.

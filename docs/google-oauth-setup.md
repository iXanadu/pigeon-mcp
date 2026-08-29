# Google OAuth setup (and the scary warning)

This server talks to Gmail through the Gmail API. **You** create the OAuth client,
and **your** server holds the resulting refresh token. There is no hosted service
in the middle: nothing is registered with us, no token ever leaves your machine,
and the redirect URI points at **your** hostname. If you are ever unsure, open
the client in Google Cloud Console — the redirect URI should be
`https://<your-host>/oauth/callback` (Hand / HTTP) or, for local stdio only,
`http://127.0.0.1:8767/oauth/callback`.

## One-time Console steps

| Step | Where | What |
| --- | --- | --- |
| 1 | APIs & Services → Library | Enable **Gmail API** (required). Calendar / Drive may already be enabled on the project for *future* tools — this server does not use them yet; do not add those OAuth scopes until it does. |
| 2 | OAuth consent screen | See [User type](#user-type-workspace-vs-personal-gmail) below |
| 3 | Credentials → Create | **OAuth client ID → Web application** |
| 4 | Web client | Authorized redirect URI **`https://<your-host>/oauth/callback`** (must match `PIGEON_MCP_OAUTH_PUBLIC_REDIRECT_URI` in `.env`) |
| 5 | `.keys` | `PIGEON_MCP_GOOGLE_WEB_CLIENT_ID` / `PIGEON_MCP_GOOGLE_WEB_CLIENT_SECRET` (or primary slots if you use one client) |

For local stdio `accounts_add` only, add a **Desktop** client with redirect
`http://127.0.0.1:8767/oauth/callback` → `PIGEON_MCP_GOOGLE_CLIENT_ID` /
`PIGEON_MCP_GOOGLE_CLIENT_SECRET`. Hand over HTTP uses the Web client and
`accounts_auth_start`; consent completes via the public `/oauth/callback` route.

## Scopes requested

| Scope | Tier | Why |
| --- | --- | --- |
| `gmail.send` | Sensitive | Sending mail on your behalf |
| `gmail.modify` | Restricted | Reading, composing, labeling, archiving — and reading the send-as list (identities, live signatures) |

Two scopes, nothing else. `gmail.modify` already covers `settings.sendAs`
**get/list**, so the server does not request `gmail.settings.basic`,
`gmail.settings.sharing`, any Admin SDK scope, a service account, or domain-wide
delegation. Creating or verifying a send-as identity is deliberately out of reach —
that is a two-minute job for a human in Gmail settings. Accounts consented before
this change (three scopes) keep working without re-consent.

## Why Google calls the app "unverified"

Google requires formal review for apps requesting restricted scopes: demo video,
written justification, and (for many cases) third-party security assessment.
That process targets products distributed to strangers. It makes no sense for a
single-tenant tool you run for yourself, so this project does not ship a
Google-verified client — you self-host, and the warning is Google saying it has
not audited *your* deployment.

### User type: Workspace vs personal Gmail

**If you have Google Workspace** (a custom domain), the easy path is **Internal**
audience in Google Auth Platform → Audience. Verification requirements drop away,
the warning screen often never appears, and there is no 100-user cap. Only accounts
in your organization can authorize. The Cloud project must live in the same
organization as the mailbox, or authorization fails with an org-policy block.

**If you are on a personal `@gmail.com` account**, Internal is not available.
Use **External** and — critically — **Publish app** so status reads *In production*.
You will see a "Google hasn't verified this app" interstitial on first consent;
choose **Advanced → Go to … (unsafe)** and continue. You are the developer and
the only user.

## Do not leave the app in Testing status

This is the failure people actually hit. An External app left in **Testing** gets
refresh tokens that **expire after seven days**, and you re-authorize every week
for no reason. Google's wording:

> A Google Cloud Platform project with an OAuth consent screen configured for an
> external user type and a publishing status of "Testing" is issued a refresh
> token expiring in 7 days

Internal apps are unaffected. External apps **In production** are unaffected.
Only **Testing** has the 7-day fuse.

Flip to **In production** before you depend on this server in production — not
after cutover, not after the first successful send.

## What else can invalidate your token

- **Changing your Google account password** (Gmail scopes) — requires re-auth.
- **Six months without use.**
- **Revoking access** at [myaccount.google.com/permissions](https://myaccount.google.com/permissions),
  or a Workspace admin restricting the app.

## Protecting the token

The refresh token is long-lived and, with these scopes, is equivalent to standing
access to your mailbox. Keep credential files readable only by the service user
(`chmod 600` for `.keys`, `0640` for token JSON), out of version control, and out
of backup trees you do not trust. Revoke at the permissions link above if a host
is compromised.

On some production hosts, secrets are `0640` (not `0600`) so a backup agent in the
same group can read them — see your deploy runbook.

## Legal pages (OAuth consent screen)

Google asks for Privacy Policy and Terms of Service URLs on the consent screen.
For the c52.com deployment these are published at:

- Privacy: `https://pigeon.c52.com/privacy`
- Terms: `https://pigeon.c52.com/terms`

Markdown copies for your fork live in [`docs/legal/`](legal/README.md). Replace
with your own URLs when you self-host under another domain.

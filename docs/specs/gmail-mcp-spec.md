# Gmail MCP — what to build

This is the connector Cursor should have written. Gmail only. Share is done and out of scope.

Hand (and Inbox) have to talk to any Gmail account the operator adds: a consumer Gmail, a Workspace Gmail, a third — tomorrow a fourth without a code change.

Do not wrap `https://gmailmcp.googleapis.com/mcp/v1`. That host is what chopped a 140 KB PDF to a 3 KB stub and rewrote every live href to `https://www.google.com/url?q=...`. There is no repo to patch. Replace the send path.

## Auth: OAuth. Not password.

Google does not let a normal Gmail login (user + password) hit the Gmail API. App passwords are IMAP-only, weaker, and still not "any account." Domain-wide service accounts only cover a Workspace you admin, not a personal `@gmail.com`.

Use Google OAuth 2.0 with a refresh token (offline access). One Desktop OAuth client the operator owns. Each Gmail identity is a separate consent. Tokens live on the MCP host as files whose names contain `token` (mode 0640 so a group-readable backup can see them), never in chat, never in a tool argument.

`accounts.add` starts the Google consent for whichever Google identity the human picks in the browser. The server records the email Google returns. That email is the account key forever.

`accounts.remove` drops that token. Revoke it at Google if still valid.

No username. No password. No app password. No "paste a refresh token into chat."

Scopes, all of them, on every account:

- `https://www.googleapis.com/auth/gmail.modify`
- `https://www.googleapis.com/auth/gmail.send`

That is enough to search, read, label, trash, archive, draft, send, and reply — and `gmail.modify` also reads the send-as list, which is where live signatures and verified identities come from. Do not ask for `gmail.settings.basic` (redundant), the full-mail god scope, or any settings-sharing / admin scope. Do not cache the signature text.

## Identities and routing (mailroom)

One token can serve many agents. Gmail's send-as list is the registry — never a hand-kept roster.

- `identities_list(account)` returns send-as entries with `verificationStatus` accepted (the primary carries none and counts as accepted). Pending entries are filtered out.
- `send`, `reply`, `forward`, `draft_create` take optional `from_identity`. It must match an entry from that list, case-insensitively, **checked in the handler before any MIME is built**; otherwise the call fails naming the allowed set and nothing is uploaded. The chosen entry supplies `From` display name, `Reply-To` (its `replyToAddress` or itself) and its own live signature. Empty `from_identity` = bare account address, no `Reply-To`.
- Every message returned by `get_message`, `get_thread`, `messages_list` carries `originalTo` (`X-Gm-Original-To`), `deliveredTo`, `replyTo`, `messageId`, `authResults`. `format=metadata` asks Gmail for headers only (no body fetch).
- `messages_list(account, query)` lists messages (not threads) with those headers and a snippet.
- Never request `gmail.settings.sharing`, Admin SDK scopes, or attempt `sendAs.create`/`verify`.

## What failed, exactly

Cursor's hosted Gmail MCP is connected and has send. Send is still broken.

1. Attachments are a `content` field of base64 inside the tool JSON. The harness chops it. A 139,796-byte deed left Sent as `sizeEstimate` ~3350.
2. HTML hrefs are rewritten to `google.com/url`. Display text can look clean. Long-press on a phone shows Google.
3. `reply` has no attachment field at all.
4. A send that returns a message id is treated as success. It is not.

## Send contract

Build the RFC822 MIME on the MCP host. Send it with Gmail's media upload:

`POST https://gmail.googleapis.com/upload/gmail/v1/users/me/messages/send?uploadType=multipart`

Do not put file bytes in the tool-call JSON. Do not send a JSON `attachments[].content` field. If a caller passes `content` or `contentBase64`, reject the call.

Attachments are paths the server can read (`path`, plus optional `filename` and `mimeType`). Read the file, attach the real bytes, keep the name. Gmail's own 25 MB cap is the only size limit. A 140 KB PDF is a nothing burger.

Body:

- `body` only: `text/plain`.
- `htmlBody` only: `text/html` plus a plain alternative you generate without rewriting links.
- both: `multipart/alternative`. Use the HTML as written.

Never rewrite a URL. Never wrap `google.com/url`. Never "linkify." If the caller wrote `https://example.com/s/abc`, that string is the href.

`reply` and `forward` take the same attachment list as `send`. Thread with `In-Reply-To` and `References` from the source message. Stay on that thread.

From is the connected account. No From spoof.

Signatures: use them. The operator writes them in Gmail settings. Gmail's send API will not apply them for you. At send time, GET that account's send-as record (`users.settings.sendAs`) and append whatever is there now (HTML signature onto the HTML part, plain onto the plain part). Do not keep a copy on disk or in Hand. A stored paste is how a signature change still showed the old one.

After the live signature, add a caller-supplied footer (Hand passes its own; default is empty).

If send-as has no signature, send without one. Do not invent a KW / phone / social block.

## Proof is part of send

After Gmail accepts the message, GET it back (`format=raw` or `full`) and return facts, not hope:

- `id`, `threadId`, `from`, `sizeEstimate`
- each attachment: `filename`, `size`
- every href in the HTML (or empty if plain)
- `ok` true only if every attached file's Sent size is at least 90% of the source file and no href contains `google.com/url`

If `ok` is false, the tool errors. Do not report a successful send.

## Any account

Every tool except `accounts.list` and `accounts.add` takes `account` (the Gmail address). Wrong account is a hard error, not a guess.

Adding another mailbox is OAuth, not a deploy. One server, N tokens.

`accounts.list` returns the connected addresses and whether the refresh token still works.

## Tools (this many, not 31)

Keep the surface small. Cursor shipped thirty-one tools and still could not send a PDF.

| Tool | Does |
| --- | --- |
| `accounts.list` | Connected addresses |
| `accounts.add` | Start OAuth. Returns the email Google consented. |
| `accounts.remove` | Drop that token |
| `search` | Gmail query language. Threads. Pagination. |
| `get_thread` | Messages on a thread. Default plain text. `format=full` when we need HTML or hrefs. |
| `get_message` | One message |
| `get_attachment` | Write the file to a host path. Return path and byte size. Do not dump megabytes of base64 into the model. |
| `send` | New mail. Paths for files. Proof on the way out. |
| `reply` | Same as send, on a thread. Attachments allowed. |
| `forward` | Same. Attachments allowed. |
| `draft.create` / `draft.send` | Same attach and proof rules. |
| `labels.list` | System + user labels |
| `labels.create` | User labels (GBOT, GB-clutter, and the rest) |
| `label` / `unlabel` | Message or thread. Names or ids. Resolve names. |
| `archive` | Remove INBOX from a thread |
| `trash` / `untrash` | Thread. Prefer thread over single message. |

That covers inbox triage and real send. Filters, spam theater, and label color presets are not the hole. Skip them.

## Host

A local MCP the operator runs (stdio on this computer, or HTTP on a host this seat can reach). It talks to `gmail.googleapis.com`. It does not talk to `gmailmcp.googleapis.com`.

User-Agent on Google is whatever you want. This is not a Cloudflare problem.

Refresh tokens silently. If Google returns `invalid_grant`, that account is `needsAuth`. Say so. Do not send with a different account.

## Acceptance (do not ship without)

Run these against two real mailboxes the operator names (consumer → Workspace is enough).

1. `accounts.add` for a consumer Gmail and a Workspace Gmail. Both show up in `accounts.list`.
2. Send a ≥140 KB PDF from account A to account B. B receives that filename. Size matches. Sent `sizeEstimate` is not a stub.
3. Same send includes `https://example.com/x` in the HTML. The href in Sent and in B's inbox is that URL. Long-press is not `google.com`.
4. Reply on that thread with a second small file. Stays on the thread. File arrives.
5. `search`, `label`, `archive`, `trash` on a thread. Labels resolve by name (`GB-clutter`).
6. Add a third account with `accounts.add` and send from it. No code change.
7. A send that would have chopped (if someone passes base64 content) is rejected before it hits Gmail.
8. Change a unique string in that account's Gmail signature. The next send contains the new string and not the old one. Hand never supplied the signature text.

If 2, 3, or 8 fail, it is not done. 2 and 3 are the Cursor connector. 8 is the stale-signature bug.

## Out of scope

- Share. It works. Do not put Share tools in this server.
- AgentMail. Different MTA. Not the operator's Gmail boxes.
- A second plugin pointed at Google's hosted Gmail MCP.
- IMAP, passwords, app passwords.
- Caching a signature and pasting it later. Read it live or skip it.
- Mailing anyone. Policy stays with Hand. This server sends when a tool is called.

## Done looks like

Hand says send on any connected Gmail. The counterpart gets mail from that box, on that thread, with the signature that is in Gmail right now. The file opens. The link goes where we wrote it. Sent mail matches. A new Gmail is one OAuth, not a rewrite.

# pigeon.c52.com — asset kit and placement instructions

Open `placement-mockups.html` first. It is a single self-contained file showing all four pages
at structure level with every asset in position and numbered markers keyed to notes. Everything
below is the same information in text form.

This is a dressing pass, not a rewrite. Existing copy stays as written except where marked
**FIX** (something is wrong) or **NEW** (genuinely new copy, three short blocks, all on page four).

---

## The direction

tiding.sh is an engraved bird on a teal tide line, set in serif on paper, with process colours
used small. pigeon should read as the same press, different edition — not a copy of it.

The distinguishing idea: tiding's magpie **collects**. pigeon's bird **carries and returns**.
So the motif is the message capsule on the leg, the line is a single wire, and the palette
leans magenta where tiding leans cyan. Same paper, same serif, same plate separation.

Set every heading and all body copy in Source Serif 4. Do not introduce a sans for UI chrome —
including the wordmark. Mono is only for code, paths and tool names.

---

## Assets

| File | What it is | Where it goes |
| --- | --- | --- |
| `01-hero-bird-on-wire.jpg` | Engraved pigeon on a wire, capsule on the leg | Overview hero, right of the headline |
| `02-mark-bold.jpg` | Simplified bold-line bird | Nav mark at 46px; cropped square for the favicon |
| `03-bird-engraved-standing.jpg` | Finely hatched bird, no wire | No slot assigned yet — spare |
| `04-og-banner.jpg` | Bird right, bare wire, empty left two thirds | OG / share image only |
| `05-spot-feather.png` | Engraved feather | How it works, top right, ~130px |
| `06-spot-foot-capsule.jpg` | Foot gripping the wire, capsule hanging | For agents, top right, 200px minimum |
| `07-lockup-navy-offsite-only.jpg` | Navy bird + sans wordmark | GitHub and social profiles only — never on the site |
| `08-shot-linode-plans.png` | Linode plan picker, Nanode 1 GB selected | Your own server, above the provider list |
| `09-shot-cgtop.png` | `systemd-cgtop` on the live box | Your own server, after the timeline |

### Handling

All illustrations are black-on-white JPG/PNG. The site ground is paper, not white, so a raw
`<img>` will show as a visible square. Two options:

- `mix-blend-mode: multiply` on the image — works, no re-export needed, used throughout the mockups.
- Or knock the background out and ship transparent PNGs. Cleaner, but not required.

`06-spot-foot-capsule` is densely hatched. Below about 300px the capsule turns to mud — give it room.

Crop `08-shot-linode-plans` to the Shared CPU tile grid only; drop the tab row and the scrollbar.

Before publishing `09-shot-cgtop`, check the service names in it. It lists your other services by
name. If any of those shouldn't be public, crop or rerun filtered.

---

## Page one — Overview

**1 · The mark.** Bold-line bird at 46px beside "pigeon" set in the serif. Use the artwork's bird,
not its wordmark.

**2 · Dateline rail.** Thick-thin rule pair under the wordmark, carrying:
`Vol. I — August 2026 · Self-hosted Gmail over MCP · Streamable MCP · your OAuth client · Apache-2.0`
Overview only. This is the one place the system prints rules; do not repeat it on inner pages.

**3 · Hero bird.** Right of the headline, wire roughly on the baseline of the last line of body copy.

**4 · Numbers rail.** Four figures between the hero and "What it does". Every one is already true
and already stated somewhere on your site — three come from Hand's testimony, the fourth from
your own cgtop. Nothing invented.

- Of a 140 KB deed, what the standard connector delivered — **3 KB**
- What pigeon delivers, Gmail's own ceiling — **25 MB**
- Live links rewritten to a `google.com/url` redirect — **0**
- Resident memory on a shared $5 box — **70 MB**

**5 · The reason, moved up. FIX.** This is the real problem with the Overview: it explains what
pigeon *is* and never says what broke. Hand's first paragraph says it in one sentence and it is
currently sitting at the bottom of page three. Pull it forward, verbatim, as a pull quote before
"What it does". Nothing rewritten — moved.

Everything else on this page is unchanged.

---

## Page two — How it works

**6 · Feather spot.** Top right, aligned to the H1 cap height, ~130px. One spot per inner page is
the device that makes the four pages read as one publication without repeating the hero.

**7 · Four steps across, not down.** Same four steps, same words, set as four columns with large
cyan numerals. A vertical list of four reads as a procedure; four columns read as a diagram.

**8 · Routes as a table.** Currently a bulleted list with path and description run together.
Two columns — mono left, serif right. No content change.

Nothing on this page is wrong. It needs a spot and a layout pass, not edits.

---

## Page three — For agents

**9 · Foot and capsule spot.** Top right, 200px or larger.

**10 · Testimony to the top. FIX.** Hand's account is currently the last thing on the page, under
the footer rule, styled as an aside. It is the most persuasive writing on the site and the only
place the product's reason for existing is stated. Move it directly under the H1, word for word.
Set the last line as the pull quote and the two preceding paragraphs as a two-column run beneath it.

Connect / Send with a file / Rules of the road / What you will not do all stay as written,
in the current order, now below the testimony.

One note: "Cap is Gmail's ~25 MB" is buried in a caption under the stage example. That figure is
the direct answer to the 3 KB stub — it is why it appears in the numbers rail on page one. Leave
the caption as is.

---

## Page four — Your own server

This is the fear page. The fix is not shorter copy — it is showing the reader the *size* of the
thing before showing them the detail. Four assets, in this order, before the provider list.

**11 · The ten-minute timeline.** A single horizontal bar. Four solid-ink segments for the manual
steps (create the instance, DNS record, update and make a user, start the agent), then a much
longer tinted segment for everything that gets prompted. Labels beneath; "≈ 10 minutes by hand"
under the ink, "prompted, reviewed, not typed" under the tint. Solid ink is work you do; tint is
work you delegate, and the proportion is the argument. Check my four segment lengths — they are
guesses from your own step list.

**12 · The Linode screen.** Screenshot left, statement right: "One box. $5 a month." This does more
work than any diagram — the reader sees six tiles and a highlighted $5 one and understands that
the decision is one click. Place it *above* the provider list, not inside it. The eleven providers
below then read as optional shopping rather than eleven decisions.

**13 · The cgtop readout.** Full width, with a one-line caption pointing out that pigeon is
`uvicorn_gmcp_prod` at 70.5 MB. Ship it untouched — the mess is the credibility. Mail, chat, file
share, sip-phone, redis and fail2ban all on the one box, none of them large.

**14 · The undo button. NEW.** The only genuinely new copy in this kit. Three short blocks:

- *If you wreck it — Destroy it.* Delete the instance and create another. Nothing on the box
  can't be rebuilt by running the same four prompts again.
- *What a mistake costs — $0.0075/hr.* Linode prints the hourly rate on the tile. An instance
  you kill after twenty minutes costs a quarter of a cent.
- *What you can't lose — Your mail.* Gmail holds the mail; the box holds a token. Revoke it in
  your Google account and the wrecked server is inert.

The fear is not "will I understand nginx", it is "what if I break something I cannot fix". The
page never says the box is disposable. Check the revoke claim reads right to you before shipping.

### Two corrections on this page

- **"you do not need to become a sysadmin first"** is a denial, and denials plant the idea.
  Cut the clause. The sentence after it already says what you do instead.
- **"Worth knowing before you start"** is the last thing before the footer, so the page ends on
  four risks. Move it above the prompts, where the same words read as instructions.

---

## Still open

- Transparent PNG exports, if you want them instead of `mix-blend-mode: multiply`.
- The OG banner still needs cropping to 1.91:1 and the bird mirrored to face into the empty space.
- The loft-box spot was never generated. Nothing depends on it.
- `03-bird-engraved-standing.jpg` has no slot. Keep it in reserve.

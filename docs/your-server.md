# Your own server — the $5 VPS on-ramp

pigeon is small. So are the other tools worth self-hosting. One cheap VPS runs
several of them — you do about ten minutes of work by hand, then you prompt an
agent for the rest.

**If you wreck it — destroy it.** Delete the instance and create another;
nothing on the box can't be rebuilt by running the same four prompts again. A
mistake costs fractions of a cent an hour. **What you can't lose is your mail:**
Gmail holds the mail; the box holds a token. Revoke it in your Google account
and the wrecked server is inert.

## What you are buying

Any provider with a small Linux instance works. Around $5 / €5 a month buys
roughly 1–4 GB of RAM, a shared vCPU and 20–50 GB of disk. Prices and tiers
move constantly — treat the names below as where to look, not as a quote.

| Region | Providers | Notes |
| --- | --- | --- |
| Global | Akamai (Linode), DigitalOcean, Vultr | Linode runs the reference site; DO has the gentlest console; Vultr the widest region list |
| Europe | Hetzner, OVHcloud, Scaleway, netcup, IONOS, UpCloud | Hetzner usually most RAM per euro; EU-resident = GDPR-simple |
| Asia-Pacific / elsewhere | Alibaba, Tencent, BinaryLane, Bunny, local hosts | Local latency and billing often beat a big name |
| Free | Oracle Cloud Free Tier | Genuinely free ARM; capacity often unavailable, idle instances reclaimed — poor place for something you rely on |

**Pick the region deliberately.** Two things depend on it and neither is speed:
the jurisdiction your mail tokens sit in, and — if you are in the EU or serving
EU users — GDPR. An EU-resident host is the simpler answer there. Otherwise the
city closest to you, not the cheapest.

**Size.** 1 GB is comfortable for pigeon plus a couple of other small Python
services behind nginx (pigeon idles around 70 MB). Adding a database and three
or four more tools: start at 2–4 GB; resizing later means downtime. ARM
instances are cheaper and work fine; check anything you install has an arm64
build.

## The part you do by hand

Once, as root, before any agent is involved — so the agent has a safe account to
work in and a name to get a certificate for.

1. **Create the instance.** Ubuntu LTS. Paste your SSH public key into the
   create form — doing it now means you never enable password login at all.
2. **Point a DNS name at it.** An A record, e.g. `pigeon.example.com` → the
   instance IP. Do this early; certificates need the name to resolve.
3. **Update, and make yourself a user.** Log in as root once:
   ```bash
   apt update && apt full-upgrade -y
   adduser you
   usermod -aG sudo you
   rsync --archive --chown=you:you ~/.ssh /home/you/
   ```
   From then on log in as that user, not root.
4. **Install your agent, and stop typing.** Install whichever coding agent you
   use, log in as your user, start it in a working directory. That is the end
   of the manual part.

Worth knowing before you start:

- The agent has your sudo — give it a user account, not a root login.
- $5 is the box, not the backups — ask it to set up an off-box backup too.
- This host will hold mail tokens — its security is your mailbox's security.
- Cheap instances are shared — fine for tools; not for anything latency-critical.

## Then you prompt for the rest

You are not learning to administer a server; you are learning to direct one.
Work in small steps, ask for an explanation before a change, and ask for
evidence after it.

**1 · Look before touching**
```
You are on a fresh Ubuntu server that will be on the public internet. Change
nothing yet. Tell me: what is installed, what is listening on a port, what the
firewall state is, and what you would change before this box is exposed. List
it as findings, worst first.
```

**2 · Basic hardening**
```
Do the standard hardening for a small public server: unattended security
upgrades, a firewall allowing only SSH, HTTP and HTTPS, SSH key-only
authentication, and fail2ban. Explain each change before you make it, and
after each one show me the command that proves it took effect.
```

**3 · A name and a certificate**
```
Install nginx and certbot. Set up pigeon.example.com with a Let's Encrypt
certificate. Then prove renewal actually works with a dry run — do not just
tell me it is configured.
```
That last sentence matters more than it looks. A certificate that installs
cleanly and silently fails to renew is a site that breaks in ninety days.

**4 · Install pigeon**
```
Install pigeon-mcp from https://github.com/iXanadu/pigeon-mcp on this server,
following the repo's deploy documentation. Run it as its own service user,
never as root or as me. Bind it to loopback and put nginx in front with the
certificate you just set up. Read deploy/DEPLOYING.md first and tell me what it
requires before you start.
```

## How to talk to it

- **Ask for proof, not a report.** "Show me the command that proves it" beats
  "is it working?" — an agent that says done is describing its intent, not the
  machine.
- **One thing at a time.** A prompt that installs and configures and hardens in
  one pass is one you cannot review.
- **Make it explain first.** If the explanation is wrong, you have caught it
  before it ran.
- **Keep the secrets out of the chat.** Tokens and keys belong in files on the
  server. Tell it to write them there and show you the permissions, not the
  contents.

## One $5 box, in practice

The reference host runs pigeon (a few mailboxes, a few hundred MB of RAM), a
file share so an agent can hand out a link instead of an attachment, and a
memory service so agents remember across sessions and machines — all small
Python services behind one nginx. The cost of the server is not the interesting
number; the interesting number is that none of them are someone else's SaaS,
and none of them can change their terms on you.

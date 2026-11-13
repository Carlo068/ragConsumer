# Accounts, sessions and sign-in safety

How people sign in, how an administrator takes access away, and what protects
against password guessing. Everything below is implemented and tested
(`backend/__tests__/test_account_lifecycle.py`); the numbers are settings in
`backend/app/config.py`.

## Sessions live on the server

Signing in creates a **session** in the database. The browser's cookie only carries
that session's id (signed, `HttpOnly`, `SameSite=Lax`, `Secure` in production). So a
session can be ended on the server, and a copied cookie stops working with it:

- **Signing out** ends the session on the server, not just in that browser.
- A session also ends after **2 hours without use** (`SESSION_IDLE_MINUTES`) and
  after **12 hours in any case** (`SESSION_MAX_AGE_HOURS`).
- Every request re-checks that the session is open and that the account is active.
  Ending a session, disabling the account or going idle therefore takes effect on the
  very next click, with no waiting for a cookie to expire.

## When someone leaves the firm (offboarding)

On **Usuarios e invitaciones** (administrator), next to the person:

| Button | What happens |
|---|---|
| **Desactivar** | They are signed out of every browser at once, cannot sign in, and **all their AI access keys are revoked** (the MCP server also refuses any key whose owner is disabled). Their matters, uploads and history are untouched. You cannot disable your own account, so the firm can never be left without an administrator. |
| **Reactivar** | They can sign in again with their current password. Their old AI keys stay revoked; they create new ones. |
| **Cerrar sesión en todo lado** | Signs them out everywhere without disabling the account (a lost laptop, a shared computer). |
| **Restablecer contraseña** | Creates a one-use link (valid 72 hours) to send them. They choose a new password and every other session is ended. The administrator never sees or sets a password. |

Also remove them from the matters they belonged to (that is separate: disabling an
account does not change matter membership) and, if they ever had server access,
follow `deployment/04-secrets.md` ("when to rotate"). Every one of these actions is
written to the activity log.

## Changing your own password

**Mi cuenta y contraseña** (the menu under the initials, top right). It needs the
current password, enforces the 12-character minimum, and signs out every *other*
device. Wrong current passwords count like failed sign-ins (below), so a stolen
session cannot be used to guess the password.

## Password guessing

| Protection | Setting (default) |
|---|---|
| Failed sign-ins are counted per account **and** per address over a 15-minute window | `LOGIN_WINDOW_MINUTES=15` |
| 10 failures for one account pause sign-in for that account | `LOGIN_MAX_FAILURES_PER_ACCOUNT=10` |
| 30 failures from one address pause sign-in from it, for every account | `LOGIN_MAX_FAILURES_PER_IP=30` |
| While paused, even the right password is refused; the pause ends by itself | |
| The pause is recorded in the log **once per window**, so hammering an account cannot fill the log | |
| Invitation and reset links: 30 requests per address per 15 minutes | `INVITE_MAX_REQUESTS_PER_IP=30` |
| An unknown email, a wrong password and a disabled account all get the same answer, and take the same time | |
| Passwords are argon2 hashes, minimum 12 characters | `MIN_PASSWORD_LENGTH=12` |

Counting is done in the audit log, so it survives a restart. Trade-off to know: someone
who deliberately fails 10 times against a colleague's email can lock *that* account for
up to 15 minutes (it unlocks by itself). The activity log shows these as "Inicio de
sesión en pausa por intentos fallidos" with the address, so a real attack is visible.

The reverse proxy (Caddy) has no rate limiting of its own; the limits above are in the
application. The address used is the real client address, which Caddy forwards
(`FORWARDED_ALLOW_IPS` in `docker-compose.prod.yml`).

## What is in the activity log

`login`, `login_failed` (with the reason `account_disabled` when that was the cause),
`login_throttled`, `logout`, `password_changed`, `password_reset_created`,
`password_reset_completed`, `user_disabled`, `user_enabled`, `sessions_ended`,
`access_denied` (a refused matter request: who, which matter, which request, from
where), plus
everything listed in the application's activity view.

## Cross-site request forgery

The cookie is `SameSite=Lax` and everything is served from one HTTPS address, so
other websites cannot make a signed-in browser perform actions. **This depends on
both facts.** Before ever relaxing `SameSite`, or serving the web app and the API
from different sites, add an explicit CSRF defence (a per-session token or a strict
`Origin` check); a test asserts the cookie's attributes so a change cannot go
unnoticed.

## Upgrading from the earlier version

The first deploy of this change signs everybody out once (old cookies have no server
session). The database migration is additive, so a rollback is safe
(`deployment/06-deploy-and-rollback.md`).

# Hardening the server

The server will hold privileged client documents, so it is locked down before
anything is installed on it. Two scripts in `deploy/` do and check this on a
fresh **Ubuntu 24.04** server.

## First time

1. Create the server at your provider with an **encrypted disk** (see below)
   and add your SSH public key to the root account when asked.
2. Log in as root, get the repository onto the server, and run:

   ```bash
   sudo DEPLOY_SSH_KEY="ssh-ed25519 AAAA... you@laptop" bash deploy/harden-server.sh
   ```

   It will refuse to run without a key, because turning passwords off without
   a key to log in with would lock everybody out.
3. **Before closing that session**, open a second terminal and log in as the
   new user: `ssh deploy@<server>`. Only if that works, close the first one.
4. Check the result: `sudo bash deploy/check-hardening.sh`.

The script is safe to run again; every step checks before it changes anything.

## What it sets up

| Control | Detail |
|---|---|
| Non-root user | `deploy` runs Docker and does the administration (it has sudo, which adds no power beyond what Docker membership already gives). |
| SSH | Keys only. No passwords, no keyboard-interactive, no root login, only `deploy` may log in, 3 attempts per connection, 30 seconds to log in, no X11 or agent forwarding. The root password is locked. |
| Firewall (`ufw`) | Everything incoming is denied except 22 (rate limited: repeated connections are refused), 80, 443 and 443/udp (HTTP/3). |
| `fail2ban` | Bans an address that keeps failing SSH logins, for an hour at first and longer for repeat offenders (up to a week). |
| Updates | Security updates install automatically. If one needs a reboot (a kernel update), the server reboots at 04:00 and every container restarts by itself. |
| Docker | Container logs rotate (10 MB, 5 files) so they cannot fill the disk, and `no-new-privileges` is the default for containers. |
| Kernel | SYN-flood protection, reverse-path filtering, and no ICMP redirects or source routing. |

## Disk encryption (done at the provider)

Encryption at rest is a volume setting at the cloud provider, not something a
script can turn on afterwards. Enable it when creating the server, for the
system disk *and* any extra data volume, and snapshots should inherit it.
`check-hardening.sh` reminds you because it cannot see this from inside the
server. See `01-provider-options.md` for each provider.

## One thing to know about Docker and the firewall

Docker publishes container ports by editing the firewall itself, in a way that
`ufw` does not see. That is why the production compose file
(`docker-compose.prod.yml`) is built to publish **only** ports 80 and 443, and
why the check script lists what Docker publishes and fails if anything else is
reachable from outside. Never add a `ports:` entry to a service in production.

## Checking later

`sudo bash deploy/check-hardening.sh` prints PASS or FAIL for each control and
exits non-zero if anything is wrong. Run it after hardening, after every deploy
(KAN-90) and now and then in between. It also checks that `.env` is readable
only by `deploy` (mode 600).

## If you get locked out

Use the provider's web console (every provider has one) to log in as root
locally, fix `/etc/ssh/sshd_config.d/00-ragconsumer-hardening.conf` or
`/home/deploy/.ssh/authorized_keys`, and `systemctl reload ssh`. The SSH
settings live in that one file.

## How this was tested

`bash deploy/test-hardening.sh` builds a throwaway Ubuntu 24.04 machine with
real systemd (a privileged container), hardens it, and then tries to break in:
it checks that the script refuses to run without a key, that `deploy` can log in
with its key but not with a password, that root and other users are refused
even with a valid key, that only the intended ports are open, and that the
check script passes when everything is right and fails when password login or
an extra port is switched on. A separate attack from another address was also
confirmed to be rate limited by the firewall and then banned by `fail2ban`.
Run it again after changing either script.

# Agora

Highly available voting platform deployed on two independent sites, linked by an IPsec site-to-site VPN between two OPNsense firewalls.

## Architecture

Each site is identical and self-contained:

| Component | Role | Site A (10.0.2.0/24) | Site B (10.15.15.0/24) |
|---|---|---|---|
| OPNsense | Firewall, NAT, port forwarding, IPsec | 10.0.2.1 (LAN) | 10.15.15.1 (LAN) |
| Virtual IP | Held by the Keepalived MASTER | 10.0.2.100 | 10.15.15.100 |
| ha1 | HAProxy + Keepalived (MASTER) | 10.0.2.5 | 10.15.15.10 |
| ha2 | HAProxy + Keepalived (BACKUP) | 10.0.2.6 | 10.15.15.11 |
| web | Web server running the Agora app | 10.0.2.7 | 10.15.15.7 |
| db | MySQL | 10.0.2.8 | 10.15.15.8 |

Request path: client → OPNsense WAN (80/443) → virtual IP → active HAProxy → web server → MySQL.

Between the two sites, traffic goes through the IPsec tunnel (IKEv2, ESP, tunnel mode) with no NAT.

## Repository layout

```
agora-infra/
├── app/        Shared voting application (same code on both sites)
├── site_a/     Site A: Vagrantfile, Ansible, OPNsense export
├── site_b/     Site B: Vagrantfile, Ansible, OPNsense export
└── docs/       Diagrams, addressing plan, IPsec parameters, report, test screenshots
```

Each site folder is independent. Commands run inside `site_a/` only ever touch site A's VMs, and the same goes for `site_b/`.

## Prerequisites

- Debian host
- VirtualBox, Vagrant, Ansible
- An OPNsense ISO (installed by hand, see below)

## Build a site

Example for site B. For site A, use `site_a/` instead.

1. **Create the VMs**
```bash
   cd site_b
   vagrant up
```
   Check: every VM pings the other three (Test 1).

2. **Install OPNsense by hand** in VirtualBox with two NICs:
   - WAN: bridged adapter (network shared with the other site)
   - LAN: internal network `site_b_lan`, IP 10.15.15.1/24

   Then set the default route of the VMs through OPNsense:
```bash
   vagrant provision --provision-with route
```
   Check: the VMs reach the internet through OPNsense (Test 2).

3. **Configure the VMs with Ansible**
```bash
   cd ansible
   ansible-playbook site.yml
```
   This installs MySQL, the web server, the app, Keepalived and HAProxy.

4. **NAT and firewall rules** in OPNsense: forward WAN ports 80/443 to the virtual IP, and keep the other rules minimal.

5. **IPsec tunnel**: configure phase 1 and phase 2 as mirrors on both OPNsense, using the table in `docs/ipsec-parameters.md`.

## Validation tests

| # | Test | Command or action | Expected result |
|---|---|---|---|
| 1 | Public web access | `http://<OPNsense WAN IP>` | Agora home page |
| 2 | High availability | `sudo systemctl stop keepalived` on the MASTER | VIP moves, site stays reachable |
| 3 | Database access | `mysql -h <db IP> -u <user> -p` from the web VM | Connection accepted |
| 4 | Isolation | Port 3306 from the WAN | Connection refused |
| 5 | IPsec tunnel | VPN › IPsec › Status Overview | Phase 1 and phase 2 established |
| 6 | Inter-site | `ping` the other site's web VM | Replies, no NAT |

Screenshots of each test go in `docs/tests/`.

## The application

Agora is a simple voting app where admins create polls and logged-in users vote once per poll. It is built with Python, Flask and MySQL, with a pastel, friendly interface.

The code is identical on both sites. Only environment variables change (database host, site name), and Ansible sets them.

A footer on every page shows which site served the request ("Served by Site A/B"), which is useful for the failover demo.

Full documentation: **[app/README.md](app/README.md)**

## Team and ownership

| Person | Site | Folder |
|---|---|---|
| <your name> | Site B | `site_b/` |
| <colleague name> | Site A | `site_a/` |

The `app/` and `docs/` folders are shared. Use branches and pull requests there.

## Security notes

- OPNsense XML exports contain the IPsec PSK and password hashes. Keep this repo private, or replace secrets with placeholders before committing.
- Passwords (MySQL, app secret) are stored with `ansible-vault`, never in plain text. The vault password file is in `.gitignore`.
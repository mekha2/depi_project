# Ansible automation

Prepares a Linux server, installs Docker Engine and the Compose plugin, and deploys the traffic dashboard stack
(with the monitoring add-on from `docker-compose.monitoring.yml`).

Targets: Ubuntu or Debian (amd64/arm64) with systemd. Tested with ansible-core 2.21 and community.docker 4.8.

## Requirements (machine running Ansible)

- Linux, macOS or WSL2. Ansible does not run natively on Windows.
- `ansible-core` 2.15 or newer: `pip install ansible-core`
- Collection: `ansible-galaxy collection install -r requirements.yml`

## Layout

```
ansible/
  ansible.cfg                  run Ansible from this folder
  requirements.yml             community.docker
  inventory/hosts.yml          default: this machine (ansible_connection: local)
  inventory/remote.example.yml template for a real server
  inventory/group_vars/all.yml every setting, with comments
  playbooks/{site,common,docker,deploy}.yml
  roles/common                 apt packages (ca-certificates, curl, gnupg, git), optional timezone
  roles/docker                 Docker apt repo + key, docker-ce, containerd, buildx, compose plugin, daemon.json, service, docker group
  roles/traffic_stack          copy/clone project, optional .env, docker compose up, HTTP checks
```

## Run

```bash
cd ansible
ansible-playbook playbooks/site.yml --syntax-check
ansible-playbook playbooks/site.yml --ask-become-pass            # this machine
ansible-playbook playbooks/site.yml -e traffic_become=false      # when already root
```

Parts: `--tags common`, `--tags docker`, `--tags deploy` (inside it: `sync`, `up`, `verify`).
Without monitoring: `-e traffic_enable_monitoring=false`. Without HTTP checks: `-e traffic_verify=false`.

Afterwards: http://SERVER, http://SERVER:9090, http://SERVER:3000.

## Real server or VM

```bash
cp inventory/remote.example.yml inventory/remote.yml     # set ansible_host, ansible_user, key
ansible-playbook -i inventory/remote.yml playbooks/site.yml
```

- SSH access and a user with sudo. Add `--ask-become-pass` if sudo needs a password.
- Ports 80, 9090 and 3000 reachable (open them in the server firewall or cloud security group yourself; these roles do not touch firewalls).
- Default `traffic_deploy_source: local` copies `app/`, `dashboard/`, `nginx/`, `monitoring/` and the compose files from the checkout on the machine running Ansible.
  To clone from Git instead: `-e traffic_deploy_source=git -e traffic_repo_url=<url>` (the server needs access to that repository).
- Set a Grafana password: `ansible-vault encrypt_string 'password' --name traffic_grafana_admin_password`, paste into `inventory/group_vars/all.yml`, run with `--ask-vault-pass`.
- `docker_configure_daemon: true` overwrites `/etc/docker/daemon.json`. Set it to `false` on servers that already have one.
- Use `docker_users: [youruser]` to allow that user to run docker without sudo (needs a new login).
- Re-running is safe. Removed repository files are not deleted from the server.

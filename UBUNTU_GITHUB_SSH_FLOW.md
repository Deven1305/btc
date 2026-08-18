# Ubuntu server to GitHub: complete SSH flow

Use the normal Ubuntu Terminal. Git Bash on Windows is not required, and the Python virtual environment is unrelated to Git/SSH.

The GitHub repository is **`Deven1305/btc`**. The local folder may be named `btc`, `btc-intel`, or something else; the folder name does not change the GitHub repository name. The commands below use the path shown in your screenshot: `~/Desktop/wallet_add/btc`.

```text
Ubuntu terminal -> generate SSH key -> add public key to GitHub
                -> configure SSH remote -> test -> git push origin main
                -> optionally start the sync tmux session
```

The private key stays on Ubuntu. GitHub receives only the public key. Deleting the key from GitHub settings revokes future access from this server.

## 1. Enter the existing repository

```bash
cd ~/Desktop/wallet_add/btc
whoami
pwd
git remote -v
```

Do not run `git init` again or clone a second copy if this directory is already the repository.

## 2. Generate a dedicated key

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
ssh-keygen -t ed25519 \\
  -C "btc-intel-ubuntu-server" \\
  -f ~/.ssh/id_ed25519_btcintel
```

For unattended pushing, press Enter twice for an empty passphrase. A passphrase is safer for manual use but requires an SSH agent after reboot.

### If the multiline command gives `Too many arguments`

Use this single line instead. It avoids Bash line-continuation problems when copying from a document:

```bash
mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh" && ssh-keygen -t ed25519 -C "btc-intel-ubuntu-server" -f "$HOME/.ssh/id_ed25519_btcintel"
```

The command must contain ordinary single hyphens (`-C` and `-f`). Do not paste doubled backslashes (`\\`) at the end of lines. If you want to check whether a key already exists first:

```bash
ls -la "$HOME/.ssh"
```

Only continue with `ssh-keygen` if `id_ed25519_btcintel` does not already exist.

## 3. Add the public key on GitHub

```bash
cat ~/.ssh/id_ed25519_btcintel.pub
```

Open **GitHub -> Settings -> SSH and GPG keys -> New SSH key** and fill:

```text
Title: BTC-Intel Ubuntu Server
Key type: Authentication Key
Key: paste the complete output from the cat command
```

Paste only the `.pub` output into your GitHub account's **SSH and GPG keys** page. This public key is not pushed into the Git repository. Never paste `~/.ssh/id_ed25519_btcintel`, which is private.

If the private key (the file without `.pub`) was pasted into GitHub by mistake, delete that GitHub key immediately, delete the local key files, and generate a new pair. Treat an exposed private key as compromised.

## 4. Configure SSH

```bash
nano ~/.ssh/config
```

Paste this block, then save with `Ctrl+O`, Enter, and exit with `Ctrl+X`:

```ssh
Host github.com-btcintel
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_btcintel
    IdentitiesOnly yes
```

```bash
chmod 600 ~/.ssh/config
ssh -T git@github.com-btcintel
```

The successful response says authentication succeeded but GitHub provides no shell access. That is expected.

## 5. Change the `Deven1305/btc` repository remote and test a push

```bash
cd ~/Desktop/wallet_add/btc
git remote set-url origin git@github.com-btcintel:Deven1305/btc.git
git remote -v
printf 'SSH push test from Ubuntu at %s\\n' "$(date -Is)" > github_ssh_test.txt
git add github_ssh_test.txt
git commit -m "Test SSH push from Ubuntu"
git pull --rebase origin main
git push origin main
```

Verify from Windows at:

```text
https://github.com/Deven1305/btc/blob/main/github_ssh_test.txt
```

## 6. Start only the optional sync session

The running `kaggle` and `elliptic` sessions do not need to be stopped. Start the missing `sync` session:

```bash
cd ~/Desktop/wallet_add/btc/server_backfill
source venv/bin/activate
chmod +x run_sync_daemon.sh auto_git_sync.sh
tmux new-session -d -s sync './run_sync_daemon.sh'
tmux list-sessions
```

You should see `kaggle`, `elliptic`, and `sync`.

Inspect it without interrupting anything:

```bash
tmux capture-pane -pt sync:0 -S -30
tail -30 logs/sync_daemon.log
```

## Revocation and authentication notes

From any laptop, delete `BTC-Intel Ubuntu Server` under GitHub **Settings -> SSH and GPG keys**. Future server authentication will then fail. A public repository can be cloned without authentication, but pushing still requires an account with write permission. Git commit name/email are author metadata, not passwords.

Making the repository private is not required for SSH safety. The SSH key is attached to your GitHub account, not to the repository contents. Keeping the repository private is still preferable if the data or output files should not be publicly downloadable.

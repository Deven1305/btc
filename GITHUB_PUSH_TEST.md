# GitHub push test from the Ubuntu server

The GitHub repository used here is **`Deven1305/btc`**. `btc-intel` is only a project/local-folder name used in some older instructions; it is not the GitHub repository name.

The repository may be public for easy cloning, but GitHub still requires authentication for every push. You do not need to enter your GitHub password, and you should never put a password in a command. Use a Personal Access Token (PAT) for this one-time HTTPS test, or use SSH for unattended 24/7 pushing.

## What the two screenshots show

The server is Ubuntu 22.04.5 LTS on an Intel Xeon Bronze 3204. It has 6 CPU cores/threads, 62 GiB RAM with about 53 GiB available, an approximately 1.8 TB root filesystem with about 579 GB free, and a Matrox G200eH3 display adapter (not a CUDA/NVIDIA compute GPU). Uptime is about 10 weeks. The machine has plenty of RAM for these workers; disk usage should be watched because output CSVs grow continuously.

The second screenshot shows two active tmux sessions:

```text
elliptic
kaggle
```

That means the two backfill jobs are running. There is no `sync` session in the screenshot, so the automatic GitHub sync daemon is not currently running.

## Check the running jobs without stopping them

Run these commands from the repository directory. They are read-only:

```bash
cd ~/Desktop/wallet_add/btc
whoami
pwd
tmux list-sessions
ps -fu "$USER" | grep -E 'backfill_server|run_kaggle|run_elliptic' | grep -v grep
```

View recent output without attaching or interrupting a job:

```bash
tmux capture-pane -pt kaggle:0 -S -20
tmux capture-pane -pt elliptic:0 -S -20
```

Check queue progress:

```bash
cd ~/Desktop/wallet_add/btc/server_backfill
source venv/bin/activate
python3 backfill_server.py \
  --queue queues/kaggle_all_addresses.csv \
  --out output/backfill_kaggle_reverse.csv --status
python3 backfill_server.py \
  --queue queues/queue_elliptic_pp.csv \
  --out output/backfill_elliptic_reverse.csv --status
```

## Option A: quickest HTTPS push test with a GitHub PAT

1. On GitHub, open **Settings -> Developer settings -> Personal access tokens -> Fine-grained tokens -> Generate new token**.
2. Give it access only to `Deven1305/btc`.
3. Grant repository **Contents: Read and write** permission.
4. Copy the token once. It is used as the password when Git asks.

On the Ubuntu server, run exactly:

```bash
cd ~/Desktop/wallet_add/btc
git config user.name "Deven1305"
git config user.email "YOUR_GITHUB_EMAIL"
printf 'GitHub push test from Ubuntu at %s\n' "$(date -Is)" > github_push_test.txt
git add github_push_test.txt
git commit -m "Test GitHub push from Ubuntu"
git pull --rebase origin main
git push origin main
```

When prompted:

```text
Username: Deven1305
Password: paste the PAT here (not your GitHub account password)
```

The token is not displayed while typing. Never paste it into a remote URL or into this file.

Confirm the test from Windows by opening:

```text
https://github.com/Deven1305/btc/blob/main/github_push_test.txt
```

## Option B: recommended authentication for unattended 24/7 pushes

For the long-running sync daemon, configure a dedicated SSH key on the Ubuntu server. Keep the private key on the server, and add only its `.pub` file under **GitHub -> Settings -> SSH and GPG keys**. Then use:

```bash
cd ~/Desktop/wallet_add/btc
git remote set-url origin git@github.com:Deven1305/btc.git
ssh -T git@github.com
git push origin main
```

SSH avoids storing a PAT and works with a private or public repository. A public repository changes cloning only; it does not remove the requirement to authenticate when pushing.

## Start the optional automatic status-push daemon

The screenshots show only `kaggle` and `elliptic`. Start `sync` separately after the manual test succeeds:

```bash
cd ~/Desktop/wallet_add/btc/server_backfill
source venv/bin/activate
chmod +x run_sync_daemon.sh auto_git_sync.sh
tmux new-session -d -s sync './run_sync_daemon.sh'
tmux list-sessions
```

You should then see `kaggle`, `elliptic`, and `sync`. The daemon generates `STATUS.md` and attempts its scheduled Git push. Check `logs/sync_daemon.log` if `sync` exits.

## Windows Git note

Install **Git for Windows** only if you want to clone or inspect the repository from Windows. It is not required for the Ubuntu server to push. If you do install it, use Git Bash; do not copy the Ubuntu server's private SSH key to the Windows computer.

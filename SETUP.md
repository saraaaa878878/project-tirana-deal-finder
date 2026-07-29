# Week 0 — Setting Up Your Computer

Welcome! Before we build anything, we need to get your computer ready. This guide takes you
from **nothing installed** to **ready to run the project** — no prior terminal experience needed.

**Take your time.** This is a one-time setup, maybe 30–45 minutes. If something goes wrong,
that's normal — check [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) or ask. Everyone hits a snag
here; it's part of the process.

> **On a Mac?** Skip to the [Mac section](#appendix-setting-up-on-a-mac) at the bottom.
> The steps below are for **Windows**.


## What we're installing

By the end you'll have:

1. **WSL (Ubuntu)** a real Linux system running inside Windows. This is where our code runs.
2. **Python**  the programming language the project is built in.
3. **Git**  the tool that downloads the code and tracks changes.
4. **VS Code**  the editor we'll write code in.
5. *(Optional)* a **free Gemini API key** for the chat assistant.

Don't worry about what each one does yet. Just follow the steps in order.


## 1. Install Linux (WSL) on Windows

WSL lets you run Linux inside Windows. Our whole project runs there.

1. Click the **Start** menu, type **PowerShell**, **right-click** it, and choose
   **Run as administrator**.
2. In the blue window that opens, type this and press **Enter**:

```powershell
   wsl --install
```

3. Wait for it to finish, then **restart your computer**.
4. After restarting, an **Ubuntu** window opens automatically and asks you to create a
   **username** and **password**.
   - Use a simple lowercase username (e.g. your first name).
   - **The password won't show as you type** — no dots, no stars, nothing. That's normal!
     Just type it and press Enter.

![Ubuntu](https://i.imgur.com/6fQKxwb.png)

> If Ubuntu doesn't open on its own, click **Start**, type **Ubuntu**, and open it.

✅ **You now have Linux.** This Ubuntu window is your **terminal**; the place you'll type commands.


## 2. Get comfortable with the terminal

The terminal feels strange at first, but you only need a handful of commands. Try these in
your Ubuntu window (type each, press Enter):

```bash
pwd        # print working directory — "where am I?"
ls         # list the files here
cd ..      # go up one folder
clear      # clean up the screen
```

That's genuinely most of what you'll use day to day.

📚 **Learn the basics properly (highly recommended):**
Work through the **"Learn the Shell"** lessons at **<https://linuxcommand.org/>**.
Even just the first few pages will make the whole course easier.

## 3. Install Python, Git, and tools

In your **Ubuntu terminal**, run these one at a time. (You'll be asked for the password you
created in Step 1; again, it won't show as you type.)

```bash
# Update Ubuntu's list of available software
sudo apt update && sudo apt upgrade -y

# Install Python, the virtual-environment tool, pip, and Git
sudo apt install -y python3 python3-venv python3-pip git
```

Check they installed:

```bash
python3 --version
git --version
```

You should see a version number for each (e.g. `Python 3.10.x`, `git version 2.x`).

✅ **Python and Git are ready.**


## 4. Set up Git and GitHub

**Git** tracks your code. **GitHub** is the website where the course code lives.

1. **Create a free GitHub account** at <https://github.com/> (if you don't have one).
2. Tell Git who you are (use the same email as your GitHub account):

```bash
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
```

That's all you need to **download** (clone) the course code. Later, if you want to **upload**
(push) your own work to GitHub, you'll create a **Personal Access Token** — GitHub explains
how [here](<https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens>).

📚 **Learn Git gently (pick one):**
- **<https://learngitbranching.js.org/>** — interactive and visual, the friendliest way to start.
- **<https://rogerdudler.github.io/git-guide/>** — "git, the simple guide" — one short page of the essentials.
- **<https://git-scm.com/book>** — the free *Pro Git* book, for when you want the full story.



## 5. Install VS Code (the editor)

VS Code is where we'll read and write code.

1. Download it from **<https://code.visualstudio.com/>** and install it (accept the defaults).
2. Open VS Code.
3. On the left, click the **Extensions** icon (four little squares), search for **WSL**,
   and install the extension called **WSL** (published by Microsoft). This lets VS Code work
   with your Ubuntu Linux.

![WSL Extension](https://i.imgur.com/234AOpk.jpeg)

To open a project in VS Code from Ubuntu, you'll `cd` into its folder and run:

```bash
code .
```

The first time, it installs a small helper automatically. When it works, you'll see a green
**`WSL: Ubuntu`** label in the **bottom-left** corner of VS Code — that means you're editing
your Linux files. 🎉


## 6. (Optional) Get a free Gemini API key

The listings site and analytics page work **without** a key. Only the **chat assistant**
needs one.

1. Go to **<https://aistudio.google.com/>** and sign in with a Google account.
2. Click **"Get API key"** and create one.
3. Keep it somewhere safe — you'll paste it into the project's `.env` file later
   (the README's Quick Start shows exactly where).

> **Important for the class:** the free quota is shared per Google **project**, not per key.
> Use **your own** Google account so you're not sharing limits with classmates.

## ✅ You're ready!

Your computer is now set up. Head to the **[README](README.md)** and follow the
**Quick Start** to download and run the project.

Quick recap of what you can now do:

- Open your **Ubuntu terminal** (Start → Ubuntu)
- Type commands like `ls`, `cd`, `pwd`
- Use **Git** to get code, **Python** to run it, **VS Code** to edit it

If anything above didn't work, don't panic — see [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).


## Appendix — Setting up on a Mac

Mac already has a Unix terminal, so it's a bit shorter. Open the **Terminal** app
(Cmd+Space, type "Terminal") and:

1. **Install Homebrew** (a package installer for Mac) from **<https://brew.sh/>** — paste the
   command on their homepage and follow the prompts.
2. **Install Python and Git:**

```bash
   brew install python git
```

3. **Configure Git:**

```bash
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
```

4. **Install VS Code** from <https://code.visualstudio.com/> (you do **not** need the WSL
   extension on a Mac).

Then follow the same learning resources above (linuxcommand.org for the shell, the Git guides
for Git) and continue with the **README** Quick Start.
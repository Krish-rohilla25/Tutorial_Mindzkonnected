"""
Publisher helpers — copy content to clipboard and open Reddit URLs.
Works on macOS via pbcopy and the open command.
"""

import subprocess
import webbrowser


def copy_to_clipboard(text):
    """Copy text to the system clipboard (macOS)."""
    try:
        process = subprocess.Popen(
            ["pbcopy"],
            stdin=subprocess.PIPE,
            env={"LANG": "en_US.UTF-8"},
        )
        process.communicate(text.encode("utf-8"))
        return True
    except Exception:
        return False


def open_reddit_url(url):
    """Open a Reddit URL in the default browser."""
    webbrowser.open(url)


def copy_and_open(content, reddit_url):
    """
    One-click publish helper:
    1. Copies the approved content to clipboard.
    2. Opens the Reddit URL in the browser.

    The user just needs to paste (Cmd+V) and submit.
    Returns True if clipboard copy succeeded.
    """
    success = copy_to_clipboard(content)
    open_reddit_url(reddit_url)
    return success


def get_reply_url(post_url):
    """
    Convert a Reddit post URL to one the user can reply on.
    Reddit post URLs already point to the comment page.
    """
    # Ensure it's a clean URL
    if "?" in post_url:
        post_url = post_url.split("?")[0]
    return post_url


def get_submit_url(subreddit):
    """Get the URL to submit a new post in a subreddit."""
    sub = subreddit.replace("r/", "").strip("/")
    return f"https://www.reddit.com/r/{sub}/submit"

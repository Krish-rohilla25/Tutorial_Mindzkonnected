import re

with open("reddit_marketing/app.py", "r") as f:
    content = f.read()

# Replace Comment score with Reddit Upvotes
content = content.replace('st.write(f"**Comment score:** {comment.get(\'score\', 0)}")',
                          'st.write(f"**Reddit Upvotes:** {comment.get(\'score\', 0)}")')

# Fix checkbox default to False
content = content.replace('st.session_state[select_key] = is_new',
                          'st.session_state[select_key] = False')

with open("reddit_marketing/app.py", "w") as f:
    f.write(content)

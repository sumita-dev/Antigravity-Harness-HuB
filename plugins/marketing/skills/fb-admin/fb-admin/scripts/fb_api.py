import sys
import requests
import json

PAGE_ID = "YOUR_FB_PAGE_ID"
TOKEN = "YOUR_PAGE_ACCESS_TOKEN_HERE"
BASE_URL = "https://graph.facebook.com/v20.0"

def post_message(message):
    url = f"{BASE_URL}/{PAGE_ID}/feed"
    payload = {'message': message, 'access_token': TOKEN}
    resp = requests.post(url, data=payload)
    print(json.dumps(resp.json(), indent=2))

def list_posts():
    url = f"{BASE_URL}/{PAGE_ID}/posts?access_token={TOKEN}"
    resp = requests.get(url)
    print(json.dumps(resp.json(), indent=2, ensure_ascii=False))

def list_comments(post_id):
    url = f"{BASE_URL}/{post_id}/comments?access_token={TOKEN}"
    resp = requests.get(url)
    print(json.dumps(resp.json(), indent=2, ensure_ascii=False))

def reply_comment(comment_id, message):
    url = f"{BASE_URL}/{comment_id}/comments"
    payload = {'message': message, 'access_token': TOKEN}
    resp = requests.post(url, data=payload)
    print(json.dumps(resp.json(), indent=2))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fb_api.py [post|list_posts|list_comments|reply_comment] [args...]")
        sys.exit(1)
    
    action = sys.argv[1]
    
    if action == "post" and len(sys.argv) >= 3:
        post_message(sys.argv[2])
    elif action == "list_posts":
        list_posts()
    elif action == "list_comments" and len(sys.argv) >= 3:
        list_comments(sys.argv[2])
    elif action == "reply_comment" and len(sys.argv) >= 4:
        reply_comment(sys.argv[2], sys.argv[3])
    else:
        print("Invalid action or missing arguments.")

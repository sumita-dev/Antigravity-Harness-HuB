import sys
import requests
import json
import datetime
import os

PAGE_ID = "YOUR_FB_PAGE_ID"
TOKEN = "YOUR_FB_PAGE_ACCESS_TOKEN"
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

def schedule_feed_post(image_path, caption, unix_time):
    photo_url = f"{BASE_URL}/{PAGE_ID}/photos"
    photo_payload = {"published": "false", "access_token": TOKEN}
    with open(image_path, "rb") as f:
        photo_resp = requests.post(photo_url, data=photo_payload, files={"source": f}).json()
    photo_id = photo_resp.get("id")
    if not photo_id:
        return {"error": "Failed to upload photo", "details": photo_resp}
    feed_url = f"{BASE_URL}/{PAGE_ID}/feed"
    feed_payload = {
        "message": caption,
        "published": "false",
        "scheduled_publish_time": str(unix_time),
        "attached_media": json.dumps([{"media_fbid": photo_id}]),
        "access_token": TOKEN
    }
    return requests.post(feed_url, data=feed_payload).json()

def list_scheduled():
    url = f"{BASE_URL}/{PAGE_ID}/scheduled_posts?fields=id,is_published,scheduled_publish_time,created_time,status_type&access_token={TOKEN}"
    resp = requests.get(url)
    data = resp.json().get('data', [])
    print(f"Total scheduled posts: {len(data)}")
    for p in data:
        print("ID:", p.get('id'), "Timestamp:", p.get('scheduled_publish_time'))

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
    elif action == "list_scheduled":
        list_scheduled()
    elif action == "schedule_json" and len(sys.argv) >= 3:
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            items = json.load(f)
        for item in items:
            dt = datetime.datetime.strptime(item["datetime_str"], "%Y-%m-%d %H:%M:%S")
            res = schedule_feed_post(item["image"], item["caption"], int(dt.timestamp()))
            print(f"Scheduled: {item.get('day', 'Post')} -> {res}")
    elif action == "list_comments" and len(sys.argv) >= 3:
        list_comments(sys.argv[2])
    elif action == "reply_comment" and len(sys.argv) >= 4:
        reply_comment(sys.argv[2], sys.argv[3])
    else:
        print("Invalid action or missing arguments.")

#!/usr/bin/env python3
"""Publish due items from queue.json to Instagram (Instagram API with Instagram Login).

Run every few minutes by GitHub Actions. Stdlib only.

  python3 publish.py            publish everything that is due and not yet posted
  python3 publish.py --check    create containers for every queued item WITHOUT publishing
                                (verifies media URLs and formats; unpublished containers expire)
  python3 publish.py --id X     publish item X now, ignoring its time

Needs env IG_ACCESS_TOKEN. Media is fetched by Instagram from MEDIA_BASE + path.
A file named PAUSED in this folder stops all publishing.
"""
import json, os, sys, time, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
API = "https://graph.instagram.com/v23.0"
MEDIA_BASE = os.environ.get("MEDIA_BASE", "https://founderlumory-sys.github.io/frontline-instagram/")
MAX_LATE = timedelta(hours=3)   # never publish something more than 3h after its slot
MAX_ATTEMPTS = 3
TOKEN = os.environ.get("IG_ACCESS_TOKEN", "").strip()


class ApiError(Exception):
    pass


def call(method, path, **params):
    params["access_token"] = TOKEN
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        req = urllib.request.Request(f"{API}/{path}?{data.decode()}")
    else:
        req = urllib.request.Request(f"{API}/{path}", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        err = json.load(e).get("error", {})
        # never echo the request URL: it contains the token
        raise ApiError(f"{err.get('type')} {err.get('code')}: {err.get('error_user_msg') or err.get('message')}") from None


def media_url(p):
    return MEDIA_BASE + urllib.parse.quote(p)


def wait_ready(container_id, timeout=300):
    deadline = time.time() + timeout
    while True:
        st = call("GET", container_id, fields="status_code,status")
        code = st.get("status_code")
        if code in ("FINISHED", "PUBLISHED"):
            return
        if code in ("ERROR", "EXPIRED"):
            raise ApiError(f"container {code}: {st.get('status')}")
        if time.time() > deadline:
            raise ApiError(f"container still {code} after {timeout}s")
        time.sleep(5)


def is_video(p):
    return p.lower().endswith((".mp4", ".mov"))


def create_container(user_id, item):
    kind, media, caption = item["type"], item["media"], item.get("caption", "")
    if kind == "CAROUSEL":
        children = []
        for p in media:
            key = "video_url" if is_video(p) else "image_url"
            extra = {"media_type": "VIDEO"} if is_video(p) else {}
            c = call("POST", f"{user_id}/media", is_carousel_item="true", **{key: media_url(p)}, **extra)["id"]
            wait_ready(c)
            children.append(c)
        cid = call("POST", f"{user_id}/media", media_type="CAROUSEL", children=",".join(children), caption=caption)["id"]
    elif kind == "REELS":
        cid = call("POST", f"{user_id}/media", media_type="REELS", video_url=media_url(media[0]),
                   caption=caption, share_to_feed="true")["id"]
    elif kind == "IMAGE":
        cid = call("POST", f"{user_id}/media", image_url=media_url(media[0]), caption=caption)["id"]
    elif kind == "STORY":
        key = "video_url" if is_video(media[0]) else "image_url"
        cid = call("POST", f"{user_id}/media", media_type="STORIES", **{key: media_url(media[0])})["id"]
    else:
        raise ValueError(f"unknown type {kind}")
    wait_ready(cid)
    return cid


def main():
    if not TOKEN:
        sys.exit("IG_ACCESS_TOKEN is not set")
    args = sys.argv[1:]
    check = "--check" in args
    only = args[args.index("--id") + 1] if "--id" in args else None
    if (HERE / "PAUSED").exists() and not check and not only:
        print("PAUSED file present: nothing published.")
        return

    queue = json.loads((HERE / "queue.json").read_text())
    state_file = HERE / "state.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    user_id = call("GET", "me", fields="user_id,username")["user_id"]
    now = datetime.now(timezone.utc)
    failed = False

    for item in sorted(queue, key=lambda i: i["publish_at"]):
        iid = item["id"]
        s = state.get(iid, {})
        if check:
            try:
                create_container(user_id, item)
                print(f"OK    {iid} {item['type']}")
            except ApiError as e:
                failed = True
                print(f"FAIL  {iid} {item['type']}: {e}")
            continue
        if s.get("media_id"):
            continue
        when = datetime.fromisoformat(item["publish_at"])
        if only:
            if iid != only:
                continue
        elif when > now:
            continue
        elif now - when > MAX_LATE:
            if not s.get("skipped"):
                state[iid] = {**s, "skipped": f"missed slot ({now:%Y-%m-%d %H:%M} UTC)"}
                print(f"SKIP  {iid}: more than {MAX_LATE} late")
            continue
        if s.get("attempts", 0) >= MAX_ATTEMPTS:
            continue
        try:
            cid = create_container(user_id, item)
            media_id = call("POST", f"{user_id}/media_publish", creation_id=cid)["id"]
            state[iid] = {"media_id": media_id, "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            print(f"POSTED {iid} {item['type']} → {media_id}")
        except ApiError as e:
            failed = True
            state[iid] = {**s, "attempts": s.get("attempts", 0) + 1, "last_error": str(e)}
            print(f"FAIL  {iid} (attempt {state[iid]['attempts']}): {e}")
        state_file.write_text(json.dumps(state, indent=2) + "\n")

    if not check:
        state_file.write_text(json.dumps(state, indent=2) + "\n")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()

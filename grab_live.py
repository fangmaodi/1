#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# grab_live.py - fetch live sports streams from xinzhibo and emit IPTV lists.
# API base: http://8.160.168.109/xinzhibo/api.php
#   lives:  ?action=lives&matchType=1|2   (1 football, 2 basketball)
#   room:   ?action=room&anchorId=XXX    (returns playAddr + stream_profiles)
# Play URLs carry time-limited auth_info tokens, so re-run to refresh.
# Output: txt (name,url per line, TVBox live format) and m3u.
# Usage:
#   python3 grab_live.py [--out-txt PATH] [--out-m3u PATH] [--verify|--no-verify]
#   [--all-lines|--first-line] [--quality hd|ori|ud|sd|ld]

import argparse
import json
import sys
import time
import urllib.request

BASE = "http://8.160.168.109/xinzhibo/api.php"
UA = "Mozilla/5.0 (Linux; Android 13; iQOO Z9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36"

SPORT_LABEL = {1: "足球", 2: "篮球"}
QUALITY_ORDER = ["hd_m3u8", "ori_m3u8", "ud_m3u8", "sd_m3u8", "ld_m3u8"]


def http_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def api(action, params):
    qs = "&".join(["action=" + action] + ["%s=%s" % (k, v) for k, v in params.items()])
    return http_json(BASE + "?" + qs)


def pick_m3u8(play_addr, quality):
    order = [quality + "_m3u8"] if quality else []
    for key in order + [k for k in QUALITY_ORDER if k not in order]:
        u = play_addr.get(key)
        if isinstance(u, str) and u.startswith("http"):
            return u, key
    return None, None


def verify_m3u8(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            head = r.read(512).decode("utf-8", "replace")
            return r.status == 200 and "#EXTM3U" in head
    except Exception:
        return False


def clean_name(s):
    return " ".join(str(s or "").split()).replace(",", "，")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-txt", default="")
    ap.add_argument("--out-m3u", default="")
    ap.add_argument("--quality", default="hd", choices=["hd", "ori", "ud", "sd", "ld"])
    ap.add_argument("--all-lines", action="store_true")
    ap.add_argument("--verify", dest="verify", action="store_true", default=True)
    ap.add_argument("--no-verify", dest="verify", action="store_false")
    args = ap.parse_args()

    channels = []
    total_matches = 0
    for mt in (1, 2):
        try:
            j = api("lives", {"matchType": mt})
        except Exception as e:
            print("lives matchType=%d failed: %s" % (mt, e), file=sys.stderr)
            continue
        matches = j.get("data") or []
        total_matches += len(matches)
        for m in matches:
            sport = SPORT_LABEL.get(m.get("matchType") or mt, "")
            title = clean_name(m.get("liveTitle") or "未命名")
            lines = m.get("lines") or []
            if not lines:
                continue
            use_lines = lines if args.all_lines else lines[:1]
            for ln in use_lines:
                anchor_id = ln.get("anchorId")
                nick = clean_name(ln.get("nickname") or "主播")
                if not anchor_id:
                    continue
                try:
                    rj = api("room", {"anchorId": anchor_id})
                except Exception as e:
                    print("room anchorId=%s failed: %s" % (anchor_id, e), file=sys.stderr)
                    continue
                data = (rj or {}).get("data") or {}
                play_addr = data.get("playAddr") or {}
                url, qkey = pick_m3u8(play_addr, args.quality)
                if not url:
                    print("no m3u8 for anchorId=%s (%s)" % (anchor_id, title), file=sys.stderr)
                    continue
                name = "【%s】%s|%s" % (sport, title, nick)
                channels.append((sport, name, url, qkey))
                time.sleep(0.2)

    ok = 0
    verified = {}
    if args.verify:
        for _g, name, url, _q in channels:
            good = verify_m3u8(url)
            verified[name] = good
            ok += 1 if good else 0
            print(("OK  " if good else "FAIL") + " " + name)
    else:
        ok = len(channels)

    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    if args.out_txt:
        with open(args.out_txt, "w", encoding="utf-8") as f:
            f.write("# xinzhibo live, updated %s, %d matches, %d channels\n" % (stamp, total_matches, len(channels)))
            for _g, name, url, _q in channels:
                if args.verify:
                    f.write("# %s [%s]\n" % (name, "OK" if verified.get(name) else "FAIL"))
                f.write("%s,%s\n" % (name, url))
    if args.out_m3u:
        with open(args.out_m3u, "w", encoding="utf-8") as f:
            f.write('#EXTM3U x-tvg-url=""\n')
            for g, name, url, _q in channels:
                f.write('#EXTINF:-1 group-title="%s",%s\n%s\n' % (g, name, url))

    print("matches: %d, channels: %d, verified OK: %d/%d" % (total_matches, len(channels), ok, len(channels)))
    return 0 if channels else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# grab_live.py - fetch live sports streams from 88zhibo and emit IPTV lists.
# Site: https://www.88zhibo.me/
#   list:   homepage HTML, server-rendered <li class="list-group-item group-game-item">
#           live ones carry a button with text "直播中"; each has data-id + /live/{id}/play
#   source: GET /live/{id}/source (Referer: play page)
#           -> {"data": "<6-char prefix><base64 JSON><2-char suffix>"}
#           -> JSON {links: [{url, name, shareLock}]} ; links may be null
#   lines:  "88player.top/m3u8.html?url=<urlencoded m3u8>" -> unwrap inner m3u8 (usable)
#           "play.sportsteam368.com/..." player pages -> Cloudflare-blocked here, skipped
# Play URLs may carry time-limited auth_key, so re-run to refresh.
# Output: txt (name,url per line, TVBox live format) and m3u.
# Usage:
#   python3 grab_live.py [--out-txt PATH] [--out-m3u PATH] [--verify|--no-verify]
#   [--all-lines|--first-line] [--quality hd|ori|ud|sd|ld]

import argparse
import base64
import json
import re
import sys
import time
import urllib.parse
import urllib.request

BASE = "https://www.88zhibo.me"
UA = "Mozilla/5.0 (Linux; Android 13; iQOO Z9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36"

BASKETBALL_LEAGUES = ("NBA", "CBA", "NCAA", "WNBA", "NBL", "韩篮", "澳篮", "欧篮", "篮")


def http_get(url, timeout=20, referer=None):
    headers = {"User-Agent": UA}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def decode_source(raw):
    data = raw.get("data") or ""
    for cand in (data[6:-2], data[6:]):
        try:
            obj = json.loads(base64.b64decode(cand).decode("utf-8"))
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return {}


def unwrap_link(url):
    if "88player.top/m3u8.html" in url and "url=" in url:
        inner = urllib.parse.unquote(url.split("url=", 1)[1])
        return inner if inner.startswith("http") and ".m3u8" in inner else None
    if ".m3u8" in url and url.startswith("http"):
        return url
    return None


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


def sport_of(league):
    for k in BASKETBALL_LEAGUES:
        if k in league:
            return "篮球"
    return "足球"


def parse_homepage(html):
    parts = html.split('<li class="list-group-item group-game-item')
    matches = []
    for it in parts[1:]:
        m = re.search(r"/live/(\d+)/play", it)
        if not m:
            continue
        if "直播中" not in it:
            continue
        league = re.search(r'class="game-type">([^<]+)<', it)
        if not league:
            league = re.search(r'<span class="center-block">([^<]{1,12})</span>', it)
        tm = re.search(r'category-game-time">\s*(\d{2}:\d{2})', it)
        if not tm:
            tm = re.search(r'game-time">(\d{2}:\d{2})', it)
        teams = re.findall(r'class="team-name"[^>]*>\s*([^<]+)', it)
        teams = [t.strip() for t in teams if t.strip()]
        if len(teams) < 2:
            continue
        matches.append({
            "id": m.group(1),
            "league": clean_name(league.group(1)) if league else "",
            "time": tm.group(1) if tm else "",
            "home": teams[0],
            "away": teams[1],
        })
    return matches


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-txt", default="")
    ap.add_argument("--out-m3u", default="")
    ap.add_argument("--quality", default="hd", choices=["hd", "ori", "ud", "sd", "ld"])
    ap.add_argument("--all-lines", action="store_true")
    ap.add_argument("--verify", dest="verify", action="store_true", default=True)
    ap.add_argument("--no-verify", dest="verify", action="store_false")
    args = ap.parse_args()

    try:
        html = http_get(BASE + "/").decode("utf-8", "replace")
    except Exception as e:
        print("homepage failed: %s" % e, file=sys.stderr)
        return 1
    matches = parse_homepage(html)
    print("live matches on homepage: %d" % len(matches))

    channels = []
    skipped_steam = 0
    for m in matches:
        mid = m["id"]
        sport = sport_of(m["league"])
        title = clean_name("%s %s vs %s" % (m["league"], m["home"], m["away"]))
        try:
            raw = json.loads(http_get(
                BASE + "/live/%s/source" % mid,
                referer=BASE + "/live/%s/play" % mid).decode("utf-8", "replace"))
        except Exception as e:
            print("source id=%s failed: %s" % (mid, e), file=sys.stderr)
            continue
        obj = decode_source(raw)
        links = obj.get("links") or []
        if not links:
            print("no lines id=%s (%s)" % (mid, title), file=sys.stderr)
            continue
        cands = []
        for ln in links:
            url = ln.get("url") or ""
            name = clean_name(ln.get("name") or "线路")
            if "sportsteam368.com" in url:
                skipped_steam += 1
                continue
            inner = unwrap_link(url)
            if inner:
                cands.append((name, inner))
        if not cands:
            print("no usable m3u8 id=%s (%s)" % (mid, title), file=sys.stderr)
            continue
        use = cands if args.all_lines else cands[:1]
        for lname, url in use:
            name = "【%s】%s|%s" % (sport, title, lname)
            channels.append((sport, name, url))
        time.sleep(0.2)

    ok = 0
    verified = {}
    if args.verify:
        for _g, name, url in channels:
            good = verify_m3u8(url)
            verified[url] = good
            ok += 1 if good else 0
            print(("OK  " if good else "FAIL") + " " + name)
    else:
        ok = len(channels)

    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    if args.verify:
        keep = [(g, n, u) for g, n, u in channels if verified.get(u)]
    else:
        keep = list(channels)
    if args.out_txt:
        with open(args.out_txt, "w", encoding="utf-8") as f:
            f.write("# 88zhibo live, updated %s, %d matches, %d channels\n" % (stamp, len(matches), len(keep)))
            for _g, name, url in keep:
                f.write("%s,%s\n" % (name, url))
    if args.out_m3u:
        with open(args.out_m3u, "w", encoding="utf-8") as f:
            f.write('#EXTM3U x-tvg-url=""\n')
            for g, name, url in keep:
                f.write('#EXTINF:-1 group-title="%s",%s\n%s\n' % (g, name, url))

    print("matches: %d, channels: %d, verified OK: %d/%d, steam368 skipped: %d"
          % (len(matches), len(channels), ok, len(channels), skipped_steam))
    return 0 if channels else 1


if __name__ == "__main__":
    sys.exit(main())

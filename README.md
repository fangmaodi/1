# IPTV 自动更新脚本（buyu/zb 同款）

这是从 Gitee 公开仓库 `g1753462733/zb` 拉下来的原版脚本，没改过。
它就是每 15 分钟自动换 IP、生成 IPTV.txt 的那套东西。

## 它是怎么工作的

`fofa_fetch.py` 分三步：

1. **找 IP**：去 FOFA（fofa.info）搜 `"udpxy" && country="CN"`，把搜到的
   代理服务器 IP:端口 抓下来，用 ip-api.com 查每个 IP 是哪个省、哪个运营商
   （电信/联通/移动），写进 `ip/<省份><运营商>.txt`。
   注意：这里用的是 FOFA 网页搜索，不是 FOFA API，**不用 key**，直接抓网页。
2. **拼地址**（每 10 次运行一次）：把 `ip/` 里的 IP 和 `rtp/` 里的频道组播地址
   （比如 `CCTV1,rtp://225.1.8.1:8008`）拼成 `CCTV1,http://IP:端口/rtp/225.1.8.1:8008`，
   写进 `zubo.txt`。
3. **测速筛选**（每 10 次运行一次）：用 ffprobe 测每个 IP 能不能播（拿 CCTV1 当代表），
   能播的才留下来，按央视/卫视/数字频道分类，生成 `IPTV.txt`。
   同时把可用的 IP 写回 `ip/` 目录（覆盖掉不能播的）。

`.github/workflows/ip.yml` 是 GitHub Actions 定时任务：
每 15 分钟跑一次，装 Python + requests + ffmpeg，运行 `fofa_fetch.py`，
然后自动提交 `计数.txt`、`ip/*.txt`、`IPTV.txt` 并推送。

## 文件说明

- `fofa_fetch.py`：主脚本（498 行）
- `.github/workflows/ip.yml`：GitHub Actions 定时任务配置
- `rtp/`：各省运营商的频道组播地址（CCTV1 对应哪个 rtp 地址等），脚本靠它拼播放地址
- `ip/`：已收集到的 IP 列表（按省份+运营商分文件），第一次跑可以是空的
- `计数.txt`：运行次数计数，每 10 次才做一次拼地址+测速（省时间）
- `IPTV_example.txt`：脚本生成出来的 IPTV.txt 样子（2026-11-03 的版本）

## 怎么用（在 GitHub 上跑）

1. 在 GitHub 上新建一个公开仓库，把这个文件夹里的东西全传上去。
2. 打开仓库的 Settings → Actions → General，把 Workflow permissions 改成
   **Read and write permissions**（不然机器人推不上去）。
3. Actions 就会每 15 分钟自动跑一次，`IPTV.txt` 会自动更新。
   也可以点进 Actions → FOFA IP → Run workflow 手动跑一次。
4. 生成的 `IPTV.txt` 地址就是：
   `https://raw.githubusercontent.com/<你的用户名>/<仓库名>/main/IPTV.txt`
   把这个地址当直播源加进 TVBox，每次打开都会拉最新的。

## 注意

- 脚本里有个小 bug：`first_stage()` 里用了 `socket.gethostbyname` 但没 `import socket`。
  只有搜到域名（不是 IP）时才会触发，平时搜到的都是 IP，不影响。
  想修的话在文件开头加一行 `import socket` 就行。
- FOFA 网页搜索有访问频率限制，如果某次抓不到 IP，等下一次跑就行。
- 每次只测 CCTV1 一个频道当代表，某个 IP 只要 CCTV1 能播就认为全台能播。
  想更严的话可以改 `detect_ip` 去测更多频道。
- 仓库原作者：Gitee `buyu`（@g1753462733），本包只是把他的公开仓库原样拉下来。

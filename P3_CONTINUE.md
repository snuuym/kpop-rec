# P3 续作交接文档（音频特征推荐）

> 明天读这份文档直接继续。最后更新：2026-06-27 凌晨。

## TL;DR（一句话）

P3 已上线但**特征覆盖只建到一半（520/1264）**，因为 Spotify 把我们限流了 18 小时。
**等限流解除后，重跑一次 `build_features.py`（带新 secret）即可把覆盖率补到约 1100。**

---

## 现在的状态

### 已完成并推送到 GitHub（commit `502f7e9`）
- **P3 推荐逻辑**（`kpop-mp3-player.html`）：种子歌在库内能匹配到时，用加权欧氏距离做音频特征最近邻推荐；否则回退标签推荐。访客无需登录 Spotify。
- **`build_features.py`**：用 Spotify 搜索解析 track ID → ReccoBeats 取音频特征，写进 `songs.json`。可断点续跑，带限流保护。
- **`songs.json`**：520/1264 首已有 `features` 字段，其余回退标签推荐。库总量仍是完整 1264 首。

### 关键事实
- **库没有缩水**，1264 首全部可推荐。520 只是"有音频特征、走精准相似度"的那部分。
- Spotify 的 `audio-features` 接口已于 2024-11-27 停用，本项目改用 **ReccoBeats**（免费、无需鉴权、字段与 Spotify 一致）替代。
- ReccoBeats 只能按 Spotify track ID 查，所以建库仍需 Spotify 搜索来拿 ID（这是唯一会触发限流的步骤）。

---

## 唯一的剩余任务：续跑建库脚本

### 何时可以跑
Spotify 限流（Retry-After ≈ 65400 秒 ≈ 18 小时）从 **2026-06-26 约 23:22** 开始，
即 **2026-06-27 约 17:30 之后**应已解除。

### 怎么跑
> ⚠️ 用**重新生成后的新 secret**（旧的 `7313...` 已作废）。

在 Claude Code 输入框里贴（开头 `!` 让命令在本会话直接跑）：

```
! cd /Users/mcrs/python/kpop-rec && SPOTIFY_CLIENT_SECRET=新的secret python3 build_features.py
```

脚本会：
1. **跳过已缓存的 600 首**，从第 601 首接着解析（`features_cache.json` 记录了进度）。
2. 剩余约 664 首走 Spotify 搜索（已放慢到 0.35 秒/次，并对长 Retry-After 自动停止而非死等）。
3. 自动接 ReccoBeats 取特征，合并进 `songs.json`。

### 预期结果
- 覆盖率从 520 → **约 1100（85–90%）**。
  - 计算：1264 × Spotify 命中率 ~99% × ReccoBeats 覆盖 ~88% ≈ 1100。
  - 剩约 160 首是 ReccoBeats 数据库里确实没有的，永远走标签，属正常。
- 若**又被限流**：脚本会优雅停止并提示还剩多少首，过几小时再跑一次即可（已缓存的不重复）。

---

## 跑完后的收尾

1. **验证覆盖率**：
   ```
   python3 -c "import json; d=json.load(open('songs.json')); print(sum(1 for s in d if s.get('features')),'/',len(d))"
   ```
2. **冒烟测试**（确认最近邻合理）：见 git 历史里那段 Python 片段，或让 Claude 重跑。
3. **提交推送**：
   ```
   git add songs.json && git commit -m "Expand audio-feature coverage to ~XX%" && git push
   ```
   （只有 `songs.json` 会变；`features_cache.json` 已 gitignore。）

---

## 注意事项 / 坑

- **不要并发或快速连发 Spotify 搜索** —— 这就是被关 18 小时的原因。脚本已限速，别去改快。
- `features_cache.json`（建库进度缓存）和 `songs.json.bak` 已在 `.gitignore`，不会进库，也不含 secret。
- secret 只在 `build_features.py` 运行时从环境变量读，**绝不写进任何文件、绝不提交**。
- 网页用的是 PKCE 登录，**不依赖 client secret**，所以换 secret 不影响网站运行。

---

## P4：搜索自动扩库（已完成，2026-06-27）

### 做了什么
搜索一首**不在库里**的种子歌时，现在会自动把它写回 `songs.json`，丰富以后的歌单生成。
- 新增 `server.py`（本地 Flask 服务器）：在 `http://127.0.0.1:5000` 提供网页和 `songs.json`，
  并暴露唯一写接口 `POST /library/add`（白名单校验 → 按 `歌手::歌名` 去重 → 备份 `songs.json.bak`
  → 临时文件+原子替换写入，只绑 `127.0.0.1`）。
- `kpop-mp3-player.html`：不在库的种子歌自动入库（`addSeedToLibrary` / `classifyGenres`），
  先进内存立即生效，再 POST 持久化；服务器没开也不报错（退化成本次会话内存生效）。
  种子歌不再把自己推荐进歌单。

### 新的启动方式（重要，不再双击文件）
```
! cd /Users/mcrs/python/kpop-rec && python3 server.py
```
然后浏览器开 **http://127.0.0.1:5000**。Ctrl-C 停。
> 注意 `python3`（→ /usr/local/bin/python3.13）和 `pip3`（→ homebrew）是两个不同的 Python。
> 装依赖要用 `python3 -m pip install flask`，否则装错解释器。

### 与建库的衔接
搜进来的新歌**当场没有音频特征，只有标签**。下次跑 `build_features.py` 会自动拾取这些新增的歌补特征。
即：平时搜歌悄悄扩库，偶尔跑一次建库脚本统一补特征。

### Spotify redirect URI
- `SPOTIFY_REDIRECT_URI` 已改为**动态**（`location.origin + pathname`），GitHub Pages 和本地都自动适配。
- GitHub 那个 URI **保留不要删**。若想在本地登录 Spotify 播放，去开发者后台**再加**
  `http://127.0.0.1:5000/kpop-mp3-player.html`（Spotify 只允许 loopback `127.0.0.1`，不接受 `localhost`）。
- 只用推荐/扩库则无需登录，可忽略这步。

---

## 相关文件
- `kpop-mp3-player.html` — 单文件应用（`buildPlaylist` / `featureDist` / `findInLibrary` / `addSeedToLibrary` 在此）
- `server.py` — 本地服务器 + 扩库写接口（P4 新增）
- `build_features.py` — 特征建库脚本（P3 新增）
- `buildlib.py` — 歌曲库生成脚本（决定总量 1264，与特征无关）
- `RECOMMENDATION_FIX.md` — 原始修复计划（P0/P1/P2 已完成，P3 即本文档）

# 推荐系统修复计划

## 项目现状

所有五个 Phase 已实现完毕（详见 `KPOP_PLAYER_PROMPT.md`）。  
当前唯一需要改进的模块是**推荐引擎**，问题分三层，彼此独立，可按顺序修复。

工作文件：`kpop-mp3-player.html`（单文件，所有逻辑在此）、`songs.json`（歌曲库）、`build_library.py`（生成库的脚本）。

---

## 问题一：代码 Bug（必须修，5 分钟）

### 1a. `song.tag` 字段名错误

`songs.json` 的 schema 是：
```json
{ "tags": ["Dance pop", "Girl group"], ... }
```

但 `kpop-mp3-player.html` 里的 `buildPlaylist()` 读的是 `song.tag`（不存在的单数字段），导致**所有歌曲得分永远是 1**，推荐完全随机。

**需要修改的位置（`kpop-mp3-player.html`）：**

```js
// ❌ 现在（buildPlaylist 内，约 400 行附近）
score: matchedGenres.has(song.tag) ? 2 : 1

// ✅ 改为：按 tags 数组与 matchedGenres 的交集数量计分
score: song.tags.filter(t => matchedGenres.has(t)).length + 1
```

```js
// ❌ 现在（updateScreen 内）
document.getElementById('track-tag').textContent = t.tag || 'K-pop';

// ✅ 改为显示第一个标签
document.getElementById('track-tag').textContent = (t.tags && t.tags[0]) || 'K-pop';
```

```js
// ❌ 现在（buildPlaylist 内，tagCounts 用于多样性控制）
tagCounts[song.tag] = (tagCounts[song.tag] || 0) + 1;
if (tagCounts[song.tag] <= maxPerTag || result.length < 10)

// ✅ 改为用第一个 tag
const primaryTag = song.tags[0] || 'K-pop';
tagCounts[primaryTag] = (tagCounts[primaryTag] || 0) + 1;
if (tagCounts[primaryTag] <= maxPerTag || result.length < 10)
```

### 1b. TAG_MAP 标签名与 songs.json 不一致

`TAG_MAP` 把 Last.fm 原始标签映射成的目标标签，和 `songs.json` 里实际存储的标签名不匹配：

| TAG_MAP 输出（现在） | songs.json 实际标签 |
|---------------------|-------------------|
| `K-R&B` | `R&B` |
| `K-ballad` | `Ballad` |
| `K-hip-hop` | `Hip-hop` |
| `K-rock` | `Rock` |
| `K-OST` | `OST` |
| `K-indie` | `Indie` |
| `Boy band` | `Boy group` |

目前只有 4 个标签两边一致：`Bubblegum pop`、`Dance pop`、`Dream pop`、`Girl group`。

**需要修改的位置（`kpop-mp3-player.html`，`TAG_MAP` 对象，约 365 行）：**

```js
// ❌ 现在
const TAG_MAP = {
  "k-pop":         "K-pop",
  "kpop":          "K-pop",
  "korean pop":    "K-pop",
  "k-indie":       "K-indie",       // 改
  "k-ballad":      "K-ballad",      // 改
  "k-hip-hop":     "K-hip-hop",     // 改
  "hip hop":       "K-hip-hop",     // 改
  "k-r&b":         "K-R&B",         // 改
  "r&b":           "K-R&B",         // 改
  "k-rock":        "K-rock",        // 改
  "korean ost":    "K-OST",         // 改
  "ost":           "K-OST",         // 改
  "girl group":    "Girl group",    // OK
  "boy band":      "Boy band",      // 改
  "bubblegum pop": "Bubblegum pop", // OK
  "dance pop":     "Dance pop",     // OK
  "dream pop":     "Dream pop",     // OK
};

// ✅ 改为（与 songs.json taxonomy 对齐）
const TAG_MAP = {
  "k-pop":         "K-pop",
  "kpop":          "K-pop",
  "korean pop":    "K-pop",
  "k-indie":       "Indie",
  "indie":         "Indie",
  "ballad":        "Ballad",
  "k-ballad":      "Ballad",
  "hip hop":       "Hip-hop",
  "hip-hop":       "Hip-hop",
  "k-hip-hop":     "Hip-hop",
  "rap":           "Hip-hop",
  "r&b":           "R&B",
  "k-r&b":         "R&B",
  "soul":          "R&B",
  "rock":          "Rock",
  "k-rock":        "Rock",
  "korean ost":    "OST",
  "ost":           "OST",
  "soundtrack":    "OST",
  "electronic":    "Electronic",
  "electropop":    "Electronic",
  "synth-pop":     "Electronic",
  "dance":         "Dance",
  "girl group":    "Girl group",
  "girl band":     "Girl group",
  "boy band":      "Boy group",
  "boy group":     "Boy group",
  "bubblegum pop": "Bubblegum pop",
  "bubblegum":     "Bubblegum pop",
  "dance pop":     "Dance pop",
  "dream pop":     "Dream pop",
  "j-pop":         "K-pop",        // 偶尔误标，归入通用池
};
```

同时把 `matchedGenres.add("K-pop")` fallback 改为 `matchedGenres.add("Ballad")`（因为 87% 的库曲目是 Ballad，这能保证 fallback 时歌单有足够曲目）：

```js
// buildPlaylist 内
// ❌ matchedGenres.add("K-pop");   // songs.json 里没有这个标签
// ✅
if (matchedGenres.size === 0) matchedGenres.add("Ballad");
```

---

## 问题二：songs.json 数据质量（根本原因，需重建库）

### 现状

```
Ballad:    1110 首（87.8%）
Hip-hop:     44 首
Dance pop:   34 首
R&B:         23 首
Electronic:  18 首
Dance:       16 首
其他:        19 首
```

1110 首被标为 Ballad 是因为 `build_library.py` 从 Last.fm 拉取 per-track tags 时，大量 K-pop 曲目只有 `k-pop`、`kpop`、`pop` 等根标签，没有细分流派。分类器匹配不到细分标签时，第一个能宽泛匹配上的往往是 Ballad（`k-ballad` 或 `ballad` 在 Last.fm 上出现频率较高）。

### 修复方向（`build_library.py`）

需要扩宽分类逻辑，增加以下规则（按优先级顺序检查）：

**规则 1：从 `all_tags` 里检测艺人/组合类型**
```python
GROUP_TYPE_KEYWORDS = {
    "girl group": ["girl group", "girl band", "girlgroup", "female group"],
    "boy group":  ["boy band", "boy group", "boyband", "male group"],
    "solo":       ["solo", "soloist"],
}
```

**规则 2：OST 检测（曲名/标签）**
```python
OST_KEYWORDS = ["ost", "soundtrack", "original soundtrack", "drama ost"]
# 如果 track title 包含 "(ost)" 或 "[ost]" 也应检测
```

**规则 3：扩大各流派的匹配关键词**
```python
TAG_TAXONOMY = {
    "Dance pop":     ["dance pop", "dancepop", "k-pop dance", "dance"],
    "Electronic":    ["electronic", "electropop", "synth-pop", "synthpop", "edm", "electronica"],
    "Hip-hop":       ["hip hop", "hip-hop", "rap", "k-hip-hop", "korean hip hop", "hiphop"],
    "R&B":           ["r&b", "k-r&b", "rnb", "neo soul", "soul"],
    "Ballad":        ["ballad", "k-ballad", "korean ballad", "slow ballad"],
    "Bubblegum pop": ["bubblegum pop", "bubblegum", "cute", "aegyo"],
    "Rock":          ["rock", "k-rock", "korean rock", "indie rock", "punk"],
    "Indie":         ["indie", "k-indie", "indie pop", "lo-fi"],
    "Dream pop":     ["dream pop", "dreampop", "shoegaze", "ethereal"],
    "OST":           ["ost", "soundtrack", "original soundtrack"],
    "Girl group":    ["girl group", "girl band", "girlgroup"],
    "Boy group":     ["boy band", "boy group", "boyband"],
    "Dance":         ["dance", "choreography"],
}
```

**规则 4：多标签保留（现在只保留 1 个）**

`songs.json` 里只有 42/1264 首有多个标签。建议 `build_library.py` 最多保留 3 个标签，这样推荐引擎的交集计分才有意义。

**重建步骤：**
```bash
pip install requests
python3 build_library.py   # 约 8 分钟
```

---

## 问题三：推荐算法本身（可选升级）

即使修完以上两个问题，推荐准确度仍受限于 Last.fm 标签质量。更根本的升级：

### 方案 A：用 all_tags 做直接 tag 相似度
不经过分类器，直接把搜索曲目的原始 Last.fm tags 和库中每首歌的 `all_tags` 取交集，交集越大得分越高。

- **优点**：绕开分类器误差，更细粒度
- **缺点**：`all_tags` 目前只有 313/1264 首有数据（需要在 `build_library.py` 里确保全量获取）

代码改动（`kpop-mp3-player.html`，`buildPlaylist` 函数）：
```js
// 在现有按 tags 分类匹配之上，额外加一层 all_tags 原始 tag 匹配
const rawTagScore = song.all_tags
  ? rawSearchTags.filter(t => song.all_tags.includes(t)).length
  : 0;
song.score = classifiedScore + rawTagScore * 0.5;
```
（需要把 Last.fm 返回的原始 `tags` 数组一并传入 `buildPlaylist`）

### 方案 B：Spotify 音频特征（最准确）
用 `GET /v1/audio-features/{id}` 获取 danceability、energy、valence、tempo、acousticness，用欧氏距离替代标签匹配做相似度计算。

- **优点**：完全客观，不依赖 Last.fm 标签质量
- **缺点**：需要为库中每首歌先解析 Spotify URI，再批量获取 audio features（`/v1/audio-features?ids=...` 每次最多 100 首），结果缓存到本地 JSON
- **工作量**：约需一个新的 `build_features.py` 脚本 + `buildPlaylist` 逻辑重写

---

## 实施顺序建议

| 优先级 | 任务 | 文件 | 预估时间 |
|--------|------|------|---------|
| P0 | 修 `song.tag` → `song.tags` + 修 fallback | `kpop-mp3-player.html` | 5 min |
| P0 | 修 TAG_MAP 标签名对齐 | `kpop-mp3-player.html` | 5 min |
| P1 | 扩大 `build_library.py` 分类关键词 + 保留多标签 | `build_library.py` | 30 min |
| P1 | 重建 `songs.json` | 运行脚本 | 8 min |
| P2 | 加入 `all_tags` 原始 tag 匹配层 | `kpop-mp3-player.html` | 20 min |
| P3 | Spotify 音频特征推荐 | 新脚本 + HTML | 2~3 h |

P0 修完后推荐就不再是完全随机的了。P1 修完后库的质量大幅提升，推荐效果应该有明显改善。

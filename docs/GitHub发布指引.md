# GitHub 发布授权指引

本文说明如何为本项目创建访问令牌、以及需要授予哪些权限。
**照着做即可，全程约 3 分钟。**

---

## 一、为什么不能用密码

GitHub 自 **2021-08-13** 起已完全移除密码认证（Git operations over HTTPS
require a token）。用账号密码推送**必然失败**，且违反 GitHub 服务条款。

因此需要的是一枚 **Personal Access Token（PAT）**——它是一串可随时撤销的
临时凭据，权限可精确限定，泄露后立即失效，比密码安全得多。

---

## 二、获取 Token（推荐 Fine-grained）

### 步骤

1. 登录 GitHub，点击右上角头像 → **Settings**
2. 左侧最下方 → **Developer settings**
3. **Personal access tokens** → **Fine-grained tokens** → **Generate new token**
4. 填写：

| 字段 | 填写内容 |
|---|---|
| **Token name** | `LanPulse-Publisher` |
| **Expiration** | `7 days`（发布完就可以删，不需要长期） |
| **Resource owner** | 你自己的账号 |
| **Repository access** | 选 **All repositories**（见下方说明） |

> **为什么推荐 All repositories 而不是 Only select repositories：**
> 本脚本要**新建**一个仓库。新建的仓库在你勾选列表时还不存在，
> 无法预先选中，因此运行时会报 403。
> All repositories 只授权给已有和将来创建的仓库，仍然只作用于你自己的账号，
> 不会碰别人的仓库。用完立即删除即可。

5. 展开 **Repository permissions**，勾选这三项：

| 权限 | 设为 | 用途 |
|---|---|---|
| **Administration** | Read and write | **创建仓库**（缺它无法建仓） |
| **Contents** | Read and write | 推送代码、创建 Release、上传安装包 |
| **Workflows** | Read and write | 推送 `.github/workflows/release.yml` |

> **Workflows 为什么必须给：** 仓库里有 GitHub Actions 工作流文件。
> 缺少该权限时 `git push` 会被拒绝，错误信息会明确提到 `workflow`。

6. **不要**勾选任何 Account permissions（不需要）
7. 点 **Generate token**
8. **立刻复制**开头为 `github_pat_` 的字符串

> ⚠️ 这串 token **只显示一次**，关掉页面就再也看不到。丢了只能重新生成。

### 备选：Classic Token

如果 fine-grained 页面打不开或报错，可用经典版：

1. Settings → Developer settings → **Personal access tokens** → **Tokens (classic)**
2. Generate new token (classic)
3. Expiration 选 7 days
4. 勾选两个 scope：

```
☑ repo        （完整仓库读写，含创建仓库）
☑ workflow    （推送 Actions 工作流文件）
```

5. 生成后复制 `ghp_` 开头的字符串

---

## 三、把 Token 交给我

### 方式 A：你自己在 PowerShell 里设置（推荐）

在项目目录打开 PowerShell，执行：

```powershell
$env:GITHUB_TOKEN = "github_pat_粘贴你的token"
```

然后告诉我「已设置」，我来执行发布。
这样 token **不会出现在聊天记录里**。

### 方式 B：直接贴给我

你可以在对话里直接给我 token。我的处理方式：

- 只用于这一次 API 调用
- 不写入任何文件、不写进 `.git/config`、不写进日志
- 发布完成后建议你立即到 GitHub 页面 **Revoke** 该 token

### 方式 C：授权范围更小的替代方案

如果你不放心给我建仓库的权限，可以：

1. 你自己在 GitHub 网页上建一个空仓库（**不要勾选** README / .gitignore / license）
2. 给我一个**只有 Contents + Workflows** 的 token
3. 我跳过建仓步骤，直接推送并发布 Release

---

## 四、我会做什么（精确清单）

脚本 `tools/publish_github.py` 会依次执行：

| 步骤 | API / 操作 | 需要权限 |
|---|---|---|
| 1 | `GET /user` 校验 token、读取你的用户名 | 无（任何 token 都行） |
| 2 | `POST /user/repos` 创建仓库 `LanPulse` | Administration: R/W |
| 3 | 本地把 README 里的 `{OWNER}` `{REPO}` 替换成真实值 | 无 |
| 4 | `git push` 推送 133 个文件到 `main` | Contents: R/W + Workflows: R/W |
| 5 | `POST /repos/{owner}/{repo}/releases` 创建 `v1.0.0` | Contents: R/W |
| 6 | 上传 `LanPulse-1.0.0-Setup.exe`（31.8 MB） | Contents: R/W |
| 7 | 上传 `LanPulse-1.0.0-win64-portable.zip`（44.1 MB） | Contents: R/W |
| 8 | 上传 `SHA256SUMS.txt` | Contents: R/W |

**不会做的事：**

- ❌ 不删除任何已有仓库
- ❌ 不修改你账号下的其它仓库
- ❌ 不添加协作者、不改账号设置
- ❌ 不读取你的私有仓库内容（脚本只操作 LanPulse 一个仓库）
- ❌ token 不写进磁盘（推送时用一次性凭据，push 完立刻从 remote 摘掉）

---

## 五、执行方式

### 先预检（不需要 token，只检查产物齐全）

```powershell
cd D:\Documents\deepseek-harness\default-workspace\netpulse
.\.venv\Scripts\python.exe tools\publish_github.py --dry-run
```

### 正式发布

```powershell
$env:GITHUB_TOKEN = "你的token"
.\.venv\Scripts\python.exe tools\publish_github.py
```

### 其他选项

```powershell
# 仓库已建好，只想更新代码和 Release
.\.venv\Scripts\python.exe tools\publish_github.py --skip-repo

# 用私有仓库（发布后再手动改公开）
.\.venv\Scripts\python.exe tools\publish_github.py --private

# 换仓库名
.\.venv\Scripts\python.exe tools\publish_github.py --repo MyNetTool
```

---

## 六、常见错误对照

| 错误 | 原因 | 解决 |
|---|---|---|
| `403 Resource not accessible by personal access token` | 建仓权限不足 | 加 Administration: R/W（fine-grained）或 repo scope（classic） |
| `refusing to allow a Personal Access Token to create or update workflow` | 缺 Workflows 权限 | 加 Workflows: R/W |
| `422 Repository creation failed` | 仓库名已被占用 | 换 `--repo` 名称 |
| `401 Bad credentials` | token 过期或复制不全 | 重新生成 |
| `404` 建仓后立刻访问 | token 的 Resource owner 选错了组织 | 确认 Resource owner 是目标账号 |

---

## 七、发布完成后

1. 到 https://github.com/settings/tokens 找到 `LanPulse-Publisher`
2. 点 **Revoke**（或 Delete）
3. 确认仓库页面的徽章能正常显示（shields.io 需要几秒到几分钟缓存）

> 建议**务必执行第 2 步**。虽然设置了 7 天过期，但主动撤销更稳妥。

---

## 八、如果你不想用脚本

也可以完全手动，步骤是：

```powershell
cd D:\Documents\deepseek-harness\default-workspace\netpulse

# 1. 在 GitHub 网页上建空仓库（不要勾 README/.gitignore/license）
# 2. 替换 README 占位符（把 your-name 换成你的用户名）
(Get-Content README.md -Raw) -replace '\{OWNER\}','your-name' -replace '\{REPO\}','LanPulse' | Set-Content README.md -Encoding utf8
(Get-Content README_EN.md -Raw) -replace '\{OWNER\}','your-name' -replace '\{REPO\}','LanPulse' | Set-Content README_EN.md -Encoding utf8

# 3. 提交并推送
git add -A
git -c user.name="You" -c user.email="you@example.com" commit -m "chore: set owner"
git remote add origin https://github.com/your-name/LanPulse.git
git push -u origin main

# 4. 网页上 Create a new release，tag 填 v1.0.0
#    上传 release/ 下的两个安装包
```

---

## 附：当前待发布内容

| 项目 | 状态 |
|---|---|
| 已提交文件 | 133 个 |
| 安装包 | `LanPulse-1.0.0-Setup.exe` 31.80 MB |
| 绿色包 | `LanPulse-1.0.0-win64-portable.zip` 44.14 MB |
| 校验和 | `SHA256SUMS.txt` |
| 目标 tag | `v1.0.0` |
| 分支 | `main` |

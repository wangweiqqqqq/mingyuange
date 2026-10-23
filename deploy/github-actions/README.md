# 明远阁 · 云端部署包（GitHub Actions，免费）

## 这套东西解决什么
把每天的通知搬到云端跑，**不依赖你的电脑开着**。GitHub 免费额度足够（私有仓库每月 2000 分钟，这个用量每天不到 10 分钟）。

## 一次性配置（约 10 分钟）

### 1. 建仓库
1. 打开 github.com，注册/登录
2. 右上角 + → New repository
3. 名字随便起，比如 `mingyuan`，选 **Private**，点 Create

### 2. 上传文件
最简单的方式：在这个仓库页面点 **uploading an existing file**，把本文件夹 `repo` 里的**全部内容**拖进去（包括 `.github` 这个隐藏文件夹，它里面有定时任务配置）。
> 注意：`.github` 文件夹必须一起上传，否则定时任务不会生效。

### 3. 配置邮箱授权码
1. 进入仓库 → Settings → Secrets and variables → Actions
2. 点 **New repository secret**
3. Name 填 `MAIL_PASS`，Secret 填你的 QQ 邮箱 16 位授权码
4. 保存

### 4. 确认时区
工作流里已经写死 `TZ=Asia/Shanghai`，cron 时间按 UTC 换算：
- 盘前简报：UTC `30 0` = 北京 **08:30**
- 收盘总结：UTC `5 7` = 北京 **15:05**
- 盘中巡检：UTC `*/10 1-3,5-6` = 北京 **09:30–11:30 / 13:00–15:00，每 10 分钟**

### 5. 手动跑一次验证
仓库 → Actions → 选「明远阁 · 盘前简报」→ Run workflow。
几十秒后刷新，看是否变绿；邮箱里收到就说明通了。

## 已知限制（必须知道）
1. **GitHub 的定时任务可能延迟 5–15 分钟**，不是秒级精准。
2. **境外网络访问新浪/东财接口可能不稳定**，如果连续几天失败，说明这条路走不通，得换国内云（阿里云函数计算有免费额度）。
3. 免费额度每月 2000 分钟，这套配置约消耗 200–300 分钟/月，够用。
4. 报告会回写到仓库，所以历史数据能积累；但仓库会慢慢变大（每天几 KB，一年几 MB，可接受）。

## 文件说明
- `market_data.py`：取数核心（akshare 封装，四类数据）
- `tools/premarket.py`：盘前简报（外盘 + 外盘板块分化 + 昨日情绪 + 触发线）
- `tools/daily_report.py`：收盘总结（涨停池 / 封板率 / 连板 / 板块持续性 / 观察池判定）
- `tools/watch_check.py`：盘中触发检查（价格 + 量能 + 距低点）
- `tools/mail_report.py`：邮件发送
- `tools/common.py`：路径解析（靠环境变量 `MY_BASE` 适配本地与云端）
- `mail_config.json`：SMTP 配置（不含密码）
- `watch_baseline.json`：观察池的量能基准（每周重建一次更准）
- `.github/workflows/*.yml`：三个定时任务

## 如果要换标的
改 `tools/watch_check.py` 里的 `WATCH` 字典和 `tools/premarket.py` 里的 `watch_levels()`，两处要一致。

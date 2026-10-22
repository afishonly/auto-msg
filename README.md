# auto-msg

浏览器保活 + 每日自动发消息机器人。

## 用途

- **保活**：每 `heartbeat_minutes`（默认 10 分钟）刷新一次页面，保持浏览器会话在线。
- **每日发消息**：在 `send_window` 时间窗内，每天自动发送一条消息（默认内容见 `config.example.json` 的 `message`），保持账号活跃。

> 原始场景：在 MonkeyCode 容器里用一个常驻的 Playwright 浏览器实例打开目标站点，
> 既防止会话掉线，也通过每日一条消息维持账号活跃度。

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `keepalive.py` | 主程序：心跳保活 + 每日发消息，含自动登录逻辑 |
| `send_msg.py` | 发送消息的独立脚本 |
| `send_daily_random.sh` | 每日随机消息的辅助脚本 |
| `start_keepalive.sh` | 启动 keepalive 的入口脚本 |
| `stop_keepalive.sh` | 停止 keepalive 的脚本 |
| `uninstall.bat` | Windows 卸载辅助 |
| `test_site/` | 本地测试站点 |
| `ensure_running.sh` | **自愈守护**：检测 keepalive 未运行则自动拉起（用于容器重启后自启） |
| `config.example.json` | 配置模板（**不含真实账号密码**） |

## 配置

```bash
cp config.example.json config.json
# 然后编辑 config.json，填入真实的 account / password 以及目标站点信息
```

关键配置项：

- `url` / `login_url`：目标站点与登录页
- `account` / `password`：登录账号（**请勿提交到仓库**，已被 `.gitignore` 忽略）
- `message`：每日发送的默认消息内容
- `heartbeat_minutes`：心跳刷新间隔（分钟）
- `send_window`：每日发消息的时间窗，如 `["08:00","22:00"]`
- `send_random` / `send_times`：是否随机内容 / 发送次数配置
- `user_data_dir`：浏览器用户数据目录（保持登录态）
- `*_selectors`：页面元素选择器，按需调整

## 运行

```bash
chmod +x start_keepalive.sh stop_keepalive.sh ensure_running.sh
./start_keepalive.sh
```

## 容器重启后自动拉起

该容器由 `firecracker-init` 作为 PID 1 启动，**没有 systemd / cron / pm2**，因此用 shell rc 钩子实现自启：

1. `ensure_running.sh` 做自愈检测：若 `keepalive.py` 未运行则用 `start_keepalive.sh` 拉起。
2. 在 `/root/.zshrc` 与 `/root/.bashrc` 末尾追加一行，在 shell 启动时后台调用 `ensure_running.sh`：

   ```sh
   # >>> auto-msg autostart hook >>>
   ( /workspace/auto_web_msg_deploy/auto_web_msg/ensure_running.sh >/dev/null 2>&1 & ) 2>/dev/null
   # <<< auto-msg autostart hook <<<
   ```

> 自启日志写入 `autostart.log`，可用 `cat autostart.log` 查看。

## 已知修复记录

- **致命 bug（已修复）**：原 `keepalive.py` 中 `today = datetime.now().strftime('%Y-%m-%d')`
  写在了 `while True` 循环**之外**，导致 `today` 在启动当天被冻结，
  `if send_done_date != today` 永远为 False，**35 天从未真正发过消息**。
  修复：把 `today` 的计算移入循环内部。
- **配置未持久化（已修复）**：发送成功后仅修改内存中的 `cfg["_send_done_date"]`，
  没有写回 `config.json`，重启后会重复发送同一天。
  修复：发送后 `json.dump` 写回 `config.json`。

## 安全说明

真实 `config.json`（含账号密码）已被 `.gitignore` 忽略，仓库中只保留 `config.example.json`。
推送前请确认没有把敏感信息提交进来。

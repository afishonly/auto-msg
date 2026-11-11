# auto-msg

浏览器保活 + 每日自动发消息机器人。

## 用途

- **保活**：每 `heartbeat_minutes`（默认 10 分钟）刷新一次页面，保持浏览器会话在线。
- **每日发消息**：在 `send_window` 时间窗内，每天自动发送一条消息（默认内容见 `config.example.json` 的 `message`），保持账号活跃。
- **每日签到**（可选）：每天自动完成 MonkeyCode 每日签到，领取 100 积分。

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
- `checkin_enabled`：每日签到开关（默认 `true`，设为 `false` 关闭）
- `_checkin_done_date`：签到防重复标记，由程序写回，**不要手改**（与 `_send_done_date` 相互独立）
- `proxy_server` + `use_proxy`：仅当部署环境需要走代理出网时，设置 `proxy_server` 并把 `use_proxy` 设为 `true`；默认直连（沙箱部署 config 里即使留有 `proxy_server` 字段也不会生效）

## 每日签到

主循环里与「每日发消息」平行的一条独立逻辑（独立标签页执行，不扰动任务页与发消息流程）：

1. **查状态**：在页面上下文用官方接口 `GET /api/v1/users/wallet/checkin` 查今日是否已签
   （自动带浏览器登录 cookie），同时 `GET /api/v1/users/wallet` 读积分余额原始值
   （界面显示积分 = `round(balance / 1000)`）。
2. **已签到**：直接记录完成，不重复点击（重复签到无收益且可能触发风控）。
3. **未签到**：点击页面上的签到按钮——控制台外壳的「Check in for credits / 签到领积分」，
   或钱包弹窗「My credits / 我的积分」页的「Check in for 100 credits / 签到领 100 积分」。
   领取接口需要验证码 token，只能走页面按钮自带的验证码流程，**不直调领取接口**；
   若出现滑块/拼图类验证码，程序截图存 `debug/` 后本轮放弃、下一心跳周期重试，不硬闯。
4. **校验**：点击后轮询状态接口翻为 `checked_in=true` 且余额增加 100（原始值 +100000）才判成功，
   成功后把 `_checkin_done_date` 写回 `config.json` 防重复；失败按心跳周期重试。

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

# -*- coding: utf-8 -*-
"""常驻浏览器保活 + 每天定点发消息（Linux/Windows + Playwright）

效果等同于 Windows 上一直开着网页：浏览器进程常驻，定期刷新页面/轻量交互保持会话活跃，
并在配置的时间点向聊天框发送固定消息。

MonkeyCode 适配说明：
- 未登录时任务页只显示登录入口、不含表单，必须先跳到 /login 并点击 "Email and Password" 标签，
  表单（#user-email / #user-password）才会出现。
- 登录页/任务页可能弹出通知/订阅弹窗（dialog-overlay），需先关闭再交互。
- 聊天输入框为 textarea[placeholder*='Describe']，发送方式为按 Enter（提示语：Enter to send）。
"""
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print("[错误] 缺少 config.json")
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_debug(page, tag):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(os.path.join(BASE_DIR, "debug"), exist_ok=True)
    png = os.path.join(BASE_DIR, "debug", f"{tag}_{ts}.png")
    try:
        page.screenshot(path=png, full_page=False)
        print(f"[调试] 截图已保存: {png}")
    except Exception as e:
        print(f"[调试] 截图失败: {e}")


def dismiss_overlays(page):
    """关闭页面上可能拦截点击的弹窗（通知/订阅/语言切换等）。

    直接按文案匹配可点击的关闭按钮（不依赖特定 overlay 选择器），
    因为不同弹窗的实现差异较大（如「留在中文版」是 Radix 弹窗）。
    """
    dismiss_texts = [
        "留在中文版", "Close", "关闭", "稍后", "稍后再说", "取消", "知道了",
        "X", "Don't show", "忽略", "Got it", "Dismiss", "No thanks", "Confirm",
    ]
    for _ in range(12):
        closed_any = False
        # 先尝试 Esc
        try:
            page.keyboard.press("Escape")
            time.sleep(0.3)
        except Exception:
            pass
        # 按文案点击可见的关闭按钮（button / a / role=button）
        for txt in dismiss_texts:
            try:
                loc = page.locator("button, a, [role='button']").filter(has_text=txt).first
                if loc.count() and loc.is_visible(timeout=800):
                    loc.click(timeout=1500)
                    closed_any = True
                    time.sleep(0.5)
            except Exception:
                pass
        # 通用关闭图标按钮
        try:
            for e in page.query_selector_all("button[aria-label='Close']"):
                if e.is_visible():
                    e.click(timeout=1500)
                    closed_any = True
                    time.sleep(0.4)
        except Exception:
            pass
        # 若本轮没关掉任何东西，且确实没有可见弹窗，则结束
        if not closed_any:
            try:
                ov = page.query_selector("div[data-slot='dialog-overlay']:visible") or \
                    page.query_selector("[role='dialog']:visible")
                if ov is None:
                    break
            except Exception:
                break
        time.sleep(0.3)


def is_logged_in(page, input_selectors):
    for sel in input_selectors:
        try:
            page.wait_for_selector(sel, timeout=5000)
            return True
        except Exception:
            continue
    return False


def click_scan_entry(page, scan_selectors):
    """点击扫码登录入口（如「微信扫码」tab/按钮），让二维码弹出来。"""
    if not scan_selectors:
        return
    for sel in scan_selectors:
        try:
            el = page.wait_for_selector(sel, timeout=3000)
            el.click()
            print(f"[登录] 已点击扫码入口: {sel}")
            time.sleep(2)
            return
        except Exception:
            continue
    print("[登录] 未找到扫码入口按钮，跳过（直接截图当前页面）")


def try_password_login(page, cfg):
    """自动账号密码登录。成功返回 True，失败返回 False（交给扫码流程兜底）。"""
    account = cfg.get("account", "")
    password = cfg.get("password", "")
    if not account or not password:
        return False
    login_url = cfg.get("login_url", "https://monkeycode-ai.com/login")
    try:
        # 跳到真正的登录页（任务页未登录时不含表单）
        page.goto(login_url, timeout=45000, wait_until="domcontentloaded")
        page.wait_for_load_state("domcontentloaded")
        time.sleep(2)
        dismiss_overlays(page)
        # /login 默认不含输入框，必须点击 "Email and Password" 标签
        clicked = False
        for attempt in range(3):
            try:
                page.get_by_text("Email and Password", exact=True).click(timeout=5000)
                clicked = True
                print("[登录] 已点击 Email and Password 标签")
                break
            except Exception as e:
                print(f"[登录] 点击 Email and Password 被拦截，重试关闭弹窗: {e}")
                dismiss_overlays(page)
                time.sleep(1)
        if not clicked:
            print("[登录] 无法点击 Email and Password（可能已在当前标签）")
        time.sleep(1.5)

        box = None
        for sel in cfg.get("account_input_selectors", ["input#user-email"]):
            try:
                box = page.wait_for_selector(sel, timeout=8000)
                break
            except Exception:
                continue
        if box is None:
            print("[登录] 未找到账号输入框，跳过账号密码登录")
            return False
        box.fill(account)

        pwd = None
        for sel in cfg.get("password_input_selectors", ["input#user-password"]):
            try:
                pwd = page.wait_for_selector(sel, timeout=8000)
                break
            except Exception:
                continue
        if pwd is None:
            print("[登录] 未找到密码输入框，跳过账号密码登录")
            return False
        pwd.fill(password)

        # 关闭可能在登录前弹出的干扰弹窗
        dismiss_overlays(page)
        btn = None
        for sel in cfg.get("login_btn_selectors", []):
            try:
                btn = page.wait_for_selector(sel, timeout=5000)
                break
            except Exception:
                continue
        if btn is None:
            try:
                btn = page.get_by_role("button", name="Sign in")
                btn.wait_for(timeout=5000)
            except Exception:
                print("[登录] 未找到登录按钮，跳过账号密码登录")
                return False
        btn.click()
        print("[登录] 已提交账号密码，等待登录结果...")
        # 等待跳转到控制台（已登录）
        try:
            page.wait_for_url("**/console/**", timeout=20000)
        except Exception:
            pass
        time.sleep(3)
        dismiss_overlays(page)
        return True
    except Exception as e:
        print(f"[登录] 账号密码登录异常: {e}")
        return False


def wait_login(page, input_selectors, login_timeout=600, scan_selectors=None):
    """等待用户扫码登录完成，期间自动点击扫码入口并持续截图二维码。"""
    click_scan_entry(page, scan_selectors or [])
    deadline = time.time() + login_timeout
    print("[登录] 检测到未登录，请扫码登录...")
    while time.time() < deadline:
        try:
            for fr in page.frames:
                try:
                    if fr.wait_for_selector(input_selectors[0], timeout=1000):
                        print("[登录] 登录成功")
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[登录] {ts} 等待扫码中，请查看 debug 目录二维码截图")
        save_debug(page, "qr")
        time.sleep(10)
    print("[登录] 等待扫码超时，退出")
    return False


def find_target(page, input_selectors, frame):
    if frame is None:
        try:
            page.wait_for_selector(input_selectors[0], timeout=8000)
            return page, None
        except Exception:
            for fr in page.frames:
                try:
                    if fr.wait_for_selector(input_selectors[0], timeout=1500):
                        return fr, fr
                except Exception:
                    continue
    return page, frame


def send_message(page, cfg, frame=None):
    input_selectors = cfg["input_selectors"]
    send_selectors = cfg.get("send_selectors", [])
    message = cfg["message"]

    dismiss_overlays(page)
    target, frame = find_target(page, input_selectors, frame)
    box = None
    for sel in input_selectors:
        try:
            box = target.wait_for_selector(sel, timeout=8000)
            break
        except Exception:
            continue
    if box is None:
        raise RuntimeError("未找到输入框")
    dismiss_overlays(page)
    box.click()
    box.fill(message)
    print(f"[{datetime.now():%H:%M:%S}] 已填入消息: {message}")
    time.sleep(1.5)

    # 优先尝试发送按钮，失败则按 Enter 发送（提示语：Enter to send）
    sent = False
    for sel in send_selectors:
        try:
            btn = target.wait_for_selector(sel, timeout=3000)
            if btn and btn.is_visible():
                btn.click()
                sent = True
                print(f"[{datetime.now():%H:%M:%S}] 已点击发送按钮")
                break
        except Exception:
            continue
    if not sent:
        try:
            box.click()
            page.keyboard.press("Enter")
            print(f"[{datetime.now():%H:%M:%S}] 已按 Enter 发送")
        except Exception as e:
            raise RuntimeError(f"发送失败: {e}")
    time.sleep(2)
    return True


def ensure_login(page, cfg, input_selectors, scan_selectors):
    """优先账号密码登录，失败则回退扫码登录。返回是否已登录。"""
    url = cfg["url"]
    if cfg.get("account") and cfg.get("password"):
        try_password_login(page, cfg)
        # 登录后回到任务页再判定
        try:
            page.goto(url, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_load_state("domcontentloaded")
            time.sleep(5)
            dismiss_overlays(page)
        except Exception as e:
            print(f"[登录] 回到任务页失败: {e}")
        if is_logged_in(page, input_selectors):
            print("[登录] 账号密码登录成功")
            return True
        print("[登录] 账号密码登录未生效，回退扫码登录")
    if wait_login(page, input_selectors, scan_selectors=scan_selectors):
        return True
    return False


def main():
    cfg = load_config()
    url = cfg["url"]
    message = cfg["message"]
    input_selectors = cfg["input_selectors"]
    headless = cfg.get("headless", True)
    user_data_dir = cfg.get("user_data_dir", os.path.join(BASE_DIR, "browser_profile"))
    wait_after_load = cfg.get("wait_after_load", 5)
    scan_selectors = cfg.get("scan_selectors", [])

    heartbeat_minutes = cfg.get("heartbeat_minutes", 10)
    send_times = cfg.get("send_times", ["09:00"])
    send_random = cfg.get("send_random", True)
    send_window = cfg.get("send_window", ["08:00", "22:00"])
    send_done_date = cfg.get("_send_done_date", None)
    heartbeat_done = 0.0

    def pick_send_time():
        """每天随机选一个发送时间，落在 send_window 区间内。"""
        if not send_random:
            return send_times[0]
        try:
            start_h, start_m = map(int, send_window[0].split(":"))
            end_h, end_m = map(int, send_window[1].split(":"))
            start_min = start_h * 60 + start_m
            end_min = end_h * 60 + end_m
            if end_min < start_min:
                end_min = 23 * 60 + 59
            pick = random.randint(start_min, end_min)
            return f"{pick // 60:02d}:{pick % 60:02d}"
        except Exception:
            return send_times[0]

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        frame = None

        page.goto(url, timeout=45000, wait_until="domcontentloaded")
        page.wait_for_load_state("domcontentloaded")
        time.sleep(wait_after_load)
        dismiss_overlays(page)

        if not is_logged_in(page, input_selectors):
            if not ensure_login(page, cfg, input_selectors, scan_selectors):
                context.close()
                sys.exit(1)

        print("[启动] 常驻保活模式已启动，Ctrl+C 停止")
        print(f"[启动] 心跳间隔 {heartbeat_minutes} 分钟")
        if send_random:
            print(f"[启动] 每天 {send_window[0]}-{send_window[1]} 之间随机发送 1 次")
        else:
            print(f"[启动] 每日发送时间 {send_times}")

        today = datetime.now().strftime("%Y-%m-%d")
        target_time = None
        sent_today = False

        try:
            while True:
                now = datetime.now()
                today = now.strftime("%Y-%m-%d")  # FIX: refresh every loop

                if send_done_date != today:
                    if target_time is None:
                        target_time = pick_send_time()
                        print(f"[计划] 今日 {target_time} 发送消息")
                    hh, mm = target_time.split(":")
                    if (now.hour, now.minute) >= (int(hh), int(mm)):
                        try:
                            send_message(page, cfg, frame)
                            sent_today = True
                            print(f"[发送] {now:%H:%M:%S} 消息已发送")
                        except Exception as e:
                            print(f"[发送] 失败: {e}")
                            save_debug(page, "send_fail")
                            page.reload(timeout=45000)
                            time.sleep(wait_after_load)
                            dismiss_overlays(page)
                            if not is_logged_in(page, input_selectors):
                                print("[发送] 会话可能已失效，尝试重新登录")
                                ensure_login(page, cfg, input_selectors, scan_selectors)
                            frame = None
                        if sent_today:
                            send_done_date = today
                            cfg["_send_done_date"] = today
                            try:  # FIX: persist to config.json to avoid duplicate send after restart
                                with open(CONFIG_PATH, "w", encoding="utf-8") as _f:
                                    json.dump(cfg, _f, ensure_ascii=False, indent=2)
                                print(f"[配置] 已写回 _send_done_date={today}")
                            except Exception as _e:
                                print(f"[配置] 写回失败: {_e}")
                            target_time = None
                            sent_today = False

                if time.time() - heartbeat_done >= heartbeat_minutes * 60:
                    try:
                        print(f"[心跳] {now:%H:%M:%S} 刷新页面保持活跃")
                        page.reload(timeout=45000)
                        page.wait_for_load_state("domcontentloaded")
                        time.sleep(2)
                        dismiss_overlays(page)
                        if not is_logged_in(page, input_selectors):
                            print("[心跳] 会话失效，尝试重新登录")
                            ensure_login(page, cfg, input_selectors, scan_selectors)
                        frame = None
                    except Exception as e:
                        print(f"[心跳] 异常: {e}")
                        save_debug(page, "hb_fail")
                    heartbeat_done = time.time()

                time.sleep(30)
        except KeyboardInterrupt:
            print("[停止] 用户手动停止")
        finally:
            context.close()


if __name__ == "__main__":
    main()

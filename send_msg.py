# -*- coding: utf-8 -*-
"""定时向网页聊天框发送固定消息（Linux/Windows + Playwright）"""
import json
import os
import sys
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print("[错误] 缺少 config.json，请先复制 config.example.json 并填写")
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


def try_password_login(page, cfg):
    """自动账号密码登录。成功返回 True，失败返回 False。"""
    account = cfg.get("account", "")
    password = cfg.get("password", "")
    if not account or not password:
        return False
    try:
        for sel in cfg.get("login_mode_selectors", []):
            try:
                el = page.wait_for_selector(sel, timeout=3000)
                el.click()
                print(f"[登录] 已点击账号密码登录入口: {sel}")
                time.sleep(1)
                break
            except Exception:
                continue

        box = None
        for sel in cfg.get("account_input_selectors", []):
            try:
                box = page.wait_for_selector(sel, timeout=5000)
                break
            except Exception:
                continue
        if box is None:
            print("[登录] 未找到账号输入框，跳过账号密码登录")
            return False
        box.fill(account)

        pwd = None
        for sel in cfg.get("password_input_selectors", []):
            try:
                pwd = page.wait_for_selector(sel, timeout=5000)
                break
            except Exception:
                continue
        if pwd is None:
            print("[登录] 未找到密码输入框，跳过账号密码登录")
            return False
        pwd.fill(password)

        btn = None
        for sel in cfg.get("login_btn_selectors", []):
            try:
                btn = page.wait_for_selector(sel, timeout=5000)
                break
            except Exception:
                continue
        if btn is None:
            print("[登录] 未找到登录按钮，跳过账号密码登录")
            return False
        btn.click()
        print("[登录] 已提交账号密码，等待登录结果...")
        time.sleep(5)
        return True
    except Exception as e:
        print(f"[登录] 账号密码登录异常: {e}")
        return False


def main():
    cfg = load_config()

    url = cfg["url"]
    message = cfg["message"]
    input_selectors = cfg["input_selectors"]
    send_selectors = cfg["send_selectors"]
    headless = cfg.get("headless", True)
    user_data_dir = cfg.get(
        "user_data_dir", os.path.join(BASE_DIR, "browser_profile")
    )
    wait_after_load = cfg.get("wait_after_load", 5)
    max_attempts = cfg.get("max_attempts", 3)
    scan_selectors = cfg.get("scan_selectors", [])

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        if context.pages:
            page = context.pages[0]
        else:
            page = context.new_page()

        try:
            page.goto(url, timeout=45000)
            print(f"[{datetime.now():%H:%M:%S}] 页面已打开，等待加载...")
            page.wait_for_load_state("domcontentloaded")
            time.sleep(wait_after_load)
        except Exception as e:
            print(f"[错误] 页面打开失败: {e}")
            save_debug(page, "load")
            context.close()
            sys.exit(1)

        frame = None
        target = page

        try:
            page.wait_for_selector(input_selectors[0], timeout=5000)
        except Exception:
            if cfg.get("account") and cfg.get("password"):
                print("[登录] 页面未登录，尝试账号密码登录")
                try_password_login(page, cfg)
                try:
                    page.wait_for_selector(input_selectors[0], timeout=5000)
                except Exception:
                    pass
            elif scan_selectors:
                for sel in scan_selectors:
                    try:
                        el = page.wait_for_selector(sel, timeout=3000)
                        el.click()
                        print(f"[登录] 已点击扫码入口: {sel}")
                        time.sleep(2)
                        break
                    except Exception:
                        continue

        for i in range(max_attempts):
            try:
                if frame is None:
                    target = page
                    try:
                        target.wait_for_selector(input_selectors[0], timeout=8000)
                    except Exception:
                        for fr in page.frames:
                            try:
                                if fr.wait_for_selector(input_selectors[0], timeout=1500):
                                    frame = fr
                                    target = fr
                                    break
                            except Exception:
                                continue

                box = None
                for sel in input_selectors:
                    try:
                        box = target.wait_for_selector(sel, timeout=6000)
                        break
                    except Exception:
                        continue
                if box is None:
                    raise RuntimeError("未找到输入框")

                box.click()
                box.fill(message)
                print(f"[{datetime.now():%H:%M:%S}] 已填入消息: {message}")

                btn = None
                for sel in send_selectors:
                    try:
                        btn = target.wait_for_selector(sel, timeout=5000)
                        break
                    except Exception:
                        continue
                if btn is None:
                    raise RuntimeError("未找到发送按钮")

                btn.click()
                print(f"[{datetime.now():%H:%M:%S}] 已点击发送")
                time.sleep(2)
                print("[成功] 消息发送完成")
                context.close()
                return
            except Exception as e:
                print(f"[第{i+1}次尝试] 失败: {e}")
                if i == max_attempts - 1:
                    save_debug(target, "fail")
                time.sleep(3)

        print("[失败] 多次尝试后仍未成功，请查看 debug 目录截图并调整 config.json 选择器")
        context.close()
        sys.exit(1)


if __name__ == "__main__":
    main()

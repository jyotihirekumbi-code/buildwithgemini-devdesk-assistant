import asyncio
import glob
import os
import shutil
import subprocess
from playwright.async_api import async_playwright

FRONTEND_URL = "https://devdesk-assistant-frontend-1023883542702.us-central1.run.app"
ARTIFACT_DIR = "/config/.gemini/antigravity/brain/e3ea7023-f4cd-4265-a9ad-725240f12d61"
OUTPUT_VIDEO_PATH = os.path.join(ARTIFACT_DIR, "devdesk_assistant_demo.mp4")

async def record():
    temp_video_dir = "/tmp/playwright_videos"
    os.makedirs(temp_video_dir, exist_ok=True)
    os.makedirs(ARTIFACT_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=temp_video_dir,
            record_video_size={"width": 1280, "height": 800}
        )

        page = await context.new_page()
        print("Navigating to DevDesk Assistant Frontend...")
        await page.goto(FRONTEND_URL, wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # 1. First Prompt: Core incident ticket database lookup
        print("Executing First Prompt: Open high-severity tickets...")
        await page.click(".chip:has-text('Open high-severity tickets')")
        
        # Wait for agent response to appear in log
        await page.wait_for_selector(".msg.agent:nth-of-type(1)", timeout=30000)
        await page.wait_for_timeout(5000)

        # 2. Second Prompt: Rich image generation tool call
        print("Executing Second Prompt: Generate server rack status badge...")
        input_el = page.locator("#input")
        await input_el.fill("Generate a server rack status badge image")
        await page.click("button[type='submit']")

        # Wait for second agent response
        await page.wait_for_selector(".msg.agent:nth-of-type(2)", timeout=45000)
        await page.wait_for_timeout(6000)

        # 3. Demonstrate UI feature: Toggle theme mode
        print("Toggling Dark / Light theme...")
        await page.click("#theme-toggle")
        await page.wait_for_timeout(2000)
        await page.click("#theme-toggle")
        await page.wait_for_timeout(2000)

        video_file = await page.video.path()
        await page.close()
        await context.close()
        await browser.close()
        print(f"Recorded video saved to: {video_file}")

        # Convert webm to mp4 or copy
        ffmpeg_bin = shutil.which("ffmpeg") or "/config/.cache/ms-playwright/ffmpeg-1011/ffmpeg"
        if os.path.exists(ffmpeg_bin):
            print(f"Converting video using {ffmpeg_bin}...")
            cmd = [ffmpeg_bin, "-y", "-i", video_file, "-c:v", "libx264", "-pix_fmt", "yuv420p", OUTPUT_VIDEO_PATH]
            subprocess.run(cmd, check=True)
            print(f"Converted demo video successfully to: {OUTPUT_VIDEO_PATH}")
        else:
            shutil.copy(video_file, OUTPUT_VIDEO_PATH.replace(".mp4", ".webm"))
            print(f"Copied webm video to artifact path: {OUTPUT_VIDEO_PATH}")

if __name__ == "__main__":
    asyncio.run(record())

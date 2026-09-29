const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const ffmpegPath = require('ffmpeg-static');

const FRONTEND_URL = 'https://devdesk-assistant-frontend-1023883542702.us-central1.run.app';
const ARTIFACT_DIR = '/config/.gemini/antigravity/brain/e3ea7023-f4cd-4265-a9ad-725240f12d61';
const FRAMES_DIR = '/tmp/demo_frames';
const OUTPUT_VIDEO = path.join(ARTIFACT_DIR, 'devdesk_assistant_demo.mp4');

async function record() {
  if (fs.existsSync(FRAMES_DIR)) {
    fs.rmSync(FRAMES_DIR, { recursive: true, force: true });
  }
  fs.mkdirSync(FRAMES_DIR, { recursive: true });
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });

  const executablePath = '/usr/bin/google-chrome';
  const browser = await puppeteer.launch({
    executablePath: fs.existsSync(executablePath) ? executablePath : undefined,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1280,800']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800 });

  let frameIdx = 0;
  async function grabFrame() {
    const numStr = String(frameIdx++).padStart(5, '0');
    const framePath = path.join(FRAMES_DIR, `frame_${numStr}.png`);
    await page.screenshot({ path: framePath, type: 'png' });
  }

  async function holdScene(durationMs) {
    const fps = 5;
    const totalFrames = Math.max(1, Math.floor((durationMs / 1000) * fps));
    const delay = durationMs / totalFrames;
    for (let i = 0; i < totalFrames; i++) {
      await grabFrame();
      await new Promise(r => setTimeout(r, delay));
    }
  }

  async function typeSlowly(selector, text) {
    await page.focus(selector);
    for (const char of text) {
      await page.keyboard.type(char);
      await grabFrame();
    }
  }

  console.log('Navigating to DevDesk Assistant Frontend...');
  await page.goto(FRONTEND_URL, { waitUntil: 'networkidle2' });
  await holdScene(2000);

  // 1. First Prompt: Core ticket lookup
  console.log('Step 1: Open high-severity tickets prompt');
  await page.click('.chip:nth-child(1)');
  await grabFrame();

  let responseArrived = false;
  const start = Date.now();
  while (Date.now() - start < 30000 && !responseArrived) {
    await grabFrame();
    const agentMsg = await page.$('.msg.agent');
    if (agentMsg) {
      responseArrived = true;
      break;
    }
    await new Promise(r => setTimeout(r, 500));
  }
  await holdScene(5000);

  // 2. Second Prompt: Rich image generation tool call
  console.log('Step 2: Generate server rack status badge image prompt');
  await typeSlowly('#input', 'Generate a server rack status badge image');
  await holdScene(500);
  await page.click('button[type="submit"]');
  await grabFrame();

  responseArrived = false;
  const start2 = Date.now();
  while (Date.now() - start2 < 45000 && !responseArrived) {
    await grabFrame();
    const secondMsg = await page.$('.msg.agent:nth-of-type(2)');
    if (secondMsg) {
      responseArrived = true;
      break;
    }
    await new Promise(r => setTimeout(r, 500));
  }
  await holdScene(6000);

  // 3. UI Feature: Toggle theme mode
  console.log('Step 3: Toggle theme mode');
  await page.click('#theme-toggle');
  await holdScene(2500);
  await page.click('#theme-toggle');
  await holdScene(2500);

  await browser.close();

  console.log(`Captured ${frameIdx} frames. Encoding video with ffmpeg...`);
  await encodeVideo(frameIdx);
}

function encodeVideo(totalFrames) {
  return new Promise((resolve, reject) => {
    const args = [
      '-y',
      '-r', '5',
      '-i', path.join(FRAMES_DIR, 'frame_%05d.png'),
      '-c:v', 'libx264',
      '-pix_fmt', 'yuv420p',
      '-vf', 'scale=1280:800',
      OUTPUT_VIDEO
    ];

    console.log(`Running ffmpeg (${ffmpegPath})...`);
    const proc = spawn(ffmpegPath, args);

    proc.stdout.on('data', d => console.log(d.toString()));
    proc.stderr.on('data', d => {
      const str = d.toString();
      if (str.includes('frame=')) {
        process.stdout.write(`\r${str.trim().slice(0, 60)}`);
      }
    });

    proc.on('close', code => {
      console.log('\n');
      if (code === 0) {
        console.log(`Successfully generated demo video: ${OUTPUT_VIDEO}`);
        resolve();
      } else {
        reject(new Error(`ffmpeg exited with code ${code}`));
      }
    });
  });
}

record().catch(err => {
  console.error('Error during demo recording:', err);
  process.exit(1);
});

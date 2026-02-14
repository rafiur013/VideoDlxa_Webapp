#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
VideoDlx Bot - Complete Solution
Backend for Railway.app
"""

import os
import logging
import asyncio
from datetime import datetime
from threading import Thread

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import yt_dlp
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration - Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-app.vercel.app")

app = Flask(__name__)
CORS(app)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

class VideoDownloader:
    @staticmethod
    async def get_info(url: str):
        try:
            ydl_opts = {'quiet': True, 'no_warnings': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, url, download=False)
                if not info: return None
                
                formats = []
                seen = set()
                for fmt in info.get('formats', []):
                    h = fmt.get('height')
                    if h and h not in seen and fmt.get('vcodec') != 'none':
                        formats.append({'quality': f"{h}p", 'format_id': fmt['format_id'], 'filesize': fmt.get('filesize', 0)})
                        seen.add(h)
                formats.sort(key=lambda x: int(x['quality'][:-1]), reverse=True)
                
                return {
                    'title': info.get('title', 'Unknown'),
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': info.get('duration', 0),
                    'formats': formats[:6],
                    'url': url,
                    'source': info.get('extractor', 'Unknown')
                }
        except Exception as e:
            logger.error(f"Error: {e}")
            return None
    
    @staticmethod
    async def download_video(url: str, quality: str = '720p'):
        try:
            ts = datetime.now().timestamp()
            fn = f"{DOWNLOAD_FOLDER}/video_{ts}"
            qm = {'1080p': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]', '720p': 'bestvideo[height<=720]+bestaudio/best[height<=720]', '480p': 'bestvideo[height<=480]+bestaudio/best[height<=480]', '360p': 'bestvideo[height<=360]+bestaudio/best[height<=360]'}
            opts = {'format': qm.get(quality, 'bestvideo+bestaudio/best'), 'outtmpl': f'{fn}.%(ext)s', 'merge_output_format': 'mp4', 'quiet': True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                await asyncio.to_thread(ydl.download, [url])
            for f in os.listdir(DOWNLOAD_FOLDER):
                if f.startswith(f"video_{int(ts)}"): return os.path.join(DOWNLOAD_FOLDER, f)
            return None
        except Exception as e:
            logger.error(f"Error: {e}")
            return None
    
    @staticmethod
    async def download_audio(url: str):
        try:
            ts = datetime.now().timestamp()
            fn = f"{DOWNLOAD_FOLDER}/audio_{ts}"
            opts = {'format': 'bestaudio/best', 'outtmpl': f'{fn}.%(ext)s', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}], 'quiet': True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                await asyncio.to_thread(ydl.download, [url])
            for f in os.listdir(DOWNLOAD_FOLDER):
                if f.startswith(f"audio_{int(ts)}"): return os.path.join(DOWNLOAD_FOLDER, f)
            return None
        except Exception as e:
            logger.error(f"Error: {e}")
            return None

@app.route('/')
def home():
    return jsonify({'status': 'online', 'service': 'VideoDlx API'})

@app.route('/api/video-info', methods=['POST'])
def video_info():
    try:
        url = request.json.get('url')
        if not url: return jsonify({'error': 'URL required'}), 400
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        info = loop.run_until_complete(VideoDownloader.get_info(url))
        loop.close()
        if not info: return jsonify({'error': 'Failed'}), 400
        return jsonify(info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def download_api():
    try:
        data = request.json
        url = data.get('url')
        quality = data.get('quality', '720p')
        is_audio = data.get('is_audio', False)
        if not url: return jsonify({'error': 'URL required'}), 400
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        fp = loop.run_until_complete(VideoDownloader.download_audio(url) if is_audio else VideoDownloader.download_video(url, quality))
        loop.close()
        if not fp or not os.path.exists(fp): return jsonify({'error': 'Failed'}), 400
        return send_file(fp, as_attachment=True, download_name=f'video_{quality}.mp4' if not is_audio else 'audio.mp3')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = f"🎬 <b>Welcome to VideoDlx!</b>\n\n👋 Hi {update.effective_user.first_name}!\n\n✨ Download videos from YouTube, Facebook, Instagram, TikTok & 1000+ sites!\n\n🚀 <b>Tap 'Start App' to begin!</b>"
    kb = [[InlineKeyboardButton("🚀 Start App", web_app=WebAppInfo(url=WEBAPP_URL))], [InlineKeyboardButton("ℹ️ Help", callback_data="help")]]
    await update.message.reply_text(txt, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith('http'):
        await update.message.reply_text("Please use the Web App! 🎬", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Open App", web_app=WebAppInfo(url=WEBAPP_URL))]]))
        return
    await update.message.reply_text("Use Web App for better experience! 🎨")

async def btn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "help":
        txt = "📱 <b>How to Use</b>\n\n1️⃣ Tap 'Start App'\n2️⃣ Paste video link\n3️⃣ Select quality\n4️⃣ Download!\n\n✨ Supports YouTube, Facebook, Instagram, TikTok & more!"
        await q.edit_message_text(txt, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Open App", web_app=WebAppInfo(url=WEBAPP_URL))]]))

def run_flask():
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

def main():
    if not BOT_TOKEN or BOT_TOKEN == "8212890715:AAFV4WtLLjQftKeq3a1fUDzpZ52yank9JGw":
        logger.error("❌ Set BOT_TOKEN!")
        return
    logger.info("🤖 Starting...")
    Thread(target=run_flask, daemon=True).start()
    logger.info("✅ Flask API Started")
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    application.add_handler(CallbackQueryHandler(btn_handler))
    logger.info("✅ Bot Started")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

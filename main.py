#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from dotenv import load_dotenv

# ==================== 0. 环境初始化 ====================
# 自动加载环境变量 (兼容模式：有文件读文件，没文件读 Secrets)
load_dotenv()

# 调试打印：检查密钥是否存在 (不会打印真实值)
print("-" * 30)
print("🔍 环境自检...")
if os.getenv('GITHUB_ACTIONS'):
    print("☁️ 运行环境: GitHub Actions (自动直连模式)")
else:
    print("🌍 运行环境: 本地 (尝试加载代理)")
    # 只有在本地才强制走代理，GitHub 上绝对不能设
    os.environ['HTTP_PROXY'] = 'http://127.0.0.1:21879'
    os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:21879'

if os.getenv('GOOGLE_API_KEY'):
    print("✅ GOOGLE_API_KEY: 已检测到")
else:
    print("❌ 错误: 未找到 GOOGLE_API_KEY，请检查 GitHub Settings -> Secrets")
    
if os.getenv('PUSHPLUS_TOKEN'):
    print("✅ PUSHPLUS_TOKEN: 已检测到")
else:
    print("❌ 错误: 未找到 PUSHPLUS_TOKEN，请检查 GitHub Settings -> Secrets")
print("-" * 30)

# ==================== 常量配置 ====================
TARGET_URL = "https://news.aibase.com/zh/daily"
PUSHPLUS_URL = "http://www.pushplus.plus/send"
# 伪装成浏览器，防止 403 Forbidden
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# ==================== 1. 爬虫模块 ====================
def scrape_news():
    print(f"🕷️ 开始抓取: {TARGET_URL}")
    try:
        # 注意：这里千万不能传 proxies 参数，让 requests 自动处理
        resp = requests.get(TARGET_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status() # 如果 404 或 403 会直接报错
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        news_list = []
        
        # 针对 AIbase 的通用抓取策略
        # 查找所有的链接，筛选看起来像新闻的
        links = soup.find_all('a', href=True)
        
        for link in links:
            text = link.get_text(strip=True)
            href = link['href']
            
            # 简单的筛选逻辑：长度够长，且包含 AI 关键词
            if len(text) > 10 and any(k in text.lower() for k in ['ai', 'gpt', '模型', '智能', 'daily', 'news']):
                if not href.startswith('http'):
                    href = f"https://news.aibase.com{href}"
                
                # 去重
                if not any(n['link'] == href for n in news_list):
                    news_list.append({'title': text, 'link': href})
            
            if len(news_list) >= 10: # 只要前10条
                break
        
        if not news_list:
            print("⚠️ 警告: 未找到符合条件的新闻，尝试抓取页面所有 H3 标题...")
            for h3 in soup.find_all('h3'):
                t = h3.get_text(strip=True)
                if len(t) > 5:
                    news_list.append({'title': t, 'link': TARGET_URL})
        
        print(f"✅ 抓取到 {len(news_list)} 条内容")
        return news_list

    except Exception as e:
        print(f"❌ 爬虫出错: {e}")
        return []

# ==================== 2. AI 总结模块 ====================
def summarize(news_data):
    if not news_data:
        return "今日暂无 AI 资讯获取。"
        
    print("🧠 正在请求 Gemini 进行总结...")
    try:
        genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # 构建 Prompt
        content_text = "\n".join([f"- {n['title']} ({n['link']})" for n in news_data])
        prompt = f"""
        你是一个科技主编。请根据以下 AI 新闻列表，写一份【AI 每日早报】。
        
        要求：
        1. 挑选 5-6 条最重要的内容。
        2. 每条用 Emoji 开头，一句话概括，并附带链接。
        3. 只要正文，不要废话。
        
        新闻列表：
        {content_text}
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"❌ AI 总结出错: {e}")
        return "AI 总结服务暂时不可用。"

# ==================== 3. 推送模块 ====================
def push_msg(content):
    print("📨 正在推送...")
    token = os.getenv('PUSHPLUS_TOKEN')
    if not token:
        print("❌ 无法推送：缺少 Token")
        return

    try:
        data = {
            'token': token,
            'title': 'AI 每日早报',
            'content': content,
            'template': 'markdown'
        }
        # 注意：这里也不能传 proxies
        resp = requests.post(PUSHPLUS_URL, json=data, timeout=30)
        print(f"✅ 推送响应: {resp.text}")
    except Exception as e:
        print(f"❌ 推送出错: {e}")

# ==================== 主入口 ====================
if __name__ == "__main__":
    # 1. 抓取
    news = scrape_news()
    
    # 2. 如果没抓到，不报错退出，而是发送一条“空日报”提醒，方便排查
    if not news:
        final_content = "⚠️ 警告：爬虫今日未抓取到任何数据，请检查网站结构是否变更。"
    else:
        # 3. 总结
        final_content = summarize(news)
    
    # 4. 发送
    push_msg(final_content)
    print("🚀 任务全部完成")

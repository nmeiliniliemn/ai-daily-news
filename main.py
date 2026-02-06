#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 每日早报 2.0
自动从 AIbase 获取最新 AI 新闻，使用 Google Gemini 总结，并推送至 PushPlus
"""

import os
import sys
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from dotenv import load_dotenv

# ==================== 环境与网络配置 ====================
# 加载环境变量
load_dotenv('config.env')  # 使用 config.env 文件而不是 .env

# 强制设置代理（非常重要）
os.environ['HTTP_PROXY'] = 'http://127.0.0.1:21879'
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:21879'
os.environ['http_proxy'] = 'http://127.0.0.1:21879'
os.environ['https_proxy'] = 'http://127.0.0.1:21879'

# ==================== 常量配置 ====================
TARGET_URL = "https://news.aibase.com/zh/daily"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
PUSHPLUS_URL = "http://www.pushplus.plus/send"

# AI Prompt 模板
AI_PROMPT = """你是一个 AI 科技观察员。请根据我提供的 AIbase 最新资讯列表，写一份【AI 每日早报】。

要求：
提炼 5-8 条最重要的 AI 行业动态。
每一条用 Emoji 开头（如 🤖, 🚀），一句话概括核心，并在末尾附上原文链接。
风格简洁、高信噪比。
只要输出最终内容，不要多余的废话。

资讯列表：
{news_content}
"""

# ==================== 爬虫模块 ====================
def scrape_aibase_news():
    """
    从 AIbase 网站爬取最新的 AI 新闻
    """
    try:
        print("🔍 开始爬取 AIbase 新闻...")

        headers = {
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        # 设置代理
        proxies = {
            'http': 'http://127.0.0.1:21879',
            'https': 'http://127.0.0.1:21879'
        }

        response = requests.get(TARGET_URL, headers=headers, proxies=proxies, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8'

        soup = BeautifulSoup(response.text, 'html.parser')

        # 提取新闻列表
        news_items = []

        # 方法1: 查找包含新闻链接的容器
        news_containers = soup.find_all(['div', 'article', 'section'], class_=lambda x: x and any(keyword in x.lower() for keyword in ['news', 'article', 'item', 'card', 'post']))

        if not news_containers:
            # 方法2: 查找所有 h3 和 a 标签
            news_containers = soup.find_all(['h3', 'a'])

        for container in news_containers[:20]:  # 限制搜索范围
            # 查找标题和链接
            title_elem = None
            link_elem = None

            # 如果是 h3 标签，直接使用
            if container.name == 'h3':
                title_elem = container
                link_elem = container.find_parent('a') or container.find('a')

            # 如果是 a 标签
            elif container.name == 'a':
                title_elem = container
                link_elem = container

            # 如果是其他容器，查找内部的标题和链接
            else:
                title_elem = container.find(['h3', 'h4', 'h2', 'a'])
                link_elem = container.find('a') or title_elem if title_elem and title_elem.name == 'a' else container.find('a')

            if title_elem and link_elem:
                title = title_elem.get_text(strip=True)
                link = link_elem.get('href')

                # 过滤有效的新闻标题
                if (title and len(title) > 10 and
                    any(keyword in title.lower() for keyword in ['ai', '人工智能', '机器学习', '深度学习', 'chatgpt', 'gpt', 'llm', '大模型', '科技', '技术']) and
                    link and 'http' in link):

                    # 确保链接是完整的 URL
                    if not link.startswith('http'):
                        link = f"https://news.aibase.com{link}" if link.startswith('/') else link

                    news_items.append({
                        'title': title,
                        'link': link
                    })

                    # 限制数量
                    if len(news_items) >= 15:
                        break

        # 如果没找到足够的新闻，尝试另一种方法
        if len(news_items) < 5:
            print("⚠️  标准方法未找到足够新闻，尝试备用方法...")
            all_links = soup.find_all('a', href=True)
            for link in all_links[:50]:  # 检查前50个链接
                title = link.get_text(strip=True)
                href = link['href']

                if (title and len(title) > 20 and  # 增加标题长度要求
                    any(keyword in title.lower() for keyword in ['ai', '人工智能', '机器学习', 'chatgpt', 'gpt', '日报', '新闻']) and
                    ('daily' in href or 'news' in href or 'article' in href)):

                    if not href.startswith('http'):
                        href = f"https://news.aibase.com{href}" if href.startswith('/') else href

                    news_items.append({
                        'title': title[:100] + '...' if len(title) > 100 else title,  # 限制标题长度
                        'link': href
                    })

                    if len(news_items) >= 15:
                        break

        # 如果还是没找到足够新闻，尝试解析页面中的文章内容
        if len(news_items) < 3:
            print("⚠️  备用方法仍未找到足够新闻，尝试解析页面内容...")
            # 查找包含新闻内容的div或section
            content_areas = soup.find_all(['div', 'section', 'article'], class_=lambda x: x and any(word in ' '.join(x).lower() for word in ['content', 'news', 'article', 'post', 'entry']))

            for area in content_areas[:5]:  # 只检查前5个内容区域
                # 在内容区域内查找段落或列表项
                paragraphs = area.find_all(['p', 'li', 'h3', 'h4'])
                for para in paragraphs:
                    text = para.get_text(strip=True)
                    if (text and len(text) > 30 and len(text) < 200 and  # 合适的段落长度
                        any(keyword in text.lower() for keyword in ['ai', '人工智能', '机器学习', 'chatgpt', 'gpt'])):

                        news_items.append({
                            'title': text[:150] + '...' if len(text) > 150 else text,
                            'link': TARGET_URL  # 使用主页链接
                        })

                        if len(news_items) >= 10:  # 降低要求到10条
                            break
                if len(news_items) >= 10:
                    break

        print(f"✅ 成功获取 {len(news_items)} 条新闻")
        return news_items[:15]  # 最多返回15条

    except Exception as e:
        print(f"❌ 爬取失败: {str(e)}")
        raise

# ==================== AI 总结模块 ====================
def summarize_with_ai(news_items):
    """
    使用 Google Gemini 对新闻进行总结
    """
    try:
        print("🤖 开始 AI 总结...")

        # 检查 API 密钥
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("未找到 GOOGLE_API_KEY 环境变量")

        # 配置 Gemini
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        # 准备新闻内容
        news_content = ""
        for i, item in enumerate(news_items, 1):
            news_content += f"{i}. {item['title']}\n   链接: {item['link']}\n\n"

        # 生成总结
        prompt = AI_PROMPT.format(news_content=news_content)
        response = model.generate_content(prompt)

        summary = response.text.strip()
        print("✅ AI 总结完成")
        return summary

    except Exception as e:
        error_msg = str(e)
        print(f"❌ AI 总结失败: {error_msg}")

        # 如果是API相关问题，生成简单的文本总结
        if ("quota" in error_msg.lower() or "429" in error_msg or
            "404" in error_msg or "not found" in error_msg.lower() or
            "unavailable" in error_msg.lower()):
            print("⚠️  API 调用失败，使用简单文本总结...")
            simple_summary = "# AI 每日早报\n\n由于 API 限制，以下是今日 AI 新闻摘要：\n\n"
            for i, item in enumerate(news_items[:8], 1):  # 最多显示8条
                simple_summary += f"{i}. {item['title']}\n🔗 {item['link']}\n\n"
            simple_summary += "\n*注：API 服务暂时不可用，建议稍后重试或升级付费计划*"
            return simple_summary
        else:
            # 对于其他未知错误，仍然抛出异常
            raise

# ==================== 推送模块 ====================
def send_push_notification(title, content):
    """
    发送推送通知到 PushPlus
    """
    try:
        print("📱 开始推送通知...")

        # 检查推送令牌
        token = os.getenv('PUSHPLUS_TOKEN')
        if not token:
            raise ValueError("未找到 PUSHPLUS_TOKEN 环境变量")

        # 准备推送数据
        data = {
            'token': token,
            'title': title,
            'content': content,
            'template': 'markdown'
        }

        # 设置代理
        proxies = {
            'http': 'http://127.0.0.1:21879',
            'https': 'http://127.0.0.1:21879'
        }

        # 发送推送
        response = requests.post(PUSHPLUS_URL, json=data, proxies=proxies, timeout=30)
        response.raise_for_status()

        result = response.json()
        if result.get('code') == 200:
            print("✅ 推送成功")
        else:
            raise ValueError(f"推送失败: {result.get('msg', '未知错误')}")

    except Exception as e:
        print(f"❌ 推送失败: {str(e)}")
        raise

# ==================== 主函数 ====================
def main():
    """
    主函数：串联整个流程
    """
    try:
        print("🚀 AI 每日早报 2.0 开始执行")
        print("=" * 50)

        # 1. 爬取新闻
        news_items = scrape_aibase_news()
        if not news_items:
            raise ValueError("未获取到任何新闻内容")

        # 2. AI 总结
        summary = summarize_with_ai(news_items)

        # 3. 推送通知
        send_push_notification("AI每日早报", summary)

        print("=" * 50)
        print("🎉 AI 每日早报执行完成！")

    except Exception as e:
        print(f"💥 执行失败: {str(e)}")
        sys.exit(1)

# ==================== 程序入口 ====================
if __name__ == "__main__":
    main()
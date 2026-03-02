import os
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai

# ==================== 配置区 ====================
# 直接从环境变量读取，不需要 dotenv
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
PUSHPLUS_TOKEN = os.getenv('PUSHPLUS_TOKEN')
TARGET_URL = "https://news.aibase.com/zh/daily"

def main():
    print("🚀 程序启动...")
    
    # 1. 检查密钥
    if not GOOGLE_API_KEY:
        print("❌ 错误: 缺少 GOOGLE_API_KEY")
        return
    if not PUSHPLUS_TOKEN:
        print("❌ 错误: 缺少 PUSHPLUS_TOKEN")
        return

    # 2. 爬取新闻
    print("🕷️ 正在爬取 AIbase...")
    news_data = ""
    try:
        # 伪装浏览器头
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
        # 不使用任何代理参数，GitHub 会自动直连
        resp = requests.get(TARGET_URL, headers=headers, timeout=30)
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        # 抓取所有链接
        links = soup.find_all('a', href=True)
        
        count = 0
        for link in links:
            text = link.get_text(strip=True)
            href = link['href']
            # 简单的关键词过滤
            if len(text) > 10 and any(k in text.lower() for k in ['ai', 'gpt', '模型', '智能']):
                if not href.startswith('http'):
                    href = f"https://news.aibase.com{href}"
                news_data += f"- {text} {href}\n"
                count += 1
                if count >= 8: break # 只取前8条
        
        if not news_data:
            news_data = "今日未抓取到特定 AI 新闻，请访问官网查看。"
        print(f"✅ 抓取完成，共 {count} 条")

    except Exception as e:
        print(f"❌ 爬虫出错: {e}")
        news_data = f"爬虫发生错误: {str(e)}"

    # 3. AI 总结
    print("🧠 正在请求 Gemini...")
    summary = ""
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"你是科技编辑。请将以下新闻总结为【AI早报】，5条精简内容，emoji开头：\n{news_data}"
        
        response = model.generate_content(prompt)
        summary = response.text
        print("✅ AI 总结完成")
    except Exception as e:
        print(f"❌ AI 出错: {e}")
        summary = f"AI 总结失败，原始内容如下：\n{news_data}"

    # 4. 推送
    print("📨 正在推送...")
    try:
        url = "http://www.pushplus.plus/send"
        data = {
            'token': PUSHPLUS_TOKEN,
            'title': 'AI 每日早报',
            'content': summary,
            'template': 'markdown'
        }
        requests.post(url, json=data, timeout=30)
        print("✅ 推送请求已发送")
    except Exception as e:
        print(f"❌ 推送出错: {e}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
ChatGPT Terminal CLI for Geminisdk / Antigravity workspace.
Usage:
  1. Interactive mode:
     .venv/bin/python chatgpt_cli.py
  2. Single question:
     .venv/bin/python chatgpt_cli.py "Savolingizni shu yerga yozing"
"""

import sys
import os
import dotenv
from openai import OpenAI

# Load environment variables
dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("\033[91m[XATO] OPENAI_API_KEY .env faylida topilmadi!\033[0m")
    sys.exit(1)

client = OpenAI(api_key=api_key)

SYSTEM_PROMPT = {
    "role": "system",
    "content": "Siz qulay, bilimdon va do'stona Sun'iy Intellekt yordamchisiz. O'zbek tilida aniq va chiroyli javob bering."
}

def ask_single_question(question: str):
    print(f"\033[96m🤖 ChatGPT o'ylamoqda...\033[0m\n")
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[SYSTEM_PROMPT, {"role": "user", "content": question}],
            temperature=0.7,
        )
        answer = response.choices[0].message.content
        print(f"\033[92m🤖 ChatGPT:\033[0m\n{answer}\n")
    except Exception as e:
        print(f"\033[91m[XATO]: {e}\033[0m")

def interactive_chat():
    print("\033[95m====================================================\033[0m")
    print("\033[95m    🤖 ChatGPT Terminal CLI (GPT-4o-mini)          \033[0m")
    print("\033[95m    Chiqish uchun 'exit' yoki 'q' deb yozing        \033[0m")
    print("\033[95m====================================================\033[0m\n")
    
    messages = [SYSTEM_PROMPT]
    
    while True:
        try:
            user_input = input("\033[93mSiz > \033[0m").strip()
            if not user_input:
                continue
            if user_input.lower() in ['exit', 'quit', 'q', 'chiqish']:
                print("\033[94mSuhbat yakunlandi. Xayr!\033[0m")
                break
            
            messages.append({"role": "user", "content": user_input})
            print("\033[96m🤖 ChatGPT o'ylamoqda...\033[0m")
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.7,
            )
            
            answer = response.choices[0].message.content
            messages.append({"role": "assistant", "content": answer})
            
            print(f"\n\033[92m🤖 ChatGPT:\033[0m\n{answer}\n")
            print("-" * 50)
        except (KeyboardInterrupt, EOFError):
            print("\n\033[94mSuhbat yakunlandi. Xayr!\033[0m")
            break
        except Exception as e:
            print(f"\033[91m[XATO]: {e}\033[0m\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        ask_single_question(question)
    else:
        interactive_chat()

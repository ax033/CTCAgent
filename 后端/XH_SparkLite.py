import requests
# -*- coding: utf-8 -*-
import base64
import os
import io
import tempfile
from elasticsearch_dsl import connections, Text, Search, Q
import json
from fastapi import FastAPI, Request,File, UploadFile,Form,HTTPException
# from starlette.responses import FileResponse
# web服务器
import uvicorn
from pydantic import BaseModel, Field
from typing import List,Optional
import requests
import time
import logging

# from demo import ocr_process
"""放在ORC文件里，才没有冲突"""
import uuid
class Attachment(BaseModel):
    id: str
    type: str

class BotChat(BaseModel):
    role: str
    content: str
    attachments: List[Attachment] = []

class ChatRequest(BaseModel):
    openid: str
    chat_id: int
    message: List[BotChat]

class ChatMessage(BaseModel):
    """通原课堂返回响应的数据格式"""
    chat_id: int
    content: str
    attachments: List[Attachment] = []

class Token(BaseModel):
    """access_token接口返回的数据结构"""
    access_token: str
    expire: int  # 多少秒后过期

token_pool={
    "ori_token":{
        # 普通的token和到期时间
        "access_token":None,
        "expires_at": 0.0
    },
    "model_token": {
        # 大模型的token（其实就是测试服务器的token）和到期时间
        "access_token": None,
        "expires_at": 0.0
    }
}
# 初始化 FastAPI 应用
app = FastAPI()


# # 定义请求体模型
# class ChatRequest(BaseModel):
#     content: str


@app.get('/')
async def root():
    return {"message":"hello"}

# 定义 FastAPI 路由
@app.post("/chat")
async def chat_with_api(request: Request):
    try:
        request_data = await request.json()  # 获取 JSON 数据并转化为字典
        # chat_request = ChatRequest(**request_data)  # 使用解包操作将字典传递给 ChatRequest 构造函数
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    quetions = request_data["message"]

    url = "https://spark-api-open.xf-yun.com/v1/chat/completions"
    data = {
        "max_tokens": 4096,
        "top_k": 4,
        "temperature": 0.5,
        "messages": [
            {
                "role": "user",
                "content": quetions  # 从请求体获取用户输入内容
            }
        ],
        "model": "lite",
        "stream": True  # 开启流式传输
    }

    header = {
        "Authorization": "Bearer NdciCklGdVWUqeXKtIuh:SXDEYQFdRwrZnCnXNtVt"
    }

    try:
        # 发送 POST 请求
        response = requests.post(url, headers=header, json=data, stream=True)
        response.encoding = "utf-8"

        # 初始化空字符串存储完整响应
        full_response = ""

        # 解析流式响应
        for line in response.iter_lines(decode_unicode=True):
            # 忽略 '[DONE]' 行
            if line == 'data: [DONE]':
                continue

            # 移除 'data: ' 前缀
            line = line.replace('data: ', '')
            try:
                if line != '"' :
                    # 解析 JSON 数据
                    data = json.loads(line)

                    # 累积 content 字段
                    full_response += data['choices'][0]['delta'].get('content', '')

            except json.JSONDecodeError as e:
                print("error")

        response_data = ChatMessage(
            chat_id= 0,  # 替换为实际的对话 ID
            content=full_response,
            attachments=[]
        )
        return response_data

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Request failed: {e}")

if __name__ == '__main__':
    uvicorn.run(app, host="127.0.0.1", port=9453)  # 第一个参数要写这个python脚本的名字，reload就是是否自动刷新
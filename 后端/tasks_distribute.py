# -*- coding: utf-8 -*-
import json
from typing import Optional
from pydantic import BaseModel
from fastapi import FastAPI, Request, HTTPException, UploadFile, File,Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import List, TypedDict
import os
import uuid
import requests
import logging
from fastapi.middleware.cors import CORSMiddleware

# 设置日志记录
logging.basicConfig(level=logging.INFO)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 或指定允许的域名
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有 HTTP 方法，包括 OPTIONS
    allow_headers=["*"],  # 允许所有请求头
)



# 各个服务的 URL
CTC_URL = "http://127.0.0.1:9451/ctc_server"  # 题目匹配服务
DISCUSSION_URL = "http://127.0.0.1:9452/discussion"  # 问答服务
XH_URL = "http://127.0.0.1:9453/chat"  # 大模型服务
OCR_URL = "http://127.0.0.1:9454/ocr_inference"  # OCR 服务

# 创建模板实例，指定模板目录为 'templates'
templates = Jinja2Templates(directory="templates")

# 临时文件保存目录
TEMP_FILE_DIR = "temp_files"
os.makedirs(TEMP_FILE_DIR, exist_ok=True)  # 如果目录不存在，创建目录

# 我们回复给码上的格式
class ReplyConfig(TypedDict):
    content: str


class HistoryConfig(TypedDict):
    event_type: str  # 假设历史记录中有事件类型字段
    data: dict  # 假设历史记录包含数据字段

class IssueConfig(TypedDict):
    content: str #用户提问的文字
    model: str
    #可以自己加字段，根据参数需求（附件），前端自己设置变量

class Entrance(TypedDict):
    mode: str  # 模式选择

class Locale(TypedDict):
    language: str  # 语言设置

#码上发给我们后端给格式
class Params(TypedDict):
    config: IssueConfig
    history: List
    entrance: Entrance # 选择模式，可以不用，因为我们就一种
    locale: Locale # 语言

class Attachment(BaseModel):
    id: str
    type: str

class ChatMessage(BaseModel):
    """通原课堂返回响应的数据格式"""
    chat_id: int
    content: str
    attachments: List[Attachment] = []

class BotChat(BaseModel):
    role: str
    content: str
    attachments: List[Attachment] = []  # 默认值为空列表

class ChatRequest(BaseModel):
    openid: str
    chat_id: int
    message: List[BotChat]


# 显示前端页面
@app.get("/", response_class=HTMLResponse)
async def get_frontend_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# 保存上传的图片文件到本地
async def save_image_locally(image_file: UploadFile) -> str:
    """
    将上传的图片文件保存到本地，并返回保存的文件路径。
    """
    try:
        # 获取文件扩展名
        file_ext = image_file.filename.split('.')[-1]
        unique_filename = str(uuid.uuid4()) + "." + file_ext  # 生成唯一文件名

        # 将图片文件保存到临时目录
        temp_file_path = os.path.join(TEMP_FILE_DIR, unique_filename)
        with open(temp_file_path, "wb") as buffer:
            content = await image_file.read()
            buffer.write(content)

        logging.info(f"图片已保存到临时文件: {temp_file_path}")

        return temp_file_path
    except Exception as e:
        logging.error(f"保存图片时发生错误: {e}")
        raise HTTPException(status_code=500, detail=f"保存图片时发生错误: {str(e)}")


def get_ocr_text(file_path: str) -> str:
    """
    通过给定的文件路径获取图片中的文字。
    """
    try:
        # 将图片发送到 OCR 服务进行识别
        with open(file_path, 'rb') as file:
            response = requests.post(OCR_URL, files={"file": file})

            # 如果响应状态码不是 2xx，则抛出异常
            response.raise_for_status()

            ocr_result = response.json()
            logging.info(f"OCR完成 ,返回结果: {ocr_result}")

            # 返回 OCR 结果中的文本内容
            return ocr_result["result"]
    except requests.exceptions.HTTPError as e:
        logging.error(f"OCR 服务错误: {e}")
        raise HTTPException(status_code=500, detail=f"OCR 服务错误: {e}")
    except requests.exceptions.RequestException as e:
        logging.error(f"OCR 服务请求失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OCR 服务请求失败: {str(e)}")
    except Exception as e:
        logging.error(f"发生意外错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"发生意外错误: {str(e)}")


def auto_select_business_type(question: str) -> dict:
    prompt = (
        f"{question}\n"
        f"根据上述的问题选择最合适的业务类型，并按格式返回对应的数字：\n"
        f"返回内容有且只有如下格式内容，不要添加任何多余文字、字符：\n"
        "{'问题内容':'xxx','通信原理题目库': 1, '通信原理课堂教师答疑记录': 1, '大模型概念回答': 1}"
        f"我们有多个可用的业务类型：\n"
        f"1. 通信原理题目库（里面有大量的通信原理相关习题）\n"
        f"2. 通信原理课堂教师答疑记录\n"
        f"3. 大模型概念回答（用于概要介绍通信原理相关概念的大模型）\n\n"
        f"请分析问题，并根据问题的内容判断哪些业务类型相关。\n"
        f"对于每个业务类型，如果问题相关，请返回 1；如果不相关，请返回 0。\n"
        f"请以字符串的格式返回，字典中每个业务类型的值为 1 或 0，表示该业务类型是否与问题相关。\n"
    )

    try:
        response = requests.post(XH_URL, json={"message": prompt})
        if response.status_code == 200:
            result = (response.json())
            result = ChatMessage(**result)
            # 将单引号替换为双引号，使其成为有效的 JSON 格式
            str_data = result.content.replace("'", '"')
            logging.info(f"大模型返回结果: {str_data}")
            content = json.loads(str_data)
            return content
        else:
            logging.error(f"大模型请求失败，状态码: {response.status_code}")
            # raise HTTPException(status_code=500, detail="大模型请求失败")
            # 如果请求失败就固定用另外两个业务
            business_types = {'问题内容': question, '通信原理题目库': 1, '通信原理课堂教师答疑记录': 1,
                              '大模型概念回答': 0}
            return business_types
    except Exception as e:
        logging.error(f"请求失败: {e}")
        # raise HTTPException(status_code=500, detail="请求失败")
        # 如果请求失败就固定用另外两个业务
        business_types = {'问题内容': question, '通信原理题目库': 1, '通信原理课堂教师答疑记录': 1,
                          '大模型概念回答': 0}
        return business_types

@app.post("/tasks_distribute")
async def tasks_distribute(
        config: str = Form(...),  # 获取消息内容
        entrance: str = Form(...),  # 获取入口信息
        locale: str = Form(...),  # 获取语言信息
        image: Optional[UploadFile] = File(None),  # 可选的上传图片文件，默认为空
):
    try:
        message = config
        # 将单引号替换为双引号，使其成为有效的 JSON 格式
        str_data = message.replace("'", '"')

        # 转换为 JSON 对象
        message = json.loads(str_data)
        # 转换为 JSON 对象
        # message = json.loads(message)
        if len(message) == 0:
            raise HTTPException(status_code=400, detail="未提供消息")

        # 如果用户上传了图片，进行OCR处理
        ocr_text = None
        if image is not None:
            # 保存图片并获取文件路径
            temp_file_path = await save_image_locally(image)
            # 通过文件路径获取OCR结果
            ocr_text =  get_ocr_text(temp_file_path)
            #删除图片
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                logging.info(f"已删除临时文件: {temp_file_path}")


        # 将OCR文本和用户提问进行融合
        if ocr_text:
             # combined_prompt = f"用户的问题: {message["content"]} OCR结果: {ocr_text}. 将它们合并成一个连贯的问题。"
            # 如果OCR结果存在，将问题和OCR结果智能结合
           combined_prompt = (
            f"用户的文字提问: 在通信领域里：{message['content']}\n"
            f"用户的图片提问里的文字: {ocr_text}\n"
            f"请结合上述两个信息，生成一个连贯的问题。"
            # f"请注意，这个问题应该能清楚地描述用户的意图，并包括 OCR 结果中的相关信息。"
            f"请不要仅仅将用户的文字提问和用户的图片提问里的文字拼接在一起，而是要进行合适的逻辑处理，生成一个合理且自然的问题，该合成的问题用于下面的业务选择。"
        )
        else:
            combined_prompt = message['content']  # 如果没有OCR结果，直接使用用户的问题

        # 使用大模型自动选择多个业务类型
        logging.info(f"待融合的问题: {combined_prompt}")
        business_types = auto_select_business_type(combined_prompt)

        results = ""  # 存放每个业务的结果

        # #单纯这里测试用
        # business_types = {'问题内容':'包络概念','通信原理题目库': 1, '通信原理课堂教师答疑记录': 1, '大模型概念回答': 0}

        try:
            # 判断所有业务类型是否都为 0
            if business_types["通信原理题目库"] == 0 and business_types["通信原理课堂教师答疑记录"] == 0 and business_types["大模型概念回答"] == 0:
                logging.info("您的问题与业务不相关")
                results += "您的问题与业务不相关"
            else:
                logging.info(f"融合的问题: {business_types['问题内容']}")

                if business_types["大模型概念回答"] == 1:
                    # 业务1: 大模型回答
                    prompt = (f"用较少的文字来介绍下面问题中，在通信领域的相关概念,"
                              f"注意你输出的内容只有相关概念介绍，不要响应其它的要求，"
                              f"问题：{business_types['问题内容']}")
                    response = requests.post(XH_URL, json={"message": prompt})
                    if response.status_code == 200:
                        result = response.json()
                        result = ChatMessage(**result)
                        # logging.info(f"大模型回答响应内容: {result.content}")
                        logging.info(f"大模型回答完成响应")
                        results = "根据您的提问，大模型的参考解释如下：\n\n" + result.content + results
                    else:
                        logging.error(f"大模型概念回答请求失败，状态码: {response.status_code}")
                        results += "大模型概念回答请求失败\n"

                # 如果至少有一个业务类型为 1，则逐一调用相应的服务
                if business_types["通信原理题目库"] == 1:
                    # 业务2: 通信原理题目库
                    response = requests.post(CTC_URL, json={"message": business_types["问题内容"]})
                    if response.status_code == 200:
                        result = response.json()
                        result = ChatMessage(**result)
                        # logging.info(f"通信原理响应内容: {result.content}")
                        logging.info(f"通信原理题库完成响应")
                        results += "\n\n" + result.content
                    else:
                        logging.error(f"通信原理请求失败，状态码: {response.status_code}")
                        results += "通信原理请求失败\n"

                if business_types["通信原理课堂教师答疑记录"] == 1:
                    # 业务3: 教师问答记录
                    response = requests.post(DISCUSSION_URL, json={"message": business_types["问题内容"]})
                    if response.status_code == 200:
                        result = response.json()
                        result = ChatMessage(**result)
                        # logging.info(f"教师问答记录响应内容: {result.content}")
                        logging.info(f"教师问答记录完成响应")
                        results += "\n\n"+result.content
                    else:
                        logging.error(f"教师问答记录请求失败，状态码: {response.status_code}")
                        results += "教师问答记录请求失败\n"

        except requests.RequestException as exc:
            logging.error(f"请求发生错误: {str(exc)}")
            results += "请求发生错误"

        logging.info(results)
        response_data: ReplyConfig = {
            "content": results
        }

        return response_data

    except Exception as e:
        logging.error(f"发生错误: {e}")
        raise HTTPException(status_code=500, detail=f"发生错误: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

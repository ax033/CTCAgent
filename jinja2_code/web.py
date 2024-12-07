# -*- coding: utf-8 -*-
from fastapi import FastAPI, Request, HTTPException, File, UploadFile
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uuid
from PIL import Image
import uvicorn
import logging
import os
import io
from apscheduler.schedulers.background import BackgroundScheduler

# 设置日志记录
logging.basicConfig(level=logging.INFO)
app = FastAPI()

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")

# 使用 Jinja2Templates 渲染 HTML 模板
templates = Jinja2Templates(directory="templates")

# 静态文件目录
IMAGE_FOLDER = "./static/images/"
os.makedirs(IMAGE_FOLDER, exist_ok=True)


# 返回前端 HTML 页面
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# 接收上传的图片
@app.post("/upload_image")
async def save_image(image_file: UploadFile = File(...)):
    """
    接收上传的图片，强制保存为 PNG 格式，并存储到 IMAGE_FOLDER。
    返回文件的唯一访问路径。
    """
    try:
        # 生成唯一的 PNG 文件名
        unique_filename = f"{uuid.uuid4()}.png"
        temp_file_path = os.path.join(IMAGE_FOLDER, unique_filename)

        # 读取上传的图片并转换为 PNG 格式
        content = await image_file.read()
        image = Image.open(io.BytesIO(content))
        image = image.convert("RGBA")  # 确保兼容 PNG 的格式

        # 保存图片为 PNG 格式到目标路径
        image.save(temp_file_path, format="PNG")

        logging.info(f"图片已保存为 PNG 格式: {temp_file_path}")

        return {"store_path": temp_file_path}
    except Exception as e:
        logging.error(f"保存图片时发生错误: {e}")
        raise HTTPException(status_code=500, detail=f"保存图片时发生错误: {str(e)}")

# 定时清空图片文件夹的任务
def clear_image_folder():
    try:
        for filename in os.listdir(IMAGE_FOLDER):
            file_path = os.path.join(IMAGE_FOLDER, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
                logging.info(f"已删除文件: {file_path}")
    except Exception as e:
        logging.error(f"清空图片文件夹时发生错误: {e}")


# 设置定时器，每 12 小时清空一次 IMAGE_FOLDER
scheduler = BackgroundScheduler()
scheduler.add_job(clear_image_folder, 'interval', hours=12)
scheduler.start()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8082) #0.0.0.0

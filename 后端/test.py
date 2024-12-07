import requests
import json
import time


# 测试参数
message = {
    "content": "什么是包络"
}

entrance = "communication_exam"  # 模式选择
locale = "zh"  # 语言设置
image_path = "images/test_image.png"  # 如果需要测试 OCR，指定图片路径

# 请求的 URL
url = "http://127.0.0.1:8000/tasks_distribute"

# 准备文件和数据
files = {
    "image": open(image_path, "rb")  # 打开并上传图片文件
}
files_empty = {
    "image": ""  # 打开并上传图片文件
}
data = {
    "message": json.dumps(message),  # 将消息字典转为JSON字符串
    "entrance": entrance,
    "locale": locale
}
# 记录程序开始时间
start_time = time.time()
try:
    # 发送 POST 请求
    response = requests.post(url, data=data, files=files)#有图片版本
    # response = requests.post(url, data=data)#无图片版本
    # 处理响应
    if response.status_code == 200:
        print(f"成功：{response.json()}")
    else:
        print(f"请求失败，状态码：{response.status_code}")
        print(f"响应内容：{response.text}")
except Exception as e:
    print(f"请求发生错误：{str(e)}")
finally:
    # 确保文件被关闭
    files["image"].close()
# 记录程序结束时间
end_time = time.time()
# 计算运行时间
print("----------------------------------------------------")
execution_time = end_time - start_time
print(f"程序运行时间: {execution_time} 秒")


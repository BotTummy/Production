# ใช้ Python image ที่เป็น lightweight
FROM python:3.9-slim

# ตั้งค่า working directory
WORKDIR /app

# คัดลอกไฟล์ requirements.txt และติดตั้ง dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# คัดลอกโปรเจกต์ทั้งหมดลงใน container
COPY . .

# กำหนด environment variables
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_ENV=production

# เปิดพอร์ตที่ต้องการสำหรับ Flask
EXPOSE 5000

# คำสั่งสำหรับรัน Flask
CMD ["flask", "run"]

# ใช้ Python image ที่เป็น lightweight
FROM python:3.9

# ติดตั้ง dependencies ที่จำเป็นสำหรับ mysqlclient
RUN apt-get update && apt-get install -y \
    pkg-config \
    libmariadb-dev \
    && rm -rf /var/lib/apt/lists/*

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
ENV FLASK_ENV=masterpallet

# เปิดพอร์ตที่ต้องการสำหรับ Flask
EXPOSE 5000

# คำสั่งสำหรับรัน Flask
CMD ["flask", "run"]

# EcoBot

Discord bot สำหรับบันทึกรายรับ-รายจ่าย และจัดกลุ่มข้อมูลเป็น Session / Set

## Features

- บันทึกรายรับด้วย `!รับ`
- บันทึกรายจ่ายด้วย `!จ่าย`
- ดูสรุป Session ปัจจุบันด้วย `!สรุป`
- เริ่ม Session ใหม่ด้วย `!newday`
- ลบ Session ที่จบแล้วด้วย `!delsession`
- สร้างและจัดการ Set สำหรับรวมหลาย Session
- เปิดดูสรุป Set ผ่านห้อง Discord ชั่วคราว
- ห้อง Set ชั่วคราวลบอัตโนมัติหลัง 15 นาที
- ป้องกันการบันทึกรายการซ้ำจากข้อความ Discord เดิม
- ใช้ SQLite เป็นฐานข้อมูล
- มีคำสั่ง `!clearall` พร้อมการยืนยันก่อนล้างข้อมูล

## Commands

| Command | Description |
|---|---|
| `!รับ <จำนวน> <รายละเอียด>` | บันทึกรายรับ |
| `!จ่าย <จำนวน> <รายละเอียด>` | บันทึกรายจ่าย |
| `!สรุป` | ดูสรุป Session ปัจจุบัน |
| `!newday [Set]` | จบ Session เดิมและเริ่ม Session ใหม่ |
| `!delsession <ID>` | ลบ Session ที่จบแล้ว |
| `!newset <ชื่อ>` | สร้าง Set ใหม่ |
| `!set <เลขหรือชื่อ>` | ผูก Session ปัจจุบันกับ Set |
| `!setname <เลขหรือชื่อ> <ชื่อใหม่>` | เปลี่ยนชื่อ Set |
| `!showset <เลขหรือชื่อ>` | เปิดสรุป Set ในห้องชั่วคราว |
| `!hideset [เลขหรือชื่อ]` | ปิดห้อง Set ชั่วคราว |
| `!clearall` | ล้างข้อมูลทั้งหมดหลังยืนยัน `CONFIRM` |
| `!help` / `!?` | แสดงรายการคำสั่ง |

## Requirements

- Python 3.12+
- Discord Bot
- Discord bot permission: `View Channels`, `Send Messages`, `Read Message History`, `Manage Channels`

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

สร้างไฟล์ `.env` ในโฟลเดอร์โปรเจกต์:

```env
DISCORD_TOKEN=your_bot_token_here
```

> อย่า commit `.env` หรือ Discord bot token ลง Git

## Run

```bash
python bot.py
```

เมื่อเริ่มครั้งแรก EcoBot จะสร้าง `finance.db` ให้อัตโนมัติ

## Data

ข้อมูลถูกเก็บใน SQLite ที่ไฟล์ `finance.db` โดยมี Session, Transaction, Set และข้อมูลห้อง Set ชั่วคราว

ไฟล์ฐานข้อมูลถูกตั้งค่าให้ไม่ถูก commit ขึ้น Git ผ่าน `.gitignore`

## Project Structure

```text
EcoBot/
├── bot.py
├── database.py
├── requirements.txt
├── .gitignore
├── README.md
└── finance.db          # generated locally, ignored by Git
```

## License

ยังไม่ได้กำหนด License

# Python Clean Architecture — FastAPI + React

Python port ของ [Golang Clean Architecture template](https://github.com/max38/golang-clean-code-architecture)
สำหรับโจทย์ Software Engineer ของ Khaojai IT ใช้ FastAPI, SQLAlchemy async, PostgreSQL,
Alembic และ React/TypeScript มี Register, Login, JWT, Profile, Refresh token, Logout
และ API read/list/describe พร้อม owner/admin permissions

## โครงสร้างโค้ด

```text
backend/
  app/
    domain/
      entities/user.py          User ไม่ผูกกับ DB หรือ HTTP
      entities/auth.py          TokenPair และ UserSession
      user_repository.py        Repository Protocol
      errors.py                 Application errors
    usecases/
      usecease_auth.py          Register/Login/Profile/JWT/Refresh/Logout
      data.py                   Read/list/describe และ scope ของสิทธิ์
    interface/http/
      dependencies.py           Bearer token, inject repository, HTTP errors
      routes/auth.py            Auth controllers
      routes/data.py            Data controllers
      schemas/auth.py           Pydantic request/response DTO
    infrastructure/
      database/connector.py     Engine, session factory, lifecycle
      database/session.py       DB session ต่อ request
      database/models/          SQLAlchemy models
      database/user_repository.py  PostgreSQL implementation
      mapper/user_mapper.py     SQL model ↔ domain entity
    config/settings.py          อ่าน backend/.env ด้วย prefix FASTAPIAPP_
    main.py                     ประกอบ app, CORS และ routes
  migrations/                   Alembic revisions
  tests/                        Unit/API และ PostgreSQL integration tests
frontend/
  src/pages/                    Login, Register, Profile
  src/components/AuthLayout.tsx กรอบร่วมของฟอร์ม
  src/api.ts                    API URL, errors, token storage และ refresh
  src/App.tsx                   React Router routes
```

domain/usecases ไม่ import FastAPI หรือ SQLAlchemy Usecase รับ UserRepository Protocol
และ HTTP dependency สร้าง PostgresUserRepository ให้ จึงแทน DB ด้วย fake repository ใน tests ได้
Repository จัดการ transaction; mapper แยก ORM ออกจาก entity; DTO จำกัดข้อมูล HTTP response

```text
Register: JSON → UserCreate → register_user → repository → users table
          → mapper → User → UserRead → HTTP 201
Profile:  HTTPBearer → authenticate_user → ตรวจ JWT และ session ใน DB
          → get_profile → repository → User → UserRead → HTTP 200
```

## ติดตั้งจาก clone ใหม่

ต้องมี Git, Docker Desktop ที่เปิดอยู่, uv และ Node.js ทดสอบด้วย Python 3.12 และ Node 24
ตัวอย่างใช้ Windows CMD จาก root ของ repository

```cmd
git clone https://github.com/EqrthX/golang-clean-code-architecture.git
cd golang-clean-code-architecture
copy backend\env.demo backend\.env
copy frontend\.env.example frontend\.env.local
cd backend
uv sync --frozen --link-mode copy
uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
```

นำค่าที่สุ่มได้ใส่ FASTAPIAPP_SECRET_KEY ใน backend/.env และตั้ง DB user/password/name
สำหรับ environment ของคุณ ค่าใน env.demo เป็นตัวอย่างให้แก้ก่อนใช้จริง
settings.py คำนวณ path ของ .env จากตำแหน่งไฟล์ จึงไม่ผูกกับชื่อโฟลเดอร์เดิม
อายุ access token ใช้ FASTAPIAPP_JWT_ACCESS_EXPIRES เป็นนาที; refresh ใช้
FASTAPIAPP_JWT_REFRESH_EXPIRES เป็นวัน

เปิด PostgreSQL และ API:

```cmd
cd ..
docker compose --env-file backend/.env up -d db
cd backend
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

เปิด terminal อีกหน้าต่างจาก root ของ repo:

```cmd
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Frontend: http://127.0.0.1:5173 — Swagger: http://127.0.0.1:8000/docs
frontend/.env.local ใช้ VITE_API_URL=http://127.0.0.1:8000; เปลี่ยนแล้ว restart Vite
Docker รัน DB ส่วน backend/frontend รันบนเครื่อง host/port ของ Uvicorn กำหนดผ่าน CLI

หากเคยคัดลอก .venv จากโฟลเดอร์อื่น ให้ปิด server แล้วสร้างใหม่จาก backend:

```cmd
uv venv --clear --python 3.12 .venv
uv sync --frozen --link-mode copy
```

## ฟีเจอร์และ API

| API | Request / ผลลัพธ์ |
| --- | --- |
| GET /health | ชื่อ/เวอร์ชัน API; liveness ไม่ใช่ DB readiness |
| POST /register | name/email/password; 201, อีเมลซ้ำ 409, input ผิด 422 |
| POST /login | email/password; access_token, refresh_token, token_type |
| GET /profile | Bearer access token; UserRead หรือ 401 |
| GET /protected | Bearer access token; user_id หรือ 401 |
| POST /refresh-token | JSON refresh_token; หมุน token pair |
| POST /logout | JSON refresh_token; revoke session แล้วคืน 204 |
| GET /data/{resource}/describe | Bearer token; public field schema |
| GET /data/{resource}/ | Bearer token; _page และ _pageSize (1–100) |
| GET /data/{resource}/{id} | Bearer token; รายตัว หรือ 404 |

Auth มี aliases /api/v1/users/* และ Data มี /api/v1/data/* เช่น Go
Profile รับ POST เป็น alias ของ GET ด้วย
UserRead ส่ง id/name/email/created_at/updated_at ไม่มี password/hash
รหัสผ่านใช้ bcrypt: อย่างน้อย 8 ตัวอักษร ไม่เกิน 72 UTF-8 bytes

JWT ใช้ HS256 และบังคับ exp/sub/sid/type; refresh มี jti และใช้แทน access token ไม่ได้
DB เก็บ SHA-256 hash ของ refresh token Refresh ใช้ compare-and-swap เพื่อป้องกันการใช้ซ้ำ
และการแข่งขันสอง requests โดยวันหมดอายุ session ยึดค่าเดิม Logout revoke ทั้ง access/refresh
ของ session นั้น Login หลายครั้งได้คนละ session บัญชีเดิมยังอยู่หลัง migration แต่ต้อง Login ใหม่
เพื่อรับ token ที่มี session

Read API ใช้ allowlist users/user_tokens/user_permissions ผู้ใช้ทั่วไปอ่านได้เฉพาะข้อมูลตนเอง
admin อ่านทั้งชุดได้ บัญชีใหม่และบัญชีเดิมจาก migration ได้ permission user
API สมัครสมาชิกไม่รับ role; read API ไม่ส่ง password, refresh hash หรือ raw tokens
หากจะทดสอบ admin ให้ผู้ดูแล DB กำหนดเฉพาะบัญชีทดสอบที่เลือกเอง:

```sql
UPDATE user_permissions SET permission = 'admin'
WHERE user_id = (SELECT id FROM users WHERE email = 'reviewer@example.com');
```

ลองใช้ frontend ตาม flow Register → Login → Profile → refresh หน้า → Logout
frontend ต่ออายุ access token เมื่อได้ 401 และแสดง loading/error พร้อมปุ่มลองใหม่

## ทดสอบ

จาก backend:

```cmd
uv run pytest -q
uv run ruff check app tests migrations
uv run alembic check
```

Unit/API tests ใช้ fake repository ส่วน PostgreSQL integration tests เปิดด้วย:

```cmd
set RUN_DB_TESTS=1
uv run pytest -q
set RUN_DB_TESTS=
```

ทดสอบ migration จาก schema ว่าง, downgrade/upgrade, Register/Login/Profile,
owner/admin permissions, concurrent refresh และ Logout ใน schema UUID แยก แล้วลบเฉพาะ
schema ทดสอบ Registration integration test ใช้อีเมล UUID และลบเฉพาะข้อมูลนั้น
มีเคส validation/null, อีเมลซ้ำ, bcrypt Unicode boundary, token ลายเซ็นผิด/หมดอายุ/ชนิดผิด,
ID ผิด, ผู้ใช้หาย, session revoked และ transaction rollback

จาก frontend ใช้ npm run build และ npm run lint

## ขอบเขตและการปรับจาก Go

- DTO ใช้ name แทน first_name/last_name และ token response เป็นรูปแบบที่ระบุข้างบน
- เพิ่ม owner/admin enforcement; Go รับ permission เข้า usecase แต่ยังไม่ได้กรองข้อมูล
- Read API ใช้ public field schema แทน reflection/Avro และใช้ resource allowlist 3 models
- Generic create/update/delete ใน Go เป็น placeholder และไม่มี HTTP routes จึงไม่เพิ่ม endpoint
- MongoDB connector เป็นตัวเลือกเสริม ยังไม่มี business model เปิดด้วย
  docker compose --env-file backend/.env --profile mongodb up -d
  และ FASTAPIAPP_MONGODB_ENABLED=true; users/sessions/permissions ใช้ PostgreSQL
- frontend เก็บ tokens ใน localStorage; hosting ต้อง fallback ไป index.html สำหรับ frontend URLs
- มีการใช้ AI ช่วย implementation, debugging และ tests ขอบเขตและ flow อธิบายไว้ในเอกสารนี้

ต้นฉบับอยู่ใน Git history และเก็บ LICENSE เดิม .env/.venv/node_modules/dist/caches ถูก ignore
ส่ง source, lockfiles, env examples และเอกสาร พร้อม Resume ตามประกาศ

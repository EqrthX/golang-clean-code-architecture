# React frontend

รายละเอียดสถาปัตยกรรม/API และการติดตั้ง backend อยู่ใน [README หลัก](../README.md)

```cmd
copy .env.example .env.local
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

VITE_API_URL ใน .env.local ชี้ backend เปลี่ยนแล้ว restart Vite

- /login: บันทึก token pair แล้วไป Profile
- /register: ตรวจรหัสผ่านยืนยัน พร้อม loading และ validation/duplicate errors
- /profile: โหลด name/email, refresh access token เมื่อได้ 401 และ Logout
- /: redirect ไป Login; URL ที่ไม่มี route แสดงหน้า 404

App.tsx กำหนด routes และ AuthLayout ใช้ Outlet สำหรับฟอร์ม Login/Register
api.ts รวม URL, token storage, errors และ refresh request ที่แชร์กันภายใน tab
Profile ใช้ AbortController cleanup เมื่อออกจากหน้าและใน StrictMode

ตรวจด้วย npm run build และ npm run lint
ลอง Register→Login→Profile→refresh หน้า→Logout, อีเมลซ้ำ, รหัสผ่านผิด,
ปิด backend แล้วส่งฟอร์ม และเข้าหน้า Profile โดยไม่มี token
loading ต้องหยุดเมื่อเกิด error และปุ่มฟอร์มต้องกลับมาใช้งานได้
